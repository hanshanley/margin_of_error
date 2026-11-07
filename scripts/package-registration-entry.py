"""Reproduce broad registration-date descriptives, not first-time-voter estimates."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-registration-entry/{VERSION}"
PUBLIC = f"public/participation-registration-entry/{VERSION}"
INPUT_SHA256 = "c42d6fa217dbf005f374719f2c4fa2233417a4a9b0c3eb24ef3dad0fab2f338e"
FIELDS = {"county", "accepted_cohort", "post_2024_registration",
          "positive_2024_nc_history", "no_2024_nc_history_found"}
SCOPE = {
    "state": "NC", "cohort_election": "2026-11-03",
    "accepted_status": "ACCEPTED", "accepted_methods": ["EARLY VOTING", "MAIL"],
    "registration_field": "registr_dt", "registration_after_exclusive": "2024-11-05",
    "registration_through_inclusive": "2026-11-03", "history_election": "2024-11-05",
    "history_search": "statewide_NC_general_election",
    "deduplication": "exclude_every_record_for_ambiguous_identifiers",
}
LIMITS = [
    "The date on the current registration record is not a first-ever registration date.",
    "Registration after 2024 can include movers or re-registrations with prior participation.",
    "No 2024 North Carolina history match leaves national participation unresolved.",
    "Accepted early/mail records are not all-mode final turnout or proof of a counted ballot.",
    "The registration/history snapshots precede Election Day; the accepted snapshot is later.",
    "Unmatched registration dates and all other dates remain outside the selected date interval.",
    "No candidate choice, first-time-voter count, staying-home count or turnout rate is inferred.",
    "These two selected counties do not estimate North Carolina or nationwide entry.",
    "No individual records, fine joint cells, identities or individual scores are released.",
]


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def reviewed_row(row):
    if set(row) != FIELDS or row["county"] not in ("WAKE", "MECKLENBURG"):
        raise ValueError("Require the selected broad county row, without private or extra fields")
    if any(type(row[key]) is not int or row[key] < 1000 for key in FIELDS - {"county"}):
        raise ValueError("Require integer, disclosure-qualified broad counts")
    if (row["positive_2024_nc_history"] + row["no_2024_nc_history_found"]
            != row["post_2024_registration"]
            or row["post_2024_registration"] > row["accepted_cohort"]):
        raise ValueError("Date/history groups must partition their own selected cohort")
    return {
        **row,
        "post_registration_share_of_accepted_pct":
            100 * row["post_2024_registration"] / row["accepted_cohort"],
        "positive_history_share_of_post_registration_pct":
            100 * row["positive_2024_nc_history"] / row["post_2024_registration"],
    }


def select_private(directory):
    audit = json.loads((directory / "audit.json").read_bytes())
    raw = (directory / "joint-cells.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != audit["joint_cells_sha256"]:
        raise ValueError("Private cells differ from the qualified linkage audit")
    row = {key: 0 for key in FIELDS}
    row["county"] = audit["county"]
    accepted = {"Accepted 2026 EARLY VOTING", "Accepted 2026 MAIL"}
    periods = {"Registered by 2024 election", "Registration after 2024 election",
               "Registration after 2026 election", "Unknown registration date"}
    histories = {
        "Positive 2024 NC history": "positive_2024_nc_history",
        "No 2024 NC history found; national participation unresolved": "no_2024_nc_history_found",
    }
    for cell in json.loads(raw):
        membership = cell["cohort_membership_2026"]
        if membership == "Not in selected early/mail cohort":
            continue
        if (membership not in accepted or cell["historical_search_complete"] is not True
                or cell["registration_period"] not in periods
                or cell["prior_2024_history"] not in histories
                or type(cell["records"]) is not int or cell["records"] <= 0):
            raise ValueError("Selected cohort history, date classification or count is unresolved")
        row["accepted_cohort"] += cell["records"]
        if cell["registration_period"] == "Registration after 2024 election":
            row["post_2024_registration"] += cell["records"]
            row[histories[cell["prior_2024_history"]]] += cell["records"]
    if row["accepted_cohort"] != audit["accepted_cohort"]["unambiguous_records"]:
        raise ValueError("Accepted-cohort source control changed")
    reviewed_row(row)
    return row


def review(snapshot):
    if (set(snapshot) != {"version", "scope", "limitations", "sources", "private_provenance", "rows"}
            or snapshot["version"] != VERSION or snapshot["scope"] != SCOPE
            or snapshot["limitations"] != LIMITS):
        raise ValueError("Registration-date selection or evidence scope changed")
    rows = snapshot["rows"]
    if len(rows) != 2 or {row["county"] for row in rows} != {"WAKE", "MECKLENBURG"}:
        raise ValueError("Require both qualified counties, once each")
    provenance = snapshot["private_provenance"]
    if set(provenance) != {"WAKE", "MECKLENBURG"}:
        raise ValueError("Missing qualified private-selection provenance")
    for proof in provenance.values():
        if (set(proof) != {"joint_cells_sha256", "linkage_audit_sha256", "independent_controls_sha256"}
                or any(not re.fullmatch(r"[a-f0-9]{64}", digest) for digest in proof.values())):
            raise ValueError("Private provenance must contain only source-control digests")
    sources = snapshot["sources"]
    if (len(sources) != 4 or {s["source_id"] for s in sources}
            != {"registration_wake", "registration_mecklenburg", "statewide_history", "accepted_early_mail"}):
        raise ValueError("Require all four used native source receipts")
    for source in sources:
        url = urlsplit(source["url"])
        if (set(source) != {"source_id", "url", "sha256", "bytes", "retrieved_at", "last_modified"}
                or type(source["bytes"]) is not int or source["bytes"] <= 0
                or not re.fullmatch(r"[a-f0-9]{64}", source["sha256"])
                or url.scheme != "https" or url.hostname != "s3.amazonaws.com"
                or not url.path.startswith("/dl.ncsbe.gov/")):
            raise ValueError("Native source receipt or disclosure changed")
    return {
        "version": VERSION, "status": "selected_accepted_cohort_registration_date_descriptives",
        "scope": SCOPE, "rows": [reviewed_row(row) for row in rows],
        "limitations": LIMITS, "sources": sources, "private_provenance": provenance,
        "first_time_voters": None, "nationally_new_voters": None,
        "all_mode_turnout": None, "turnout_rates": None,
        "candidate_choice": None, "persuasion": None, "measured_staying_home": None,
        "statewide_or_national_estimates": None,
    }


def frozen_write(path, raw):
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("Frozen registration-entry output differs; use a new version")
    path.write_bytes(raw)


def package():
    raw = (ROOT / DATA / "selected-aggregates.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise ValueError("Qualified selected aggregates changed")
    analysis = review(json.loads(raw))
    out = ROOT / PUBLIC
    out.mkdir(parents=True, exist_ok=True)
    frozen_write(out / "summary.json", encoded(analysis))
    paths = [f"{DATA}/selected-aggregates.json", f"{PUBLIC}/summary.json",
             "scripts/package-registration-entry.py", "scripts/test-package-registration-entry.py"]
    contents = {path: (ROOT / path).read_bytes() for path in paths}
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9, standard library only. Extract preserving all paths.\n"
        "Verify all files against checksums.json, then run:\n"
        "python3 scripts/test-package-registration-entry.py\n"
        "python3 scripts/package-registration-entry.py\n"
        "Selected aggregate inputs, results, full ZIP and metadata reproduce without network.\n"
        "The selected table contains both counties' entire qualified date/history selection,\n"
        "including positive 2024 NC history AND unmatched/unresolved history, plus each full\n"
        "accepted-cohort control. Rates use their explicitly named denominators, not all voters.\n"
        "This is not a metadata-only download or an export of personal records/fine cells.\n"
        "Source: North Carolina State Board of Elections. Full native source URLs, dates, bytes,\n"
        "hashes and private linkage/control proof hashes are in selected-aggregates.json.\n"
        "Native voter-level records remain private. Reproducing initial private linkage requires\n"
        "those frozen sources; no fresh native linkage is claimed by this offline reproduction.\n"
        "The optional --private-review DIRECTORY reads existing qualified joint-cells.json and\n"
        "audit.json and emits only the broad selected county row after source-control checks.\n"
        "Registration dates belong to the current record, not necessarily first registration.\n"
        "Positive 2024 NC general history proves prior participation, not prior candidate choice.\n"
        "An absent NC match does not establish no 2024 vote elsewhere or first-time participation.\n"
        "Accepted early/mail membership is not all-mode turnout or proof of a counted ballot.\n"
        "Registration/history files were last modified November 2; accepted records November 6.\n"
        "No first-time-voter, national entry, staying-home, candidate-choice or persuasion claim.\n"
        "No demographic breakdown or allocation outside these two selected counties is made.\n"
    ).encode()
    contents["checksums.json"] = encoded({
        path: {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
        for path, value in sorted(contents.items())})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, value in sorted(contents.items()):
            member = zipfile.ZipInfo(path, date_time=(2026, 11, 7, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, value, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    raw = buffer.getvalue()
    frozen_write(out / "complete-analysis.zip", raw)
    metadata = {
        "file": "complete-analysis.zip", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "members": len(contents), "complete_selected_aggregate_inputs_and_code": True,
        "personal_records_included": False, "fine_joint_cells_included": False,
        "fresh_native_linkage_reproduced": False, "first_time_voter_estimates_released": False,
    }
    frozen_write(out / "download.json", encoded(metadata))
    print(json.dumps(metadata))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-review", type=Path)
    args = parser.parse_args()
    if args.private_review:
        print(json.dumps(select_private(args.private_review), indent=2))
    else:
        package()

"""Reduce private registration/cohort/history joins to reproducible aggregate model cells."""

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("cohort", Path(__file__).with_name("review-nc-demographic-cohort.py"))
cohort = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cohort)

GENERAL = {"11/08/2016": 2016, "11/06/2018": 2018, "11/03/2020": 2020,
           "11/08/2022": 2022, "11/05/2024": 2024, "11/03/2026": 2026}
BASELINE = datetime(2024, 11, 5).date()
OUTCOME = datetime(2026, 11, 3).date()


def registration_date(value):
    if not value or value.lower() in {"xx/xx/xxxx", "##/##/####"}:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError:
        raise ValueError("Unrecognized registration date") from None


def registration_period(value):
    date = registration_date(value)
    if date is None:
        return "Unknown registration date"
    return ("Registered by 2024 election" if date <= BASELINE else
            "Registration after 2024 election" if date <= OUTCOME else "Registration after 2026 election")


def unique_records(rows, fields, county, accepted=False):
    records, repeated = {}, set()
    audit = Counter()
    for row in rows:
        if row["county_desc"].strip() != county:
            continue
        if accepted:
            if row["election_dt"] != "11/03/2026":
                raise ValueError("Wrong cohort election")
            if row["ballot_rtn_status"].strip() != "ACCEPTED":
                continue
        audit["selected_source_records"] += 1
        identity = row["ncid"].strip()
        if not identity:
            audit["missing_identifier_records"] += 1
            continue
        if identity in records or identity in repeated:
            records.pop(identity, None)
            repeated.add(identity)
            audit["repeated_identifier_records_beyond_first"] += 1
            continue
        records[identity] = {field: row[field].strip() for field in fields}
    audit["ambiguous_identifiers_excluded"] = len(repeated)
    audit["unambiguous_records"] = len(records)
    return records, dict(audit)


def native_history(path):
    with zipfile.ZipFile(path) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if len(members) != 1:
            raise ValueError("Expected one native history table")
        with archive.open(members[0]) as raw:
            buffer = io.BufferedReader(raw)
            encoding = "utf-16" if buffer.peek(4).startswith((b"\xff\xfe", b"\xfe\xff")) else "latin-1"
            reader = csv.reader(io.TextIOWrapper(buffer, encoding=encoding), delimiter="\t")
            header = next(reader)
            fields = ["ncid", "election_lbl", "election_desc", "voted_county_desc",
                      "voting_method", "voted_party_cd"]
            positions = [header.index(field) for field in fields]
            for row in reader:
                if len(row) != len(header):
                    raise ValueError("Malformed native history row")
                yield tuple(row[index].strip() for index in positions)


def linked_history(rows, identities, county):
    history = defaultdict(lambda: {"general": {}, "primary_2024": set(), "complete_search": False})
    audit = Counter()
    county_2024 = set()
    for identity, date, description, voted_county, method, party in rows:
        audit["native_records"] += 1
        year = GENERAL.get(date)
        if year is not None and "GENERAL" not in description.upper():
            raise ValueError("Wrong general-election identity")
        if year is not None:
            audit[f"general_{year}_records"] += 1
        in_baseline = year == 2024 and voted_county == county
        if in_baseline:
            audit["baseline_county_2024_records"] += 1
            if not identity:
                raise ValueError("Missing baseline history identifier")
            county_2024.add(identity)
        if identity not in identities and not in_baseline:
            continue
        history[identity]["complete_search"] = identity in identities
        if year is not None:
            entries = history[identity]["general"].setdefault(year, set())
            entry = (voted_county, method)
            if entry in entries:
                audit["duplicate_selected_general_entries"] += 1
            entries.add(entry)
        elif date == "03/05/2024":
            if "PRIMARY" not in description.upper():
                raise ValueError("Wrong primary identity")
            history[identity]["primary_2024"].add(party or "Unspecified")
    audit["baseline_county_2024_unique_identifiers"] = len(county_2024)
    return history, county_2024, dict(audit)


def model_features(registration, native, history):
    registration = registration or {}
    native = native or {}
    year = registration.get("birth_year", "")
    age = cohort.age_group(str(2024 - int(year))) if year.isdigit() else "Unknown"
    if year.isdigit() and 0 <= 2024 - int(year) < 18:
        age = "Under 18 in 2024"
    primary = history.get("primary_2024", set())
    complete_search = history.get("complete_search", True)
    registered = registration_date(registration.get("registr_dt", ""))
    output = {
        "age_2024": age, "race": native.get("race") or registration.get("race_code") or "Unknown",
        "ethnicity": native.get("ethnicity") or registration.get("ethnic_code") or "Unknown",
        "gender": native.get("gender") or registration.get("gender_code") or "Unknown",
        "registered_party_2026": native.get("voter_party_code") or registration.get("party_cd") or "Unknown",
        "primary_2024": ("History coverage incomplete" if not complete_search else
                         next(iter(primary)) if len(primary) == 1 else
                         "Multiple parties" if primary else "No matched primary"),
        "registration_period": registration_period(registration.get("registr_dt", "")),
        "registration_status_2026": registration.get("voter_status_desc", "Not linked"),
    }
    for cutoff_year, month, day in [(2016, 11, 8), (2020, 11, 3)]:
        output[f"registration_by_{cutoff_year}"] = registered <= datetime(cutoff_year, month, day).date() if registered else None
    for election in [2018, 2022, 2026]:
        years = election - int(year) if year.isdigit() else None
        output[f"age_{election}"] = cohort.age_group(str(years)) if years is not None and years >= 18 else "Under 18" if years is not None else "Unknown"
    return output


def aggregate_linkage(registrations, accepted, history, baseline_ids):
    cells = Counter()
    for identity in registrations.keys() | accepted.keys() | baseline_ids:
        prior = history.get(identity, {})
        complete_search = prior.get("complete_search", True)
        general = prior.get("general", {})
        native = accepted.get(identity)
        features = model_features(registrations.get(identity), native, prior)
        prior_scope = ("Positive 2024 NC history" if 2024 in general else
                       "No 2024 NC history found; national participation unresolved")
        membership = "Accepted 2026 " + native["ballot_req_type"] if native else "Not in selected early/mail cohort"
        baseline = identity in baseline_ids
        if (not native and not baseline
                and features["registration_status_2026"] not in {"ACTIVE", "INACTIVE"}):
            continue
        values = {**features, "prior_2024_history": prior_scope,
                  "baseline_2024_voted_county": baseline,
                  "cohort_membership_2026": membership,
                  "historical_search_complete": complete_search,
                  "prior_2016_history": 2016 in general if complete_search else None,
                  "prior_2018_history": 2018 in general if complete_search else None,
                  "prior_2020_history": 2020 in general if complete_search else None,
                  "prior_2022_history": 2022 in general if complete_search else None,
                  "prior_2024_voted_counties": "|".join(sorted({entry[0] for entry in general.get(2024, set())})),
                  "prior_2024_voting_methods": "|".join(sorted({entry[1] for entry in general.get(2024, set())})),
                  "positive_2026_history": 2026 in general if complete_search else None}
        cells[tuple(sorted(values.items()))] += 1
    return [{**dict(key), "records": count} for key, count in
            sorted(cells.items(), key=lambda item: json.dumps(dict(item[0]), sort_keys=True))]


def verify(path, receipt):
    expected = json.loads(receipt.read_text())
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if path.stat().st_size != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
        raise ValueError("Changed native source")
    return expected


def review(private, prior_private, output, county="DURHAM"):
    if output.exists():
        raise ValueError("Refusing to overwrite an existing review")
    receipts = [verify(private / name, private / f"{name}.receipt.json")
                for name in ["registration-durham.zip", "history-statewide.zip"]]
    original = json.loads((prior_private / "receipts.json").read_text())
    absentee = next(row for row in original if row["file"] == "absentee.zip")
    if hashlib.sha256((prior_private / "absentee.zip").read_bytes()).hexdigest() != absentee["sha256"]:
        raise ValueError("Changed cohort source")
    receipts.append(absentee)
    registrations, registration_audit = unique_records(
        cohort.archive_rows(private / "registration-durham.zip", "\t"),
        ["birth_year", "race_code", "ethnic_code", "party_cd", "gender_code", "registr_dt", "voter_status_desc"],
        county)
    accepted, accepted_audit = unique_records(
        cohort.archive_rows(prior_private / "absentee.zip", ","),
        ["race", "ethnicity", "gender", "age", "voter_party_code", "ballot_req_type"], county, accepted=True)
    print(json.dumps({"phase": "sources_loaded", "registration": registration_audit, "cohort": accepted_audit}), flush=True)
    history, baseline, history_audit = linked_history(
        native_history(private / "history-statewide.zip"), registrations.keys() | accepted.keys(), county)
    cells = aggregate_linkage(registrations, accepted, history, baseline)
    audit = {
        "version": "20261106-linked-cohort-03", "state_code": "NC", "county": county,
        "sources": receipts, "registration": registration_audit, "accepted_cohort": accepted_audit,
        "history": history_audit, "aggregate_cells": len(cells),
        "accepted_with_registration": len(accepted.keys() & registrations.keys()),
        "baseline_with_registration": len(baseline & registrations.keys()),
        "baseline_without_registration": len(baseline - registrations.keys()),
        "limitations": [
            "An absent statewide history match does not establish national nonparticipation.",
            "Not in the early/mail cohort is not sitting out the 2026 election.",
            "Registration after 2024 includes movers and re-registrations, not just first-time voters.",
            "2026 registration party/status/demographics are not observed 2024 choice or necessarily 2024 attributes.",
            "Race/ethnicity fields retain source codes or native descriptions; harmonization is a separate model step.",
            "Every repeated accepted or registration identifier is excluded, never arbitrarily deduplicated.",
            "Baseline voters outside the initial target set have incomplete other-year searches, explicitly unknown.",
            "Only aggregate model cells are exported, never identifiers or individual scores.",
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, value in [("audit.json", audit), ("joint-cells.json", cells)]:
        (output / name).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(audit, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-directory", type=Path, required=True)
    parser.add_argument("--prior-private-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review(args.private_directory, args.prior_private_directory, args.output)

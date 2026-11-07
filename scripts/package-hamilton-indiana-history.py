"""Reproduce complete selected Hamilton, Indiana report counts without native documents."""

import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-hamilton-indiana-history/{VERSION}"
PUBLIC = f"public/participation-hamilton-indiana-history/{VERSION}"
PINS = {
    "selected-observations.json": "67adea5c2f993861a365a666bb5b2d8b56349987186c4e9c3a9764face218af2",
    "methodology-review.json": "0bc040f420722e6bf93b2be2ac1e86d415bcd61c2951b03321ff296cc8aad290",
    "native-source-consistency.json": "a6d867c34368acd103dcdff5e795887b7529ef87f150e81f8d5012d9d69e4223",
}
CODE = ("scripts/package-hamilton-indiana-history.py", "scripts/test-package-hamilton-indiana-history.py")
COUNTS = ("registered_voters", "election_day", "paper_absentee", "walk_in_absentee", "total_votes_cast")
SCOPE = {"state_code": "IN", "county_name": "Hamilton", "county_fips": "18057"}
ROWS = (221, 217, 220, 234)
TOTALS = (195988, 130376, 199731, 150804)
YEARS = (2020, 2022, 2024, 2026)
WITHHELD = (
    "current_count_finality_qualified", "unique_person_population_qualified",
    "precinct_cross_year_identity_qualified", "demographic_turnout_qualified",
    "individual_transitions_qualified", "native_documents_redistributed", "personal_records_included",
)


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def count(value):
    require(type(value) is int and value >= 0, "Invalid native aggregate count")
    return value


def exact_keys(value, expected):
    require(set(value) == set(expected), "Missing or unexpected selected fields")


def rounded(rate, numerator, denominator, tolerance):
    require(denominator > 0 and isinstance(rate, str), "Missing native rate denominator")
    require(abs(Decimal(rate.rstrip("%")) - 100 * Decimal(numerator) / Decimal(denominator))
            <= Decimal(tolerance), "Native rounded percentage does not reconcile")


def review(snapshot, methods):
    exact_keys(snapshot, ("scope", "observations", "contests", "source_receipts"))
    require(snapshot["scope"] == SCOPE, "County scope changed")
    require(methods["status"] == "qualified_descriptive_native_report_counts_only"
            and all(methods[key] is False for key in WITHHELD), "Unsupported qualification")
    require(len(snapshot["observations"]) == 4 and len(snapshot["contests"]) == 3,
            "Incomplete four-election selection")
    county_rows, anomalies, by_year = [], [], {}
    for observation, year, nrows, total in zip(snapshot["observations"], YEARS, ROWS, TOTALS):
        require(observation["year"] == year and len(observation["precincts"]) == nrows,
                "Missing election or precinct observations")
        require(observation["source_report_time"] is None and observation["source_report_timezone"] is None,
                "Do not impute native PDF source clocks")
        require(observation["native_footer_year_truncated"] is (year == 2020),
                "Truncated native footer changed")
        if year == 2020:
            require(observation["native_footer_date_literal"] == "Friday, November 13, 202",
                    "Truncated native year was imputed")
        if year == 2026:
            require(observation["status"] == "UNOFFICIAL", "Unofficial source promoted")
        precincts = observation["precincts"]
        lookup = {row["precinct_id"]: row for row in precincts}
        require(len(lookup) == nrows, "Duplicate within-election precinct")
        for row in precincts:
            allowed = {"native_label", "source_page", "native_turnout_percent", *COUNTS,
                       "precinct_id", "precinct_name", "township", "native_subtotal_group"}
            require(set(row) <= allowed, "Private or unexpected precinct fields")
            for key in COUNTS:
                count(row[key])
            require(row["total_votes_cast"] == sum(row[key] for key in COUNTS[1:4])
                    <= row["registered_voters"], "Precinct modes or registration do not reconcile")
            rounded(row["native_turnout_percent"], row["total_votes_cast"], row["registered_voters"], "0.05")
        county = {key: sum(row[key] for row in precincts) for key in COUNTS}
        require(county["total_votes_cast"] == total, "County report control changed")
        controls = observation["native_controls"]
        require(len(controls) == (10 if year in (2020, 2026) else 2), "Missing native control rows")
        for control in controls:
            require(set(control) <= {"native_label", "source_page", "native_turnout_percent",
                                     *COUNTS, "township", "child_precinct_ids", "derived_from_precinct_rows"},
                    "Private or unexpected control fields")
            ids = control["child_precinct_ids"]
            require(ids and len(ids) == len(set(ids)) and set(ids) <= set(lookup),
                    "Invalid native control membership")
            derived = {key: sum(lookup[identity][key] for identity in ids) for key in COUNTS}
            require(derived == control["derived_from_precinct_rows"], "Control children do not reconcile")
            for key in COUNTS:
                count(control[key])
            require(all(control[key] == derived[key] for key in COUNTS[:4]), "Native mode control changed")
            rounded(control["native_turnout_percent"], derived["total_votes_cast"], derived["registered_voters"], "0.05")
            if control["total_votes_cast"] != derived["total_votes_cast"]:
                require(control["total_votes_cast"] == lookup[ids[0]]["total_votes_cast"],
                        "Unreviewed native total discrepancy")
                anomalies.append({
                    "year": year, "native_label": control["native_label"], "source_page": control["source_page"],
                    "native_total_votes_cast": control["total_votes_cast"],
                    "derived_precinct_and_mode_sum": derived["total_votes_cast"],
                })
        county_control = [row for row in controls if row["native_label"] == "CountyWide Totals"]
        require(len(county_control) == 1 and all(county_control[0][key] == county[key] for key in COUNTS),
                "Native county control missing or changed")
        county_rows.append({
            "year": year, "election_date": observation["election_date"], **county,
            "native_turnout_percent": county_control[0]["native_turnout_percent"],
            "precinct_count": nrows, "status": observation["status"],
            "native_mode_labels": observation["native_mode_labels"],
            "native_footer_date_literal": observation["native_footer_date_literal"],
            "receipt_key": observation["receipt_key"],
        })
        by_year[year] = lookup
    require(len(anomalies) == 10, "Native discrepancies were lost or silently repaired")
    contest_rows = []
    identities = set()
    for contest in snapshot["contests"]:
        exact_keys(contest, ("title", "candidate_total", "candidates", "precincts",
                            "reported_count_minus_candidate_votes", "same_year_whole_county_native_precinct_names_match",
                            "receipt_key", "scope", "summary_controls"))
        scope, summary = contest["scope"], contest["summary_controls"]
        require(all(scope[key] == value for key, value in SCOPE.items()), "Contest county mismatch")
        year = scope["year"]
        require(year in (2024, 2026) and scope["source_report_timezone"] is None,
                "Contest year or source timezone changed")
        title = contest["title"]
        identity = (year, title)
        require(identity not in identities, "Duplicate county contest")
        identities.add(identity)
        lookup = by_year[year]
        native_by_name = {row["precinct_name"].casefold(): row for row in lookup.values()}
        require(len(contest["precincts"]) == len(lookup)
                and contest["same_year_whole_county_native_precinct_names_match"] is True,
                "Partial-county contest cannot use whole-county baseline")
        candidates = contest["candidates"]
        by_label = {row["native_label"]: row for row in candidates}
        require(len(by_label) == len(candidates) == (3 if year == 2026 else 5),
                "Missing candidate, literal party or write-in")
        total = count(contest["candidate_total"])
        mode_fields = ("election_day", "paper_absentee", "walk_in_absentee")
        for row in candidates:
            exact_keys(row, ("native_label", "candidate_name", "party", *mode_fields, "total_votes", "native_percent"))
            label = row["native_label"]
            match = re.fullmatch(r"\((D|R|L|I|WTP)\) (.+)", label)
            require((match is not None and (row["party"], row["candidate_name"]) == match.groups())
                    or (label == "Write-In" and row["party"] is None and row["candidate_name"] == label),
                    "Literal party or write-in changed")
            require(sum(count(row[key]) for key in mode_fields) == count(row["total_votes"]),
                    "Candidate modes do not reconcile")
            rounded(row["native_percent"], row["total_votes"], total, "0.005")
        seen = set()
        for row in contest["precincts"]:
            exact_keys(row, ("candidate_votes", "candidate_total", "native_contest_precinct_label",
                            "native_turnout_precinct_id", "native_turnout_precinct_label",
                            "reported_count_minus_candidate_votes", "turnout_report_total_votes_cast"))
            name = row["native_contest_precinct_label"].casefold()
            require(name in native_by_name and name not in seen, "Duplicate or unknown contest precinct")
            seen.add(name)
            original = native_by_name[name]
            require(row["native_turnout_precinct_id"] == original["precinct_id"]
                    and row["native_turnout_precinct_label"] == original["precinct_name"]
                    and row["turnout_report_total_votes_cast"] == original["total_votes_cast"],
                    "Same-election turnout linkage changed")
            exact_keys(row["candidate_votes"], by_label)
            require(sum(count(v) for v in row["candidate_votes"].values()) == count(row["candidate_total"]),
                    "Native precinct candidate vector changed")
            gap = original["total_votes_cast"] - row["candidate_total"]
            require(gap >= 0 and gap == row["reported_count_minus_candidate_votes"], "Count gap changed")
        require(all(sum(row["candidate_votes"][label] for row in contest["precincts"]) == candidate["total_votes"]
                    for label, candidate in by_label.items()), "Precinct candidate totals do not reconcile")
        require(sum(row["total_votes"] for row in candidates) == total, "Contest total changed")
        require(summary["public_count"] == sum(row["total_votes_cast"] for row in lookup.values()),
                "Candidate votes were substituted for participation")
        require(summary["registered_voters"] == sum(row["registered_voters"] for row in lookup.values()),
                "Native summary registration changed")
        for key in mode_fields:
            require(summary[key] == sum(row[key] for row in lookup.values())
                    and sum(row[key] for row in candidates) <= summary[key], "Candidate/participation mode conflict")
        gap = summary["public_count"] - total
        require(gap == contest["reported_count_minus_candidate_votes"], "Native unclassified gap changed")
        parties = {party: [row for row in candidates if row["party"] == party] for party in ("D", "R")}
        require(all(len(value) == 1 for value in parties.values()), "Nonunique major-party contest")
        d, r = (parties[party][0]["total_votes"] for party in ("D", "R"))
        contest_rows.append({
            "year": year, "title": title, "scope": scope, "precinct_count": len(lookup),
            "reported_public_count": summary["public_count"], "candidate_total": total,
            "unclassified_reported_count_gap": gap, "candidates": candidates,
            "two_party_margin_pp": float(100 * Decimal(d - r) / Decimal(d + r)),
            "receipt_key": contest["receipt_key"],
        })
    require(identities == {(2024, "President and Vice-President of the U.S."),
                           (2024, "United States Representative District 5"),
                           (2026, "United States Representative District 5")}, "Actual contest scope changed")
    receipts = snapshot["source_receipts"]
    require(len(receipts) == 15, "Incomplete used-source receipts")
    for receipt in receipts.values():
        exact_keys(receipt, ("filename", "requested_url", "final_url", "status", "bytes", "sha256",
                            "started_at_utc", "finished_at_utc", "headers"))
        require(receipt["status"] == 200 and count(receipt["bytes"]) > 0
                and re.fullmatch(r"[a-f0-9]{64}", receipt["sha256"]), "Invalid used-source receipt")
        require(all(key.lower() in {"content-type", "content-length", "content-disposition", "date",
                                    "last-modified", "etag", "cache-control"} for key in receipt["headers"]),
                "Private session or unexpected headers")
        require(all(receipt[key].startswith("https://") for key in ("requested_url", "final_url")),
                "Invalid native source URL")
    for observation in snapshot["observations"]:
        require(observation["receipt_key"] in receipts, "Missing turnout provenance")
    for row in contest_rows:
        require(row["receipt_key"] in receipts, "Missing contest provenance")
    current_margin = contest_rows[-1]["two_party_margin_pp"]
    return {
        "version": VERSION, "scope": SCOPE, "methodology": methods, "elections": county_rows,
        "native_total_cell_discrepancies": anomalies, "contests": contest_rows,
        "reported_count_comparisons": [
            {"baseline_year": row["year"], "current_year": 2026,
             "reported_count_change": TOTALS[-1] - row["total_votes_cast"]}
            for row in county_rows[:-1]
        ],
        "descriptive_contest_comparisons": [
            {"baseline_year": 2024, "baseline_contest": row["title"],
             "current_year": 2026, "current_contest": contest_rows[-1]["title"],
             "two_party_margin_change_pp": current_margin - row["two_party_margin_pp"]}
            for row in contest_rows[:-1]
        ],
        "unsupported_estimates": {key: None for key in (
            "individual_switchers", "measured_staying_home", "new_or_returning_voter_identity",
            "demographic_turnout", "original_coalition_absence", "causal_persuasion",
            "precinct_cross_year_flows", "design_confidence_interval")},
        "source_receipts": receipts,
    }


def csv_bytes(rows, columns):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def archive_bytes(contents):
    inventory = {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                 for name, raw in sorted(contents.items())}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, raw in sorted({**contents, "checksums.json": encoded(inventory)}.items()):
            member = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def package(root=ROOT):
    inputs = {}
    for name, digest in PINS.items():
        raw = (root / DATA / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, "Reviewed input changed; create a new version")
        inputs[name] = json.loads(raw)
    snapshot = inputs["selected-observations.json"]
    result = review(snapshot, inputs["methodology-review.json"])
    proof = inputs["native-source-consistency.json"]
    require(proof["status"] == "four_completed_independent_native_checks"
            and (proof["turnout_rows"], proof["turnout_precinct_rows"], proof["turnout_controls"],
                 proof["preserved_bad_total_cells"], proof["contest_precinct_rows"]) == (916, 892, 24, 10, 674)
            and all(p["independent_native_verification_passed"] is True
                    and p["network_blocked_and_probed"] is True for p in proof["reviews"].values()),
            "Completed independent native qualification required")
    contents = {path: (root / path).read_bytes()
                for path in [*(f"{DATA}/{name}" for name in PINS), *CODE]}
    contents[f"{PUBLIC}/history.json"] = encoded(result)
    contents["results/precinct-participation.csv"] = csv_bytes(
        [{"year": o["year"], **row} for o in snapshot["observations"] for row in o["precincts"]],
        ("year", "precinct_id", "precinct_name", "native_label", "source_page", *COUNTS, "native_turnout_percent"))
    contents["results/native-controls.csv"] = csv_bytes(
        [{"year": o["year"], **row, "derived_total_votes_cast": row["derived_from_precinct_rows"]["total_votes_cast"]}
         for o in snapshot["observations"] for row in o["native_controls"]],
        ("year", "native_label", "source_page", *COUNTS, "native_turnout_percent", "derived_total_votes_cast"))
    contents["results/precinct-candidate-vectors.csv"] = csv_bytes(
        [{"year": c["scope"]["year"], "contest": c["title"],
          "precinct_id": row["native_turnout_precinct_id"],
          "precinct_name": row["native_contest_precinct_label"], "candidate": label,
          "votes": votes, "reported_participation": row["turnout_report_total_votes_cast"]}
         for c in snapshot["contests"] for row in c["precincts"] for label, votes in row["candidate_votes"].items()],
        ("year", "contest", "precinct_id", "precinct_name", "candidate", "votes", "reported_participation"))
    contents["REPRODUCTION.txt"] = (
        "Python >=3.9; standard library only. Extract preserving all paths.\n"
        "Verify every member against checksums.json, then run:\n"
        "python3 scripts/test-package-hamilton-indiana-history.py\n"
        "python3 scripts/package-hamilton-indiana-history.py\n"
        "Complete selected facts, CSVs, summary, ZIP and metadata reproduce OFFLINE.\n"
        "All 892 precinct participation observations, 24 native controls, ten literal bad\n"
        "total cells, 674 contest precinct vectors, every candidate and 15 receipts included.\n"
        "CSV identifiers should be imported as text. No longitudinal precinct crosswalk.\n"
        "Source: Hamilton County, Indiana Election Office. Source endorsement not implied.\n"
        "2026 is unofficial. Reported totals and current registered denominators are not\n"
        "verified unique-person populations, fixed eligible cohorts or demographic turnout.\n"
        "2020 mode labels differ. Footer dates, HTML clocks and receipt dates are distinct.\n"
        "Native 2020 footer truncates its year; it is not repaired. Ten bad source total\n"
        "cells remain beside recomputed child sums. Contest count gaps are unclassified.\n"
        "Separate President/House comparisons describe county margin changes, not causal\n"
        "persuasion, individual switching, staying home, new/returning identity or group flows.\n"
        "No native HTML/PDF, cookies, personal records, joins, scores or demographic fine cells.\n"
        "Original native extraction requires private hash-pinned originals; this selected-fact\n"
        "reproduction does not rerun it or validate latent transitions or independent outcomes.\n"
    ).encode()
    raw_zip = archive_bytes(contents)
    metadata = {
        "file": "complete-analysis.zip", "bytes": len(raw_zip),
        "sha256": hashlib.sha256(raw_zip).hexdigest(), "members": len(contents) + 1,
        "complete_selected_aggregate_inputs_and_code": True,
        "participation_precinct_observations": 892, "native_controls": 24,
        "contest_precinct_vectors": 674, "source_receipts": 15,
        "native_documents_or_personal_records_included": False,
        "individual_transitions_released": False,
    }
    outputs = {"history.json": encoded(result), "complete-analysis.zip": raw_zip, "download.json": encoded(metadata)}
    for name, raw in outputs.items():
        path = root / PUBLIC / name
        require(not path.exists() or path.read_bytes() == raw, "Frozen output differs; create a new version")
    (root / PUBLIC).mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        path = root / PUBLIC / name
        if not path.exists():
            path.write_bytes(raw)
    return metadata


if __name__ == "__main__":
    print(json.dumps(package()))

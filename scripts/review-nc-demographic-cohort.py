"""Review private native NC archives; export only county-level aggregate evidence."""

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path


DIMENSIONS = {
    "race": "race", "ethnicity": "ethnicity", "sex_gender": "gender",
    "age": "age", "registered_party": "voter_party_code",
}


def archive_rows(path, delimiter):
    with zipfile.ZipFile(path) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if len(members) != 1:
            raise ValueError("Expected exactly one native table")
        with archive.open(members[0]) as raw:
            buffer = io.BufferedReader(raw)
            encoding = "utf-16" if buffer.peek(4).startswith((b"\xff\xfe", b"\xfe\xff")) else "latin-1"
            reader = csv.DictReader(io.TextIOWrapper(buffer, encoding=encoding), delimiter=delimiter)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError("Missing or repeated native header")
            for row in reader:
                if None in row or None in row.values():
                    raise ValueError("Malformed native row")
                yield row


def age_group(value):
    if not re.fullmatch(r"\d{1,3}", value):
        return "Unknown"
    age = int(value)
    if not 18 <= age <= 120:
        return "Unknown"
    return "18-29" if age < 30 else "30-44" if age < 45 else "45-64" if age < 65 else "65+"


def historical_participants(rows):
    participants = set()
    identities = set()
    dates = Counter()
    duplicates = 0
    for row in rows:
        required = ["ncid", "election_lbl", "election_desc", "voted_county_desc"]
        if any(field not in row for field in required):
            raise ValueError("Historical schema changed")
        label = row["election_lbl"].strip()
        dates[label] += 1
        if label not in {"11/05/2024", "2024-11-05"}:
            continue
        if "GENERAL" not in row["election_desc"].upper() or not row["ncid"].strip():
            raise ValueError("Conflicting historical general-election identity")
        identity = row["ncid"].strip()
        if identity in identities:
            duplicates += 1
        identities.add(identity)
        participants.add(identity)
    return participants, {"history_records": sum(dates.values()), "native_election_dates": dict(sorted(dates.items())),
                          "positive_2024_history_matches_available": len(participants),
                          "duplicate_2024_history_records": duplicates}


def aggregate_cohort(rows, participants, pilot="DURHAM"):
    counts, matched, status_counts = Counter(), Counter(), Counter()
    ids, duplicates = set(), 0
    missing_ids, accepted = 0, 0
    source_rows = 0
    for row in rows:
        required = ["county_desc", "ncid", "election_dt", "ballot_req_type", "ballot_rtn_status",
                    *DIMENSIONS.values()]
        if any(field not in row for field in required):
            raise ValueError("Cohort schema changed")
        if row["election_dt"] not in {"11/03/2026", "2026-11-03"}:
            raise ValueError("Wrong election")
        source_rows += 1
        method, status = row["ballot_req_type"].strip(), row["ballot_rtn_status"].strip()
        status_counts[(method, status)] += 1
        if status != "ACCEPTED":
            continue
        county, identity = row["county_desc"].strip(), row["ncid"].strip()
        if not county or not method:
            raise ValueError("Missing native cohort identity")
        accepted += 1
        if not identity:
            missing_ids += 1
        elif identity in ids:
            duplicates += 1
        else:
            ids.add(identity)
        dimensions = {"overall": "All accepted records"}
        for dimension, field in DIMENSIONS.items():
            value = row[field].strip() or "Unknown"
            dimensions[dimension] = age_group(value) if dimension == "age" else value
        for dimension, group in dimensions.items():
            key = county, method, dimension, group
            counts[key] += 1
            if county == pilot and identity in participants:
                matched[key] += 1
    records = [{
        "state_code": "NC", "county": county, "method_literal": method,
        "dimension": dimension, "group": group, "accepted_records": value,
        "positive_2024_history_matches": matched[(county, method, dimension, group)] if county == pilot else None,
        "history_unresolved": value - matched[(county, method, dimension, group)] if county == pilot else None,
        "group_turnout_pct": None, "prior_democratic_share_pct": None, "swing_margin_pp": None,
    } for (county, method, dimension, group), value in sorted(counts.items())]
    return records, {
        "source_rows": source_rows, "accepted_records": accepted,
        "unique_nonempty_accepted_identifiers": len(ids), "duplicate_accepted_identifier_records": duplicates,
        "accepted_records_missing_identifier": missing_ids,
        "county_count": len({row["county"] for row in records}),
        "native_method_status_counts": [
            {"method": method, "status": status, "records": value}
            for (method, status), value in sorted(status_counts.items())
        ],
        "membership_unique": duplicates == 0 and missing_ids == 0,
    }


def review(private_directory, output):
    if output.exists():
        raise ValueError("Refusing to overwrite an existing review")
    receipts = json.loads((private_directory / "receipts.json").read_text())
    for receipt in receipts:
        path = private_directory / receipt["file"]
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        if path.stat().st_size != receipt["bytes"] or digest.hexdigest() != receipt["sha256"]:
            raise ValueError("Changed native archive")
    participants, history = historical_participants(archive_rows(private_directory / "history-durham.zip", "\t"))
    records, audit = aggregate_cohort(archive_rows(private_directory / "absentee.zip", ","), participants)
    output.mkdir(parents=True, exist_ok=False)
    summary = {
        "version": "20261106-demographic-cohort-01", "state_code": "NC",
        "pilot_county": "DURHAM", "cohort_date": "2026-11-03", "prior_election_date": "2024-11-05",
        "source_receipts": receipts, "cohort_audit": audit, "history_audit": history,
        "evidence": {
            "membership_verified": audit["membership_unique"], "same_people": False,
            "methods_matched": False, "geography_matched": False, "cutoff_matched": False,
            "valid_vote_universe_matched": False, "prior_turnout_verified": False,
            "prior_preference_validated": False, "demographic_choice_validated": False,
        },
        "status": "aggregate_cohort_audit_only",
        "persuasion_estimates_released": False,
        "limitations": [
            "Accepted records are a source status, not proof of counted ballots or candidate selections.",
            "Only the literal ACCEPTED status is selected. ACCEPTED - CURED and ACCEPTED - EXCEPTION remain separate in the complete status audit, not silently included.",
            "No-match to one county's history is unresolved, not proof of 2024 nonvoting or 2026 staying home.",
            "History archive predates the 2026 election and cannot measure 2026 drop-off.",
            "Primary participation and registered party are not candidate choices.",
            "Age bins are derived from source-supplied age; its reference date is not independently established.",
            "Race and ethnicity are separate overlapping dimensions; dimensions cannot be summed.",
            "Education, household income and residence type are not supplied by these archives.",
            "Group sizes are accepted-record composition, not group turnout rates.",
            "No historical-choice model, matched 2026 cohort returns, or demographic-choice validation is supplied.",
            "Personal source archives stay private. The public package contains complete aggregate review inputs and outputs, not individual records.",
        ],
    }
    for name, value in [("audit.json", summary), ("aggregate-cohort.json", records)]:
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps({"records": len(records), "audit": audit, "history": history}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review(args.private_directory, args.output)

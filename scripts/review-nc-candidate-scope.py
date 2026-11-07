"""Reconcile native county/contest/method totals without allocating administrative votes."""

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


MODES = ["Election Day", "Early Voting", "Absentee by Mail", "Provisional"]


def candidate_totals(path, year):
    with zipfile.ZipFile(path) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if len(members) != 1:
            raise ValueError("Expected one native results table")
        text = archive.read(members[0]).decode("utf-8-sig").replace("\t\x00\t", "\t\t")
        if "\x00" in text:
            raise ValueError("Unexpected NUL beyond the documented empty-party field")
    return aggregate_candidates(csv.DictReader(io.StringIO(text), delimiter="\t"), year)


def aggregate_candidates(source, year):
    date = {2024: "11/05/2024", 2026: "11/03/2026"}[year]
    totals, seen = Counter(), set()
    partitions = defaultdict(set)
    identities = defaultdict(set)
    for row in source:
        contest = row["Contest Name"]
        if not (year == 2024 and contest == "US PRESIDENT" or year == 2026
                and (contest == "US SENATE" or contest.startswith("US HOUSE OF REPRESENTATIVES DISTRICT "))):
            continue
        if row["Election Date"] != date or row["Vote For"] != "1":
            raise ValueError("Wrong election or multi-seat contest")
        county, party, choice = row["County"], row["Choice Party"], row["Choice"]
        if not county or not choice or row["Real Precinct"] not in {"Y", "N"}:
            raise ValueError("Missing native identity")
        key = county, row["Precinct"], contest, choice, party
        if key in seen:
            raise ValueError("Repeated candidate/reporting-unit identity")
        seen.add(key)
        partitions[county].add(contest)
        identities[(county, contest, party)].add(choice)
        counts = {}
        for mode in [*MODES, "Total Votes"]:
            value = row[mode]
            if not value.isdigit():
                raise ValueError("Missing, negative or suppressed candidate count")
            counts[mode] = int(value)
        if sum(counts[mode] for mode in MODES) != counts["Total Votes"]:
            raise ValueError("Native candidate methods do not reconcile")
        for mode, value in counts.items():
            totals[(county, contest, mode, choice, party)] += value
    if not totals:
        raise ValueError("No requested general-election contests")
    for (county, contest, party), choices in identities.items():
        if party in {"DEM", "REP"} and len(choices) != 1:
            raise ValueError("Multiple candidates on one major-party label")
    return [{
        "year": year, "county": county, "contest": contest, "method": mode,
        "candidate": choice, "party_literal": party, "votes": count,
    } for (county, contest, mode, choice, party), count in sorted(totals.items())]


def review(directory, current_archive):
    output = directory / "county-contest-methods.json"
    if output.exists():
        raise ValueError("Refusing to overwrite an existing scope review")
    baseline = directory / "NC-results-20241105.zip"
    receipt = json.loads((directory / "source-receipt.json").read_text())
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != receipt["sha256"]:
        raise ValueError("Changed baseline source")
    records = candidate_totals(baseline, 2024) + candidate_totals(current_archive, 2026)
    audit = {
        "source_receipts": [receipt, {
            "file": str(current_archive), "bytes": current_archive.stat().st_size,
            "sha256": hashlib.sha256(current_archive.read_bytes()).hexdigest(),
            "url": "https://www.ncsbe.gov/results-data/election-results/historical-election-results-data",
            "reporting_clock": None, "election_date": "2026-11-03",
        }],
        "rows": len(records), "years": [2024, 2026],
        "counties_by_year": {str(year): len({row["county"] for row in records if row["year"] == year})
                             for year in [2024, 2026]},
        "method_reconciliation": "Every native candidate row reconciles exactly across four methods.",
        "participation_measure": None, "matched_fixed_cohort": False,
        "precinct_panel_qualified": False,
        "limits": [
            "2026 counts are provisional; reporting clock is not established by this cached archive.",
            "Every county's presidential baseline includes all county voters, not the fixed 2026 early cohort.",
            "House contests remain separate; split counties need a qualified cross-year county/district presidential baseline.",
            "Administrative units are retained in county method totals, never assigned to residential precincts.",
            "Literal candidate parties and independent/other choices are retained.",
            "Candidate counts do not measure turnout or identify demographic or individual choices.",
            "Membership, valid contest votes, report clocks, and status coverage do not yet reconcile to the fixed cohort.",
        ],
    }
    output.write_text(json.dumps(records, indent=2) + "\n")
    (directory / "candidate-audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({key: value for key, value in audit.items() if key != "source_receipts"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--current-archive", type=Path, required=True)
    args = parser.parse_args()
    review(args.directory, args.current_archive)

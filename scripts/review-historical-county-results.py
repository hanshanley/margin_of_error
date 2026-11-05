"""Reconcile the acquired historical compilation without approving maps or source reuse."""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "data/precinct-source-reviews/20261105-historical-county-bulk-01/acquisition.json"
OFFICES = ("house", "president", "senate")
CODES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()


def key(row):
    return row["year"], row["office"], row["state_po"], row["county_fips"]


def reconcile(rows, summaries):
    groups, problems = defaultdict(list), defaultdict(set)
    identities, stages = set(), defaultdict(set)
    exceptions = []
    for line, row in enumerate(rows, 2):
        identity = key(row)
        if (row["office"] not in OFFICES or row["state_po"] not in CODES
                or not re.fullmatch(r"\d{4}", row["year"])
                or int(row["year"]) not in range(1990, 2025, 2)
                or not re.fullmatch(r"\d{5}", row["county_fips"])
                or row["county_fips"][:2] != row["state_fips"]
                or row["party_group"] not in {"DEM", "REP", "OTHER"}
                or row["stage"] not in {"general", "runoff"}):
            raise ValueError("Invalid native county/year/office identity at line " + str(line))
        party_line = identity + tuple(row[field] for field in ("district", "stage", "candidate", "party", "source"))
        if party_line in identities:
            problems[identity].add("duplicate_candidate_party_line")
        identities.add(party_line)
        stages[identity + (row["district"],)].add(row["stage"])
        if not re.fullmatch(r"\d+", row["votes"]):
            problems[identity].add("noninteger_or_missing_votes")
            exceptions.append(dict(line=line, **row))
        groups[identity].append(row)
    for district, rounds in stages.items():
        if len(rounds) > 1:
            problems[district[:4]].add("overlapping_general_and_runoff")
    summary_index = {}
    for row in summaries:
        identity = key(row)
        if identity in summary_index:
            raise ValueError("Duplicate published county summary")
        summary_index[identity] = row
    if set(groups) != set(summary_index):
        raise ValueError("Candidate and published-summary county identities differ")
    matched, report, parties, accepted = 0, [], [], []
    for identity, candidates in sorted(groups.items(), key=lambda item: (-int(item[0][0]), *item[0][1:])):
        totals = defaultdict(Decimal)
        try:
            for row in candidates:
                count = Decimal(row["votes"])
                if not count.is_finite() or count < 0:
                    raise InvalidOperation
                totals[row["party_group"]] += count
            summary = summary_index[identity]
            expected = {group: Decimal(summary[field]) for group, field in
                        (("DEM", "dem_votes"), ("REP", "rep_votes"), ("OTHER", "other_votes"))}
            match = (all(totals[group] == count for group, count in expected.items())
                     and sum(totals.values()) == Decimal(summary["total_votes"]))
        except InvalidOperation:
            match = False
        if match:
            matched += 1
        else:
            problems[identity].add("candidate_summary_disagreement")
        reasons = sorted(problems[identity])
        report.append(dict(zip(("year", "office", "state_code", "county_fips"), identity),
            candidate_rows=len(candidates), arithmetic_matches_source_summary=match,
            integer_counts_accepted=not reasons, withheld_reasons=";".join(reasons),
            source_quality_flags=summary_index[identity]["quality_flag"],
            source_stages=";".join(sorted({row["stage"] for row in candidates}))))
        if reasons:
            continue
        literal_parties = Counter()
        for row in candidates:
            literal_parties[(row["party"], row["party_group"])] += int(row["votes"])
            accepted.append(row)
        for (party, group), votes in sorted(literal_parties.items()):
            parties.append(dict(zip(("year", "office", "state_code", "county_fips"), identity),
                                party=party, party_group=group, votes=votes))
    return report, parties, accepted, dict(summary_rows=len(summaries),
        arithmetic_matched_summaries=matched, accepted_integer_counties=sum(not problems[k] for k in groups),
        withheld_counties=sum(bool(problems[k]) for k in groups), literal_vote_exceptions=exceptions)


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def coverage(report, gaps, no_ballot, current_index, state_codes):
    grouped, native_gaps, native_absences = defaultdict(list), Counter(), Counter()
    for row in report:
        grouped[(int(row["year"]), row["office"], row["state_code"])].append(row)
    for row in gaps:
        native_gaps[(int(row["year"]), row["office"], state_codes[row["state"]])] += 1
    for row in no_ballot:
        native_absences[(int(row["year"]), row["office"], row["state_po"])] += 1
    result = []
    for year in range(2026, 1963, -2):
        for office in OFFICES:
            for code in sorted(set(CODES)):
                scope = year, office, code
                rows = grouped.get(scope, [])
                item = dict(year=year, office=office, state_code=code, status="not_reviewed_in_this_pipeline",
                    source_candidate_rows="", source_counties="", arithmetic_matched_counties="",
                    integer_accepted_counties="", withheld_counties="", source_gap_records=native_gaps[scope],
                    source_no_ballot_records=native_absences[scope], county_candidate_maps=0,
                    fully_complete=False)
                if office == "president" and year % 4:
                    item["status"] = "no_regular_presidential_election"
                if rows:
                    item.update(status="compiled_counts_reviewed_not_map_or_reuse_approval",
                        source_candidate_rows=sum(row["candidate_rows"] for row in rows), source_counties=len(rows),
                        arithmetic_matched_counties=sum(row["arithmetic_matches_source_summary"] for row in rows),
                        integer_accepted_counties=sum(row["integer_counts_accepted"] for row in rows),
                        withheld_counties=sum(not row["integer_counts_accepted"] for row in rows))
                if year == 2026 and office == "house" and code in current_index["coverage"]:
                    count = current_index["coverage"][code]["counties"]
                    item.update(status="reviewed_partial_county_map", source_counties=count,
                        arithmetic_matched_counties=count, integer_accepted_counties=count,
                        withheld_counties=0, county_candidate_maps=count)
                result.append(item)
    return result


def review(archive_path, output):
    acquisition = json.loads(ACQUISITION.read_bytes())
    raw = archive_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != acquisition["complete_download_sha256"]:
        raise ValueError("Changed pinned original historical archive")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt original historical archive")

        def table(name):
            return list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig"), newline="")))

        rows, summaries = table("us_county_results_long.csv"), table("us_county_results_summary.csv")
        report, parties, accepted, audit = reconcile(rows, summaries)
        sources = table("SOURCES.csv")
        audit.update(input_rows=len(rows), source_commit=acquisition["source_commit"],
            complete_original_url=acquisition["complete_download_url"],
            complete_original_sha256=acquisition["complete_download_sha256"],
            stage_rows=dict(Counter(row["stage"] for row in rows)),
            source_license_statuses=dict(Counter(row["license_status"] for row in sources)),
            compilation_attribution="Paul Heideman (2026), U.S. county-level election results, v1.0.0, CC BY 4.0.",
            publication_status="Local derived tables only. Arithmetic is not source certification, reuse permission, "
            "correct-election geometry approval or proof of complete coverage. Preserve upstream license terms.",
            candidate_votes_are_not_ballots_or_turnout=True, new_maps_approved=False)
        pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
        index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
        state_codes = {row["state"].upper(): row["state_po"] for row in rows}
        ledger = coverage(report, table("us_county_results_gaps.csv"),
                          table("us_county_results_no_ballot.csv"), index, state_codes)
    output.mkdir(parents=True, exist_ok=False)
    for name, records in (("county-review.csv", report), ("county-party-totals.csv", parties),
                          ("candidate-party-lines.csv", accepted), ("county-candidate-coverage.csv", ledger)):
        (output / (name + ".gz")).write_bytes(gzip.compress(csv_bytes(records), mtime=0))
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "checksums.json").write_text(json.dumps({
        path.name: dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.iterdir())}, indent=2) + "\n")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.source_archive, args.output), indent=2))

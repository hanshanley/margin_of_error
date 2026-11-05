"""Reconcile Idaho's complete public workbooks without allocating pooled ballots."""

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
from urllib.parse import unquote
import zipfile

import openpyxl


spec = importlib.util.spec_from_file_location("precinct_results", Path(__file__).with_name("build-precinct-results.py"))
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)
PORTAL = "https://results.voteidaho.gov/results/public/id/elections/nov2026"
API = "https://results.voteidaho.gov/results/public/api/elections/id/nov2026/"
JURISDICTION = "8c9d6490-6c2e-460e-8e42-0d1c8609ce42"
ELECTION = "01000000-9c16-51a0-5d47-08df20ba1eaa"
SUMMARY_FIELDS = ["County", "Office Name", "Contest ID", "Ballot Name", "Choice ID", "Party", "Total", "Votes Allowed"]
PRECINCT_FIELDS = ["Precinct"] + SUMMARY_FIELDS
BALLOT_FIELDS = ["County", "Precinct", "Total Number of Registered Voters at the cutoff",
                 "Total Number of Election Day Registrants", "Total Number of Registered Voters",
                 "Total Number of Ballots Cast", "% of Registered Voters who Voted"]
STATISTICS = {"Ballots Cast", "Over Votes", "Under Votes"}
PARTIES = {"DEM": "Democratic", "REP": "Republican", "IND": "Independent",
           "CON": "Constitution", "LIB": "Libertarian"}
EXTRA_FIELDS = ["congressional_district", "reported_ballots", "overvotes", "undervotes"]


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Missing or invalid Idaho count; do not substitute zero")
    return value


def english(values):
    texts = [row["text"] for row in values if row["languageId"] == "en"]
    if len(texts) != 1 or not texts[0]:
        raise ValueError("Missing or ambiguous Idaho English identity")
    return texts[0]


def workbook_rows(path, title, fields):
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = book[title]
        rows = sheet.iter_rows(values_only=True)
        header = next(rows)
        if list(header[:len(fields)]) != fields or any(value is not None for value in header[len(fields):]):
            raise ValueError("Idaho workbook schema changed")
        for row in rows:
            if not any(value is not None for value in row):
                continue
            if any(value is not None for value in row[len(fields):]):
                raise ValueError("Unexpected Idaho workbook data outside reviewed columns")
            yield tuple(row[:len(fields)])
    finally:
        book.close()


def idaho_results(summary, precincts, ballots, metadata):
    election = metadata["election"]
    if (election["id"] != ELECTION or election["jurisdictionId"] != JURISDICTION
            or election["electionDate"] != "2026-11-03" or election["isPrimary"] is not False
            or election["isProduction"] is not True
            or english(election["name"]) != "General Election - November 3, 2026"):
        raise ValueError("Incorrect Idaho election identity")
    registrations = {}
    for row in metadata["voterRegistration"]:
        county = english(row["localityName"])
        if county in registrations:
            raise ValueError("Duplicate Idaho county registration identity")
        registrations[county] = count(row["total"])
    expected, rollup, groups = {}, Counter(), defaultdict(dict)
    for row in summary:
        county, office, contest, name, choice, party, total, allowed = row
        key = (county, office, contest, name, choice, party, allowed)
        if county not in registrations or key in expected or not all([office, contest, name]):
            raise ValueError("Duplicate or unknown Idaho county-summary identity")
        expected[key] = count(total)
    seen, units = set(), set()
    for row in precincts:
        precinct, county, office, contest, name, choice, party, total, allowed = row
        key = (county, office, contest, name, choice, party, allowed)
        unit = (county, precinct)
        if (not isinstance(precinct, str) or not precinct or key not in expected
                or (unit, key) in seen):
            raise ValueError("Duplicate or unknown Idaho precinct-result identity")
        seen.add((unit, key))
        units.add(unit)
        rollup[key] += count(total)
        if contest in {"usrep1", "usrep2"}:
            if office != f"United States Representative District {contest[-1]}" or allowed != 1:
                raise ValueError("Incorrect Idaho House contest scope")
            identity = (county, precinct, contest)
            option = (name, choice, party)
            if option in groups[identity]:
                raise ValueError("Duplicate Idaho House candidate/statistic")
            groups[identity][option] = total
    if set(expected) != set(rollup) or any(expected[key] != rollup[key] for key in expected):
        raise ValueError("Idaho precinct-to-county totals do not reconcile")
    candidates, district_totals = {}, defaultdict(Counter)
    for item in metadata["ballotItems"]:
        name = english(item["name"])
        if name not in {f"United States Representative District {n}" for n in [1, 2]}:
            continue
        contest = "usrep" + name[-1]
        if contest in candidates or english(item["voteFor"]) != "Vote for 1":
            raise ValueError("Duplicate or incorrect Idaho House district scope")
        candidates[contest] = {}
        for option in item["summaryResults"]["ballotOptions"]:
            cid = option["nativeId"]
            party = option["party"]["abbreviation"]
            if not cid or cid in candidates[contest] or party not in PARTIES:
                raise ValueError("Duplicate or unreviewed Idaho House candidate identity")
            candidates[contest][cid] = dict(name=english(option["name"]), party=PARTIES[party],
                category=party if party in {"DEM", "REP"} else "OTHER", votes=count(option["voteCount"]))
        if sum(option["votes"] for option in candidates[contest].values()) != count(item["voteTotal"]):
            raise ValueError("Idaho district candidate totals do not reconcile")
    if set(candidates) != {"usrep1", "usrep2"}:
        raise ValueError("Missing Idaho House district")
    rows = []
    for (county, precinct, contest), options in sorted(groups.items()):
        statistics, votes, sums = {}, {}, Counter()
        for (name, choice, party), total in options.items():
            if name in STATISTICS:
                if choice or party or name in statistics:
                    raise ValueError("Ambiguous Idaho House statistic identity")
                statistics[name] = total
                continue
            candidate = candidates[contest].get(choice)
            if (not candidate or candidate["name"] != name
                    or party not in {candidate["party"], candidate["party"] + " Party"} or choice in votes):
                raise ValueError("Idaho candidate identity differs from district API")
            votes[choice] = total
            sums[candidate["category"]] += total
            district_totals[contest][choice] += total
        if set(statistics) != STATISTICS or set(votes) != set(candidates[contest]):
            raise ValueError("Missing Idaho House candidate or statistic; do not substitute zero")
        if sum(votes.values()) + statistics["Over Votes"] + statistics["Under Votes"] != statistics["Ballots Cast"]:
            raise ValueError("Idaho House candidates, overvotes and undervotes do not reconcile to ballots")
        pooled = bool(re.search(r"absentee|early", precinct, flags=re.I))
        row = results.result(2026, "ID", county, precinct, "U.S. House",
            sums["DEM"], sums["REP"], sums["OTHER"], "Source-reported House votes; pooled absentee/early units remain separate.",
            PORTAL, kind="pooled_absentee_or_early_unit" if pooled else "source_reporting_unit")
        row.update(congressional_district=contest[-1], reported_ballots=statistics["Ballots Cast"],
                   overvotes=statistics["Over Votes"], undervotes=statistics["Under Votes"])
        rows.append(row)
    if len(rows) != len(units) or {(r["county"], r["precinct"]) for r in rows} != units:
        raise ValueError("Idaho House reporting-unit scope differs or a unit spans districts")
    for contest, options in candidates.items():
        if dict(district_totals[contest]) != {cid: option["votes"] for cid, option in options.items()}:
            raise ValueError("Idaho House precinct counts do not reconcile to district API")
    statistics, county_registration = {}, Counter()
    for county, precinct, cutoff, edr, registered, cast, source_percent in ballots:
        key = (county, precinct)
        if key in statistics or key not in units:
            raise ValueError("Duplicate or unknown Idaho ballot-report identity")
        statistics[key] = dict(registered_at_cutoff=count(cutoff), election_day_registrants=count(edr),
            registered=count(registered), ballots=count(cast), source_reported_percent=source_percent)
        county_registration[county] += registered
    if set(statistics) != units or {key[0] for key in units} != set(registrations):
        raise ValueError("Idaho ballot/results/county reporting scopes differ")
    pooled_counties = {r["county"] for r in rows if r["reporting_unit_kind"] == "pooled_absentee_or_early_unit"}
    participation = []
    for row in rows:
        county, precinct = row["county"], row["precinct"]
        record = statistics[(county, precinct)]
        flags = []
        if record["ballots"] != row["reported_ballots"]:
            flags.append("house_contest_ballots_disagree_with_ballot_report")
        if county in pooled_counties:
            flags.append("county_has_separately_reported_absentee_or_early_units")
        if row["reporting_unit_kind"] == "pooled_absentee_or_early_unit":
            flags.append("pooled_nongeographic_reporting_unit")
        if county_registration[county] != registrations[county]:
            flags.append("county_registration_does_not_reconcile_to_API")
        if record["registered_at_cutoff"] + record["election_day_registrants"] != record["registered"]:
            flags.append("registration_components_do_not_reconcile")
        if record["registered"] < 25:
            flags.append("small_or_missing_registration_denominator")
        if record["ballots"] > record["registered"]:
            flags.append("ballots_exceed_registration")
        participation.append(dict(year=2026, state_code="ID", key=row["key"], county=county, precinct=precinct,
            reporting_unit_kind=row["reporting_unit_kind"], **record, quality_flags=flags,
            house_contest_ballots=row["reported_ballots"],
            reported_pct=None if flags else 100 * record["ballots"] / record["registered"],
            basis="Unofficial reported ballots / source total registered voters; not final, citizen or demographic turnout.",
            source_url=PORTAL))
    return rows, participation, dict(original_summary_rows=len(expected), original_precinct_rows=len(seen),
        pooled_counties=sorted(pooled_counties),
        county_registration_disagreements=[dict(county=county, workbook=county_registration[county], api=total)
            for county, total in sorted(registrations.items()) if county_registration[county] != total],
        house_ballot_disagreements=[dict(county=r["county"], precinct=r["precinct"],
            house_contest_ballots=r["house_contest_ballots"], ballot_report=r["ballots"])
            for r in participation if r["house_contest_ballots"] != r["ballots"]],
        district_candidate_totals={contest: dict(totals) for contest, totals in district_totals.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Use new unpublished Idaho output and archive")
    receipts = json.loads((args.cache / "sources.json").read_text())
    names = ["public-response-01.json", "public-response-02.json", "ballots-by-precinct.xlsx",
             "summary-results.pdf", "precinct-results.pdf", "summary-and-precinct-results.xlsx"]
    if set(receipts) != set(names):
        raise ValueError("Missing or unexpected Idaho original sources")
    originals = {}
    for name in names:
        raw = (args.cache / name).read_bytes()
        if len(raw) != receipts[name]["bytes"] or hashlib.sha256(raw).hexdigest() != receipts[name]["sha256"]:
            raise ValueError("Idaho original bytes disagree with acquisition receipt")
        originals[name] = raw
    metadata = json.loads(originals["public-response-02.json"])
    if receipts[names[0]]["url"] != API + "closeraces" or receipts[names[1]]["url"] != API + "data":
        raise ValueError("Incorrect Idaho public API source")
    advertised = {r["blobName"] for c in metadata["election"]["publicReportCategories"] for r in c["reports"]}
    base = f"https://results.voteidaho.gov/cdn/results/{JURISDICTION}/"
    actual = set()
    for name in names[2:]:
        url = receipts[name]["url"]
        if not url.startswith(base):
            raise ValueError("Unadvertised Idaho report host or jurisdiction")
        actual.add(unquote(url[len(base):]))
    if actual != advertised:
        raise ValueError("Idaho originals do not exactly match the advertised reports")
    close_races = json.loads(originals[names[0]])
    jurisdiction_ids = {JURISDICTION} | {r["id"] for r in metadata["voterRegistration"]}
    if not isinstance(close_races, list) or any(
            r["jurisdictionId"] not in jurisdiction_ids
            or any(item["publishPublicElectionId"] != "nov2026" for item in r["ballotItems"])
            for r in close_races):
        raise ValueError("Idaho close-races capture belongs to another election")
    rows, participation, reconciliation = idaho_results(
        workbook_rows(args.cache / names[5], "Summary Results", SUMMARY_FIELDS),
        workbook_rows(args.cache / names[5], "Precinct Results", PRECINCT_FIELDS),
        workbook_rows(args.cache / names[2], "Ballots Cast by Precinct", BALLOT_FIELDS), metadata)
    if len(rows) != 986 or len({row["county"] for row in rows}) != 44:
        raise ValueError("Idaho reporting scope changed; review before publication")
    args.output.mkdir(parents=True)
    (args.output / "originals").mkdir()
    for name, raw in originals.items():
        (args.output / "originals" / (name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
    text = io.StringIO()
    writer = csv.DictWriter(text, results.CSV_FIELDS + EXTRA_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(text.getvalue().encode(), mtime=0))
    (args.output / "participation.json.gz").write_bytes(gzip.compress(
        json.dumps(participation, separators=(",", ":")).encode(), mtime=0))
    (args.output / "original-source-checksums.json").write_text(json.dumps(receipts, indent=2) + "\n")
    audit = dict(year=2026, state_code="ID", complete="no", reporting_units=len(rows), counties=44,
        candidate_results="acquired_reconciled", participation="acquired_precinct_counts_and_provisional_rates",
        boundaries="correct_election_reference_pending", join="withheld", validation="counts_passed_map_withheld",
        publication="full_counts_download_only", source_url=PORTAL,
        election_id=ELECTION, election_version=metadata["election"]["publishVersionId"],
        source_updated=metadata["election"]["asOf"], original_sources=len(originals),
        original_bytes=sum(len(raw) for raw in originals.values()),
        candidate_totals={field: sum(row[field] for row in rows) for field in
            ["democratic_votes", "republican_votes", "other_votes", "contest_votes"]},
        ballots=sum(row["ballots"] for row in participation),
        registrations=sum(row["registered"] for row in participation),
        rates_available=sum(row["reported_pct"] is not None for row in participation),
        rates_withheld=sum(row["reported_pct"] is None for row in participation),
        reconciliation=reconciliation,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-precinct-idaho-20261105/complete-idaho-2026-source-review.zip",
        notes="All original precinct candidate/statistic rows reconcile to the complete county-summary workbook. "
              "House candidates additionally reconcile by native candidate identity to both district API totals; "
              "only the explicit optional terminal ' Party' label is normalized between county exports. "
              "candidate votes plus overvotes and undervotes equal House-contest ballots for every unit. "
              "Separate ballot-report disagreements remain explicit and have no participation rate. "
              "Other contests' candidate semantics are not independently reviewed. "
              "Registration and ballot counts remain separate from candidate votes. Provisional fractions are "
              "withheld for entire counties with separately reported absentee/early units or an API registration "
              "disagreement, and for small, missing or inconsistent local denominators. Source percentages and "
              "all original counts are retained, never allocated or repaired. These are source reporting units, "
              "not verified polling-precinct geography or demographic participation estimates. "
              "The complete ZIP retains both complete XLSX workbooks, both PDFs, both public JSON captures, "
              "all normalized House and participation rows, receipts and audits. No boundaries are mapped.",
        next_action="Acquire explicitly identified 2026 precinct geography and documented reporting-unit crosswalks. "
                    "Resolve pooled absentee/early scope, Twin Falls registration disagreement and local denominators "
                    "before enabling withheld rates. Do not substitute the portal's Idaho2025 basemap.")
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    checksums = {str(path.relative_to(args.output)): dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(args.output.rglob("*")) if path.is_file()}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(args.output)))
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()

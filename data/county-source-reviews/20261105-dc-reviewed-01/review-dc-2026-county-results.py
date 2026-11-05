"""Reconcile D.C.'s native reports, keeping delegate votes separate from ballots."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile


DELEGATE = "DELEGATE TO THE HOUSE OF REPRESENTATIVES FROM THE DISTRICT OF COLUMBIA"
ACCOUNTING = {"OVER VOTES", "UNDER VOTES"}
HEADERS = ["ElectionDate", "ElectionName", "ContestNumber", "ContestName",
           "PrecinctNumber", "WardNumber", "Candidate", "Party", "Votes"]
SOURCE = "https://electionresults.dcboe.org"
LIMITATIONS = [
    "Nonvoting delegate only, not a voting House district or the shadow Senator/Representative offices.",
    "Native RCV-marked published tallies; no independently verified round or final ranked-choice outcome.",
    "Accounting party literals are retained separately, never counted as candidate-party votes.",
    "The delegate accounting difference is unresolved, not filled or allocated into candidates.",
    "Native EarlyVotes zero with ShowEarlyVotes false does not establish zero early ballots.",
    "No new map, 2026 precinct geometry, demographic estimate or final certified turnout is approved.",
    "Complete native originals remain attached; no blanket upstream license certification is asserted.",
]


def integer(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"0|[1-9]\d*", value):
        return int(value)
    raise ValueError(f"Missing or invalid explicit integer: {value!r}")


def load_originals(source):
    receipts = json.loads((source / "receipts.json").read_bytes())
    names = {"election.json", "citywide.json", "voters.json", "parties.json",
             "report.csv", "report.xml", "report.pdf"}
    if {r["file"] for r in receipts} != names or len(receipts) != len(names):
        raise ValueError("Missing or duplicate original receipt")
    raw = {}
    for receipt in receipts:
        name = receipt["file"]
        data = (source / name).read_bytes()
        if (receipt["status"] != 200 or receipt["bytes"] != len(data)
                or receipt["sha256"] != hashlib.sha256(data).hexdigest()
                or not receipt["url"].startswith(SOURCE + "/")):
            raise ValueError(f"Original disagrees with official acquisition receipt: {name}")
        raw[name] = data
    election = json.loads(raw["election.json"])
    for field, name in [("CsvLink", "report.csv"), ("XmlLink", "report.xml"),
                        ("PdfLink", "report.pdf")]:
        if election[field] != next(r["url"] for r in receipts if r["file"] == name):
            raise ValueError("Report URL differs from native declared election report")
    return raw


def review(raw):
    election = json.loads(raw["election.json"])
    voters = json.loads(raw["voters.json"])
    citywide = json.loads(raw["citywide.json"])
    if (election["ElectionName"] != "General Election"
            or election["ElectionDate"] != "2026-11-03T00:00:00"
            or election["ElectionResultsTypeName"] != "Election Night Unofficial Results"
            or re.search(r"\btest(?:ing)?\b", election.get("ElectionNameDisplay", ""), re.I)):
        raise ValueError("Wrong election or source test/publication status")
    reader = csv.DictReader(io.StringIO(raw["report.csv"].decode("utf-8-sig"), newline=""))
    if reader.fieldnames != HEADERS:
        raise ValueError("Changed native CSV schema")
    native = list(reader)
    sums, csv_parties, contest_ids, unit_wards = Counter(), defaultdict(set), {}, {}
    seen = set()
    for row in native:
        if (None in row or None in row.values()
                or row["ElectionDate"] != "11/3/2026 12:00:00 AM"
                or row["ElectionName"] != election["ElectionName"]):
            raise ValueError("Malformed row or wrong CSV election")
        count = integer(row["Votes"])
        integer(row["PrecinctNumber"])
        integer(row["WardNumber"])
        identity = (row["ContestNumber"], row["PrecinctNumber"], row["Candidate"])
        if identity in seen:
            raise ValueError("Duplicate native CSV observation")
        seen.add(identity)
        contest = row["ContestName"]
        if contest in contest_ids and contest_ids[contest] != row["ContestNumber"]:
            raise ValueError("Ambiguous native contest identity")
        contest_ids[contest] = row["ContestNumber"]
        unit = row["PrecinctNumber"]
        if unit in unit_wards and unit_wards[unit] != row["WardNumber"]:
            raise ValueError("Native unit has inconsistent ward identity")
        unit_wards[unit] = row["WardNumber"]
        key = (contest, row["Candidate"])
        sums[key] += count
        csv_parties[key].add(row["Party"])
    if (not native or len(unit_wards) != integer(election["TotalPrecincts"])
            or integer(election["PrecinctsCounted"]) != len(unit_wards)):
        raise ValueError("Missing native reporting units")

    xml = ET.fromstring(raw["report.xml"])
    if (xml.findtext("ElectionName") != election["ElectionName"]
            or xml.findtext("ElectionDate") != election["ElectionDate"]):
        raise ValueError("Wrong XML election")
    summary, xml_values = [], {}
    for contest in xml.findall("./ContestList/ContestDataExportViewModel"):
        name = contest.findtext("ContestName")
        for record in contest.findall("./ElectionData/ElectionDataExportViewModel"):
            candidate = record.findtext("Candidate", "")
            party = record.findtext("Party", "")
            key = (name, candidate)
            count = integer(record.findtext("Votes"))
            if key in xml_values or key not in sums or sums[key] != count:
                raise ValueError("Missing, duplicate or unreconciled XML summary")
            if len(csv_parties[key]) != 1:
                raise ValueError("Inconsistent native candidate-party identity")
            csv_party = next(iter(csv_parties[key]))
            if candidate not in ACCOUNTING and csv_party != party:
                raise ValueError("Non-accounting candidate party disagreement")
            xml_values[key] = (count, party)
            kind = ("ballot_accounting" if candidate in ACCOUNTING else
                    "participation_summary" if contest_ids[name] in ("-2", "-1")
                    else "candidate_or_option")
            summary.append(dict(contest_number=contest_ids[name], contest_name=name,
                                candidate_or_option=candidate, row_type=kind,
                                party_csv_literal=csv_party, party_xml_literal=party,
                                party_literal_disagreement=csv_party != party, votes=count))
    if set(xml_values) != set(sums):
        raise ValueError("XML does not cover every native CSV observation")

    scoped = [c for c in citywide if c["OfficeName"] == DELEGATE]
    if len(scoped) != 1 or scoped[0]["ContestNumber"] != 4:
        raise ValueError("Missing or ambiguous nonvoting delegate contest")
    contest = scoped[0]
    options = contest["ElectionData"]
    if (len({r["Contestant"] for r in options}) != len(options)
            or {r["Contestant"] for r in options} != {k[1] for k in sums if k[0] == DELEGATE}):
        raise ValueError("Delegate city/CSV option identities disagree")
    candidate_total = sum(integer(r["Votes"]) for r in options if r["Contestant"] not in ACCOUNTING)
    candidates, accounting = [], []
    for row in options:
        name = row["Contestant"]
        if (xml_values[(DELEGATE, name)] != (integer(row["Votes"]), row["PartyCode"])
                or integer(row["TotalVotes"]) != candidate_total):
            raise ValueError("Delegate city JSON disagrees with CSV/XML")
        data = dict(year=2026, state_code="DC", county_fips="11001",
                    office="nonvoting_us_house_delegate", contest_number=4,
                    contest_name=DELEGATE, candidate_or_accounting_literal=name,
                    party_csv_literal=next(iter(csv_parties[(DELEGATE, name)])),
                    party_json_literal=row["PartyCode"], votes=integer(row["Votes"]),
                    source_update_literal=election["LastUpdated"],
                    result_status=election["ElectionResultsTypeName"],
                    native_is_rcv=contest["IsRCV"], final_rcv_round_verified=False)
        (accounting if name in ACCOUNTING else candidates).append(data)
    if {r["candidate_or_accounting_literal"] for r in accounting} != ACCOUNTING:
        raise ValueError("Missing delegate accounting option")
    party_votes = Counter()
    for row in candidates:
        party_votes[row["party_csv_literal"]] += row["votes"]

    units = defaultdict(dict)
    for row in native:
        if row["ContestNumber"] in ("-2", "-1"):
            field = "registered_voters" if row["ContestNumber"] == "-2" else "ballots_cast"
            if (row["Candidate"] or row["Party"] != "CITYWIDE"
                    or field in units[row["PrecinctNumber"]]):
                raise ValueError("Duplicate or ambiguous unit participation")
            units[row["PrecinctNumber"]][field] = integer(row["Votes"])
    if set(units) != set(unit_wards) or any(set(u) != {"registered_voters", "ballots_cast"} for u in units.values()):
        raise ValueError("Missing native participation observation")
    registered, ballots = integer(voters["RegisteredVoters"]), integer(voters["TotalBallotsCast"])
    if (voters["SummaryType"] != "c" or voters["WardNumber"] is not None
            or voters["PrecinctNumber"] is not None
            or sum(u["registered_voters"] for u in units.values()) != registered
            or sum(u["ballots_cast"] for u in units.values()) != ballots
            or not registered or ballots > registered):
        raise ValueError("Native participation does not reconcile to city summary")
    delegate_rows = [r for r in native if r["ContestNumber"] == "4"]
    for unit in units:
        names = [r["Candidate"] for r in delegate_rows if r["PrecinctNumber"] == unit]
        if set(names) != {r["Contestant"] for r in options} or len(names) != len(options):
            raise ValueError("Missing delegate option in native reporting unit")
    accounted = candidate_total + sum(r["votes"] for r in accounting)
    participation = dict(year=2026, state_code="DC", county_fips="11001",
                         geography="District of Columbia", geography_level="county_equivalent",
                         registered_voters=registered, ballots_cast=ballots,
                         registered_ballot_ratio_pct=100 * ballots / registered,
                         delegate_candidate_votes=candidate_total,
                         delegate_over_under_votes=sum(r["votes"] for r in accounting),
                         delegate_accounted_votes=accounted,
                         unresolved_ballot_accounting_difference=ballots - accounted,
                         native_election_day_voters=integer(voters["ElectionDayVoters"]),
                         native_absentee_special_ballot_votes=integer(voters["AbsenteeSpecialBallotVotes"]),
                         native_early_votes=integer(voters["EarlyVotes"]),
                         native_show_early_votes=election["ShowEarlyVotes"],
                         early_ballot_total_established=False,
                         source_update_literal=election["LastUpdated"],
                         result_status=election["ElectionResultsTypeName"])
    unit_participation = [dict(precinct_number=unit, ward_number=unit_wards[unit], **counts)
                          for unit, counts in units.items()]
    tables = {
        "county-delegate-candidate-results.csv": candidates,
        "county-delegate-party-totals.csv": [
            dict(year=2026, state_code="DC", county_fips="11001",
                 office="nonvoting_us_house_delegate", party_literal=party, votes=count)
            for party, count in sorted(party_votes.items())],
        "county-delegate-ballot-accounting.csv": accounting,
        "county-participation.csv": [participation],
        "native-unit-participation.csv": unit_participation,
        "native-unit-delegate-counts.csv": delegate_rows,
        "all-contest-native-summary.csv": summary,
    }
    audit = dict(status="original_backed_counts_reviewed_not_final_rcv_or_maps",
                 native_csv_rows=len(native), native_csv_zero_rows=sum(r["Votes"] == "0" for r in native),
                 native_contests=len(contest_ids), xml_summary_rows=len(summary),
                 accounting_party_literal_disagreements=sum(r["party_literal_disagreement"] for r in summary),
                 native_reporting_units=len(units), participation=participation,
                 delegate_candidate_rows=len(candidates),
                 delegate_literal_party_totals=dict(sorted(party_votes.items())),
                 source_update_literal=election["LastUpdated"],
                 source_election_is_rcv=election["IsRCV"],
                 native_rcv_status_id=election["RCVStatusId"],
                 native_rcv_published_display_names=election["RCVPublishedDisplayNames"],
                 final_rcv_round_verified=False, new_maps_approved=False,
                 fully_complete=False, limitations=LIMITATIONS,
                 table_rows={name: len(rows) for name, rows in tables.items()})
    return tables, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    raw = load_originals(args.source)
    tables, audit = review(raw)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, rows in tables.items():
        with (args.output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    shutil.copytree(args.source, args.output / "originals")
    shutil.copyfile(__file__, args.output / Path(__file__).name)
    paths = sorted(p for p in args.output.rglob("*") if p.is_file())
    checksums = {p.relative_to(args.output).as_posix(): dict(
        bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in args.output.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(args.output).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()

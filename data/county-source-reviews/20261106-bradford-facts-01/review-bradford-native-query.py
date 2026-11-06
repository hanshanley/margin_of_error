"""Reproduce both complete Bradford Election Day summary queries offline."""

import argparse
from collections import Counter
import csv
from decimal import Decimal, ROUND_HALF_UP
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


INPUT_SHA256 = "0a7a245d36e90702acb85fc14d9c103186f504f432b51ccac69b229c5483ecf0"
ARCHIVE = "complete-bradford-election-day-native-query-01.zip"
TITLES = (
    "GOVERNOR AND LT GOVERNOR",
    "REPRESENTATIVE IN CONGRESS 9TH CONGRESSIONAL DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 68TH LEGISLATIVE DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 110TH LEGISLATIVE DISTRICT",
)
HEADERS = (
    ("bradford-election-day-final.pdf", 20982, "53.73", 61, "11/3/2026 10:15:12 PM EST",
     "Unofficial Final Election Day Results"),
    ("bradford-earlier-results.pdf", 12488, "31.98", 46, "11/3/2026 8:45:38 PM EST",
     "Unoffcial Results 5"),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def percent(numerator, denominator):
    return (Decimal(100) * numerator / denominator).quantize(
        Decimal(".01"), rounding=ROUND_HALF_UP)


def validate(records, check_pinned=True):
    if check_pinned:
        require(hashlib.sha256(json_bytes(records)).hexdigest() == INPUT_SHA256,
                "Changed complete factual input")
    require((records["year"], records["state_code"], records["county"]) == (2026, "PA", "Bradford"),
            "Changed election identity")
    require(records["source_fips"] == "", "Invented native FIPS")
    require(records["all_mode_participation"] is None and records["counted_mail_ballots"] is None,
            "Invented all-mode or counted-mail participation")
    require(records["parent_received_mail_absentee_ballots"] == 3346, "Changed separate mail receipts")
    require(records["maps_approved"] is False and records["counting_complete"] is False,
            "Invented mapping or completed-counting approval")
    require(len(records["snapshots"]) == 2, "Missing earlier or later snapshot")
    for row, expected in zip(records["snapshots"], HEADERS):
        snapshot, contests = row["snapshot"], row["contests"]
        require(tuple(snapshot[field] for field in (
            "file", "native_total_ballots", "printed_pct", "reported_precincts",
            "source_update_literal", "source_status_literal")) == expected,
            "Changed native snapshot identity, clock or status")
        require(snapshot["registered_voters"] == 39048 and snapshot["total_precincts"] == 61,
                "Changed native county reporting universe")
        require(snapshot["voting_mode_literal"] == "Election Day", "Promoted Election Day to all-mode")
        require(percent(snapshot["native_total_ballots"], 39048) == Decimal(snapshot["printed_pct"]),
                "Printed participation fraction disagrees")
        require(len(contests) == 4, "Incomplete contest query")
        for contest, title, size in zip(contests, TITLES, (4, 3, 3, 3)):
            require(contest["contest_literal"] == title and contest["vote_for"] == 1,
                    "Changed contest or office stage")
            choices = contest["choices"]
            require(len(choices) == size, "Incomplete candidate/write-in query")
            require(sum(choice["votes"] for choice in choices) == contest["total_votes"],
                    "Native choice sum disagrees with printed total")
            require(0 < contest["reporting_precincts"] <= contest["total_precincts"],
                    "Invalid contest reporting units")
            require(percent(contest["reporting_precincts"], contest["total_precincts"])
                    == Decimal(contest["native_printed_reporting_percent"]),
                    "Printed reporting fraction disagrees")
            for choice in choices:
                require(type(choice["votes"]) is int and choice["votes"] >= 0, "Invalid native votes")
                require(percent(choice["votes"], contest["total_votes"])
                        == Decimal(choice["native_printed_percent"]), "Printed candidate fraction disagrees")
                label = " ".join(choice["native_label_lines"])
                match = re.search(r"\s*\(([^()]*)\)$", label)
                party = match.group(1) if match else ""
                name = label[:match.start()].strip() if match else label
                require((name, party) == (choice["native_choice"], choice["native_party"]),
                        "Changed native candidate lines or inferred write-in party")
        require(sum(contest["total_precincts"] for contest in contests[2:]) == 61,
                "Changed within-county Assembly scopes")
        require(all(contest["total_precincts"] == 61 for contest in contests[:2]),
                "Changed countywide report scope")
    require(len(records["source_receipts"]) == 3 and len(records["source_declarations"]) == 2,
            "Incomplete actual source receipts/declarations")


def csv_bytes(rows):
    require(bool(rows), "Empty native query table")
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return target.getvalue().encode()


def tables(records):
    validate(records)
    candidates, contests, accounting, parties, participation = [], [], [], [], []
    for row in records["snapshots"]:
        snapshot = row["snapshot"]
        identity = dict(year=2026, state_code="PA", county="Bradford", source_file=snapshot["file"],
                        source_update_literal=snapshot["source_update_literal"],
                        source_status_literal=snapshot["source_status_literal"],
                        voting_mode_literal=snapshot["voting_mode_literal"])
        participation.append(dict(**identity, native_total_ballots=snapshot["native_total_ballots"],
            registered_voters=snapshot["registered_voters"], native_printed_turnout=snapshot["printed_pct"],
            native_percent_unit="percent", reported_precincts=snapshot["reported_precincts"],
            total_precincts=snapshot["total_precincts"], all_mode_participation_approved=False,
            counted_mail_ballots="", source_fips="", counting_complete=False, maps_approved=False))
        for index, contest in enumerate(row["contests"]):
            scope = "countywide_Election_Day_summary" if index < 2 else "within_county_Assembly_district_subset"
            base = dict(**identity, contest_literal=contest["contest_literal"], geographic_scope=scope)
            choices = contest["choices"]
            contests.append(dict(**base, native_total_votes=contest["total_votes"], vote_for=contest["vote_for"],
                reporting_precincts=contest["reporting_precincts"], total_precincts=contest["total_precincts"],
                native_printed_reporting_percent=contest["native_printed_reporting_percent"]))
            for choice in choices:
                candidates.append(dict(**base, native_choice=choice["native_choice"],
                    native_party=choice["native_party"], votes=choice["votes"],
                    native_printed_percent=choice["native_printed_percent"],
                    native_label_lines_json=json.dumps(choice["native_label_lines"], ensure_ascii=True),
                    kind="write_in_total" if choice["native_choice"] == "Write-in" else "candidate"))
            total = sum(choice["votes"] for choice in choices)
            accounting.append(dict(**base, derived_candidate_sum=total,
                native_scope_ballots=snapshot["native_total_ballots"] if index < 2 else "",
                unclassified_ballot_minus_candidate_sum=snapshot["native_total_ballots"]-total if index < 2 else "",
                qualifications="Candidate votes are not voters; residuals are unclassified; district electorates are not extrapolated."))
            totals = Counter()
            for choice in choices:
                totals[choice["native_party"]] += choice["votes"]
            parties.extend(dict(**base, native_party=party, votes=votes,
                measure="candidate_choice_votes_not_party_participation") for party, votes in totals.items())
    return {
        "county-candidate-results.csv": candidates,
        "native-contest-query.csv": contests,
        "county-contest-accounting.csv": accounting,
        "county-literal-party-totals.csv": parties,
        "election-day-participation.csv": participation,
        "parent-processing-observations.csv": [dict(year=2026, state_code="PA", county="Bradford",
            received_mail_absentee_ballots=3346, counted_mail_ballots="", all_mode_participation="",
            source_url=records["source_receipts"][0]["url"],
            qualifications="Parent receipt count; not counted mail, not added to Election Day ballots.")],
        "native-source-declarations.csv": records["source_declarations"],
        "source-receipts.csv": records["source_receipts"],
    }


def reproduce(folder):
    records = json.loads(gzip.decompress((folder / "source-records.json.gz").read_bytes()))
    exported = {name: csv_bytes(rows) for name, rows in tables(records).items()}
    exported["audit.json"] = json_bytes(dict(
        county="Bradford", year=2026, native_snapshots=2, contest_snapshots=8, candidate_choice_rows=26,
        voting_mode_literal="Election Day", later_ballots=20982, earlier_ballots=12488,
        registered_voters=39048, parent_received_mail_absentee_ballots=3346, counted_mail_ballots=None,
        all_mode_participation=None, maps_approved=False, counting_complete=False,
        original_html_or_pdf_redistributed=False, complete_factual_query=True,
        qualifications=[
            "Both complete factual Election Day summary queries are reproduced, not source templates.",
            "Both original report bodies independently reconciled using pypdf and PyMuPDF before packaging.",
            "The earlier snapshot and literal Unoffcial status typo remain separate and unchanged.",
            "Election Day ballots and percentages are not promoted to all-mode county participation.",
            "Separate parent mail receipts are not counted mail and are never added to reported ballots.",
            "Assembly 68 and 110 are distinct within-county scopes, not whole-county electorates.",
            "Write-in parties remain missing; native names, line wraps, parties, clocks and percentages survive.",
            "Candidate-party votes are not voter participation by party; residuals remain unclassified.",
            "No election geometry, demographic turnout, completed counting or nationwide completeness is approved."]))
    exported.update({name: (folder / name).read_bytes() for name in (
        "source-records.json.gz", "review-bradford-native-query.py", "test-bradford-native-query.py")})
    exported["checksums.json"] = json_bytes([
        dict(file=name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(exported.items())])
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(exported.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, body, compresslevel=9)
    exported[ARCHIVE] = target.getvalue()
    return exported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    folder = Path(__file__).parent
    expected = reproduce(folder)
    for name, body in expected.items():
        if args.write:
            (folder / name).write_bytes(body)
        require((folder / name).read_bytes() == body, "Changed complete output: " + name)
    print(f"All {len(expected)} entire files reproduce, including the complete archive.")

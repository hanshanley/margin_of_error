"""Reproduce the complete native Maryland unofficial turnout query offline."""

import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


TITLE = "Unofficial MIB 1, Early Voting and Election Day Turnout"
ELECTION = "Election: 2026 Gubernatorial General"
COUNTIES = (
    "Allegany County", "Anne Arundel County", "Baltimore City", "Baltimore County",
    "Calvert County", "Caroline County", "Carroll County", "Cecil County",
    "Charles County", "Dorchester County", "Frederick County", "Garrett County",
    "Harford County", "Howard County", "Kent County", "Montgomery County",
    "Prince George's County", "Queen Anne's County", "Saint Mary's County",
    "Somerset County", "Talbot County", "Washington County", "Wicomico County",
    "Worcester County",
)
NUMBER = r"(?:0|[1-9]\d{0,2}(?:,\d{3})*)"
ROW = re.compile(r"(.+?) \((\d+) of (\d+)\) (" + NUMBER + r") (" + NUMBER + r") (\d+\.\d{2})%")
TOTAL = re.compile(r"Total (" + NUMBER + r") (" + NUMBER + r") (\d+\.\d{2})%")
FIELDS = (
    "state_code", "native_geography_literal", "geography_level", "cards_cast",
    "eligible_voters", "native_printed_percentage", "reported_units", "total_units",
    "native_measure_literal", "native_denominator_literal", "native_status_literal",
    "native_election_literal", "native_update_literal", "declared_timezone", "source_fips",
    "mail_in_1_count", "early_voting_count", "election_day_count", "provisional_count",
    "candidate_votes", "unique_voters", "analysis_ballots_approved", "analysis_rates_approved",
    "maps_approved", "complete_counting", "source_url",
)
METHODS = """Maryland 2026 native unofficial turnout query

All 24 county equivalents and the separate statewide total come from the single
complete report actually linked by the Maryland State Board of Elections press
room. Two independently extracted complete numerical pages must agree on every
field. County sums and all 25 native rounded percentages are checked exactly.
The source update is a native literal with no supplied timezone.

Cards Cast and Eligible Voters remain the source's literal measures. This query
does not establish that cards are unique people or interchangeable with ballots,
or that Eligible Voters is CVAP, VAP, VEP, CPS or a matched registration snapshot.
The title names MIB 1, Early Voting and Election Day. Separate mode counts,
provisionals, candidate votes and unique-voter counts are absent, not zero.
Complete reporting-unit counters do not establish completed counting or
certification. No FIPS, contextual join, geometry or demographic rate is invented.
Generic ballot counts, analysis turnout rates and map approval remain withheld.

The separately acquired official-statistics guide is context only: its declaring
index explicitly limits its applicability to Official Turnout Statistics, not
this unofficial report. Its definitions are not silently imposed here.
Different source hosts and cached search extracts can represent other snapshots.
No values, clocks or totals from those snapshots are spliced into this query.
This is the acquired snapshot, not an assertion of the globally latest report.

Reproduce without third-party packages or network access:
python3 -I review-maryland.py --output /a/new/directory
Run the focused portable tests:
python3 -I test_review_maryland.py
The output directory must not already exist. The deterministic archive contains
all other complete query files, and checksums cover every file except themselves
and the archive. Original source URLs, sizes and SHA-256s are in native-source-pages.csv.
"""


def parse_page(text):
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if len(lines) != 29 or lines[:3] != [TITLE, ELECTION, "County Cards Cast Eligible Voters Percentage"]:
        raise ValueError("Unexpected complete report layout or election")
    clock = re.fullmatch(r"Run Date: (\d{1,2}/\d{1,2}/2026 \d{1,2}:\d{2} [ap]m)", lines[-1])
    total = TOTAL.fullmatch(lines[-2])
    if not clock or not total:
        raise ValueError("Missing native update or statewide total")
    rows = []
    for line in lines[3:-2]:
        match = ROW.fullmatch(line)
        if not match:
            raise ValueError("Malformed native county row")
        name, reported, units, cards, eligible, printed = match.groups()
        reported, units = int(reported), int(units)
        cards, eligible = int(cards.replace(",", "")), int(eligible.replace(",", ""))
        if not 0 <= reported <= units or eligible <= 0 or cards > eligible:
            raise ValueError("Invalid native reporting counters or counts")
        rows.append(dict(native_geography_literal=name, geography_level="county_equivalent",
            cards_cast=cards, eligible_voters=eligible, native_printed_percentage=printed + "%",
            reported_units=reported, total_units=units))
    if tuple(row["native_geography_literal"] for row in rows) != COUNTIES:
        raise ValueError("Missing, duplicated, reordered or unknown county")
    statewide = dict(native_geography_literal="Total", geography_level="statewide",
        cards_cast=int(total[1].replace(",", "")), eligible_voters=int(total[2].replace(",", "")),
        native_printed_percentage=total[3] + "%", reported_units="", total_units="")
    for field in ("cards_cast", "eligible_voters"):
        if sum(row[field] for row in rows) != statewide[field]:
            raise ValueError("County/statewide numerical disagreement")
    for row in [*rows, statewide]:
        actual = (Decimal(100) * row["cards_cast"] / row["eligible_voters"]).quantize(
            Decimal(".01"), rounding=ROUND_HALF_UP)
        if actual != Decimal(row["native_printed_percentage"][:-1]):
            raise ValueError("Native percentage disagrees with exact arithmetic")
    return rows, statewide, clock[1]


def review(facts):
    if set(facts["extractors"]) != {"pymupdf", "pdfplumber"}:
        raise ValueError("Two independent complete extractions are required")
    pages = []
    for name in ("pymupdf", "pdfplumber"):
        if len(facts["extractors"][name]) != 1:
            raise ValueError("The complete report has one page")
        pages.append(parse_page(facts["extractors"][name][0]))
    if pages[0] != pages[1]:
        raise ValueError("Independent numerical extractions disagree")
    source = facts["sources"][1]
    if source["status"] != 200 or source["content_type"] != "application/pdf":
        raise ValueError("The numerical source must be a successful complete PDF")
    if facts["declaration"]["url"] != source["final_url"] or "2026 General" not in facts["declaration"]["label"]:
        raise ValueError("The source must be the actually declared general report")
    rows, statewide, clock = pages[0]
    result = []
    for native in [*rows, statewide]:
        result.append(dict(state_code="MD", **native, native_measure_literal="Cards Cast",
            native_denominator_literal="Eligible Voters", native_status_literal="Unofficial",
            native_election_literal="2026 Gubernatorial General", native_update_literal=clock,
            declared_timezone="", source_fips="", mail_in_1_count="", early_voting_count="",
            election_day_count="", provisional_count="", candidate_votes="", unique_voters="",
            analysis_ballots_approved=False, analysis_rates_approved=False, maps_approved=False,
            complete_counting=False, source_url=source["final_url"]))
    return result


def csv_bytes(rows, fields):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def build(native_path, output):
    native_path, output = Path(native_path), Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite an existing output directory")
    native = native_path.read_bytes()
    facts = json.loads(native)
    rows = review(facts)
    output.mkdir(parents=True)
    files = {"native-facts.json": native,
        "county-native-participation.csv": csv_bytes(rows[:-1], FIELDS),
        "statewide-native-participation.csv": csv_bytes(rows[-1:], FIELDS),
        "native-source-pages.csv": csv_bytes(facts["sources"], tuple(facts["sources"][0])),
        "METHODS.txt": METHODS.encode(),
        "audit.json": (json.dumps(dict(county_equivalents=24, statewide_rows=1,
            independent_complete_extractions=2, all_county_fields_match=True,
            county_totals_match_statewide=True, native_percentages_checked=25,
            reporting_units=sum(row["reported_units"] for row in rows[:-1]),
            total_reporting_units=sum(row["total_units"] for row in rows[:-1]),
            native_clock=rows[0]["native_update_literal"], declared_timezone="",
            analysis_ballot_approvals=0, analysis_rate_approvals=0, map_approvals=0,
            missing_modes_remain_missing=True, official_guidance_not_imposed=True),
            indent=2) + "\n").encode()}
    for name in ("review-maryland.py", "test_review_maryland.py"):
        files[name] = Path(__file__).with_name(name).read_bytes()
    checksums = [dict(file=name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
                 for name, body in sorted(files.items())]
    files["checksums.json"] = (json.dumps(checksums, indent=2) + "\n").encode()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, body in sorted(files.items()):
            member = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            zipped.writestr(member, body)
    files["complete-query.zip"] = archive.getvalue()
    for name, body in files.items():
        (output / name).write_bytes(body)
    return checksums


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, default=Path(__file__).with_name("native-facts.json"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build(args.native, args.output)

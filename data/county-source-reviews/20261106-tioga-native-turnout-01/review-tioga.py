"""Reproduce the complete native Tioga query without network access or dependencies."""

import argparse
from collections import Counter
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


PARENT = "https://www.tiogacountypa.us/departments/voter-registration/election-results"
PDF = "https://www.tiogacountypa.us/getmedia/89deb223-31ad-4a42-a464-e27b6b77eef0/Unofficial-General-Nov-3-2026.pdf"
SOURCES = {
    PARENT: (40946, "5eaa4df400d65f6b7b2bc1534585b1ea43bb095a84e5976c855e55099ebaa3ae"),
    PDF: (365378, "3d5a971c20610c6a7b94a32cccb4e7880a30854e2a0c8a294f71df0fba2379ec"),
}
MODES = ("TOTAL", "Election Day", "Absentee /Mail-in", "Provisional Ballots")
CONTESTS = {
    "GOVERNOR AND LIEUTENANT GOVERNOR": {
        ("REP", "Stacy Garrity"), ("DEM", "Josh Shapiro"), ("LIB", "Ken Krawchuk"), ("", "Write-In Totals")},
    "REP IN CONGRESS 15TH DISTRICT": {
        ("REP", "Glenn GT Thompson"), ("DEM", "Ray Bilger"), ("", "Write-In Totals")},
    "REP IN GEN ASSEM 68TH DISTRICT": {
        ("REP", "Clint Owlett"), ("DEM", "Quentin Gee"), ("", "Write-In Totals")},
}
REPORTING = (
    "Election Day Precincts Reporting", "Precincts Complete",
    "Precincts Partially Reported", "Absentee/ Early Precincts Reporting",
)
INTEGER = r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)"
VECTOR = rf"({INTEGER}) ({INTEGER}) ({INTEGER}) ({INTEGER})"
REVIEWED_INPUT_SHA256 = "88423f9ae25f7afb9482e77a5c73cd02074f4f24ceadd1ed71aa437f5c662ff2"
EXPECTED_PERCENT_CONFLICTS = {
    (21, "REP IN CONGRESS 15TH DISTRICT", "REP Glenn GT Thompson", 435, 549, "79.24", "79.23"),
    (38, "REP IN GEN ASSEM 68TH DISTRICT", "DEM Quentin Gee", 55, 352, "15.62", "15.63"),
    (41, "REP IN GEN ASSEM 68TH DISTRICT", "DEM Quentin Gee", 269, 695, "38.70", "38.71"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def count(value):
    require(re.fullmatch(INTEGER, value) is not None, "Invalid native integer")
    return int(value.replace(",", ""))


def percentage(numerator, denominator):
    require(denominator > 0, "Missing or zero percentage denominator")
    return str((Decimal(numerator) * 100 / Decimal(denominator)).quantize(
        Decimal(".01"), rounding=ROUND_HALF_UP))


def vector(values):
    result = tuple(count(value) for value in values)
    require(result[0] == sum(result[1:]), "Native total disagrees with reported modes")
    return result


def parse_pages(pages):
    require(len(pages) == 43, "Incomplete 43-page numerical report")
    units, sources, reporting, percent_conflicts = [], [], [], []
    for physical_page, text in enumerate(pages, 1):
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
        require(lines[:2] == ["Summary Results Report UNOFFICIAL RESULTS", "General November 3 2026"],
                "Changed election or source status")
        require(lines[2] == ("November 3, 2026 Tioga County" if physical_page <= 2 else
                            "November 3 2026 Tioga County"), "Changed native election date or county")
        lines = lines[3:]
        require(lines[-1] == "Report generated with Electionware Copyright © 2007-2020",
                "Missing complete native footer")
        lines.pop()
        footer = re.fullmatch(r"(Election|Precinct) Summary - (08/08/2026) (1:1[78] AM) (\d+) of (\d+)",
                              lines.pop())
        require(footer is not None, "Changed or repaired native generation clock")
        expected = ("Election", "1:17 AM", physical_page, 2) if physical_page <= 2 else (
            "Precinct", "1:18 AM", physical_page - 2, 41)
        require((footer[1], footer[3], int(footer[4]), int(footer[5])) == expected,
                "Incorrect native page inventory or clock")
        sources.append(dict(physical_page=physical_page, native_page_scope=footer[1],
            native_page=int(footer[4]), native_total_pages=int(footer[5]),
            source_generation_clock_literal=footer[2] + " " + footer[3], declared_timezone="",
            source_clock_precedes_election=True, source_status_literal="UNOFFICIAL RESULTS"))
        name = "Tioga" if physical_page <= 2 else lines.pop(0)
        scope = "county" if physical_page <= 2 else "precinct"
        unit = dict(native_unit=name, scope=scope, contests=[])
        lines = [line for line in lines if not line.startswith("Statistics ")
                 and line not in {"TOTAL VOTE % Election Absentee Provision", "Day /Mail-in al", "Ballots"}]
        if physical_page == 1:
            for label in REPORTING:
                row = re.fullmatch(re.escape(label) + r" (\d+) of (\d+) (\d+) (\d+) (\d+)", lines.pop(0))
                require(row is not None, "Missing native reporting statistic")
                values = vector(row.group(1, 3, 4, 5))
                require(int(row[2]) == 41 and values[0] <= 41, "Changed reporting-unit denominator")
                reporting.append(dict(native_label=label, native_unit_denominator=41, values=values))
        if physical_page != 2:
            registrations = re.fullmatch(r"Registered Voters - Total (" + INTEGER + ")", lines.pop(0))
            ballots = re.fullmatch(r"Ballots Cast - Total " + VECTOR, lines.pop(0))
            blank = re.fullmatch(r"Ballots Cast - Blank " + VECTOR, lines.pop(0))
            turnout = re.fullmatch(r"Voter Turnout - Total (\d+\.\d{2})%", lines.pop(0))
            require(all(row is not None for row in (registrations, ballots, blank, turnout)),
                    "Missing native participation statistic")
            unit.update(registered_voters=count(registrations[1]), ballots=vector(ballots.groups()),
                        blank_ballots=vector(blank.groups()), native_printed_turnout=turnout[1])
            require(0 < unit["ballots"][0] <= unit["registered_voters"]
                    and all(a >= b for a, b in zip(unit["ballots"], unit["blank_ballots"])),
                    "Invalid participation or blank-ballot relationship")
            require(percentage(unit["ballots"][0], unit["registered_voters"]) == turnout[1],
                    "Native turnout percentage disagrees")
        if physical_page != 1:
            for title, expected_choices in CONTESTS.items():
                require(lines.pop(0) == title and lines.pop(0) == "Vote For 1",
                        "Unexpected contest or vote-for scope")
                choices = []
                while lines and not lines[0].startswith("Total Votes Cast "):
                    row = re.fullmatch(r"(.+?) " + rf"({INTEGER}) (\d+\.\d{{2}})% "
                                       + rf"({INTEGER}) ({INTEGER}) ({INTEGER})", lines.pop(0))
                    require(row is not None, "Unconsumed native candidate row")
                    label = row[1]
                    party = re.fullmatch(r"(DEM|REP|LIB) (.+)", label)
                    require(party is not None or label == "Write-In Totals", "Unknown literal party or write-in row")
                    choices.append(dict(native_party=party[1] if party else "",
                        native_choice=party[2] if party else label, native_printed_percent=row[3],
                        values=vector(row.group(2, 4, 5, 6))))
                total = re.fullmatch(r"Total Votes Cast " + rf"({INTEGER}) (100\.00)% "
                                    + rf"({INTEGER}) ({INTEGER}) ({INTEGER})", lines.pop(0))
                contest = re.fullmatch(r"Contest Totals " + VECTOR, lines.pop(0))
                require(total is not None and contest is not None, "Missing native contest totals")
                total_values, contest_values = vector(total.group(1, 3, 4, 5)), vector(contest.groups())
                require(len(choices) == len(expected_choices)
                        and {(row["native_party"], row["native_choice"]) for row in choices} == expected_choices,
                        "Missing, duplicate or changed native candidate")
                for mode in range(4):
                    require(sum(row["values"][mode] for row in choices) == total_values[mode]
                            <= contest_values[mode], "Candidate/contest accounting disagrees")
                for row in choices:
                    calculated = percentage(row["values"][0], total_values[0])
                    if calculated != row["native_printed_percent"]:
                        native_label = (row["native_party"] + " " + row["native_choice"]).strip()
                        conflict = (physical_page, title, native_label, row["values"][0],
                                    total_values[0], row["native_printed_percent"], calculated)
                        require(conflict in EXPECTED_PERCENT_CONFLICTS,
                                "Unreviewed native candidate percentage conflict")
                        percent_conflicts.append(conflict)
                if physical_page != 2:
                    require(contest_values == unit["ballots"], "Contest totals differ from native ballots")
                unit["contests"].append(dict(native_contest=title, choices=choices,
                    total_votes=total_values, contest_totals=contest_values))
        require(not lines, "Unconsumed numerical report lines")
        if physical_page == 2:
            units[0]["contests"] = unit["contests"]
            require(all(row["contest_totals"] == units[0]["ballots"] for row in unit["contests"]),
                    "County contest totals differ from county ballots")
        else:
            units.append(unit)
    require(len(units) == 42 and len({row["native_unit"] for row in units[1:]}) == 41,
            "Missing or duplicate native precinct")
    require(len(percent_conflicts) == len(EXPECTED_PERCENT_CONFLICTS)
            and set(percent_conflicts) == EXPECTED_PERCENT_CONFLICTS,
            "Changed independently reviewed percentage conflicts")
    county, precincts = units[0], units[1:]
    require(sum(row["registered_voters"] for row in precincts) == county["registered_voters"],
            "Precinct registrations do not reconcile to county")
    for field in ("ballots", "blank_ballots"):
        require(all(sum(row[field][mode] for row in precincts) == county[field][mode] for mode in range(4)),
                "Precinct participation vectors do not reconcile")
    for contest_index, contest in enumerate(county["contests"]):
        for field in ("total_votes", "contest_totals"):
            require(all(sum(row["contests"][contest_index][field][mode] for row in precincts) ==
                        contest[field][mode] for mode in range(4)), "Precinct contest vectors do not reconcile")
        for choice in contest["choices"]:
            for mode in range(4):
                require(sum(next(item["values"][mode] for item in row["contests"][contest_index]["choices"]
                                 if (item["native_party"], item["native_choice"]) ==
                                 (choice["native_party"], choice["native_choice"])) for row in precincts) ==
                        choice["values"][mode], "Precinct candidate vectors do not reconcile")
    return dict(units=units, pages=sources, reporting=reporting, percent_conflicts=percent_conflicts)


def review(facts):
    if REVIEWED_INPUT_SHA256:
        require(hashlib.sha256(json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                == REVIEWED_INPUT_SHA256, "Changed entire reviewed input")
    require(facts["year"] == 2026 and facts["county"] == "Tioga"
            and facts["maps_approved"] is False and facts["analysis_rates_approved"] is False,
            "Changed source identity or unauthorized promotion")
    require(len(facts["source_receipts"]) == 2, "Incomplete original-response receipts")
    for receipt in facts["source_receipts"]:
        require(receipt["url"] in SOURCES and receipt["status"] == 200
                and receipt["final_url"] == receipt["url"]
                and (receipt["bytes"], receipt["sha256"]) == SOURCES[receipt["url"]],
                "Changed complete original response")
    require(len({row["url"] for row in facts["source_receipts"]}) == 2, "Duplicate source receipt")
    require(facts["source_declaration"] == dict(parent_url=PARENT,
        label="Unofficial General Nov 3 2026 (opens in a new window)", url=PDF),
        "Changed actual declaring-page link")
    parsed = [parse_pages(facts["native_pages"][engine]) for engine in ("pymupdf", "pdfplumber")]
    require(parsed[0] == parsed[1], "Entire numerical extractions disagree")
    for one, two in zip(facts["native_pages"]["pymupdf"], facts["native_pages"]["pdfplumber"]):
        require(Counter(re.findall(r"[A-Za-z]+|\d+(?:[,.]\d+)*%?", one)) ==
                Counter(re.findall(r"[A-Za-z]+|\d+(?:[,.]\d+)*%?", two)),
                "Entire native page token inventories disagree")
    tables = {"county-participation.csv": [], "precinct-participation.csv": [],
              "candidate-results.csv": [], "literal-party-totals.csv": [],
              "contest-accounting.csv": [], "reporting-statistics.csv": [],
              "native-source-pages.csv": parsed[0]["pages"]}
    for unit in parsed[0]["units"]:
        common = dict(year=2026, state_code="PA", county="Tioga", native_unit=unit["native_unit"],
                      scope=unit["scope"])
        clock = "08/08/2026 1:17 AM" if unit["scope"] == "county" else "08/08/2026 1:18 AM"
        for mode, ballots, blank in zip(MODES, unit["ballots"], unit["blank_ballots"]):
            tables[unit["scope"] + "-participation.csv"].append(dict(**common, native_mode=mode,
                native_participation_measure_literal="Ballots Cast - Total", ballots_cast=ballots,
                blank_ballots_already_included=blank,
                registered_voters=unit["registered_voters"] if mode == "TOTAL" else "",
                native_printed_turnout=unit["native_printed_turnout"] if mode == "TOTAL" else "",
                source_status_literal="UNOFFICIAL RESULTS", source_generation_clock_literal=clock,
                declared_timezone="", source_clock_precedes_election=True, source_fips="",
                analysis_rates_approved=False, maps_approved=False))
        for contest in unit["contests"]:
            meta = dict(**common, native_contest=contest["native_contest"], native_vote_for=1)
            for mode_index, mode in enumerate(MODES):
                parties = Counter()
                for choice in contest["choices"]:
                    votes = choice["values"][mode_index]
                    parties[choice["native_party"]] += votes
                    tables["candidate-results.csv"].append(dict(**meta, native_mode=mode,
                        native_choice=choice["native_choice"], native_party=choice["native_party"], votes=votes,
                        native_printed_percent=choice["native_printed_percent"] if mode_index == 0 else "",
                        recomputed_half_up_percent=percentage(votes, contest["total_votes"][mode_index])
                        if mode_index == 0 else "",
                        native_percent_differs_from_half_up=(
                            choice["native_printed_percent"] != percentage(votes, contest["total_votes"][0]))
                        if mode_index == 0 else ""))
                tables["literal-party-totals.csv"].extend(
                    dict(**meta, native_mode=mode, native_party=party, votes=votes,
                         party_missing=party == "") for party, votes in parties.items())
                votes = contest["total_votes"][mode_index]
                total = contest["contest_totals"][mode_index]
                tables["contest-accounting.csv"].append(dict(**meta, native_mode=mode,
                    candidate_and_write_in_votes=votes, native_contest_total=total, native_ballots=unit["ballots"][mode_index],
                    unclassified_contest_total_minus_votes=total - votes, native_overvotes="", native_undervotes="",
                    native_blank_ballots_not_added_to_contests=unit["blank_ballots"][mode_index]))
    for row in parsed[0]["reporting"]:
        tables["reporting-statistics.csv"].extend(dict(native_label=row["native_label"],
            native_reporting_unit_denominator=row["native_unit_denominator"], native_mode=mode, native_value=value,
            counting_complete=False) for mode, value in zip(MODES, row["values"]))
    audit = dict(complete_numerical_pages=43, native_county_rows=1, native_precinct_rows=41,
        entire_numerical_extractions_agree=True, all_precinct_county_vectors_reconcile=True,
        all_native_participation_percentages_reconcile=True,
        all_native_candidate_percentages_match_half_up=False,
        candidate_percent_conflict_columns=["physical_page", "native_contest", "native_label", "votes",
                                           "total_votes", "native_printed_percent", "recomputed_half_up_percent"],
        reviewed_candidate_percent_conflicts=parsed[0]["percent_conflicts"], source_clock_precedes_election=True,
        source_status_literal="UNOFFICIAL RESULTS", generic_ballot_analysis_approvals=0,
        analysis_rate_approvals=0, map_approvals=0, counting_complete=False,
        qualification="The native November election title and August generation clocks conflict. "
        "Preserve the complete numerical query without silently correcting clocks or promoting it to analysis/maps. "
        "Reporting 41 of 41 coexists with 0 complete and 41 partial. Separate overvotes/undervotes are absent, not zero.",
        csv_rows={name: len(rows) for name, rows in tables.items()})
    return tables, audit


def build(destination):
    source = Path(__file__).parent
    tables, audit = review(json.loads((source / "native-facts.json").read_text()))
    require(not destination.exists(), "Output must not already exist")
    files = {name: (source / name).read_bytes() for name in
             ("review-tioga.py", "test_review_tioga.py", "native-facts.json", "METHODS.txt")}
    for name, rows in tables.items():
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        files[name] = buffer.getvalue().encode()
    files["audit.json"] = json_bytes(audit)
    files["checksums.json"] = json_bytes({name: dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                                        for name, data in sorted(files.items())})
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, data)
    files["complete-query.zip"] = archive.getvalue()
    destination.mkdir(parents=True)
    for name, data in files.items():
        (destination / name).write_bytes(data)
    print(json.dumps(dict(output=str(destination), files=len(files), audit=audit), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)

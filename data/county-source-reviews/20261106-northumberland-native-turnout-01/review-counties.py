import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


HERE = Path(__file__).resolve().parent
MODES = ("TOTAL", "Election Day", "Mail/Absentee", "Provisional")
TITLES = (
    "Governor & Lieutenant Governor",
    "Representative in Congress 9th District",
    "Representative in the General Assembly 107th District",
    "Representative in General Assembly 108th District",
    "City of Shamokin Home Rule Charter Referendum Shamokin City",
    "Commission Member Shamokin City",
)
STATIC = ("source-inputs.json", "source-provenance.json", "methods.json",
          "review-counties.py", "test_review_counties.py")
NUMBER = r"([\d,]+)"
VECTOR = r"\s+".join([NUMBER] * 4)


def one(pattern, text):
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError(f"Expected one field: {pattern!r}, found {len(matches)}")
    return matches[0]


def integer(value):
    return int(value.replace(",", ""))


def vector(match, offset=0):
    values = [integer(value) for value in match.groups()[offset:offset + 4]]
    if len(values) != 4 or values[0] != sum(values[1:]):
        raise ValueError("Native TOTAL/ED/Mail/Provisional vector does not reconcile")
    return values


def parse(pages):
    if len(pages) != 3 or not all(isinstance(page, str) for page in pages):
        raise ValueError("Three entire physical pages are required")
    text = [" ".join(page.split()) for page in pages]
    clocks = []
    for number, page in enumerate(text, 1):
        for literal in ("Summary Results Report UNOFFICIAL RESULTS", "2026 General Election",
                        "November 3, 2026", "Northumberland County"):
            one(re.escape(literal), page)
        footer = one(r"Election Summary - (\d+/\d+/\d+ \d+:\d+ [AP]M) Page (\d+) of (\d+)", page)
        if (int(footer[2]), int(footer[3])) != (number, 3):
            raise ValueError("Native printed and physical pages disagree")
        clocks.append(footer[1])
    if len(set(clocks)) != 1:
        raise ValueError("Native clocks differ across complete pages")
    first = text[0]
    registration = integer(one(r"Registered Voters - Total " + NUMBER, first)[1])
    ballots = vector(one(r"Ballots Cast - Total " + VECTOR, first))
    blanks = vector(one(r"Ballots Cast - Blank " + VECTOR, first))
    printed = one(r"Voter Turnout - Total (\d+\.\d{2})%", first)[1]
    calculated = str((Decimal(ballots[0]) * 100 / Decimal(registration)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))
    if printed != calculated or any(blank > count for blank, count in zip(blanks, ballots)):
        raise ValueError("Native county turnout or blank-ballot vector changed")
    county = dict(native_county="Northumberland County", election_date="2026-11-03",
        native_status="UNOFFICIAL RESULTS", ballots_cast=ballots[0],
        registered_voters=registration, blank_ballots=blanks[0], native_turnout_pct=printed,
        native_report_clock=clocks[0], native_timezone=None, native_fips=None,
        native_undervotes=None, native_overvotes=None, analysis_rate_approved=False,
        map_approved=False, source_page=1)
    modes = [dict(native_counting_group=mode, ballots_cast=count, blank_ballots=blank,
        registered_voters=registration if index == 0 else None,
        native_turnout_pct=printed if index == 0 else None,
        is_aggregate=index == 0, source_page=1)
        for index, (mode, count, blank) in enumerate(zip(MODES, ballots, blanks))]
    reporting = []
    for literal in ("Election Day Precincts Reporting", "Precincts Complete",
                    "Precincts Partially Reported", "Absentee/ Early Precincts Reporting"):
        row = one(re.escape(literal) + r" (\d+) of (\d+) (\d+) (\d+) (\d+)", first)
        reported, total, ed, mail, provisional = map(int, row.groups())
        if reported > total or reported != ed + mail + provisional:
            raise ValueError("Native reporting vector changed")
        reporting.append(dict(native_scope=literal, reported=reported, total=total,
            election_day=ed, mail_absentee=mail, provisional=provisional, source_page=1))
    candidates, contests, accounting, scopes = [], [], [], []
    for index, title in enumerate(TITLES):
        page_number = 2 if index < 3 else 3
        page = text[page_number - 1]
        one(re.escape(title), page)
        section = page.split(title, 1)[1]
        if index in (0, 1, 3, 4):
            section = section.split(TITLES[index + 1], 1)[0]
        else:
            section = section.split("Election Summary -", 1)[0]
        limit = int(one(r"Vote For (\d+)", section)[1])
        if limit != (7 if index == 5 else 1):
            raise ValueError("Native vote-for limit changed")
        selected = vector(one(r"Total Votes Cast " + VECTOR, section))
        total = vector(one(r"Contest Totals " + VECTOR, section))
        if any(votes > capacity for votes, capacity in zip(selected, total)):
            raise ValueError("Selected votes exceed native contest total")
        candidate_text = section.split(f"Vote For {limit}", 1)[1].split("Total Votes Cast ", 1)[0].strip()
        header = "Election Mail/Absent TOTAL Provisional Day ee"
        if not candidate_text.startswith(header):
            raise ValueError("Native mode header changed")
        candidate_text = candidate_text[len(header):].strip()
        pattern = r"\s*(?:(DEM|REP|LIB) )?(.+?) " + VECTOR
        position = 0
        native_candidates = []
        for match in re.finditer(pattern, candidate_text):
            if candidate_text[position:match.start()].strip():
                raise ValueError("Unparsed candidate text")
            party, name = match[1], match[2].strip()
            counts = vector(match, 2)
            if (name == "Write-In Totals" or index >= 4) and party is not None:
                raise ValueError("Invented write-in, city candidate or referendum party")
            native_candidates.append(dict(contest=title, candidate_or_option=name,
                native_party=party, total=counts[0], election_day=counts[1],
                mail_absentee=counts[2], provisional=counts[3], native_pct=None,
                is_write_in=name == "Write-In Totals",
                is_referendum_option=index == 4, vote_for=limit, source_page=page_number))
            position = match.end()
        if candidate_text[position:].strip() or not native_candidates:
            raise ValueError("Incomplete native candidate extraction")
        if len({row["candidate_or_option"] for row in native_candidates}) != len(native_candidates):
            raise ValueError("Repeated native candidate")
        expected_writeins = 0 if index == 4 else 1
        if sum(row["is_write_in"] for row in native_candidates) != expected_writeins:
            raise ValueError("Missing or repeated write-in summary")
        for mode, key, votes, native_total in zip(MODES,
                ("total", "election_day", "mail_absentee", "provisional"), selected, total):
            if sum(row[key] for row in native_candidates) != votes:
                raise ValueError("All candidate/option mode vectors must reconcile")
            accounting.append(dict(contest=title, native_counting_group=mode,
                native_total_votes_cast=votes, native_contest_totals=native_total,
                unclassified_contest_total_minus_votes=native_total - votes,
                native_undervotes=None, native_overvotes=None,
                residual_is_not_native_undervote=True, vote_for=limit, source_page=page_number))
        contests.append(dict(contest=title, vote_for=limit, native_total_votes_cast=selected[0],
            native_contest_totals=total[0], unclassified_residual=total[0] - selected[0],
            nonadditive_across_contests=True, source_page=page_number))
        scopes.append(dict(contest=title,
            native_subcounty_scope="Shamokin City" if index >= 4 else
                ("107th District" if index == 2 else "108th District" if index == 3 else None),
            vote_for=limit, native_registered_voters=None, native_ballots_cast=None,
            not_county_participation=True, source_page=page_number))
        candidates.extend(native_candidates)
    for mode in MODES:
        rows = [row for row in accounting if row["native_counting_group"] == mode]
        if rows[0]["native_contest_totals"] != ballots[MODES.index(mode)] or (
                rows[1]["native_contest_totals"] != rows[0]["native_contest_totals"] or
                rows[2]["native_contest_totals"] + rows[3]["native_contest_totals"] != rows[0]["native_contest_totals"]):
            raise ValueError("Countywide and two House-district native totals do not reconcile")
        if rows[5]["native_contest_totals"] != 7 * rows[4]["native_contest_totals"]:
            raise ValueError("City VoteFor7 native total is not the city VoteFor1 total times7")
    return dict(county=[county], modes=modes, candidates=candidates, contests=contests,
        accounting=accounting, reporting=reporting, scopes=scopes,
        pages=[dict(physical_page=n, printed_page=n, printed_pages=3,
            native_report_clock=clock, native_timezone=None,
            mixed_24_hour_and_pm_format_retained=True) for n, clock in enumerate(clocks, 1)])


def review(inputs):
    if inputs["numeric_pages_sha256"] != hashlib.sha256(
            json.dumps(inputs["extractions"], ensure_ascii=True, sort_keys=True).encode()).hexdigest():
        raise ValueError("Complete numerical evidence changed")
    parsed = [parse(inputs["extractions"][name]) for name in ("pymupdf", "pdfplumber")]
    if parsed[0] != parsed[1]:
        raise ValueError("Independent complete extractions disagree")
    return parsed[0]


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def build(output):
    if output.exists():
        raise ValueError("Refusing to overwrite an existing package")
    inputs = json.loads((HERE / "source-inputs.json").read_text())
    parsed = review(inputs)
    files = {name: (HERE / name).read_bytes() for name in STATIC}
    tables = {"county-participation.csv": "county", "ballot-modes.csv": "modes",
        "candidate-results.csv": "candidates", "contest-totals.csv": "contests",
        "contest-accounting.csv": "accounting", "reporting.csv": "reporting",
        "contest-scope.csv": "scopes", "source-pages.csv": "pages"}
    for name, key in tables.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(parsed[key][0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(parsed[key])
        files[name] = stream.getvalue().encode()
    audit = dict(row_counts={name: len(parsed[key]) for name, key in tables.items()},
        source_pdf_sha256=inputs["source_pdf_sha256"],
        both_complete_independent_extractions_match=True,
        all_native_candidate_mode_vectors_reconcile=True,
        native_total_is_first_column_not_last=True,
        multi_vote_native_contest_totals_are_not_ballots_or_unique_voters=True,
        all_contest_residuals_remain_unclassified_not_native_undervotes=True,
        no_mode_registration_or_rate_inferred=True, no_native_party_inferred=True,
        native_mixed_clock_literal_not_normalized=True, native_timezone_missing=True,
        native_fips_missing=True, analysis_rate_approvals=0, map_approvals=0)
    files["audit.json"] = encode(audit)
    files["checksums.json"] = encode({name: dict(bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest()) for name, body in sorted(files.items())})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, body, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    files["complete-query.zip"] = stream.getvalue()
    output.mkdir()
    for name, body in files.items():
        (output / name).write_bytes(body)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(build(parser.parse_args().output), indent=2))

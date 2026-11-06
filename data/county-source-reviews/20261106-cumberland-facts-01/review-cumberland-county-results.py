"""Reproduce complete Cumberland numerical facts without source presentation templates."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


INDEX = "https://www.cumberlandcountypa.gov/3135/Election-Results"
TERMS = "https://www.cumberlandcountypa.gov/site/copyright"
SOURCES = {
    "summary": "https://www.cumberlandcountypa.gov/DocumentCenter/View/52457/Unofficial-Summary-Report",
    "precinct": "https://www.cumberlandcountypa.gov/DocumentCenter/View/54411/Unofficial-Precinct-Results",
}
OFFICES = (
    "GOVERNOR AND LIEUTENANT GOVERNOR",
    "REPRESENTATIVE IN CONGRESS 10TH DISTRICT",
    "REPRESENTATIVE IN CONGRESS 13TH DISTRICT",
    "SENATOR IN THE GENERAL ASSEMBLY 34TH DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 87TH DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 88TH DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 103RD DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 193RD DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 199TH DISTRICT",
    "BALLOT QUESTION UPPER ALLEN TOWNSHIP",
)
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
MODES = ("Total", "Election Day", "Mail")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(isinstance(value, str) and re.fullmatch(NUMBER, value),
            f"Invalid native integer: {value!r}")
    return int(value.replace(",", ""))


def counts(literals):
    require(len(literals) == 3, "Incomplete native count vector")
    values = [integer(value) for value in literals]
    require(values[0] == sum(values[1:]), "Native mode counts do not equal total")
    return values


def parse_pages(texts, kind):
    expected_pages = 4 if kind == "summary" else 214
    require(len(texts) == expected_pages, "Incomplete native report pagination")
    pages = []
    for ordinal, text in enumerate(texts, 1):
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        require(lines[:3] == [
            "Summary Results Report UNOFFICIAL RESULTS",
            "2026 GENERAL ELECTION", "November 3, 2026 Cumberland County",
        ], "Missing native election identity or status")
        footer = re.fullmatch(
            rf"{'Summary' if kind == 'summary' else 'Precinct'} Report - Election Night - "
            r"(11/04/2026 \d{1,2}:\d{2}[AP]M) Page (\d+) of (\d+)", lines[-1])
        require(footer and int(footer[2]) == ordinal and int(footer[3]) == expected_pages,
                "Missing, duplicated or unordered native page")
        unit = "Cumberland" if kind == "summary" else lines[3]
        page = {"page_number": ordinal, "unit": unit, "source_update_literal": footer[1],
                "native_status_literal": "UNOFFICIAL RESULTS", "declared_timezone": None,
                "participation": None, "reporting": [], "contests": []}
        contest = None
        for line in lines[3 if kind == "summary" else 4:-1]:
            if line == "STATISTICS" or set(line.split()) <= {"TOTAL", "Election", "Day", "Mail"}:
                continue
            if line in OFFICES:
                contest = {"office_literal": line, "vote_for_literal": None, "rows": []}
                page["contests"].append(contest)
            elif line == "Vote For 1":
                require(contest is not None and contest["vote_for_literal"] is None,
                        "Unexpected or duplicated vote-for statement")
                contest["vote_for_literal"] = line
            elif line.startswith("Registered Voters - Total"):
                require(page["participation"] is None, "Duplicate native participation")
                page["participation"] = {"registered_voters_literal": line.split()[-1]}
            elif line.startswith("Ballots Cast - Total"):
                require(page["participation"] is not None
                        and "ballot_count_literals" not in page["participation"],
                        "Unexpected or duplicated ballot statement")
                page["participation"]["ballot_count_literals"] = line.split()[-3:]
            elif "Voter Turnout - Total" in line:
                match = re.fullmatch(r"(?:Voter Turnout - Total (\d+\.\d{2}%)|"
                                     r"(\d+\.\d{2}%)\s*Voter Turnout - Total)", line)
                require(match and page["participation"] is not None
                        and "printed_turnout_literal" not in page["participation"],
                        "Unexpected or incomplete native turnout statement")
                page["participation"]["printed_turnout_literal"] = match[1] or match[2]
            elif "Precincts Reporting" in line:
                match = re.fullmatch(
                    r"(Election Day|Absentee/ Early) Precincts Reporting (\d+) of (\d+) (\d+) (\d+)", line)
                require(match is not None and kind == "summary", "Unknown reporting statement")
                page["reporting"].append({
                    "mode_literal": match[1], "reported_literal": match[2],
                    "total_literal": match[3], "election_day_literal": match[4],
                    "mail_literal": match[5],
                })
            else:
                match = re.fullmatch(rf"(.+?) ({NUMBER}) ({NUMBER}) ({NUMBER})", line)
                require(match is not None and contest is not None,
                        f"Unrecognized native result line: {line}")
                label = match[1]
                if label == "Write-In Totals":
                    name, party, row_kind = label, "", "write_in_total"
                elif label in ("YES", "NO"):
                    name, party, row_kind = label, "", "ballot_option"
                else:
                    party, name = label.split(" ", 1)
                    require(party in ("DEM", "REP", "LIB"), "Unexpected native party literal")
                    row_kind = "candidate"
                contest["rows"].append({
                    "name": name, "party_literal": party, "row_kind": row_kind,
                    "count_literals": list(match.groups()[1:]),
                })
        pages.append(page)
    return {"kind": kind, "source_url": SOURCES[kind], "pages": pages}


def validate(facts):
    require(facts["schema"] == "cumberland-2026-complete-numerical-facts-v1",
            "Unknown numerical-facts schema")
    reports = facts["reports"]
    require([report["kind"] for report in reports] == ["summary", "precinct"],
            "Incomplete source report inventory")
    participation, vectors, reporting, units, printed_exceptions = {}, {}, [], set(), []
    for report in reports:
        kind = report["kind"]
        require(report["source_url"] == SOURCES[kind]
                and len(report["pages"]) == (4 if kind == "summary" else 214),
                "Incomplete native source pages")
        updates, report_units = set(), set()
        for ordinal, page in enumerate(report["pages"], 1):
            require(page["page_number"] == ordinal and page["declared_timezone"] is None
                    and page["native_status_literal"] == "UNOFFICIAL RESULTS"
                    and re.fullmatch(r"11/04/2026 \d{1,2}:\d{2}[AP]M", page["source_update_literal"]),
                    "Changed native pagination, status or update")
            unit = page["unit"]
            require(unit and (kind != "summary" or unit == "Cumberland"),
                    "Missing native reporting-unit identity")
            updates.add(page["source_update_literal"])
            report_units.add(unit)
            if kind == "precinct":
                units.add(unit)
            key = (kind, unit)
            if page["participation"] is not None:
                native = page["participation"]
                ballots = counts(native["ballot_count_literals"])
                denominator = integer(native["registered_voters_literal"])
                printed = native["printed_turnout_literal"]
                require(key not in participation and denominator > 0 and ballots[0] <= denominator
                        and re.fullmatch(r"\d+\.\d{2}%", printed),
                        "Duplicate or inconsistent native participation")
                if abs(100 * ballots[0] / denominator - float(printed[:-1])) > .005000001:
                    require(key == ("precinct", "UPPER ALLEN 6")
                            and native["ballot_count_literals"] == ["1,155", "921", "234"]
                            and native["registered_voters_literal"] == "1,767" and printed == "65.36%",
                            "Unexpected native printed-turnout discrepancy")
                    printed_exceptions.append(unit)
                participation[key] = native
            for statement in page["reporting"]:
                require(kind == "summary"
                        and integer(statement["reported_literal"]) <= integer(statement["total_literal"])
                        and integer(statement["reported_literal"])
                        == integer(statement["election_day_literal"]) + integer(statement["mail_literal"]),
                        "Inconsistent native reporting counters")
                reporting.append(statement)
            for contest in page["contests"]:
                office = contest["office_literal"]
                identity = (kind, unit, office)
                require(identity not in vectors and office in OFFICES
                        and contest["vote_for_literal"] == "Vote For 1",
                        "Duplicate or unexpected native contest")
                rows = contest["rows"]
                expected = ([("YES", "", "ballot_option"), ("NO", "", "ballot_option")]
                            if office == OFFICES[-1] else None)
                identities = [(row["name"], row["party_literal"], row["row_kind"]) for row in rows]
                require(len(identities) == len(set(identities)) and rows,
                        "Duplicate or absent native candidate/option")
                if expected is not None:
                    require(identities == expected, "Incomplete ballot options")
                else:
                    require(len(rows) == (4 if office == OFFICES[0] else 3)
                            and [row["party_literal"] for row in rows[:-1]]
                            == (["DEM", "REP", "LIB"] if office == OFFICES[0] else ["DEM", "REP"])
                            and rows[-1]["row_kind"] == "write_in_total"
                            and rows[-1]["name"] == "Write-In Totals"
                            and rows[-1]["party_literal"] == ""
                            and all(row["row_kind"] == "candidate"
                                    and row["party_literal"] in ("DEM", "REP", "LIB")
                                    for row in rows[:-1]), "Incomplete candidate/write-in inventory")
                for row in rows:
                    counts(row["count_literals"])
                vectors[identity] = contest
        require(len(updates) == 1, "Mixed native timestamps within one report")
        require(all((kind, unit) in participation for unit in report_units),
                "Missing native unit participation")
    require(len(units) == 118 and len(participation) == 119
            and len(vectors) == 461 and len(reporting) == 2,
            "Incomplete native unit/contest/reporting inventory")
    require(printed_exceptions == ["UPPER ALLEN 6"],
            "Changed source-specific printed-turnout discrepancy")
    require([row["mode_literal"] for row in reporting] == ["Election Day", "Absentee/ Early"],
            "Unexpected native reporting-mode inventory")
    require({identity[2] for identity in vectors if identity[0] == "summary"} == set(OFFICES),
            "Incomplete county contest inventory")
    county = participation["summary", "Cumberland"]
    for index in range(3):
        require(sum(counts(participation["precinct", unit]["ballot_count_literals"])[index]
                    for unit in units) == counts(county["ballot_count_literals"])[index],
                "Native unit ballots do not reconcile to county")
    require(sum(integer(participation["precinct", unit]["registered_voters_literal"]) for unit in units)
            == integer(county["registered_voters_literal"]),
            "Native unit registrations do not reconcile to county")
    for office in OFFICES:
        county_rows = vectors["summary", "Cumberland", office]["rows"]
        expected = {(row["name"], row["party_literal"], row["row_kind"]): counts(row["count_literals"])
                    for row in county_rows}
        actual = {identity: [0, 0, 0] for identity in expected}
        for (kind, unit, native_office), contest in vectors.items():
            if kind != "precinct" or native_office != office:
                continue
            require([(row["name"], row["party_literal"], row["row_kind"]) for row in contest["rows"]]
                    == list(expected), "Native unit candidate inventory differs from county")
            for row in contest["rows"]:
                identity = (row["name"], row["party_literal"], row["row_kind"])
                actual[identity] = [a + b for a, b in zip(actual[identity], counts(row["count_literals"]))]
        require(actual == expected, "Native unit candidate/option vectors do not reconcile to county")
    for key, native in participation.items():
        require((*key, OFFICES[0]) in vectors, "Missing countywide governor contest")
        ballots = counts(native["ballot_count_literals"])
        selections = [sum(counts(row["count_literals"])[i] for row in vectors[(*key, OFFICES[0])]["rows"])
                      for i in range(3)]
        require(all(votes <= total for votes, total in zip(selections, ballots)),
                "Governor selections exceed native ballots")
    return facts


def build(facts, output):
    validate(facts)
    output.mkdir(parents=True, exist_ok=False)
    common = {"year": 2026, "state_code": "PA", "county": "Cumberland", "county_fips": "42041"}
    qualifications = [
        "All 118 native reporting units sum to the county ballots, registrations and separate Election Day/mail counts; candidate selections are not ballots.",
        "Summary and precinct reports retain distinct native November 4 run times; no timezone is declared and equal totals do not establish simultaneous snapshots.",
        "Native reporting is 118 of 118 separately for Election Day and Absentee/ Early; this does not establish final counting or certification.",
        "Under/overvotes and a separate provisional count are absent, not zero. Governor ballots minus recorded selections remain unclassified, not labeled blanks or allocated to parties.",
        "Congressional district rows include a split reporting unit; unit-level district selections must not be assigned the whole unit electorate.",
        "UPPER ALLEN 6 prints 65.36% for 1,155 / 1,767; the calculated 65.36502546689304% rounds to 65.37%. The source fraction is retained, not silently corrected.",
        "Native UNOFFICIAL RESULTS is retained. No county/precinct mapping, statewide completeness or demographic turnout is approved.",
    ]
    tables = {name: [] for name in (
        "county-participation.csv", "native-unit-participation.csv", "county-candidate-option-results.csv",
        "native-unit-candidate-option-results.csv", "county-literal-party-totals.csv",
        "native-reporting-statements.csv", "native-source-pages.csv", "governor-unclassified-ballot-residuals.csv",
    )}
    for report in facts["reports"]:
        county = report["kind"] == "summary"
        for page in report["pages"]:
            base = {**common, "native_unit": page["unit"], "source_report": report["kind"],
                    "source_page": page["page_number"], "source_url": report["source_url"],
                    "source_update_literal": page["source_update_literal"], "declared_timezone": "",
                    "native_status_literal": page["native_status_literal"]}
            tables["native-source-pages.csv"].append(base)
            native = page["participation"]
            if native is not None:
                values = counts(native["ballot_count_literals"])
                row = {**base, "ballots_cast": values[0], "election_day_ballots": values[1],
                       "mail_ballots": values[2], "registered_voters": integer(native["registered_voters_literal"]),
                       "registered_voters_literal": native["registered_voters_literal"],
                       "native_printed_turnout": native["printed_turnout_literal"],
                       "ballot_count_literals_json": json.dumps(native["ballot_count_literals"]),
                       "county_fips_basis": "Reviewed 2026 Census identity, not a native PDF field",
                       "counting_qualifications_json": json.dumps(qualifications)}
                tables["county-participation.csv" if county else "native-unit-participation.csv"].append(row)
            for statement in page["reporting"]:
                tables["native-reporting-statements.csv"].append({**base, **statement})
            for contest in page["contests"]:
                scope = {**base, "office_literal": contest["office_literal"],
                         "vote_for_literal": contest["vote_for_literal"]}
                for native_row in contest["rows"]:
                    row = {**scope, "candidate_or_option": native_row["name"],
                           "party_literal": native_row["party_literal"], "row_kind": native_row["row_kind"]}
                    for mode, value, literal in zip(MODES, counts(native_row["count_literals"]),
                                                    native_row["count_literals"]):
                        row.update({mode: value, mode + "_count_literal": literal})
                    tables["county-candidate-option-results.csv" if county
                           else "native-unit-candidate-option-results.csv"].append(row)
    party = Counter()
    for row in tables["county-candidate-option-results.csv"]:
        if row["row_kind"] == "candidate":
            party[row["office_literal"], row["party_literal"]] += row["Total"]
    tables["county-literal-party-totals.csv"] = [
        {**common, "office_literal": office, "party_literal": label, "candidate_votes": votes}
        for (office, label), votes in party.items()
    ]
    for county in (True, False):
        participation = tables["county-participation.csv" if county else "native-unit-participation.csv"]
        results = tables["county-candidate-option-results.csv" if county else "native-unit-candidate-option-results.csv"]
        for native in participation:
            rows = [row for row in results if row["native_unit"] == native["native_unit"]
                    and row["office_literal"] == OFFICES[0]]
            row = {**common, "native_unit": native["native_unit"], "source_report": native["source_report"],
                   "office_literal": OFFICES[0], "source_update_literal": native["source_update_literal"],
                   "residual_classification": "unclassified; native under/overvote accounting absent"}
            for mode, field in zip(MODES, ("ballots_cast", "election_day_ballots", "mail_ballots")):
                row[mode + "_ballots_minus_recorded_selections"] = native[field] - sum(r[mode] for r in rows)
            tables["governor-unclassified-ballot-residuals.csv"].append(row)
    for filename, rows in tables.items():
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / filename).write_text(buffer.getvalue())
    (output / "source-records.json").write_text(json.dumps(facts, indent=2) + "\n")
    audit = {"scope": "Cumberland County only; complete numerical facts from both declared 2026 general reports",
             "maps_approved": False, "demographic_turnout_approved": False,
             "county_participation": tables["county-participation.csv"][0],
             "table_rows": {name: len(rows) for name, rows in tables.items()},
             "qualifications": qualifications,
             "source_representation": "Numerical facts only. Original HTML/PDF bytes and extracted presentation text remain private; no template redistribution license is claimed."}
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "review-cumberland-county-results.py").write_bytes(Path(__file__).read_bytes())
    files = sorted(output.iterdir())
    checksums = {path.name: {"bytes": path.stat().st_size,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in files}
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    target = output / "complete-cumberland-2026-numerical-facts-01.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path == target:
                continue
            info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--private-source", type=Path)
    source.add_argument("--facts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.private_source:
        import fitz
        from pypdf import PdfReader
        receipts = json.loads((args.private_source / "receipts.json").read_text())
        require({row["file"] for row in receipts}
                == {"official-index.html", "copyright.html", "summary.pdf", "precinct.pdf"}
                and len(receipts) == 4, "Incomplete source receipts")
        for receipt in receipts:
            raw = (args.private_source / receipt["file"]).read_bytes()
            require(receipt["status"] == 200 and len(raw) == receipt["bytes"]
                    and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                    "Source receipt mismatch")
        reports = []
        for kind in SOURCES:
            source_path = args.private_source / (kind + ".pdf")
            with fitz.open(source_path) as document:
                first = parse_pages([page.get_text(sort=True) for page in document], kind)
            second = parse_pages([page.extract_text(extraction_mode="layout")
                                  for page in PdfReader(source_path).pages], kind)
            require(first == second, "Independent PDF engines disagree on native facts")
            reports.append(first)
        facts = {"schema": "cumberland-2026-complete-numerical-facts-v1",
                 "reports": reports, "source_receipts": receipts,
                 "source_context_url": INDEX, "source_terms_url": TERMS,
                 "independent_extraction": "PyMuPDF sorted text and pypdf layout agree on every page fact"}
    else:
        facts = json.loads(args.facts.read_text())
    print(json.dumps(build(facts, args.output), indent=2))


if __name__ == "__main__":
    main()

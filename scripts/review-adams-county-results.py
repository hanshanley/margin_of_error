"""Reproduce complete Adams numerical facts without source presentation templates."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


OFFICES = (
    "Governor/Lieutenant Governor", "Representative in Congress",
    "Representative in the General Assembly 91st District",
    "Representative in the General Assembly 193rd District",
)
MODES = ("Total", "Election Day", "Mail", "Provisional")
ACCOUNTING = ("Total Votes Cast", "Overvotes", "Undervotes", "Contest Totals")
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
SOURCES = {
    "summary": "https://www.adamscountypa.gov/getmedia/369dc41b-5483-43fc-82c1-8bbb7b187ad0/ElectionSummary2026General.pdf",
    "precinct": "https://www.adamscountypa.gov/getmedia/0999a217-97b2-477c-ad02-1383ab2d17a5/PrecinctSummary2026General.pdf",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(isinstance(value, str) and re.fullmatch(NUMBER, value),
            f"Invalid native integer: {value!r}")
    return int(value.replace(",", ""))


def counts(literals):
    require(len(literals) == 4, "Incomplete native count vector")
    values = [integer(value) for value in literals]
    require(values[0] == sum(values[1:]), "Native mode counts do not equal total")
    return values


def parse_pages(texts, kind):
    expected_pages = 3 if kind == "summary" else 106
    require(len(texts) == expected_pages, "Incomplete native report pagination")
    pages = []
    for ordinal, text in enumerate(texts, 1):
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        require(lines[:3] == ["Summary Results Report UNOFFICIAL RESULTS", "General Election",
                             "November 3, 2026 ADAMS COUNTY, PENNSYLVANIA"],
                "Missing native election identity or status")
        footer = re.fullmatch(
            rf"{'Election' if kind == 'summary' else 'Precinct'} Summary - "
            r"(11/03/2026 10:23PM) Page (\d+) of (\d+)", lines[-1])
        require(footer and int(footer[2]) == ordinal and int(footer[3]) == expected_pages,
                "Missing, duplicated or unordered native page")
        page = {"page_number": ordinal, "unit": "Adams" if kind == "summary" else lines[3],
                "source_update_literal": footer[1], "declared_timezone": None,
                "native_status_literal": "UNOFFICIAL RESULTS",
                "participation": None, "reporting": [], "contests": []}
        contest = None
        for line in lines[3 if kind == "summary" else 4:-1]:
            if line == "STATISTICS" or set(line.split()) <= {
                    "TOTAL", "Election", "Day", "Mail", "Provisional", "Votes"}:
                continue
            if line in OFFICES:
                contest = {"office_literal": line, "vote_for_literal": None,
                           "rows": [], "accounting": {}}
                page["contests"].append(contest)
            elif line == "Vote For 1":
                require(contest is not None and contest["vote_for_literal"] is None,
                        "Unexpected or duplicated vote-for statement")
                contest["vote_for_literal"] = line
            elif line.startswith("Registered Voters - Total"):
                require(page["participation"] is None, "Duplicate native participation")
                page["participation"] = {"registered_voters_literal": line.split()[-1]}
            elif line.startswith(("Ballots Cast - Total", "Ballots Cast - Blank")):
                native = page["participation"]
                field = "ballot_count_literals" if line.startswith("Ballots Cast - Total") else "blank_count_literals"
                require(native is not None and field not in native,
                        "Unexpected or duplicated native ballot statement")
                native[field] = line.split()[-4:]
            elif "Voter Turnout - Total" in line:
                match = re.fullmatch(r"(?:Voter Turnout - Total (\d+\.\d{2}%)|"
                                     r"(\d+\.\d{2}%)\s*Voter Turnout - Total)", line)
                require(match and page["participation"] is not None
                        and "printed_turnout_literal" not in page["participation"],
                        "Unexpected or incomplete native turnout statement")
                page["participation"]["printed_turnout_literal"] = match[1] or match[2]
            elif line.startswith(("Election Day Precincts", "Absentee/ Early Precincts",
                                  "Precincts Complete", "Precincts Partially Reported")):
                match = re.fullmatch(
                    r"(Election Day Precincts Reporting|Absentee/ Early Precincts Reporting|"
                    r"Precincts Complete|Precincts Partially Reported) "
                    r"(\d+) of (\d+) (\d+) (\d+) (\d+)", line)
                require(match and kind == "summary", "Unknown native reporting statement")
                page["reporting"].append({
                    "label_literal": match[1], "reported_literal": match[2],
                    "total_literal": match[3], "mode_count_literals": list(match.groups()[3:]),
                })
            else:
                match = re.fullmatch(rf"(.+?) ({NUMBER}) ({NUMBER}) ({NUMBER}) ({NUMBER})", line)
                require(match and contest is not None, f"Unrecognized native result line: {line}")
                label, literals = match[1], list(match.groups()[1:])
                if label in ACCOUNTING:
                    require(label not in contest["accounting"], "Duplicate native accounting row")
                    contest["accounting"][label] = literals
                else:
                    if label == "Write-In Totals":
                        name, party, row_kind = label, "", "write_in_total"
                    else:
                        party, name = label.split(" ", 1)
                        require(party in ("DEM", "REP", "LIB"), "Unexpected native party literal")
                        row_kind = "candidate"
                    contest["rows"].append({"name": name, "party_literal": party,
                                            "row_kind": row_kind, "count_literals": literals})
        pages.append(page)
    return {"kind": kind, "source_url": SOURCES[kind], "pages": pages}


def validate(facts):
    require(facts["schema"] == "adams-2026-complete-numerical-facts-v1", "Unknown numerical-facts schema")
    require([report["kind"] for report in facts["reports"]] == ["summary", "precinct"],
            "Incomplete source report inventory")
    participation, contests, statements, units = {}, {}, [], set()
    for report in facts["reports"]:
        kind = report["kind"]
        require(report["source_url"] == SOURCES[kind]
                and len(report["pages"]) == (3 if kind == "summary" else 106),
                "Incomplete native source pages")
        for ordinal, page in enumerate(report["pages"], 1):
            unit = page["unit"]
            require(page["page_number"] == ordinal and page["declared_timezone"] is None
                    and page["source_update_literal"] == "11/03/2026 10:23PM"
                    and page["native_status_literal"] == "UNOFFICIAL RESULTS"
                    and unit and (kind != "summary" or unit == "Adams"),
                    "Changed native pagination, identity, status or update")
            if kind == "precinct":
                units.add(unit)
            key = kind, unit
            native = page["participation"]
            if native is not None:
                require(set(native) == {"registered_voters_literal", "ballot_count_literals",
                                        "blank_count_literals", "printed_turnout_literal"},
                        "Incomplete native participation")
                ballots, blanks = counts(native["ballot_count_literals"]), counts(native["blank_count_literals"])
                denominator = integer(native["registered_voters_literal"])
                printed = native["printed_turnout_literal"]
                require(key not in participation and denominator > 0 and ballots[0] <= denominator
                        and all(blank <= ballot for blank, ballot in zip(blanks, ballots))
                        and re.fullmatch(r"\d+\.\d{2}%", printed)
                        and abs(100 * ballots[0] / denominator - float(printed[:-1])) <= .005000001,
                        "Duplicate or inconsistent native participation")
                participation[key] = native
            require(not page["reporting"] or kind == "summary", "Unit reporting counter changes scope")
            statements.extend(page["reporting"])
            for contest in page["contests"]:
                identity = kind, unit, contest["office_literal"]
                require(identity not in contests and identity[2] in OFFICES
                        and contest["vote_for_literal"] == "Vote For 1"
                        and set(contest["accounting"]) == set(ACCOUNTING),
                        "Duplicate or incomplete native contest")
                rows = contest["rows"]
                parties = ["DEM", "REP", "LIB"] if identity[2] == OFFICES[0] else ["DEM", "REP"]
                require(len(rows) == len(parties) + 1
                        and [row["party_literal"] for row in rows[:-1]] == parties
                        and all(row["row_kind"] == "candidate" for row in rows[:-1])
                        and rows[-1]["name"] == "Write-In Totals"
                        and rows[-1]["party_literal"] == ""
                        and rows[-1]["row_kind"] == "write_in_total"
                        and len({row["name"] for row in rows}) == len(rows),
                        "Incomplete native candidate/write-in inventory")
                votes = [sum(counts(row["count_literals"])[i] for row in rows) for i in range(4)]
                accounting = {label: counts(values) for label, values in contest["accounting"].items()}
                require(votes == accounting["Total Votes Cast"]
                        and [sum(values) for values in zip(accounting["Total Votes Cast"],
                            accounting["Overvotes"], accounting["Undervotes"])] == accounting["Contest Totals"],
                        "Native candidate or under/overvote accounting does not reconcile")
                contests[identity] = contest
    require(len(units) == 53 and len(participation) == 54 and len(contests) == 163,
            "Incomplete native unit/contest inventory")
    require([(row["label_literal"], row["reported_literal"], row["total_literal"],
              row["mode_count_literals"]) for row in statements] == [
        ("Election Day Precincts Reporting", "53", "53", ["53", "0", "0"]),
        ("Precincts Complete", "0", "53", ["0", "0", "0"]),
        ("Precincts Partially Reported", "53", "53", ["53", "0", "0"]),
        ("Absentee/ Early Precincts Reporting", "53", "53", ["0", "53", "0"]),
    ], "Changed native reporting/completion qualifiers")
    county = participation["summary", "Adams"]
    require(integer(county["registered_voters_literal"]) == 77163
            and counts(county["ballot_count_literals"]) == [42660, 32340, 10320, 0]
            and counts(county["blank_count_literals"]) == [5, 1, 4, 0],
            "Changed frozen county participation")
    require(sum(integer(participation["precinct", unit]["registered_voters_literal"]) for unit in units)
            == integer(county["registered_voters_literal"]),
            "Native unit registrations do not reconcile to county")
    for field in ("ballot_count_literals", "blank_count_literals"):
        require([sum(counts(participation["precinct", unit][field])[i] for unit in units)
                 for i in range(4)] == counts(county[field]),
                "Native unit ballot or blank vectors do not reconcile to county")
    for key, native in participation.items():
        offices = {identity[2] for identity in contests if identity[:2] == key}
        require(offices == set(OFFICES) if key[0] == "summary" else
                set(OFFICES[:2]) <= offices and len(offices) == 3,
                "Incomplete unit office scope")
        for office in offices:
            if key[0] == "precinct" or office in OFFICES[:2]:
                require(counts(contests[(*key, office)]["accounting"]["Contest Totals"])
                        == counts(native["ballot_count_literals"]),
                        "Native contest ballots differ from participation")
    require([sum(counts(contests["summary", "Adams", office]["accounting"]["Contest Totals"])[i]
                 for office in OFFICES[2:]) for i in range(4)] == counts(county["ballot_count_literals"]),
            "County legislative districts do not partition native ballots")
    for office in OFFICES:
        expected = contests["summary", "Adams", office]
        district_units = [contest for (kind, unit, native_office), contest in contests.items()
                          if kind == "precinct" and native_office == office]
        identities = [(row["name"], row["party_literal"], row["row_kind"]) for row in expected["rows"]]
        require(all([(row["name"], row["party_literal"], row["row_kind"]) for row in contest["rows"]]
                    == identities for contest in district_units), "Unit candidate identities differ from county")
        for row_index, row in enumerate(expected["rows"]):
            require([sum(counts(contest["rows"][row_index]["count_literals"])[i]
                         for contest in district_units) for i in range(4)] == counts(row["count_literals"]),
                    "Native unit candidate vectors do not reconcile to county")
        for label in ACCOUNTING:
            require([sum(counts(contest["accounting"][label])[i] for contest in district_units)
                     for i in range(4)] == counts(expected["accounting"][label]),
                    "Native unit contest accounting does not reconcile to county")
    return facts


def build(facts, output):
    validate(facts)
    output.mkdir(parents=True, exist_ok=False)
    common = {"year": 2026, "state_code": "PA", "county": "Adams", "county_fips": "42001"}
    qualifications = [
        "All 53 native units reconcile to county ballots, registrations, blanks, separate Election Day/mail/provisional counts and every candidate/contest vector.",
        "Native reporting is 53 of 53, but separately 0 of 53 complete and all 53 partially reported; UNOFFICIAL RESULTS is not certification.",
        "Mail ballots counted are 10,320, not the index's separately scoped 10,348 mail/absentee receipts.",
        "Blank ballots and under/overvotes are native explicit rows, not inferred candidate residuals. Native provisional zeros remain explicit.",
        "The 91st and 193rd legislative districts partition county ballots, not separate whole-county electorates.",
        "The native November 3 run time has no declared timezone. Native registered-voter fractions are not VEP/CVAP or demographic turnout.",
        "No county/precinct mapping or statewide completeness is approved. Source HTML/PDF templates and extracted presentation text remain private.",
    ]
    tables = {name: [] for name in (
        "county-participation.csv", "native-unit-participation.csv", "county-candidate-results.csv",
        "native-unit-candidate-results.csv", "county-literal-party-totals.csv",
        "native-contest-accounting.csv", "native-reporting-statements.csv", "native-source-pages.csv",
    )}
    for report in facts["reports"]:
        county = report["kind"] == "summary"
        for page in report["pages"]:
            base = {**common, "native_unit": page["unit"], "source_report": report["kind"],
                    "source_page": page["page_number"], "source_url": report["source_url"],
                    "source_update_literal": page["source_update_literal"], "declared_timezone": "",
                    "native_status_literal": page["native_status_literal"]}
            tables["native-source-pages.csv"].append(base)
            if page["participation"] is not None:
                native = page["participation"]
                ballots, blanks = counts(native["ballot_count_literals"]), counts(native["blank_count_literals"])
                row = {**base, "ballots_cast": ballots[0], "election_day_ballots": ballots[1],
                       "mail_ballots": ballots[2], "provisional_ballots": ballots[3],
                       "registered_voters": integer(native["registered_voters_literal"]),
                       "native_printed_turnout": native["printed_turnout_literal"],
                       "registered_turnout_percent": 100 * ballots[0] / integer(native["registered_voters_literal"]),
                       "native_count_literals_json": json.dumps(native),
                       "blank_ballots": blanks[0], "election_day_blank_ballots": blanks[1],
                       "mail_blank_ballots": blanks[2], "provisional_blank_ballots": blanks[3],
                       "county_fips_basis": "Reviewed Census identity, not a native PDF field",
                       "counting_qualifications_json": json.dumps(qualifications)}
                tables["county-participation.csv" if county else "native-unit-participation.csv"].append(row)
            for statement in page["reporting"]:
                tables["native-reporting-statements.csv"].append({**base, **statement})
            for contest in page["contests"]:
                scope = {**base, "office_literal": contest["office_literal"],
                         "vote_for_literal": contest["vote_for_literal"]}
                for native in contest["rows"]:
                    row = {**scope, "candidate": native["name"], "party_literal": native["party_literal"],
                           "row_kind": native["row_kind"], "native_count_literals_json": json.dumps(native["count_literals"])}
                    row.update(zip(MODES, counts(native["count_literals"])))
                    tables["county-candidate-results.csv" if county else "native-unit-candidate-results.csv"].append(row)
                for label in ACCOUNTING:
                    literals = contest["accounting"][label]
                    row = {**scope, "accounting_label_literal": label,
                           "native_count_literals_json": json.dumps(literals)}
                    row.update(zip(MODES, counts(literals)))
                    tables["native-contest-accounting.csv"].append(row)
    parties = Counter()
    for row in tables["county-candidate-results.csv"]:
        if row["row_kind"] == "candidate":
            for mode in MODES:
                parties[row["office_literal"], row["party_literal"], mode] += row[mode]
    tables["county-literal-party-totals.csv"] = [
        {**common, "office_literal": office, "party_literal": party, "mode_literal": mode,
         "candidate_votes": value} for (office, party, mode), value in parties.items()
    ]
    for filename, rows in tables.items():
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / filename).write_text(buffer.getvalue())
    (output / "source-records.json").write_text(json.dumps(facts, indent=2) + "\n")
    audit = {"scope": "Adams County only; complete numerical facts from both declared 2026 general reports",
             "maps_approved": False, "demographic_turnout_approved": False,
             "county_participation": tables["county-participation.csv"][0],
             "table_rows": {name: len(rows) for name, rows in tables.items()},
             "qualifications": qualifications}
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "review-adams-county-results.py").write_bytes(Path(__file__).read_bytes())
    files = sorted(output.iterdir())
    (output / "checksums.json").write_text(json.dumps({
        path.name: {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in files}, indent=2) + "\n")
    target = output / "complete-adams-2026-numerical-facts-01.zip"
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
        require(set(receipts) == {"official-index.html", "summary.pdf", "precinct.pdf", "terms.pdf", "privacy.pdf"},
                "Incomplete primary-source receipts")
        for filename, receipt in receipts.items():
            raw = (args.private_source / filename).read_bytes()
            require(receipt["status"] == 200 and len(raw) == receipt["bytes"]
                    and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                    "Source receipt mismatch")
        reports = []
        for kind in SOURCES:
            require(receipts[kind + ".pdf"]["url"] == SOURCES[kind], "Unexpected native report URL")
            source_path = args.private_source / (kind + ".pdf")
            with fitz.open(source_path) as document:
                first = parse_pages([page.get_text(sort=True) for page in document], kind)
            second = parse_pages([page.extract_text(extraction_mode="layout")
                                  for page in PdfReader(source_path).pages], kind)
            require(first == second, "Independent PDF engines disagree on native facts")
            reports.append(first)
        facts = {"schema": "adams-2026-complete-numerical-facts-v1", "reports": reports,
                 "source_receipts": receipts,
                 "independent_extraction": "PyMuPDF sorted text and pypdf layout agree on every page fact"}
    else:
        facts = json.loads(args.facts.read_text())
    print(json.dumps(build(facts, args.output), indent=2))


if __name__ == "__main__":
    main()

"""Reproduce Lebanon numerical facts without redistributing report templates."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


INDEX = "https://www.lebanoncountypa.gov/departments/voter-registration/election-results"
SOURCES = {
    "county": "https://www.lebanoncountypa.gov/getmedia/5b982a5b-faae-4cf5-bb06-d39f5aef102c/SUMMARY-WITH-WRITE-INS.pdf",
    "unit": "https://www.lebanoncountypa.gov/getmedia/d1cab2fa-f213-484e-86e9-8910e25cfed1/PRECINCT-SUMMARY-WITH-WRITE-INS.pdf",
}
FILES = {"county": "county-summary.pdf", "unit": "precinct-summary.pdf"}
SOURCE_HASHES = {
    "official-index.html": (102047, "da7d428ff290b81361c31d93b636ed548351ed99bd5d3735a569768eab896594"),
    "county-summary.pdf": (24110, "90805818f97075c2771786fbe291a9c5fe52fbad1ee1c6ffeec1ecf7698c5e41"),
    "precinct-summary.pdf": (292975, "a56bf2a23e544276ddf4893edff7fe0dd93561dad2d7bd7fd8c994143315f97e"),
}
OFFICES = (
    "GOVERNOR AND LIEUTENANT GOVERNOR", "REPRESENTATIVE IN CONGRESS 9TH DISTRICT",
    "SENATOR IN THE GENERAL ASSEMBLY 48TH DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 101ST",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 102ND",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 98TH",
)
MODES = ("Total", "Election Day", "Mail In/Absentee", "Provisional")
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
HEADER_WORDS = set("Statistics TOTAL ELECTIO N DAY MAIL IN/ABSE NTEE PROVISI ONAL".split())
QUALIFICATIONS = [
    "All 60 native units reconcile independently to county ballots, blank ballots, modes and candidate vectors.",
    "Native registrations are explicitly zero alongside positive ballots; preserve the literal zero and 0.00%, but withhold the usable denominator and every turnout rate.",
    "The index reports 10,498 mail ballots, none left to process, and 268 provisionals still to process; these pending provisionals are not counted ballots.",
    "The county report separately declares 60/60 Election Day and absentee/early reporting, 0/60 complete and 60/60 partially reported.",
    "UNOFFICIAL RESULTS is not certification; county and unit run times are distinct and have no supplied timezone.",
    "The unit report's literal county label is Electionware County; its actual county scope comes from the declaring Lebanon government page and independently matching county counts.",
    "Write-in details plus Not Assigned equal Write-In Totals; do not sum these overlapping classifications twice or invent parties for write-ins.",
    "Candidate selections do not account for all ballots. Missing under/overvote classifications remain absent; calculated ballot-minus-selection residuals stay unclassified.",
    "The three state-House districts partition county ballots, not three whole-county electorates.",
    "No map, geometry, demographic turnout, final-counting or statewide completion approval. Source presentation templates remain private.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(isinstance(value, str) and re.fullmatch(NUMBER, value), "Invalid native integer")
    return int(value.replace(",", ""))


def counts(values):
    require(isinstance(values, list) and len(values) == 4, "Incomplete native count vector")
    result = [integer(value) for value in values]
    require(result[0] == sum(result[1:]), "Native mode vector does not reconcile")
    return result


def parse_pages(texts, kind):
    size = 3 if kind == "county" else 120
    require(len(texts) == size, "Incomplete report pages")
    pages = []
    for ordinal, text in enumerate(texts, 1):
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        require(lines[:3] == ["Summary Results Report UNOFFICIAL RESULTS",
                "General Election" if kind == "county" else "2026 General",
                "November 3, 2026 " + ("Lebanon County" if kind == "county" else "Electionware County")],
                "Changed election identity, county label or status")
        footer = re.fullmatch(
            rf"{'Election' if kind == 'county' else 'Precinct'} Summary - "
            r"(11/05/2026 \d{1,2}:\d{2} [AP]M) (\d+) of (\d+)", lines[-2])
        require(footer and int(footer[2]) == ordinal and int(footer[3]) == size
                and lines[-1] == "Report generated with Electionware Copyright \u00a9 2007-2020",
                "Missing, unordered or duplicate report page")
        page = dict(page_number=ordinal, unit="Lebanon" if kind == "county" else lines[3],
                    source_update_literal=footer[1], declared_timezone=None,
                    native_status_literal="UNOFFICIAL RESULTS",
                    native_county_label="Lebanon County" if kind == "county" else "Electionware County",
                    participation=None, reporting=[], contests=[])
        contest = None
        for line in lines[3 if kind == "county" else 4:-2]:
            if set(line.split()) <= HEADER_WORDS:
                continue
            if line in OFFICES:
                contest = dict(office_literal=line, vote_for_literal=None, rows=[])
                page["contests"].append(contest)
            elif line == "Vote For 1":
                require(contest is not None and contest["vote_for_literal"] is None, "Duplicate vote-for scope")
                contest["vote_for_literal"] = line
            elif line.startswith("Registered Voters - Total "):
                require(page["participation"] is None, "Duplicate participation")
                page["participation"] = {"registered_voters_literal": line.split()[-1]}
            elif line.startswith(("Ballots Cast - Total ", "Ballots Cast - Blank ")):
                field = "ballot_count_literals" if " - Total " in line else "blank_count_literals"
                require(page["participation"] is not None and field not in page["participation"],
                        "Unexpected or duplicate ballot vector")
                page["participation"][field] = line.split()[-4:]
            elif line.startswith("Voter Turnout - Total "):
                require(page["participation"] is not None
                        and "printed_turnout_literal" not in page["participation"], "Duplicate native turnout")
                page["participation"]["printed_turnout_literal"] = line.split()[-1]
            elif line.startswith(("Election Day Precincts", "Absentee/ Early Precincts",
                                  "Precincts Complete", "Precincts Partially Reported")):
                require(kind == "county", "Unit reporting scope changed")
                match = re.fullmatch(r"(.+?) (\d+) of (\d+) (\d+) (\d+) (\d+)", line)
                require(match is not None, "Incomplete reporting statement")
                page["reporting"].append(dict(label_literal=match[1], reported_literal=match[2],
                    total_literal=match[3], mode_count_literals=list(match.groups()[3:])))
            else:
                match = re.fullmatch(rf"(.+?) ({NUMBER}) ({NUMBER}) ({NUMBER}) ({NUMBER})", line)
                if match:
                    require(contest is not None, "Count row outside native contest")
                    contest["rows"].append(dict(label_literal=match[1],
                                                count_literals=list(match.groups()[1:])))
                else:
                    require(contest is not None and contest["rows"]
                            and contest["rows"][-1]["label_literal"].startswith("Write-In:")
                            and re.fullmatch(r"[A-Z][A-Z .'-]*", line),
                            f"Unrecognized native result line: {line}")
                    contest["rows"][-1]["label_literal"] += " " + line
        pages.append(page)
    return dict(kind=kind, source_url=SOURCES[kind], pages=pages)


def validate(facts):
    require(facts["schema"] == "lebanon-2026-complete-numerical-facts-v1", "Unknown facts schema")
    require(set(facts["source_receipts"]) == set(SOURCE_HASHES), "Incomplete primary-source receipts")
    for name, (size, digest) in SOURCE_HASHES.items():
        receipt = facts["source_receipts"][name]
        url = INDEX if name == "official-index.html" else SOURCES[next(k for k in FILES if FILES[k] == name)]
        require(receipt["url"] == receipt["final_url"] == url and receipt["status"] == 200
                and receipt["bytes"] == size and receipt["sha256"] == digest,
                "Changed frozen source provenance")
    require([report["kind"] for report in facts["reports"]] == ["county", "unit"], "Incomplete report inventory")
    require(facts["index_observation"] == dict(source_url=INDEX, mail_ballots_literal="10498",
            mail_left_to_process_literal="none", pending_provisionals_literal="268"),
            "Changed pending-ballot observations")
    participation, contests, units, statements = {}, {}, set(), []
    for report in facts["reports"]:
        kind = report["kind"]
        require(report["source_url"] == SOURCES[kind] and len(report["pages"]) == (3 if kind == "county" else 120),
                "Incomplete report source/pagination")
        for ordinal, page in enumerate(report["pages"], 1):
            unit = page["unit"]
            require(page["page_number"] == ordinal and page["declared_timezone"] is None
                    and page["source_update_literal"] == ("11/05/2026 12:16 PM" if kind == "county" else "11/05/2026 1:02 PM")
                    and page["native_status_literal"] == "UNOFFICIAL RESULTS"
                    and page["native_county_label"] == ("Lebanon County" if kind == "county" else "Electionware County")
                    and (unit == "Lebanon" if kind == "county" else bool(re.fullmatch(r"\d{2}[A-Z]? .+", unit))),
                    "Changed native page identity/status/update")
            if kind == "unit":
                units.add(unit)
            native, key = page["participation"], (kind, unit)
            if native is not None:
                require(set(native) == {"registered_voters_literal", "ballot_count_literals",
                        "blank_count_literals", "printed_turnout_literal"} and key not in participation,
                        "Incomplete or duplicate native participation")
                require(native["registered_voters_literal"] == "0" and native["printed_turnout_literal"] == "0.00%",
                        "Changed frozen native zero registration/printed rate")
                ballots, blanks = counts(native["ballot_count_literals"]), counts(native["blank_count_literals"])
                require(ballots[0] > 0 and all(blank <= ballot for blank, ballot in zip(blanks, ballots)),
                        "Invalid native ballot/blank counts")
                participation[key] = native
            require(kind == "county" or not page["reporting"], "Wrong reporting scope")
            statements.extend(page["reporting"])
            for contest in page["contests"]:
                identity = (*key, contest["office_literal"])
                require(identity not in contests and identity[2] in OFFICES
                        and contest["vote_for_literal"] == "Vote For 1", "Duplicate or unknown contest")
                rows = {row["label_literal"]: counts(row["count_literals"]) for row in contest["rows"]}
                require(len(rows) == len(contest["rows"]) and "Write-In Totals" in rows and "Not Assigned" in rows,
                        "Duplicate or missing candidate/accounting row")
                require(all(label in ("Write-In Totals", "Not Assigned", "Contest Totals")
                        or label.startswith(("DEM ", "REP ", "LIB ", "INT ", "Write-In: ")) for label in rows),
                        "Unknown literal candidate/party scope")
                writeins = [value for label, value in rows.items() if label.startswith("Write-In: ") or label == "Not Assigned"]
                require([sum(values[i] for values in writeins) for i in range(4)] == rows["Write-In Totals"],
                        "Native write-in details do not reconcile")
                require(("Contest Totals" in rows) == (kind == "county"), "Changed native contest-ballot availability")
                contests[identity] = rows
    require(len(units) == 60 and len(participation) == 61 and len(contests) == 246, "Incomplete native unit/contest inventory")
    require(statements == [
        dict(label_literal=label, reported_literal=n, total_literal="60", mode_count_literals=modes)
        for label, n, modes in [
            ("Election Day Precincts Reporting", "60", ["60", "0", "0"]),
            ("Precincts Complete", "0", ["0", "0", "0"]),
            ("Precincts Partially Reported", "60", ["60", "0", "0"]),
            ("Absentee/ Early Precincts Reporting", "60", ["0", "60", "0"])]], "Changed reporting/completion scope")
    county = participation["county", "Lebanon"]
    require(counts(county["ballot_count_literals"]) == [51268, 40770, 10498, 0]
            and counts(county["blank_count_literals"]) == [3, 2, 1, 0], "Changed frozen county ballots")
    for field in ("ballot_count_literals", "blank_count_literals"):
        require([sum(counts(participation["unit", unit][field])[i] for unit in units) for i in range(4)]
                == counts(county[field]), "Native unit ballots/blanks do not equal county")
    for unit in units:
        offices = {office for kind, name, office in contests if kind == "unit" and name == unit}
        require(set(OFFICES[:3]) <= offices and len(offices) == 4, "Incomplete unit office scope")
    for office in OFFICES:
        expected = contests["county", "Lebanon", office]
        native = [rows for (kind, unit, label), rows in contests.items() if kind == "unit" and label == office]
        require(native and all(set(rows) == set(expected) - {"Contest Totals"} for rows in native),
                "Unit candidate inventories differ from county")
        for label, values in expected.items():
            if label != "Contest Totals":
                require([sum(rows[label][i] for rows in native) for i in range(4)] == values,
                        "Unit candidate vectors do not reconcile to county")
        ballots = [sum(counts(participation["unit", unit]["ballot_count_literals"])[i]
                  for kind, unit, label in contests if kind == "unit" and label == office) for i in range(4)]
        require(ballots == expected["Contest Totals"], "District ballots do not equal unit participation")
        if office in OFFICES[:3]:
            require(ballots == counts(county["ballot_count_literals"]), "Whole-county contest scope differs")
    require([sum(contests["county", "Lebanon", office]["Contest Totals"][i] for office in OFFICES[3:])
             for i in range(4)] == counts(county["ballot_count_literals"]), "State-House districts do not partition ballots")
    for (kind, unit, office), rows in contests.items():
        ballots = rows.get("Contest Totals", counts(participation[kind, unit]["ballot_count_literals"]))
        selections = [sum(values[i] for label, values in rows.items()
                      if label == "Write-In Totals" or re.match(r"^(DEM|REP|LIB|INT) ", label)) for i in range(4)]
        require(all(value <= ballot for value, ballot in zip(selections, ballots)),
                "Candidate selections exceed native ballot scope")
    return facts


def build(facts, output):
    validate(facts)
    output.mkdir(parents=True, exist_ok=False)
    tables = {name: [] for name in ("county-participation.csv", "native-unit-participation.csv",
        "county-candidate-results.csv", "native-unit-candidate-results.csv", "county-literal-party-totals.csv",
        "native-reporting-statements.csv", "native-source-pages.csv", "county-contest-accounting.csv")}
    common = dict(year=2026, state_code="PA", county="Lebanon")
    parties = Counter()
    for report in facts["reports"]:
        county = report["kind"] == "county"
        for page in report["pages"]:
            base = dict(**common, native_unit=page["unit"], source_report=report["kind"],
                source_page=page["page_number"], source_url=report["source_url"],
                source_update_literal=page["source_update_literal"], declared_timezone="",
                native_status_literal=page["native_status_literal"], native_county_label=page["native_county_label"])
            tables["native-source-pages.csv"].append(base)
            if page["participation"] is not None:
                native = page["participation"]
                ballots, blanks = counts(native["ballot_count_literals"]), counts(native["blank_count_literals"])
                row = dict(**base, ballots_cast=ballots[0], election_day_ballots=ballots[1], mail_ballots=ballots[2],
                    provisional_ballots=ballots[3], native_registered_voters=integer(native["registered_voters_literal"]),
                    registered_voters="", native_printed_turnout=native["printed_turnout_literal"],
                    registered_turnout_percent="", blank_ballots=blanks[0],
                    election_day_blank_ballots=blanks[1], mail_blank_ballots=blanks[2], provisional_blank_ballots=blanks[3],
                    native_count_literals_json=json.dumps(native), counting_qualifications_json=json.dumps(QUALIFICATIONS))
                tables["county-participation.csv" if county else "native-unit-participation.csv"].append(row)
            for row in page["reporting"]:
                tables["native-reporting-statements.csv"].append({**base, **row})
            for contest in page["contests"]:
                scope = dict(**base, office_literal=contest["office_literal"], vote_for_literal=contest["vote_for_literal"])
                for native in contest["rows"]:
                    label, values = native["label_literal"], counts(native["count_literals"])
                    if label == "Contest Totals":
                        totals = {row["label_literal"]: counts(row["count_literals"]) for row in contest["rows"]}
                        selections = [sum(v[i] for name, v in totals.items()
                            if name == "Write-In Totals" or re.match(r"^(DEM|REP|LIB|INT) ", name)) for i in range(4)]
                        for mode, ballots, votes in zip(MODES, values, selections):
                            tables["county-contest-accounting.csv"].append(dict(**scope, mode_literal=mode,
                                native_contest_ballots=ballots, candidate_selections_including_write_in_total=votes,
                                unclassified_ballot_minus_selection_residual=ballots-votes,
                                native_under_or_overvote_classification=""))
                        continue
                    party = label.split(" ", 1)[0] if re.match(r"^(DEM|REP|LIB|INT) ", label) else ""
                    row = dict(**scope, label_literal=label, party_literal=party,
                        row_kind="candidate" if party else "write_in_detail" if label.startswith("Write-In: ")
                        else "write_in_total" if label == "Write-In Totals" else "unassigned_write_in_detail",
                        native_count_literals_json=json.dumps(native["count_literals"]))
                    row.update(zip(MODES, values))
                    tables["county-candidate-results.csv" if county else "native-unit-candidate-results.csv"].append(row)
                    if county and party:
                        for mode, value in zip(MODES, values):
                            parties[contest["office_literal"], party, mode] += value
    tables["county-literal-party-totals.csv"] = [dict(**common, office_literal=office, party_literal=party,
        mode_literal=mode, candidate_votes=value) for (office, party, mode), value in parties.items()]
    for name, rows in tables.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / name).write_text(stream.getvalue())
    (output / "source-records.json.gz").write_bytes(gzip.compress(
        (json.dumps(facts, sort_keys=True, indent=2) + "\n").encode(), mtime=0))
    audit = dict(scope="Lebanon only; complete numerical facts, not source presentation templates",
        maps_approved=False, demographic_turnout_approved=False, statewide_completion_approved=False,
        county_participation=tables["county-participation.csv"][0], qualifications=QUALIFICATIONS,
        table_rows={name: len(rows) for name, rows in tables.items()})
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "source-receipts.json").write_text(json.dumps(facts["source_receipts"], indent=2) + "\n")
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "checksums.json").write_text(json.dumps({p.name: dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(output.iterdir())}, indent=2) + "\n")
    target = output / "complete-lebanon-2026-numerical-facts-01.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path != target:
                info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
                info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
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
        from bs4 import BeautifulSoup
        import pdfplumber
        receipts = {}
        for name in ("official-index.html", *FILES.values()):
            body = (args.private_source / name).read_bytes()
            receipt = json.loads((args.private_source / (name + ".receipt.json")).read_text())
            expected_url = INDEX if name == "official-index.html" else SOURCES[next(k for k in FILES if FILES[k] == name)]
            require(receipt["url"] == expected_url and receipt["final_url"] == expected_url
                    and receipt["status"] == 200 and receipt["bytes"] == len(body)
                    and receipt["sha256"] == hashlib.sha256(body).hexdigest(), "Source receipt mismatch")
            receipts[name] = receipt
        soup = BeautifulSoup((args.private_source / "official-index.html").read_bytes(), "html.parser")
        from urllib.parse import urljoin
        declared = {urljoin(INDEX, a["href"]) for a in soup.select("a[href]")}
        require(set(SOURCES.values()) <= declared, "County does not declare source reports")
        index_text = " ".join(soup.get_text(" ", strip=True).split())
        require("2026 General Election and had 10498 mail in ballots, with none still left to process."
                in index_text and "There are 268 Provisionals to process." in index_text,
                "Changed native pending-ballot notice")
        reports = []
        for kind, name in FILES.items():
            with fitz.open(args.private_source / name) as doc:
                first = parse_pages([page.get_text(sort=True) for page in doc], kind)
            with pdfplumber.open(args.private_source / name) as doc:
                second = parse_pages([page.extract_text(x_tolerance=1, y_tolerance=.1) for page in doc.pages], kind)
            require(first == second, "Independent PDF engines disagree on numerical facts")
            reports.append(first)
        facts = dict(schema="lebanon-2026-complete-numerical-facts-v1", reports=reports,
            source_receipts=receipts, independent_extraction="PyMuPDF sorted text and pdfplumber coordinate-sensitive text agree on all page facts",
            index_observation=dict(source_url=INDEX, mail_ballots_literal="10498",
                mail_left_to_process_literal="none", pending_provisionals_literal="268"))
    else:
        facts = json.loads(gzip.decompress(args.facts.read_bytes()))
    print(json.dumps(build(facts, args.output), indent=2))


if __name__ == "__main__":
    main()

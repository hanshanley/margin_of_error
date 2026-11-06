"""Reproduce complete Blair numerical facts, keeping the zero report separate."""

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


INDEX = "https://www.blaircountypa.gov/departments/elections-voter-registration/election-results"
GENERAL = INDEX + "/2026-general"
SOURCES = {
    "current": "https://www.blaircountypa.gov/getmedia/000da964-7b46-40e2-8389-1c3a466b16de/Summary-Results-Report.pdf",
    "pre_election_zero": "https://www.blaircountypa.gov/getmedia/3f761611-d507-4b5f-a5e5-a10625152334/2026-General-Election-11-03-2026-Zero-Report.pdf",
}
FILES = {"current": "county-summary.pdf", "pre_election_zero": "pre-election-zero.pdf"}
SOURCE_HASHES = {
    "official-index.html": (55846, "bf40557bafe1027191640854eef87ecb615e79f6ad9963d082b4fd5242858b70"),
    "general-index.html": (50747, "22c5f9c7e7bf6f7df6f61c13c6e0537c9585be7cbb8563cad3b6eece3234e26e"),
    "county-summary.pdf": (20791, "01555c3d0b0fddea8fdc4cc16647030ba3892ace68a60f49cf3df3d6719cc597"),
    "pre-election-zero.pdf": (20657, "06b5a6f846696452b3e8894e82999551377fa339f92690baf43a1ca59e5be070"),
}
OFFICES = (
    "GOVERNOR / LIEUTENANT GOVERNOR", "REPRESENTATIVE IN CONGRESS",
    "SENATOR IN THE GENERAL ASSEMBLY",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 79TH DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 80TH DISTRICT",
)
MODES = ("Total", "Election Day", "Mail Votes", "Provisional Votes")
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
REPORT_FACTS_SHA256 = "3687fe68bc7d2dbcfc6bf8e690f11470127271c3b9f6fd889ab4106b77c331f9"
QUALIFICATIONS = [
    "Current ballots are 43,898 = 35,560 Election Day + 8,338 Mail Votes + explicit provisional zero.",
    "Native registrations are 81,846; printed 53.63% and the calculated registered-voter fraction remain separate, not CVAP/VEP or demographic turnout.",
    "The separately declared Zero Report is a 6:00 AM pre-election snapshot, not current zero participation; current report time is 10:45 PM. Neither supplies a timezone.",
    "Election Day reporting is 93 of 93 with mode entries 93, 0, 0; these are reporting statements, not zero mail ballots or independent completion/certification.",
    "Candidate/party/write-in selections are separate from ballots; missing under/overvote classifications remain absent and residuals unclassified.",
    "State-House districts are separate electorates with no published district ballot denominators; do not subtract each district's votes from whole-county ballots.",
    "Native UNOFFICIAL RESULTS is not certification. Blank ballots and pending ballots are not supplied, not zero.",
    "No county/precinct map, demographic turnout, statewide completion or finished-counting approval. Source presentation templates remain private.",
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
    require(kind in SOURCES and len(texts) == 2, "Incomplete report or invalid scope")
    pages = []
    for ordinal, text in enumerate(texts, 1):
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        zero = kind == "pre_election_zero"
        require(lines[:3] == ["Summary Results Report UNOFFICIAL RESULTS",
                "GENERAL ELECTION" + (" Zero Report" if zero else ""),
                "November 3, 2026 Blair County, Pennsylvania"], "Changed election identity, county or status")
        update = "11/03/2026 6:00 AM" if zero else "11/03/2026 10:45 PM"
        require(lines[-2:] == [f"Election night for web - {update} {ordinal} of 2",
                "Report generated with Electionware Copyright \u00a9 2007-2020"], "Changed page, timestamp or pagination")
        page = dict(page_number=ordinal, source_update_literal=update, declared_timezone=None,
                    native_status_literal="UNOFFICIAL RESULTS", participation=None, reporting=[], contests=[])
        contest = None
        for line in lines[3:-2]:
            if line in ("Statistics", "TOTAL Election Mail Provision", "Day Votes al Votes",
                        "Statistics TOTAL Election Mail Provision Day Votes al Votes"):
                continue
            if line in OFFICES:
                require(ordinal == 2, "Contest on unexpected page")
                contest = dict(office_literal=line, vote_for_literal=None, rows=[])
                page["contests"].append(contest)
            elif line == "Vote For 1":
                require(contest is not None and contest["vote_for_literal"] is None, "Duplicate vote-for scope")
                contest["vote_for_literal"] = line
            elif line.startswith("Registered Voters - Total "):
                require(ordinal == 1 and page["participation"] is None, "Duplicate participation")
                page["participation"] = dict(registered_voters_literal=line.split()[-1])
            elif line.startswith("Ballots Cast - Total "):
                require(page["participation"] is not None and "ballot_count_literals" not in page["participation"],
                        "Unexpected or duplicate ballots")
                page["participation"]["ballot_count_literals"] = line.split()[-4:]
            elif line.startswith("Voter Turnout - Total "):
                require(page["participation"] is not None and "printed_turnout_literal" not in page["participation"],
                        "Unexpected or duplicate native fraction")
                page["participation"]["printed_turnout_literal"] = line.split()[-1]
            elif line.startswith("Election Day Precincts Reporting "):
                match = re.fullmatch(r"Election Day Precincts Reporting (\d+) of (\d+) (\d+) (\d+) (\d+)", line)
                require(ordinal == 1 and match is not None and not page["reporting"], "Invalid reporting statement")
                page["reporting"].append(dict(label_literal="Election Day Precincts Reporting",
                    reported_literal=match[1], total_literal=match[2], mode_count_literals=list(match.groups()[2:])))
            else:
                match = re.fullmatch(rf"(.+?) ({NUMBER}) ({NUMBER}) ({NUMBER}) ({NUMBER})", line)
                require(contest is not None and match is not None, "Unexpected or incomplete native row: " + line)
                require(re.match(r"^(DEM |REP |LIB |Write-In Totals$)", match[1]), "Unrecognized native result label")
                contest["rows"].append(dict(label_literal=match[1], count_literals=list(match.groups()[1:])))
        pages.append(page)
    return dict(kind=kind, source_url=SOURCES[kind], pages=pages)


def report_digest(reports):
    return hashlib.sha256(json.dumps(reports, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(facts):
    require(facts["schema"] == "blair-2026-complete-numerical-facts-v1", "Changed factual schema")
    require(set(facts["source_receipts"]) == set(SOURCE_HASHES), "Incomplete source receipts")
    for name, (size, digest) in SOURCE_HASHES.items():
        receipt = facts["source_receipts"][name]
        url = INDEX if name == "official-index.html" else GENERAL if name == "general-index.html" else SOURCES[
            next(kind for kind, file in FILES.items() if file == name)]
        require(receipt["url"] == receipt["final_url"] == url and receipt["status"] == 200
                and receipt["bytes"] == size and receipt["sha256"] == digest, "Changed source provenance")
    require([report["kind"] for report in facts["reports"]] == list(SOURCES), "Missing or duplicate report scope")
    inventories = []
    for report in facts["reports"]:
        zero = report["kind"] == "pre_election_zero"
        require(report["source_url"] == SOURCES[report["kind"]] and len(report["pages"]) == 2, "Incomplete native pages")
        stats, results = report["pages"]
        require(stats["page_number"] == 1 and results["page_number"] == 2
                and not stats["contests"] and results["participation"] is None
                and not results["reporting"], "Changed native page scope")
        native = stats["participation"]
        ballots = counts(native["ballot_count_literals"])
        require(integer(native["registered_voters_literal"]) == 81846
                and ballots == ([0, 0, 0, 0] if zero else [43898, 35560, 8338, 0])
                and native["printed_turnout_literal"] == ("0.00%" if zero else "53.63%"), "Changed native participation")
        require(stats["reporting"] == [dict(label_literal="Election Day Precincts Reporting",
                reported_literal="0" if zero else "93", total_literal="93",
                mode_count_literals=["0", "0", "0"] if zero else ["93", "0", "0"])], "Changed reporting scope")
        require([contest["office_literal"] for contest in results["contests"]] == list(OFFICES), "Incomplete contest scopes")
        inventory = []
        for contest in results["contests"]:
            require(contest["vote_for_literal"] == "Vote For 1", "Changed vote-for scope")
            rows = contest["rows"]
            require(len(rows) == (4 if contest["office_literal"] == OFFICES[0] else 3)
                    and rows[-1]["label_literal"] == "Write-In Totals"
                    and len({row["label_literal"] for row in rows}) == len(rows), "Incomplete or duplicate native result lines")
            values = [counts(row["count_literals"]) for row in rows]
            require(all(sum(vector[i] for vector in values) <= ballots[i] for i in range(4)),
                    "Selections exceed county ballot scope")
            if zero:
                require(not any(value for vector in values for value in vector), "Nonzero pre-election zero report")
            inventory.append([row["label_literal"] for row in rows])
        inventories.append(inventory)
    require(inventories[0] == inventories[1], "Current and zero report candidate inventories differ")
    require(report_digest(facts["reports"]) == REPORT_FACTS_SHA256, "Complete reviewed report facts changed")
    return facts


def build(facts, output):
    validate(facts)
    output.mkdir(parents=True, exist_ok=False)
    tables = {name: [] for name in ("county-participation.csv", "pre-election-zero-participation.csv",
        "county-candidate-results.csv", "pre-election-zero-candidate-results.csv",
        "county-literal-party-totals.csv", "native-reporting-statements.csv",
        "native-source-pages.csv", "county-contest-accounting.csv")}
    parties = Counter()
    common = dict(year=2026, state_code="PA", county="Blair")
    for report in facts["reports"]:
        current = report["kind"] == "current"
        for page in report["pages"]:
            base = dict(**common, source_report=report["kind"], source_page=page["page_number"],
                source_url=report["source_url"], source_update_literal=page["source_update_literal"],
                declared_timezone="", native_status_literal=page["native_status_literal"])
            tables["native-source-pages.csv"].append(base)
            if page["participation"] is not None:
                native = page["participation"]
                ballots = counts(native["ballot_count_literals"])
                denominator = integer(native["registered_voters_literal"])
                tables["county-participation.csv" if current else "pre-election-zero-participation.csv"].append(
                    dict(**base, ballots_cast=ballots[0], election_day_ballots=ballots[1], mail_ballots=ballots[2],
                        provisional_ballots=ballots[3], registered_voters=denominator,
                        native_printed_turnout=native["printed_turnout_literal"],
                        registered_turnout_percent=100 * ballots[0] / denominator,
                        native_count_literals_json=json.dumps(native, sort_keys=True),
                        counting_qualifications_json=json.dumps(QUALIFICATIONS)))
            for row in page["reporting"]:
                tables["native-reporting-statements.csv"].append(dict(**base,
                    label_literal=row["label_literal"], reported_literal=row["reported_literal"],
                    total_literal=row["total_literal"],
                    native_mode_count_literals_json=json.dumps(row["mode_count_literals"])))
            for contest in page["contests"]:
                scope = dict(**base, office_literal=contest["office_literal"], vote_for_literal=contest["vote_for_literal"])
                selections = [0] * 4
                for native in contest["rows"]:
                    label, values = native["label_literal"], counts(native["count_literals"])
                    party = label.split(" ", 1)[0] if label != "Write-In Totals" else ""
                    row = dict(**scope, label_literal=label, party_literal=party,
                        row_kind="candidate" if party else "write_in_total",
                        native_count_literals_json=json.dumps(native["count_literals"]))
                    row.update(zip(MODES, values))
                    tables["county-candidate-results.csv" if current else "pre-election-zero-candidate-results.csv"].append(row)
                    selections = [a + b for a, b in zip(selections, values)]
                    if current and party:
                        for mode, value in zip(MODES, values):
                            parties[contest["office_literal"], party, mode] += value
                for i, mode in enumerate(MODES):
                    whole = contest["office_literal"] in OFFICES[:3]
                    ballots = [43898, 35560, 8338, 0][i] if current else 0
                    tables["county-contest-accounting.csv"].append(dict(**scope, mode_literal=mode,
                        candidate_selections_including_write_in_total=selections[i],
                        native_contest_ballot_denominator="",
                        reviewed_county_ballots_for_whole_county_contest_only=ballots if whole else "",
                        unclassified_ballot_minus_selection_residual=ballots - selections[i] if whole else "",
                        native_under_or_overvote_classification=""))
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
    audit = dict(scope="Blair county only; current and pre-election zero reports remain separate",
        maps_approved=False, demographic_turnout_approved=False, statewide_completion_approved=False,
        county_participation=tables["county-participation.csv"][0], qualifications=QUALIFICATIONS,
        table_rows={name: len(rows) for name, rows in tables.items()})
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "source-receipts.json").write_text(json.dumps(facts["source_receipts"], sort_keys=True, indent=2) + "\n")
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "checksums.json").write_text(json.dumps({p.name: dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(output.iterdir())}, indent=2) + "\n")
    target = output / "complete-blair-2026-numerical-facts-01.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path != target:
                info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
                info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
                archive.writestr(info, path.read_bytes())
    return audit


def acquire(directory):
    import fitz
    import pdfplumber
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    receipts = {}
    for name in SOURCE_HASHES:
        body = (directory / name).read_bytes()
        receipt = json.loads((directory / (name + ".receipt.json")).read_text())
        require(receipt["bytes"] == len(body) and receipt["sha256"] == hashlib.sha256(body).hexdigest(),
                "Source bytes and receipt disagree")
        receipts[name] = receipt
    parent = BeautifulSoup((directory / "official-index.html").read_bytes(), "html.parser")
    general = BeautifulSoup((directory / "general-index.html").read_bytes(), "html.parser")
    require(GENERAL in {urljoin(INDEX, a["href"]) for a in parent.select("a[href]")},
            "Government parent does not declare 2026 general index")
    require(set(SOURCES.values()) <= {urljoin(GENERAL, a["href"]) for a in general.select("a[href]")},
            "Government general index does not declare both reports")
    reports = []
    for kind, name in FILES.items():
        with fitz.open(directory / name) as doc:
            first = parse_pages([page.get_text(sort=True) for page in doc], kind)
        with pdfplumber.open(directory / name) as doc:
            second = parse_pages([page.extract_text(x_tolerance=1, y_tolerance=.1) for page in doc.pages], kind)
        require(first == second, "Independent PDF engines disagree on complete report facts")
        reports.append(first)
    return dict(schema="blair-2026-complete-numerical-facts-v1", reports=reports,
        source_receipts=receipts,
        independent_extraction="PyMuPDF sorted text and pdfplumber coordinate-sensitive text agree on all four pages")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--private-source", type=Path)
    source.add_argument("--facts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    facts = acquire(args.private_source) if args.private_source else json.loads(gzip.decompress(args.facts.read_bytes()))
    print(json.dumps(build(facts, args.output), indent=2))


if __name__ == "__main__":
    main()

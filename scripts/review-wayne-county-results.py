"""Reproduce Wayne's complete county numerical facts without substituting contest totals."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


PARENT = "https://www.waynecountypa.gov/197/Bureau-Of-Elections"
INDEX = "https://www.waynecountypa.gov/1100/2026-General-Election-Unofficial-Results"
SOURCE = ("https://www.waynecountypa.gov/DocumentCenter/View/8660/"
          "Statement-of-Votes-Cast--for-NOVEMBER_3_2026_GENERALELECTION_bdfx-34")
TERMS = "https://www.waynecountypa.gov/site/copyright"
SOURCE_HASHES = {
    "browser-election-parent.html": (PARENT, 142680, "56f6b25556de51b667b910c4bc7d3c20f3cf3618901bc5498f09eaad9de21b68"),
    "browser-results-index.html": (INDEX, 111132, "1cca2d068c934aac33bad4e999881330c193a35e2285f8d4a023a10c393c1c7e"),
    "county-statement.pdf": (SOURCE, 4659, "a69e920c3693be54abb882001665e493b1c5a07659272f969557437926e823b6"),
    "copyright-notices.html": (TERMS, 103075, "4e0c103c014154de2fdd5e5f36c3a734c6022826961b25650b24079fa0aa08b6"),
}
OFFICES = (
    "GOVERNOR AND LIEUTENANT GOVERNOR (Vote for 1)",
    "REPRESENTATIVE IN CONGRESS 8TH DISTRICT (Vote for 1)",
    "SENATOR IN THE GENERAL ASSEMBLY 20TH DISTRICT (Vote for 1)",
    "SENATOR IN THE GENERAL ASSEMBLY 40TH DISTRICT (Vote for 1)",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 111TH DISTRICT (Vote for 1)",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 139TH DISTRICT (Vote for 1)",
)
SUMMARY = "All Precincts, All Districts, All Counter Groups, All ScanStations, All Contests, All Boxes"
PARENT_STATUS = "2026 General Election Unofficial Results"
MODES = ("Total", "ED", "MI", "PR")
NUMBER = r"(?:0|[1-9]\d*)"
REPORT_FACTS_SHA256 = "31a3882d0e8c18c07ef7a489d007dcc47162333fae736752966e1b39ad3e59ca"
QUALIFICATIONS = [
    "Native county header reports 21,707 Total Ballots Cast, 36,885 registered voters and printed 58.85%; candidate selections and contest ballots are separate.",
    "The governor contest reports 21,689 ballots, 18 fewer than the county header. Each pair of state legislative district ballot counts also sums to 21,689. Preserve the unexplained 18-ballot scope difference; do not overwrite the header or invent pending-ballot explanations.",
    "Congress reports 21,707 ballots. Every individual contest reconciles its own ballots with its candidate/write-in selections, overvotes and undervotes.",
    "Over voted ballots and Overvotes are separately printed descriptions of the same count in these vote-for-one contests, not two additive residuals.",
    "Literal ED, MI and PR columns contain candidate selections, not mode-level ballots or registrations; their expansions and mode participation denominators are not supplied in this report.",
    "All nineteen choice rows include six Write-in rows. Native Total includes write-ins and is not an additional candidate.",
    "Candidate parties are not supplied. Preserve missing party literals; do not infer affiliation from names or treat missing party totals as zero.",
    "Six native contest registration/ballot denominators and printed rates retain their actual district scopes; no district becomes a county denominator.",
    "Printed 35 precincts reported out of 35 total is reporting coverage, not independently certified or complete ballot counting.",
    "Parent page labels results unofficial; PDF supplies no separate result-status literal. Native 2026-11-05 15:08:51 has no declared timezone.",
    "Source notices reserve rights in county and CivicPlus content. Original HTML/PDF presentation remains private; only complete numerical facts, provenance and reproducible derived tables are redistributed.",
    "No precinct geometry, map, demographic turnout, certification or statewide completion approval.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(isinstance(value, str) and re.fullmatch(NUMBER, value), "Invalid native integer")
    return int(value)


def vector(values):
    require(isinstance(values, list) and len(values) == 4, "Incomplete native count vector")
    numbers = [integer(value) for value in values]
    require(numbers[0] == sum(numbers[1:]), "Native selection modes do not reconcile")
    return numbers


def parse_contest(office, text):
    match = re.match(
        rf"({NUMBER}) ballots \(({NUMBER}) over voted ballots, ({NUMBER}) overvotes, "
        rf"({NUMBER}) undervotes\), ({NUMBER}) registered voters, turnout (\d+\.\d+%) ", text)
    require(match is not None, "Missing native contest participation")
    contest = dict(office_literal=office, ballots_literal=match[1],
        over_voted_ballots_literal=match[2], overvotes_literal=match[3],
        undervotes_literal=match[4], registered_voters_literal=match[5],
        printed_turnout_literal=match[6], rows=[])
    choices, separator, totals = text[match.end():].partition(" Total ")
    require(separator, "Missing native contest subtotal")
    while choices:
        row = re.match(rf"(.+?) ({NUMBER}) (\d+\.\d+%) ({NUMBER}) ({NUMBER}) ({NUMBER})(?: |$)", choices)
        require(row is not None, "Incomplete native choice vector")
        contest["rows"].append(dict(label_literal=row[1], party_literal="",
            row_kind="write_in" if row[1] == "Write-in" else "candidate",
            printed_vote_percent_literal=row[3],
            count_literals=[row[2], row[4], row[5], row[6]]))
        choices = choices[row.end():]
    tail = re.fullmatch(
        rf"({NUMBER}) (100\.00%) ({NUMBER}) ({NUMBER}) ({NUMBER}) "
        rf"Overvotes ({NUMBER}) Undervotes ({NUMBER})", totals)
    require(tail is not None, "Incomplete native subtotal or accounting")
    require(tail[6] == contest["overvotes_literal"]
        and tail[7] == contest["undervotes_literal"], "Native repeated accounting differs")
    contest["native_total_count_literals"] = [tail[1], tail[3], tail[4], tail[5]]
    contest["native_total_percent_literal"] = tail[2]
    return contest


def parse_pages(texts):
    require(len(texts) == 1, "Incomplete or changed county report pagination")
    text = " ".join(texts[0].split())
    for pattern in (r"Page: 1 of 1", r"\b\d{4}-\d{2}-\d{2}\b", r"\b\d{2}:\d{2}:\d{2}\b"):
        matches = list(re.finditer(pattern, text))
        require(len(matches) == 1, "Missing or ambiguous native timestamp/pagination")
        match = matches[0]
        if pattern.startswith(r"\b\d{4}"):
            date = match[0]
        elif pattern.startswith(r"\b\d{2}"):
            time = match[0]
        text = text[:match.start()] + text[match.end():]
    text = " ".join(text.split())
    prefix = ("Statement of Votes Cast by Geography WAYNE COUNTY, NOVEMBER 3, 2026 "
              "GENERAL ELECTION, Nov 03, 2026 " + SUMMARY + " ")
    require(text.startswith(prefix), "Changed county, election or native report scope")
    text = text[len(prefix):]
    match = re.match(rf"Total Ballots Cast: ({NUMBER}), Registered Voters: ({NUMBER}), "
        rf"Overall Turnout: (\d+\.\d+%) ({NUMBER}) precincts reported out of ({NUMBER}) total "
        r"Choice Votes Vote % ED MI PR All Precincts ", text)
    require(match is not None, "Missing native county participation or selection header")
    report = dict(source_url=SOURCE, source_page=1, source_update_literal=date + " " + time,
        declared_timezone=None, native_summary_scope_literal=SUMMARY, native_status_literal="",
        native_parent_status_literal=PARENT_STATUS, native_participation_measure_literal="Total Ballots Cast",
        ballots_literal=match[1], registered_voters_literal=match[2],
        printed_turnout_literal=match[3], precincts_reported_literal=match[4],
        precincts_total_literal=match[5], contests=[])
    text = text[match.end():]
    for position, office in enumerate(OFFICES):
        require(text.startswith(office + " "), "Missing or changed native contest scope")
        text = text[len(office) + 1:]
        if position < len(OFFICES) - 1:
            body, separator, remainder = text.partition(" " + OFFICES[position + 1] + " ")
            require(separator, "Incomplete next contest")
            text = OFFICES[position + 1] + " " + remainder
        else:
            body, text = text, ""
        report["contests"].append(parse_contest(office, body))
    require(not text, "Unconsumed county report facts")
    return report


def report_digest(report):
    return hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(facts):
    require(facts["schema"] == "wayne-2026-complete-numerical-facts-v1", "Changed factual schema")
    require(set(facts["source_receipts"]) == set(SOURCE_HASHES), "Incomplete source receipts")
    for name, (url, size, digest) in SOURCE_HASHES.items():
        receipt = facts["source_receipts"][name]
        require(receipt["url"] == receipt["final_url"] == url and receipt["status"] == 200
            and receipt["bytes"] == size and receipt["sha256"] == digest, "Changed source provenance")
    report = facts["report"]
    require(report["source_url"] == SOURCE and report["source_page"] == 1
        and report["native_summary_scope_literal"] == SUMMARY and not report["native_status_literal"]
        and report["native_parent_status_literal"] == PARENT_STATUS
        and report["native_participation_measure_literal"] == "Total Ballots Cast"
        and report["declared_timezone"] is None, "Changed native report scope")
    require(report["ballots_literal"] == "21707" and report["registered_voters_literal"] == "36885"
        and report["printed_turnout_literal"] == "58.85%"
        and report["precincts_reported_literal"] == report["precincts_total_literal"] == "35",
        "Changed county header participation")
    require([contest["office_literal"] for contest in report["contests"]] == list(OFFICES),
            "Incomplete native contest inventory")
    for position, contest in enumerate(report["contests"]):
        rows = contest["rows"]
        require(len(rows) == (4 if position == 0 else 3)
            and rows[-1]["row_kind"] == "write_in" and rows[-1]["label_literal"] == "Write-in"
            and all(row["party_literal"] == "" for row in rows)
            and len({row["label_literal"] for row in rows}) == len(rows), "Changed native choice inventory or missing parties")
        vectors = [vector(row["count_literals"]) for row in rows]
        subtotal = vector(contest["native_total_count_literals"])
        require([sum(values[index] for values in vectors) for index in range(4)] == subtotal,
                "Native choice subtotal does not reconcile")
        require(contest["over_voted_ballots_literal"] == contest["overvotes_literal"],
                "Changed vote-for-one overvote relationship")
        require(integer(contest["ballots_literal"]) == subtotal[0]
            + integer(contest["overvotes_literal"]) + integer(contest["undervotes_literal"]),
            "Contest participation/accounting does not reconcile")
        integer(contest["registered_voters_literal"])
    require(report_digest(report) == REPORT_FACTS_SHA256, "Complete reviewed report facts changed")
    return facts


def build(facts, output):
    validate(facts)
    output.mkdir(parents=True, exist_ok=False)
    tables = {name: [] for name in ("county-participation.csv", "county-candidate-results.csv",
        "native-contest-participation.csv", "native-contest-subtotals.csv",
        "county-contest-accounting.csv", "native-source-pages.csv", "native-source-statements.csv")}
    report = facts["report"]
    common = dict(year=2026, state_code="PA", county="Wayne", source_url=SOURCE, source_page=1,
        source_update_literal=report["source_update_literal"], declared_timezone="",
        native_summary_scope_literal=SUMMARY, native_status_literal="",
        native_parent_status_literal=PARENT_STATUS)
    tables["native-source-pages.csv"].append(common)
    ballots, registrations = integer(report["ballots_literal"]), integer(report["registered_voters_literal"])
    tables["county-participation.csv"].append(dict(**common,
        native_participation_measure_literal=report["native_participation_measure_literal"],
        ballots_cast=ballots, election_day_ballots="", mail_ballots="", provisional_ballots="",
        registered_voters=registrations, native_printed_turnout=report["printed_turnout_literal"],
        registered_turnout_percent=100 * ballots / registrations,
        precincts_reported=integer(report["precincts_reported_literal"]),
        precincts_total=integer(report["precincts_total_literal"]),
        counting_qualifications_json=json.dumps(QUALIFICATIONS)))
    for label, value, url in (
        ("parent_result_status", PARENT_STATUS, INDEX),
        ("precincts_reported", report["precincts_reported_literal"], SOURCE),
        ("precincts_total", report["precincts_total_literal"], SOURCE),
    ):
        tables["native-source-statements.csv"].append(dict(**common,
            statement_label=label, native_value_literal=value, statement_source_url=url))
    for contest in report["contests"]:
        base = dict(**common, office_literal=contest["office_literal"])
        tables["native-contest-participation.csv"].append(dict(**base,
            ballots_literal=contest["ballots_literal"], registered_voters_literal=contest["registered_voters_literal"],
            printed_turnout_literal=contest["printed_turnout_literal"],
            over_voted_ballots_literal=contest["over_voted_ballots_literal"],
            overvotes_literal=contest["overvotes_literal"], undervotes_literal=contest["undervotes_literal"]))
        subtotal = vector(contest["native_total_count_literals"])
        row = dict(**base, native_label_literal="Total",
            printed_vote_percent_literal=contest["native_total_percent_literal"],
            native_count_literals_json=json.dumps(contest["native_total_count_literals"]))
        row.update(zip(MODES, subtotal))
        tables["native-contest-subtotals.csv"].append(row)
        for choice in contest["rows"]:
            row = dict(**base, label_literal=choice["label_literal"], party_literal=choice["party_literal"],
                row_kind=choice["row_kind"], printed_vote_percent_literal=choice["printed_vote_percent_literal"],
                native_count_literals_json=json.dumps(choice["count_literals"]))
            row.update(zip(MODES, vector(choice["count_literals"])))
            tables["county-candidate-results.csv"].append(row)
        for index, mode in enumerate(MODES):
            whole = contest["office_literal"] in OFFICES[:2] and mode == "Total"
            tables["county-contest-accounting.csv"].append(dict(**base, mode_literal=mode,
                candidate_selections_including_write_in=subtotal[index],
                native_contest_ballots=integer(contest["ballots_literal"]) if index == 0 else "",
                native_overvotes=integer(contest["overvotes_literal"]) if index == 0 else "",
                native_undervotes=integer(contest["undervotes_literal"]) if index == 0 else "",
                unclassified_contest_accounting_residual=0 if index == 0 else "",
                county_header_ballots_for_whole_county_scope_only=ballots if whole else "",
                unclassified_header_minus_contest_ballots=(
                    ballots - integer(contest["ballots_literal"]) if whole else "")))
    for name, rows in tables.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / name).write_text(stream.getvalue())
    (output / "source-records.json.gz").write_bytes(gzip.compress(
        (json.dumps(facts, sort_keys=True, indent=2) + "\n").encode(), mtime=0))
    audit = dict(scope="Wayne whole-county header participation; six separately scoped contest denominators",
        maps_approved=False, demographic_turnout_approved=False, statewide_completion_approved=False,
        county_participation=tables["county-participation.csv"][0], qualifications=QUALIFICATIONS,
        table_rows={name: len(rows) for name, rows in tables.items()})
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "source-receipts.json").write_text(json.dumps(facts["source_receipts"], sort_keys=True, indent=2) + "\n")
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "checksums.json").write_text(json.dumps({path.name: dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(output.iterdir())}, indent=2) + "\n")
    target = output / "complete-wayne-2026-numerical-facts-01.zip"
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
    parent = BeautifulSoup((directory / "browser-election-parent.html").read_bytes(), "html.parser")
    require(INDEX in {urljoin(PARENT, a["href"]) for a in parent.select("a[href]")},
            "Government parent does not declare current result index")
    index = BeautifulSoup((directory / "browser-results-index.html").read_bytes(), "html.parser")
    links = {urljoin(INDEX, a["href"]) for a in index.select("a[href]")}
    require({SOURCE, TERMS} <= links and PARENT_STATUS in index.get_text(" ", strip=True),
            "Government index does not declare report, notices or unofficial status")
    with fitz.open(directory / "county-statement.pdf") as doc:
        first = parse_pages([page.get_text(sort=True) for page in doc])
    with pdfplumber.open(directory / "county-statement.pdf") as doc:
        second = parse_pages([page.extract_text(x_tolerance=1, y_tolerance=.1) for page in doc.pages])
    require(first == second, "Independent PDF engines disagree on complete report facts")
    return dict(schema="wayne-2026-complete-numerical-facts-v1", report=first,
        source_receipts=receipts,
        independent_extraction="PyMuPDF sorted text and pdfplumber coordinate-sensitive text agree on the complete page")


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

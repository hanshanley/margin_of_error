"""Reproduce the complete two-page Huntingdon summary as numerical facts."""

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


INDEX = "https://www.huntingdoncountypa.gov/"
SUMMARY = INDEX + "getmedia/de181940-3a03-4f1c-8654-0fc4f445da7d/2026-Primary-Election-Summary.pdf"
SOURCES = {
    "parent.html": (INDEX, 77893, "f8089841ee03b5fad40ec768fdb264525362fde2d7e4bfee142e61d2d0b55c67"),
    "summary.pdf": (SUMMARY, 21140, "4f0281121f4cac439e8d116bb8b2cd2f3993156872f66a46f7ca273d80450e57"),
}
OFFICES = (
    "GOVERNOR AND LIEUTENANT GOVERNOR", "REPRESENTATIVE IN CONGRESS",
    "SENATOR 30TH DISTRICT", "REPRESENTATIVE 80TH DISTRICT", "REPRESENTATIVE 81ST DISTRICT",
)
REPORTING = ("Election Day Precincts Reporting", "Precincts Complete",
    "Precincts Partially Reported", "Absentee/ Early Precincts Reporting")
MODES = ("Total", "Election Day", "Mail Votes", "Provisional Votes")
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
VECTOR = " ".join([f"({NUMBER})"] * 4)
FACTS_SHA256 = "271b6cc922f3c90fd656e7516dff0237bb992194dfdb96a56c5269389f61ab83"
QUALIFICATIONS = [
    "The complete two-page general-election summary supplies 16,024 ballots and 27,917 registrations; candidate selections are separate.",
    "Ballots are 13,855 Election Day + 2,169 Mail Votes + explicit provisional zero. Actual blank ballots are explicitly zero, not an inferred residual.",
    "57.40% is the native printed registered-voter fraction, not CVAP, VAP, VEP or demographic turnout.",
    "Both pages retain 11/03/2026 9:56 PM, with no supplied timezone. HTTP retrieval and Last-Modified timestamps are not election update clocks.",
    "The report is UNOFFICIAL RESULTS. Its 58/58 complete and 0/58 partially reported statements do not establish certification or finished counting.",
    "The county declares a URL containing Primary but the response disposition and every PDF page identify the November 3 general election; preserve the literal URL.",
    "Each candidate keeps its literal party and all four mode counts; write-ins have no supplied party. Overvotes and undervotes remain native accounting, not candidate votes.",
    "The first three contest accounting vectors each match county ballots. The two state-House accounting vectors sum to county ballots, but this is not a verified geographic partition.",
    "District ballot scopes are derived from supplied selections plus overvotes and undervotes; district electorates and mode registration denominators are absent, not the whole-county registrations.",
    "No native FIPS, new geometry, demographic turnout, statewide completion or redistribution permission for original HTML/PDF templates is approved.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def counts(values):
    require(isinstance(values, list) and len(values) == 4
        and all(isinstance(v, str) and re.fullmatch(NUMBER, v) for v in values),
        "Incomplete native count vector")
    numbers = [int(v.replace(",", "")) for v in values]
    require(numbers[0] == sum(numbers[1:]), "Native mode vector does not reconcile")
    return numbers


def parse_pages(texts):
    require(len(texts) == 2, "Incomplete summary")
    pages = []
    for ordinal, text in enumerate(texts, 1):
        text = " ".join(text.split())
        anchor = REPORTING[0] if ordinal == 1 else OFFICES[0]
        header, separator, body = text.partition(anchor)
        require(separator and all(v in header for v in (
            "Summary Results Report", "UNOFFICIAL RESULTS", "General Election",
            "November 3, 2026", "Huntingdon County")), "Changed report identity")
        body = anchor + body
        footer = re.search(r" Election Summary - (11/03/2026 \d{1,2}:\d{2} [AP]M) "
            + str(ordinal) + r" of 2 Report generated with Electionware Copyright \u00a9 2007-2020$", body)
        require(footer is not None, "Changed page, timestamp or pagination")
        body = body[:footer.start()]
        page = dict(page_number=ordinal, source_update_literal=footer[1], declared_timezone=None,
            native_status_literal="UNOFFICIAL RESULTS", participation=None, reporting=[], contests=[])
        if ordinal == 1:
            for label in REPORTING:
                match = re.match(re.escape(label) + r" (\d+) of (\d+) (\d+) (\d+) (\d+) ", body)
                require(match is not None, "Incomplete native reporting")
                page["reporting"].append(dict(label_literal=label, reported_literal=match[1],
                    total_literal=match[2], mode_count_literals=list(match.groups()[2:])))
                body = body[match.end():]
            match = re.fullmatch(rf"Registered Voters - Total ({NUMBER}) Ballots Cast - Total {VECTOR} "
                rf"Ballots Cast - Blank {VECTOR} Voter Turnout - Total (\d+\.\d{{2}}%)", body)
            require(match is not None, "Incomplete county participation")
            page["participation"] = dict(registered_voters_literal=match[1],
                ballot_count_literals=list(match.groups()[1:5]),
                blank_count_literals=list(match.groups()[5:9]), printed_turnout_literal=match[10])
        else:
            for index, office in enumerate(OFFICES):
                require(body.startswith(office + " "), "Changed or missing office")
                body = body[len(office) + 1:]
                if index + 1 < len(OFFICES):
                    section, separator, tail = body.partition(" " + OFFICES[index + 1] + " ")
                    require(separator, "Missing next contest")
                    body = OFFICES[index + 1] + " " + tail
                else:
                    section, body = body, ""
                heading = re.match(r"Vote For 1 TOTAL Election "
                    r"(?:Day Mail Votes Provision al|Mail Provision Day Votes al) Votes ", section)
                require(heading is not None, "Changed contest mode columns")
                section = section[heading.end():]
                rows = []
                while section:
                    row = re.match(rf"(DEM .+?|REP .+?|LIB .+?|Write-In Totals|Overvotes|Undervotes) "
                        + VECTOR + r"(?: |$)", section)
                    require(row is not None, "Unrecognized native result row")
                    rows.append(dict(label_literal=row[1], count_literals=list(row.groups()[1:])))
                    section = section[row.end():]
                page["contests"].append(dict(office_literal=office, vote_for_literal="Vote For 1", rows=rows))
            require(not body, "Unconsumed contest facts")
        pages.append(page)
    return pages


def validate(facts):
    require(facts["schema"] == "huntingdon-2026-complete-summary-facts-v1", "Changed schema")
    require(set(facts["source_receipts"]) == set(SOURCES), "Incomplete source inventory")
    for name, (url, size, sha) in SOURCES.items():
        receipt = facts["source_receipts"][name]
        require(receipt["url"] == receipt["final_url"] == url and receipt["status"] == 200
            and receipt["bytes"] == size and receipt["sha256"] == sha
            and receipt["chain_verified"] is True and receipt["hostname_verified"] is True,
            "Changed source provenance")
    pages = facts["pages"]
    require(len(pages) == 2 and [p["page_number"] for p in pages] == [1, 2], "Incomplete native pages")
    require(all(p["source_update_literal"] == "11/03/2026 9:56 PM"
        and p["declared_timezone"] is None and p["native_status_literal"] == "UNOFFICIAL RESULTS"
        for p in pages), "Changed clock or status")
    native = pages[0]["participation"]
    require(pages[1]["participation"] is None and not pages[0]["contests"]
        and not pages[1]["reporting"], "Changed native page scopes")
    ballots, blanks = counts(native["ballot_count_literals"]), counts(native["blank_count_literals"])
    registrations = int(native["registered_voters_literal"].replace(",", ""))
    require(registrations > 0 and all(b <= a for a, b in zip(ballots, blanks)), "Invalid participation")
    require(abs(100 * ballots[0] / registrations
        - float(native["printed_turnout_literal"].removesuffix("%"))) <= .005001,
        "Printed turnout does not reconcile")
    reporting = pages[0]["reporting"]
    require([r["label_literal"] for r in reporting] == list(REPORTING), "Incomplete reporting statements")
    for row in reporting:
        require(0 <= int(row["reported_literal"]) <= int(row["total_literal"])
            and len(row["mode_count_literals"]) == 3, "Invalid native reporting scope")
    contests = pages[1]["contests"]
    require([c["office_literal"] for c in contests] == list(OFFICES), "Incomplete contest scopes")
    totals = []
    for contest in contests:
        require(contest["vote_for_literal"] == "Vote For 1", "Changed vote-for scope")
        rows = {r["label_literal"]: counts(r["count_literals"]) for r in contest["rows"]}
        require(len(rows) == len(contest["rows"])
            and list(rows)[-3:] == ["Write-In Totals", "Overvotes", "Undervotes"]
            and all(label.startswith(("DEM ", "REP ", "LIB ")) for label in list(rows)[:-3]),
            "Duplicate, missing or invented candidate/accounting rows")
        totals.append([sum(v[i] for v in rows.values()) for i in range(4)])
    require(totals[:3] == [ballots] * 3 and [sum(v[i] for v in totals[3:]) for i in range(4)] == ballots,
        "Contest accounting does not reconcile to county ballot vectors")
    require(digest(pages) == FACTS_SHA256, "Native facts differ from reviewed two-engine extraction")


def build(facts, output):
    validate(facts)
    output.mkdir(parents=True, exist_ok=False)
    common = dict(state="Pennsylvania", county="Huntingdon", election_date="2026-11-03",
        source_fips="", source_url=SUMMARY, source_update_literal="11/03/2026 9:56 PM",
        declared_timezone="", native_status_literal="UNOFFICIAL RESULTS")
    pages = facts["pages"]
    native = pages[0]["participation"]
    ballots, blanks = counts(native["ballot_count_literals"]), counts(native["blank_count_literals"])
    registrations = int(native["registered_voters_literal"].replace(",", ""))
    tables = {
        "county-participation.csv": [dict(**common, native_participation_measure_literal="Ballots Cast - Total",
            ballots_cast=ballots[0], election_day_ballots=ballots[1], mail_ballots=ballots[2],
            provisional_ballots=ballots[3], registered_voters=registrations, blank_ballots=blanks[0],
            native_printed_turnout=native["printed_turnout_literal"],
            registered_turnout_percent=100 * ballots[0] / registrations,
            native_count_literals_json=json.dumps(native, sort_keys=True), qualifications_json=json.dumps(QUALIFICATIONS))],
        "native-source-pages.csv": [dict(**common, page_number=p["page_number"],
            total_pages=2, has_native_county_participation=p["participation"] is not None) for p in pages],
        "native-reporting-statements.csv": [dict(**common, **row) for row in pages[0]["reporting"]],
        "native-candidate-results.csv": [], "native-contest-accounting.csv": [],
        "county-contest-accounting.csv": [], "county-literal-party-totals.csv": [],
    }
    parties = Counter()
    for contest in pages[1]["contests"]:
        office = contest["office_literal"]
        total, selections, overs, unders = [0] * 4, [0] * 4, None, None
        for native_row in contest["rows"]:
            label, values = native_row["label_literal"], counts(native_row["count_literals"])
            accounting = label in {"Overvotes", "Undervotes"}
            party = label.split(" ", 1)[0] if label.startswith(("DEM ", "REP ", "LIB ")) else ""
            row = dict(**common, office_literal=office, vote_for_literal=contest["vote_for_literal"],
                label_literal=label, party_literal=party,
                row_kind="accounting" if accounting else "candidate" if party else "write_in_total",
                native_count_literals_json=json.dumps(native_row["count_literals"]))
            row.update(zip(MODES, values))
            tables["native-contest-accounting.csv" if accounting else "native-candidate-results.csv"].append(row)
            total = [a + b for a, b in zip(total, values)]
            if not accounting:
                selections = [a + b for a, b in zip(selections, values)]
            elif label == "Overvotes":
                overs = values
            else:
                unders = values
            if party:
                for mode, value in zip(MODES, values):
                    parties[office, party, mode] += value
        for index, mode in enumerate(MODES):
            tables["county-contest-accounting.csv"].append(dict(**common, office_literal=office,
                mode_literal=mode, candidate_and_write_in_selections=selections[index],
                native_overvotes=overs[index], native_undervotes=unders[index],
                derived_contest_ballots=total[index], district_registered_voters="",
                geographic_partition_verified=False, matches_county_ballot_vector=total == ballots))
    tables["county-literal-party-totals.csv"] = [dict(**common, office_literal=office,
        party_literal=party, mode_literal=mode, candidate_votes=value)
        for (office, party, mode), value in parties.items()]
    for name, rows in tables.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / name).write_text(stream.getvalue())
    (output / "source-records.json.gz").write_bytes(gzip.compress(
        (json.dumps(facts, sort_keys=True, indent=2) + "\n").encode(), mtime=0))
    audit = dict(scope="Huntingdon only; complete two-page numerical report, not source templates",
        maps_approved=False, demographic_turnout_approved=False, statewide_completion_approved=False,
        county_participation=tables["county-participation.csv"][0], qualifications=QUALIFICATIONS,
        table_rows={name: len(rows) for name, rows in tables.items()})
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "source-receipts.json").write_text(json.dumps(facts["source_receipts"], sort_keys=True, indent=2) + "\n")
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "checksums.json").write_text(json.dumps({p.name: dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(output.iterdir())}, indent=2) + "\n")
    target = output / "complete-huntingdon-2026-numerical-facts-01.zip"
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
        import pdfplumber
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        receipts = json.loads((args.private_source / "receipts.json").read_text())
        for name, (url, size, sha) in SOURCES.items():
            body = (args.private_source / name).read_bytes()
            require(len(body) == size and hashlib.sha256(body).hexdigest() == sha, "Changed source bytes")
        soup = BeautifulSoup((args.private_source / "parent.html").read_bytes(), "html.parser")
        require(SUMMARY in {urljoin(INDEX, a["href"]) for a in soup.select("a[href]")},
            "County does not declare the summary")
        with fitz.open(args.private_source / "summary.pdf") as document:
            first = parse_pages([page.get_text() for page in document])
        with pdfplumber.open(args.private_source / "summary.pdf") as document:
            second = parse_pages([page.extract_text() for page in document.pages])
        require(first == second, "Independent PDF engines disagree on native facts")
        facts = dict(schema="huntingdon-2026-complete-summary-facts-v1", pages=first,
            source_receipts=receipts,
            independent_extraction="PyMuPDF and pdfplumber agree on every numerical fact on both pages")
    else:
        facts = json.loads(gzip.decompress(args.facts.read_bytes()))
    print(json.dumps(build(facts, args.output), indent=2))


if __name__ == "__main__":
    main()

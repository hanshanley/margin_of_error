"""Reproduce Armstrong's complete numerical facts without inventing provisional participation."""

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


INDEX = "https://www.co.armstrong.pa.us/index.php/resourses-m/election-results-unofficial-m"
TERMS = "https://www.co.armstrong.pa.us/index.php/about-m/terms-of-use-m"
SOURCE = "https://www.co.armstrong.pa.us/images/resources/electionresults/unofficial/totals.pdf"
SOURCE_HASHES = {
    "official-index.html": (INDEX, 174271, "ea645e1cce5a1402ef2c9189f607f2134742c66dd7ffc7e2a7c4f19a1e513a2f"),
    "official-terms.html": (TERMS, 150297, "dea41faa51d47e786d09a1fb6f46afdfa79c4ff09b822e36fb27e8d58de58c92"),
    "county-totals.pdf": (SOURCE, 177200, "da30e7287c77f051b791afe4ae6d2370309aeb5981d5c87a1959725ed930c6e7"),
}
OFFICES = (
    "GOVERNOR/LIEUTENANT GOVERNOR (Vote for 1)",
    "REPRESENTATIVE IN CONGRESS 15TH CONGRESSIONAL DISTRICT (Vote for 1)",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 60TH LEGISLATIVE DISTRICT (Vote for 1)",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 63TH DISTRICT (Vote for 1)",
)
MODES = ("Election Day", "Mail", "Provisional", "Total")
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
RATE = r"(?:N/A|\d+(?:\.\d+)?%)"
VECTOR = " ".join([NUMBER] * 4)
SUMMARY = "All Contests, All Districts, All Tabulators, Election Day, Mail"
STATUS = "2026 General Election Unofficial Results w/o PROV"
HEADER = "Candidate Party Election Day Mail Provisional Total"
REPORT_FACTS_SHA256 = "dc524a39ddbbe1493c5dfd4711e74359d0d36038a9f87d1587653264333c201a"
QUALIFICATIONS = [
    "Native participation is Voters Cast, not candidate selections: 24,039 = 20,853 Election Day + 3,186 Mail.",
    "The declared counting scope explicitly excludes provisionals. Provisional participation is absent, not zero; separate candidate provisional zeroes do not supply a participation denominator.",
    "Native registrations are 43,750 and printed turnout is 54.95%; the calculated registered-voter fraction is separate, not CVAP/VEP or demographic turnout.",
    "DEMOCRATIC and REPUBLICAN elector-group rows contain explicit zeroes and N/A turnout while county participation is positive. Preserve these rows, not measured party turnout or zero participation.",
    "Candidate party literals DEM, REP and LIB are separate from administrative elector groups, registrations and participation.",
    "Total Votes excludes the separately printed Unresolved Write-In row. Preserve both, without double-counting the subtotal.",
    "Only the governor and congressional contests cover the whole county; state-House district participation denominators are absent.",
    "Ballot-minus-selection differences remain unclassified; blanks, under/overvotes, pending ballots and precinct reporting counts are not supplied, not zero.",
    "Native update 11/3/2026 10:26:30 PM has no declared timezone. Unofficial is not certification or independently finished counting.",
    "County terms describe a supplementary public service with changeable information, not guaranteed completeness, currency or accuracy.",
    "No county/precinct map, demographic turnout or statewide completion approval. Source presentation templates remain private.",
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
    require(sum(result[:3]) == result[3], "Native mode vector does not reconcile")
    return result


def parse_participation(text):
    header = "Elector Group Counting Group Voters Cast Registered Voters Turnout "
    require(text.startswith(header), "Changed participation header")
    rest, rows = text[len(header):], []
    for group in ("DEMOCRATIC", "REPUBLICAN", "Total"):
        pattern = (rf"{re.escape(group)} Election Day ({NUMBER}) ({RATE}) "
                   rf"Mail ({NUMBER}) ({RATE}) Total ({NUMBER}) ({NUMBER}) ({RATE})(?: |$)")
        match = re.match(pattern, rest)
        require(match is not None, "Missing or changed native elector-group row")
        for mode, value, denominator, rate in (
            ("Election Day", match[1], None, match[2]),
            ("Mail", match[3], None, match[4]),
            ("Total", match[5], match[6], match[7]),
        ):
            rows.append(dict(elector_group_literal=group, counting_group_literal=mode,
                voters_cast_literal=value, registered_voters_literal=denominator,
                printed_turnout_literal=rate))
        rest = rest[match.end():]
    require(not rest, "Unconsumed participation facts")
    return rows


def parse_contest(office, text):
    inventory, separator, body = text.partition(" " + HEADER + " ")
    require(separator and inventory == ("DEM,REP,LIB" if office == OFFICES[0] else "DEM,REP"),
            "Changed literal party inventory or result header")
    for first, last in (("STACY GARRITY/JASON", "RICHEY"),
                        ("JOSH SHAPIRO/AUSTIN", "DAVIS"), ("KEN KRAWCHUK/JOHN", "THOMAS")):
        body = re.sub(rf"{re.escape(first)} ((?:REP|DEM|LIB) {VECTOR}) {last}(?= |$)",
                      lambda match: first + " " + last + " " + match[1], body)
    candidates, separator, tail = body.partition(" Total Votes ")
    require(separator, "Missing native candidate subtotal")
    rows = []
    while candidates:
        match = re.match(rf"(.+?) (REP|DEM|LIB) ({NUMBER}) ({NUMBER}) ({NUMBER}) ({NUMBER})(?: |$)",
                         candidates)
        require(match is not None, "Incomplete native candidate row")
        rows.append(dict(label_literal=match[1], party_literal=match[2],
            row_kind="candidate", count_literals=list(match.groups()[2:])))
        candidates = candidates[match.end():]
    match = re.fullmatch(rf"({NUMBER}) ({NUMBER}) ({NUMBER}) ({NUMBER}) "
        rf"Election Day Mail Provisional Total Unresolved Write-In "
        rf"({NUMBER}) ({NUMBER}) ({NUMBER}) ({NUMBER})", tail)
    require(match is not None, "Changed or incomplete subtotal/write-in facts")
    rows.append(dict(label_literal="Unresolved Write-In", party_literal="",
        row_kind="unresolved_write_in", count_literals=list(match.groups()[4:])))
    return dict(office_literal=office, native_party_inventory_literal=inventory,
        rows=rows, native_total_votes_literals=list(match.groups()[:4]))


def parse_pages(texts):
    require(len(texts) == 2, "Incomplete native report")
    pages = []
    for ordinal, source in enumerate(texts, 1):
        text = " ".join(source.split())
        match = re.match(rf"Page: {ordinal} of 2 ([\d/]+ [\d:]+ [AP]M) ", text)
        require(match is not None, "Changed page, timestamp or pagination")
        page = dict(page_number=ordinal, source_update_literal=match[1],
            declared_timezone=None, elector_group_participation=[], contests=[])
        text = text[match.end():]
        if ordinal == 1:
            identity = ("Election Summary Report General Election Armstrong County November 03, 2026 "
                        "Summary for: " + SUMMARY + " " + STATUS + " ")
            require(text.startswith(identity), "Changed election identity, county or counting scope")
            text = text[len(identity):]
            stats, separator, remainder = text.partition(OFFICES[0] + " ")
            require(separator, "Missing complete county participation section")
            page["elector_group_participation"] = parse_participation(stats.strip())
            text = OFFICES[0] + " " + remainder
        expected = OFFICES[:2] if ordinal == 1 else OFFICES[2:]
        for position, office in enumerate(expected):
            require(text.startswith(office + " "), "Missing or changed native contest scope")
            text = text[len(office) + 1:]
            if position == 0:
                body, separator, rest = text.partition(" " + expected[1] + " ")
                require(separator, "Incomplete second native contest")
                text = expected[1] + " " + rest
            else:
                body, text = text, ""
            page["contests"].append(parse_contest(office, body))
        require(not text, "Unconsumed report facts")
        pages.append(page)
    return dict(source_url=SOURCE, native_summary_scope_literal=SUMMARY,
        native_status_literal=STATUS, native_participation_measure_literal="Voters Cast", pages=pages)


def report_digest(report):
    return hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(facts):
    require(facts["schema"] == "armstrong-2026-complete-numerical-facts-v1", "Changed factual schema")
    require(set(facts["source_receipts"]) == set(SOURCE_HASHES), "Incomplete source receipts")
    for name, (url, size, digest) in SOURCE_HASHES.items():
        receipt = facts["source_receipts"][name]
        require(receipt["url"] == receipt["final_url"] == url and receipt["status"] == 200
            and receipt["bytes"] == size and receipt["sha256"] == digest, "Changed source provenance")
    report = facts["report"]
    require(report["source_url"] == SOURCE and report["native_summary_scope_literal"] == SUMMARY
        and report["native_status_literal"] == STATUS
        and report["native_participation_measure_literal"] == "Voters Cast", "Changed native report scope")
    require(len(report["pages"]) == 2, "Incomplete native pages")
    first, second = report["pages"]
    require(first["page_number"] == 1 and second["page_number"] == 2
        and not second["elector_group_participation"], "Changed native page scopes")
    groups = first["elector_group_participation"]
    require(len(groups) == 9, "Incomplete native participation groups")
    for index, row in enumerate(groups):
        require(row["elector_group_literal"] == ("DEMOCRATIC", "REPUBLICAN", "Total")[index // 3]
            and row["counting_group_literal"] == ("Election Day", "Mail", "Total")[index % 3],
            "Changed native participation inventory")
        integer(row["voters_cast_literal"])
        if index % 3 != 2:
            require(row["registered_voters_literal"] is None, "Invented mode registration")
        else:
            integer(row["registered_voters_literal"])
    require([integer(row["voters_cast_literal"]) for row in groups] == [0] * 6 + [20853, 3186, 24039]
        and groups[-1]["registered_voters_literal"] == "43,750"
        and groups[-1]["printed_turnout_literal"] == "54.95%", "Changed native participation")
    contests = [contest for page in report["pages"] for contest in page["contests"]]
    require([contest["office_literal"] for contest in contests] == list(OFFICES), "Incomplete contest scopes")
    for contest in contests:
        rows = contest["rows"]
        require(len(rows) == (4 if contest["office_literal"] == OFFICES[0] else 3)
            and rows[-1]["row_kind"] == "unresolved_write_in"
            and len({row["label_literal"] for row in rows}) == len(rows), "Incomplete native result inventory")
        vectors = [counts(row["count_literals"]) for row in rows]
        require([sum(vector[i] for vector in vectors[:-1]) for i in range(4)]
            == counts(contest["native_total_votes_literals"]), "Native candidate subtotal does not reconcile")
        if contest["office_literal"] in OFFICES[:2]:
            require(all(sum(vector[i] for vector in vectors) <= total
                for i, total in ((0, 20853), (1, 3186), (3, 24039))), "Selections exceed native county scope")
    require(report_digest(report) == REPORT_FACTS_SHA256, "Complete reviewed report facts changed")
    return facts


def build(facts, output):
    validate(facts)
    output.mkdir(parents=True, exist_ok=False)
    tables = {name: [] for name in ("county-participation.csv", "native-elector-group-participation.csv",
        "county-candidate-results.csv", "county-literal-party-totals.csv",
        "native-contest-subtotals.csv", "native-source-pages.csv", "county-contest-accounting.csv")}
    common = dict(year=2026, state_code="PA", county="Armstrong", source_url=SOURCE,
        native_summary_scope_literal=SUMMARY, native_status_literal=STATUS)
    participation = facts["report"]["pages"][0]["elector_group_participation"]
    election_day, mail, total = [integer(row["voters_cast_literal"]) for row in participation[-3:]]
    registrations = integer(participation[-1]["registered_voters_literal"])
    parties = Counter()
    for page in facts["report"]["pages"]:
        base = dict(**common, source_page=page["page_number"],
            source_update_literal=page["source_update_literal"], declared_timezone="")
        tables["native-source-pages.csv"].append(base)
        for native in page["elector_group_participation"]:
            tables["native-elector-group-participation.csv"].append(dict(**base,
                elector_group_literal=native["elector_group_literal"],
                counting_group_literal=native["counting_group_literal"],
                voters_cast_literal=native["voters_cast_literal"],
                registered_voters_literal=native["registered_voters_literal"],
                printed_turnout_literal=native["printed_turnout_literal"]))
        if page["elector_group_participation"]:
            native = page["elector_group_participation"]
            tables["county-participation.csv"].append(dict(**base,
                native_participation_measure_literal="Voters Cast", reported_voters_cast=total,
                election_day_voters_cast=election_day, mail_voters_cast=mail, provisional_voters_cast="",
                registered_voters=registrations, native_printed_turnout=native[-1]["printed_turnout_literal"],
                registered_turnout_percent=100 * total / registrations,
                native_elector_group_records_json=json.dumps(native, sort_keys=True),
                counting_qualifications_json=json.dumps(QUALIFICATIONS)))
        for contest in page["contests"]:
            scope = dict(**base, office_literal=contest["office_literal"],
                native_party_inventory_literal=contest["native_party_inventory_literal"])
            subtotal = dict(**scope, native_label_literal="Total Votes",
                native_count_literals_json=json.dumps(contest["native_total_votes_literals"]))
            subtotal.update(zip(MODES, counts(contest["native_total_votes_literals"])))
            tables["native-contest-subtotals.csv"].append(subtotal)
            selections = [0] * 4
            for native in contest["rows"]:
                values = counts(native["count_literals"])
                row = dict(**scope, label_literal=native["label_literal"], party_literal=native["party_literal"],
                    row_kind=native["row_kind"], native_count_literals_json=json.dumps(native["count_literals"]))
                row.update(zip(MODES, values))
                tables["county-candidate-results.csv"].append(row)
                selections = [a + b for a, b in zip(selections, values)]
                if native["row_kind"] == "candidate":
                    for mode, value in zip(MODES, values):
                        parties[contest["office_literal"], native["party_literal"], mode] += value
            for index, mode in enumerate(MODES):
                whole = contest["office_literal"] in OFFICES[:2] and mode != "Provisional"
                denominator = (election_day, mail, None, total)[index] if whole else None
                tables["county-contest-accounting.csv"].append(dict(**scope, mode_literal=mode,
                    candidate_selections_including_unresolved_write_in=selections[index],
                    native_contest_participation_denominator="",
                    reviewed_county_voters_cast_for_whole_county_scope_only=denominator,
                    unclassified_participation_minus_selection_residual=(
                        denominator - selections[index] if denominator is not None else ""),
                    native_under_or_overvote_classification=""))
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
    audit = dict(scope="Armstrong county; native Voters Cast; Election Day and Mail, excluding provisionals",
        maps_approved=False, demographic_turnout_approved=False, statewide_completion_approved=False,
        county_participation=tables["county-participation.csv"][0], qualifications=QUALIFICATIONS,
        table_rows={name: len(rows) for name, rows in tables.items()})
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "source-receipts.json").write_text(json.dumps(facts["source_receipts"], sort_keys=True, indent=2) + "\n")
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "checksums.json").write_text(json.dumps({path.name: dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(output.iterdir())}, indent=2) + "\n")
    target = output / "complete-armstrong-2026-numerical-facts-01.zip"
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
    links = {urljoin(INDEX, a["href"]) for a in parent.select("a[href]")}
    require({SOURCE, TERMS} <= links, "Government parent does not declare report and terms")
    require("November 03, 2026" in parent.get_text(" ", strip=True), "Missing declared election date")
    with fitz.open(directory / "county-totals.pdf") as doc:
        first = parse_pages([page.get_text(sort=True) for page in doc])
    with pdfplumber.open(directory / "county-totals.pdf") as doc:
        second = parse_pages([page.extract_text(x_tolerance=1, y_tolerance=.1) for page in doc.pages])
    require(first == second, "Independent PDF engines disagree on complete report facts")
    return dict(schema="armstrong-2026-complete-numerical-facts-v1", report=first,
        source_receipts=receipts,
        independent_extraction="PyMuPDF sorted text and pdfplumber coordinate-sensitive text agree on both complete pages")


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

"""Reproduce Jefferson's county participation query without reconstructing suppressed votes."""

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


INDEX = "https://www.jeffersoncountypa.gov/election-results/"
FINAL_INDEX = "https://www.jeffersoncountypa.gov/departments/commissioners/election-info/election-results/"
POLICY = "https://www.jeffersoncountypa.gov/privacy-policy/"
BASE = "https://www.jeffersoncountypa.gov/wp-content/uploads/2026/11/"
SUMMARY_FILE = "ElectionSummaryReportRPTPro.pdf"
STATEMENT_FILE = "StatementOfVotesCastRPTpro.pdf"
SOURCES = {
    "official-results-index.html": (INDEX, FINAL_INDEX, 91771,
        "19b97441588723640509c7a1ae6040a00d868f03b606352343079940601f1dd7"),
    "official-privacy-policy.html": (POLICY, POLICY, 92678,
        "4feeb35a0688c7d5771f40e9c4f067c22a261480b7b964fbdea02903cd304cd0"),
    SUMMARY_FILE: (BASE + SUMMARY_FILE, BASE + SUMMARY_FILE, 182183,
        "986feb9bbcbade1cba3b2c910bb16982a5e18c8a90b88793a941aaf2fb323b38"),
    STATEMENT_FILE: (BASE + STATEMENT_FILE, BASE + STATEMENT_FILE, 646763,
        "2b217a420f1918668bd4753f18dcc75b611fe6ee799c91a608ec324710bcee27"),
}
OFFICES = (
    "Governor and Lieutenant Governor (Vote for 1)",
    "Representative in Congress - 15th District (Vote for 1)",
    "Representative in the General Assembly - 66th District (Vote for 1)",
    "Representative in the General Assembly - 75th District (Vote for 1)",
)
MODES = ("Election Day", "Mail-In", "Provisional", "Total")
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
RATE = r"(?:N/A|\d+(?:\.\d+)?%)"
VECTOR = " ".join([f"({NUMBER})"] * 4)
MODE_HEADER = "Election Day Mail-In Provisional Total"
SUMMARY_SCOPE = "All Contests, All Districts, All Tabulators, All Counting Groups"
STATEMENT_SCOPE = "All Contests, All Districts, All Counting Groups"
FACTS_SHA256 = "731827b8a44811108b3602d309b6f910f1c653066516070c78a2c00905b8fb42"
FOOTERS = {
    20: (0, ("Shapiro/Davis", "Garrity/Richey")),
    21: (0, ("Krawchuk/Thomas", "Total Votes", "Unresolved Write-In")),
    34: (1, ("Ray Bilger", "Glenn GT Thompson", "Total Votes")),
    35: (1, ("Unresolved Write-In",)),
    48: (2, ("Lisa Gourley", "Brian Smith", "Total Votes")),
    49: (2, ("Unresolved Write-In",)),
    50: (3, ("Kim Kohlhepp", "Mike Armanini", "Total Votes")),
    51: (3, ("Unresolved Write-In",)),
}
QUALIFICATIONS = [
    "Native participation is Voters Cast: 15,205 = 13,052 Election Day + 2,114 Mail-In + 39 Provisional.",
    "Registered-voter participation uses the native 28,226 registrations; 53.87% is the printed fraction, not CVAP, VEP or demographic turnout.",
    "Summary mode registrations are absent, not zero. The statement separately repeats the whole electorate for each mode; do not sum repeated registrations.",
    "The 38 actual reporting units reconcile to county participation. The separate Cumulative zero/N/A container is retained, not an additional geographical unit.",
    "Each contest has its own native Times Cast and registration scope. The 66th and 75th district electorates partition the county; neither is whole-county participation.",
    "Total Votes excludes Unresolved Write-In. Preserve both, native literal parties and explicit zeroes; candidate votes are not turnout.",
    "Selection differences are unclassified accounting residuals, not supplied blanks, undervotes or overvotes.",
    "Act 88 received absentee/mail ballots are a separate receipt measure, not an addition to counted Mail-In voters.",
    "The full query covers both summary pages, all seven unit-participation pages, all 53 page identities and every native county candidate footer.",
    "Unit candidate pages 8-51 are not transcribed. Suppressed cells are not recovered by subtraction, reassigned or interpreted as zero.",
    "The two reports have different native update times and no declared timezone. Unofficial and 38 of 38 reporting do not establish certification or completed counting.",
    "County disclaimers restrict commercial use of source materials and reserve reproduction rights; no source HTML, PDF, templates or unit-candidate details are redistributed.",
    "No county/precinct geometry, demographic turnout, statewide completion or redistribution permission for original documents is approved.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(isinstance(value, str) and re.fullmatch(NUMBER, value), "Invalid native integer")
    return int(value.replace(",", ""))


def vector(values):
    require(isinstance(values, list) and len(values) == 4, "Incomplete native vector")
    result = [integer(value) for value in values]
    require(sum(result[:3]) == result[3], "Native mode vector does not reconcile")
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def page_header(source, ordinal, total):
    text = " ".join(source.split())
    match = re.match(rf"Page: {ordinal} of {total} ([\d/]+ [\d:]+ [AP]M) ", text)
    require(match is not None, "Changed page, timestamp or pagination")
    return dict(page_number=ordinal, source_update_literal=match[1], declared_timezone=None), text[match.end():]


def parse_contest(office, text):
    pattern = (rf"Precincts Reported: ({NUMBER}) of ({NUMBER}) \(({RATE})\) "
        rf"{MODE_HEADER} Times Cast {VECTOR} / ({NUMBER}) ({RATE}) "
        rf"Candidate Party {MODE_HEADER} ")
    match = re.match(pattern, text)
    require(match is not None, "Missing native contest participation or reporting scope")
    contest = dict(office_literal=office, reported_units_literal=match[1],
        total_units_literal=match[2], printed_reporting_literal=match[3],
        times_cast_literals=list(match.groups()[3:7]), registered_voters_literal=match[8],
        printed_turnout_literal=match[9], rows=[])
    body, separator, tail = text[match.end():].partition(" Total Votes ")
    require(separator, "Missing native candidate subtotal")
    while body:
        row = re.match(rf"(.+?) (DEM|REP|LIB) {VECTOR}(?: |$)", body)
        require(row is not None, "Incomplete candidate/party/mode row")
        contest["rows"].append(dict(label_literal=row[1], party_literal=row[2],
            row_kind="candidate", count_literals=list(row.groups()[2:])))
        body = body[row.end():]
    match = re.fullmatch(rf"{VECTOR} {MODE_HEADER} Unresolved Write-In {VECTOR}", tail)
    require(match is not None, "Changed subtotal or unresolved-write-in scope")
    contest["native_total_votes_literals"] = list(match.groups()[:4])
    contest["rows"].append(dict(label_literal="Unresolved Write-In", party_literal="",
        row_kind="unresolved_write_in", count_literals=list(match.groups()[4:])))
    return contest


def parse_summary(texts):
    require(len(texts) == 2, "Incomplete summary")
    pages = []
    for ordinal, source in enumerate(texts, 1):
        page, text = page_header(source, ordinal, 2)
        page.update(source_report="summary", source_url=BASE + SUMMARY_FILE,
                    participation=[], contests=[])
        if ordinal == 1:
            identity = ("Election Summary Report General Election JEFFERSON COUNTY November 03, 2026 "
                        f"Summary for: {SUMMARY_SCOPE} Unofficial Results ")
            require(text.startswith(identity), "Changed election identity or summary scope")
            text = text[len(identity):]
            pattern = (rf"Elector Group Counting Group Voters Cast Registered Voters Turnout Total "
                rf"Election Day ({NUMBER}) ({RATE}) Mail-In ({NUMBER}) ({RATE}) "
                rf"Provisional ({NUMBER}) ({RATE}) Total ({NUMBER}) ({NUMBER}) ({RATE}) "
                rf"Precincts Reported: ({NUMBER}) of ({NUMBER}) \(({RATE})\) "
                rf"Voters Cast: ({NUMBER}) of ({NUMBER}) \(({RATE})\) ")
            match = re.match(pattern, text)
            require(match is not None, "Incomplete native county participation")
            for mode, value, denominator, rate in (
                (MODES[0], match[1], None, match[2]), (MODES[1], match[3], None, match[4]),
                (MODES[2], match[5], None, match[6]), (MODES[3], match[7], match[8], match[9])):
                page["participation"].append(dict(mode_literal=mode, voters_cast_literal=value,
                    registered_voters_literal=denominator, printed_turnout_literal=rate))
            page["county_reporting"] = dict(reported_units_literal=match[10], total_units_literal=match[11],
                printed_reporting_literal=match[12], voters_cast_literal=match[13],
                registered_voters_literal=match[14], printed_turnout_literal=match[15])
            text = text[match.end():]
        expected = OFFICES[:2] if ordinal == 1 else OFFICES[2:]
        for position, office in enumerate(expected):
            require(text.startswith(office + " "), "Changed or missing native office")
            text = text[len(office) + 1:]
            if position == 0:
                body, separator, rest = text.partition(" " + expected[1] + " ")
                require(separator, "Missing complete second contest")
                text = expected[1] + " " + rest
            else:
                body, text = text, ""
            page["contests"].append(parse_contest(office, body))
        require(not text, "Unconsumed summary facts")
        pages.append(page)
    return pages


def parse_statement(texts, footer_panels):
    require(len(texts) == 51, "Incomplete statement")
    pages, units, rollups, footers = [], [], [], []
    row_pattern = " ".join(rf"{re.escape(mode)} ({NUMBER}) ({NUMBER}) ({RATE})" for mode in MODES)
    for ordinal, source in enumerate(texts, 1):
        page, text = page_header(source, ordinal, 51)
        page.update(source_report="statement", source_url=BASE + STATEMENT_FILE,
            reviewed_scope="unit participation" if ordinal <= 7 else "county footers and page identity only",
            native_privacy_notice_present="Insufficient Turnout to Protect Voter Privacy" in text)
        pages.append(page)
        if ordinal > 7:
            if ordinal in FOOTERS:
                office, labels = FOOTERS[ordinal]
                panels = [("Times Cast", "Registered Voters"), labels] if ordinal in (20, 34, 48, 50) else [labels]
                require(len(footer_panels[ordinal]) == len(panels), "Incomplete native panel inventory")
                for panel, source_panel in enumerate(footer_panels[ordinal]):
                    seen = Counter()
                    for match in re.finditer(rf"(Jefferson County - Total|Cumulative - Total) "
                                             rf"((?:{NUMBER}(?: |$))+)", " ".join(source_panel.split())):
                        native_label = match[1]
                        seen[native_label] += 1
                        values = match[2].split()
                        require(len(values) == len(panels[panel]), "Changed native county footer columns")
                        footers.extend(dict(source_page=ordinal, office_literal=OFFICES[office],
                            native_footer_label_literal=native_label, panel_ordinal=panel + 1,
                            repeat_ordinal=seen[native_label], label_literal=label, total_literal=value,
                            scope_kind="county" if native_label.startswith("Jefferson") else "nongeographical_container")
                            for label, value in zip(panels[panel], values))
                    require(seen == Counter({"Jefferson County - Total": 2, "Cumulative - Total": 1}),
                            "Missing or duplicated native footer scopes")
            continue
        if ordinal == 1:
            identity = ("Statement of Votes Cast General Election JEFFERSON COUNTY November 03, 2026 "
                        f"SOVC for: {STATEMENT_SCOPE} Unofficial Results ")
            require(text.startswith(identity), "Changed statement election or counting scope")
            text = text[len(identity):]
        header = "Registered Precinct Voters Cast % Turnout Voters "
        require(text.startswith(header), "Changed unit participation header")
        text = text[len(header):]
        if ordinal == 1:
            require(text.startswith("Jefferson County Jefferson County "), "Changed county container")
            text = text[len("Jefferson County Jefferson County "):]
        footer = re.search(r"(?:Jefferson County|Cumulative) - Total ", text)
        unit_text, tail = (text[:footer.start()].strip(), text[footer.start():]) if footer else (text, "")
        if ordinal == 6:
            require(tail.endswith(" Cumulative"), "Changed continued Cumulative heading")
            tail = tail[:-len(" Cumulative")]
        while unit_text:
            match = re.match(rf"(.+?) {row_pattern}(?: |$)", unit_text)
            require(match is not None, "Missing or incomplete native unit participation")
            rows = []
            for i, mode in enumerate(MODES):
                denominator, value, rate = match.groups()[1 + i * 3:4 + i * 3]
                rows.append(dict(mode_literal=mode, registered_voters_literal=denominator,
                    voters_cast_literal=value, printed_turnout_literal=rate))
            units.append(dict(source_page=ordinal, unit_literal=match[1],
                scope_kind="nongeographical_container" if match[1] == "Cumulative" else "native_reporting_unit",
                participation=rows))
            unit_text = unit_text[match.end():]
        while tail:
            match = re.match(rf"((?:Jefferson County|Cumulative) - Total) ({NUMBER}) ({NUMBER}) ({RATE})(?: |$)", tail)
            if match:
                label, denominator, value, rate = match.groups()
            else:
                match = re.match(rf"(Election Day|Mail-In|Provisional) ({NUMBER}) ({NUMBER}) ({RATE})(?: |$)", tail)
                require(match is not None and ordinal == 7, "Unconsumed native participation footer")
                label, denominator, value, rate = match.groups()
            rollups.append(dict(source_page=ordinal, label_literal=label,
                registered_voters_literal=denominator, voters_cast_literal=value,
                printed_turnout_literal=rate))
            tail = tail[match.end():]
    return dict(pages=pages, units=units, participation_rollups=rollups, county_candidate_footers=footers)


def validate(facts):
    require(facts["schema"] == "jefferson-2026-county-query-v1", "Changed query schema")
    require(set(facts["source_receipts"]) == set(SOURCES), "Incomplete source provenance")
    for name, (url, final, size, sha) in SOURCES.items():
        row = facts["source_receipts"][name]
        require((row["url"], row["final_url"], row["status"], row["bytes"], row["sha256"])
            == (url, final, 200, size, sha), "Changed source provenance")
    query = facts["query"]
    pages, statement = query["summary_pages"], query["statement"]
    require(len(pages) == 2 and len(statement["pages"]) == 51, "Incomplete native page inventory")
    require([p["source_update_literal"] for p in pages] == ["11/4/2026 3:47:13 PM"] * 2
        and [p["source_update_literal"] for p in statement["pages"]] == ["11/4/2026 3:47:52 PM"] * 51,
        "Changed native update")
    groups = pages[0]["participation"]
    require(len(groups) == 4 and [r["mode_literal"] for r in groups] == list(MODES)
        and [r["registered_voters_literal"] for r in groups] == [None] * 3 + ["28,226"],
        "Changed or invented native registration scope")
    county = vector([r["voters_cast_literal"] for r in groups])
    require(county == [13052, 2114, 39, 15205] and groups[-1]["printed_turnout_literal"] == "53.87%",
            "Changed native county participation")
    actual = [unit for unit in statement["units"] if unit["scope_kind"] == "native_reporting_unit"]
    require(len(actual) == 38 and len({u["unit_literal"] for u in actual}) == 38,
            "Missing or duplicated reporting-unit scope")
    cumulative = [u for u in statement["units"] if u["scope_kind"] == "nongeographical_container"]
    require(len(cumulative) == 1 and cumulative[0]["unit_literal"] == "Cumulative",
            "Changed Cumulative container")
    for unit in statement["units"]:
        rows = unit["participation"]
        require([r["mode_literal"] for r in rows] == list(MODES), "Missing native unit mode")
        vector([r["voters_cast_literal"] for r in rows])
        require(len({integer(r["registered_voters_literal"]) for r in rows}) == 1,
                "Changed repeated unit electorate")
        for row in rows:
            value, denominator = integer(row["voters_cast_literal"]), integer(row["registered_voters_literal"])
            rate = row["printed_turnout_literal"]
            require((denominator == 0 and value == 0 and rate == "N/A") or
                (denominator > 0 and value <= denominator and re.fullmatch(RATE, rate)
                 and rate != "N/A" and abs(float(rate[:-1]) - 100 * value / denominator) <= .011),
                "Native participation fraction does not reconcile")
    require([sum(integer(u["participation"][i]["voters_cast_literal"]) for u in actual)
        for i in range(4)] == county
        and sum(integer(u["participation"][-1]["registered_voters_literal"]) for u in actual) == 28226,
        "Unit participation does not reconcile to county")
    contests = [c for page in pages for c in page["contests"]]
    require([c["office_literal"] for c in contests] == list(OFFICES), "Incomplete contest scopes")
    for contest in contests:
        participation = vector(contest["times_cast_literals"])
        rows = contest["rows"]
        require(len(rows) == (4 if contest["office_literal"] == OFFICES[0] else 3)
            and rows[-1]["row_kind"] == "unresolved_write_in" and rows[-1]["party_literal"] == "",
            "Incomplete candidate/write-in inventory")
        values = [vector(row["count_literals"]) for row in rows]
        require([sum(v[i] for v in values[:-1]) for i in range(4)]
            == vector(contest["native_total_votes_literals"]), "Candidate subtotal does not reconcile")
        require(all(sum(v[i] for v in values) <= participation[i] for i in range(4)),
                "Selections exceed the native contest electorate")
    require(all(vector(c["times_cast_literals"]) == county
        and integer(c["registered_voters_literal"]) == 28226 for c in contests[:2]),
        "Whole-county contest denominators changed")
    require([sum(vector(c["times_cast_literals"])[i] for c in contests[2:]) for i in range(4)] == county
        and sum(integer(c["registered_voters_literal"]) for c in contests[2:]) == 28226,
        "State-House electorate partition does not reconcile")
    anchors = {}
    require(len(statement["county_candidate_footers"]) == 75, "Incomplete county/container footer anchors")
    for row in statement["county_candidate_footers"]:
        if row["scope_kind"] == "county":
            anchors.setdefault((row["office_literal"], row["label_literal"]), []).append(integer(row["total_literal"]))
        else:
            require(integer(row["total_literal"]) == 0, "Changed explicit Cumulative footer zero")
    for c in contests:
        expected = {r["label_literal"]: vector(r["count_literals"])[-1] for r in c["rows"]}
        expected["Total Votes"] = vector(c["native_total_votes_literals"])[-1]
        expected["Times Cast"] = vector(c["times_cast_literals"])[-1]
        expected["Registered Voters"] = integer(c["registered_voters_literal"])
        require(all(anchors.get((c["office_literal"], label)) == [value, value] for label, value in expected.items()),
                "Independent statement footer disagrees with summary")
    require(digest(query) == FACTS_SHA256, "Complete reviewed query facts changed")
    return facts


def build(facts, output):
    validate(facts)
    output.mkdir(parents=True, exist_ok=False)
    names = ("county-participation", "native-summary-participation", "native-unit-participation",
        "native-participation-rollups", "county-candidate-results", "county-literal-party-totals",
        "native-contest-subtotals", "county-contest-accounting", "native-source-pages",
        "native-county-candidate-footers", "native-mail-ballot-receipts")
    tables = {name + ".csv": [] for name in names}
    common = dict(year=2026, state_code="PA", county="Jefferson", native_status_literal="Unofficial Results")
    query, parties = facts["query"], Counter()
    all_pages = query["summary_pages"] + query["statement"]["pages"]
    for page in all_pages:
        tables["native-source-pages.csv"].append(dict(**common, **{k: v for k, v in page.items()
            if k not in ("participation", "contests", "county_reporting")}))
    for page in query["summary_pages"]:
        base = dict(**common, source_url=page["source_url"], source_page=page["page_number"],
            source_report="summary", source_update_literal=page["source_update_literal"], declared_timezone="")
        for row in page["participation"]:
            tables["native-summary-participation.csv"].append(dict(**base, **row))
        if page["participation"]:
            rows = page["participation"]
            tables["county-participation.csv"].append(dict(**base,
                native_participation_measure_literal="Voters Cast", reported_voters_cast=15205,
                election_day_voters_cast=13052, mail_voters_cast=2114, provisional_voters_cast=39,
                registered_voters=28226, native_printed_turnout=rows[-1]["printed_turnout_literal"],
                registered_turnout_percent=100 * 15205 / 28226, reported_units=38, total_units=38,
                native_summary_scope_literal=SUMMARY_SCOPE,
                counting_qualifications_json=json.dumps(QUALIFICATIONS)))
        for contest in page["contests"]:
            scope = dict(**base, office_literal=contest["office_literal"])
            subtotal = dict(**scope, native_label_literal="Total Votes",
                native_count_literals_json=json.dumps(contest["native_total_votes_literals"]))
            subtotal.update(zip(MODES, vector(contest["native_total_votes_literals"])))
            tables["native-contest-subtotals.csv"].append(subtotal)
            selections = [0] * 4
            for native in contest["rows"]:
                values = vector(native["count_literals"])
                row = dict(**scope, label_literal=native["label_literal"], party_literal=native["party_literal"],
                    row_kind=native["row_kind"], native_count_literals_json=json.dumps(native["count_literals"]))
                row.update(zip(MODES, values))
                tables["county-candidate-results.csv"].append(row)
                selections = [a + b for a, b in zip(selections, values)]
                if native["row_kind"] == "candidate":
                    for mode, value in zip(MODES, values):
                        parties[contest["office_literal"], native["party_literal"], mode] += value
            for i, mode in enumerate(MODES):
                native = vector(contest["times_cast_literals"])[i]
                tables["county-contest-accounting.csv"].append(dict(**scope, mode_literal=mode,
                    native_times_cast=native, native_registered_voters=integer(contest["registered_voters_literal"]),
                    native_printed_turnout=contest["printed_turnout_literal"] if mode == "Total" else "",
                    reported_units=integer(contest["reported_units_literal"]),
                    total_units=integer(contest["total_units_literal"]),
                    native_printed_reporting=contest["printed_reporting_literal"],
                    candidate_selections_including_unresolved_write_in=selections[i],
                    unclassified_participation_minus_selection_residual=native - selections[i],
                    native_under_or_overvote_classification=""))
    tables["county-literal-party-totals.csv"] = [dict(**common, office_literal=office,
        party_literal=party, mode_literal=mode, candidate_votes=value)
        for (office, party, mode), value in parties.items()]
    statement_base = dict(**common, source_url=BASE + STATEMENT_FILE, source_report="statement",
        source_update_literal="11/4/2026 3:47:52 PM", declared_timezone="")
    for unit in query["statement"]["units"]:
        for row in unit["participation"]:
            tables["native-unit-participation.csv"].append(dict(**statement_base,
                source_page=unit["source_page"], unit_literal=unit["unit_literal"],
                scope_kind=unit["scope_kind"], **row))
    for table, field in (("native-participation-rollups.csv", "participation_rollups"),
                         ("native-county-candidate-footers.csv", "county_candidate_footers")):
        tables[table] = [dict(**statement_base, **row) for row in query["statement"][field]]
    tables["native-mail-ballot-receipts.csv"] = [{**common, "source_url": FINAL_INDEX, **query["act88"]}]
    for name, rows in tables.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=sorted({k for row in rows for k in row}),
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / name).write_text(stream.getvalue())
    (output / "source-records.json.gz").write_bytes(gzip.compress(
        (json.dumps(facts, sort_keys=True, indent=2) + "\n").encode(), mtime=0))
    audit = dict(scope="Jefferson complete county/aggregate query, not unit candidate results",
        maps_approved=False, demographic_turnout_approved=False, statewide_completion_approved=False,
        county_participation=tables["county-participation.csv"][0], qualifications=QUALIFICATIONS,
        table_rows={name: len(rows) for name, rows in tables.items()})
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "source-receipts.json").write_text(json.dumps(facts["source_receipts"], sort_keys=True, indent=2) + "\n")
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "checksums.json").write_text(json.dumps({path.name: dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(output.iterdir())}, indent=2) + "\n")
    target = output / "complete-jefferson-2026-county-query-01.zip"
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

    receipt_names = {"official-results-index.html": "source-receipt.json",
        "official-privacy-policy.html": "privacy-policy-receipt.json"}
    receipts = {row["file"]: {k: v for k, v in row.items() if k != "file"}
                for row in json.loads((directory / "report-receipts.json").read_text())}
    receipts.update({name: json.loads((directory / receipt).read_text())
                     for name, receipt in receipt_names.items()})
    for name in SOURCES:
        body = (directory / name).read_bytes()
        require(receipts[name]["bytes"] == len(body)
            and receipts[name]["sha256"] == hashlib.sha256(body).hexdigest(), "Source receipt disagrees with bytes")
    parent = BeautifulSoup((directory / "official-results-index.html").read_bytes(), "html.parser")
    links = {urljoin(FINAL_INDEX, a["href"]) for a in parent.select("a[href]")}
    require({BASE + SUMMARY_FILE, BASE + STATEMENT_FILE, POLICY} <= links, "Undeclared county reports or policy")
    text = parent.get_text(" ", strip=True)
    require("2026 General Election Unofficial Results" in text, "Changed parent election scope")
    match = re.search(r"Absentee and Mail-In Ballots which were received by Jefferson County by "
                      r"(8:00 PM on November 3, 2026) is: (\d+)", text)
    require(match is not None, "Missing Act 88 native receipt measure")
    extracted = []
    for engine in ("pymupdf", "pdfplumber"):
        reports = {}
        for name, parse in ((SUMMARY_FILE, parse_summary), (STATEMENT_FILE, parse_statement)):
            if engine == "pymupdf":
                with fitz.open(directory / name) as doc:
                    texts = [p.get_text(sort=True) for p in doc]
                    # The engines order side-by-side panels differently; compare native panels separately.
                    panels = {n: [doc[n - 1].get_text(sort=True, clip=fitz.Rect(x, 0, right, 612))
                        for x, right in ((0, 396), (396, 792))[:2 if n in (20, 34, 48, 50) else 1]]
                        for n in FOOTERS} if name == STATEMENT_FILE else None
            else:
                with pdfplumber.open(directory / name) as doc:
                    texts = [p.extract_text(x_tolerance=1, y_tolerance=.1) for p in doc.pages]
                    panels = {n: [doc.pages[n - 1].crop((x, 0, right, 612)).extract_text(
                        x_tolerance=1, y_tolerance=.1)
                        for x, right in ((0, 396), (396, 792))[:2 if n in (20, 34, 48, 50) else 1]]
                        for n in FOOTERS} if name == STATEMENT_FILE else None
            reports[name] = parse(texts, panels) if name == STATEMENT_FILE else parse(texts)
        extracted.append(dict(summary_pages=reports[SUMMARY_FILE], statement=reports[STATEMENT_FILE],
            act88=dict(measure_kind="received_absentee_and_mail_in_ballots",
                count_literal=match[2], native_deadline_literal=match[1], declared_timezone=None,
                native_status_literal="unofficial", counting_measure=False)))
    require(extracted[0] == extracted[1], "Independent PDF engines disagree on reviewed query")
    return dict(schema="jefferson-2026-county-query-v1", query=extracted[0], source_receipts=receipts,
        independent_extraction="PyMuPDF and pdfplumber agree on both complete summary pages, seven unit-participation pages, all 53 page identities and all 75 native county/container footer values, including repeated county footers")


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

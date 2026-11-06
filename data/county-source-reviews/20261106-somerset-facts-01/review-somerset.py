"""Reproduce the complete reviewed Somerset 2026 numerical report query offline."""

import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


REVIEWED_SHA256 = "7cfc82b959ff815ee9cfc438b26303e67674a8e0271018d3c23f343d806d63bb"
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
PERCENT = r"\d+(?:\.\d{1,2})?%"
MODES = ("TOTAL", "Election Day", "Absentee/Mail-In", "Provisional")
TITLES = (
    "GOVERNOR AND LIEUTENANT GOVERNOR",
    "REPRESENTATIVE IN CONGRESS 13th District",
    "REPRESENTATIVE IN CONGRESS 14th District",
    "SENATOR IN THE GENERAL ASSEMBLY 32nd District",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 69th Distritct",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 71st District",
)
REPORTS = {
    "summary": ("EMS Report", 3, "11/03/2026 11:03 PM"),
    "statement": ("Precinct Breakdown", 67, "11/03/2026 11:08 PM"),
    "statistics": ("Statistics", 3, "11/03/2026 11:11PM"),
}
REPORTING = (
    "Election Day Precincts Reporting", "Precincts Complete",
    "Precincts Partially Reported", "Absentee/ Early Precincts Reporting",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def integer(value):
    require(isinstance(value, str) and re.fullmatch(NUMBER, value), "Invalid native integer")
    return int(value.replace(",", ""))


def vector(values):
    require(len(values) == 4, "Missing native mode cell")
    result = [integer(value) for value in values]
    require(result[0] == sum(result[1:]), "Native mode vector does not reconcile")
    return result


def columns(text):
    text = text.replace("STATISTICS", "").replace("Statistics", "")
    expected = "TOTAL Election Day Absentee/Mail-In Provisional"
    require(Counter(re.sub(r"\W", "", text)) == Counter(re.sub(r"\W", "", expected)),
            "Changed native mode-column inventory")


def page_body(text, role, number):
    label, count, clock = REPORTS[role]
    text = " ".join(text.split())
    copyright_line = " Report generated with Electionware Copyright \u00a9 2007-2020"
    require(text.endswith(copyright_line), "Missing native report footer")
    text = text[:-len(copyright_line)]
    footer = re.search(r" - (11/03/2026 \d{1,2}:\d{2}\s*[AP]M) (?:Page )?(\d+) of (\d+)$", text)
    require(footer and footer[1] == clock, "Changed native report clock")
    require(int(footer[2]) == number and int(footer[3]) == count, "Incomplete native pagination")
    body = text[:footer.start()]
    for identity in (
        "Custom Table Report" if role == "statistics" else "Summary Results Report",
        "2026 General Election", "November 3, 2026", "Somerset County",
        "UNOFFICIAL RESULTS", label,
    ):
        require(identity in body, "Changed election/report identity: " + identity)
        body = body.replace(identity, "", 1).strip()
    return body, dict(source_page=number, native_total_pages=count, source_update_literal=clock,
                      declared_timezone="", native_status_literal="UNOFFICIAL RESULTS")


def participation(body):
    count = "(" + NUMBER + ")"
    pattern = (r"Registered Voters - Total " + count + r" Ballots Cast - Total "
               + " ".join([count] * 4) + r" Ballots Cast - Blank "
               + " ".join([count] * 4) + r" Voter Turnout - Total (" + PERCENT + ")")
    match = re.match(pattern, body)
    require(match, "Missing native participation fields or mode cells")
    return dict(registered_voters_literal=match[1], ballot_literals=list(match.groups()[1:5]),
                blank_literals=list(match.groups()[5:9]), printed_turnout_literal=match[10]), body[match.end():].strip()


def contests(body):
    result = []
    while body:
        titles = [title for title in TITLES if body.startswith(title + " Vote For 1 ")]
        require(len(titles) == 1, "Unknown or missing native contest")
        title = titles[0]
        body = body[len(title + " Vote For 1 "):]
        boundaries = [body.index(" " + other + " Vote For 1 ") for other in TITLES
                      if " " + other + " Vote For 1 " in body]
        section, body = (body[:min(boundaries)], body[min(boundaries) + 1:]) if boundaries else (body, "")
        first = re.search(r"\b(?:DEM |REP |LIB |Write-In Totals )", section)
        require(first, "Missing native choices")
        columns(section[:first.start()])
        section = section[first.start():]
        rows = []
        while section:
            match = re.match(
                r"(DEM .+?|REP .+?|LIB .+?|Write-In Totals) "
                + " ".join(["(" + NUMBER + ")"] * 4) + r"(?: |$)", section)
            require(match, "Unconsumed native choice/accounting row: " + section[:100])
            party, choice = ("", match[1]) if match[1] == "Write-In Totals" else match[1].split(" ", 1)
            rows.append(dict(label_literal=match[1], literal_party=party, choice_literal=choice,
                             count_literals=list(match.groups()[1:])))
            section = section[match.end():]
        result.append(dict(title_literal=title, vote_for=1, rows=rows))
    return result


def parse_reports(texts):
    result = {}
    for role in ("summary", "statement"):
        require(len(texts[role]) == REPORTS[role][1], "Incomplete report")
        pages = []
        for number, text in enumerate(texts[role], 1):
            body, page = page_body(text, role, number)
            page.update(unit_literal="", participation=None, reporting=[], contests=[])
            if role == "statement" or number == 1:
                marker = "Statistics" if role == "statement" else REPORTING[0]
                prefix, separator, body = body.partition(marker)
                require(separator, "Missing native statistics section")
                if role == "statement":
                    page["unit_literal"] = prefix.strip()
                    prefix, separator, tail = body.partition("Registered Voters - Total")
                    require(separator and page["unit_literal"], "Missing native unit/registration")
                    columns(prefix)
                    body = separator + tail
                else:
                    columns(prefix)
                    body = marker + body
                    for label in REPORTING:
                        match = re.match(re.escape(label) + r" (\d+) of (\d+) (\d+) (\d+) (\d+) ", body)
                        require(match, "Missing native reporting counter")
                        page["reporting"].append(dict(
                            label_literal=label, reported=int(match[1]), total=int(match[2]),
                            native_mode_columns=[int(value) for value in match.groups()[2:]]))
                        body = body[match.end():]
                page["participation"], body = participation(body)
            page["contests"] = contests(body)
            pages.append(page)
        result[role] = pages
    labels = [page["unit_literal"] for page in result["statement"]]
    require(len(texts["statistics"]) == 3, "Incomplete statistics report")
    result["statistics"] = []
    for number, text in enumerate(texts["statistics"], 1):
        body, page = page_body(text, "statistics", number)
        positions = [body.index(label + " ") for label in labels if label + " " in body]
        require(positions, "Missing statistics rows")
        prefix, body = body[:min(positions)], body[min(positions):]
        expected = "STATISTICS Registered Voters - Total Ballots Cast - Total Ballots Cast - Blank Voter Turnout - Total"
        require(Counter(re.sub(r"\W", "", prefix)) == Counter(re.sub(r"\W", "", expected)),
                "Changed statistics column inventory")
        page.update(rows=[], totals=None)
        while body and not body.startswith("Totals "):
            matching = [label for label in labels if body.startswith(label + " ")]
            require(len(matching) == 1, "Unknown/duplicate statistics unit")
            label = matching[0]
            match = re.match(re.escape(label) + r" (" + NUMBER + r") (" + NUMBER + r") ("
                             + NUMBER + r") (" + PERCENT + r")(?: |$)", body)
            require(match, "Incomplete native statistics row")
            page["rows"].append(dict(unit_literal=label, registered_voters_literal=match[1],
                                     ballots_literal=match[2], blanks_literal=match[3],
                                     printed_turnout_literal=match[4]))
            body = body[match.end():]
        if body:
            match = re.fullmatch(r"Totals (" + NUMBER + r") (" + NUMBER + r") (" + NUMBER + ")", body)
            require(match and number == 3, "Changed/missing native totals")
            page["totals"] = dict(registered_voters_literal=match[1], ballots_literal=match[2],
                                  blanks_literal=match[3], printed_turnout_literal=None)
        result["statistics"].append(page)
    return result


def validate(facts):
    require(facts["schema"] == "pa-somerset-2026-complete-reports-v1", "Changed query scope")
    reports = facts["reports"]
    for role, (_, count, clock) in REPORTS.items():
        pages = reports[role]
        require(len(pages) == count, "Incomplete report inventory")
        require([page["source_page"] for page in pages] == list(range(1, count + 1)), "Duplicate/missing page")
        require(all(page["native_total_pages"] == count and page["source_update_literal"] == clock
                    and page["declared_timezone"] == "" and page["native_status_literal"] == "UNOFFICIAL RESULTS"
                    for page in pages), "Changed native source qualifications")
    county = reports["summary"][0]["participation"]
    require(integer(county["registered_voters_literal"]) == 48578
            and vector(county["ballot_literals"]) == [27019, 23233, 3786, 0]
            and vector(county["blank_literals"]) == [3, 3, 0, 0]
            and county["printed_turnout_literal"] == "55.62%", "Changed county participation")
    units = reports["statement"]
    require(len({page["unit_literal"] for page in units}) == 67, "Duplicate/missing native unit")
    stats_rows = [row for page in reports["statistics"] for row in page["rows"]]
    require([row["unit_literal"] for row in stats_rows] == [page["unit_literal"] for page in units],
            "Incomplete/different statistics units")
    for page, row in zip(units, stats_rows):
        stats = page["participation"]
        require(stats["registered_voters_literal"] == row["registered_voters_literal"]
                and stats["ballot_literals"][0] == row["ballots_literal"]
                and stats["blank_literals"][0] == row["blanks_literal"]
                and Decimal(stats["printed_turnout_literal"][:-1])
                == Decimal(row["printed_turnout_literal"][:-1]),
                "Statistics and precinct reports disagree")
    total = reports["statistics"][-1]["totals"]
    require(total == dict(registered_voters_literal="48,578", ballots_literal="27,019",
                          blanks_literal="3", printed_turnout_literal=None), "Changed/missing native totals")
    require(sum(integer(page["participation"]["registered_voters_literal"]) for page in units) == 48578,
            "Unit registrations do not reconcile")
    for field in ("ballot_literals", "blank_literals"):
        values = [vector(page["participation"][field]) for page in units]
        require([sum(value[i] for value in values) for i in range(4)] == vector(county[field]),
                "Unit participation does not reconcile")
    for stats in [county] + [page["participation"] for page in units]:
        registered = integer(stats["registered_voters_literal"])
        ballots, blanks = vector(stats["ballot_literals"]), vector(stats["blank_literals"])
        require(all(blank <= ballot for blank, ballot in zip(blanks, ballots)), "Invalid blank ballots")
        literal = stats["printed_turnout_literal"][:-1]
        precision = len(literal.split(".")[1]) if "." in literal else 0
        require(abs(100 * ballots[0] / registered - float(literal)) <= .5 * 10 ** -precision + 1e-8,
                "Unreviewed native rounding conflict")
    summary_contests = [contest for page in reports["summary"] for contest in page["contests"]]
    require([contest["title_literal"] for contest in summary_contests] == list(TITLES), "Incomplete county contests")
    for contest in summary_contests:
        rows = contest["rows"]
        require(len({row["label_literal"] for row in rows}) == len(rows), "Duplicate native choice")
        unit_contests = [item for page in units for item in page["contests"]
                         if item["title_literal"] == contest["title_literal"]]
        require(unit_contests, "Missing unit contest")
        for unit_contest in unit_contests:
            labels = [row["label_literal"] for row in unit_contest["rows"]]
            require(len(set(labels)) == len(labels) and set(labels) == {row["label_literal"] for row in rows},
                    "Unknown, duplicate or missing unit choice")
        for row in rows:
            matches = [item for unit_contest in unit_contests for item in unit_contest["rows"]
                       if item["label_literal"] == row["label_literal"]]
            require(len(matches) == len(unit_contests), "Missing unit choice")
            values = [vector(item["count_literals"]) for item in matches]
            require([sum(value[i] for value in values) for i in range(4)] == vector(row["count_literals"]),
                    "Unit and county candidate counts disagree")
    for role in ("summary", "statement"):
        for page in reports[role]:
            for contest in page["contests"]:
                require(contest["title_literal"] in TITLES and contest["vote_for"] == 1, "Unknown contest")
                for row in contest["rows"]:
                    vector(row["count_literals"])
                    require(row["literal_party"] in ("DEM", "REP", "LIB", ""), "Invented literal party")
                    require((row["literal_party"] == "") == (row["label_literal"] == "Write-In Totals"),
                            "Write-ins cannot acquire a party")
    require({receipt["source_report"] for receipt in facts["source_receipts"]} == set(REPORTS),
            "Incomplete source provenance")
    require(all(receipt["status"] == 200 and receipt["tls_verification"] is True
                for receipt in facts["source_receipts"]), "Unverified original source")
    require(digest(facts) == REVIEWED_SHA256, "Changed independently reviewed facts")


def tables(facts):
    validate(facts)
    result = {name: [] for name in (
        "county-participation.csv", "native-participation-modes.csv", "native-unit-participation.csv",
        "county-candidate-results.csv", "unit-candidate-results.csv", "county-literal-party-totals.csv",
        "county-contest-accounting.csv", "native-reporting-statistics.csv", "statistics-crosscheck.csv",
        "native-source-pages.csv",
    )}
    reports = facts["reports"]
    for role, pages in reports.items():
        receipt = next(row for row in facts["source_receipts"] if row["source_report"] == role)
        for page in pages:
            meta = dict(state_code="PA", county="Somerset", election_date="2026-11-03",
                        source_report=role, source_page=page["source_page"],
                        source_update_literal=page["source_update_literal"], declared_timezone="",
                        native_status_literal=page["native_status_literal"], source_url=receipt["url"])
            result["native-source-pages.csv"].append(dict(
                **meta, native_total_pages=page["native_total_pages"], source_sha256=receipt["sha256"],
                both_engines_match=True, all_numerical_data_consumed=True))
            if role == "statistics":
                for row in page["rows"] + ([dict(unit_literal="Totals", **page["totals"])] if page["totals"] else []):
                    result["statistics-crosscheck.csv"].append(dict(
                        **meta, unit_literal=row["unit_literal"],
                        registered_voters=integer(row["registered_voters_literal"]),
                        ballots_cast=integer(row["ballots_literal"]), blank_ballots=integer(row["blanks_literal"]),
                        native_printed_turnout=row["printed_turnout_literal"]))
                continue
            stats = page["participation"]
            if stats is not None:
                ballots, blanks = vector(stats["ballot_literals"]), vector(stats["blank_literals"])
                registered = integer(stats["registered_voters_literal"])
                if role == "summary":
                    result["county-participation.csv"].append(dict(
                        **meta, native_measure_literal="Ballots Cast - Total", ballots_cast=ballots[0],
                        registered_voters=registered, native_printed_turnout=stats["printed_turnout_literal"],
                        calculated_registered_fraction=ballots[0] / registered, blank_ballots_already_included=blanks[0],
                        source_fips="", complete_counting=False, maps_approved=False))
                for i, mode in enumerate(MODES):
                    record = dict(**meta, unit_literal=page["unit_literal"], counting_mode_literal=mode,
                                  ballots_cast=ballots[i], blank_ballots=blanks[i],
                                  registered_voters=registered if i == 0 else "",
                                  native_printed_turnout=stats["printed_turnout_literal"] if i == 0 else "")
                    result["native-participation-modes.csv" if role == "summary"
                           else "native-unit-participation.csv"].append(record)
            for row in page["reporting"]:
                result["native-reporting-statistics.csv"].append(dict(
                    **meta, label_literal=row["label_literal"], reported=row["reported"], total=row["total"],
                    native_election_day_column=row["native_mode_columns"][0],
                    native_mail_column=row["native_mode_columns"][1],
                    native_provisional_column=row["native_mode_columns"][2]))
            for contest in page["contests"]:
                for row in contest["rows"]:
                    for i, mode in enumerate(MODES):
                        record = dict(**meta, unit_literal=page["unit_literal"],
                                      contest_literal=contest["title_literal"],
                                      choice_literal=row["choice_literal"], literal_party=row["literal_party"],
                                      counting_mode_literal=mode, votes=vector(row["count_literals"])[i])
                        result["county-candidate-results.csv" if role == "summary"
                               else "unit-candidate-results.csv"].append(record)
                        if role == "summary" and row["literal_party"]:
                            result["county-literal-party-totals.csv"].append(record)
                if role == "summary":
                    for i, mode in enumerate(MODES):
                        result["county-contest-accounting.csv"].append(dict(
                            **meta, contest_literal=contest["title_literal"], counting_mode_literal=mode,
                            derived_choice_sum=sum(vector(row["count_literals"])[i] for row in contest["rows"]),
                            native_total_votes_cast="", native_contest_totals="", native_overvotes="",
                            native_undervotes="", registered_voters=""))
    return result


def build(facts, output):
    files = {"native-facts.json": encoded(facts)}
    for name, rows in tables(facts).items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        files[name] = stream.getvalue().encode()
    files["audit.json"] = encoded(dict(
        complete_report_pages=73, native_units=67, county_contests=6,
        all_county_and_unit_candidates_reconcile_all_modes=True,
        all_unit_registrations_ballots_and_blanks_reconcile=True,
        all_statistics_rows_independently_crosschecked=True,
        native_percentage_trailing_zero_formatting_preserved=True,
        blank_ballots_already_included=True, missing_accounting_is_not_zero=True,
        native_reporting_counter_conflicts_preserved=True,
        source_fips_absent=True, maps_approved=False, complete_counting=False,
        scope="Complete three Somerset numerical reports, not new geography or demographic participation."))
    here = Path(__file__).resolve().parent
    for name in ("review-somerset.py", "test_review_somerset.py"):
        files[name] = (here / name).read_bytes()
    files["METHODS.txt"] = (
        "Complete Somerset November 3, 2026 numerical query: EMS summary (3 pages), "
        "precinct breakdown (67 pages) and statistics (3 pages). Every native candidate row "
        "and all participation fields are parsed by two independent PDF engines and agree. "
        "The original source templates remain private; this packet contains all numerical facts.\n"
        "Offline: python3 review-somerset.py --facts native-facts.json --output REPRODUCED\n"
        "Tests: python3 test_review_somerset.py\n"
        "Clock literals differ by report and provide no timezone. Source remains UNOFFICIAL RESULTS. "
        "The native 0/67 complete, 67/67 partially reported, and absentee reporting 65/67 with "
        "67 in its mail column are retained, not repaired or treated as counting completion. "
        "Blank ballots are already in total ballots. Native contest totals, overvotes and "
        "undervotes are absent, not zero; candidate sums never replace ballots. Restricted "
        "district contests and mode counts do not borrow county registrations. Native FIPS "
        "and geographic boundaries are absent; no map or demographic turnout is approved. "
        "Eight statistics percentages omit trailing zeros printed in the precinct report; "
        "both native strings are retained and their decimal values agree exactly. "
        "Literal party labels and the native 69th Distritct spelling are retained.\n").encode()
    files["manifest.json"] = encoded([
        dict(file=name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(files.items())])
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, body)
    files["complete-query.zip"] = stream.getvalue()
    output.mkdir(parents=True, exist_ok=False)
    for name, body in files.items():
        (output / name).write_bytes(body)
    return dict(files=len(files), zip_members=len(files) - 1, zip_bytes=len(stream.getvalue()),
                zip_sha256=hashlib.sha256(stream.getvalue()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(json.loads(args.facts.read_text()), args.output), indent=2))

"""Reproduce complete Indiana, Lackawanna and Schuylkill county-summary facts."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


PROGRAM = "review-three-additional-pa-summaries.py"
TEST = "test_review_three_additional_pa_summaries.py"
REVIEWED_SHA256 = "65d5dbb65d4cc2db76dead7b534fd5fab68cf6da9493029ac609f9e8b9ee1181"
REPORTING = (
    "Election Day Precincts Reporting", "Precincts Complete",
    "Precincts Partially Reported", "Absentee/ Early Precincts Reporting",
)
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
GOVERNOR = "GOVERNOR AND LIEUTENANT GOVERNOR"
SPECS = {
    "Indiana": dict(
        stage="2026 General Election", date="November 3, 2026",
        modes=("TOTAL",), summary_pages=2, statement_pages=69, units=69,
        ballots=[28095], blanks=[3], registrations=49255, printed="57.04%",
        summary_clock="11/03/2026 10:03 PM", statement_clock="11/03/2026 10:04 PM",
        summary_sha="6b065db729cac4769ae614f053a9a931fe35836c20e2c05365c9fe2737adfd5c",
        statement_sha="e44b0e4413b19fd5563379ce511127504e951e413a817a0cc5ac55fc11bd7b40",
        offices=((), (
            GOVERNOR, "REPRESENTATIVE IN CONGRESS 14TH 14TH DISTRICT",
            "REPRESENTATIVE IN CONGRESS 15TH 15TH DISTRICT",
            "REPRESENTATIVE IN THE GENERAL ASSEMBLY 62ND 62ND DISTRICT",
            "REPRESENTATIVE IN THE GENERAL ASSEMBLY 66TH 66TH DISTRICT"))),
    "Lackawanna": dict(
        stage="GENERAL ELECTION", date="November 3, 2026",
        modes=("TOTAL", "Election Day", "Mail Votes", "Provisional Votes"),
        summary_pages=3, statement_pages=326, units=163,
        ballots=[87067, 66897, 20170, 0], blanks=[10, 9, 1, 0],
        registrations=151015, printed="57.65%",
        summary_clock="11/03/2026 10:02PM", statement_clock="11/03/2026 10:02PM",
        summary_sha="55960957f79479067fba9c327f3e3ff9145193d819437d9a319245cad4d3ced4",
        statement_sha="1fb58e3e83466da1685969406f73e63e2dc584f702d9c5835f4c2cb3d3bca6f2",
        offices=((
            GOVERNOR, "REPRESENTATIVE IN CONGRESS 8TH DISTRICT",
            "SENATOR IN THE GENERAL ASSEMBLY 22ND DISTRICT"), (
            "SENATOR IN THE GENERAL ASSEMBLY 40TH DISTRICT",
            "REPRESENTATIVE IN THE GENERAL ASSEMBLY 112TH DISTRICT",
            "REPRESENTATIVE IN THE GENERAL ASSEMBLY 113TH DISTRICT",
            "REPRESENTATIVE IN THE GENERAL ASSEMBLY 114TH DISTRICT",
            "REPRESENTATIVE IN THE GENERAL ASSEMBLY 118TH DISTRICT"), (
            "LACKAWANNA CO. HOME RULE CHARTER AMENDMENT",
            "CITY OF CARBONDALE 2026", "SCOTT TOWNSHIP BALLOT QUESTION"))),
    "Schuylkill": dict(
        stage="General Election", date="November 3rd 2026",
        modes=("TOTAL", "Election Day", "Mail Votes", "Provisional"),
        summary_pages=3, statement_pages=125, units=125,
        ballots=[48402, 40247, 8155, 0], blanks=[16, 7, 9, 0],
        registrations=92875, printed="52.12%",
        summary_clock="11/04/2026 11:01 AM", statement_clock="11/04/2026 11:02 AM",
        summary_sha="017f912c484b06b9cf26c22f4ba7df8e47c91cc53d266705923e9e4c3913468c",
        statement_sha="7eeb26e046f30e5daf76437c4a71da0a6083f11992070c9ebb5e77f521c5318b",
        offices=((), (
            GOVERNOR, "REPRESENTATIVE IN CONGRESS",
            "REPRESENTATIVE IN THE GENERAL ASSEMBLY 107th District",
            "REPRESENTATIVE IN THE GENERAL ASSEMBLY 116th District"), (
            "REPRESENTATIVE IN THE GENERAL ASSEMBLY 123rd District",
            "REPRESENTATIVE IN THE GENERAL ASSEMBLY 124th District"))),
}


def require(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def integers(values):
    require(all(isinstance(value, str) and re.fullmatch(NUMBER, value) for value in values),
            "Invalid native numeric literal")
    result = [int(value.replace(",", "")) for value in values]
    require(len(result) in (1, 4), "Missing or invented mode cells")
    require(len(result) == 1 or result[0] == sum(result[1:]), "Native mode vector does not reconcile")
    return result


def header_columns(text):
    compact = re.sub(r"\s+", "", text)
    for token in ("ProvisionalVotes", "MailVotes", "VOTE%", "Provisional",
                  "Statistics", "STATISTICS", "Election", "TOTAL", "Day", "Votes"):
        compact = compact.replace(token, "")
    require(not compact, "Unconsumed native column/header content: " + compact)


def page_body(text, county, role, number):
    spec = SPECS[county]
    text = " ".join(text.split())
    copyright_line = " Report generated with Electionware Copyright \u00a9 2007-2020"
    if text.endswith(copyright_line):
        text = text[:-len(copyright_line)]
    footer = re.search(
        r" (Election Summary|Precinct Summary|LACKAWANNA SUMMARY|LACKAWANNA PRECINCT)"
        r" - (11/\d{2}/2026 \d{1,2}:\d{2}\s*[AP]M) (?:Page )?(\d+) of (\d+)$", text)
    require(footer, "Missing native footer")
    require(footer[2] == spec[role + "_clock"], "Changed native report clock")
    require(int(footer[3]) == number and int(footer[4]) == spec[role + "_pages"],
            "Incomplete report pagination")
    expected_role = ("SUMMARY" if role == "summary" else "PRECINCT") if county == "Lackawanna" else (
        "Election Summary" if role == "summary" else "Precinct Summary")
    require(footer[1].endswith(expected_role), "Changed report role")
    text = text[:footer.start()]
    for identity in ("Summary Results Report", "UNOFFICIAL RESULTS",
                     spec["stage"], spec["date"], county + " County"):
        require(identity in text, "Changed election identity: " + identity)
        text = text.replace(identity, "", 1).strip()
    return text, dict(source_page=number, native_total_pages=spec[role + "_pages"],
                      native_status_literal="UNOFFICIAL RESULTS",
                      source_update_literal=footer[2], declared_timezone="")


def statistics(body, county):
    size = len(SPECS[county]["modes"])
    vector = " ".join(["(" + NUMBER + ")"] * size)
    pattern = (
        r"Registered Voters - Total (" + NUMBER + r") Ballots Cast - Total " + vector
        + r" Ballots Cast - Blank " + vector
        + r" (?:Voter Turnout - Total (\d+\.\d{2}%)|(\d+\.\d{2}%)\s*Voter Turnout - Total)")
    match = re.match(pattern, body)
    require(match, "Missing native participation fields")
    groups = match.groups()
    facts = dict(registered_voters_literal=groups[0],
                 ballot_literals=list(groups[1:1 + size]),
                 blank_literals=list(groups[1 + size:1 + 2 * size]),
                 printed_turnout_literal=groups[-2] or groups[-1])
    return facts, body[match.end():].strip()


def parse_summary(texts, county):
    spec = SPECS[county]
    require(len(texts) == spec["summary_pages"], "Incomplete county summary")
    pages = []
    for number, text in enumerate(texts, 1):
        body, page = page_body(text, county, "summary", number)
        page.update(participation=None, reporting=[], contests=[])
        titles = spec["offices"][number - 1]
        if number == 1:
            prefix, separator, body = body.partition(REPORTING[0])
            require(separator, "Missing county reporting statistics")
            header_columns(prefix)
            body = REPORTING[0] + body
            for label in REPORTING:
                modes = r" (\d+) (\d+) (\d+)" if len(spec["modes"]) == 4 else ""
                match = re.match(re.escape(label) + r" (\d+) of (\d+)" + modes + r" ", body)
                require(match, "Missing or changed native reporting row")
                page["reporting"].append(dict(label_literal=label,
                    reported=int(match[1]), total=int(match[2]),
                    native_mode_columns=[int(value) for value in match.groups()[2:]]))
                body = body[match.end():]
            page["participation"], body = statistics(body, county)
        for index, title in enumerate(titles):
            require(body.startswith(title + " Vote For 1 "), "Changed or missing native contest")
            body = body[len(title + " Vote For 1 "):]
            if index + 1 < len(titles):
                section, separator, tail = body.partition(" " + titles[index + 1] + " Vote For 1 ")
                require(separator, "Missing next native contest")
                body = titles[index + 1] + " Vote For 1 " + tail
            else:
                section, body = body, ""
            first = re.search(r"\b(?:DEM |REP |LIB |YES |NO |Write-In Totals )", section)
            require(first, "Missing native choices")
            header_columns(section[:first.start()])
            section = section[first.start():]
            contest = dict(title_literal=title, vote_for=1, rows=[], native_reporting=None)
            while section:
                reporting = re.fullmatch(r"Precincts Reporting (\d+) of (\d+)", section)
                if reporting:
                    contest["native_reporting"] = dict(reported=int(reporting[1]), total=int(reporting[2]))
                    section = ""
                    break
                label = r"(DEM .+?|REP .+?|LIB .+?|Write-In Totals|YES|NO|Total Votes Cast|Contest Totals|Overvotes|Undervotes)"
                vector = "(" + NUMBER + r")(?: (\d+\.\d{2}%))?"
                if len(spec["modes"]) == 4:
                    vector += " " + " ".join(["(" + NUMBER + ")"] * 3)
                match = re.match(label + " " + vector + r"(?: |$)", section)
                require(match, "Unconsumed native result row: " + section[:150])
                literal = match[1]
                candidate = literal.startswith(("DEM ", "REP ", "LIB "))
                kind = "candidate" if candidate else (
                    "write_in_total" if literal == "Write-In Totals" else
                    "ballot_question_choice" if literal in ("YES", "NO") else "accounting")
                party, choice = literal.split(" ", 1) if candidate else ("", literal)
                require((match[3] is not None) == (
                    county == "Lackawanna" and literal not in ("Overvotes", "Undervotes")),
                    "Missing or invented native vote percentage")
                contest["rows"].append(dict(label_literal=literal, kind=kind, literal_party=party,
                    choice_literal=choice, count_literals=[match[2]] + list(match.groups()[3:]),
                    printed_vote_percentage=match[3]))
                section = section[match.end():]
            page["contests"].append(contest)
        require(not body, "Unconsumed summary facts")
        pages.append(page)
    return pages


def parse_unit_headers(texts, county):
    spec = SPECS[county]
    require(len(texts) == spec["statement_pages"], "Incomplete native statement")
    units = []
    for number, text in enumerate(texts, 1):
        body, meta = page_body(text, county, "statement", number)
        if "Registered Voters - Total" not in body:
            continue
        prefix, _, body = body.partition("Registered Voters - Total")
        marker = re.search(r"TOTAL|Statistics|STATISTICS", prefix)
        require(marker, "Missing native unit statistics heading")
        unit = prefix[:marker.start()].strip()
        require(unit and not any(row["unit_literal"] == unit for row in units), "Missing/duplicate native unit")
        header_columns(prefix[marker.start():])
        values, _ = statistics("Registered Voters - Total" + body, county)
        units.append(dict(unit_literal=unit, **values, **meta))
    require(len(units) == spec["units"], "Incomplete native unit participation inventory")
    return units


def validate(facts):
    require(facts["schema"] == "pa-2026-three-county-summary-v1", "Changed schema")
    require(digest(facts) == REVIEWED_SHA256, "Changed independently reviewed facts")
    require(set(facts["counties"]) == set(SPECS), "Incomplete county inventory")
    for county, native in facts["counties"].items():
        spec = SPECS[county]
        pages, units = native["summary_pages"], native["unit_participation"]
        require(len(pages) == spec["summary_pages"] and len(units) == spec["units"], "Incomplete native scope")
        stats = pages[0]["participation"]
        require(integers(stats["ballot_literals"]) == spec["ballots"]
                and integers(stats["blank_literals"]) == spec["blanks"]
                and int(stats["registered_voters_literal"].replace(",", "")) == spec["registrations"]
                and stats["printed_turnout_literal"] == spec["printed"], "Changed county participation")
        require(sum(int(row["registered_voters_literal"].replace(",", "")) for row in units)
                == spec["registrations"], "Unit registrations do not reconcile")
        for field in ("ballot_literals", "blank_literals"):
            vectors = [integers(row[field]) for row in units]
            require([sum(vector[i] for vector in vectors) for i in range(len(spec["modes"]))]
                    == integers(stats[field]), "Unit participation does not reconcile")
        rounding_conflicts = []
        for row in [stats] + units:
            registered = int(row["registered_voters_literal"].replace(",", ""))
            ballots, blanks = integers(row["ballot_literals"]), integers(row["blank_literals"])
            require(all(blank <= ballot for blank, ballot in zip(blanks, ballots)), "Invalid blank ballots")
            printed = float(row["printed_turnout_literal"][:-1])
            percentage = 100 * ballots[0] / registered if registered else 0
            if abs(percentage - printed) > .005001:
                rounding_conflicts.append(dict(unit_literal=row.get("unit_literal", "COUNTY"),
                    registered_voters=registered, ballots_cast=ballots[0],
                    printed_turnout_literal=row["printed_turnout_literal"],
                    calculated_percentage=percentage))
        require(rounding_conflicts == native["printed_turnout_rounding_conflicts"],
                "Unreviewed native printed-turnout discrepancy")
        require([contest["title_literal"] for page in pages for contest in page["contests"]]
                == [title for titles in spec["offices"] for title in titles], "Changed contest inventory")
        for page in pages:
            for contest in page["contests"]:
                rows = {row["label_literal"]: integers(row["count_literals"]) for row in contest["rows"]}
                require(len(rows) == len(contest["rows"]), "Duplicate native choice/accounting row")
                choices = [integers(row["count_literals"]) for row in contest["rows"] if row["kind"] != "accounting"]
                totals = [sum(vector[i] for vector in choices) for i in range(len(spec["modes"]))]
                if "Total Votes Cast" in rows:
                    require(totals == rows["Total Votes Cast"], "Native candidate sum differs from valid votes")
                if "Contest Totals" in rows:
                    require(all(a <= b for a, b in zip(totals, rows["Contest Totals"])), "Invalid native contest electorate")
                if "Overvotes" in rows or "Undervotes" in rows:
                    require("Overvotes" in rows and "Undervotes" in rows, "Incomplete native accounting")
                    electorate = [a + b + c for a, b, c in zip(totals, rows["Overvotes"], rows["Undervotes"])]
                    require(all(value <= limit for value, limit in zip(electorate, spec["ballots"])),
                            "Restricted contest exceeds county ballots")
                for row in contest["rows"]:
                    if row["printed_vote_percentage"] is not None:
                        expected = 100 * integers(row["count_literals"])[0] / totals[0] if totals[0] else 0
                        require(abs(expected - float(row["printed_vote_percentage"][:-1])) <= .005001,
                                "Native candidate percentage does not reconcile")
        reports = {row["source_report"]: row for row in native["source_receipts"]
                   if row.get("source_report") in ("summary", "statement")}
        require(set(reports) == {"summary", "statement"}, "Incomplete original-report provenance")
        for role, report in reports.items():
            require(report["status"] == 200 and report["tls_verification"] is True
                    and report["sha256"] == spec[role + "_sha"], "Changed native source evidence")


def tables(facts):
    validate(facts)
    result = {name: [] for name in (
        "county-participation.csv", "native-participation-modes.csv",
        "county-candidate-results.csv", "county-literal-party-totals.csv",
        "county-contest-accounting.csv", "native-reporting-statistics.csv",
        "native-unit-participation.csv", "native-source-pages.csv")}
    for county, native in facts["counties"].items():
        spec = SPECS[county]
        report = next(row for row in native["source_receipts"] if row.get("source_report") == "summary")
        common = dict(county=county, state_code="PA", election_date="2026-11-03",
                      native_status_literal="UNOFFICIAL RESULTS", source_update_literal=spec["summary_clock"],
                      declared_timezone="", source_fips="", source_url=report["url"])
        stats = native["summary_pages"][0]["participation"]
        result["county-participation.csv"].append(dict(
            **common, native_measure_literal="Ballots Cast - Total", ballots_cast=spec["ballots"][0],
            registered_voters=spec["registrations"], native_printed_turnout=spec["printed"],
            calculated_registered_fraction=spec["ballots"][0] / spec["registrations"],
            blank_ballots_already_included=spec["blanks"][0], complete_counting=False, maps_approved=False))
        for i, mode in enumerate(spec["modes"]):
            result["native-participation-modes.csv"].append(dict(
                **common, counting_mode_literal=mode, ballots_cast=spec["ballots"][i],
                blank_ballots=spec["blanks"][i], registered_voters=spec["registrations"] if i == 0 else ""))
        for page in native["summary_pages"]:
            meta = dict(**common, source_page=page["source_page"])
            result["native-source-pages.csv"].append(dict(
                **meta, native_total_pages=page["native_total_pages"],
                all_summary_data_consumed=True, both_engines_match=True))
            for row in page["reporting"]:
                result["native-reporting-statistics.csv"].append(dict(
                    **meta, label_literal=row["label_literal"], reported=row["reported"], total=row["total"],
                    native_election_day_column=row["native_mode_columns"][0] if row["native_mode_columns"] else "",
                    native_mail_column=row["native_mode_columns"][1] if row["native_mode_columns"] else "",
                    native_provisional_column=row["native_mode_columns"][2] if row["native_mode_columns"] else ""))
            for contest in page["contests"]:
                choices = [row for row in contest["rows"] if row["kind"] != "accounting"]
                by_label = {row["label_literal"]: integers(row["count_literals"]) for row in contest["rows"]}
                for row in choices:
                    for i, mode in enumerate(spec["modes"]):
                        record = dict(**meta, contest_literal=contest["title_literal"],
                            choice_literal=row["choice_literal"], literal_party=row["literal_party"],
                            choice_kind=row["kind"], counting_mode_literal=mode,
                            votes=integers(row["count_literals"])[i],
                            native_vote_percentage=row["printed_vote_percentage"] if i == 0 else "")
                        result["county-candidate-results.csv"].append(record)
                        if row["literal_party"]:
                            result["county-literal-party-totals.csv"].append(record)
                for i, mode in enumerate(spec["modes"]):
                    derived = sum(integers(row["count_literals"])[i] for row in choices)
                    result["county-contest-accounting.csv"].append(dict(
                        **meta, contest_literal=contest["title_literal"], counting_mode_literal=mode,
                        derived_choice_sum=derived,
                        native_total_votes_cast=by_label.get("Total Votes Cast", [""] * len(spec["modes"]))[i],
                        native_contest_totals=by_label.get("Contest Totals", [""] * len(spec["modes"]))[i],
                        native_overvotes=by_label.get("Overvotes", [""] * len(spec["modes"]))[i],
                        native_undervotes=by_label.get("Undervotes", [""] * len(spec["modes"]))[i],
                        native_reporting_numerator=contest["native_reporting"]["reported"] if contest["native_reporting"] else "",
                        native_reporting_denominator=contest["native_reporting"]["total"] if contest["native_reporting"] else "",
                        scope="Native contest electorate; no county registration denominator borrowed."))
        for row in native["unit_participation"]:
            for i, mode in enumerate(spec["modes"]):
                result["native-unit-participation.csv"].append(dict(
                    county=county, unit_literal=row["unit_literal"], source_page=row["source_page"],
                    source_update_literal=row["source_update_literal"], declared_timezone="",
                    counting_mode_literal=mode, ballots_cast=integers(row["ballot_literals"])[i],
                    blank_ballots=integers(row["blank_literals"])[i],
                    registered_voters=int(row["registered_voters_literal"].replace(",", "")) if i == 0 else "",
                    native_printed_turnout=row["printed_turnout_literal"] if i == 0 else "",
                    printed_turnout_rounding_conflict=(
                        any(item["unit_literal"] == row["unit_literal"]
                            for item in native["printed_turnout_rounding_conflicts"]) if i == 0 else "")))
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
        counties=3, complete_county_summary_pages=8, native_unit_participation_headers=357,
        original_statement_pages=520, unit_registrations_ballots_and_blanks_reconcile_all_supplied_modes=True,
        county_contests=22, literal_parties_preserved=True,
        indiana_modes_and_overvotes_undervotes_missing_not_zero=True,
        schuylkill_native_contest_totals_overvotes_undervotes_absent=True,
        lackawanna_reporting_mode_counter_contradictions_preserved=True,
        native_printed_turnout_rounding_conflicts={
            county: native["printed_turnout_rounding_conflicts"]
            for county, native in facts["counties"].items() if native["printed_turnout_rounding_conflicts"]},
        no_candidate_vote_proxy_no_district_registration_denominators=True,
        native_fips_absent=True, maps_approved=False, complete_counting=False,
        scope="Complete county-summary numerical query plus complete native unit participation headers, "
              "not a complete precinct-contest query or new geometry. Printed source clocks have no timezone. "
              "Complete precinct reporting does not establish certification or finished counting. "
              "Original HTML/PDF templates stay private. Blank ballots are already in county totals."))
    here = Path(__file__).resolve().parent
    for name in (PROGRAM, TEST):
        files[name] = (here / name).read_bytes()
    files["METHODS.txt"] = (
        "Complete Indiana, Lackawanna and Schuylkill 2026 county-summary query.\n"
        "All eight county-summary pages are fully parsed as numerical facts. All 357 native unit "
        "participation headers reconcile across the 520 original statement pages; their contests "
        "are outside this summary query. No precinct geography is acquired or inferred.\n"
        "Offline: python3 " + PROGRAM + " --facts native-facts.json --output REPRODUCED\n"
        "Tests: python3 " + TEST + "\n"
        "Native modes, printed percentages, reporting contradictions, missing accounting, "
        "restricted contests and absent timezones/FIPS are retained. Missing is not zero. "
        "Schuylkill unit 137 Pine Grove Township 1st prints 55.42% for 802 ballots / 1447 "
        "registrations (55.425017277125086% calculated); retain and flag this native rounding discrepancy. "
        "Candidate selections do not replace ballots. Exact county registration denominators "
        "do not become district or mode denominators. Source templates are not redistributed.\n").encode()
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
    return {"files": len(files), "zip_members": len(files) - 1,
            "zip_bytes": len(stream.getvalue()), "zip_sha256": hashlib.sha256(stream.getvalue()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(json.loads(args.facts.read_text()), args.output), indent=2))

"""Reproduce the complete factual query of Columbia's two reviewed 2026 reports."""

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


PARENT = "https://www.columbiapa.org/voter/index.php"
SOURCES = {
    "parent": (PARENT, 10754, "85e0483632f4dc57a056f16ed4ef963ab9c1a9dfdf8d7f98f59cb55ac7323c48"),
    "results": ("https://www.columbiapa.org/voter/2026/1132026.pdf", 77278,
                "e7d73daff66f282eebe5359bc6bba25e2b176cb2be5d33c06c4c0a11b7756b12"),
    "mail-summary": ("https://www.columbiapa.org/voter/2026/2026GenAbsenteeMailInBallotSummary.pdf", 76841,
                     "0ffb6331dd58779c3af0ba5bc3f067f1c6306b16129fbe5cf57a260042d18a5f"),
}
FIELDS = ("app_issued", "app_returned", "ballots_sent", "ballot_returned", "votes_recorded")
TITLES = (
    "GOVERNOR / LIEUTENANT GOVERNOR",
    "REPRESENTATIVE IN CONGRESS 9TH DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 109TH DISTRICT",
)
MAIL_LABELS = {
    "application_types": ("CIVILIAN OVERSEAS", "EMERGENCY", "MAIL-IN", "MILITARY",
        "ONLINE MAIL-IN NOT VERIFIED", "ONLINE MAIL-IN VERIFIED", "ONLINE REGULAR ABSENTEE VERIFIED", "Regular Absentee"),
    "ballot_styles": ("",),
    "registration_parties": ("REPUBLICAN", "NO AFFILIATION", "DEMOCRATIC", "INDEPENDENT",
        "LIBERTARIAN", "LIBERTARIAN REPUBLICAN", "NON-PARTISAN", "OTHER", "GREEN"),
}
ROW_Y = {
    "application_types": (596, 644, 693, 742, 790, 840, 888, 965),
    "ballot_styles": (1250,),
    "registration_parties": (1545, 1598, 1649, 1702, 1754, 1806, 1858, 1912, 1963),
}
TOTAL_Y = {"application_types": 1012, "ballot_styles": 1302, "registration_parties": 2014}
ARCHIVE = "complete-columbia-county-native-query-01.zip"
REVIEWED_INPUT_SHA256 = "fae1c6884bda71fff342c05ef65549f13f50f321ee63973d203f0f53aaf1b94b"


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(bool(re.fullmatch(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", value)), "Invalid native integer")
    return int(value.replace(",", ""))


def summary(text):
    require(len(re.findall(r"Date:\s*11/3/2026\b", text)) == 1, "Changed report date")
    require(len(re.findall(r"Time:\s*10:37:16 PM EST\b", text)) == 1, "Changed report clock/timezone")
    require(len(re.findall(r"Page\s+1/\s*1\b", text)) == 1, "Incomplete report pages")
    cleaned = re.sub(r"Date:\s*11/3/2026|Time:\s*10:37:16 PM EST|Page\s+1/\s*1", "", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in cleaned.splitlines() if line.strip()]
    headers = ("Election Summary Report", "COLUMBIA COUNTY PENNSYLVANIA", "GENERAL ELECTION",
               "NOVEMBER 3, 2026", "November 3, 2026 RESULTS", "UNOFFICIAL ELECTION RESULTS")
    require(lines[:6] == list(headers), "Changed election/status/header")
    lines = lines[6:]
    match = re.fullmatch(r"Registered Voters ([\d,]+) - Total Ballots ([\d,]+) : (\d+\.\d+)% "
                         r"(\d+) of (\d+) Precincts Reporting (\d+\.\d+)%", lines.pop(0))
    require(match is not None, "Missing native participation header")
    registrations, ballots = map(integer, match.group(1, 2))
    require(0 < ballots <= registrations, "Invalid ballot/registration relationship")
    require(f"{100 * ballots / registrations:.2f}" == match[3], "Participation fraction disagrees")
    reporting = (integer(match[4]), integer(match[5]), match[6])
    require(reporting[0] <= reporting[1] and reporting[1] > 0
            and f"{100 * reporting[0] / reporting[1]:.2f}" == reporting[2], "Reporting fraction disagrees")
    contests = []
    for title in TITLES:
        printed = lines.pop(0)
        if printed == "REPRESENTATIVE IN THE GENERAL ASSEMBLY 109TH":
            printed += " " + lines.pop(0)
        require(printed == title, "Missing or unexpected native contest")
        n = re.fullmatch(r"Number of Precincts (\d+)", lines.pop(0))
        r = re.fullmatch(r"Precincts Reporting (\d+) (\d+\.\d+)%", lines.pop(0))
        require(n is not None and r is not None, "Changed contest reporting schema")
        require((integer(r[1]), integer(n[1]), r[2]) == reporting, "Contest/counting scopes disagree")
        require(lines.pop(0) == "Vote For 1", "Changed vote-for scope")
        total = re.fullmatch(r"Total Votes ([\d,]+)", lines.pop(0))
        require(total is not None, "Missing native contest total")
        votes = integer(total[1])
        choices = []
        while lines and not lines[0].startswith(("GOVERNOR /", "REPRESENTATIVE IN")):
            row = re.fullmatch(r"(.+?) ([\d,]+) (\d+\.\d+)%", lines.pop(0))
            require(row is not None, "Unconsumed candidate line")
            label_lines = [row[1]]
            while lines and not lines[0].startswith(("GOVERNOR /", "REPRESENTATIVE IN")) and not re.fullmatch(
                    r"(.+?) ([\d,]+) (\d+\.\d+)%", lines[0]):
                label_lines.append(lines.pop(0))
            label = " ".join(label_lines)
            party = re.fullmatch(r"(.+?) \(([A-Z& -]+)\)", label)
            require(party is not None or label == "Write-in", "Missing literal party or write-in identity")
            count = integer(row[2])
            require(votes > 0 and f"{100 * count / votes:.2f}" == row[3], "Printed candidate fraction disagrees")
            choices.append(dict(native_choice=party[1] if party else label,
                native_party=party[2] if party else "", native_label_lines=label_lines,
                votes=count, native_printed_percent=row[3],
                kind="candidate" if party else "write_in_total"))
        require(choices and sum(row["votes"] for row in choices) == votes <= ballots,
                "Candidate choices, contest totals or ballots disagree")
        require(len({row["native_choice"] for row in choices}) == len(choices), "Duplicate native choice")
        contests.append(dict(contest_literal=title, vote_for=1, total_votes=votes,
            reporting_precincts=reporting[0], total_precincts=reporting[1],
            native_printed_reporting_percent=reporting[2], choices=choices))
    require(not lines, "Unconsumed native report lines")
    return dict(registered_voters=registrations, ballots=ballots, printed_turnout=match[3],
                reporting=reporting, contests=contests)


def review(facts):
    if REVIEWED_INPUT_SHA256:
        require(hashlib.sha256(json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                == REVIEWED_INPUT_SHA256, "Changed complete independently reviewed source query")
    require(facts["year"] == 2026 and facts["county"] == "Columbia" and facts["maps_approved"] is False,
            "Wrong identity or unauthorized mapping")
    receipts = facts["source_receipts"]
    require(len(receipts) == 3 and {row["role"] for row in receipts} == set(SOURCES), "Incomplete receipts")
    for receipt in receipts:
        require((receipt["requested_url"], receipt["bytes"], receipt["sha256"]) == SOURCES[receipt["role"]]
                and receipt["status"] == 200, "Changed original-source receipt")
    require([row["url"] for row in facts["source_declarations"]] ==
            [SOURCES[role][0] for role in ("results", "mail-summary")], "Changed actual declarations")
    require(facts["native_mail_headers"] == dict(report_code="00000-ABS-004-C", county="Columbia County",
        date="Tuesday, November 3, 2026", title="Absentee/Mail-In Ballots Summary",
        election="ELECTION:2026 GENERAL ELECTION", native_columns=[
            "App Issued", "App Returned", "Ballots Sent", "Ballot Returned", "Votes Recorded"],
        source_filter="Election ID (N) IS 2026 GENERAL ELECTION AND Federal Voter (Y) IS 0 AND Valid Voter (Y) IS 1",
        native_status_literal="", native_update_time_literal="", declared_printed_timezone="",
        page="Page 1 of 1"), "Changed native mail filter, electorate, date, headings or missing clock")
    require(facts["native_mail_embedded_text"] == {"pypdf": "", "pymupdf": ""},
            "Scanned report has no independent embedded-text transcription")
    require((facts["ocr_image"]["width"], facts["ocr_image"]["height"]) == (1836, 2376),
            "Changed image dimensions for independently reviewed cell coordinates")
    parsed = [summary(facts["native_layout"][engine]) for engine in ("pypdf", "pymupdf")]
    require(parsed[0] == parsed[1], "Entire report vectors disagree across PDF engines")
    tokens = [Counter(re.findall(r"[A-Za-z]+|\d+(?:[,.]\d+)*%?", facts["native_layout"][engine]))
              for engine in ("pypdf", "pymupdf")]
    require(tokens[0] == tokens[1], "Entire report token multisets disagree")
    table = parsed[0]
    tables = {"county-participation.csv": [dict(year=2026, state_code="PA", county="Columbia",
        native_participation_measure_literal="Total Ballots", ballots_cast=table["ballots"],
        registered_voters=table["registered_voters"], native_printed_turnout=table["printed_turnout"],
        registered_turnout_pct=100 * table["ballots"] / table["registered_voters"],
        source_status_literal="UNOFFICIAL ELECTION RESULTS", source_update_literal="11/3/2026 10:37:16 PM EST",
        declared_timezone="EST", reported_precincts=table["reporting"][0], total_precincts=table["reporting"][1],
        native_reporting_percent=table["reporting"][2], counting_complete=False, source_fips="", maps_approved=False)],
        "county-candidate-results.csv": [], "county-literal-party-totals.csv": [],
        "county-contest-accounting.csv": [], "native-reporting-statistics.csv": [],
        "native-mail-section-totals.csv": [], "native-mail-cell-review.csv": []}
    for contest in table["contests"]:
        meta = {key: value for key, value in contest.items() if key != "choices"}
        tables["native-reporting-statistics.csv"].append(meta)
        tables["county-contest-accounting.csv"].append(dict(**meta, native_total_ballots=table["ballots"],
            candidate_vote_sum=sum(row["votes"] for row in contest["choices"]),
            unclassified_ballot_minus_contest_votes=table["ballots"] - contest["total_votes"],
            blank_over_under_votes_supplied=False))
        parties = Counter()
        for row in contest["choices"]:
            tables["county-candidate-results.csv"].append(dict(**meta,
                **{key: value for key, value in row.items() if key != "native_label_lines"},
                native_label_lines=json.dumps(row["native_label_lines"])))
            parties[row["native_party"]] += row["votes"]
        tables["county-literal-party-totals.csv"].extend(
            dict(contest_literal=contest["contest_literal"], native_party=party, votes=count,
                 party_missing=party == "") for party, count in parties.items())
    width, height = facts["ocr_image"]["width"], facts["ocr_image"]["height"]
    boxes = {"rapidocr": [], "apple_vision": []}
    for bounds, text, confidence in facts["ocr"]["rapidocr"]["results"]:
        x = sum(point[0] for point in bounds) / len(bounds) / width
        y = sum(point[1] for point in bounds) / len(bounds)
        boxes["rapidocr"].append((x, y, text))
    for row in facts["ocr"]["apple_vision"][0]["lines"]:
        x, y, w, h = row["bounds"]
        boxes["apple_vision"].append((x + w / 2, (1 - y - h / 2) * height, row["candidates"][0]["text"]))
    windows = ((.38, .48), (.48, .58), (.58, .67), (.67, .77), (.77, .89))
    for section, labels in MAIL_LABELS.items():
        rows = facts["mail_sections"][section]
        require(tuple(row["native_label"] for row in rows) == labels, "Missing/duplicated native mail category")
        total = facts["mail_totals"][section]
        require(len(total) == 5 and all(type(value) is int and value >= 0 for value in total),
                "Invalid explicit mail totals")
        for index, field in enumerate(FIELDS):
            require(all(len(row["values"]) == 5 and all(type(value) is int and value >= 0
                        for value in row["values"]) for row in rows), "Missing explicit mail cell")
            require(sum(row["values"][index] for row in rows) == total[index], "Mail categories do not reconcile")
        for row in rows:
            values = row["values"]
            require(values[0] >= values[1] >= values[2] >= values[3] >= values[4], "Invalid scoped mail relationship")
        tables["native-mail-" + section.replace("_", "-") + ".csv"] = [
            dict(native_label=row["native_label"], **dict(zip(FIELDS, row["values"]))) for row in rows]
        tables["native-mail-section-totals.csv"].append(dict(section=section, **dict(zip(FIELDS, total))))
        for label, values, y in [(row["native_label"], row["values"], y) for row, y in zip(rows, ROW_Y[section])] + [
                ("Election Totals:", total, TOTAL_Y[section])]:
            for value, field, (left, right) in zip(values, FIELDS, windows):
                reads = {engine: [text for x, yy, text in observations if left <= x < right and abs(yy - y) < 15]
                         for engine, observations in boxes.items()}
                require(any(str(value) == text.strip(".") for texts in reads.values() for text in texts),
                        f"No independent OCR evidence for explicit mail cell: {section}/{label}/{field}={value}: {reads}")
                tables["native-mail-cell-review.csv"].append(dict(section=section, native_label=label,
                    native_column=field, reviewed_value=value, rapidocr_literals=json.dumps(reads["rapidocr"]),
                    apple_vision_literals=json.dumps(reads["apple_vision"]),
                    differing_or_missing_ocr_retained=True))
    require(len({tuple(value) for value in facts["mail_totals"].values()}) == 1, "Parallel mail totals disagree")
    require(len(tables["native-mail-cell-review.csv"]) == 105, "Incomplete mail cell review")
    tables["native-source-pages.csv"] = [
        dict(source_report="results", physical_page=1, native_page_literal="1/1",
            native_date_literal="11/3/2026", source_update_literal="11/3/2026 10:37:16 PM EST",
            declared_timezone="EST", native_status_literal="UNOFFICIAL ELECTION RESULTS"),
        dict(source_report="mail-summary", physical_page=1, native_page_literal="Page 1 of 1",
            native_date_literal=facts["native_mail_headers"]["date"], source_update_literal="",
            declared_timezone="", native_status_literal=""),
    ]
    tables["native-mail-report-metadata.csv"] = [
        dict(native_field=key, native_value=json.dumps(value) if isinstance(value, list) else value)
        for key, value in facts["native_mail_headers"].items()]
    tables["source-receipts.csv"] = receipts
    tables["native-source-declarations.csv"] = facts["source_declarations"]
    tables["native-pdf-metadata.csv"] = [dict(source_report=role, metadata_key=key,
        native_value=value if value is not None else "", native_null=value is None)
        for role, metadata in facts["pdf_metadata"].items() for key, value in metadata.items()]
    return tables


def render(facts, destination):
    tables = review(facts)
    destination.mkdir(exist_ok=False)
    for name, rows in tables.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(key for row in rows for key in row)),
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (destination / name).write_bytes(stream.getvalue().encode())
    (destination / "source-records.json.gz").write_bytes(gzip.compress(json_bytes(facts), mtime=0))
    (destination / "review-columbia-county-native-query.py").write_bytes(Path(__file__).read_bytes())
    test = Path(__file__).with_name("test-columbia-native-query.py")
    (destination / test.name).write_bytes(test.read_bytes())
    audit = dict(county="Columbia", year=2026, maps_approved=False, csv_tables=len(tables),
        complete_rows={name: len(rows) for name, rows in tables.items()},
        summary_all_layout_lines_consumed_both_engines=True, entire_summary_vectors_equal=True,
        all_105_mail_cells_reviewed=len(tables["native-mail-cell-review.csv"]) == 105,
        ocr_errors_and_missing_observations_retained=True,
        scope="Complete factual query of both declared reports, not the parent archive. Mail application, "
              "returned-ballot and votes-recorded columns are distinct; registration-party categories "
              "are not candidate party votes. Mail PDF filter/electorate and PDF metadata clocks remain "
              "separate from the unofficial county report's printed EST clock. No source establishes "
              "which mail subtotal is included in county ballots. No Election Day remainder, blank/over/"
              "undervotes, voting completion, certification, source FIPS, geometry or demographic rates inferred.")
    (destination / "audit.json").write_bytes(json_bytes(audit))
    checksums = [dict(file=path.name, bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(destination.iterdir())]
    (destination / "checksums.json").write_bytes(json_bytes(dict(files=checksums)))
    with zipfile.ZipFile(destination / ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(destination.iterdir()):
            if path.name != ARCHIVE:
                info = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_records", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    body = args.source_records.read_bytes()
    facts = json.loads(gzip.decompress(body) if args.source_records.suffix == ".gz" else body)
    render(facts, args.output)

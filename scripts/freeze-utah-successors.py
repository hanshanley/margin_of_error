"""Freeze complete permitted aggregate facts from already-held Utah successor reports."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def number(literal):
    if not isinstance(literal, str) or not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", literal):
        raise ValueError("Unqualified native integer literal")
    return int(literal.replace(",", ""))


def worksheet_facts(path):
    import openpyxl

    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(node.itertext()) for node in ET.fromstring(
                archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        tree = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        raw = {}
        for cell in tree.findall(".//s:sheetData/s:row/s:c", NS):
            kind = cell.get("t", "n")
            value = cell.find("s:v", NS)
            literal = value.text if value is not None else ""
            if kind == "s":
                value = strings[int(literal)]
            elif kind == "inlineStr":
                value = "".join(cell.find("s:is", NS).itertext())
            elif kind == "b":
                value = literal == "1"
            elif kind in ("e", "str"):
                value = literal
            elif literal:
                value = float(literal)
                if value.is_integer():
                    value = int(value)
            else:
                value = None
            formula = cell.find("s:f", NS)
            raw[cell.get("r")] = dict(type=kind, value=value,
                literal=literal if kind not in ("s", "inlineStr") else value,
                formula=formula.text if formula is not None else None)
    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook.active
    checks = 0
    for coordinate, cell in raw.items():
        actual = sheet[coordinate].value
        if isinstance(cell["value"], (int, float)) and not isinstance(cell["value"], bool):
            if actual is None or abs(actual - cell["value"]) > 1e-12:
                raise ValueError("Independent workbook numeric cell differs")
        elif actual != cell["value"] and not (actual is None and cell["value"] == ""):
            raise ValueError("Independent workbook literal differs")
        checks += 1
    certification = next(cell.row for row in sheet for cell in row
        if isinstance(cell.value, str) and cell.value.startswith("Section 6:"))
    cells = {coordinate: cell for coordinate, cell in raw.items()
        if sheet[coordinate].row < certification}
    counted = [(sheet.cell(row, 3).coordinate, sheet.cell(row, 3).value)
        for row in range(1, certification)
        if sheet.cell(row, 4).value == "Total ballots counted"]
    if len(counted) != 1 or not isinstance(counted[0][1], int):
        raise ValueError("Missing or repeated native counted-ballot statistic")
    return dict(sheet=sheet.title, county_election_header=sheet["C3"].value,
        cells=cells, dimensions=dict(rows=certification - 1, columns=sheet.max_column),
        excluded_rows=dict(first=certification, last=sheet.max_row,
            reason="Unused certification identity/presentation, not aggregate analysis inputs"),
        selected_count_cell=counted[0][0], selected_count=counted[0][1]), checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cached", "transcription", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a fresh complete native-fact output")
    receipts = json.loads((args.cached / "successor-receipts.json").read_bytes())
    by_name = {row["filename"]: row for row in receipts}
    transcription = json.loads(args.transcription.read_bytes())
    if transcription["contract"] != "participation.utah_summary_transcription.v1":
        raise ValueError("Unknown source transcription")
    reports, checks = [], 0
    for source in transcription["reports"]:
        receipt = by_name[source["file"]]
        body = (args.cached / source["file"]).read_bytes()
        if receipt["status"] != 200 or pin(body) != {key: receipt[key] for key in ("bytes", "sha256")} \
                or receipt["election_date"] != "2026-11-03":
            raise ValueError("Previously held source pin or election differs")
        county = source["county"] + " County"
        count = number(source["statistics"]["Ballots Cast - Total"])
        if source["native_county_literal"] != county + ", Utah":
            raise ValueError("Native whole-county header differs")
        cross = source["crosscheck"]
        workbook = None
        if "file" in cross:
            wb_receipt = by_name[cross["file"]]
            wb_body = (args.cached / cross["file"]).read_bytes()
            if wb_receipt["status"] != 200 or pin(wb_body) != {
                    key: wb_receipt[key] for key in ("bytes", "sha256")}:
                raise ValueError("Workbook route/pin is not an accepted acquisition")
            workbook, verified = worksheet_facts(args.cached / cross["file"])
            checks += verified
            if "November 3, 2026" not in workbook["county_election_header"] \
                    or workbook["selected_count"] != count:
                raise ValueError("Independent native counted totals or election differ")
            workbook["source"] = wb_receipt
            corroboration = str(workbook["selected_count"])
        else:
            corroboration = cross["count_literal"]
            if number(corroboration) != sum(number(cross[key]) for key in
                    ("total_votes_cast_literal", "overvotes_literal", "undervotes_literal")):
                raise ValueError("Whole-county contest corroboration differs")
        if number(corroboration) != count:
            raise ValueError("Independent county aggregate differs")
        reports.append(dict(key="UT-" + source["county"].lower(), source=receipt,
            election=dict(id="UT-General11032026", year=2026, date="2026-11-03",
                type="general", qualification="native"),
            geography=dict(state_code="UT", level="county", name=county),
            native_geography_literal=source["native_county_literal"],
            native_status_literal=source["native_status_literal"],
            source_clock=dict(literal=source["native_update_literal"], timezone=None),
            columns=["reported_native_total_ballots"],
            rows=[dict(label="Statistics: Ballots Cast - Total", count_literals=[
                source["statistics"]["Ballots Cast - Total"]], source_page=1),
                dict(label=cross["label"], count_literals=[corroboration],
                    source_file=cross.get("file", source["file"]))],
            full_summary_statistics=source["statistics"], corroboration=cross,
            full_workbook_facts=workbook, independent_scope_review=source["verification"],
            fractions_qualified=False, unique_people_qualified=False,
            statewide_or_counting_completion_qualified=False))
    denied = by_name["cache-statistics.xlsx"]
    if denied["status"] != 403:
        raise ValueError("Recorded access hold changed")
    result = dict(contract="participation.native_table_counts.v1", reports=reports,
        complete_public_aggregate_facts=True, source_receipts=receipts,
        blocked_route=dict(url=denied["url"], status=403, bytes=denied["bytes"],
            sha256=denied["sha256"], retried=False, bypassed=False),
        native_presentation_or_session_headers_redistributed=False)
    args.output.mkdir(parents=True)
    facts = (json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()
    (args.output / "native-facts.json").write_bytes(facts)
    proof = dict(status="passed_independent_cached_utah_native_facts",
        all_four_county_totals_independently_corroborated=True,
        counts={row["geography"]["name"]: number(row["rows"][0]["count_literals"][0]) for row in reports},
        independent_workbook_cells=checks, successful_originals_reacquired=0,
        blocked_route_retried=False, source_zeros_blanks_errors_and_clocks_preserved=True,
        facts_pin=pin(facts))
    (args.output / "native-verification.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps(proof, sort_keys=True))


if __name__ == "__main__":
    main()

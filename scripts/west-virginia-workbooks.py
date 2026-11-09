"""Read every original WV workbook cell with standard-library OOXML, preserving blanks and native totals."""

from decimal import Decimal
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
HEADERS = ["COUNTY", "CONSTITUTION PARTY", "DEMOCRATIC PARTY", "REPUBLICAN PARTY",
           "MOUNTAIN PARTY", "NO PARTY", "LIBERTARIAN PARTY", "OTHER PARTY", "TOTAL VOTERS"]
PRODUCTS = {
    "early-in-person-cast": ("in_person_early", 162349),
    "absentee-requested": ("absentee_requested", 9735),
    "absentee-returned": ("mail_returned", 7001),
}


def original_sheets(path):
    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(node.itertext()) for node in ET.fromstring(
                archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        relationships = {node.attrib["Id"]: node.attrib["Target"] for node in ET.fromstring(
            archive.read("xl/_rels/workbook.xml.rels"))}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = []
        for sheet in workbook.findall("s:sheets/s:sheet", NS):
            target = relationships[sheet.attrib[REL]]
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            xml = ET.fromstring(archive.read(target))
            cells = []
            for node in xml.findall("s:sheetData/s:row/s:c", NS):
                literal = node.find("s:v", NS)
                kind = node.attrib.get("t", "n")
                if kind == "inlineStr":
                    value = "".join(node.find("s:is", NS).itertext())
                elif literal is None or literal.text is None:
                    value = None
                elif kind == "s":
                    value = strings[int(literal.text)]
                elif kind == "b":
                    value = literal.text == "1"
                elif kind in {"str", "e"}:
                    value = literal.text
                else:
                    number = Decimal(literal.text)
                    if number != number.to_integral_value():
                        raise ValueError("Noninteger native WV count; no rounding")
                    value = int(number)
                formula = node.find("s:f", NS)
                cells.append(dict(address=node.attrib["r"], value=value, native_type=kind,
                    formula_literal=formula.text if formula is not None else None))
            sheets.append(dict(name=sheet.attrib["name"], native_cells=cells))
    return sheets


def review_workbooks(directory, identities):
    if len(identities) != 55:
        raise ValueError("Full 55-county identity reference required")
    by_name = {name.lower().removesuffix(" county"): fips for fips, name in identities.items()}
    result = {}
    for product, (mode, expected_state) in PRODUCTS.items():
        sheets = original_sheets(Path(directory) / (product + "-original.xlsx"))
        first = sheets[0]
        cells = {cell["address"]: cell["value"] for cell in first["native_cells"]}
        headers = [cells.get(f"{column}1") for column in "ABCDEFGHI"]
        if headers != HEADERS:
            raise ValueError("Changed WV native workbook measure/party fields")
        for other in sheets[1:]:
            if any(cell["value"] is not None for cell in other["native_cells"]):
                raise ValueError("Unexpected additional WV worksheet observations")
        records = []
        for row_number in range(2, 58):
            native = {header: cells.get(f"{column}{row_number}")
                      for column, header in zip("ABCDEFGHI", HEADERS)}
            values = [native[header] for header in HEADERS[1:]]
            if any(type(value) is not int or value < 0 for value in values):
                raise ValueError("Missing or unsafe native WV count is not zero")
            if sum(values[:-1]) != values[-1]:
                raise ValueError("Native WV party cells do not equal their row total; never repair")
            records.append(dict(native_excel_row=row_number, native_record=native))
        state = records[-1]
        if (state["native_record"]["COUNTY"] != "WEST VIRGINIA"
                or state["native_record"]["TOTAL VOTERS"] != expected_state):
            raise ValueError("Changed WV explicit state subtotal")
        for header in HEADERS[1:]:
            if sum(row["native_record"][header] for row in records[:-1]) != state["native_record"][header]:
                raise ValueError("Native WV county cells disagree with the separate state subtotal")
        counties = []
        for record in records[:-1]:
            native = record["native_record"]
            fips = by_name.get(native["COUNTY"].lower())
            if fips is None:
                raise ValueError("Unmatched WV source county")
            counties.append(dict(record, year=2026, state_code="WV", county_fips=fips,
                county=identities[fips], mode=mode, source_product=product,
                source_count=native["TOTAL VOTERS"], denominator=None, reported_pct=None,
                native_party_counts={header: native[header] for header in HEADERS[1:-1]},
                party_scope="Native source party category, not candidate vote choice; operational affiliation definition unqualified.",
                literal_total_field="TOTAL VOTERS", source_period_start="2026-10-21" if mode == "in_person_early" else None,
                source_period_end="2026-10-31", source_clock=None, source_timezone=None,
                article_publication_date="2026-11-02", full_election_turnout_qualified=False,
                unique_voters_certified=False, analysis_rate_approved=False))
        if len({row["county_fips"] for row in counties}) != 55:
            raise ValueError("Duplicate or incomplete WV county query")
        result[mode] = dict(original_state_row=state,
            original_worksheets=sheets, publisher_measure=product,
            counties=sorted(counties, key=lambda row: row["county_fips"]))
    return result

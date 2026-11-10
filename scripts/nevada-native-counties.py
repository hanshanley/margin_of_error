"""Reproduce literal Nevada county participation without candidate-vote substitution."""

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-nevada-native-counties-01"
DOWNLOAD = ("https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-nevada-native-counties-20261110-01/complete-analysis.zip")
PDF_MODES = {
    "Churchill": ("Early Vote", "Election Day", "Mail", "Prov-Election Day", "Prov-Early Vote"),
    "White Pine": ("Early Vote", "Election Day", "Mail"),
}
CLARK_MODES = ("Early Vote Turnout", "Election Day Turnout", "Mail Turnout",
               "Early Vote Provisional Turnout", "Election Day Provisional Turnout")


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def integer(value):
    if not re.fullmatch(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", str(value)):
        raise ValueError("Invalid native count: " + str(value))
    return int(str(value).replace(",", ""))


def percent(count, denominator, literal):
    if denominator <= 0 or f"{100 * count / denominator:.2f}%" != literal:
        raise ValueError("Native percentage disagrees with its printed registration basis")


def parse_clark(facts):
    text = facts["source_text"]
    if text.count("2026 General Election") != 1 or text.count("REGISTRATION & TURNOUT") != 1:
        raise ValueError("Wrong Clark election or missing native participation header")
    if "Unofficial Results" not in text or not facts["publisher_application_code_excluded"]:
        raise ValueError("Missing Clark native status or unsafe factual projection")
    registers = [re.fullmatch(r"([\d,]+) Registered Voters", value) for value in text]
    registers = [match for match in registers if match]
    clocks = [value for value in text if value.startswith("Updated ")]
    tables = [table for table in facts["all_tables"]
              if table and table[0] == ["Voting Method", "Total", "% / Reg", "Grand Total / Total"]]
    if len(registers) != 1 or len(clocks) != 1 or len(tables) != 1:
        raise ValueError("Missing or duplicated Clark participation, register or clock")
    table = tables[0]
    if len(table) != 7 or [row[0] for row in table[1:]] != [*CLARK_MODES, "Total"]:
        raise ValueError("Changed Clark native counting-group scope")
    registered = integer(registers[0][1])
    total = integer(table[-1][1])
    percent(total, registered, table[-1][2])
    modes = []
    for row in table[1:-1]:
        if len(row) != 4:
            raise ValueError("Incomplete Clark counting-group row")
        count = integer(row[1])
        percent(count, registered, row[2])
        percent(count, total, row[3])
        modes.append(dict(native_counting_group=row[0], source_count=count,
            native_percent_of_register=row[2], native_percent_of_source_total=row[3]))
    if sum(row["source_count"] for row in modes) != total:
        raise ValueError("Clark mode components disagree with printed county total")
    return dict(county="Clark", source_count=total, registered=registered,
        native_printed_pct=table[-1][2], source_measure_literal="REGISTRATION & TURNOUT / Total",
        source_status_literal="Unofficial Results", source_clock_literal=clocks[0],
        source_clock_kind="native_page_update", source_timezone=None,
        source_scope_literal="Clark County official countywide Election Night Results",
        source_modes=modes, complete_native_table_count=len(facts["all_tables"]),
        native_participation_table=table)


def parse_pdf(county, facts):
    pages = facts["page_texts"]
    expected_pages = {"Churchill": 16, "White Pine": 7}[county]
    if len(pages) != expected_pages or facts["original_pdf_pages"] != expected_pages:
        raise ValueError("Incomplete native PDF")
    first = pages[0]
    clock = first.splitlines()[0]
    for index, page in enumerate(pages, 1):
        if not page.startswith(clock + f"\nPage: {index} of {expected_pages}\n"):
            raise ValueError("Changed PDF page, ordering or literal generation clock")
    election_literal = "November 03, 2026" if county == "Churchill" else "2026 General Election"
    if (election_literal not in first or "General Election" not in first
            or county.upper() + " COUNTY" not in first.upper()):
        raise ValueError("Wrong county, election or native participation scope")
    headers = re.findall(r"Voters Cast:\s*([\d,]+) of ([\d,]+) \(([\d.]+%)\)", first)
    if len(headers) != 1:
        raise ValueError("Missing or duplicated native county Voters Cast header")
    count_text, registered_text, printed = headers[0]
    count, registered = integer(count_text), integer(registered_text)
    independent = re.findall(r"Voters Cast:\s*([\d,]+)\s+of\s+([\d,]+)\s*\(\s*([\d.]+%)\s*\)",
                             facts["independent_first_page_text"])
    if independent != headers:
        raise ValueError("Independent native PDF readers disagree on participation")
    marker = "Elector Group\nCounting Group\nVoters Cast\nRegistered Voters\nTurnout\nTotal\n"
    if first.count(marker) != 1:
        raise ValueError("Missing independent county counting-group summary")
    summary = first.split(marker)[1]
    if re.findall(r"(?:^|\n)Total\n([\d,]+)\n([\d,]+)\n([\d.]+%)\s*$", summary) != headers:
        raise ValueError("Printed county header and summary disagree")
    modes = []
    for name in PDF_MODES[county]:
        cells = re.findall(r"(?:^|\n)" + re.escape(name) + r"\n([\d,]+)\n([\d.]+%)", summary)
        if len(cells) != 1:
            raise ValueError("Missing or duplicated native counting group")
        value = integer(cells[0][0])
        percent(value, registered, cells[0][1])
        modes.append(dict(native_counting_group=name, source_count=value,
            native_percent_of_register=cells[0][1], native_percent_of_source_total=None))
    if sum(row["source_count"] for row in modes) != count:
        raise ValueError("Counting groups disagree with county participation")
    percent(count, registered, printed)
    status = "Unofficial Results - 03" if county == "Churchill" else "Election Day Results-Unofficial"
    if status not in first:
        raise ValueError("Missing literal native unofficial status")
    casts = []
    size = len(PDF_MODES[county])
    expression = (r"Times Cast\n((?:[\d,]+\n){" + str(size)
                  + r"})([\d,]+) / ([\d,]+)\s+([\d.]+%|N/A)")
    for page_number, page in enumerate(pages, 1):
        for component, total, register, fraction in re.findall(expression, page):
            values = [integer(value) for value in component.splitlines()]
            if sum(values) != integer(total):
                raise ValueError("Native contest Times Cast components disagree")
            casts.append(dict(page=page_number, native_counting_group_counts=values,
                native_times_cast=integer(total), native_registered=integer(register),
                native_percent_literal=fraction,
                is_county_parent=False,
                differs_from_county_parent=integer(total) != count or integer(register) != registered))
    if not casts:
        raise ValueError("Missing independent contest accounting")
    return dict(county=county, source_count=count, registered=registered,
        native_printed_pct=printed, source_measure_literal="Voters Cast",
        source_status_literal=status, source_clock_literal=clock,
        source_clock_kind="native_PDF_generation", source_timezone=None,
        source_election_date_literal="November 03, 2026" if county == "Churchill" else None,
        source_scope_literal="Native countywide Voters Cast header and matching total summary",
        source_modes=modes, complete_native_pdf_pages=expected_pages,
        all_native_contest_times_cast=casts)


def load(root=ROOT):
    directory = root / VERSION
    inputs = json.loads((directory / "inputs.json").read_bytes())
    if inputs["version"] != VERSION:
        raise ValueError("Changed sufficient-input version")
    for name, expected in inputs["files"].items():
        if pin((directory / name).read_bytes()) != expected:
            raise ValueError("Changed sufficient original: " + name)
    receipts = json.loads((directory / "source-receipts-without-headers.json").read_bytes())
    observations = []
    for county in ("Clark", "Churchill", "White Pine"):
        name = county.lower().replace(" ", "-")
        facts = json.loads((directory / "originals" / (name + "-complete-numerical-facts.json")).read_bytes())
        row = parse_clark(facts) if county == "Clark" else parse_pdf(county, facts)
        receipt = receipts[county]
        if receipt["status"] != 200:
            raise ValueError("No successful native source")
        row["source_url"] = receipt["url"]
        row["newly_acquired"] = True
        observations.append(row)
    held = directory / "held-washoe"
    rows = list(csv.DictReader(io.StringIO((held / "county-participation.csv").read_text())))
    modes = list(csv.DictReader(io.StringIO((held / "counting-group-participation.csv").read_text())))
    if len(rows) != 1 or rows[0]["county"] != "Washoe" or len(modes) != 6:
        raise ValueError("Changed held Washoe scope")
    native = rows[0]
    held_facts = json.loads(gzip.decompress((held / "source-records.json.gz").read_bytes()))
    first = held_facts["page_texts"][0]
    if not re.search(r"Voters Cast: 191,830 of 329,777 \(58.17%\)", first):
        raise ValueError("Held Washoe count no longer matches its complete native facts")
    observations.append(dict(county="Washoe", source_count=integer(native["ballots_cast"]),
        registered=integer(native["registered_voters"]), native_printed_pct=native["native_reported_percent"],
        source_measure_literal="Voters Cast", source_status_literal=native["source_status_literal"],
        source_clock_literal=native["source_generated_at"], source_clock_kind="native_PDF_generation",
        source_timezone=None, source_scope_literal=native["source_scope"],
        source_url=json.loads((held / "source-receipt.json").read_bytes())["url"],
        newly_acquired=False, legacy_record=native,
        source_modes=[dict(native_counting_group=row["native_counting_group"],
            source_count=integer(row["ballots"]), native_percent_of_register=row["native_reported_percent"],
            native_percent_of_source_total=None) for row in modes]))
    reference = json.loads((directory / "county-reference.json").read_bytes())
    geometry = json.loads(gzip.decompress((directory / "NV-full-county-reference.geojson.gz").read_bytes()))
    if (len(geometry["features"]) != 17 or len({f["properties"]["key"] for f in geometry["features"]}) != 17
            or reference["boundary_year"] != 2026):
        raise ValueError("Changed complete Nevada county reference")
    names = {row["county"]: row for row in observations}
    decisions = []
    for feature in sorted(geometry["features"], key=lambda f: f["properties"]["key"]):
        prop = feature["properties"]
        county = re.sub(r" County$", "", prop["name"])
        if prop["state_code"] != "NV" or not re.fullmatch(r"32\d{3}", prop["key"]):
            raise ValueError("Wrong reference jurisdiction")
        observed = names.get(county)
        decisions.append(dict(year=2026, state_code="NV", county=county,
            county_fips=prop["key"], reference_county_name=prop["name"],
            observed=observed is not None, source_count=None if observed is None else observed["source_count"],
            registered=None if observed is None else observed["registered"],
            analysis_rate=None, native_record=observed,
            qualification="native_county_source_snapshot" if observed else "no_qualified_native_participation_observation"))
    if sum(row["observed"] for row in decisions) != 4:
        raise ValueError("Missing or ambiguous direct county identity")
    pairs = json.loads((directory / "reference-review.json").read_bytes())
    if len(pairs["all136_county_pairs"]) != 136 or not pairs["all17_valid_without_repairs"]:
        raise ValueError("Incomplete full-reference geometry review")
    if any(row["positive_overlap_area_degrees_squared"] != 0 for row in pairs["all136_county_pairs"]):
        raise ValueError("Overlapping county reference")
    mode_rows = [dict(county=row["county"], **mode) for row in observations for mode in row["source_modes"]]
    summary = dict(reference_counties=17, observed_counties=4, unknown_counties=13,
        newly_acquired_counties=3, held_counties_reused=1, native_counting_group_rows=len(mode_rows),
        source_counts={row["county"]: row["source_count"] for row in observations},
        state_ballots=None, state_registration=None, approved_analysis_rates=0,
        new_precinct_counts=0, new_demographic_estimates=0,
        county_counts_not_added_across_different_source_clocks=True,
        candidate_votes_used_as_ballots=False, source_counts_repaired=False)
    return dict(summary=summary, county_decisions=decisions, native_counting_groups=mode_rows,
        all136_county_pairs=pairs["all136_county_pairs"], county_reference=reference,
        native_observations=observations,
        source_qualification="Distinct county snapshots, not statewide/final/unique-person turnout; "
            "native register definitions unqualified; all analysis rates and 13 unknown counts remain null.")


if __name__ == "__main__":
    import sys
    sys.stdout.buffer.write(encoded(load()))

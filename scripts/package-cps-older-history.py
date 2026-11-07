"""Reproduce the separate 2010-2016 Census state participation package offline."""

import argparse
from collections import Counter
from html.parser import HTMLParser
import importlib.util
import io
import json
import math
from pathlib import Path
from urllib.parse import urljoin
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DATA = "data/participation-cps-older-history/20261107-01"
SHARED = "scripts/package-cps-state-history.py"
SHARED_SHA = "4b0696dce79f6ffde7c95a9997208f46af4e1f3c34eaee22a0dcfcf20a0e7b90"
MANIFEST_SHA = "3d5b13f7a5fe3ba320a8fdca74dd759571f4583e2d5015b8d1a90c818b399fee"
CODE = (SHARED, "scripts/package-cps-older-history.py",
        "scripts/test-package-cps-older-history.py", "scripts/requirements-cps-older-history.txt")
YEARS = (2010, 2012, 2014, 2016)
AGES = {
    2010: ("Total", "18 to 24", "25 to 44", "45 to 64", "65 to 74", "75+"),
    2012: ("Total", "18 to 24", "25 to 34", "35 to 44", "45 to 64", "65+"),
    2014: ("Total", "18 to 24", "25 to 34", "35 to 44", "45 to 64", "65+"),
    2016: ("Total", "18 to 24", "25 to 34", "35 to 44", "45 to 64", "65+"),
}
AGE_VIEWS = ("18 to 24", "25 to 34", "35 to 44", "25 to 44", "45 to 64",
             "65+", "65 to 74", "75+")
STATUSES = ("published", "native_B_not_published", "withheld_small_rounded_population_base",
            "native_zero_or_rounds_to_zero", "not_native_age_bin_this_year")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def shared(root):
    import hashlib
    require(hashlib.sha256((root / SHARED).read_bytes()).hexdigest() == SHARED_SHA,
            "Frozen shared reader changed")
    spec = importlib.util.spec_from_file_location("cps_shared", root / SHARED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = set()

    def handle_starttag(self, tag, attributes):
        if tag == "a":
            href = dict(attributes).get("href")
            if href:
                self.hrefs.add(href)


def workbook(raw, suffix, module):
    if suffix == ".xlsx":
        return module.workbook(raw)
    import xlrd
    book = xlrd.open_workbook(file_contents=raw)
    require(book.nsheets == 1, "Unexpected legacy sheet inventory")
    sheet = book.sheet_by_index(0)
    require(sheet.ncols == 14, "Unexpected legacy columns")
    rows = {}
    for r in range(sheet.nrows):
        cells = {}
        for c in range(sheet.ncols):
            cell = sheet.cell(r, c)
            if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                continue
            require(cell.ctype in (xlrd.XL_CELL_NUMBER, xlrd.XL_CELL_TEXT),
                    "Unsupported native legacy cell")
            value = cell.value
            if cell.ctype == xlrd.XL_CELL_NUMBER:
                require(math.isfinite(value), "Nonfinite native cell")
                if value.is_integer():
                    value = int(value)
            cells[chr(65 + c)] = value
        if cells:
            rows[r + 1] = cells
    return rows


def disposition(native, year):
    pct, moe = native["voted_citizen_pct"], native["voted_citizen_moe90_pp"]
    base = native["adult_citizens_thousands"]
    if pct in ("B", "(B)") or moe in ("B", "(B)"):
        require(pct == moe and pct in ("B", "(B)"), "Inconsistent native suppression")
        return STATUSES[1], None, None
    require(base == "-" or type(base) in (int, float), "Invalid citizen population")
    if base == "-" or base <= (100 if year == 2016 else 75):
        return STATUSES[2], None, None
    if pct == "-":
        return STATUSES[3], None, None
    require(type(pct) in (int, float) and type(moe) in (int, float)
            and 0 <= pct <= 100 and 0 <= moe <= 100, "Invalid native rate/margin")
    return STATUSES[0], pct, moe


def parse_table(raw, year, table, filename, module):
    rows = workbook(raw, Path(filename).suffix, module)
    title_row, header_row = (1, 3) if year == 2010 else (2, 4 if year < 2016 else 5)
    title = rows[title_row]["A"]
    require(title.startswith(f"Table {table}.") and f"November {year}" in title
            and ("by Age" if table == "4c" else "by Sex, Race and Hispanic Origin") in title,
            "Unexpected native title/year")
    major, header = rows[4] if year == 2016 else rows[header_row], rows[header_row]
    require(major["C"] == "Total Population" and major["D"] == "Total Citizen Population"
            and header["E"] == "Total registered" and header["J"] == "Total voted"
            and header["M"] == "Percent voted\n(Citizen)"
            and header["N"].startswith("Margin of Error"), "Native denominator/schema changed")
    notes = [row["A"] for number, row in sorted(rows.items())
             if number > header_row and isinstance(row.get("A"), str)
             and not row.get("B") and row["A"].strip()]
    limit = 100 if year == 2016 else 75
    require(any("90-percent confidence interval" in note for note in notes)
            and any(f"less than {limit},000" in note for note in notes)
            and any("zero or rounds to zero" in note for note in notes)
            and any(f"November {year}" in note for note in notes), "Native notes changed")
    expected = module.B_GROUPS if table == "4b" else AGES[year]
    state_map = {name.upper(): name for name in module.NAMES}
    result, state = [], None
    for number, row in sorted(rows.items()):
        if number <= header_row or not row.get("B"):
            continue
        label = row.get("A")
        if label:
            if label in ("US", "All", "UNITED STATES"):
                state = module.STATES[0]
            else:
                require(label in state_map, "Unknown native state")
                state = state_map[label]
        require(state is not None, "Missing state context")
        group = {".White non-Hispanic alone": "White non-Hispanic alone",
                 "Hispanic (of any race)": "Hispanic (any race)"}.get(row["B"], row["B"])
        require(group in expected, "Unknown or incompatible native group")
        values = {metric: row.get(column)
                  for column, metric in zip("CDEFGHIJKLMN", module.METRICS)}
        for metric, value in values.items():
            require((type(value) in (int, float) and value >= 0)
                    or value in ("B", "(B)", "-"), "Missing or unexpected native metric")
            if type(value) in (int, float) and ("pct" in metric or "moe90" in metric):
                require(value <= 100, "Invalid percentage/margin")
        status, pct, moe = disposition(values, year)
        result.append({"year": year, "table": table, "file": filename, "source_row": number,
                       "state": state, "group": group, "native_group": row["B"],
                       "display_status": status, "display_reported_voting_pct": pct,
                       "display_native_moe90_pp": moe, **values})
    require(len(result) == len(module.STATES) * len(expected)
            and {(r["state"], r["group"]) for r in result}
            == {(state, group) for state in module.STATES for group in expected},
            "Incomplete or duplicate native coverage")
    return result, {"year": year, "table": table, "title": title, "notes": notes,
                    "citizen_base_display_withhold_thousands": limit,
                    "native_group_order": list(expected), "file": filename}


def review(root=ROOT):
    module = shared(root)
    directory = root / DATA
    raw = (directory / "sources.json").read_bytes()
    require(module.digest(raw) == MANIFEST_SHA, "Frozen source manifest changed")
    manifest = json.loads(raw)
    require(manifest["native_acquisition_passed"] and len(manifest["receipts"]) == 12
            and len(manifest["declarations"]) == 8, "Incomplete native inventory")
    inputs, receipts = {"sources.json": raw}, {}
    safe_headers = {"Content-Type", "Content-Length", "Last-Modified", "ETag",
                    "Date", "Content-Disposition"}
    for receipt in manifest["receipts"]:
        filename = receipt["file"]
        require(Path(filename).name == filename and filename not in receipts, "Invalid source path")
        native = (directory / filename).read_bytes()
        require(module.digest(native) == receipt["sha256"] and len(native) == receipt["bytes"]
                and receipt["http_status"] == 200 and receipt["requested_url"] == receipt["final_url"]
                and set(receipt["http_headers"]) <= safe_headers, "Frozen source receipt mismatch")
        receipts[filename] = receipt
        inputs[filename] = native
    all_rows, definitions = [], []
    require({(d["year"], d["table"]) for d in manifest["declarations"]}
            == {(year, table) for year in YEARS for table in ("4b", "4c")},
            "Incomplete declaration inventory")
    for source in manifest["declarations"]:
        year, table, filename = source["year"], source["table"], source["file"]
        catalog = receipts[f"catalog-{year}.html"]
        require(receipts[filename]["requested_url"] == source["declared_url"]
                and receipts[filename]["declared_by"] == source["catalog_url"]
                and catalog["requested_url"] == source["catalog_url"], "Declaration chain mismatch")
        links = Links()
        links.feed(inputs[f"catalog-{year}.html"].decode())
        require(source["declared_url"] in {urljoin(source["catalog_url"], h) for h in links.hrefs},
                "Workbook not declared by actual native catalog")
        rows, definition = parse_table(inputs[filename], year, table, filename, module)
        all_rows.extend(rows)
        definitions.append(definition)
    lookup = {(r["year"], r["state"], r["group"], r["table"]): r for r in all_rows}
    for year in YEARS:
        for state in module.STATES:
            require(all(lookup[year, state, "Total", "4b"][metric]
                        == lookup[year, state, "Total", "4c"][metric]
                        for metric in module.METRICS), "Duplicate overall controls differ")
    rows = [r for r in all_rows if r["table"] == "4b" or r["group"] != "Total"]
    groups = (*module.B_GROUPS, *AGE_VIEWS)
    rows.sort(key=lambda r: (module.STATES.index(r["state"]), groups.index(r["group"]), r["year"]))
    require(len(rows) == 3328 and len(lookup) == 3536, "Incomplete retained/native coverage")
    limits = [
        "2010/2014 are midterms; 2012/2016 presidential elections. These are repeated cross-sections.",
        "Native 2010 ages 25-44,65-74,75+ are not the later age bins. Unsupported year/group combinations stay unavailable; no split bins or combined margins are invented.",
        "Native citizen-population B threshold is 100000 in2016,75000 earlier. Population base is NOT respondent sample size/effective n. Display also withholds the rounded boundary and smaller bases; this is not a precision guarantee.",
        "B and (B) retain literal source suppression; dash means zero or rounds to zero. Never recover suppressed cells or replace dash with an inferred exact zero.",
        "Native percentages and 90% margins are transcribed, never calculated from rounded thousands. Margins do not describe cross-year differences, simultaneous intervals or nonsampling errors.",
        "The native civilian noninstitutionalized adult citizen population is not established legal eligibility. Self/proxy-reported voting can over-report administrative participation.",
        "Sex,race-alone,race-in-combination,Hispanic and age are separate overlapping views,not intersections or an exclusive partition. Education,income,urbanicity are absent.",
        "Native US includes D.C. and is not reconstructed by summing rounded states. Current attributes and changing population controls do not establish fixed-person cohorts.",
        "No2026participation,individual switching,measured stayinghome,first-time/returning identity,county/precinct estimates,causal effects or group-difference significance is established.",
        "Full native governmental tables and transcription retain small-base cells; those are not qualified display estimates. Historical acquisition-only flags in sources.json are preserved provenance,not a replacement for this package's checks.",
        "The complete separate 2018-2024 package is unchanged. No source clocks,revisions,age groups or fieldwork are blended.",
        "Offline: install scripts/requirements-cps-older-history.txt,run python scripts/test-package-cps-older-history.py and python scripts/package-cps-older-history.py --output NEW_DIRECTORY.",
    ]
    summary = {
        "status": "published_historical_CPS_self_report_not_2026_or_individual_transitions",
        "years": list(YEARS), "states_and_DC": 51, "national_scope": module.STATES[0],
        "groups": list(groups), "unique_observations": len(rows),
        "native_rows_including_duplicate_overall_controls": len(all_rows),
        "duplicate_overall_controls_verified": 208,
        "display_dispositions": dict(sorted(Counter(r["display_status"] for r in rows).items())),
        "denominator": "Native civilian noninstitutionalized adult citizen population, not legal eligibility.",
        "units": "Native weighted counts in thousands; rates and native90% margins in percentage points.",
        "native_definitions": definitions, "limits": limits,
    }
    keyed = {(r["state"], r["group"], r["year"]): r for r in rows}
    display = {"years": list(YEARS), "states": list(module.STATES), "groups": list(groups),
               "statuses": list(STATUSES), "values": []}
    for state in module.STATES:
        state_values = []
        for group in groups:
            values = []
            for year in YEARS:
                row = keyed.get((state, group, year))
                values.append([-4] if row is None else (
                    [row["display_reported_voting_pct"], row["display_native_moe90_pp"]]
                    if row["display_status"] == STATUSES[0]
                    else [-STATUSES.index(row["display_status"])]))
            state_values.append(values)
        display["values"].append(state_values)
    return rows, summary, display, inputs


def package(root=ROOT, output=None):
    module = shared(root)
    rows, summary, display, inputs = review(root)
    members = {f"{DATA}/{name}": raw for name, raw in inputs.items()}
    members.update({name: (root / name).read_bytes() for name in CODE})
    members.update({"results/observations.csv": module.csv_bytes(rows),
                    "results/review.json": module.encoded(summary),
                    "results/display.json": module.encoded(display, compact=True),
                    "METHODOLOGY.txt": ("\n\n".join([summary["denominator"], summary["units"],
                                                    *summary["limits"]]) + "\n").encode()})
    members["checksums.json"] = module.encoded({
        name: {"bytes": len(raw), "sha256": module.digest(raw)}
        for name, raw in sorted(members.items())})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(members.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw, compresslevel=9)
    raw = stream.getvalue()
    result = {"bytes": len(raw), "sha256": module.digest(raw), "members": len(members),
              "unique_observations": len(rows), "source_workbooks": 8, "source_catalogs": 4}
    destination = Path(output) if output else root / DATA / "output"
    outputs = {"observations.csv": members["results/observations.csv"],
               "review.json": members["results/review.json"], "display.json": members["results/display.json"],
               "complete-analysis.zip": raw, "archive.json": module.encoded(result)}
    for name, content in outputs.items():
        if (destination / name).exists():
            require((destination / name).read_bytes() == content, f"Frozen output changed: {name}")
    for name, content in outputs.items():
        module.frozen_write(destination / name, content)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.root, args.output), indent=2))

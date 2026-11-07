"""Reproduce the separate 2004/2006/2008 Census participation package offline."""

import argparse
from collections import Counter
import csv
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import math
from pathlib import Path
from urllib.parse import urljoin
import zipfile

import xlrd


ROOT = Path(__file__).resolve().parents[1]
DATA = "data/participation-cps-early-history/20261107-01"
SHARED = "scripts/package-cps-state-history.py"
SHARED_SHA = "4b0696dce79f6ffde7c95a9997208f46af4e1f3c34eaee22a0dcfcf20a0e7b90"
MANIFEST_SHA = "a825beb5690259e58819eaef3bb62c94e53dbd5e5f0a2f1cb8a6d412f01e6c35"
CODE = (SHARED, "scripts/package-cps-early-history.py",
        "scripts/test-package-cps-early-history.py", "scripts/requirements-cps-older-history.txt")
PINS = {
    "2004-table4a.xls": "790a565b8556410403e36ae5816bfad31f56653cd503f23768aaba61fc45f9ee",
    "2004-table4b.xls": "5a188bfa4160498599e62b53f5cfceb6b5bd4556c37e27abc862f6933af74535",
    "2006-table4b.xls": "494e46569849ad11bcdc91b6c6b6f9896bde17bb4cde5599cff03d7a5861b7a5",
    "2008-table4b.xls": "105678634d1af9dd2ee10f04872d6547df015d254c5c440f159128a4952f5015",
    "2008-table4c.xls": "9c19941a037c81aa554f89adaced2cf673280dd352a18b3fc889d4f8206ba720",
}
BASE_GROUPS = (
    ".Total", ".Male", ".Female", ".White alone", "..White non-Hispanic alone",
    ".Black alone", ".Asian alone", ".Hispanic (of any race)",
    ".White alone or in combination", ".Black alone or in combination ",
    ".Asian alone or in combination",
)
EARLY_GROUPS = BASE_GROUPS[:9] + ("..White non-Hispanic alone or in combination",) + BASE_GROUPS[9:]
AGE_OLD = (".Total", ".18 to 24", ".25 to 44", ".45 to 64", ".65 to 74", ".75+")
AGE_US = (".Total", ".18 to 24", ".25 to 34", ".35 to 44", ".45 to 54", ".55 to 64", ".65 to 74", ".75+")
AGE_COLLAPSED = (".Total", ".18 to 44", ".45 to 64", ".65+")
COLLAPSED_STATES = (
    "ALASKA", "DELAWARE", "DISTRICT OF COLUMBIA", "IDAHO", "MONTANA",
    "NORTH DAKOTA", "RHODE ISLAND", "SOUTH DAKOTA", "VERMONT", "WYOMING",
)
METRICS_2004 = (
    "adults_thousands", "adult_citizens_thousands", "citizen_adults_pct",
    "citizen_adults_moe90_pp", "registered_thousands", "registered_adults_pct",
    "registered_adults_moe90_pp", "voted_thousands", "voted_adults_pct", "voted_adults_moe90_pp",
)
METRICS_LATER = (
    "adults_thousands", "adult_citizens_thousands", "registered_thousands",
    "registered_adults_pct", "registered_adults_moe90_pp", "registered_citizens_pct",
    "registered_citizens_moe90_pp", "voted_thousands", "voted_adults_pct",
    "voted_adults_moe90_pp", "voted_citizens_pct", "voted_citizens_moe90_pp",
)
PAIR_EXCEPTIONS = {
    ("2006-table4b.xls", 171, "registered_citizens_pct"): 11.7,
    ("2006-table4b.xls", 171, "voted_citizens_pct"): 9.6,
    ("2008-table4b.xls", 207, "registered_citizens_pct"): 18.3,
    ("2008-table4b.xls", 207, "voted_citizens_pct"): 18.7,
    ("2008-table4b.xls", 243, "registered_citizens_pct"): 21.7,
    ("2008-table4b.xls", 243, "voted_citizens_pct"): 23,
    ("2008-table4b.xls", 351, "registered_citizens_pct"): 17.2,
    ("2008-table4b.xls", 351, "voted_citizens_pct"): 17.5,
    ("2008-table4b.xls", 507, "registered_citizens_pct"): 22,
    ("2008-table4b.xls", 507, "voted_citizens_pct"): 22.1,
    ("2008-table4c.xls", 93, "voted_citizens_pct"): 7.6,
}
CONFLICTS = {
    (2008, "FLORIDA"): {"voted_citizens_pct": [63.8, 64.2]},
    (2008, "GEORGIA"): {"voted_citizens_pct": [64.2, 51.8]},
    (2008, "HAWAII"): {"voted_citizens_pct": [51.8, 61.4]},
}
LIMITS = [
    "Census CPS Voting and Registration Supplement, November 2004/2006/2008. 2006 is a midterm; 2004/2008 are presidential elections. These are repeated cross-sections, not fixed-person cohorts.",
    "2004 native rates/MOEs use ALL adults18+, not citizen adults. No citizen voting rate/MOE is derived from rounded counts. Do not splice adult and citizen rates into one comparable series.",
    "2006/2008 use native citizen-adult voting rates. Civilian noninstitutionalized citizen adults are not established legal eligibility. Self/proxy-reported voting can over-report administrative participation.",
    "Counts are native weighted population estimates in rounded thousands, NOT respondent n/effective n. Native percentages/MOEs are never recalculated from those counts.",
    "Native90% margins do not establish precision for cross-year differences, simultaneous intervals, nonsampling error or significance of group differences.",
    "Sex,race-alone,race-in-combination,Hispanic and age views overlap. They are not intersections or an exclusive partition. These tables do not supply education,income or urbanicity.",
    "Native(B) suppression and dash(zero or rounds to zero) remain literal. Do not recover suppressed rates or replace dash by an exact zero. Eleven suppressed-rate/numeric-margin pairs are retained, never used to recover missing rates.",
    "2006/2008sex-race notes state a75000population suppression base. 2004/2008age notes do not supply a numeric threshold. The additional citizen-base<=75000 display screen is not native respondent support or a precision guarantee.",
    "2006/2008first sex-race blocks have no native geography label; all22rows are display-withheld. 2008first total matches every explicit national age-total metric, but this does not create a native national label.",
    "Arizona2004extra.Non-HispanicWhite row duplicates White-alone values; preserve all literal rows and withhold the ambiguous extra row, not alias/delete it.",
    "SouthDakota2008White-alone-or-combination citizen registration percentage is literal423. Preserve and flag it; withhold the row's voting display rather than silently repair source data.",
    "2008Florida/Georgia/Hawaii total citizen voting rates disagree between sex-race and age tables. Preserve BOTH native vectors and withhold BOTH total voting displays for each state. 104control pairs comprise101agreeing and3conflicting pairs, not104matching pairs.",
    "Native2004age bins are18-24/25-44/45-64/65-74/75+. 2008US uses18-24/25-34/35-44/45-54/55-64/65-74/75+;41larger states use2004bins;10small jurisdictions use18-44/45-64/65+. No common-bin splitting or combined margins are invented.",
    "2008age notes literally refer toTable4b and say Internet Release date: Month xx,2009. Both are retained; no release date is imputed. Native geography suffix2 is normalized only for the10specified small jurisdictions.",
    "2006state-age table is not declared in THIScatalog; this is not evidence that no other native table exists. Unsupported combinations remain unavailable, not zero.",
    "All2375native observations and26626metric cells, including104repeated total-control pairs and unqualified/small-base rows, are retained. Repeated controls are not independent observations. Qualified displays do not promote the remaining native rows.",
    "NativeUS scope includesDC where explicitly labeled. Do not reconstruct national values by summing rounded states. Current attributes and changing populations do not establish fixed demographic cohorts.",
    "No2026participation,individual switching,measured stayinghome,first-time/returning identity,county/precinct demographic rates,causal effects or cross-year significance is established.",
    "All eight frozen governmental originals and complete sanitized native receipts are included with attribution toU.S.CensusBureau. Historical acquisition-only qualification flags remain provenance, not this package's publication decision. Existing2010-2024packages remain unchanged.",
    "Offline: install scripts/requirements-cps-older-history.txt; run python scripts/test-package-cps-early-history.py and python scripts/package-cps-early-history.py --output NEW_DIRECTORY from the extracted archive root. The package reextracts every XLS metric, not just selected JSON results.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value, compact=False):
    return (json.dumps(value, sort_keys=True, allow_nan=False, ensure_ascii=True,
                       indent=None if compact else 2,
                       separators=(",", ":") if compact else None) + "\n").encode()


def shared(root):
    path = root / SHARED
    require(sha(path.read_bytes()) == SHARED_SHA, "Frozen state-name reference changed")
    spec = importlib.util.spec_from_file_location("cps_state_names", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = set()

    def handle_starttag(self, tag, attributes):
        if tag == "a" and dict(attributes).get("href"):
            self.hrefs.add(dict(attributes)["href"])


def parse_table(raw, declaration, state_names):
    filename, year, role = declaration["file"], declaration["year"], declaration["role"]
    require(sha(raw) == PINS[filename], "Changed frozen workbook")
    book = xlrd.open_workbook(file_contents=raw)
    require(book.nsheets == 1, "Unexpected sheet inventory")
    sheet = book.sheet_by_index(0)
    metrics = METRICS_2004 if year == 2004 else METRICS_LATER
    require(sheet.ncols == len(metrics) + 1, "Unexpected metric columns")
    title = sheet.cell_value(1, 0)
    require(title.startswith("Table " + declaration["table"] + ".")
            and f"November {year}" in title
            and ("by Age" if role == "age" else "by Sex, Race and Hispanic Origin") in title,
            "Changed native table meaning")
    require(sheet.cell_value(2, 0) == "(In thousands)", "Changed native units")
    major, minor = sheet.row_values(4), sheet.row_values(5)
    if year == 2004:
        require(major[1:] == ["Population 18 and over", "Total citizen", "", "",
                "Total registered", "", "", "Total voted", "", ""], "Changed adult schema")
        require(minor[1:] == ["", "Total  ", "Percent citizen (18+)", "Margin of error1",
                "Total  ", "Percent registered (18+)", "Margin of error1", "Total  ",
                "Percent voted (18+)", "Margin of error1"], "Changed adult denominators")
    else:
        require(major[1:] == ["Total Population", "Total Citizen Population", "Registered",
                "", "", "", "", "Total Voted", "", "", "", ""], "Changed population schema")
        require(minor[1:] == ["", "", "Total Registered", "Percent registered (Total 18+)",
                "Margin of error1", "Percent registered (Citizen 18+)", "Margin of error1",
                "Total Voted", "Percent voted (Total 18+)", "Margin of error1",
                "Percent voted (Citizen 18+)", "Margin of error1"], "Changed citizen denominators")
    blocks, notes, observations, exceptions = [], [], [], {}
    block = None
    for index in range(6, sheet.nrows):
        row = sheet.row_values(index)
        label = row[0]
        if type(row[1]) in (int, float) or row[1] == "-":
            if block is None:
                require(index == 7 and year in (2006, 2008) and role == "sex_race",
                        "Unexpected missing geography")
                block = {"native_geography": None, "geography": "UNLABELED_FIRST_BLOCK", "rows": []}
                blocks.append(block)
            require(isinstance(label, str) and label.startswith("."), "Unknown native row label")
            values = {}
            for column, metric in enumerate(metrics, 1):
                cell = sheet.cell(index, column)
                value = cell.value
                require(cell.ctype in (xlrd.XL_CELL_TEXT, xlrd.XL_CELL_NUMBER),
                        "Unsupported metric cell type")
                if cell.ctype == xlrd.XL_CELL_NUMBER:
                    require(math.isfinite(value) and value >= 0, "Invalid native number")
                    if value.is_integer():
                        value = int(value)
                    if metric.endswith(("_pct", "_pp")):
                        require(value <= 100 or (filename, index + 1, metric, value)
                                == ("2008-table4b.xls", 520, "registered_citizens_pct", 423),
                                "Unreviewed invalid native percentage")
                else:
                    require(value in ("(B)", "-"), "Unknown native nonnumeric symbol")
                values[metric] = value
            record = {
                "year": year, "table": declaration["table"], "role": role, "file": filename,
                "source_row": index + 1, "native_group": label,
                "native_geography": block["native_geography"], "geography": block["geography"],
                "native": values,
                "native_out_of_range_metrics": [
                    key for key, value in values.items()
                    if key.endswith(("_pct", "_pp")) and type(value) in (int, float) and value > 100],
                "native_suppression_pair_anomalies": [],
            }
            for metric in metrics:
                if metric.endswith("_pct"):
                    margin = metric.removesuffix("_pct") + "_moe90_pp"
                    if (values[metric] == "(B)") != (values[margin] == "(B)"):
                        key = (filename, index + 1, metric)
                        require(values[metric] == "(B)" and PAIR_EXCEPTIONS.get(key) == values[margin],
                                "Unreviewed native suppression-pair anomaly")
                        exceptions[key] = values[margin]
                        record["native_suppression_pair_anomalies"].append(metric)
            block["rows"].append(record)
            observations.append(record)
        elif label and all(value == "" for value in row[1:]):
            geography = label
            if year == 2008 and role == "age" and label.endswith(" 2"):
                require(label[:-2] in COLLAPSED_STATES, "Unexpected geography footnote")
                geography = label[:-2]
            if geography in state_names or geography == "UNITED STATES":
                block = {"native_geography": label, "geography": geography, "rows": []}
                blocks.append(block)
            else:
                notes.append({"source_row": index + 1, "literal": label})
        else:
            require(all(value == "" for value in row), "Unparsed nonempty native row")
    require(len(blocks) == 52 and {b["geography"] for b in blocks[1:]} == state_names,
            "Incomplete 50-state/DC inventory")
    require(blocks[0]["geography"] == (
        "UNLABELED_FIRST_BLOCK" if role == "sex_race" and year > 2004 else "UNITED STATES"),
        "Unexpected first block label")
    for block in blocks:
        if role == "sex_race":
            expected = EARLY_GROUPS if year == 2004 else BASE_GROUPS
            if year == 2004 and block["geography"] == "ARIZONA":
                expected = expected[:3] + (".Non-Hispanic White",) + expected[3:]
        else:
            expected = AGE_OLD
            if year == 2008:
                if block["geography"] == "UNITED STATES":
                    expected = AGE_US
                elif block["geography"] in COLLAPSED_STATES:
                    expected = AGE_COLLAPSED
        require(tuple(r["native_group"] for r in block["rows"]) == expected,
                "Changed or collapsed native group schema")
    all_notes = "\n".join(note["literal"] for note in notes)
    require("90-percent confidence interval" in all_notes and "zero or rounds to zero" in all_notes
            and f"November {year}" in all_notes, "Missing source/statistical notes")
    if role == "sex_race" and year > 2004:
        require("less than 75,000" in all_notes, "Missing explicit suppression definition")
    if year == 2008 and role == "age":
        require("Table 4b utilizes a collapsed set of age-groups" in all_notes
                and "Month xx, 2009" in all_notes, "Altered native footnote/release placeholder")
    definition = {
        "file": filename, "year": year, "role": role, "title": title,
        "major_header": major, "minor_header": minor, "metric_names": list(metrics),
        "notes": notes, "sheet_name": sheet.name, "native_rows": len(observations),
        "citizen_voting_rate_supplied": year != 2004,
        "numeric_suppression_threshold_supplied": 75000 if role == "sex_race" and year > 2004 else None,
    }
    return observations, definition, exceptions


def qualify(observations, state_names):
    extra = [r for r in observations if r["year"] == 2004 and r["geography"] == "ARIZONA"
             and r["native_group"] == ".Non-Hispanic White"]
    require(len(extra) == 1, "Missing literal extra Arizona row")
    white = next(r for r in observations if r["year"] == 2004 and r["geography"] == "ARIZONA"
                 and r["native_group"] == ".White alone")
    require(extra[0]["native"] == white["native"], "Changed Arizona label conflict")
    invalid = [r for r in observations if r["native_out_of_range_metrics"]]
    require(len(invalid) == 1 and invalid[0]["geography"] == "SOUTH DAKOTA"
            and invalid[0]["native_group"] == ".White alone or in combination"
            and invalid[0]["native_out_of_range_metrics"] == ["registered_citizens_pct"],
            "Changed literal out-of-range metric inventory")
    controls, withheld = [], set()
    for year in (2004, 2008):
        totals = [r for r in observations if r["year"] == year and r["native_group"] == ".Total"]
        for state in ("UNITED STATES", *sorted(state_names)):
            sex_geo = "UNLABELED_FIRST_BLOCK" if year == 2008 and state == "UNITED STATES" else state
            left = next(r for r in totals if r["role"] == "sex_race" and r["geography"] == sex_geo)
            right = next(r for r in totals if r["role"] == "age" and r["geography"] == state)
            differences = {key: [left["native"][key], right["native"][key]]
                           for key in left["native"] if left["native"][key] != right["native"][key]}
            require(differences == CONFLICTS.get((year, state), {}),
                    "Unreviewed conflicting same-year total controls")
            if differences:
                withheld.update((r["file"], r["source_row"]) for r in (left, right))
            controls.append({
                "year": year, "geography": state, "left_file": left["file"],
                "left_row": left["source_row"], "right_file": right["file"],
                "right_row": right["source_row"],
                "equivalent_metrics": len(left["native"]) - len(differences),
                "literal_conflicting_metrics": differences,
            })
    for record in observations:
        denominator = "all_adults_18_plus" if record["year"] == 2004 else "citizen_adults_18_plus"
        prefix = "voted_adults" if record["year"] == 2004 else "voted_citizens"
        rate, moe = record["native"][prefix + "_pct"], record["native"][prefix + "_moe90_pp"]
        if record is extra[0]:
            status = "withheld_conflicting_extra_native_label"
        elif record["native_out_of_range_metrics"]:
            status = "withheld_native_out_of_range_metric"
        elif (record["file"], record["source_row"]) in withheld:
            status = "withheld_conflicting_same_year_total"
        elif record["geography"] == "UNLABELED_FIRST_BLOCK":
            status = "withheld_unlabeled_native_geography"
        elif rate == "(B)":
            status = "native_B_not_published"
        elif rate == "-":
            status = "native_zero_or_rounds_to_zero"
        elif denominator == "citizen_adults_18_plus" and record["native"]["adult_citizens_thousands"] <= 75:
            status = "withheld_small_rounded_population_base"
        else:
            status = "published_native_rate"
        record["display"] = {
            "status": status, "denominator": denominator,
            "rate_pct": rate if status == "published_native_rate" else None,
            "native_moe90_pp": moe if status == "published_native_rate" else None,
            "not_a_2026_or_fixed_cohort_estimate": True,
        }
    return controls


def review(root=ROOT):
    module = shared(root)
    state_names = {name.upper() for name in module.NAMES}
    directory = root / DATA
    manifest_raw = (directory / "sources.json").read_bytes()
    require(sha(manifest_raw) == MANIFEST_SHA, "Frozen source manifest changed")
    manifest = json.loads(manifest_raw)
    require(manifest["native_acquisition_passed"] and manifest["workbooks"] == 5
            and len(manifest["receipts"]) == 8 and len(manifest["declarations"]) == 5,
            "Incomplete acquisition")
    inputs, receipts = {"sources.json": manifest_raw}, {}
    safe_headers = {"Content-Type", "Content-Length", "Last-Modified", "ETag", "Date", "Content-Disposition"}
    for receipt in manifest["receipts"]:
        filename = receipt["file"]
        require(Path(filename).name == filename and filename not in receipts, "Invalid source path")
        raw = (directory / filename).read_bytes()
        require(receipt["http_status"] == 200 and len(raw) == receipt["bytes"]
                and sha(raw) == receipt["sha256"]
                and receipt["requested_url"] == receipt["final_url"]
                and set(receipt["http_headers"]) <= safe_headers, "Source byte/receipt mismatch")
        inputs[filename], receipts[filename] = raw, receipt
    require({d["file"] for d in manifest["declarations"]} == set(PINS), "Wrong sources")
    observations, definitions, actual_exceptions = [], [], {}
    for declaration in manifest["declarations"]:
        filename, year = declaration["file"], declaration["year"]
        catalog = receipts[f"catalog-{year}.html"]
        require(catalog["requested_url"] == declaration["catalog_url"]
                and receipts[filename]["requested_url"] == declaration["declared_url"]
                and receipts[filename]["declared_by"] == declaration["catalog_url"],
                "Declaration chain mismatch")
        links = Links()
        links.feed(inputs[f"catalog-{year}.html"].decode())
        require(declaration["declared_url"] in {
            urljoin(declaration["catalog_url"], href) for href in links.hrefs},
            "Workbook not declared by actual native catalog")
        rows, definition, exceptions = parse_table(inputs[filename], declaration, state_names)
        observations.extend(rows)
        definitions.append(definition)
        actual_exceptions.update(exceptions)
    require(len(observations) == 2375 and sum(len(r["native"]) for r in observations) == 26626,
            "Incomplete native metric inventory")
    require(actual_exceptions == PAIR_EXCEPTIONS, "Incomplete suppression anomaly inventory")
    controls = qualify(observations, state_names)
    summary = {
        "status": "qualified_historical_CPS_self_report_not_2026_or_individual_transitions",
        "years": [2004, 2006, 2008], "states_and_DC": 51,
        "native_observations_including_repeated_controls": len(observations),
        "native_metric_cells": 26626, "duplicate_controls": controls,
        "compared_total_controls": len(controls),
        "agreeing_total_controls": sum(not c["literal_conflicting_metrics"] for c in controls),
        "conflicting_total_controls": sum(bool(c["literal_conflicting_metrics"]) for c in controls),
        "native_definitions": definitions, "catalog_dispositions": manifest["catalog_dispositions"],
        "display_status_counts": dict(sorted(Counter(r["display"]["status"] for r in observations).items())),
        "source_acquisition_sha256": sha(manifest_raw), "limits": LIMITS,
        "public_qualification": "Historical native aggregate transcription and conservative display only.",
        "individual_or_2026_transitions_qualified": False,
    }
    display = [
        {key: record[key] for key in ("year", "table", "role", "file", "source_row",
                                     "geography", "native_geography", "native_group", "display")}
        for record in observations
    ]
    return observations, summary, display, inputs


def csv_bytes(observations):
    metrics = tuple(dict.fromkeys((*METRICS_2004, *METRICS_LATER)))
    fields = ("year", "table", "role", "file", "source_row", "geography", "native_geography",
              "native_group", "display_status", "display_denominator", "display_rate_pct",
              "display_native_moe90_pp", "native_out_of_range_metrics",
              "native_suppression_pair_anomalies", *metrics)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for record in observations:
        row = {key: record[key] for key in fields[:8]}
        row.update({"display_" + key: value for key, value in record["display"].items()
                    if key in ("status", "denominator", "rate_pct", "native_moe90_pp")})
        row.update({key: "|".join(record[key]) for key in
                    ("native_out_of_range_metrics", "native_suppression_pair_anomalies")})
        row.update(record["native"])
        writer.writerow(row)
    return stream.getvalue().encode()


def package(root=ROOT, output=None):
    module = shared(root)
    observations, summary, display, inputs = review(root)
    members = {f"{DATA}/{name}": raw for name, raw in inputs.items()}
    members.update({name: (root / name).read_bytes() for name in CODE})
    members.update({
        "results/observations.json": encoded(observations),
        "results/observations.csv": csv_bytes(observations),
        "results/review.json": encoded(summary),
        "results/display.json": encoded(display, compact=True),
        "METHODOLOGY.txt": ("\n\n".join(LIMITS) + "\n").encode(),
    })
    members["checksums.json"] = encoded({
        name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in sorted(members.items())})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(members.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw, compresslevel=9)
    raw = stream.getvalue()
    result = {"bytes": len(raw), "sha256": sha(raw), "members": len(members),
              "native_observations": len(observations), "native_metric_cells": 26626,
              "source_workbooks": 5, "source_catalogs": 3}
    destination = Path(output) if output else root / DATA / "output"
    outputs = {"observations.json": members["results/observations.json"],
               "observations.csv": members["results/observations.csv"],
               "review.json": members["results/review.json"], "display.json": members["results/display.json"],
               "complete-analysis.zip": raw, "archive.json": encoded(result)}
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

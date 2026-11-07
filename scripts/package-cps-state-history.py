"""Reproduce published state demographic CPS histories offline, without microdata."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DATA = "data/participation-cps-state-history/20261107-01"
CODE = ("scripts/package-cps-state-history.py", "scripts/test-package-cps-state-history.py")
YEARS = (2018, 2020, 2022, 2024)
PINS = {
    (2018, "4b"): "0a7aa533c7c571f269a0138400118d9d26982e2effce52ba82359f730975af02",
    (2018, "4c"): "76a3a0dc48631f7c70eb173d45dc337293514ea3f80aa06f80238940452de381",
    (2020, "4b"): "15fbea6da2024009f7d4c2e9914e2e9b087e4e96c4e2b695aac0e6512bc81688",
    (2020, "4c"): "680ec052d70101259bd1052e7a79cc70e4d8c446546cb02b189e219fadd6482f",
    (2022, "4b"): "9f9e7f12e4232955f35290700ed62c02d14ded6b20004bf7f5a32199412bbbc5",
    (2022, "4c"): "48de128c98e345cafa0f47110afa9922a789973e3b543952f7f4aed8a4884d08",
    (2024, "4b"): "fa33c7db6986e49eab1b1930fa1e9bd64f966b9be74a056d0e237cbc1431155b",
    (2024, "4c"): "dacbb628705ba82e578531b227ef3d82925027491bdbc13067a6c86525992b8e",
}
CATALOG_PINS = {
    2018: "c6378dfb46229c1f90e980f63c5df76796d54d575ab04eee2b2d364f373efae3",
    2020: "ed9359613ebd4e5f69fffa2512917e24f8288f2316500afeacaf2063c3144150",
    2022: "d1db6978ed9e0b7d94befbaebfa38671fb1829c785d732f18bffa4e31e06317b",
    2024: "7849b11c17b2fcf3aaf350261504cabe14f86ecf572d61cdf8863947701f1ade",
}
NAMES = (
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Delaware", "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
    "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri",
    "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico",
    "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee",
    "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin",
    "Wyoming",
)
STATES = ("United States (including D.C.)", *NAMES)
B_GROUPS = (
    "Total", "Male", "Female", "White alone", "White non-Hispanic alone", "Black alone",
    "Asian alone", "Hispanic (any race)", "White alone or in combination",
    "Black alone or in combination", "Asian alone or in combination",
)
C_GROUPS = ("Total", "18 to 24", "25 to 34", "35 to 44", "45 to 64", "65+")
GROUPS = (*B_GROUPS, *C_GROUPS[1:])
METRICS = (
    "adult_population_thousands", "adult_citizens_thousands", "registered_thousands",
    "registered_resident_pct", "registered_resident_moe90_pp", "registered_citizen_pct",
    "registered_citizen_moe90_pp", "reported_voters_thousands", "voted_resident_pct",
    "voted_resident_moe90_pp", "voted_citizen_pct", "voted_citizen_moe90_pp",
)
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
STATUSES = ("published", "native_B_not_published", "withheld_small_rounded_population_base",
            "native_zero_or_rounds_to_zero")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value, compact=False):
    return (json.dumps(value, allow_nan=False, ensure_ascii=True,
                       indent=None if compact else 2,
                       separators=(",", ":") if compact else None) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def workbook(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), "Duplicate XLSX members")
        require([name for name in archive.namelist()
                 if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)]
                == ["xl/worksheets/sheet1.xml"], "Unexpected worksheet inventory")
        strings = ["".join(node.itertext()) for node in
                   ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        require(not sheet.findall(".//s:f", NS), "Cached formulas are not published source values")
        rows = {}
        for cell in sheet.findall(".//s:sheetData/s:row/s:c", NS):
            address = re.fullmatch(r"([A-Z]+)([1-9]\d*)", cell.attrib["r"])
            require(address is not None, "Invalid source cell address")
            value = cell.find("s:v", NS)
            if value is None:
                continue
            kind = cell.get("t", "n")
            require(kind in ("n", "s"), "Unexpected source value type")
            text = value.text
            parsed = strings[int(text)] if kind == "s" else float(text)
            if kind == "n":
                require(math.isfinite(parsed), "Nonfinite source number")
                if parsed.is_integer():
                    parsed = int(parsed)
            column, number = address.groups()
            row = rows.setdefault(int(number), {})
            require(column not in row, "Duplicate source cell")
            row[column] = parsed
        return rows


def normalize_group(label, table):
    aliases = {
        "Hispanic (of any race)": "Hispanic (any race)",
        **{f"{label} years": label for label in C_GROUPS[1:-1]},
        "65 years and over": "65+",
    }
    group = aliases.get(label, label)
    require(group in (B_GROUPS if table == "4b" else C_GROUPS), "Unknown demographic label")
    return group


def disposition(native):
    base = native["adult_citizens_thousands"]
    pct, moe = native["voted_citizen_pct"], native["voted_citizen_moe90_pp"]
    if pct == "B" or moe == "B":
        require(pct == moe == "B", "Inconsistent native B rate/uncertainty")
        return STATUSES[1], None, None
    require(base == "-" or type(base) in (int, float), "Invalid citizen population")
    if base == "-" or base <= 75:
        return STATUSES[2], None, None
    if pct == "-":
        return STATUSES[3], None, None
    require(type(pct) in (int, float) and 0 <= pct <= 100
            and type(moe) in (int, float) and 0 <= moe <= 100,
            "Invalid published participation percentage or margin")
    return STATUSES[0], pct, moe


def parse_table(raw, year, table):
    cells = workbook(raw)
    title = cells[2]["A"]
    require(f"Table {table}." in title and f"November {year}" in title
            and ("by Age" if table == "4c" else "by Sex, Race and Hispanic Origin") in title,
            "Unexpected native table title/year")
    major, minor = (5, 6) if year < 2022 else (4, 5)
    require(cells[major]["C"] == "Total population"
            and cells[major]["D"] == "Total citizen population"
            and cells[minor]["J"] == "Total voted"
            and cells[minor]["M"] == "Percent voted\n(Citizen)"
            and cells[minor]["N"].startswith("Margin of error"),
            "Native denominator/column schema changed")
    notes = [row["A"] for number, row in sorted(cells.items())
             if number > minor and "B" not in row and isinstance(row.get("A"), str)]
    require(any("90-percent confidence interval" in note for note in notes)
            and any("rounding" in note for note in notes), "Missing native uncertainty/rounding notes")
    if year < 2022:
        require(any("base is less than 75,000" in note for note in notes),
                "Missing native suppression definition")
    expected_groups = B_GROUPS if table == "4b" else C_GROUPS
    result, current = [], None
    for number, cell in sorted(cells.items()):
        if number <= minor or "B" not in cell:
            continue
        label = cell.get("A", "")
        if label:
            if label in ("US", "UNITED STATES"):
                current = STATES[0]
            else:
                require(label in {name.upper() for name in NAMES}, "Unknown state")
                current = next(name for name in NAMES if name.upper() == label)
        require(current is not None, "Missing state context")
        group = normalize_group(cell["B"], table)
        native = {}
        for column, metric in zip("CDEFGHIJKLMN", METRICS):
            value = cell.get(column)
            require((type(value) in (int, float) and value >= 0)
                    or value in ("B", "-"), "Missing or unexpected native metric")
            native[metric] = value
        status, pct, moe = disposition(native)
        result.append({
            "year": year, "state": current, "group": group,
            "native_group": cell["B"], "table": table, "source_row": number,
            "display_status": status, "display_reported_voting_pct": pct,
            "display_native_moe90_pp": moe, **native,
        })
    require(len(result) == len(STATES) * len(expected_groups)
            and {(row["state"], row["group"]) for row in result}
            == {(state, group) for state in STATES for group in expected_groups},
            "Incomplete or duplicate state/group coverage")
    return result, {"year": year, "table": table, "title": title, "notes": notes}


def review(root=ROOT):
    directory = root / DATA
    manifest_raw = (directory / "sources.json").read_bytes()
    require(digest(manifest_raw) == "b5a6a25bd6a077b2bcb877b51b474552c880362fb19d4db7c8b981d2a71fbe76",
            "Frozen source manifest changed")
    manifest = json.loads(manifest_raw)
    sources = manifest["sources"]
    require(len(sources) == 8 and {(s["year"], s["table"]) for s in sources} == set(PINS),
            "Missing or duplicate native sources")
    all_rows, notes, inputs = [], [], {"sources.json": manifest_raw}
    for source in sources:
        year, table = source["year"], source["table"]
        raw = (directory / source["path"]).read_bytes()
        catalog = (directory / source["catalog_path"]).read_bytes()
        require(digest(raw) == source["sha256"] == PINS[year, table]
                and len(raw) == source["bytes"], "Frozen workbook changed")
        require(digest(catalog) == source["catalog_sha256"] == CATALOG_PINS[year],
                "Frozen declared-link catalog changed")
        require(source["url"] == source["catalog_url"] + source["path"].split("-", 1)[1]
                and f'href="{source["path"].split("-", 1)[1]}"'.encode() in catalog,
                "Source URL is not the native catalog-declared workbook")
        require(set(source["response_headers"]) <= {
            "date", "content-type", "content-length", "last-modified", "etag"},
            "Private or unexpected response headers")
        rows, definition = parse_table(raw, year, table)
        for row in rows:
            row["source_file"] = source["path"]
        all_rows.extend(rows)
        notes.append(definition)
        inputs[source["path"]] = raw
        inputs[source["catalog_path"]] = catalog
    lookup = {(r["year"], r["state"], r["group"], r["table"]): r for r in all_rows}
    for year in YEARS:
        for state in STATES:
            first = lookup[year, state, "Total", "4b"]
            second = lookup[year, state, "Total", "4c"]
            require(all(first[key] == second[key] for key in METRICS),
                    "Separate native tables disagree on their shared overall control")
    rows = [r for r in all_rows if r["table"] == "4b" or r["group"] != "Total"]
    rows.sort(key=lambda r: (STATES.index(r["state"]), GROUPS.index(r["group"]), r["year"]))
    summary = {
        "status": "published_historical_CPS_self_report_not_2026_or_individual_transitions",
        "years": list(YEARS), "states_and_DC": 51, "national_scope": STATES[0],
        "groups": list(GROUPS), "unique_observations": len(rows),
        "native_rows_including_duplicate_overall_controls": len(all_rows),
        "duplicate_overall_controls_verified": len(YEARS) * len(STATES),
        "display_dispositions": dict(Counter(r["display_status"] for r in rows)),
        "units": "Native weighted population counts in thousands; rates and 90% margins in percentage points.",
        "denominator": "Native civilian noninstitutionalized adult citizen population, not legal eligibility.",
        "native_definitions": notes,
        "limits": [
            "2018/2022 are midterms; 2020/2024 are presidential elections. These are repeated cross-sections.",
            "No 2026 participation, individual switching, cohort retention, first-time voting, county or precinct estimates.",
            "Percentages and margins are native published cells, never reconstructed from rounded counts.",
            "B remains not published; dash means zero or rounds to zero, never an exact inferred zero.",
            "Display also withholds rounded citizen population bases <=75 thousand, including the ambiguous rounding boundary. This is population, NOT respondent n or effective n, and is not a guarantee of precision.",
            "Small-base native numbers remain only in the complete unmodified governmental source tables and native-cell transcription, not qualified display estimates. Native B is never recovered.",
            "Native estimate +/- native margin gives the source's 90% interval, not a simultaneous interval or confidence interval for a difference. No interval clipping, pooled variance or significance tests.",
            "Self/proxy-reported participation can over-report administrative turnout; sampling margins do not cover nonsampling errors.",
            "Race-alone, race-in-combination and Hispanic views overlap. Do not sum them, cross with sex/age, or fabricate an exclusive residual.",
            "Education, income and urbanicity are not present in these tables; no intersections are manufactured.",
            "Native national observations include D.C.; they are not labeled US50 or reconstructed by summing rounded states.",
            "No revisions, changing population controls, sources or fieldwork are blended into a fixed-person panel.",
        ],
    }
    keyed = {(r["state"], r["group"], r["year"]): r for r in rows}
    display = {
        "years": list(YEARS), "states": list(STATES), "groups": list(GROUPS),
        "values": [[[
            ([keyed[state, group, year]["display_reported_voting_pct"],
              keyed[state, group, year]["display_native_moe90_pp"]]
             if keyed[state, group, year]["display_status"] == STATUSES[0]
             else [-STATUSES.index(keyed[state, group, year]["display_status"])])
            for year in YEARS] for group in GROUPS] for state in STATES],
    }
    return rows, summary, display, inputs


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def frozen_write(path, raw):
    if path.exists():
        require(path.read_bytes() == raw, f"Frozen output changed: {path.name}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def package(root=ROOT, output=None):
    rows, summary, display, inputs = review(root)
    members = {f"{DATA}/{name}": raw for name, raw in inputs.items()}
    members.update({name: (root / name).read_bytes() for name in CODE})
    members.update({
        "results/observations.csv": csv_bytes(rows),
        "results/review.json": encoded(summary),
        "results/display.json": encoded(display, compact=True),
        "METHODOLOGY.txt": ("\n\n".join([summary["denominator"], summary["units"],
                                       *summary["limits"]]) + "\n").encode(),
    })
    inventory = {name: {"bytes": len(raw), "sha256": digest(raw)}
                 for name, raw in sorted(members.items())}
    members["checksums.json"] = encoded(inventory)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(members.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw, compresslevel=9)
    raw = stream.getvalue()
    result = {"bytes": len(raw), "sha256": digest(raw), "members": len(members),
              "unique_observations": len(rows), "source_workbooks": 8, "source_catalogs": 4}
    destination = Path(output) if output else root / DATA / "output"
    outputs = {"observations.csv": members["results/observations.csv"],
               "review.json": members["results/review.json"],
               "display.json": members["results/display.json"],
               "complete-analysis.zip": raw, "archive.json": encoded(result)}
    for name, content in outputs.items():
        if (destination / name).exists():
            require((destination / name).read_bytes() == content, f"Frozen output changed: {name}")
    for name, content in outputs.items():
        frozen_write(destination / name, content)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.root, args.output), indent=2))

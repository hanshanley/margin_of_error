"""Acquire primary historical voting-method sources for the local participation review."""

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import openpyxl
import pdfplumber
import requests
import xlrd

EAC = "https://www.eac.gov"
EAVS = {
    2024: "/sites/default/files/2026-02/2024_EAVS_for_Public_Release_nolabel_V2_csv.zip",
    2022: "/sites/default/files/2023-12/2022_EAVS_for_Public_Release_nolabel_V1.1_CSV.zip",
    2020: "/sites/default/files/2023-12/2020_EAVS_for_Public_Release_nolabel_V1.2_CSV.zip",
    2018: "/sites/default/files/Research/EAVS_2018_for_Public_Release_Updates3.csv",
    2016: "/sites/default/files/2023-12/EAVS_2016_for_Public_Release_nolabel_V1.1_CSV.zip",
    2014: "/sites/default/files/eac_assets/1/1/2014_EAVS_Excel_Files1.zip",
    2012: "/sites/default/files/eac_assets/1/6/Excel%20Files-Part%202.zip",
    2010: "/sites/default/files/eac_assets/1/28/Final%20EAVS%20Data%20-%20Sections%20C%20to%20F_EXCEL.zip",
    2008: "/sites/default/files/eac_assets/1/6/2008%20eavs%20xls%20august%2011%202010.zip",
    2006: "/sites/default/files/eac_assets/1/6/2006%20UOCAVA%20Survey%20All%20Data.zip",
}
BOOKS = {
    2008: "/sites/default/files/eac_assets/1/6/2008_EAVS_Survey_Instrument.pdf",
    2010: "/sites/default/files/eac_assets/1/6/2010%20Election%20Administration%20and%20Voting%20Survey%20EAVS%20Report%20with%20OMB%20Control%20Number.pdf",
    2012: "/sites/default/files/eac_assets/1/28/2012%20Election%20Administration%20and%20Voting%20Survey_2.6.2012.pdf",
    2014: "/sites/default/files/eac_assets/1/1/2014%20EAVS%20Data%20File%20Codebook-2015-06-24-V03-Final.pdf",
    2016: "/sites/default/files/eac_assets/1/6/EAVS_Codebook_2016.pdf",
    2018: "/sites/default/files/eac_assets/1/6/2018_EAVS_Codebook.xlsx",
    2020: "/sites/default/files/2021-08/2020_EAVS_Codebook.xlsx",
    2022: "/sites/default/files/2023-06/2022_EAVS_Codebook.xlsx",
    2024: "/sites/default/files/2025-06/2024_EAVS_Codebook.xlsx",
}
MODES = {"b": "election_day", "c": "uocava", "d": "domestic_absentee",
         "e": "provisional", "f": "early_in_person", "g": "all_mail"}
REPORT = "https://www.census.gov/content/dam/Census/library/publications/2018/demo/P20-582.pdf"


def count(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not re.fullmatch(r"\d+(?:\.0+)?", text):
        return None
    return int(float(text))


def normalize_eavs(content, name, year, state_codes, source_url):
    result = []
    seen = set()
    for sheet, rows in datasets(content, name):
        header = next((row for row in rows[:20] if any(str(v).lower() in {"f1a", "qf1a"} for v in row)), None)
        if header is None:
            continue
        fields = [str(v).lower() for v in header]
        for values in rows[rows.index(header) + 1:]:
            row = dict(zip(fields, values))
            code = str(row.get("state_abbr") or row.get("state_") or row.get("state") or "").strip()
            if code not in state_codes:
                continue
            raw_id = str(row.get("fipscode", row.get("jurisid", ""))).strip()
            identifier = raw_id.removesuffix(".0")
            jurisdiction = str(row.get("jurisdiction_name") or row.get("jurisdictionname")
                               or row.get("jurisdiction") or row.get("jurisname")).strip()
            if not re.fullmatch(r"\d{1,10}|" + code + r"\d+|23\.", identifier):
                raise ValueError(f"{year}: invalid jurisdiction identity {raw_id}")
            identity = (code, identifier, jurisdiction)
            if identity in seen:
                raise ValueError(f"{year}: duplicate reporting unit {identity}")
            seen.add(identity)
            prefix = "qf1" if "qf1a" in row else "f1"
            def reported(letter):
                field = prefix + letter
                flags = [value for key, value in row.items() if key.startswith(field + "_")
                         and any(term in key for term in ["notavailable", "notapplicable", "validskip"])]
                if any(str(value or "").strip().lower() not in {"", "0", "0.0", "false", "no"} for value in flags):
                    return None
                return count(row.get(field))
            modes = {mode: reported(letter) for letter, mode in MODES.items()}
            if year == 2008:
                modes.pop("all_mail")
            modes["other"] = None
            other = [reported(letter) for letter in ("ghi" if year == 2008 else "hij")
                     if prefix + letter in row]
            if other and all(value is not None for value in other):
                modes["other"] = sum(other)
            comments = {key: value for key, value in row.items()
                        if value not in (None, "") and (key.startswith(("f1", "qf1", "f2", "qf2")))
                        and key not in {prefix + letter for letter in "abcdefghij"}}
            result.append({"year": year, "state_code": code, "jurisdiction_id": identifier,
                           "jurisdiction": jurisdiction,
                           "statewide_unit": jurisdiction.upper() == "STATEWIDE"
                           or (len(identifier) == 10 and identifier.isdigit() and identifier[2:] == "00000000"),
                           "supplemental_unit": code == "ME" and ("UOCAVA" in jurisdiction.upper() or identifier == "2300000000"),
                           "total_participation": reported("a"), "methods": modes,
                           "raw_method_fields": {key: row.get(prefix + key) for key in "abcdefghij"
                                                 if prefix + key in row},
                           "source_details": comments, "source_url": source_url, "source_sheet": sheet})
    if not result:
        raise ValueError(f"No verified F1 table for {year}")
    return result


def state_summaries(records):
    groups = defaultdict(list)
    for row in records:
        groups[(row["year"], row["state_code"])].append(row)
    result = []
    for (year, code), rows in sorted(groups.items()):
        eligible = [row for row in rows if not row.get("supplemental_unit")]
        statewide = [row for row in eligible if row["statewide_unit"]]
        # A statewide reporting unit and its component local units must never be added.
        used = statewide if statewide else eligible
        if not used:
            continue
        for mode in sorted({mode for row in used for mode in row["methods"]}):
            reported = [row for row in used if row["methods"].get(mode) is not None]
            matched = [row for row in reported if row["total_participation"]
                       and row["methods"][mode] <= row["total_participation"]]
            denominator = sum(row["total_participation"] for row in matched)
            numerator = sum(row["methods"][mode] for row in matched)
            result.append({"year": year, "state_code": code, "mode": mode,
                           "reported_count": sum(row["methods"][mode] for row in reported) if reported else None,
                           "reporting_units": len(reported), "total_units": len(used),
                           "matched_units": len(matched), "matched_count": numerator if matched else None,
                           "matched_participation": denominator or None,
                           "share_pct": round(100 * numerator / denominator, 4) if denominator else None,
                           "invalid_share_units": len([row for row in reported if row["total_participation"] is not None
                                                      and row["methods"][mode] > row["total_participation"]]),
                           "aggregation": "statewide_reporting_unit" if statewide else "local_reporting_units",
                           "excluded_component_units": len(rows) - len(used),
                           "units_with_source_notes": sum(bool(row["source_details"]) for row in used),
                           "source_url": used[0]["source_url"]})
    return result


def census_rows(content, year, source_url):
    result = []
    for rows in sheets(content).values():
        category = ""
        for row in rows:
            text = " ".join(str(value or "") for value in row[:3])
            if re.search(r"margin.*error", text, re.I):
                break
            if len(row) < 7 or count(row[2]) is None or not all(isinstance(v, (int, float)) for v in row[3:7]):
                continue
            category = str(row[0] or category).strip()
            group = str(row[1] or "").strip()
            if category.lower() == "total":
                category, group = "Overall", "All voters"
            shares = dict(zip(["election_day", "early_in_person", "mail", "unknown"], row[3:7]))
            if any(not 0 <= value <= 100 for value in shares.values()) or abs(sum(shares.values()) - 100) > .3:
                raise ValueError(f"CPS {year}: invalid share distribution {row}")
            result.append({"year": year, "category": category, "group": group,
                           "reported_voters_thousands": count(row[2]), "methods": shares,
                           "universe": "all_reported_voters", "source_url": source_url})
    if sum(row["category"] == "Overall" for row in result) != 1:
        raise ValueError(f"CPS {year}: expected exactly one overall estimate")
    return result


def historical_census(content):
    with pdfplumber.open(io.BytesIO(content)) as document:
        text = document.pages[12].extract_text()
    result = []
    for year, day, alternative, early, mail in re.findall(
            r"\b(20\d{2}|199[68])\*?\s*\.{2,}\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", text):
        day, alternative, early, mail = map(float, [day, alternative, early, mail])
        if abs(day + alternative - 100) > .15 or abs(early + mail - alternative) > .15:
            raise ValueError(f"Historical CPS {year}: percentages do not reconcile within rounding")
        result.append({"year": int(year), "category": "Overall", "group": "All voters with known method",
                       "reported_voters_thousands": None,
                       "methods": {"election_day": day, "early_in_person": early, "mail": mail, "unknown": None},
                       "universe": "valid_method_and_timing_responses", "source_url": REPORT})
    if sorted(row["year"] for row in result) != list(range(1996, 2017, 2)):
        raise ValueError("Historical Census table did not yield every election from 1996 to 2016")
    return result


def write_csv(path, rows):
    with path.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader()
        writer.writerows({key: json.dumps(value, separators=(",", ":")) if isinstance(value, (dict, list)) else value
                         for key, value in row.items()} for row in rows)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, separators=(",", ":")) + "\n")


def sheets(content):
    if content[:2] == b"PK":
        book = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        return {sheet.title: list(sheet.values) for sheet in book}
    book = xlrd.open_workbook(file_contents=content)
    return {sheet.name: [sheet.row_values(i) for i in range(sheet.nrows)] for sheet in book.sheets()}


def datasets(content, name):
    if name.lower().endswith(".csv"):
        yield name, list(csv.reader(io.StringIO(content.decode("utf-8-sig", errors="replace"))))
    elif name.lower().endswith((".xls", ".xlsx")):
        yield from sheets(content).items()
    else:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for member in archive.namelist():
                if member.startswith("__MACOSX/"):
                    continue
                if member.lower().endswith((".csv", ".xls", ".xlsx")):
                    yield from datasets(archive.read(member), member)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, default=Path("../voter-participation"))
    parser.add_argument("--snapshot-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--source-snapshot-id")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    research = args.research.resolve()
    root = research / "data/raw/voting-methods" / args.snapshot_id
    if args.source_snapshot_id and not root.exists():
        shutil.copytree(research / "data/raw/voting-methods" / args.source_snapshot_id, root)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    sources = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    def capture(name, url):
        if name in sources:
            content = (root / name).read_bytes()
            if hashlib.sha256(content).hexdigest() != sources[name]["sha256"] or sources[name]["url"] != url:
                raise ValueError(f"Cached source identity/checksum changed: {name}")
            return content
        response = requests.get(url, timeout=(15, 60))
        response.raise_for_status()
        content = response.content
        (root / name).write_bytes(content)
        sources[name] = {"url": url, "sha256": hashlib.sha256(content).hexdigest(),
                         "bytes": len(content), "retrieved_at": datetime.now(timezone.utc).isoformat()}
        save(manifest_path, sources)
        return content

    for year, path in EAVS.items():
        name = f"eavs-{year}" + Path(path).suffix
        content = capture(name, EAC + path)
        print(f"EAVS {year}: {len(content):,} source bytes", flush=True)
        if args.inspect:
            for sheet, rows in datasets(content, name):
                header = next((row for row in rows[:20] if any(str(value).lower() in {"f1a", "qf1a"} for value in row)), None)
                if header:
                    fields = [str(value) for value in header]
                    print("HEADER", sheet, fields[:6], [value for value in fields if value.lower().startswith("f1")][:22], flush=True)
                    print("EXAMPLE", {fields[i]: rows[rows.index(header) + 1][i]
                                      for i in range(len(fields)) if i < 6 or fields[i].lower().startswith("f1")}, flush=True)
    metadata = json.loads((research / "data/sources.json").read_text())
    bases = {row["year"]: row["url"].rsplit("/", 1)[0] + "/" for row in metadata["sources"]
             if row.get("year", 0) >= 2000 and "census.gov" in row.get("url", "")}
    for year, base in sorted(bases.items()):
        listing = capture(f"cps-{year}-catalog.html", base).decode()
        candidates = [link for link in re.findall(r'href="([^"]+)"', listing)
                      if re.search(r"(?:table|vote|tab)[-_]?1[456].*\.xlsx?$", link, re.I)]
        for index, link in enumerate(candidates):
            name = f"cps-{year}-{index}" + Path(link).suffix
            content = capture(name, urljoin(base, link))
            for sheet, rows in sheets(content).items():
                title = " ".join(str(cell or "") for row in rows[:5] for cell in row)
                if re.search(r"method.*voting", title, re.I):
                    print("CPS METHODS", year, name, sheet, rows[:9], flush=True)
    print(f"Captured {len(sources)} original files.", flush=True)
    if not args.export:
        return
    output = Path("public/participation-methods") / args.snapshot_id
    if (output / "index.json").exists():
        raise ValueError("Completed immutable methods snapshot already exists")
    names = {row["state"] for row in json.loads(Path("public/voter-participation/data/states.json").read_text())}
    codes = {feature["properties"]["STUSAB"] for feature in
             json.loads(Path("public/voter-participation/data/states.geojson").read_text())["features"]
             if feature["properties"]["NAME"] in names}
    jurisdictions, national = [], []
    for year in range(2008, 2025, 2):
        path = EAVS[year]
        name = f"eavs-{year}" + Path(path).suffix
        book = BOOKS[year]
        capture(f"instrument-{year}" + Path(book).suffix, EAC + book)
        jurisdictions.extend(normalize_eavs((root / name).read_bytes(), name, year, codes, EAC + path))
        print(f"Normalized EAVS {year}", flush=True)
    national.extend(historical_census(capture("census-1996-2016.pdf", REPORT)))
    for year in [2018, 2020, 2022, 2024]:
        name = f"cps-{year}-0.xlsx"
        national.extend(census_rows((root / name).read_bytes(), year, sources[name]["url"]))
    summaries = state_summaries(jurisdictions)
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in [("states", summaries), ("national", national)]:
        save(output / f"{name}.json", rows)
        write_csv(output / f"{name}.csv", rows)
    for year in range(2008, 2025, 2):
        rows = [row for row in jurisdictions if row["year"] == year]
        save(output / f"jurisdictions-{year}.json", rows)
    write_csv(output / "jurisdictions.csv", jurisdictions)
    index = {"snapshot_id": args.snapshot_id, "status": "local_review_draft",
             "national_years": sorted({row["year"] for row in national}),
             "state_years": sorted({row["year"] for row in summaries}), "jurisdiction_records": len(jurisdictions),
             "state_observations": len(summaries), "national_observations": len(national),
             "sources": sources, "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "notes": [
                 "Method shares are not turnout rates among eligible citizens.",
                 "1996-2016 national CPS estimates exclude invalid method/timing responses; 2018-2024 retain unknown responses.",
                 "CPS timing/method changed from one question in 1996-2002 to two questions from 2004.",
                 "CPS demographic method estimates currently cover 2018-2024; earlier subgroup estimates are unavailable here.",
                 "EAVS F1 is source-defined participation; older reports can use vote history, poll books or highest-office votes.",
                 "State method percentages use only jurisdictions with that method and a positive matched F1a total.",
                 "State reporting units are preferred to local component units to avoid double counting.",
                 "Separate Maine state-level UOCAVA-only reporting units are preserved but excluded from local-unit method summaries.",
                 "A source identifier plus jurisdiction name defines each reporting unit; repeated municipality IDs can represent separate wards.",
                 "Methods are not summed or renormalized: absentee may mix mail/in-person and overlap UOCAVA.",
                 "Provisional is F1e; early in-person is F1f. F1g is Other in 2008, all-mail from 2010.",
                 "Missing, unavailable, not-applicable and valid-skip fields remain missing, never zero.",
                 "Explicit unavailable flags override contradictory numeric cells; original values and flags are preserved.",
                 "Every source comment and F2 participation-basis field is preserved in jurisdiction downloads.",
                 "EAVS reporting units include municipalities and statewide units; they are not automatically counties or precincts.",
                 "2006 EAVS acquired but not normalized; 1994 and earlier voting-method observations are not supplied."
             ]}
    save(output / "index.json", index)
    with zipfile.ZipFile(output / "complete-methods.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path.name != "complete-methods.zip":
                archive.write(path, path.name)
        for name in sorted(sources):
            archive.write(root / name, "originals/" + name)
        archive.write(manifest_path, "originals/manifest.json")
        archive.write(__file__, "collector.py")
    save(output / "checksums.json", {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                    for path in sorted(output.iterdir()) if path.is_file()})
    save(output.parent / "latest.json", {"snapshot_id": args.snapshot_id})
    print(f"Exported {len(jurisdictions):,} jurisdiction records; {len(summaries)} state-method and {len(national)} national observations.")


if __name__ == "__main__":
    main()

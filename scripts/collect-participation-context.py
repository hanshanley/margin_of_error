"""Collect a separately checksummed local-review supplement; never alter the pinned export."""

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import openpyxl
import pdfplumber
import requests
import shapefile
import xlrd


def digest(content):
    return hashlib.sha256(content).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, separators=(",", ":")) + "\n")


def number(value):
    if value is None or value == "":
        return 0
    text = str(value).strip().rstrip("*").replace(",", "")
    result = int(text.split(".")[0])
    if result < 0 or float(text) != result:
        raise ValueError(f"Invalid election count: {value}")
    return result


def margin(democratic, republican, other, **fields):
    democratic, republican, other = map(number, [democratic, republican, other])
    total = democratic + republican + other
    return {**fields, "democratic_votes": democratic, "republican_votes": republican,
            "other_votes": other, "contest_votes": total,
            "margin_pp": round(100 * (democratic - republican) / total, 5) if total else None}


def workbook(content, summary_only=False):
    if content[:2] == b"PK":
        book = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        result = {}
        for sheet in book:
            if summary_only:
                heading = " ".join(str(cell or "") for row in sheet.iter_rows(
                    max_row=3, max_col=30, values_only=True) for cell in row).upper()
                if not any(phrase in re.sub(r"\s+", " ", heading) for phrase in [
                        "HOUSE OF REPRESENTATIVES BY PARTY", "GENERAL ELECTION VOTES CAST BY PARTY",
                        "SENATE BY PARTY", "GENERAL ELECTION VOTES CAST FOR"]):
                    continue
                result[sheet.title] = list(sheet.iter_rows(max_col=30, values_only=True))
            else:
                result[sheet.title] = list(sheet.values)
        book.close()
        return result
    book = xlrd.open_workbook(file_contents=content)
    return {sheet.name: [sheet.row_values(i) for i in range(sheet.nrows)] for sheet in book.sheets()}


def summary_tables(content, year, states, source_url, presidential=True, rejected=None):
    sheets = workbook(content, summary_only=True)

    def find(phrase):
        return next(rows for rows in sheets.values()
                    if phrase in re.sub(r"\s+", " ", " ".join(str(cell or "") for row in rows[:3] for cell in row)).upper())

    house = find("HOUSE OF REPRESENTATIVES BY PARTY")
    def records(rows, offset):
        result = {}
        for row in rows:
            index = next((i for i in [0, 1] if i < len(row) and str(row[i]).strip().rstrip("*") in states), None)
            if index is None:
                continue
            code = str(row[index]).strip().rstrip("*")
            if code in result:
                raise ValueError(f"{year}: duplicate state summary {code}")
            result[code] = [number(value) for value in row[index + offset:index + offset + 3]]
        return result

    h = records(house, 4)
    if set(states) - {"DC"} - set(h):
        raise ValueError(f"{year}: House table is missing states {sorted(set(states) - {'DC'} - set(h))}")
    result = [margin(*votes, year=year, state_code=code, level="state", geography=code,
                     office="U.S. House", source_url=source_url, provisional=False)
              for code, votes in h.items()]
    if presidential and year % 4 == 0:
        c = records(find("GENERAL ELECTION VOTES CAST BY PARTY"), 1)
        s = records(find("SENATE BY PARTY"), 4)
        totals = find("GENERAL ELECTION VOTES CAST FOR")
        expected = {str(row[0]).strip().rstrip("*"): number(row[1]) for row in totals
                    if str(row[0]).strip().rstrip("*") in states}
        for code, votes in c.items():
            residual = [votes[i] - h.get(code, [0] * 3)[i] - s.get(code, [0] * 3)[i] for i in range(3)]
            if min(residual) < 0 or sum(residual) != expected[code]:
                reason = f"{year} {code}: presidential party residual is negative or does not reconcile to the official total"
                if rejected is None:
                    raise ValueError(reason)
                rejected.append({"source": f"FEC {year} {code} presidential derivation", "error": reason})
                continue
            result.append(margin(*residual, year=year, state_code=code, level="state", geography=code,
                                 office="President", source_url=source_url, provisional=False))
    return result


def clerk_house(content, states, source_url):
    names = {name.upper(): code for code, name in states.items()}
    results = defaultdict(lambda: [0, 0, 0])
    state, district, active = None, None, False
    with pdfplumber.open(io.BytesIO(content)) as document:
        for page in document.pages:
            for line in (page.extract_text() or "").splitlines():
                heading = re.sub(r"[—–-].*CONTINUED.*", "", line.upper()).strip()
                if heading in {"PUERTO RICO", "AMERICAN SAMOA", "GUAM", "NORTHERN MARIANA ISLANDS", "VIRGIN ISLANDS"}:
                    state, district, active = None, None, False
                if heading in names:
                    if state != names[heading]:
                        district = None
                        active = False
                    state = names[heading]
                if line.startswith("FOR "):
                    active = "REPRESENTATIVE" in line or "DELEGATE" in line
                    if active and state == "DC":
                        district = "98"
                        results[(state, district)]
                    continue
                if line.startswith("Recapitulation") or line.startswith("RECAPITULATION"):
                    active = False
                if not state or not active:
                    continue
                if line.strip() == "AT LARGE":
                    district = "00"
                    results[(state, district)]
                first = re.match(r"^(\d+)\.\s+", line)
                if first:
                    district = f"{int(first[1]):02}"
                    results[(state, district)]
                candidate = re.match(r"(.+?)\s*\.{2,}\s*([\d,]+)$", line)
                if not candidate or district is None:
                    continue
                label, votes = candidate.groups()
                affiliation = re.search(r",\s*(Democrat(?:ic)?(?:-Farmer-Labor|-Nonpartisan League)?|Republican)\s*$", label, re.I)
                party = (0 if affiliation[1].lower().startswith("democrat") else 1) if affiliation else 2
                results[(state, district)][party] += number(votes)
        recap = document.pages[85].extract_text(line_dir_rotated="rtl", char_dir_rotated="btt")
        recap = recap.split("\nState\n")[0]
        pattern = r"(?<!\w)(" + "|".join(re.escape(name.title()).replace(r"\ ", r"\s+")
                                          for name in sorted(names, key=len, reverse=True) if names[name] != "DC") + r")\s+\.{3,}"
        matches = list(re.finditer(pattern, recap))
        if len(matches) != 50:
            raise ValueError(f"Clerk House recap yielded {len(matches)} states, expected 50")
        for i, match in enumerate(matches):
            code = names[re.sub(r"\s+", " ", match[1]).upper()]
            chunk = recap[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(recap)]
            cells = re.findall(r"\d[\d,]*|\.{2,}", chunk)
            expected = [0 if cell.startswith(".") else number(cell) for cell in [cells[0], cells[1], cells[-1]]]
            actual = [sum(votes[i] for (state, _), votes in results.items() if state == code) for i in [1, 0]]
            actual.append(sum(sum(votes) for (state, _), votes in results.items() if state == code))
            if actual != expected:
                raise ValueError(f"2024 {code} district counts do not reconcile to Clerk recap: {actual} != {expected}")
        totals = [sum(votes[i] for (state, _), votes in results.items() if state != "DC") for i in [1, 0]]
        totals.append(sum(sum(votes) for (state, _), votes in results.items() if state != "DC"))
        if totals != [74390864, 70571330, 149543421]:
            raise ValueError("2024 House counts do not match all three national recap totals")
    voting = {key for key in results if key[0] != "DC"}
    if len(voting) != 435:
        counts = {code: sum(key[0] == code for key in voting) for code in states}
        raise ValueError(f"Clerk parser found {len(voting)} voting districts, expected 435: {counts}")
    return [margin(*votes, year=2024, state_code=code, level="district", geography=code + "-" + district,
                   office="U.S. House", source_url=source_url, provisional=False)
            for (code, district), votes in sorted(results.items())]


def provider_votes(candidates):
    result = [0, 0, 0]
    for candidate in candidates:
        party = candidate.get("party", "")
        index = (0 if party in {"Democratic", "Democrat", "Democratic-Farmer-Labor"}
                 else 1 if party in {"Republican", "Independent-Republican"} else 2)
        result[index] += number(candidate["votes"])
    return result


def name_key(name):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s+(county|parish)$", "", name.lower()))


def clerk_1994(source_url):
    with Path(__file__).with_name("clerk-house-1994.csv").open() as stream:
        rows = [{key: value if key == "state_code" else number(value) for key, value in row.items()}
                for row in csv.DictReader(stream)]
    if len(rows) != 49 or len({row["state_code"] for row in rows}) != 49:
        raise ValueError("1994 Clerk transcription must cover 49 states, excluding untabulated Louisiana")
    for field, expected in [("republican_votes", 36325809), ("democratic_votes", 31542823), ("contest_votes", 70493648)]:
        if sum(row[field] for row in rows) != expected:
            raise ValueError(f"1994 Clerk transcription does not reconcile to national {field}")
    return [margin(row["democratic_votes"], row["republican_votes"],
                   row["contest_votes"] - row["democratic_votes"] - row["republican_votes"],
                   year=1994, state_code=row["state_code"], level="state", geography=row["state_code"],
                   office="U.S. House", source_url=source_url, provisional=False,
                   source_pages="47-48 (PDF pages 48-49)",
                   quality="Manually transcribed recap; exact national party/total reconciliation. Party votes, not winner margins.")
            for row in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, default=Path("../voter-participation"))
    parser.add_argument("--snapshot-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--source-snapshot-id")
    args = parser.parse_args()
    research = args.research.resolve()
    sys.path.insert(0, str(research))
    from scripts.build import simplify
    from scripts.nationwide import STATES
    output = Path("public/participation-context") / args.snapshot_id
    if (output / "index.json").exists():
        raise ValueError("This supplemental output already exists; use a new snapshot ID")
    raw = research / "data/raw/context" / args.snapshot_id
    if args.source_snapshot_id and not raw.exists():
        shutil.copytree(research / "data/raw/context" / args.source_snapshot_id, raw)
    raw.mkdir(parents=True, exist_ok=True)
    source_path = raw / "manifest.json"
    sources = json.loads(source_path.read_text()) if source_path.exists() else {}
    errors, rows = [], []

    def capture(name, url):
        if name in sources:
            content = (raw / name).read_bytes()
            if digest(content) != sources[name]["sha256"] or sources[name]["url"] != url:
                raise ValueError(f"Cached source identity/checksum changed: {name}")
            return content
        response = requests.get(url, timeout=(15, 45))
        response.raise_for_status()
        content = response.content
        (raw / name).write_bytes(content)
        sources[name] = {"url": url, "sha256": digest(content), "bytes": len(content),
                         "retrieved_at": datetime.now(timezone.utc).isoformat()}
        save(source_path, sources)
        return content

    state_features = json.loads((research / "public/data/states.geojson").read_text())["features"]
    codes = {feature["properties"]["STATE"]: feature["properties"]["STUSAB"] for feature in state_features}
    counties, districts = {}, {}
    for level, suffix in [("county", "county"), ("district", "cd119")]:
        name = f"cb_2024_us_{suffix}_500k.zip"
        content = capture(name, f"https://www2.census.gov/geo/tiger/GENZ2024/shp/{name}")
        grouped = defaultdict(list)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            stem = next(name[:-4] for name in archive.namelist() if name.endswith(".shp"))
            reader = shapefile.Reader(**{ext: io.BytesIO(archive.read(stem + "." + ext)) for ext in ["shp", "shx", "dbf"]})
            for record in reader.iterShapeRecords():
                p = record.record.as_dict()
                code = codes.get(p["STATEFP"])
                if code not in STATES:
                    continue
                geo = record.shape.__geo_interface__

                def ring(points):
                    points = simplify(points, .00035)
                    return [[round(x, 5), round(y, 5)] for x, y, *rest in points] if len(points) >= 4 else []

                polygons = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
                polygons = [[ring(points) for points in polygon] for polygon in polygons]
                polygons = [[points for points in polygon if points] for polygon in polygons if polygon and polygon[0]]
                if not polygons:
                    continue
                identifier = p["GEOID"] if level == "county" else code + "-" + p["CD119FP"]
                props = {"key": identifier, "name": p["NAMELSAD"], "state_code": code, "boundary_year": 2024}
                if level == "county":
                    props["aliases"] = [p["NAME"], p["NAMELSAD"]]
                grouped[code].append({"type": "Feature", "properties": props,
                                      "geometry": {"type": "MultiPolygon", "coordinates": polygons}})
        destination = counties if level == "county" else districts
        for code, features in grouped.items():
            destination[code] = features
            save(output / "geometry" / f"{level}-{code}.geojson", {"type": "FeatureCollection", "features": features})
        print(f"Saved {level}: {sum(map(len, grouped.values()))} boundaries", flush=True)

    for year in range(2000, 2024, 2):
        try:
            slug = "election-and-voting-information" if year == 2020 else "election-results-and-voting-information"
            page_url = f"https://www.fec.gov/introduction-campaign-finance/{slug}/federal-elections-{year}/"
            page = capture(f"fec-{year}.html", page_url).decode()
            links = re.findall(r'href="([^"]+\.xlsx?)"', page, re.I)
            link = next((link for link in links if "table" in link.lower()), links[0])
            url = urljoin(page_url, link)
            data = capture(f"fec-{year}" + Path(link).suffix, url)
            house_rows = summary_tables(data, year, STATES, url, presidential=False)
            rows.extend(house_rows)
            if year % 4 == 0:
                try:
                    rows.extend(row for row in summary_tables(data, year, STATES, url, rejected=errors) if row["office"] == "President")
                except (ValueError, StopIteration) as error:
                    errors.append({"source": f"FEC {year} presidential derivation", "error": str(error)})
            print(f"Parsed FEC {year}", flush=True)
        except Exception as error:
            errors.append({"source": f"FEC {year}", "error": str(error)})
            print(f"Not promoted: FEC {year}: {error}", flush=True)

    url = "https://history.house.gov/Institution/Election-Statistics/1994election/"
    capture("clerk-1994.pdf", url)
    rows.extend(clerk_1994(url))
    errors.append({"source": "1994 Louisiana House recap",
                   "error": "Source does not tabulate unopposed general-election votes; missing, not zero."})

    url = "https://www.fec.gov/documents/5645/2024presgeresults.xlsx"
    data = workbook(capture("2024presgeresults.xlsx", url))
    sheet = next(iter(data.values()))
    columns = {value: index for index, value in enumerate(sheet[0])}
    for row in sheet[1:]:
        if row[0] not in STATES:
            continue
        dem, rep = number(row[columns["HARRIS"]]), number(row[columns["TRUMP"]])
        total_col = next(index for label, index in columns.items() if isinstance(label, str) and "TOTAL" in label.upper())
        total = number(row[total_col])
        rows.append(margin(dem, rep, total - dem - rep, year=2024, state_code=row[0], level="state",
                           geography=row[0], office="President", source_url=url, provisional=False))
    url = "https://history.house.gov/Institution/Election-Statistics/2024election/"
    rows.extend(clerk_house(capture("clerk-2024.pdf", url), STATES, url))
    print("Parsed official 2024 presidential and House returns", flush=True)

    url = "https://civicapi.org/api/v2/race/87524"
    current = json.loads(capture("house-2026.json", url))
    if current.get("test_data") is not False or not current["election_date"].startswith("2026-11-03"):
        raise ValueError("Wrong election or test-data response")
    if current["election_type"] != "House of Representatives" or current["election_scope"] != "General":
        raise ValueError("Wrong office or election scope")
    by_state = defaultdict(lambda: [0, 0, 0])
    for key, region in current["region_results"].items():
        if region["type"] != "Congressional District":
            raise ValueError("Unexpected House breakdown geography")
        code, district = key.upper().split("-")
        if code not in STATES:
            continue
        district = "00" if district == "AL" else f"{int(district):02}"
        votes = provider_votes(region["candidates"])
        by_state[code] = [a + b for a, b in zip(by_state[code], votes)]
        rows.append(margin(*votes, year=2026, state_code=code, level="district", geography=code + "-" + district,
                           office="U.S. House", source_url=url, provisional=True,
                           source_update_label=current["last_updated"], reporting_pct=region["percent_reporting"]))
    if len([row for row in rows if row["year"] == 2026 and row["level"] == "district"]) != 435:
        raise ValueError("2026 House source does not cover 435 voting districts")
    districts_2026 = [row for row in rows if row["year"] == 2026 and row["level"] == "district"]
    if len({row["geography"] for row in districts_2026}) != 435:
        raise ValueError("Duplicate 2026 voting districts")
    national_votes = provider_votes(current["candidates"])
    district_votes = [sum(votes[i] for votes in by_state.values()) for i in range(3)]
    if national_votes != district_votes:
        raise ValueError("2026 district party counts do not reconcile to national party totals")
    for code, votes in by_state.items():
        rows.append(margin(*votes, year=2026, state_code=code, level="state", geography=code,
                           office="U.S. House", source_url=url, provisional=True,
                           source_update_label=current["last_updated"]))

    url = ("https://civicapi.org/api/v2/race/search?"
           "startDate=2024-11-05&endDate=2024-11-05&query=President&limit=1000")
    candidates = json.loads(capture("president-2024-search.json", url))["races"]
    for race in candidates:
        code = race["province"]
        if (code not in counties or race["type"] != "President" or race["election_type"] != "General"
                or not race.get("has_breakdown") or re.search(r"\bElector\b", race["election_name"], re.I)):
            continue
        url = f'https://civicapi.org/api/v2/race/{race["id"]}'
        detail = json.loads(capture(f"president-2024-{code}.json", url))
        if detail.get("test_data") is not False or detail["province"] != code or not detail["election_date"].startswith("2024-11-05"):
            raise ValueError("Wrong state/election or test data in county response")
        aliases = defaultdict(set)
        for feature in counties[code]:
            for alias in feature["properties"]["aliases"]:
                aliases[name_key(alias)].add(feature["properties"]["key"])
        matching = {}
        regions = [region for region in detail["region_results"].values() if region["type"] == "County"]
        for region in regions:
            keys = aliases.get(name_key(region["name"]), set())
            if len(keys) == 1:
                matching[next(iter(keys))] = region
        if len(matching) != len(regions) or len(matching) != len(counties[code]):
            errors.append({"source": f"2024 {code} provider regions",
                           "error": "Region collection is not a one-to-one match to Census counties; not mapped"})
            continue
        county_votes = [sum(provider_votes(region["candidates"])[i] for region in matching.values()) for i in range(3)]
        if county_votes != provider_votes(detail["candidates"]):
            errors.append({"source": f"2024 {code} provider returns",
                           "error": "County party counts do not reconcile to provider state totals; not mapped"})
            continue
        for key, region in matching.items():
            rows.append(margin(*provider_votes(region["candidates"]), year=2024, state_code=code,
                               level="county", geography=key, office="President", source_url=url,
                               provisional=region["percent_reporting"] < 100, source_update_label=detail["last_updated"],
                               reporting_pct=region["percent_reporting"]))
        print(f"Verified county identities: {code} ({len(matching)})", flush=True)

    pointer = json.loads((research / "public/data/nationwide/latest.json").read_text())
    source_root = research / "public/data/nationwide" / pointer["snapshot_id"]
    for path in source_root.iterdir():
        if path.is_file():
            target = output / "nationwide" / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    save(output / "margins.json", rows)
    fieldnames = sorted({key for row in rows for key in row})
    with (output / "margins.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    save(output / "index.json", {
        "snapshot_id": args.snapshot_id, "status": "local_review_draft",
        "state_margin_years": sorted({row["year"] for row in rows if row["level"] == "state"}),
        "geometry": {"county": {code: f"geometry/county-{code}.geojson" for code in counties},
                     "district": {code: f"geometry/district-{code}.geojson" for code in districts}},
        "boundary_year": 2024, "district_result_years": [2024],
        "county_result_years": sorted({row["year"] for row in rows if row["level"] == "county"}),
        "sources": sources, "rejected_sources": errors,
        "source_revision": subprocess.check_output(["git", "-C", str(research), "rev-parse", "HEAD"], text=True).strip(),
        "source_worktree_dirty": bool(subprocess.check_output(["git", "-C", str(research), "status", "--porcelain"], text=True).strip()),
        "collector_sha256": digest(Path(__file__).read_bytes()),
        "notes": [
            "Supplemental draft; the pinned historical publication export is unchanged.",
            "Party-margin returns provide map context only; candidate votes never replace ballots or participants.",
            "D-minus-R margin uses all reported contest votes, not a two-party denominator.",
            "House state margins aggregate district votes, not seats or a statewide race winner.",
            "Unopposed House races and missing vote returns can distort party aggregates.",
            "2024 House district counts reconcile to every state recap and all three national party/total sums.",
            "House party classifications and totals follow the Clerk recap, including its treatment of write-ins, fusion labels and blank/overvotes.",
            "2024 Census counties provide geographic context; boundaries are not certified 2026 precinct outlines.",
            "119th-Congress districts are used only with 2024 election results, never 2026 results.",
            "civicAPI public aggregate returns are attributed; no NYT modeled data is used.",
        ],
    })
    with zipfile.ZipFile(output / "complete-context.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file() and path.name != "complete-context.zip":
                archive.write(path, str(path.relative_to(output)))
        for path in sorted(raw.iterdir()):
            if path.is_file():
                archive.write(path, "originals/" + path.name)
        archive.write(__file__, "collector.py")
        archive.write(Path(__file__).with_name("clerk-house-1994.csv"), "clerk-house-1994.csv")
    files = [{"path": str(path.relative_to(output)), "bytes": path.stat().st_size,
              "sha256": digest(path.read_bytes())} for path in sorted(output.rglob("*")) if path.is_file()]
    save(output.parent / "latest.json", {"snapshot_id": args.snapshot_id, "status": "local_review_draft", "files": files})
    print(json.dumps({"margins": len(rows), "rejected_sources": errors,
                      "snapshot_id": args.snapshot_id}, indent=2), flush=True)


if __name__ == "__main__":
    main()

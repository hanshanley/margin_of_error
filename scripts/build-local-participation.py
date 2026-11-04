"""Build nationwide local participation from checksum-verified EAC survey originals."""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import shapefile
import openpyxl


spec = importlib.util.spec_from_file_location(
    "voting_methods", Path(__file__).with_name("collect-voting-methods.py"))
methods = importlib.util.module_from_spec(spec)
spec.loader.exec_module(methods)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def normalized_id(value):
    return str(value).strip().removesuffix(".0")


def identity(row):
    return (
        str(row.get("state_abbr") or row.get("state_") or row.get("state") or "").strip(),
        normalized_id(row.get("fipscode", row.get("jurisid", ""))),
        str(row.get("jurisdiction_name") or row.get("jurisdictionname")
            or row.get("jurisdiction") or row.get("jurisname") or "").strip(),
    )


def reported(row, field):
    flags = [value for key, value in row.items()
             if key.startswith(field + "_")
             and any(term in key for term in ("notavailable", "notapplicable", "validskip"))]
    if any(str(value or "").strip().lower() not in ("", "0", "0.0", "false", "no")
           for value in flags):
        return None
    return methods.count(row.get(field))


def registration_records(content, name, source_state=None):
    records = {}
    for _, values in methods.datasets(content, name):
        header_index = next((i for i, row in enumerate(values[:20])
                             if any(str(v).lower() in ("a1", "a1a", "qa1a") for v in row)), None)
        if header_index is None:
            continue
        fields = [str(value).lower() for value in values[header_index]]
        for values_row in values[header_index + 1:]:
            row = dict(zip(fields, values_row))
            key = identity(row)
            if not key[1]:
                continue
            if source_state and not key[0]:
                code, fips = source_state
                if not re.fullmatch(fips + r"\d{8}", key[1]):
                    raise ValueError(f"Registration source contains a different state: {key}")
                key = code, key[1], key[2]
            if not key[0] or not key[1]:
                continue
            field = next(field for field in ("qa1a", "a1a", "a1") if field in row)
            record = {
                "registered": reported(row, field),
                "registration_field": field,
                "registration_comment": str(row.get("a1comments") or row.get("a1_comments")
                                            or row.get("qa1_comment") or ""),
                "registration_definition": str(row.get("a2") or row.get("qa2") or ""),
            }
            if key in records:
                raise ValueError(f"Duplicate registration identity: {key}")
            records[key] = record
    return records


def local_record(row, registrations):
    result = {key: row[key] for key in (
        "year", "state_code", "jurisdiction_id", "jurisdiction", "total_participation",
        "statewide_unit", "supplemental_unit", "methods", "source_url", "source_details")}
    key = row["state_code"], row["jurisdiction_id"], row["jurisdiction"]
    result.update(registrations.get(key, {
        "registered": None, "registration_field": None, "registration_comment": "",
        "registration_definition": "",
    }))
    participants, registered = result["total_participation"], result["registered"]
    quality = []
    if participants is None:
        quality.append("Participation not reported.")
    if registered is None:
        quality.append("No matched reported registration denominator.")
    elif not registered:
        quality.append("Zero registration denominator.")
    elif participants is not None and participants > registered:
        quality.append("Participation exceeds reported registrations; rate withheld.")
    result["turnout_pct"] = (
        100 * participants / registered
        if participants is not None and registered and participants <= registered else None)
    result["quality"] = quality
    result["registration_definition"] = result.get("registration_definition", "")
    result["registration_basis"] = "Source-reported registrations; active/inactive rules and dates vary. Not eligible population."
    return result


REGISTRATION_SOURCES = {
    "2010": ("EAC2010registration.source", "input.xls",
             "https://www.eac.gov/sites/default/files/eac_assets/1/6/2010EAVS_A_Final.xls"),
    "2010-TX": ("EAC2010TXregistration.source", "input.xls",
                "https://www.eac.gov/sites/default/files/eac_assets/1/28/TX_2010%20NVRA_SectionA_Resubmitted.xls"),
    "2010-IL": ("EAC2010ILregistration.source", "input.xls",
                "https://www.eac.gov/sites/default/files/eac_assets/1/28/IL_2010%20NVRA%20Data%20(UPDATED)3.xls"),
    "2012": ("EAC2012registration.source", "input.xlsx",
             "https://www.eac.gov/sites/default/files/eac_assets/1/1/2012EAVS_NVRAData.xlsx"),
}
TIME_SERIES = "https://www.eac.gov/sites/default/files/2026-09/EAVS_Time_Series_2004_2024.xlsx"


def historical_extensions(cache, output, codes):
    originals = output / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    registrations, sources = {}, {}
    for key, (filename, kind, url) in REGISTRATION_SOURCES.items():
        path = cache / filename
        if not path.exists():
            response = requests.get(url, timeout=(15, 120))
            response.raise_for_status()
            path.write_bytes(response.content)
        content = path.read_bytes()
        registrations[key] = registration_records(content, kind, ("TX", "48") if key == "2010-TX" else None)
        sources[key] = {"url": url, "sha256": digest(content), "bytes": len(content)}
        (originals / (key + "-" + kind)).write_bytes(content)
    for code in ("TX", "IL"):
        registrations["2010"] = {key: value for key, value in registrations["2010"].items() if key[0] != code}
        corrected = registrations["2010-" + code]
        if not corrected or {key[0] for key in corrected} != {code}:
            raise ValueError(f"Unrecognized revised 2010 registration source for {code}")
        registrations["2010"].update(corrected)
    path = cache / "EAC-jurisdiction-timeseries.xlsx"
    sources["2004-2006"] = {
        "url": TIME_SERIES, "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size,
        "archived_url": "https://github.com/hanshanley/margin_of_error/releases/download/participation-sources-20261104-late/EAC-jurisdiction-timeseries.xlsx",
        "used_rows": "originals/eac-2004-2006-all-source-fields.csv.gz",
        "guide_url": "https://www.eac.gov/sites/default/files/2026-09/EAVS_Time_Series_User_Guide_v2.1.docx",
    }
    (originals / "eac-timeseries-guide.docx").write_bytes((cache / "EAC-timeseries-guide.docx").read_bytes())
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    values = iter(book.active.values)
    header = next(values)
    rows = []
    with gzip.open(originals / "eac-2004-2006-all-source-fields.csv.gz", "wt", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        for values_row in values:
            source = dict(zip(header, values_row))
            if not source.get("Year"):
                continue
            year, code = int(source["Year"]), source["State_Abbr"]
            if year not in (2004, 2006) or code not in codes:
                continue
            writer.writerow(values_row)
            identifier = normalized_id(source["FIPSCode"])
            name = source["Jurisdiction_Name"]
            methods_data = {mode: methods.count(source.get("turnout_" + suffix))
                            for mode, suffix in (("election_day", "ed"), ("early_in_person", "ev"),
                                                 ("domestic_absentee", "mail"), ("uocava", "uocava"),
                                                 ("provisional", "prov"), ("other", "oth"), ("all_mail", "allmail"))}
            total = methods.count(source["turnout_tot"])
            if total == 0 and not any(value is not None for value in methods_data.values()):
                total = None
            observation = {
                "year": year, "state_code": code, "jurisdiction_id": identifier,
                "jurisdiction": name, "total_participation": total,
                "statewide_unit": code == "AK" or identifier.zfill(10).endswith("00000000"),
                "supplemental_unit": name.upper().startswith("UOCAVA"),
                "methods": methods_data, "source_url": TIME_SERIES,
                "source_details": {
                    "basis": "EAC V2 harmonized counted-ballot total, not the later cast-ballot definition.",
                    "total_field": "2a" if year == 2004 else "Q34Total",
                    "registration_field": "1a+1b" if year == 2004 else "Q022006Total",
                    "turnout_comment": source.get("turnout_com"), "registration_comment": source.get("regist_com"),
                    "raw_total": source["turnout_tot"], "raw_registration": source["regist_tot"],
                    "harmonization": "EAC jurisdiction-level series; no county-collapse equal allocations used.",
                },
            }
            registration = {
                "registered": methods.count(source["regist_tot"]),
                "registration_field": "1a+1b" if year == 2004 else "Q022006Total",
                "registration_comment": str(source.get("regist_com") or ""),
                "registration_definition": "EAC harmonized source registration total; jurisdiction rules vary.",
            }
            row = local_record(observation, {(code, identifier, name): registration})
            row["quality"].append("2004/2006 count ballots counted; definitions differ from later cast-ballot totals. EAC harmonized totals can reflect incomplete component reporting.")
            rows.append(row)
    book.close()
    if {r["year"] for r in rows} != {2004, 2006}:
        raise ValueError("Missing historical extension years")
    return rows, registrations, sources


def name_key(value):
    value = re.sub(r"\s+-\s+.*$", "", value.upper())
    value = re.sub(r"\s+00$", "", value)
    value = re.sub(r"\b(TOWN|CITY|VILLAGE|COUNTY|PARISH|TOWNSHIP|BOROUGH|OF)\b", "", value)
    return re.sub(r"[^A-Z0-9]", "", value)


def match_geography(row, county, municipality, state_fips):
    if row["statewide_unit"] or row["supplemental_unit"]:
        return None
    identifier = row["jurisdiction_id"].zfill(10)
    if len(identifier) == 10 and identifier.endswith("00000"):
        feature = county.get(identifier[:5])
        if feature and name_key(feature["properties"]["name"]) == name_key(row["jurisdiction"]):
            if row["state_code"] == "IL" or identifier[:5] == "29095":
                return None
            return {"level": "county", "key": identifier[:5]}
    key = state_fips + row["jurisdiction_id"][-5:].zfill(5)
    feature = municipality.get(key)
    if feature and name_key(feature["properties"]["name"]) == name_key(row["jurisdiction"]):
        return {"level": "municipality", "key": key}
    return None


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(value, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(content, mtime=0))
    else:
        path.write_bytes(content)


def geometry_sources(year, state_fips, level):
    base = "https://www2.census.gov/geo/tiger/"
    if year == 2008:
        if level == "county":
            return base + "TIGER2008/tl_2008_us_county.zip"
        return None
    if year == 2010:
        suffix = "us_050" if level == "county" else f"{state_fips}_060"
        return base + f"GENZ2010/gz_2010_{suffix}_00_500k.zip"
    if year == 2012:
        suffix = "us_county" if level == "county" else f"{state_fips}_cousub"
        folder = "COUNTY" if level == "county" else "COUSUB"
        return base + f"TIGER2012/{folder}/tl_2012_{suffix}.zip"
    suffix = "us_county" if level == "county" else f"{state_fips}_cousub"
    return base + f"GENZ{year}/shp/cb_{year}_{suffix}_500k.zip"


def collect_geometry(output, cache, years, state_features, research):
    sys.path.insert(0, str(research.resolve()))
    from scripts.build import simplify
    codes = {feature["properties"]["STATE"]: feature["properties"]["STUSAB"]
             for feature in state_features}
    codes = {fips: code for fips, code in codes.items() if code != "PR"}
    municipal = {"CT", "MA", "ME", "NH", "RI", "VT", "WI"}
    jobs = []
    for year in years:
        jobs.append((year, None, "county", geometry_sources(year, None, "county")))
        for fips, code in codes.items():
            if code in municipal:
                url = geometry_sources(year, fips, "municipality")
                if url:
                    jobs.append((year, fips, "municipality", url))
    cache.mkdir(parents=True, exist_ok=True)

    def collect(job):
        year, state_fips, level, url = job
        filename = url.rsplit("/", 1)[-1]
        cached = cache / filename
        if not cached.exists():
            response = requests.get(url, timeout=(15, 120))
            response.raise_for_status()
            if not zipfile.is_zipfile(io.BytesIO(response.content)):
                raise ValueError(f"Not a ZIP: {url}")
            cached.write_bytes(response.content)
        content = cached.read_bytes()
        grouped = defaultdict(dict)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            stem = next(name[:-4] for name in archive.namelist() if name.endswith(".shp"))
            reader = shapefile.Reader(encoding="latin1" if year <= 2014 else "utf-8", **{
                ext: io.BytesIO(archive.read(stem + "." + ext)) for ext in ("shp", "shx", "dbf")})
            for record in reader.iterShapeRecords():
                p = record.record.as_dict()
                sf = str(p.get("STATEFP") or p.get("STATEFP10") or p.get("STATE") or "")
                code = codes.get(sf)
                if not code:
                    continue
                county = str(p.get("COUNTYFP") or p.get("COUNTYFP10") or p.get("COUNTY") or "")
                name = p.get("NAME") or p.get("NAME10") or p.get("NAMELSAD") or p.get("NAMELSAD10")
                suffix = p.get("COUSUBFP") or p.get("COUSUBFP10") or p.get("COUSUB")
                key = sf + (str(suffix) if level == "municipality" else county)
                if not name or not re.fullmatch(r"\d{7}" if level == "municipality" else r"\d{5}", key):
                    raise ValueError(f"Unrecognized geographic identity in {url}: {p}")
                geo = record.shape.__geo_interface__
                polygons = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
                converted = []
                for polygon in polygons:
                    rings = []
                    for ring_index, ring in enumerate(polygon):
                        points = [[round(x, 5), round(y, 5)] for x, y, *rest in simplify(ring, .00035)]
                        if len(points) >= 4:
                            rings.append(points)
                        elif ring_index == 0:
                            break
                    if rings:
                        converted.append(rings)
                if not converted:
                    continue
                if key not in grouped[code]:
                    grouped[code][key] = {
                        "type": "Feature", "properties": {
                            "key": key, "name": name, "state_code": code,
                            "boundary_year": year, "level": level,
                        }, "geometry": {"type": "MultiPolygon", "coordinates": []},
                    }
                grouped[code][key]["geometry"]["coordinates"].extend(converted)
        if sum(len(features) for features in grouped.values()) < (3000 if level == "county" else 10):
            raise ValueError(f"Incomplete or unrecognized {year} {level} collection")
        paths = {}
        for code, features in grouped.items():
            path = f"geometry/{year}/{level}-{code}.geojson.gz"
            write_json(output / path, {"type": "FeatureCollection", "features": list(features.values())})
            paths[code] = path
        print("Geometry", year, level, state_fips or "US", sum(len(f) for f in grouped.values()), flush=True)
        return year, level, paths, {"url": url, "sha256": digest(content), "bytes": len(content)}

    geometry, sources, failures = {}, {}, []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [(job, executor.submit(collect, job)) for job in jobs]
        for job, future in futures:
            try:
                year, level, paths, source = future.result()
                geometry.setdefault(str(year), {}).setdefault(level, {}).update(paths)
                sources[source["url"]] = source
            except Exception as error:
                failures.append({"year": job[0], "state_fips": job[1], "level": job[2],
                                 "source_url": job[3], "error": str(error)})
                print("Geometry unavailable", job[:3], str(error), flush=True)
    return geometry, sources, failures


def build(output, cache=None, research=Path("../voter-participation"), reuse_geometry=False, supplement_cache=None):
    root = Path("public/participation-methods")
    root /= json.loads((root / "latest.json").read_text())["snapshot_id"]
    index = json.loads((root / "index.json").read_text())
    checksums = json.loads((root / "checksums.json").read_text())
    source_bytes = (root / "complete-methods.zip").read_bytes()
    if digest(source_bytes) != checksums["complete-methods.zip"]:
        raise ValueError("Changed complete original-source archive")
    states_data = json.loads(Path("public/voter-participation/data/states.json").read_text())
    state_rows = states_data if isinstance(states_data, list) else states_data["records"]
    geometry = json.loads(Path("public/voter-participation/data/states.geojson").read_text())
    names = {row["state"] for row in state_rows}
    state_features = [feature for feature in geometry["features"] if feature["properties"]["NAME"] in names]
    codes = sorted(feature["properties"]["STUSAB"] for feature in state_features)
    years = sorted({row["year"] for row in state_rows} | {2026})
    rows = []
    provenance = {}
    supplemental_registrations, supplemental_sources = {}, {}
    if supplement_cache:
        earlier, supplemental_registrations, supplemental_sources = historical_extensions(supplement_cache, output, codes)
        rows.extend(earlier)
    with zipfile.ZipFile(io.BytesIO(source_bytes)) as archive:
        for year in index["state_years"]:
            filename = f"eavs-{year}." + ("csv" if year == 2018 else "zip")
            original = archive.read("originals/" + filename)
            source = index["sources"][filename]
            if digest(original) != source["sha256"]:
                raise ValueError(f"Changed original {filename}")
            provenance[str(year)] = source
            observations_path = root / f"jurisdictions-{year}.json"
            observations_bytes = observations_path.read_bytes()
            if digest(observations_bytes) != checksums[observations_path.name]:
                raise ValueError(f"Changed normalized participation: {observations_path.name}")
            registrations = registration_records(original, filename)
            registrations.update(supplemental_registrations.get(str(year), {}))
            observations = json.loads(observations_bytes)
            joined = [local_record(row, registrations) for row in observations]
            rows.extend(joined)
            print(year, "units", len(joined), "states", len({r["state_code"] for r in joined}),
                  "matched registration rates", sum(r["turnout_pct"] is not None for r in joined),
                  flush=True)
    source_years = sorted({row["year"] for row in rows})
    grouped = defaultdict(list)
    for row in rows:
        row["history_key"] = row["jurisdiction_id"].zfill(10) + "|" + name_key(row["jurisdiction"])
        grouped[row["state_code"]].append(row)
    for observations in grouped.values():
        counts = defaultdict(int)
        for row in observations:
            counts[(row["year"], row["history_key"])] += 1
        ambiguous = {key for (_, key), count in counts.items() if count > 1}
        for row in observations:
            if row["history_key"] in ambiguous:
                row["history_key"] = row["jurisdiction_id"] + "|" + row["jurisdiction"]
    if reuse_geometry:
        saved = json.loads((output / "index.json").read_text())
        geo, geo_sources, geo_failures = saved["geometry"], saved["geometry_sources"], saved["geometry_failures"]
        for source in geo_sources.values():
            if digest((cache / source["url"].rsplit("/", 1)[-1]).read_bytes()) != source["sha256"]:
                raise ValueError(f"Changed cached geometry source: {source['url']}")
    else:
        geo, geo_sources, geo_failures = collect_geometry(
            output, cache, index["state_years"], state_features, research) if cache else ({}, {}, [])
    fips = {f["properties"]["STUSAB"]: f["properties"]["STATE"] for f in state_features}
    for year in source_years:
        for code in codes:
            features = {}
            for level in ("county", "municipality"):
                path = geo.get(str(year), {}).get(level, {}).get(code)
                collection = json.loads(gzip.decompress((output / path).read_bytes())) if path else {"features": []}
                if any(f["properties"]["boundary_year"] != year or f["properties"]["state_code"] != code
                       for f in collection["features"]):
                    raise ValueError(f"Geometry identity/vintage mismatch: {path}")
                features[level] = {f["properties"]["key"]: f for f in collection["features"]}
            matched = defaultdict(list)
            for row in grouped[code]:
                if row["year"] == year:
                    row["geography"] = match_geography(row, features["county"], features["municipality"], fips[code])
                    if row["geography"]:
                        matched[tuple(row["geography"].values())].append(row)
            for units in matched.values():
                if len(units) > 1:
                    for row in units:
                        row["geography"] = None
                        row["quality"].append("Multiple reporting units match this boundary; no aggregation applied.")
    for code, observations in grouped.items():
        write_json(output / "states" / f"{code}.json.gz", observations)
        old = output / "states" / f"{code}.json"
        if old.exists():
            old.unlink()
    coverage = []
    for code in codes:
        for year in years:
            observations = [r for r in grouped[code] if r["year"] == year]
            coverage.append({
                "state_code": code, "year": year,
                "reporting_units": len(observations),
                "with_participation": sum(r["total_participation"] is not None for r in observations),
                "with_registration_rate": sum(r["turnout_pct"] is not None for r in observations),
                "with_matched_geometry": sum(r.get("geography") is not None for r in observations),
                "status": "reported_local_units" if observations else "local_source_not_verified",
                "precinct_status": "separate_nc_export" if code == "NC" and 2002 <= year <= 2024
                else "precinct_source_not_verified",
            })
    write_json(output / "coverage.json", coverage)
    output.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(filename=output / "observations.csv.gz", mode="wb", mtime=0) as compressed, \
            io.TextIOWrapper(compressed) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: json.dumps(value, separators=(",", ":"))
                         if isinstance(value, (dict, list)) else value
                         for key, value in row.items()} for row in rows)
    old_csv = output / "observations.csv"
    if old_csv.exists():
        old_csv.unlink()
    write_json(output / "index.json", {
        "source_snapshot_id": index["snapshot_id"], "sources": provenance,
        "collector_sha256": digest(Path(__file__).read_bytes()),
        "state_codes": codes, "years": source_years, "records": len(rows),
        "supplemental_sources": supplemental_sources,
        "coverage": "coverage.json",
        "geometry": geo, "geometry_sources": geo_sources, "geometry_failures": geo_failures,
        "notes": [
            "EAC county, municipal and statewide reporting units are not nationwide precinct data.",
            "Only exact state, reporting-unit ID and name matches join registrations to participation.",
            "A1 (2008), QA1a and A1a are source-reported registrations, not citizen voting-age population. Early active/inactive definitions vary and are preserved.",
            "2004/2006 use EAC V2 jurisdiction-level harmonized counts, not the equally allocated county-collapse file.",
            "No 2004/2006 election-year geometry is substituted; reporting-unit counts and histories remain accessible.",
            "Earlier unmatched denominators remain missing; observations are never interpolated.",
            "Reporting boundaries, registration dates and participation measurement can change.",
            "Illinois counties and Jackson County MO are not shaded because separate city election offices can exclude part of the Census county.",
            "Historical unit keys use IDs and standardized names, not a constant-geography crosswalk.",
            "All original survey inputs are retained in the complete historical methods download.",
        ],
    })
    write_json(output / "checksums.json", {
        str(path.relative_to(output)): {"sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
        for path in sorted(output.rglob("*")) if path.is_file() and path.name != "checksums.json"
    })
    print("Saved", len(rows), "observations;", len(codes), "states/DC;", len(coverage),
          "state-year coverage entries", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--geometry-cache", type=Path)
    parser.add_argument("--research", type=Path, default=Path("../voter-participation"))
    parser.add_argument("--reuse-geometry", action="store_true")
    parser.add_argument("--supplement-cache", type=Path)
    args = parser.parse_args()
    build(args.output, args.geometry_cache, args.research, args.reuse_geometry, args.supplement_cache)

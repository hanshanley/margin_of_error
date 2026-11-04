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


def registration_records(content, name):
    records = {}
    for _, values in methods.datasets(content, name):
        header_index = next((i for i, row in enumerate(values[:20])
                             if any(str(v).lower() in ("a1a", "qa1a") for v in row)), None)
        if header_index is None:
            continue
        fields = [str(value).lower() for value in values[header_index]]
        for values_row in values[header_index + 1:]:
            row = dict(zip(fields, values_row))
            key = identity(row)
            if not key[0] or not key[1]:
                continue
            field = "qa1a" if "qa1a" in row else "a1a"
            record = {
                "registered": reported(row, field),
                "registration_field": field,
                "registration_comment": str(row.get("a1comments") or row.get("qa1_comment") or ""),
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
    result["registration_basis"] = "Reported total registrations (active and inactive), not eligible population."
    return result


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


def build(output, cache=None, research=Path("../voter-participation"), reuse_geometry=False):
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
            observations = json.loads(observations_bytes)
            joined = [local_record(row, registrations) for row in observations]
            rows.extend(joined)
            print(year, "units", len(joined), "states", len({r["state_code"] for r in joined}),
                  "matched registration rates", sum(r["turnout_pct"] is not None for r in joined),
                  flush=True)
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
    for year in index["state_years"]:
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
        "state_codes": codes, "years": index["state_years"], "records": len(rows),
        "coverage": "coverage.json",
        "geometry": geo, "geometry_sources": geo_sources, "geometry_failures": geo_failures,
        "notes": [
            "EAC county, municipal and statewide reporting units are not nationwide precinct data.",
            "Only exact state, reporting-unit ID and name matches join registrations to participation.",
            "A1a/QA1a is reported total registration, not citizen voting-age population.",
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
    args = parser.parse_args()
    build(args.output, args.geometry_cache, args.research, args.reuse_geometry)

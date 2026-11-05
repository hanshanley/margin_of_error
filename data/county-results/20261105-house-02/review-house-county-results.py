"""Reconcile complete 2026 House county vectors against their actual district sources."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import tarfile
import zipfile

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform


spec = importlib.util.spec_from_file_location(
    "house_county_sources", Path(__file__).with_name("acquire-house-county-results.py"))
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)

FIELDS = ["year", "state_code", "level", "geography", "geography_name", "contest",
          "democratic_votes", "republican_votes", "other_votes", "total_votes", "margin_pp"]
COUNTY_TYPES = {"County", "Parish", "Borough", "City"}
NESTED_TYPES = {"Town", "Township", "House District", "State"}


def candidate_vector(candidates):
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Missing explicit candidate collection")
    vector = {}
    for candidate in candidates:
        name, party, votes = (candidate.get(k) for k in ["name", "party", "votes"])
        if (not isinstance(name, str) or not name.strip()
                or not isinstance(party, str) or not party.strip()
                or type(votes) is not int or votes < 0):
            raise ValueError("Missing literal candidate identity or explicit nonnegative integer count")
        key = (name, party)
        if key in vector:
            raise ValueError("Duplicate literal candidate/party identity")
        vector[key] = votes
    return vector


def checked_file(folder, name, url):
    path = folder / name
    raw = path.read_bytes()
    receipt = json.loads(path.with_suffix(path.suffix + ".receipt.json").read_bytes())
    if (receipt.get("status") != 200 or receipt.get("url") != url
            or receipt.get("bytes") != len(raw)
            or receipt.get("sha256") != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Original byte/URL/status receipt mismatch: " + name)
    return raw


def county_reference(folder):
    root = "https://www2.census.gov/geo/tiger/TIGER2026/COUNTY/"
    index = checked_file(folder, "official-index.html", root)
    if b'tl_2026_us_county.zip' not in index:
        raise ValueError("Complete county archive not declared by original official index")
    raw = checked_file(folder, "tl_2026_us_county.zip", root + "tl_2026_us_county.zip")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() is not None:
            raise ValueError("Invalid complete county ZIP")
        reader = shapefile.Reader(dbf=io.BytesIO(archive.read("tl_2026_us_county.dbf")))
        records = {}
        for item in reader.records():
            row = item.as_dict()
            key = row["GEOID"]
            if (not re.fullmatch(r"\d{5}", key) or key != row["STATEFP"] + row["COUNTYFP"]
                    or key in records or not row["NAME"] or not row["NAMELSAD"]):
                raise ValueError("Invalid or duplicated native county reference identity")
            records[key] = {field: row[field] for field in
                            ["GEOID", "STATEFP", "NAME", "NAMELSAD", "LSAD", "CLASSFP"]}
    return records


def county_identity(region, state_fips, reference):
    fips = region.get("fips")
    if fips is not None:
        if (not isinstance(fips, str) or not re.fullmatch(r"\d{5}", fips)
                or not fips.startswith(state_fips) or fips not in reference):
            raise ValueError("Native county FIPS is absent from the correct-state 2026 reference")
        return fips, "explicit_native_fips"
    name = region.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Missing native county-equivalent identity")
    normalize = lambda value: value.casefold().replace(".", "")
    matches = [key for key, row in reference.items() if row["STATEFP"] == state_fips
               and normalize(name) in {normalize(row["NAME"]), normalize(row["NAMELSAD"])}]
    if len(matches) != 1:
        raise ValueError("Native name lacks a unique literal 2026 county-equivalent reference")
    return matches[0], "unique_census_name_casefold_periods"


def district_counties(data, declared, state_fips, reference):
    sources.district_scope(data, declared)
    expected = candidate_vector(data.get("candidates"))
    totals = Counter({key: 0 for key in expected})
    counties, unlocated, ignored = [], [], []
    seen = set()
    selected_types = {"Planning Region"} if declared["state_code"] == "CT" else COUNTY_TYPES
    for key, region in data["region_results"].items():
        kind = region.get("type")
        if kind in NESTED_TYPES or (declared["state_code"] == "CT" and kind == "County"):
            ignored.append(dict(source_key=key, native_type=kind))
            continue
        if kind not in selected_types | {"Overseas"}:
            raise ValueError("Unreviewed native geography level: " + str(kind))
        vector = candidate_vector(region.get("candidates"))
        if set(vector) != set(expected):
            raise ValueError("County/unlocated candidate inventory differs from its district")
        totals.update(vector)
        row = dict(source_key=key, native_name=region.get("name"), native_type=kind,
                   candidates=[dict(name=name, party=party, votes=votes)
                               for (name, party), votes in vector.items()])
        if kind == "Overseas":
            unlocated.append(row)
            continue
        cook = data["region_results"].get("cook", {})
        if (declared["state_code"] == "IL" and key == "chicago"
                and kind == "County" and region.get("name") == "Chicago"
                and region.get("fips") is None and region.get("percent_reporting") == 0
                and not any(vector.values()) and cook.get("name") == "Cook"
                and cook.get("type") == "County" and cook.get("fips") == "17031"):
            unlocated.append(dict(row, geographic_status="explicit_zero_unlocated_chicago_reporting_row",
                                  native_percent_reporting=region["percent_reporting"]))
            continue
        fips, strategy = county_identity(region, state_fips, reference)
        if fips in seen:
            raise ValueError("Duplicate county equivalent within one district")
        seen.add(fips)
        counties.append(dict(row, geography=fips, join_strategy=strategy))
    if not counties:
        raise ValueError("No direct county-equivalent results")
    if dict(totals) != expected:
        raise ValueError("County plus explicit unlocated candidate vectors do not equal district totals")
    return dict(counties=counties, unlocated_regions=unlocated, ignored_nested_regions=ignored,
                candidate_totals=data["candidates"], district=declared["district"],
                source_url=declared["url"], source_updated_at=data.get("last_updated"))


def state_counties(code, declared, reviewed, reference, state_fips):
    keys = [key for key, row in declared.items() if row["state_code"] == code]
    if not keys or any(key not in reviewed or "error" in reviewed[key] for key in keys):
        raise ValueError("Not every declared state district passed source and vector reconciliation")
    grouped = {}
    for key in keys:
        for fragment in reviewed[key]["counties"]:
            fips = fragment["geography"]
            grouped.setdefault(fips, []).append(dict(fragment, district=declared[key]["district"],
                source_url=declared[key]["url"], source_updated_at=reviewed[key]["source_updated_at"]))
    expected = {key for key, row in reference.items() if row["STATEFP"] == state_fips}
    if set(grouped) != expected:
        raise ValueError("Complete state county-equivalent reference inventory is not covered")
    rows = []
    for fips, fragments in sorted(grouped.items()):
        votes = Counter()
        for fragment in fragments:
            for candidate in fragment["candidates"]:
                votes[candidate["party"]] += candidate["votes"]
        total = sum(votes.values())
        dem, rep = votes["Democratic"], votes["Republican"]
        rows.append(dict(year=2026, state_code=code, level="county", geography=fips,
                         geography_name=reference[fips]["NAMELSAD"],
                         contest="U.S. House district contests aggregated within county",
                         democratic_votes=dem, republican_votes=rep,
                         other_votes=total - dem - rep, total_votes=total,
                         margin_pp=100 * (dem - rep) / total if total else None,
                         district_fragments=fragments))
    return rows


def projected_county(geometry, project):
    original = shape(geometry)
    if original.is_empty or not original.is_valid or original.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Invalid native Census county polygon; not repaired or substituted")
    projected = transform(project, original)
    if projected.is_empty or not projected.is_valid:
        raise ValueError("County transformation produced an invalid polygon")
    return mapping(projected)


def county_geometries(folder, rows):
    wanted = {row["geography"]: row for row in rows}
    features, excluded, found = {}, {}, set()
    with zipfile.ZipFile(folder / "tl_2026_us_county.zip") as archive:
        project = Transformer.from_crs(
            CRS.from_wkt(archive.read("tl_2026_us_county.prj").decode()), CRS.from_epsg(4326),
            always_xy=True).transform
        reader = shapefile.Reader(**{suffix: io.BytesIO(archive.read("tl_2026_us_county." + suffix))
                                     for suffix in ["shp", "shx", "dbf"]})
        for item in reader.iterShapeRecords():
            native = item.record.as_dict()
            key = native["GEOID"]
            if key not in wanted:
                continue
            if key in found:
                raise ValueError("Duplicate mapped native county identity")
            found.add(key)
            row = wanted[key]
            try:
                geometry = projected_county(item.shape.__geo_interface__, project)
                features.setdefault(row["state_code"], []).append(dict(type="Feature", geometry=geometry,
                    properties=dict(key=key, name=native["NAMELSAD"], state_code=row["state_code"],
                                    boundary_year=2026,
                                    geometry_scope="Unsimplified 2026 Census county reference; not precincts")))
            except ValueError as error:
                excluded[key] = str(error)
    if found != set(wanted):
        raise ValueError("A reviewed county is absent from the complete native shapefile")
    return {code: dict(type="FeatureCollection", features=items)
            for code, items in sorted(features.items())}, excluded


def archive_inputs(folder, output):
    inventory = {}
    with output.open("xb") as target, gzip.GzipFile(fileobj=target, mode="wb", mtime=0, filename="") as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as archive:
            for path in sorted(folder.rglob("*")):
                if not path.is_file():
                    continue
                raw = path.read_bytes()
                name = path.relative_to(folder).as_posix()
                info = tarfile.TarInfo(name)
                info.size, info.mtime, info.mode = len(raw), 0, 0o644
                archive.addfile(info, io.BytesIO(raw))
                inventory[name] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cache", required=True, type=Path)
    parser.add_argument("--reference-cache", required=True, type=Path)
    parser.add_argument("--state-codes", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--map", action="store_true", help="Export unsimplified correct-year county reference shapes")
    args = parser.parse_args()
    reference = county_reference(args.reference_cache)
    codes = json.loads(args.state_codes.read_bytes())
    if (not sources.STATES <= set(codes) or len(set(codes.values())) != len(codes)
            or any(not re.fullmatch(r"\d{2}", code) for code in codes.values())):
        raise ValueError("Invalid complete state FIPS crosswalk")
    national = json.loads((args.source_cache / "original-national-house.json").read_bytes())
    declared = sources.declared_districts(national)
    reviewed = {}
    for key, binding in declared.items():
        try:
            data, receipt = sources.saved_response(args.source_cache, key, binding)
            reviewed[key] = dict(district_counties(data, binding, codes[binding["state_code"]], reference),
                                 source_sha256=receipt["sha256"])
        except Exception as error:
            reviewed[key] = dict(error=str(error), exception=type(error).__name__, **binding)
    rows, states = [], {}
    for code in sorted(sources.STATES):
        try:
            accepted = state_counties(code, declared, reviewed, reference, codes[code])
            rows.extend(accepted)
            states[code] = dict(status="county_candidate_vectors_reconciled",
                               counties=len(accepted), total_votes=sum(r["total_votes"] for r in accepted))
        except ValueError as error:
            states[code] = dict(status="withheld", error=str(error))
    args.output.mkdir(parents=True, exist_ok=False)
    def write_json(name, data):
        raw = (json.dumps(data, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode()
        (args.output / name).write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)
    write_json("county-results.json.gz", rows)
    write_json("county-reference.json.gz", reference)
    write_json("state-codes.json", codes)
    with (args.output / "county-results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    audit = dict(year=2026, election_date="2026-11-03", contest="U.S. House general election",
                 scope="Unofficial provider candidate counts, not ballots, unique voters or turnout",
                 geographic_level="county_equivalent", boundary_reference_year=2026,
                 margin_definition="100 * (Democratic - Republican) / all candidate votes",
                 participation_available=False, precinct_coverage_added=0,
                 declared_districts=len(declared),
                 reconciled_districts=sum("error" not in r for r in reviewed.values()),
                 accepted_states=sum(r["status"] != "withheld" for r in states.values()),
                 normalized_counties=len(rows), states=states, districts=reviewed,
                 notes="Every county/unlocated vector has the full literal district candidate inventory. "
                 "Counties plus separately retained explicit unlocated regions must sum to each district. "
                 "Illinois Chicago rows without FIPS remain unlocated only when every explicit candidate "
                 "count and reported percentage is zero and a native Cook County FIPS 17031 row exists. "
                 "These placeholders are not mapped, merged into Cook, or interpreted as zero participation. "
                 "Overlapping town/district/state views are retained in originals, not added. "
                 "A state is withheld if any declared district fails or any 2026 county equivalent is absent. "
                 "FIPS joins are direct; missing FIPS permits only unique Census short/long names "
                 "(ignoring case and periods only), never spelling aliases or allocated votes. "
                 "For example, St Joseph matches St. Joseph, not Saint Joseph. Snapshots can differ in update time. "
                 "Party totals follow native literal parties; no fusion-line reassignment.",
                 reproduction="Extract originals/provider.tar.gz and originals/census-reference.tar.gz into "
                 "separate empty directories. Run review-house-county-results.py --source-cache PROVIDER "
                 "--reference-cache CENSUS --state-codes state-codes.json --output NEW_DIR --archive NEW_ZIP. "
                 "Add --map to reproduce index/margins/geometry exports. "
                 "Requires Python 3, requests, pyshp, pyproj and shapely; no network access.")
    if args.map:
        geometries, excluded = county_geometries(args.reference_cache, rows)
        (args.output / "geometry").mkdir()
        coverage = {}
        for code, data in geometries.items():
            name = "geometry/" + code + ".geojson.gz"
            raw = (json.dumps(data, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
            (args.output / name).write_bytes(gzip.compress(raw, mtime=0))
            keys = {feature["properties"]["key"] for feature in data["features"]}
            coverage[code] = dict(file=name, counties=len(keys),
                colored_counties=sum(row["state_code"] == code and row["geography"] in keys
                                     and row["margin_pp"] is not None for row in rows))
        margins = [dict({key: value for key, value in row.items() if key != "district_fragments"},
                        office="U.S. House aggregate", contest_votes=row["total_votes"], provisional=True,
                        source_url=row["district_fragments"][0]["source_url"],
                        source_urls=sorted({fragment["source_url"] for fragment in row["district_fragments"]}),
                        district_count=len(row["district_fragments"]), boundary_reference_year=2026)
                   for row in rows]
        write_json("margins.json", margins)
        write_json("index.json", dict(year=2026, coverage=coverage, margins_file="margins.json",
            geographic_level="county_equivalent", office="U.S. House aggregate",
            normalized_counties=len(rows), mapped_counties=sum(r["counties"] for r in coverage.values()),
            colored_counties=sum(r["colored_counties"] for r in coverage.values()),
            boundary_reference_year=2026, participation_available=False,
            scope="County candidate votes aggregated across each county's actual House district fragments. "
            "Unofficial counts, not precinct results or turnout. Complete state district and candidate-vector "
            "reconciliation required. Explicit overseas regions and zero-only unresolved Chicago reporting "
            "placeholders remain separately unlocated in audit.json; no votes are allocated or merged. "
            "Unsimplified 2026 Census county reference shapes transformed from NAD83 to WGS84; invalid native "
            "polygons withheld, not repaired. Not certified election-precinct boundaries.",
            withheld_states={code: result for code, result in states.items() if result["status"] == "withheld"},
            excluded_geometry=excluded))
        audit["geometry"] = dict(reference_year=2026, source_crs="Native .prj",
                                 output_crs="EPSG:4326", simplification=False,
                                 mapped_counties=sum(r["counties"] for r in coverage.values()),
                                 excluded_geometry=excluded)
    if args.archive:
        originals = args.output / "originals"
        originals.mkdir()
        inventory = {name: archive_inputs(folder, originals / (name + ".tar.gz")) for name, folder in
                     [("provider", args.source_cache), ("census-reference", args.reference_cache)]}
        write_json("inputs.json.gz", inventory)
        for name in [Path(__file__).name, "acquire-house-county-results.py"]:
            (args.output / name).write_bytes(Path(__file__).with_name(name).read_bytes())
    write_json("audit.json", audit)
    if args.archive:
        checksums = {path.relative_to(args.output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(args.output.rglob("*")) if path.is_file()}
        write_json("checksums.json", checksums)
        args.archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
            for path in sorted(args.output.rglob("*")):
                if path.is_file():
                    item = zipfile.ZipInfo(path.relative_to(args.output).as_posix(), (2026, 11, 5, 0, 0, 0))
                    item.external_attr = 0o100644 << 16
                    archive.writestr(item, path.read_bytes())
        print("ARCHIVE", args.archive.stat().st_size,
              hashlib.sha256(args.archive.read_bytes()).hexdigest(), flush=True)
    print("COUNTY_REVIEW", audit["accepted_states"], "states", len(rows), "county equivalents", flush=True)
    for code, result in states.items():
        print(code, result, flush=True)


if __name__ == "__main__":
    main()

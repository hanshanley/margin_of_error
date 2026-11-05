"""Map Vermont 2026 reporting splits without allocating votes or municipal turnout."""

import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

from shapely.geometry import mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


review = module("review-vermont-precinct-results")
geometry = module("build-north-dakota-precinct-results")
ITEM = "029e24e674234e2f8c1e3ae059931fcb"
SERVICE = ("https://services1.arcgis.com/BkFxaEFNwHqX3tAw/arcgis/rest/services/"
           "FS_VCGI_VT_VOTE_AREAS_2026_general_WM_v1/FeatureServer")
TOLERANCE = 1e-10


def district_label(value):
    return " ".join(re.sub("[-_]+", " ", value).upper().split())


def mapped_splits(rows, boundary):
    if (boundary.get("exceededTransferLimit") or boundary.get("geometryType") != "esriGeometryPolygon"
            or boundary.get("spatialReference", {}).get("wkid") != 4326):
        raise ValueError("Incomplete or incorrectly projected VT boundaries")
    reporting, expected = {}, defaultdict(set)
    for row in rows:
        key = (row["town"].upper(), district_label(row["house_district"]),
               district_label(row["senate_district"]))
        if key in reporting:
            raise ValueError("VT reporting identities collide after punctuation normalization")
        reporting[key] = row
        expected[key[0]].add(key)
    groups, town_geoids, source_parts = defaultdict(list), defaultdict(set), defaultdict(list)
    actual, seen, repairs = defaultdict(set), set(), []
    for feature in boundary["features"]:
        p = feature["attributes"]
        oid, geoid = p["OBJECTID"], p["TOWN_GEOID"]
        if (type(oid) is not int or oid in seen or not re.fullmatch(r"50\d{8}", geoid)
                or not geoid.startswith(f'50{int(p["CNTY"]):03}')):
            raise ValueError("Duplicate VT boundary or inconsistent town/county geographic identity")
        seen.add(oid)
        key = (p["TOWN"].upper(), district_label(p["HOUSE_NAME"]), district_label(p["SEN_NAME"]))
        polygon, repair = geometry.esri_polygon(feature["geometry"]["rings"])
        if repair:
            repairs.append(dict(object_id=oid, **repair))
        groups[key].append(polygon)
        source_parts[key].append(oid)
        town_geoids[key[0]].add(geoid)
        actual[key[0]].add(key)
    if any(len(ids) != 1 for ids in town_geoids.values()):
        raise ValueError("VT town name maps to multiple geographic identities")
    polygons = {key: unary_union(parts) for key, parts in groups.items()}
    if any(p.is_empty or not p.is_valid or p.geom_type not in {"Polygon", "MultiPolygon"}
           for p in polygons.values()):
        raise ValueError("Invalid dissolved VT reporting-split geometry")
    conflicts = defaultdict(list)
    internal_overlaps = []
    for key, parts in groups.items():
        excess = sum(part.area for part in parts) - polygons[key].area
        if excess > TOLERANCE:
            internal_overlaps.append(dict(identity=key, excess_area_degrees_squared=excess))
            conflicts[key[0]].append("overlapping_parts_within_reporting_split")
    keys, values = list(polygons), list(polygons.values())
    tree, overlaps = STRtree(values), []
    for i, polygon in enumerate(values):
        for j in tree.query(polygon, predicate="intersects"):
            if j <= i:
                continue
            area = polygon.intersection(values[j]).area
            if area > TOLERANCE:
                left, right = keys[i], keys[j]
                overlaps.append(dict(left=left, right=right, area_degrees_squared=area,
                                     left_fraction=area / polygon.area, right_fraction=area / values[j].area))
                conflicts[left[0]].append("overlapping_reference_reporting_units")
                conflicts[right[0]].append("overlapping_reference_reporting_units")
    towns = {}
    for town, identities in sorted(expected.items()):
        reasons = set(conflicts[town])
        if identities != actual.get(town, set()):
            reasons.add("different_town_or_legislative_split_scope")
        towns[town] = dict(exact=not reasons, reasons=sorted(reasons),
            reporting_only=sorted(identities - actual.get(town, set())),
            boundary_only=sorted(actual.get(town, set()) - identities),
            reporting_units=len(identities), town_geoids=sorted(town_geoids.get(town, set())))
    mapped = []
    for key, row in reporting.items():
        if not towns[key[0]]["exact"]:
            continue
        properties = dict(row, county=row["county_name"], county_code=row["county"],
            precinct=f'{row["town"]} / {row["house_district"]} / {row["senate_district"]}',
            precinct_code=row["precinct"], town_geoid=next(iter(town_geoids[key[0]])),
            match_status="matched", boundary_date="2026 general-election reference",
            source_object_ids=sorted(source_parts[key]),
            boundary_provenance="Official November 2026 VCGI voting areas dissolved by exact town, House "
                "and Senate identity, normalizing only case, whitespace, hyphens and underscores in district "
                "labels. No town aliases inferred. Every town's complete split set must agree. Entire towns "
                "with reference overlaps are withheld; no boundary clipping or vote allocation. These are "
                "town-legislative reporting splits, not independently established polling precincts. "
                "Municipal registration and participation remain separate; no precinct rate is inferred.")
        mapped.append(dict(type="Feature", properties=properties, geometry=mapping(polygons[key])))
    audit = dict(towns=towns, reference_groups=len(groups), source_parts=len(seen),
        boundary_only_groups=sorted(set(groups) - set(reporting)),
        overlap_pairs=overlaps, internal_overlaps=internal_overlaps, topology_repairs=repairs,
        overlap_tolerance_degrees_squared=TOLERANCE, coordinate_grid_degrees=geometry.GRID,
        mapped_units=len(mapped), reporting_units=len(rows),
        withheld_units=[row["key"] for key, row in reporting.items() if not towns[key[0]]["exact"]])
    return mapped, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-directory", required=True, type=Path)
    parser.add_argument("--boundaries-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable VT mapped snapshot")
    for name, receipt in json.loads((args.review_directory / "checksums.json").read_text()).items():
        raw = (args.review_directory / name).read_bytes()
        if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("VT original count review changed: " + name)

    def original(name):
        return json.loads(gzip.decompress((args.review_directory / "originals" / (name + ".gz")).read_bytes()))

    rows, statistics = review.vt_results(original(f"full-results-{review.STAMP}.json"),
        original("election.json"), original(f"turnOut-{review.STAMP}.json"))
    text = io.StringIO()
    writer = csv.DictWriter(text, review.results.CSV_FIELDS + review.EXTRA_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    if text.getvalue().encode() != gzip.decompress((args.review_directory / "results.csv.gz").read_bytes()):
        raise ValueError("VT mapped supplement changes original normalized counts")
    if statistics != json.loads(gzip.decompress(
            (args.review_directory / "municipal-participation.json.gz").read_bytes())):
        raise ValueError("VT mapped supplement changes municipal participation")
    receipts = json.loads((args.boundaries_cache / "sources.json").read_text())
    originals = {}
    expected = dict(item="https://www.arcgis.com/sharing/rest/content/items/" + ITEM,
                    service=SERVICE, layer=SERVICE + "/0", count=SERVICE + "/0/query",
                    areas=SERVICE + "/0/query")
    for name in ["item.json", "service.json", "layer.json", "count.json", "areas.geojson", "areas-esri.json"]:
        raw, receipt = (args.boundaries_cache / name).read_bytes(), receipts[name]
        prefix = expected["areas" if name.startswith("areas") else name.split(".")[0]]
        if (receipt["url"].split("?")[0] != prefix or len(raw) != receipt["bytes"]
                or hashlib.sha256(raw).hexdigest() != receipt["sha256"]):
            raise ValueError("VT general-election boundary receipt mismatch: " + name)
        originals[name] = raw
    item, service, layer, count, geojson, native = [
        json.loads(originals[name]) for name in
        ["item.json", "service.json", "layer.json", "count.json", "areas.geojson", "areas-esri.json"]]
    if (item["id"] != ITEM or item["url"] != SERVICE or item["owner"] != "Publisher_VCGI"
            or "November 2026 general election" not in service["serviceDescription"]
            or geojson.get("exceededTransferLimit") or geojson.get("properties", {}).get("exceededTransferLimit")):
        raise ValueError("Incorrect VT general-election geography vintage or incomplete export")
    esri_attributes = {f["attributes"]["OBJECTID"]: f["attributes"] for f in native["features"]}
    geo_attributes = {f["properties"]["OBJECTID"]: f["properties"] for f in geojson["features"]}
    if (esri_attributes != geo_attributes or len(esri_attributes) != len(native["features"])
            or len(geo_attributes) != len(geojson["features"]) or len(esri_attributes) != count["count"]):
        raise ValueError("VT independent count or native/GeoJSON identities disagree")
    mapped, audit = mapped_splits(rows, native)
    if not mapped:
        raise ValueError("No verified VT reporting geometry")
    args.output.mkdir(parents=True)

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    shutil.copytree(args.review_directory, args.output / "count-review")
    for name in ["results.csv.gz", "municipal-participation.json.gz"]:
        shutil.copyfile(args.review_directory / name, args.output / name)
    (args.output / "originals").mkdir()
    for name, raw in originals.items():
        (args.output / "originals" / (name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
    save("2026/VT.geojson.gz", dict(type="FeatureCollection", features=mapped))
    audit.update(candidate_totals={field: sum(row[field] for row in rows) for field in
        ["democratic_votes", "republican_votes", "other_votes", "contest_votes"]},
        municipal_rows=len(statistics), municipal_rates_withheld=sum(
            row["registered_turnout_pct"] is None for row in statistics),
        boundary_last_edit=layer["editingInfo"]["lastEditDate"])
    save("audit.json", audit)
    save("sources.json", receipts)
    withheld_towns = sum(not town["exact"] for town in audit["towns"].values())
    notes = (f"All {len(rows)} House town/House-district/Senate-district reporting splits reconcile to statewide "
        f"candidate totals. {len(mapped)} reporting splits map to official November 2026 VCGI voting areas. "
        f"{withheld_towns} entire towns are withheld for mismatched identity/split sets or overlapping reference "
        "geometry. No town aliases are inferred, no overlapping boundaries are clipped or assigned, and no "
        "votes are allocated to wards or unincorporated areas. Whole-town split sets must match. These are "
        "town-legislative reporting splits, not independently verified polling precincts. Case, whitespace, "
        "hyphens and underscores are normalized only in district labels. Source ward parts are dissolved; "
        "votes appear once per reporting split. Candidate votes are not turnout. Separate registrations, "
        "ballots and 241 provisional registered-voter fractions remain municipality-only; six municipal "
        "rates stay withheld. No municipal counts or rates are allocated to reporting splits. All original "
        "feeds, native Esri and GeoJSON geometry, unmatched rows and town-by-town audits are downloadable.")
    coverage = dict(file="2026/VT.geojson.gz", source_url=review.HOUSE_URL,
        boundary_source=SERVICE + "/0", partial=True, features=len(mapped),
        colored=sum(f["properties"]["margin_pp"] is not None for f in mapped),
        office="U.S. House", boundary_date="2026 general-election reference", notes=notes,
        next_action="Document Essex/Essex Junction municipal identities and resolve VCGI boundary overlaps; "
            "retain unmapped unincorporated areas. Resolve municipal ballot/scope discrepancies and registration "
            "definitions without assigning municipal denominators to legislative splits.")
    save("index.json", dict(coverage={"2026": {"VT": coverage}}, result_rows=len(rows),
        municipal_participation_rows=len(statistics), complete_download=args.archive.name,
        metric="Candidate margins are not participation. Separate municipal rates are not precinct rates.",
        attribution="Vermont Center for Geographic Information; Vermont Secretary of State Elections Division",
        source_documentation=f"https://www.arcgis.com/home/item.html?id={ITEM}"))
    save("checksums.json", {str(path.relative_to(args.output)): dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(args.output.rglob("*")) if path.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(args.output)))
    print(json.dumps(dict(mapped=len(mapped), colored=coverage["colored"], withheld_towns=withheld_towns,
                         overlap_pairs=len(audit["overlap_pairs"]), archive_bytes=args.archive.stat().st_size), indent=2))


if __name__ == "__main__":
    main()

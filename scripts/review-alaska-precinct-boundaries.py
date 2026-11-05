"""Preserve and audit Alaska's current official locator without asserting 2026 vintage."""

import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import zipfile

from shapely.geometry import shape
from shapely.strtree import STRtree

spec = importlib.util.spec_from_file_location(
    "nd_geometry", Path(__file__).with_name("build-north-dakota-precinct-results.py"))
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)
APP = "579890d66c7e40ae9f7cc227d76669b1"
WEBMAP = "6fac55e6f6914c0da0f90e7e444b3626"
ITEM = "02dec5e7ae604bff951a95bc8a08f9e8"
SERVICE = ("https://services3.arcgis.com/AhVzMlCdMxpkPzPE/arcgis/rest/services/"
           "AK_Election_Geography/FeatureServer")
LOCATOR = "https://akelections.maps.arcgis.com/apps/webappviewer/index.html?id=" + APP
TOLERANCE = 1e-10


def audit_references(native, geographic, geojson, results):
    if (results["name"] != "Alaska 2026 General Election"
            or native.get("spatialReference", {}).get("wkid") not in {102100, 3857}
            or geographic.get("spatialReference", {}).get("wkid") != 4326
            or native.get("geometryType") != "esriGeometryPolygon"
            or geographic.get("geometryType") != "esriGeometryPolygon"
            or geojson.get("type") != "FeatureCollection"):
        raise ValueError("Wrong Alaska election, reference geometry type or projection")
    expected = {p["number"]: p for p in results["precincts"]}
    if not expected or len(expected) != len(results["precincts"]):
        raise ValueError("Missing or duplicate Alaska election precinct")
    exports = []
    for data, field in [(native, "attributes"), (geographic, "attributes"),
                        (geojson, "properties")]:
        values = {f[field]["OBJECTID"]: f for f in data["features"]}
        if (data.get("exceededTransferLimit") or len(values) != len(data["features"])
                or len(values) != len(expected)):
            raise ValueError("Truncated or duplicate Alaska reference export")
        exports.append(values)
    if not ({k: v["attributes"] for k, v in exports[0].items()} == {
            k: v["attributes"] for k, v in exports[1].items()} == {
            k: v["properties"] for k, v in exports[2].items()}):
        raise ValueError("Alaska reference export attributes differ")
    identities, name_differences, polygons, repairs, invalid = {}, [], {}, [], []
    projection_error, vertices = 0, 0
    cross_antimeridian, geojson_differences = [], []
    for oid, feature in exports[1].items():
        attributes = feature["attributes"]
        match = re.fullmatch(r"(\d{2}-\d{3}) (.+)", attributes["Precinct_Number"])
        if not match:
            raise ValueError("Unknown Alaska native precinct-number label")
        number, name = match.groups()
        if (number in identities or number not in expected
                or attributes["HouseDistrict"] != number[:2]):
            raise ValueError("Duplicate or unknown Alaska precinct/district identity")
        identities[number] = oid
        if name != expected[number]["name"]:
            name_differences.append(dict(precinct=number, reference_name=name,
                election_name=expected[number]["name"]))
        source_rings, rings = exports[0][oid]["geometry"]["rings"], feature["geometry"]["rings"]
        if not rings or len(source_rings) != len(rings):
            raise ValueError("Alaska projected/geographic ring structure differs")
        for projected_ring, ring in zip(source_rings, rings):
            if len(projected_ring) != len(ring) or not ring:
                raise ValueError("Alaska projected/geographic vertex structure differs")
            if any(abs(a[0] - b[0]) > 180 for a, b in zip(ring, ring[1:])):
                cross_antimeridian.append(dict(precinct=number, object_id=oid))
            for projected, lonlat in zip(projected_ring, ring):
                if (len(projected) != 2 or len(lonlat) != 2
                        or not all(math.isfinite(v) for v in projected + lonlat)
                        or any(abs(v) > math.pi * 6378137 + 1e-6 for v in projected)
                        or abs(lonlat[0]) > 180 or abs(lonlat[1]) > 90):
                    raise ValueError("Nonfinite or out-of-range Alaska reference coordinate")
                longitude = math.degrees(projected[0] / 6378137)
                latitude = math.degrees(2 * math.atan(math.exp(projected[1] / 6378137)) - math.pi / 2)
                projection_error = max(projection_error, abs(longitude - lonlat[0]),
                                       abs(latitude - lonlat[1]))
                vertices += 1
        try:
            polygon, repair = geometry.esri_polygon(rings)
            polygons[number] = polygon
            if repair:
                repairs.append(dict(precinct=number, object_id=oid, **repair))
            other = shape(exports[2][oid]["geometry"])
            if not other.is_valid:
                geojson_differences.append(dict(precinct=number, geojson_invalid=True))
            elif polygon.symmetric_difference(other).area > TOLERANCE:
                geojson_differences.append(dict(precinct=number,
                    native_geojson_symmetric_difference_degrees_squared=polygon.symmetric_difference(other).area))
        except ValueError as error:
            invalid.append(dict(precinct=number, object_id=oid, reason=str(error)))
    if set(identities) != set(expected) or projection_error >= 1e-9:
        raise ValueError("Alaska complete election IDs or independent inverse projection disagree")
    keys, values = list(polygons), list(polygons.values())
    tree, overlaps = STRtree(values), []
    for i, polygon in enumerate(values):
        for j in tree.query(polygon, predicate="intersects"):
            if j <= i:
                continue
            intersection = polygon.intersection(values[j])
            if intersection.area > TOLERANCE:
                overlaps.append(dict(left=keys[i], right=keys[j],
                    area_degrees_squared=intersection.area,
                    fraction_of_smaller_unit=intersection.area / min(polygon.area, values[j].area)))
    return dict(state_code="AK", year=2026, reference_features=len(expected),
        boundary_vintage="current official locator; exact 2026 vintage not independently established",
        join="withheld", publication="full_reference_download_only", complete=False,
        exact_2026_native_id_set=True, exact_export_attributes=True,
        independently_checked_projected_vertices=vertices,
        inverse_web_mercator_max_error_degrees=projection_error,
        name_differences=name_differences, valid_polygon_units=len(polygons),
        area_preserving_repairs=repairs, invalid_reference_units=invalid,
        cross_antimeridian_paths=cross_antimeridian,
        native_vs_service_geojson_differences=geojson_differences,
        overlap_scope_complete=len(polygons) == len(expected), overlap_pairs=overlaps,
        overlap_tolerance_degrees_squared=TOLERANCE, coordinate_grid_degrees=geometry.GRID,
        reference_creation_dates=dict(Counter(
            str(f["attributes"].get("CreationDate")) for f in geographic["features"])),
        sample_ballot_urls=sorted({f["attributes"]["Sample_Ballot_URL"]
            for f in geographic["features"] if f["attributes"].get("Sample_Ballot_URL")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-directory", required=True, type=Path)
    parser.add_argument("--boundaries-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Alaska reference review")
    for name, receipt in json.loads((args.review_directory / "checksums.json").read_text()).items():
        raw = (args.review_directory / name).read_bytes()
        if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("Alaska original count review changed: " + name)
    names = {
        "official-app-item.json": "https://www.arcgis.com/sharing/rest/content/items/" + APP,
        "official-app-data.json": "https://www.arcgis.com/sharing/rest/content/items/" + APP + "/data",
        "official-webmap-item.json": "https://www.arcgis.com/sharing/rest/content/items/" + WEBMAP,
        "official-webmap-data.json": "https://www.arcgis.com/sharing/rest/content/items/" + WEBMAP + "/data",
        "official-geography-item.json": "https://www.arcgis.com/sharing/rest/content/items/" + ITEM,
        "official-service.json": SERVICE,
        "official-precinct-layer.json": SERVICE + "/7",
        "independent-precinct-count.json": SERVICE + "/7/query",
        "complete-native-projected-precincts.json": SERVICE + "/7/query",
        "complete-native-wgs84-precincts.json": SERVICE + "/7/query",
        "complete-wgs84-precincts.geojson": SERVICE + "/7/query",
    }
    receipts = json.loads((args.boundaries_cache / "sources.json").read_text())
    originals = {}
    for name, url in names.items():
        raw, receipt = (args.boundaries_cache / name).read_bytes(), receipts[name]
        if (receipt["url"].split("?")[0] != url or len(raw) != receipt["bytes"]
                or hashlib.sha256(raw).hexdigest() != receipt["sha256"]):
            raise ValueError("Alaska locator reference receipt mismatch: " + name)
        originals[name] = raw
    data = {name: json.loads(raw) for name, raw in originals.items()}
    app, webmap, item = [data[n] for n in [
        "official-app-item.json", "official-webmap-item.json", "official-geography-item.json"]]
    if (any(d["owner"] != "DOEALASKA" or d["access"] != "public" for d in [app, webmap, item])
            or app["id"] != APP or app["url"] != LOCATOR or webmap["id"] != WEBMAP
            or item["id"] != ITEM or item["url"].rstrip("/") != SERVICE
            or data["official-app-data.json"]["map"]["itemId"] != WEBMAP
            or not any(layer.get("url") == SERVICE + "/7"
                       for layer in data["official-webmap-data.json"]["operationalLayers"])
            or data["official-precinct-layer.json"]["serviceItemId"] != ITEM
            or data["independent-precinct-count.json"]["count"] != 402):
        raise ValueError("Incorrect official Alaska locator ownership, provenance chain or complete count")
    results = json.loads(gzip.decompress(
        (args.review_directory / "originals/precincts-original.json.gz").read_bytes()))
    audit = audit_references(data["complete-native-projected-precincts.json"],
        data["complete-native-wgs84-precincts.json"], data["complete-wgs84-precincts.geojson"], results)
    audit.update(official_locator_url=LOCATOR, official_layer_url=SERVICE + "/7",
        source_review="count-review/audit.json",
        interpretation="Matching IDs, current public use and edit dates do not prove exact-election "
            "boundary vintage. No geometry or candidate votes are published as a precinct join. "
            "Overlaps and label differences remain unresolved. All original exports are retained.")
    args.output.mkdir(parents=True)
    shutil.copytree(args.review_directory, args.output / "count-review")
    (args.output / "originals").mkdir()
    for name, raw in originals.items():
        (args.output / "originals" / (name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
    for name, value in [("audit.json", audit), ("sources.json", {n: receipts[n] for n in names})]:
        (args.output / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")
    checksums = {}
    for path in sorted(args.output.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            checksums[str(path.relative_to(args.output))] = dict(
                bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(str(path.relative_to(args.output)), date_time=(2026, 11, 5, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    raw = args.archive.read_bytes()
    print(json.dumps(dict(reference_features=audit["reference_features"],
        overlap_pairs=len(audit["overlap_pairs"]), archive_bytes=len(raw),
        archive_sha256=hashlib.sha256(raw).hexdigest()), indent=2))


if __name__ == "__main__":
    main()

"""Join reconciled North Dakota 2026 returns to explicitly identified 2026 precincts."""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path

import shapefile
from shapely import make_valid, set_precision
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.validation import explain_validity

spec = importlib.util.spec_from_file_location(
    "nd_review", Path(__file__).with_name("review-north-dakota-precinct-results.py"))
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
LAYER = ("https://services1.arcgis.com/GOcSXpzwBHyk2nog/ArcGIS/rest/services/"
         "NDGISHUB_Voter_Precincts/FeatureServer/0")
BUNDLE = "https://www.sos.nd.gov/sites/default/files/documents/elections/map-shape-files/voting-shape-files-2026.zip"
GRID = 1e-9


def esri_polygon(rings):
    points, parts = [], []
    for ring in rings:
        if len(ring) < 4 or ring[0] != ring[-1] or any(
                len(p) != 2 or not all(math.isfinite(v) for v in p)
                or not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90) for p in ring):
            raise ValueError("Invalid or unclosed geographic Esri ring")
        parts.append(len(points))
        points.extend(ring)
    if not points:
        raise ValueError("Empty Esri polygon")
    # Esri shell/hole winding is authoritative; its GeoJSON export misgroups some holes.
    polygon = shape(shapefile.Shape(shapeType=5, points=points, parts=parts).__geo_interface__)
    repair = None
    if not polygon.is_valid:
        valid = make_valid(polygon)
        if not math.isclose(valid.area, polygon.area, rel_tol=1e-12, abs_tol=1e-14):
            raise ValueError("Topology repair changes polygon area")
        repair = dict(reason=explain_validity(polygon),
                      area_difference=abs(valid.area - polygon.area))
        polygon = valid
    polygon = set_precision(polygon, GRID)
    if polygon.is_empty or not polygon.is_valid or polygon.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Invalid or nonpolygonal repaired geometry")
    return polygon, repair


def mapped_precincts(rows, participation, boundary):
    if (boundary.get("exceededTransferLimit") or boundary.get("geometryType") != "esriGeometryPolygon"
            or boundary.get("spatialReference", {}).get("wkid") != 4326):
        raise ValueError("Incomplete or incorrectly projected ND boundaries")
    stats = {r["key"]: r for r in participation}
    if len(stats) != len(participation) or set(stats) != {r["key"] for r in rows}:
        raise ValueError("ND result/participation identities differ")
    counties, names = defaultdict(list), {}
    for row in rows:
        county, name = row["county"], stats[row["key"]]["county_name"]
        if name.casefold() in names and names[name.casefold()] != county:
            raise ValueError("Ambiguous ND county name")
        names[name.casefold()] = county
        counties[county].append(row)
    groups, seen, repairs = defaultdict(list), set(), []
    for feature in boundary["features"]:
        p = feature["attributes"]
        if p["OBJECTID"] in seen or p["CountyName"].casefold() not in names:
            raise ValueError("Duplicate ND boundary record or unknown county")
        seen.add(p["OBJECTID"])
        groups[names[p["CountyName"].casefold()]].append(feature)
    mapped, audits = [], {}
    for county, county_rows in sorted(counties.items()):
        features = groups[county]
        expected = {stats[r["key"]]["precinct_name"] for r in county_rows}
        actual = {f["attributes"]["Precinct"] for f in features}
        if len(expected) != len(county_rows):
            raise ValueError("Ambiguous ND reporting-unit label")
        conflicts = [f["attributes"]["OBJECTID"] for f in features
                     if str(f["attributes"]["CountyID"]) != county]
        audit = dict(county=stats[county_rows[0]["key"]]["county_name"],
                     reporting_units=len(county_rows), source_parts=len(features),
                     reporting_only=sorted(expected - actual), boundary_only=sorted(actual - expected),
                     parent_id_conflicts=conflicts, invalid_geometry=[], exact=expected == actual and not conflicts)
        audits[county] = audit
        if not audit["exact"]:
            continue
        by_precinct, object_ids = defaultdict(list), defaultdict(list)
        for feature in features:
            p = feature["attributes"]
            try:
                polygon, repair = esri_polygon(feature["geometry"]["rings"])
            except ValueError as error:
                audit["invalid_geometry"].append(dict(object_id=p["OBJECTID"], reason=str(error)))
                audit["exact"] = False
                continue
            if repair:
                repairs.append(dict(county=county, object_id=p["OBJECTID"], **repair))
            by_precinct[p["Precinct"]].append(polygon)
            object_ids[p["Precinct"]].append(p["OBJECTID"])
        if not audit["exact"]:
            continue
        county_features = []
        for row in county_rows:
            stats_row = stats[row["key"]]
            precinct = stats_row["precinct_name"]
            polygon = unary_union(by_precinct[precinct])
            if polygon.is_empty or not polygon.is_valid or polygon.geom_type not in {"Polygon", "MultiPolygon"}:
                raise ValueError("Invalid dissolved ND reporting-unit geometry")
            properties = dict(row, county=stats_row["county_name"], county_code=county,
                              precinct=precinct, precinct_code=row["precinct"], match_status="matched",
                              boundary_date="2026 election reference",
                              boundary_provenance="Union of official 2026 precinct splits using the explicit "
                                  "CountyID and Precinct fields, not part-ID prefixes. Votes are observed only "
                                  "for the complete reporting unit, never allocated to individual splits.",
                              source_object_ids=sorted(object_ids[precinct]), participation=stats_row)
            county_features.append(dict(type="Feature", properties=properties, geometry=mapping(polygon)))
        mapped.extend(county_features)
    polygons = [set_precision(shape(f["geometry"]), GRID) for f in mapped]
    tree = STRtree(polygons)
    overlaps, masks = [], defaultdict(list)
    for i, polygon in enumerate(polygons):
        for j in tree.query(polygon, predicate="intersects"):
            intersection = polygon.intersection(polygons[j])
            if j > i and intersection.area > 1e-10:
                left, right = mapped[i]["properties"], mapped[j]["properties"]
                overlaps.append(dict(left=left["key"], right=right["key"],
                                     area_degrees_squared=intersection.area))
                masks[i].append(intersection)
                masks[j].append(intersection)
    withheld, masked_units, mask_features = set(), [], []
    for i, intersections in masks.items():
        ambiguous = unary_union(intersections)
        polygon = polygons[i].difference(ambiguous)
        properties = mapped[i]["properties"]
        record = dict(key=properties["key"], area_degrees_squared=ambiguous.area,
                      fraction_of_reference_geometry=ambiguous.area / polygons[i].area)
        masked_units.append(record)
        mask_features.append(dict(type="Feature", properties=record, geometry=mapping(ambiguous)))
        if polygon.is_empty:
            withheld.add(properties["county_code"])
            continue
        if not polygon.is_valid or polygon.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Invalid ND overlap-masked reporting-unit geometry")
        mapped[i]["geometry"] = mapping(polygon)
        properties["boundary_provenance"] += (
            " Ambiguous strips shared with another reference reporting unit are excluded, not assigned "
            "to either precinct. Counts still describe the entire reporting unit. Full original boundaries "
            "and the excluded-area audit remain in the complete download.")
        properties["geometry_scope"] = "Reference geometry with overlapping strips withheld"
    for county in withheld:
        audits[county].update(exact=False, geometry_withheld="Reporting unit completely overlaps another")
    mapped = [f for f in mapped if f["properties"]["county_code"] not in withheld]
    polygons = [set_precision(shape(f["geometry"]), GRID) for f in mapped]
    tree = STRtree(polygons)
    for i, polygon in enumerate(polygons):
        for j in tree.query(polygon, predicate="intersects"):
            area = polygon.intersection(polygons[j]).area
            if j > i and area > 1e-10:
                raise ValueError("Overlapping ND reporting-unit geometry remains after masking: "
                                 f'{mapped[i]["properties"]["key"]}, {mapped[j]["properties"]["key"]}: {area}')
    return mapped, dict(counties=audits, topology_repairs=repairs,
                        source_cross_precinct_overlaps=overlaps, mapped_cross_precinct_overlaps=0,
                        masked_reporting_units=masked_units,
                        ambiguity_mask=dict(type="FeatureCollection", features=mask_features),
                        processing_grid_degrees=GRID, overlap_area_tolerance_degrees_squared=1e-10,
                        join_fields=["CountyID", "Precinct"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cache", required=True, type=Path)
    parser.add_argument("--boundaries-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable ND snapshot")
    originals, receipts = {}, {}

    def capture(name, path, receipt, compressed=False):
        raw = gzip.decompress(path.read_bytes()) if compressed else path.read_bytes()
        if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("ND original source checksum mismatch: " + name)
        originals[name], receipts[name] = raw, receipt
        return raw

    previous = json.loads((args.source_cache / "sources.json").read_text())
    for name in review.SOURCES:
        if previous[name]["url"] != review.SOURCES[name]:
            raise ValueError("ND original source URL changed")
        capture(name, args.source_cache / name, previous[name])
    cache = args.boundaries_cache
    for name, url in [
        ("layer.json", LAYER + "?f=json"),
        ("count.json", LAYER + "/query?where=1%3D1&returnCountOnly=true&f=json"),
        ("official-2026-shape-files.zip", BUNDLE),
    ]:
        path = cache / name
        capture(name, path, dict(url=url, bytes=path.stat().st_size,
                                sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    for name, receipt_file in [
        ("all-2026-splits.geojson", "all-2026-splits-source.json"),
        ("all-2026-splits.esri.json", "all-2026-esri-source.json"),
    ]:
        receipt = json.loads((cache / receipt_file).read_text())
        if not receipt["url"].startswith(LAYER + "/query?"):
            raise ValueError("Incorrect ND boundary query source")
        capture(name, cache / (name + ".gz"), receipt, compressed=True)
    layer = json.loads(originals["layer.json"])
    boundary = json.loads(originals["all-2026-splits.esri.json"])
    geojson = json.loads(originals["all-2026-splits.geojson"])
    if ("2026 election in North Dakota" not in layer["description"]
            or len(boundary["features"]) != json.loads(originals["count.json"])["count"]
            or geojson.get("properties", {}).get("exceededTransferLimit")):
        raise ValueError("Incorrect election vintage or incomplete ND boundary export")
    esri_attributes = {f["attributes"]["OBJECTID"]: f["attributes"] for f in boundary["features"]}
    geojson_attributes = {f["properties"]["OBJECTID"]: f["properties"] for f in geojson["features"]}
    if (esri_attributes != geojson_attributes or len(geojson_attributes) != len(geojson["features"])
            or len(esri_attributes) != len(boundary["features"])):
        raise ValueError("ND original Esri/GeoJSON feature identities differ")
    source, identity = (json.loads(originals[name]) for name in ["full-results.json", "election.json"])
    rows, participation = review.nd_results(source, identity)
    for row in participation:
        row["measure"] = "reported_ballots"
    mapped, audit = mapped_precincts(rows, participation, boundary)
    if not mapped:
        raise ValueError("No verified ND reporting-unit geometry")
    args.output.mkdir(parents=True)

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    for name, raw in originals.items():
        path = args.output / "originals" / (name if name.endswith(".zip") else name + ".gz")
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw if name.endswith(".zip") else gzip.compress(raw, mtime=0))
    save("2026/ND.geojson.gz", dict(type="FeatureCollection", features=mapped))
    save("2026/ND-ambiguous-reference-areas.geojson.gz", audit.pop("ambiguity_mask"))
    save("participation.json.gz", participation)
    audit.update(reporting_units=len(rows), mapped_units=len(mapped), source_parts=len(boundary["features"]),
                 candidate_totals={field: sum(row[field] for row in rows) for field in
                                   ["democratic_votes", "republican_votes", "other_votes", "contest_votes"]},
                 ballots=sum(r["ballots"] for r in participation), rates_withheld=len(participation),
                 election_id=348, source_version=identity["versionID"],
                 boundary_last_edit=layer["editingInfo"]["lastEditDate"])
    save("audit.json", audit)
    save("sources.json", receipts)
    notes = ("Official 2026 House reporting-unit returns reconcile to all 53 counties and statewide totals. "
             "The official layer explicitly describes 2026 election precinct splits; its CountyID and Precinct "
             "fields must match each county's complete reporting set. All parts are dissolved into one geometry "
             "per reporting unit, with votes counted once. Morton is withheld for conflicting county IDs; "
             "Towner is withheld for a malformed extra precinct code. Native Esri ring roles preserve holes "
             "that the service's GeoJSON export misgroups. Area-preserving topology repairs are individually "
             "audited. Overlay processing uses a 1e-9-degree coordinate grid. Ambiguous overlapping boundary "
             "strips are excluded from both precincts, leaving state "
             "fallback colors there. Votes still describe entire reporting units, not clipped-area allocations. "
             "The full original boundaries and ambiguity mask are downloadable. No distinct mapped "
             "reporting-unit polygons overlap beyond the audited numeric tolerance. Unofficial candidate votes are "
             "not turnout. Separate ballot counts have no precinct denominator; all rates are withheld.")
    coverage = dict(file="2026/ND.geojson.gz", source_url=review.SOURCES["full-results.json"],
                    boundary_source=LAYER, partial=True, features=len(mapped),
                    colored=sum(f["properties"]["margin_pp"] is not None for f in mapped),
                    office="U.S. House", boundary_date="2026 election reference", notes=notes,
                    next_action="Resolve Morton parent IDs and Towner malformed precinct code with official "
                        "crosswalk evidence; obtain precinct electorate denominators and certified returns.")
    save("index.json", dict(coverage={"2026": {"ND": coverage}}, result_rows=len(rows),
         participation_rows=len(participation), complete_download=args.archive.name,
         metric="Candidate margins are not participation. Ballot counts lack precinct denominators.",
         attribution=layer["copyrightText"], source_documentation="https://www.sos.nd.gov/elections/election-resources"))
    text = io.StringIO()
    writer = csv.DictWriter(text, review.results.CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(text.getvalue().encode(), mtime=0))
    save("checksums.json", {str(p.relative_to(args.output)): dict(bytes=p.stat().st_size,
         sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(args.output.rglob("*")) if p.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(args.output)))
    print(json.dumps(dict(mapped=len(mapped), colored=coverage["colored"],
          withheld_counties=[a["county"] for a in audit["counties"].values() if not a["exact"]],
          topology_repairs=len(audit["topology_repairs"]), archive_bytes=args.archive.stat().st_size), indent=2))


if __name__ == "__main__":
    main()

import argparse
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.validation import explain_validity


FILES = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=FILES / "massachusetts-independent-city-sources-20261110-01")
parser.add_argument("--output", type=Path)
args = parser.parse_args()
ROOT = args.root
ORIGINALS = ROOT / "selected-native-geometry-02"
OUTPUT = args.output or ROOT / "native-reference-extension-review-01"
assert not OUTPUT.exists()
base = json.loads((ROOT / "native-geometry-review-01/complete-native-reference-queries.json").read_bytes())
counts = json.loads((ROOT / "native-count-review-01/complete-native-count-queries.json").read_bytes())
sub_counts = {(row["ward"], row["precinct"]): row for row in counts["somerville_native_counts"]
              if row["native_level"] == "precinct"}
split_parents = {("1", "4"), ("2", "1"), ("4", "2"), ("6", "3")}
projection = Transformer.from_crs(26986, 4326, always_xy=True)
assert any(step.to_json_dict().get("id") == {"authority": "EPSG", "code": 1188}
           for step in projection.operations)
inverse_projection = Transformer.from_crs(26986, 4269, always_xy=True)
operation = json.loads((ROOT / "geometry-discovery-01/massgis-independent-declared-datum-operations.json").read_bytes())
declared = json.loads((ROOT / "geometry-discovery-01/massgis-declared-26986-4326-transformations.private.json").read_bytes())
assert declared["transformations"][0]["geoTransforms"] == [
    dict(wkid=108190, latestWkid=108190, transformForward=False,
         name="WGS_1984_(ITRF00)_To_NAD_1983")]
datum = Transformer.from_pipeline(operation["operations"]["108190"]["pipeline"])
city_counts = {
    "BOSTON": counts["boston_senate_times_cast_sum"],
    "SOMERVILLE": next(row["ballots_cast_literal"] for row in counts["somerville_native_counts"]
                       if row["native_level"] == "city"),
}
decisions, pairs, receipts = [], [], []


def parent_geographic_point(x, y):
    lon, lat = inverse_projection.transform(x, y)
    outlat, outlon = datum.transform(lat, lon, direction="INVERSE")
    return outlon, outlat


for name in ["somerville-parent-precincts", "massachusetts-municipalities"]:
    geo_path = ORIGINALS / (name+"-full-geographic-original.geojson")
    native_path = ORIGINALS / (name+"-full-native-projected-original.json")
    geographic = json.loads(geo_path.read_bytes())
    native = json.loads(native_path.read_bytes())
    native_by_oid = {row["attributes"]["OBJECTID"]: row for row in native["features"]}
    assert len(native_by_oid) == len(geographic["features"])
    polygons = []
    for feature in geographic["features"]:
        properties = feature["properties"]
        row = native_by_oid[properties["OBJECTID"]]
        assert properties == row["attributes"]
        rings = row["geometry"]["rings"]
        assert all(len(ring) >= 4 and ring[0] == ring[-1] for ring in rings)
        assert all(len(point) == 2 and all(math.isfinite(value) for value in point)
                   for ring in rings for point in ring)
        native_parts = [Polygon(ring) for ring in rings]
        assert not any(part.exterior.is_ccw for part in native_parts), "Unreviewed native ring role"
        native_polygon = native_parts[0] if len(native_parts) == 1 else MultiPolygon(native_parts)
        coordinates = feature["geometry"]["coordinates"]
        geo_parts = [coordinates] if feature["geometry"]["type"] == "Polygon" else coordinates
        assert len(geo_parts) == len(rings) and all(len(part) == 1 for part in geo_parts)
        geo_points = [tuple(point) for part in geo_parts for point in part[0]]
        project = parent_geographic_point if name == "somerville-parent-precincts" else projection.transform
        transformed = sorted(project(x, y) for ring in rings for x, y in ring)
        assert len(transformed) == len(geo_points)
        error = max(abs(a-b) for expected, actual in zip(transformed, sorted(geo_points))
                    for a, b in zip(expected, actual))
        default_error = None
        if name == "somerville-parent-precincts":
            default_points = sorted(projection.transform(x, y) for ring in rings for x, y in ring)
            default_error = max(abs(a-b) for expected, actual in zip(default_points, sorted(geo_points))
                                for a, b in zip(expected, actual))
            assert default_error > 1e-9
        geo_polygon = shape(feature["geometry"])
        geographic_qualified = (error <= 1e-9 and native_polygon.is_valid
                                and geo_polygon.is_valid and native_polygon.area > 0)
        if name == "somerville-parent-precincts":
            ward, precinct = properties["WARD"], properties["PRECINCT"]
            assert properties["TOWN"] == "SOMERVILLE"
            assert properties["WP_DISTRICT"] == f"{ward}-{precinct}"
            count = sub_counts[ward, precinct]["ballots_cast_literal"]
            matched = (ward, precinct) not in split_parents
            disposition = ("qualified_unchanged_native_precinct_reference" if matched else
                           "held_parent_geometry_contains_separately_reported_subprecinct_no_clipping")
            native_level = "precinct"
        else:
            ward, precinct = None, None
            count = city_counts.get(properties["TOWN"])
            matched = count is not None
            disposition = ("qualified_native_city_reference" if matched else
                           "reference_only_no_source_count_not_zero")
            native_level = "municipality"
        decisions.append(dict(
            source=name, native_object_id=properties["OBJECTID"], native_properties=properties,
            native_level=native_level, ward=ward, precinct=precinct, native_count=count,
            native_vertices=len(transformed), maximum_projection_error_degrees=error,
            rejected_default_projection_error_degrees=default_error,
            native_datum_operation=dict(authority="ESRI", code=108190, direction="inverse")
                if name == "somerville-parent-precincts" else
                dict(authority="EPSG", code=1188, projection_pipeline=projection.to_proj4()),
            native_valid=native_polygon.is_valid, geographic_valid=geo_polygon.is_valid,
            native_validity=explain_validity(native_polygon), geographic_validity=explain_validity(geo_polygon),
            native_projected_area=native_polygon.area,
            native_projected_area_units="metres_squared_NOT_geodesic",
            geometry_qualified=geographic_qualified,
            source_count_join_qualified=geographic_qualified and matched,
            disposition=disposition if geographic_qualified else "held_invalid_original_reference_no_repair",
            analysis_denominator=None, analysis_rate=None, maps_approved=False,
            legal_2026_precinct_certification=False,
        ))
        polygons.append((properties["OBJECTID"], native_polygon))
    for (left_id, left), (right_id, right) in itertools.combinations(polygons, 2):
        area = left.intersection(right).area if left.is_valid and right.is_valid else None
        pairs.append(dict(
            source=name, left_native_object_id=left_id, right_native_object_id=right_id,
            positive_native_overlap=None if area is None else area > 0,
            native_overlap_area=area, native_projected_area_units="metres_squared_NOT_geodesic",
            disposition="held_invalid_source_no_intersection_inferred" if area is None else
                        "complete_original_pair_decision_no_repair",
        ))
    for path in [geo_path, native_path]:
        receipt = json.loads(path.with_name(path.name+".receipt.json").read_bytes())
        assert receipt["status"] == 200 and receipt["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        receipts.append(dict(name=path.name, bytes=path.stat().st_size, sha256=receipt["sha256"]))

assert len(decisions) == 379 and len(pairs) == 61425 + 378
municipal = [row for row in decisions if row["source"] == "massachusetts-municipalities"]
parent_rows = [row for row in decisions if row["source"] == "somerville-parent-precincts"]
assert len(municipal) == len({row["native_properties"]["TOWN_ID"] for row in municipal}) == 351
assert len(parent_rows) == 28 and sum(row["source_count_join_qualified"] for row in parent_rows) == 24
assert all(row["source_count_join_qualified"] for row in municipal
           if row["native_properties"]["TOWN"] in ["BOSTON", "SOMERVILLE"])
summary = dict(
    status="PASS_full_native_reference_extension_review_NOT_website_acceptance",
    native_parent_precincts=28, qualified_parent_count_joins=24, split_parent_holds=4,
    native_municipalities=351, qualified_municipal_geometry=sum(row["geometry_qualified"] for row in municipal),
    municipality_geometry_holds=[row["native_properties"] for row in municipal if not row["geometry_qualified"]],
    source_city_observations=2, source_precinct_count_rows=307,
    total_qualified_reporting_references=base["summary"]["qualified_unchanged_references"]+24,
    checked_native_vertices=sum(row["native_vertices"] for row in decisions),
    pair_decisions=len(pairs), held_invalid_pair_decisions=sum(row["native_overlap_area"] is None for row in pairs),
    positive_native_overlap_pairs=sum(row["positive_native_overlap"] is True for row in pairs),
    maximum_projection_error_degrees=max(row["maximum_projection_error_degrees"] for row in decisions),
    no_clipping_allocation_source_repair_or_rates=True, maps_approved=False,
)
result = dict(summary=summary, all_reference_decisions=decisions,
              all_pair_decisions=pairs, retained_originals=receipts)
OUTPUT.mkdir()
(OUTPUT/"complete-reference-extension-queries.json.gz").write_bytes(
    gzip.compress((json.dumps(result, sort_keys=True, separators=(",", ":"))+"\n").encode(), mtime=0))
(OUTPUT/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
print(json.dumps(summary))

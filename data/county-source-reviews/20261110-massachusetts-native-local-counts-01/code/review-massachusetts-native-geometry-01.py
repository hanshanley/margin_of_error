import argparse
import collections
import hashlib
import itertools
import json
import math
from pathlib import Path
import re

from pyproj import Transformer
from shapely.geometry import Polygon, shape
from shapely.validation import explain_validity


FILES = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=FILES / "massachusetts-independent-city-sources-20261110-01")
parser.add_argument("--output", type=Path)
args = parser.parse_args()
ROOT = args.root
ORIGINALS = ROOT / "selected-native-geometry-01"
OUTPUT = args.output or ROOT / "native-geometry-review-01"
assert not OUTPUT.exists()
counts = json.loads((ROOT / "native-count-review-01/complete-native-count-queries.json").read_bytes())
boston_counts = {
    (row["ward"], row["precinct"]): row
    for row in counts["boston_all_times_cast_frames"]["SENATOR IN CONGRESS (Vote for 1)"]
}
somerville_counts = {
    (row["ward"], row["precinct"]): row
    for row in counts["somerville_native_counts"] if row["native_level"] == "precinct"
}
decisions, pairs, receipts = [], [], []

for city, oid, epsg in [
    ("boston", "FID", 3857),
    ("somerville-subprecincts", "OBJECTID", 26986),
]:
    geographic_path = ORIGINALS / (city + "-full-geographic-original.geojson")
    native_path = ORIGINALS / (city + "-full-native-projected-original.json")
    geographic = json.loads(geographic_path.read_bytes())
    native = json.loads(native_path.read_bytes())
    native_by_oid = {row["attributes"][oid]: row for row in native["features"]}
    assert len(native_by_oid) == len(geographic["features"])
    projection = Transformer.from_crs(epsg, 4326, always_xy=True)
    polygons = []
    for feature in geographic["features"]:
        properties = feature["properties"]
        native_feature = native_by_oid[properties[oid]]
        assert properties == native_feature["attributes"]
        rings = native_feature["geometry"]["rings"]
        assert len(rings) == len(feature["geometry"]["coordinates"]) == 1
        ring = rings[0]
        assert len(ring) >= 4 and ring[0] == ring[-1]
        assert all(len(point) == 2 and all(math.isfinite(value) for value in point) for point in ring)
        geographic_ring = feature["geometry"]["coordinates"][0]
        assert geographic_ring[0] == geographic_ring[-1] and len(geographic_ring) == len(ring)
        projected = sorted(projection.transform(x, y) for x, y in ring)
        observed = sorted(tuple(point) for point in geographic_ring)
        maximum_error = max(abs(a-b) for expected, actual in zip(projected, observed)
                            for a, b in zip(expected, actual))
        original_native_polygon = Polygon(ring)
        original_geographic_polygon = shape(feature["geometry"])
        if city == "boston":
            ward, precinct = str(int(properties["Ward1"])), str(int(properties["Precinct1"]))
            assert properties["WDPCT"] == f"{int(ward):02}{int(precinct):02}"
            count = boston_counts[ward, precinct]["times_cast_literal"]
            native_count_field = "SENATOR IN CONGRESS: Times Cast"
            source_level = "precinct"
        else:
            match = re.fullmatch(r"(\d+)-(\d+A)", properties["SUBPRECINCT"])
            assert match and properties["TOWN"] == "SOMERVILLE"
            ward, precinct = match.groups()
            assert properties["PARENT_PCT"] == f"Somerville Precinct {ward}-{precinct[:-1]}"
            count = somerville_counts[ward, precinct]["ballots_cast_literal"]
            native_count_field = "BALLOTS CAST - TOTAL"
            source_level = "subprecinct"
        qualified = (
            maximum_error <= 1e-9 and original_native_polygon.is_valid
            and original_geographic_polygon.is_valid and original_native_polygon.area > 0
        )
        decisions.append(dict(
            city_source=city, native_object_id=properties[oid], ward=ward, precinct=precinct,
            native_properties=properties, native_reference_level=source_level,
            source_native_epsg=epsg, vertices=len(ring),
            maximum_projection_error_degrees=maximum_error,
            native_valid=original_native_polygon.is_valid,
            geographic_valid=original_geographic_polygon.is_valid,
            native_validity=explain_validity(original_native_polygon),
            geographic_validity=explain_validity(original_geographic_polygon),
            native_projected_area=original_native_polygon.area,
            native_projected_area_units="metres_squared_NOT_geodesic",
            native_count_field=native_count_field, native_count=count,
            analysis_denominator=None, analysis_rate=None,
            qualified_unchanged_reference=qualified,
            maps_approved=False, legal_2026_precinct_certification=False,
        ))
        polygons.append((properties[oid], original_native_polygon))
    for (left_id, left), (right_id, right) in itertools.combinations(polygons, 2):
        area = left.intersection(right).area
        pairs.append(dict(
            city_source=city, left_native_object_id=left_id, right_native_object_id=right_id,
            positive_native_overlap=area > 0, native_overlap_area=area,
            native_projected_area_units="metres_squared_NOT_geodesic",
            source_geometries_repaired=False,
        ))
    for path in [geographic_path, native_path]:
        receipt = json.loads((path.with_name(path.name+".receipt.json")).read_bytes())
        assert receipt["status"] == 200 and receipt["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        receipts.append(dict(name=path.name, bytes=path.stat().st_size, sha256=receipt["sha256"]))

assert {(row["ward"], row["precinct"]) for row in decisions if row["city_source"] == "boston"} == set(boston_counts)
assert sum(row["native_count"] for row in decisions if row["city_source"] == "boston") == 185569
assert len(pairs) == 37675 + 6
result = dict(
    status="PASS_full_native_geometry_and_count_identity_review_NOT_website_acceptance",
    decisions=decisions, all_pair_decisions=pairs, retained_originals=receipts,
    summary=dict(
        boston_native_references=275, somerville_native_subprecinct_references=4,
        checked_native_vertices=sum(row["vertices"] for row in decisions),
        qualified_unchanged_references=sum(row["qualified_unchanged_reference"] for row in decisions),
        projection_holds=[row for row in decisions if row["maximum_projection_error_degrees"] > 1e-9],
        native_overlap_pairs=sum(row["positive_native_overlap"] for row in pairs),
        native_pair_decisions=len(pairs), maps_approved=False,
        somerville_remaining_count_rows=28,
        parent_precincts_not_clipped_to_infer_remainders=True,
        source_counts_not_repaired=True, legal_2026_precinct_certification=False,
    ),
)
OUTPUT.mkdir()
(OUTPUT / "complete-native-reference-queries.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result["summary"]))

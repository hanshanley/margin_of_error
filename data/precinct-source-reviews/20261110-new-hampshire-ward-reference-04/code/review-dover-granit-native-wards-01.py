import argparse
import hashlib
import itertools
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Polygon, shape
from shapely.validation import explain_validity


FILES = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=FILES / "dover-independent-state-regional-boundary-leads-01")
parser.add_argument("--output", type=Path)
args = parser.parse_args()
ROOT = args.root
OUTPUT = args.output or ROOT / "complete-native-ward-reference-review.json"
assert not OUTPUT.exists()


def original(name, receipt_name=None):
    body = (ROOT / name).read_bytes()
    receipt = json.loads((ROOT / (receipt_name or name+".receipt.json")).read_bytes())
    assert receipt["status"] == 200 and receipt["sha256"] == hashlib.sha256(body).hexdigest()
    return json.loads(body)


native = original("granit-dover2022-full-native-projected-original.json")
geographic = original("granit-dover2022-full-geographic-original.geojson")
count = original("granit-dover2022-native-count.json", "granit-dover2022-native-count.receipt.json")
ids = original("granit-dover2022-native-ids.json", "granit-dover2022-native-ids.receipt.json")
declaration = json.loads((ROOT / "granit-declared-3437-4326-transformations.json").read_bytes())
receipt = json.loads((ROOT / "granit-declared-3437-4326-transformations.receipt.json").read_bytes())
assert receipt["http_status"] == 200 and receipt["sha256"] == hashlib.sha256(
    (ROOT / "granit-declared-3437-4326-transformations.json").read_bytes()).hexdigest()
assert declaration["transformations"][0]["geoTransforms"] == [
    dict(wkid=108190, latestWkid=108190, transformForward=False,
         name="WGS_1984_(ITRF00)_To_NAD_1983")]
assert native["spatialReference"] == dict(wkid=102710, latestWkid=3437)
assert count["count"] == len(ids["objectIds"]) == len(set(ids["objectIds"])) == 6
assert len(native["features"]) == len(geographic["features"]) == 6
geo_by_id = {feature["properties"]["fid"]: feature for feature in geographic["features"]}
counts = json.loads((ROOT / "held-native-four-city-count-queries.json").read_bytes())
source_rows = {row["native_ward"]: row for row in counts["ward_rows"] if row["city"] == "Dover"}
city = next(row for row in counts["municipalities"] if row["city"] == "Dover")
assert set(source_rows) == set(range(1, 7)) and city["source_count"] == 15941
inverse = Transformer.from_crs(3437, 4269, always_xy=True)
default = Transformer.from_crs(3437, 4326, always_xy=True)
datum = Transformer.from_pipeline("ESRI:108190")
decisions, polygons = [], {}
for feature in native["features"]:
    properties = feature["attributes"]
    assert set(properties) == {"fid", "name", "county", "fips", "district"}
    assert properties["name"] == "Dover" and properties["county"] == "Strafford"
    assert properties["fips"] == 17010
    ward = next((ward for ward in range(1, 7) if properties["district"] == f"Dover Ward {ward}"), None)
    assert ward is not None and ward not in polygons and properties["fid"] in ids["objectIds"]
    geographic_feature = geo_by_id[properties["fid"]]
    assert geographic_feature["properties"] == properties
    rings = feature["geometry"]["rings"]
    assert len(rings) == len(geographic_feature["geometry"]["coordinates"]) == 1
    xy = rings[0]
    ll = geographic_feature["geometry"]["coordinates"][0]
    assert len(xy) == len(ll) and xy[0] == xy[-1] and ll[0] == ll[-1]
    expected, defaults = [], []
    for x, y in xy[:-1]:
        lon, lat = inverse.transform(x, y)
        outlat, outlon = datum.transform(lat, lon, direction="INVERSE")
        expected.append((outlon, outlat))
        defaults.append(default.transform(x, y))
    actual = ll[:-1]
    candidates = []
    for start, point in enumerate(actual):
        if max(abs(a-b) for a, b in zip(expected[0], point)) > 1e-9:
            continue
        for direction in [1, -1]:
            aligned = [actual[(start+direction*i) % len(actual)] for i in range(len(actual))]
            errors = [max(abs(a-b) for a, b in zip(left, right))
                      for left, right in zip(expected, aligned)]
            candidates.append((max(errors), start, direction, aligned))
    assert candidates
    error, start, direction, aligned = min(candidates, key=lambda row: row[0])
    assert error <= 1e-9
    wrong_error = max(max(abs(a-b) for a, b in zip(left, right))
                      for left, right in zip(defaults, aligned))
    assert wrong_error > 1e-9
    polygon = Polygon(xy)
    geo_polygon = shape(geographic_feature["geometry"])
    row = source_rows[ward]
    assert row["source_unit_id"] == f"Dover:Ward:{ward}" and row["source_count"] >= 0
    decisions.append(dict(
        city="Dover", native_ward=ward, native_properties=properties,
        source_unit_id=row["source_unit_id"], native_count=row["source_count"],
        count_source_url=row["source_url"], native_projection_epsg=3437,
        declared_datum_operation=dict(authority="ESRI", code=108190, direction="inverse"),
        native_vertices=len(xy), native_valid=polygon.is_valid, geographic_valid=geo_polygon.is_valid,
        native_validity=explain_validity(polygon), geographic_validity=explain_validity(geo_polygon),
        maximum_projection_error_degrees=error, rejected_default_projection_error_degrees=wrong_error,
        cyclic_vertex_adjacency_preserved=True, server_ring_start=start, server_ring_direction=direction,
        native_projected_area=polygon.area, native_projected_area_units="US_survey_feet_squared_NOT_geodesic",
        source_count_join_qualified=polygon.is_valid and geo_polygon.is_valid,
        source_layer_id=11, source_item_id="3d1a8bdf3eaa49e09cf5d9da5b56bf9c",
        source_reference_vintage=2022, native_fips_is_not_a_county_id=True,
        geometry_repaired_or_clipped=False, legal_2026_boundary_certification=False,
        analysis_denominator=None, analysis_rate=None, maps_approved=False))
    polygons[ward] = polygon
assert set(polygons) == set(range(1, 7))
pairs = []
for (left_ward, left), (right_ward, right) in itertools.combinations(sorted(polygons.items()), 2):
    area = left.intersection(right).area if left.is_valid and right.is_valid else None
    pairs.append(dict(
        left_native_ward=left_ward, right_native_ward=right_ward,
        native_overlap_area=area, positive_native_overlap=None if area is None else area > 0,
        native_projected_area_units="US_survey_feet_squared_NOT_geodesic",
        source_geometry_repaired=False))
assert sum(row["native_count"] for row in decisions) == city["source_count"]
summary = dict(
    status="PASS_six_direct_native_Dover_references_NOT_website_acceptance",
    source_layer_id=11, source_reference_vintage=2022,
    native_ward_count_rows=6, native_references=6,
    qualified_native_count_joins=sum(row["source_count_join_qualified"] for row in decisions),
    checked_native_vertices=sum(row["native_vertices"] for row in decisions),
    pair_decisions=len(pairs), positive_native_overlap_pairs=sum(row["positive_native_overlap"] is True for row in pairs),
    native_ward_count_sum=15941, native_printed_city_parent=15941,
    maximum_projection_error_degrees=max(row["maximum_projection_error_degrees"] for row in decisions),
    strict_projection_tolerance_degrees=1e-9,
    declared_datum_operation=dict(authority="ESRI", code=108190, direction="inverse"),
    default_null_offset_rejected=True, all_cyclic_vertex_adjacency_preserved=True,
    no_private_city_keys_parcel_or_population_allocation_used=True,
    source_geometry_repaired_or_clipped=False, analysis_rates_approved=False,
    maps_approved=False, whole_project_complete=False)
assert summary["qualified_native_count_joins"] == 6 and len(pairs) == 15
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(dict(summary=summary, all_native_reference_decisions=decisions,
    all_native_pair_decisions=pairs, independent_datum_definition=datum.to_json_dict(),
    independent_datum_pipeline=datum.to_proj4()), indent=2)+"\n")
print(json.dumps(summary))

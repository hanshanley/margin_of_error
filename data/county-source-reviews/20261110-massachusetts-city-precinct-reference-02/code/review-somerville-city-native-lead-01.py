import argparse
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import zipfile

from pyproj import CRS, Transformer
import shapefile
from shapely.geometry import shape
from shapely.ops import transform
from shapely.validation import explain_validity


FILES = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=FILES / "somerville-independent-remaining-boundary-leads-01")
parser.add_argument("--prior-root", type=Path, default=FILES / "massachusetts-independent-city-sources-20261110-01")
parser.add_argument("--output", type=Path)
args = parser.parse_args()
ROOT = args.root
ORIGINALS = args.prior_root
OUTPUT = args.output or ROOT / "native-only-review.json"
assert not OUTPUT.exists()
archive_path = ROOT / "city-declared-precinct-original.zip"
receipt = json.loads((ROOT / "city-declared-precinct-original.safe-receipt.json").read_bytes())
assert receipt["http_status"] == 200
assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == receipt["sha256"]
counts = json.loads((ORIGINALS / "native-count-review-01/complete-native-count-queries.json").read_bytes())
count_rows = {f'{row["ward"]}-{row["precinct"]}': row
              for row in counts["somerville_native_counts"] if row["native_level"] == "precinct"}
assert len(count_rows) == 32
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
    reader = shapefile.Reader(shp=io.BytesIO(archive.read("Precincts.shp")),
                              shx=io.BytesIO(archive.read("Precincts.shx")),
                              dbf=io.BytesIO(archive.read("Precincts.dbf")))
    crs = CRS.from_wkt(archive.read("Precincts.prj").decode())
    assert crs.geodetic_crs.equals(CRS.from_epsg(4269), ignore_axis_order=True)
    assert all(math.isclose(axis.unit_conversion_factor, 1200/3937, abs_tol=1e-15,
                            rel_tol=0) for axis in crs.axis_info)
    assert not crs.equals(CRS.from_epsg(2249)), "Preserve the original unrounded false easting"
    native_shapes = list(reader.iterShapeRecords())

assert len(native_shapes) == 32
polygons, rows = {}, []
for native in native_shapes:
    attributes = native.record.as_dict()
    label = attributes["Precinct"]
    assert label in count_rows and label not in polygons
    assert str(attributes["WARD"]) == count_rows[label]["ward"]
    polygon = shape(native.shape.__geo_interface__)
    polygons[label] = polygon
    rows.append(dict(
        native_label=label, native_id=attributes["ID"],
        native_vertices=len(native.shape.points), native_parts=len(native.shape.parts),
        native_valid=polygon.is_valid, native_validity=explain_validity(polygon),
        native_area_us_survey_feet_squared=polygon.area,
        native_ballots_literal=count_rows[label]["ballots_cast_literal"],
        source_count_identity_qualified=polygon.is_valid and polygon.area > 0,
        geographic_transform_verified=False, maps_approved=False,
        legal_2026_precinct_certification=False))
assert set(polygons) == set(count_rows)
pairs = []
for (left_label, left), (right_label, right) in itertools.combinations(polygons.items(), 2):
    area = left.intersection(right).area if left.is_valid and right.is_valid else None
    pairs.append(dict(left_label=left_label, right_label=right_label,
                      overlap_area_us_survey_feet_squared=area,
                      positive_overlap=None if area is None else area > 0))
assert len(pairs) == 496
unit_conversion = Transformer.from_crs(crs, 26986, always_xy=True)
parents = json.loads((ORIGINALS /
    "selected-native-geometry-02/somerville-parent-precincts-full-native-projected-original.json").read_bytes())
comparisons = []
for parent in parents["features"]:
    label = parent["attributes"]["WP_DISTRICT"]
    rings = parent["geometry"]["rings"]
    assert len(rings) == 1
    reference = shape(dict(type="Polygon", coordinates=rings))
    members = [label] + ([label+"A"] if label+"A" in polygons else [])
    original_parts = [transform(unit_conversion.transform, polygons[key]) for key in members]
    covered = original_parts[0]
    for part in original_parts[1:]:
        covered = covered.union(part)
    comparisons.append(dict(
        native_parent_label=label, original_city_members=members,
        symmetric_difference_metres_squared=covered.symmetric_difference(reference).area,
        source_parent_area_metres_squared=reference.area,
        comparison_only_no_derived_polygon_published=True))
summary = dict(
    status="PASS_native_only_candidate_32_city_shapes_NOT_geographic_or_website_acceptance",
    native_shapes=32, native_count_identity_matches=32,
    native_valid_shapes=sum(row["native_valid"] for row in rows),
    native_vertices=sum(row["native_vertices"] for row in rows),
    pair_decisions=496, positive_native_overlap_pairs=sum(row["positive_overlap"] is True for row in pairs),
    ballots_sum=sum(row["native_ballots_literal"] for row in rows),
    existing_four_parent_holds_have_direct_native_city_labels=True,
    duplicate_native_ids_retained=True,
    native_projection="original_NAD83_Massachusetts_Mainland_WKT_US_survey_feet",
    original_wkt=crs.to_wkt(),
    rejected_exact_epsg2249_assignment=True,
    comparison_projection="EPSG:26986_metres_unit_conversion_only",
    no_clipping_repair_allocation_or_rates=True,
    geographic_transform_verified=False, published_release_changed=False, maps_approved=False)
assert summary["ballots_sum"] == 64597
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(dict(summary=summary, all_native_shape_decisions=rows,
    all_native_pair_decisions=pairs, all_parent_comparisons=comparisons), indent=2)+"\n")
print(json.dumps(summary))

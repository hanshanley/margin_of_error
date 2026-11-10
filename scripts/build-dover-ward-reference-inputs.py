"""Freeze the direct state-published Dover references without replacing earlier inputs."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/precinct-source-reviews/20261110-new-hampshire-ward-reference-04"
PRIOR = "data/precinct-source-reviews/20261110-new-hampshire-ward-reference-03"


def build(source, reader):
    target = ROOT / VERSION
    if target.exists():
        raise ValueError("A frozen source version cannot be overwritten")
    previous = json.loads((ROOT / PRIOR / "inputs.json").read_bytes())
    files = dict(previous["files"])
    assert len(files) == 140
    for name, pin in files.items():
        body = (ROOT / name).read_bytes()
        assert len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"]
    bodies = {}

    def add(name, body):
        assert name not in bodies
        bodies[name] = body

    for name in [
        "granit-dover2022-full-native-projected-original.json",
        "granit-dover2022-full-native-projected-original.json.receipt.json",
        "granit-dover2022-full-geographic-original.geojson",
        "granit-dover2022-full-geographic-original.geojson.receipt.json",
        "granit-dover2022-native-count.json", "granit-dover2022-native-count.receipt.json",
        "granit-dover2022-native-ids.json", "granit-dover2022-native-ids.receipt.json",
        "granit-declared-3437-4326-transformations.json",
        "granit-declared-3437-4326-transformations.receipt.json",
        "granit-portal-declared-geometry-service.json",
        "granit-portal-declared-geometry-service.receipt.json",
        "held-native-four-city-count-queries.json",
        "complete-native-ward-reference-review.json",
    ]:
        add(name, (source / name).read_bytes())
    item = json.loads((source / "granit-2022-declared-item.private.json").read_bytes())
    layer = json.loads((source / "granit-2022-voting-ward-layer11.private.json").read_bytes())
    portal_body = (source / "granit-declared-public-portal.private.json").read_bytes()
    portal = json.loads(portal_body)
    assert item["id"] == "3d1a8bdf3eaa49e09cf5d9da5b56bf9c"
    assert item["owner"] == "NHGRANIT" and item["access"] == "public"
    assert item["url"].endswith("/APB_ElectoralDistricts/FeatureServer/11")
    assert layer["id"] == 11 and layer["name"] == "NHPolitDists_VW_2022"
    assert layer["geometryType"] == "esriGeometryPolygon"
    assert portal["helperServices"]["geometry"]["url"] == (
        "https://utility.arcgisonline.com/arcgis/rest/services/Geometry/GeometryServer")
    add("granit-2022-declared-item.json", (source / "granit-2022-declared-item.private.json").read_bytes())
    add("granit-2022-voting-ward-layer11.json",
        (source / "granit-2022-voting-ward-layer11.private.json").read_bytes())
    declaration = dict(
        city="Dover", source_owner="NHGRANIT", source_item_id=item["id"],
        source_title=item["title"], source_description=item["description"],
        source_url=item["url"], source_reference_vintage=2022, actual_ward_layer_id=11,
        native_projection_epsg=3437, native_identity_field="district",
        literal_expected_districts=[f"Dover Ward {number}" for number in range(1, 7)],
        native_fips=17010, native_fips_is_not_a_county_id=True,
        public_portal_source="https://nhgeodata.unh.edu/portal/sharing/rest/portals/self?f=json",
        public_portal_original_sha256=hashlib.sha256(portal_body).hexdigest(),
        declared_geometry_service=portal["helperServices"]["geometry"]["url"],
        unrelated_portal_contacts_accounts_and_app_config_excluded=True,
        certified_legal2026_precinct_boundaries=False, private_city_keys_used=False,
        source_geometry_repaired=False, source_geometry_clipped=False)
    add("dover-granit-safe-source-declaration.json", (json.dumps(declaration, indent=2)+"\n").encode())
    add("code/review-dover-granit-native-wards-01.py", reader.read_bytes())
    independent = json.loads(bodies["complete-native-ward-reference-review.json"])
    assert independent["summary"]["qualified_native_count_joins"] == 6
    assert independent["summary"]["checked_native_vertices"] == 1987
    assert independent["summary"]["native_ward_count_sum"] == 15941
    assert independent["summary"]["maximum_projection_error_degrees"] <= 1e-9
    assert len(bodies) == 18
    for name in ["inputs.json", "queries.json.gz"]:
        body = (ROOT / PRIOR / name).read_bytes()
        files[PRIOR + "/" + name] = dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    for name, body in bodies.items():
        files[VERSION + "/" + name] = dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    assert len(files) == 160
    inputs = dict(
        version=VERSION, files=files, previous_ward_query_path=PRIOR+"/queries.json.gz",
        source_count_election_date="2026-11-03", retained_city_source_fields=242,
        retained_native_ward_rows=37, mapped_cities=dict(Manchester=12, Concord=10, Nashua=9, Dover=6),
        held_table_only_ward_rows=0, source_reference_vintage=2022,
        source_counts_repaired=False, source_geometry_repaired=False, source_geometry_clipped=False,
        native_federal_only_added=False, analysis_denominator=None, analysis_rate=None,
        certified_legal_precinct_boundaries=False,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-new-hampshire-native-ward-reference-20261110-04/complete-analysis.zip")
    target.mkdir(parents=True)
    for name, body in bodies.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (target / "inputs.json").write_text(json.dumps(inputs, indent=2)+"\n")
    print(json.dumps(dict(status="PASS_frozen_complete_Dover_inputs_NOT_website_acceptance",
        sufficient_inputs=len(files), retained_previous_pins=140, new_originals_and_readers=len(bodies),
        source_city_observations=4, native_ward_rows=37, qualified_new_Dover_references=6)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reader", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.reader)

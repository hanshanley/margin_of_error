"""Use unmodified full native MN references, not repaired legacy generalizations."""

import argparse
import gzip
import importlib.util
import json
from pathlib import Path

from shapely.geometry import shape
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mn_followup", ROOT / "scripts/minnesota-followup.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
PUBLIC = "public/participation-precincts/20261110-minnesota-followup-02"
TAG = "voter-minnesota-native-county-followup-20261110-02"


def freeze():
    source = ROOT / core.VERSION
    if (source / "geometry-inputs.json").exists():
        raise ValueError("Never replace frozen geometry inputs")
    previous = ROOT / "data/precinct-results/20261105-expansion-01"
    checksums = json.loads((previous / "checksums.json").read_bytes())
    names = [
        "originals/MN-boundaries-0.geojson", "originals/MN-boundaries-2000.geojson",
        "originals/MN-boundaries-4000.geojson", "originals/MN-boundary-count.json",
        "originals/MN-PrctTbl.txt", "2026/MN.geojson.gz",
    ]
    bodies = {}
    for name in names:
        body = (previous / name).read_bytes()
        pin = checksums[name]
        if len(body) != pin["bytes"] or core.digest(body) != pin["sha256"]:
            raise ValueError("Changed already-held native reference: " + name)
        bodies["geometry-source/" + Path(name).name] = body
    coverage = json.loads((previous / "index.json").read_bytes())["coverage"]["2026"]["MN"]
    bodies["geometry-source/previous-qualified-MN-coverage.json"] = core.encoded(coverage)
    bodies["geometry-source/reference-declaration.json"] = core.encoded(dict(
        source_item_id="6c2c813b33144d49ba993bd86b3a58ba",
        source_url=coverage["boundary_source"], source_reference_date=coverage["boundary_date"],
        raw_native_pages=3, native_projection="source_GeoJSON_longitude_latitude",
        identity_fields=["countycode", "countyfips", "pctcode", "vtdid"],
        native_county_code_is_not_fips=True, native_county_fips_is_separate_three_digit_field=True,
        literal_reference_and_statistics_names_preserved=True,
        no_new_acquisition=True, source_geometry_repaired=False, certified_legal_boundaries=False))
    for name, body in bodies.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    (source / "geometry-inputs.json").write_text(json.dumps(dict(files={
        name: dict(bytes=len(body), sha256=core.digest(body)) for name, body in sorted(bodies.items())}),
        indent=2) + "\n")


def qualify(root=ROOT):
    source = root / core.VERSION
    inputs = json.loads((source / "geometry-inputs.json").read_bytes())
    originals = {}
    for name, pin in inputs["files"].items():
        body = (source / name).read_bytes()
        if len(body) != pin["bytes"] or core.digest(body) != pin["sha256"]:
            raise ValueError("Changed sufficient reference original")
        originals[Path(name).name] = body
    data = core.load(root)
    units = {(str(int(row["native_county_id"])), row["native_precinct_id"]): row
             for row in data["all4105_native_precinct_decisions"]}
    native = [feature for start in [0, 2000, 4000]
              for feature in json.loads(originals[f"MN-boundaries-{start}.geojson"])["features"]]
    if len(native) != len(units) or json.loads(originals["MN-boundary-count.json"])["count"] != 4105:
        raise ValueError("Incomplete native geometry universe")
    features, decisions, polygons, seen = [], [], [], set()
    for original in native:
        p = original["properties"]
        row = units.get((p["countycode"], p["pctcode"]))
        if (row is None or p["vtdid"] in seen or p["vtdid"] != row["county_fips"] + row["native_precinct_id"]
                or "27" + p["countyfips"] != row["county_fips"]
                or p["countyname"].casefold() != row["county"].casefold()):
            raise ValueError("Ambiguous native county/precinct/VTD identity; no guessed name joins")
        seen.add(p["vtdid"])
        polygon = shape(original["geometry"])
        if not polygon.is_valid or polygon.is_empty or original["geometry"]["type"] not in ["Polygon", "MultiPolygon"]:
            raise ValueError("Invalid full native reference; never repair or substitute generalized geometry")
        polygons.append(polygon)
        n = row["source_record"]
        properties = dict(
            key=f'MN|{row["native_county_id"]}|{row["native_precinct_id"]}',
            year=2026, state_code="MN", county=row["county"], county_fips=row["county_fips"],
            county_id=f'additional:MN:followup:{row["native_county_id"]}',
            unit=row["native_precinct_name"], unit_key=row["native_precinct_id"],
            unit_kind="geographic_precinct", reporting_unit_kind="geographic_precinct",
            native_county_id=row["native_county_id"], native_precinct_id=row["native_precinct_id"],
            source_snapshot="20261110-minnesota-followup-02",
            match_status="matched_current_native_reference", ballots=row["total_number_voted"],
            denominator=None, reported_pct=None, native_record=n,
            maps_approved=True, source_count_qualified=row["reported_statistics"],
            cast_ballot_count_qualified=False, unique_voter_count_qualified=False,
            source_election_date="2026-11-03", participation_measure_label="Native Total Number Voted",
            geometry_withheld_reason=None,
            rate_withheld_reason="Native statistics count only; no new precinct analysis fraction is approved.",
            reference_geometry=dict(native_vtdid=p["vtdid"], native_county_code=p["countycode"],
                native_county_fips=p["countyfips"], native_precinct_code=p["pctcode"],
                literal_reference_name=p["pctname"], source_reference_date="2026-09-18",
                source_item_id="6c2c813b33144d49ba993bd86b3a58ba",
                topology_valid_without_repairs=True, full_native_coordinates_preserved=True,
                generalized_legacy_geometry_used=False, certified_legal_boundaries=False,
                source_geometry_clipped=False, native_overlaps_preserved=True),
            source_url="https://electionresultsfiles.sos.mn.gov/20261103/pctstats.txt",
            source_update_label="Results-page update11/07/26 5:18 PM; timezone unknown. Download receipt is separate.",
            source_reporting_label="Native flag1 reports counts;26 flag0 rows remain unknown, not observed zero. "
                "Full original September18,2026 native reference, not repaired/generalized legacy shapes or certified election-day boundaries.",
            boundary_label="Full native September18,2026 Minnesota display reference; not certified legal precincts")
        features.append(dict(type="Feature", properties=properties, geometry=original["geometry"]))
        decisions.append(dict(native_vtdid=p["vtdid"], native_county_id=row["native_county_id"],
            native_precinct_id=row["native_precinct_id"], county_fips=row["county_fips"],
            source_name=row["native_precinct_name"], reference_name=p["pctname"],
            names_differ_beyond_case=p["pctname"].casefold() != row["native_precinct_name"].casefold(),
            native_identity_qualified=True, full_native_topology_valid=True,
            source_geometry_sha256=core.digest(core.encoded(original["geometry"])),
            source_count=row["total_number_voted"], source_reported=row["reported_statistics"],
            analysis_rate=None, geometry_repaired=False))
    tree = STRtree(polygons)
    pairs = []
    for left, polygon in enumerate(polygons):
        for right in sorted(int(index) for index in tree.query(polygon) if int(index) > left):
            area = polygon.intersection(polygons[right]).area
            pairs.append(dict(left_native_vtdid=decisions[left]["native_vtdid"],
                right_native_vtdid=decisions[right]["native_vtdid"],
                native_overlap_coordinate_degrees_squared=area, positive_overlap=area > 0,
                area_is_not_geodesic_or_projected_square_meters=True, source_geometry_repaired=False))
    legacy = json.loads(gzip.decompress(originals["MN.geojson.gz"]))
    invalid_legacy = [feature["properties"]["key"] for feature in legacy["features"]
                      if not shape(feature["geometry"]).is_valid]
    total_pairs = len(native) * (len(native) - 1) // 2
    return dict(summary=dict(
        source_reference_date="2026-09-18", direct_native_references=4105,
        reported_source_counts=4079, unreported_source_counts=26, analysis_rates=0,
        complete_reference_decisions=4105, complete_bbox_candidate_pair_decisions=len(pairs),
        all_native_pairs=total_pairs, bbox_disjoint_pairs=total_pairs - len(pairs),
        positive_native_overlap_pairs=sum(row["positive_overlap"] for row in pairs),
        names_differ_beyond_case=sum(row["names_differ_beyond_case"] for row in decisions),
        invalid_generalized_legacy_references_not_reused=invalid_legacy,
        full_native_geometry_repaired=False, generalized_geometry_repaired=False,
        certified_legal_boundaries=False),
        all4105_reference_decisions=decisions, all_bbox_candidate_pair_decisions=pairs,
        geojson=dict(type="FeatureCollection", features=features))


def prepare():
    source = ROOT / core.VERSION
    public = ROOT / PUBLIC
    if (source / "precinct-reference-queries.json.gz").exists() or public.exists():
        raise ValueError("Never replace an existing prepared direct-reference version")
    data = qualify()
    body = gzip.compress(core.encoded(data["geojson"]), mtime=0)
    (source / "MN.geojson.gz").write_bytes(body)
    (source / "precinct-reference-queries.json.gz").write_bytes(gzip.compress(core.encoded(data), mtime=0))
    url = f"https://raw.githubusercontent.com/hanshanley/margin_of_error/{TAG}/{core.VERSION}/MN.geojson.gz"
    metadata = dict(source_id="minnesota-native-followup-20261110-02", expected_features=4105,
        bytes=len(body), sha256=core.digest(body), counts_only=True, rates_approved=False,
        reported_source_counts=4079, unknown_source_counts=26, source_reference_date="2026-09-18",
        certified_legal_precinct_boundaries=False, boundary_label="Full native September18,2026 reference; not certified legal precincts",
        native_overlaps_preserved=True, **{key: data["summary"][key] for key in [
            "positive_native_overlap_pairs", "names_differ_beyond_case"]},
        complete_download_url=f"https://github.com/hanshanley/margin_of_error/releases/download/{TAG}/complete-analysis.zip",
        notes="All4105 references use original full native geometry, not16 invalid generalized legacy shapes or repaired boundaries. "
            "4079 native count rows/26 unknowns; no precinct rate. Literal reference/statistics names remain separate; "
            "native countycode/pctcode and explicit VTD/fips fields control joins. Native overlaps remain unchanged.")
    public.mkdir(parents=True)
    index = dict(states=dict(MN=url), state_metadata=dict(MN=metadata))
    (public / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    registry_path = ROOT / "public/participation-precincts.json"
    registry = json.loads(registry_path.read_bytes())
    pointer = {"base_url": "/" + PUBLIC.removeprefix("public/") + "/"}
    if pointer in registry["additional_sources"]:
        raise ValueError("Duplicate new Minnesota reference registration")
    registry["additional_sources"].append(pointer)
    registry_path.write_text(json.dumps(registry, indent=2) + "\n")
    print(json.dumps(dict(status="PASS_full_native_reference_prepared_NOT_live", bytes=len(body),
        sha256=core.digest(body), summary=data["summary"])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-inputs", action="store_true")
    args = parser.parse_args()
    if args.freeze_inputs:
        freeze()
    else:
        prepare()

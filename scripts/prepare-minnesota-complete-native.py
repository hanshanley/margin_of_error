"""Prepare complete numerical queries and unchanged-coordinate display references once."""

import gzip
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mn_complete", ROOT / "scripts/minnesota-complete-native.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
source = ROOT / core.VERSION
if (source / "queries.json.gz").exists():
    raise ValueError("Never replace an existing prepared native query")
data = core.load()
geometry = data.pop("full_unchanged_coordinate_feature_collection")
references = dict(all4105_native_reference_decisions=data.pop("all4105_native_reference_decisions"),
    all_bbox_candidate_pair_decisions=data.pop("all_bbox_candidate_pair_decisions"))
raw_geometry = core.encoded(geometry)
geometry_body = gzip.compress(raw_geometry, mtime=0)
(source / "MN.geojson.gz").write_bytes(geometry_body)
data["precinct_reference"] = dict(
    file="https://github.com/hanshanley/margin_of_error/releases/download/"
        "voter-minnesota-complete-native-statistics-20261110-03/MN.geojson.gz",
    bytes=len(geometry_body), sha256=core.pin(geometry_body)["sha256"],
    uncompressed_sha256=core.pin(raw_geometry)["sha256"], expected_features=4105,
    source_reference_date="2026-09-18", source_snapshot="20261110-minnesota-complete-native-03",
    certified_legal_boundaries=False, full_native_coordinates_preserved=True)
query_body = gzip.compress(core.encoded(data), mtime=0)
(source / "queries.json.gz").write_bytes(query_body)
(source / "precinct-reference-queries.json.gz").write_bytes(gzip.compress(core.encoded(references), mtime=0))
(source / "summary.json").write_text(json.dumps(data["summary"], indent=2) + "\n")
(source / "reference-summary.json").write_text(json.dumps(data["precinct_reference"], indent=2) + "\n")
print(json.dumps(dict(status="PASS_complete_native_queries_prepared_NOT_view_acceptance",
    query=core.pin(query_body), geometry=core.pin(geometry_body), summary=data["summary"])))

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


VERSION = "20261110-massachusetts-city-precinct-reference-02"
PRIOR = "20261110-massachusetts-native-local-counts-01"
parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--prior-originals", type=Path, required=True)
parser.add_argument("--readers", type=Path, required=True)
args = parser.parse_args()
target = Path("data/county-source-reviews") / VERSION
prior = Path("data/county-source-reviews") / PRIOR
assert not target.exists(), "A frozen input set cannot be overwritten"
assert Path("public/scripts/participation-explorer.js").is_file()
prior_body = (prior / "inputs.json").read_bytes()
prior_inputs = json.loads(prior_body)
assert prior_inputs["version"] == PRIOR and len(prior_inputs["files"]) == 67
for name, receipt in prior_inputs["files"].items():
    body = (prior / name).read_bytes()
    assert len(body) == receipt["bytes"] and hashlib.sha256(body).hexdigest() == receipt["sha256"]
source = args.source
bodies = {}


def add(name, body):
    assert name not in bodies
    bodies[name] = body


for name in [
    "city-declared-precinct-original.zip",
    "city-declared-precinct-original.safe-receipt.json",
    "city-declared-precinct-metadata.safe-receipt.json",
    "native-only-review.json", "geographic-review.json",
    "verified32-city-display-reference.geojson",
    "exact-wkt-transformations-request.json",
    "exact-wkt-transformations-response.json",
    "exact-wkt-transformations-receipt.json",
    "all32-exact-wkt-geographic-request.json",
    "all32-exact-wkt-geographic-response.json",
    "all32-exact-wkt-geographic-receipt.json",
]:
    add(name, (source / name).read_bytes())

metadata = (source / "city-declared-precinct-metadata.private.json").read_bytes()
metadata_receipt = json.loads(bodies["city-declared-precinct-metadata.safe-receipt.json"])
assert hashlib.sha256(metadata).hexdigest() == metadata_receipt["sha256"]
raw_metadata = json.loads(metadata)
assert raw_metadata["provenance"] == "official" and raw_metadata["name"] == "Precincts"
catalog = json.loads((source / "city-open-data-catalog.private.json").read_bytes())
dataset = [row for row in catalog["dataset"] if row["title"] == "Precincts"]
assert len(dataset) == 1
declaration = {key: dataset[0][key] for key in [
    "title", "description", "identifier", "modified", "landingPage", "distribution"]}
assert declaration["identifier"] == "https://data.somervillema.gov/api/views/da4y-vuae"
assert declaration["distribution"][0]["downloadURL"] == (
    "https://data.somervillema.gov/download/da4y-vuae/application/x-zip-compressed")
assert "September 22, 2023" in declaration["description"]
assert "2020 Census" in declaration["description"]
declaration["metadata_original_sha256"] = hashlib.sha256(metadata).hexdigest()
declaration["catalog_original_sha256"] = hashlib.sha256(
    (source / "city-open-data-catalog.private.json").read_bytes()).hexdigest()
declaration["selected_metadata"] = {key: raw_metadata[key] for key in [
    "name", "description", "publicationDate", "viewLastModified", "provenance"]}
declaration["unrelated_catalog_entries_owner_accounts_and_contacts_excluded"] = True
add("public-city-precinct-declarations.json", (json.dumps(declaration, indent=2)+"\n").encode())

for source_name, target_name in [
    ("massgis-declared-geometry-server.private.json", "public-geometry-server.json"),
    ("massgis-declared-geometry-server.safe-receipt.json", "public-geometry-server.safe-receipt.json"),
]:
    add(target_name, (args.prior_originals / "geometry-discovery-01" / source_name).read_bytes())
server = json.loads(bodies["public-geometry-server.json"])
assert set(server) <= {"serviceDescription"}
server_receipt = json.loads(bodies["public-geometry-server.safe-receipt.json"])
assert server_receipt["sha256"] == hashlib.sha256(bodies["public-geometry-server.json"]).hexdigest()
for name in ["review-somerville-city-native-lead-01.py", "project-somerville-city-native-lead-01.py"]:
    add("code/" + name, (args.readers / name).read_bytes())

native = json.loads(bodies["native-only-review.json"])
geographic = json.loads(bodies["geographic-review.json"])
features = json.loads(bodies["verified32-city-display-reference.geojson"])
assert native["summary"]["native_shapes"] == native["summary"]["native_valid_shapes"] == 32
assert native["summary"]["ballots_sum"] == 64597
assert native["summary"]["pair_decisions"] == len(native["all_native_pair_decisions"]) == 496
assert native["summary"]["positive_native_overlap_pairs"] == 0
assert geographic["summary"]["checked_vertices"] == 2697
assert geographic["summary"]["maximum_error_degrees"] <= 1e-9
assert geographic["summary"]["exact_original_wkt_preserved"]
assert all(row["cyclic_vertex_adjacency_preserved"] for row in geographic["all_decisions"])
assert len(features["features"]) == len({row["properties"]["native_label"]
                                       for row in features["features"]}) == 32
receipt = json.loads(bodies["city-declared-precinct-original.safe-receipt.json"])
assert receipt["sha256"] == hashlib.sha256(bodies["city-declared-precinct-original.zip"]).hexdigest()
assert receipt["sha256"] == "1451f29c5b93dd9409c0e9756383bc3f2ee60369535e1181a9652fea196d354c"
with zipfile.ZipFile(source / "city-declared-precinct-original.zip") as archive:
    assert archive.testzip() is None and len(archive.infolist()) == 8
assert len(bodies) == 17
inputs = dict(
    version=VERSION, state_code="MA", year=2026, native_election_date="2026-11-03",
    prior_source_version=PRIOR,
    prior_inputs_sha256=hashlib.sha256(prior_body).hexdigest(),
    prior_sufficient_inputs=67, current_additional_sufficient_inputs=17,
    complete_download_url=("https://github.com/hanshanley/margin_of_error/releases/download/"
                           "voter-massachusetts-city-precinct-reference-20261110-02/complete-analysis.zip"),
    native_reporting_rows=307, qualified_reporting_references=307, split_parent_holds=0,
    city_native_shapes=32, city_native_vertices=2697, city_native_pair_decisions=496,
    native_identity_fields=["WARD", "Precinct"], duplicate_native_ids_preserved=True,
    exact_native_wkt_required=True, native_projection_epsg=None,
    source_metadata_revision="2023-09-22", source_census_basis=2020,
    current_display_reference_year=None, certified_2026_election_boundaries=False,
    source_geometries_clipped=False, source_geometries_repaired=False,
    source_counts_repaired=False, candidate_votes_used_as_ballots=False,
    modes_added=False, analysis_rates_approved=False,
    individual_voter_or_private_address_data_requested=False,
    full_original_city_gis_zip_and_public_polling_place_columns_retained=True,
    queries=dict(native_reference="native-only-review.json", geographic_reference="geographic-review.json",
                 display_reference="verified32-city-display-reference.geojson"),
    files={name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
           for name, body in sorted(bodies.items())})
target.mkdir(parents=True)
for name, body in bodies.items():
    path = target / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
(target / "inputs.json").write_text(json.dumps(inputs, indent=2)+"\n")
print(json.dumps(dict(
    status="PASS_full_city_reference_extension_inputs_frozen_NOT_website_acceptance",
    new_sufficient_inputs=17, prior_sufficient_inputs_retained=67,
    new_input_bytes=sum(len(body) for body in bodies.values()),
    full_original_city_zip_bytes=len(bodies["city-declared-precinct-original.zip"]),
    native_shapes=32, native_vertices=2697, native_pair_decisions=496, maps_approved=False)))

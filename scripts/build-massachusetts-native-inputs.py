import argparse
import hashlib
import html
import json
from pathlib import Path

from bs4 import BeautifulSoup
import fitz


VERSION = "20261110-massachusetts-native-local-counts-01"
parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--readers", type=Path, required=True)
args = parser.parse_args()
target = Path("data/county-source-reviews") / VERSION
assert not target.exists(), "A frozen numerical input set cannot be overwritten"
assert Path("public/scripts/participation-explorer.js").is_file()
source = args.source
bodies = {}


def add(name, body):
    assert name not in bodies
    bodies[name] = body


def add_source(name):
    add(name, (source / name).read_bytes())


pdfs = sorted((source / "declared-results-01").glob("*.pdf"))
assert len(pdfs) == 4 and sum(len(fitz.open(path)) for path in pdfs) == 648
for path in pdfs:
    add_source("declared-results-01/" + path.name)
    add_source("declared-results-01/" + path.name + ".receipt.json")
for folder in ["selected-native-geometry-01", "selected-native-geometry-02"]:
    paths = sorted((source / folder).iterdir())
    assert len(paths) == 16 and all(path.is_file() for path in paths)
    for path in paths:
        add_source(folder + "/" + path.name)

boston_receipt = json.loads((source / "boston-declaring-page.safe-receipt.json").read_bytes())
raw_page = (source / "boston-declaring-page.private.html").read_bytes()
assert hashlib.sha256(raw_page).hexdigest() == boston_receipt["sha256"]
soup = BeautifulSoup(raw_page, "html.parser")
parts = ["<!doctype html><meta charset=\"utf-8\"><h1>Unofficial Election Results</h1>"]
for declaration in boston_receipt["native_2026_declarations"]:
    parts.append("<p>" + html.escape(declaration) + "</p>")
count_tables = 0
for heading in soup.select("h3"):
    if "(Vote for" not in " ".join(heading.get_text(" ", strip=True).split()):
        continue
    table = heading.find_next("table")
    if table is None:
        continue
    headers = [cell.get_text(" ", strip=True) for cell in table.select("th")]
    if not headers or "Ballots Cast" not in headers[0]:
        continue
    parts.append("<h3>" + html.escape(heading.get_text(" ", strip=True)) + "</h3>")
    # Keep the complete native aggregate table, not candidate rows, navigation or scripts.
    for node in [table, *table.find_all(True)]:
        node.attrs = {}
    parts.append(str(table))
    count_tables += 1
assert count_tables == 44
curated = ("\n".join(parts) + "\n").encode()
add("boston-declaring-page.private.html", curated)
somerville_receipt = json.loads((source / "declared-results-01/somerville-results-index.private.html.receipt.json").read_bytes())
declarations = dict(
    boston=dict(source=boston_receipt["source"], original_bytes=boston_receipt["bytes"],
                original_sha256=boston_receipt["sha256"],
                selected_public_declaration_sha256=hashlib.sha256(curated).hexdigest(),
                all44_native_aggregate_tables_retained=True,
                unrelated_navigation_contacts_scripts_and_keys_excluded=True),
    somerville=dict(source=somerville_receipt["source"],
                    original_bytes=somerville_receipt["bytes"],
                    original_sha256=somerville_receipt["sha256"],
                    native_result_heading="November 3, 2026 State Official Results",
                    native_download_label="Download the UnOfficial Election Totals",
                    declared_result_links=somerville_receipt["declared_result_links"]),
)
add("safe-city-source-declarations.json", (json.dumps(declarations, indent=2)+"\n").encode())

for name in [
    "native-count-review-01/complete-native-count-queries.json",
    "native-count-review-01/independent-native-verification.json",
    "native-count-review-01/boston-summary-native.csv",
    "native-count-review-01/boston-all-native-times-cast.csv",
    "native-count-review-01/somerville-native-counts.csv",
    "native-geometry-review-01/complete-native-reference-queries.json",
    "native-reference-extension-review-01/complete-reference-extension-queries.json.gz",
    "native-reference-extension-review-01/summary.json",
    "geometry-discovery-01/massgis-declared-26986-4326-transformations.private.json",
    "geometry-discovery-01/massgis-declared-26986-4326-transformations.safe-receipt.json",
    "geometry-discovery-01/massgis-independent-declared-datum-operations.json",
    "geometry-discovery-01/boston-declared-precinct-item.safe-receipt.json",
    "geometry-discovery-01/boston-precinct-service-parent.safe-receipt.json",
    "geometry-discovery-01/boston-precinct-layer0.safe-receipt.json",
    "geometry-discovery-01/massgis-declared-subprecinct-feature-item.safe-receipt.json",
    "geometry-discovery-01/massgis-subprecinct-service-parent.safe-receipt.json",
    "geometry-discovery-01/massgis-subprecinct-layer0.safe-receipt.json",
    "geometry-discovery-01/somerville-parent-precinct-service-parent.safe-receipt.json",
    "geometry-discovery-01/somerville-parent-precinct-layer0.safe-receipt.json",
    "geometry-discovery-01/massachusetts-municipality-service-parent.safe-receipt.json",
    "geometry-discovery-01/massachusetts-municipality-layer0.safe-receipt.json",
]:
    add_source(name)
for name in [
    "review-massachusetts-native-counts-01.py",
    "verify-massachusetts-native-counts-01.py",
    "review-massachusetts-native-geometry-01.py",
    "review-massachusetts-reference-extension-01.py",
]:
    add("code/" + name, (args.readers / name).read_bytes())

inputs = dict(
    version=VERSION, state_code="MA", year=2026, native_election_date="2026-11-03",
    complete_download_url=(
        "https://github.com/hanshanley/margin_of_error/releases/download/"
        "voter-massachusetts-native-local-counts-20261110-01/complete-analysis.zip"),
    source_city_observations=2, native_reporting_rows=307,
    qualified_reporting_references=303, split_parent_holds=4,
    native_municipal_references=351, valid_municipal_display_references=350,
    invalid_municipal_reference="WAYLAND",
    counts_repaired=False, candidate_votes_used_as_ballots=False,
    modes_added=False, parent_geometries_clipped=False,
    analysis_rates_approved=False, certified_2026_election_boundaries=False,
    private_personal_population_or_address_features_requested=False,
    queries=dict(
        counts="native-count-review-01/complete-native-count-queries.json",
        reporting_reference="native-geometry-review-01/complete-native-reference-queries.json",
        reference_extension="native-reference-extension-review-01/complete-reference-extension-queries.json.gz"),
    files={name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
           for name, body in sorted(bodies.items())},
)
target.mkdir(parents=True)
for name, body in bodies.items():
    path = target / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
(target / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
print(json.dumps(dict(status="PASS_frozen_complete_permitted_numerical_inputs_NOT_website_acceptance",
                      inputs=len(bodies), full_PDFs=4, full_pages=648,
                      source_bytes=sum(len(body) for body in bodies.values()),
                      maps_approved=False)))

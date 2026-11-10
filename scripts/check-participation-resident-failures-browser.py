"""Verify the real public county catalog and asynchronous/error isolation."""

import argparse
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4398")
parser.add_argument("--published-root", type=Path, required=True)
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
published_version = json.loads((args.published_root / "dataset.json").read_bytes())["version"]
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        page = browser.new_page(viewport=dict(width=390, height=1000))
        page.goto(base + "/robots.txt")
        page.set_content("""<main id="lab">
          <span id="native-observation">Unrelated source observation remains unchanged</span>
          <select id="year"><option value="2026">2026</option></select>
          <details id="resident-context" open hidden><summary>Resident context</summary>
            <div data-resident-controls hidden><select></select></div>
            <div data-resident-detail></div>
          </details></main>""")
        page.evaluate("""async () => {
          const module = await import('/scripts/participation-resident-context.js');
          window.residentTest = module.installResidentContext();
          const loader = await import('/scripts/participation-dataset.js');
          window.residentCatalog = await loader.loadDatasetCatalog();
          await window.residentTest.setState('FL', 'Florida');
          await window.residentTest.selectCounty('12087', 'FL');
        }""")
        host = page.locator("#resident-context")
        detail = host.locator("[data-resident-detail]")
        expect(host).to_have_attribute("data-dataset-version", published_version)
        expect(detail).to_have_attribute("data-census-geoid", "12087")
        expected = json.loads(gzip.decompress(
            (args.published_root / "states/FL.json.gz").read_bytes()))
        row = next(row for row in expected["counties"] if row["geography"]["census_geoid"] == "12087")
        value = row["median_household_income"]["estimate"]
        expect(detail).to_contain_text(f"${value:,}")
        expect(detail).to_contain_text("Native 2024 Census county reference")
        entry = page.evaluate("window.residentCatalog.datasets['resident-context']")
        remote_base = entry["base_url"]
        held = []
        page.route(remote_base + "states/MN.json.gz", lambda route: held.append(route))
        with page.expect_request(remote_base + "states/MN.json.gz"):
            page.evaluate("() => { window.residentTest.setState('MN', 'Minnesota'); }")
        page.evaluate("async () => { await window.residentTest.selectCounty('48001', 'TX'); }")
        expect(detail).to_have_attribute("data-census-geoid", "48001")
        assert len(held) == 1
        with page.expect_response(remote_base + "states/MN.json.gz"):
            held[0].fulfill(status=200, body=(args.published_root / "states/MN.json.gz").read_bytes(),
                content_type="application/gzip", headers={"Access-Control-Allow-Origin": "*"})
        page.evaluate("() => new Promise(resolve => setTimeout(resolve, 100))")
        expect(detail).to_have_attribute("data-census-geoid", "48001")
        page.route(remote_base + "states/WV.json.gz", lambda route: route.fulfill(status=200,
            body=b"corrupted test bytes", headers={"Access-Control-Allow-Origin": "*"}))
        page.evaluate("async () => { await window.residentTest.selectCounty('54001', 'WV'); }")
        expect(detail).to_contain_text("checksum differs")
        expect(detail).to_contain_text("participation observations are unchanged")
        assert detail.get_attribute("data-census-geoid") is None
        assert detail.get_attribute("data-reference-key") is None
        expect(page.locator("#native-observation")).to_have_text("Unrelated source observation remains unchanged")
        expect(detail.locator("button")).to_have_text("Retry resident context")
    finally:
        browser.close()
proof = dict(status="PASS_real_public_county_catalog_and_isolated_reader_error_behaviors",
    published_dataset_version=published_version, actual_public_catalog_and_FL_TX_files=True,
    exact_native_income=True, native_county_boundary_year_explicit=True,
    late_state_response_cannot_overwrite_new_selection=True,
    corrupted_shard_cannot_leave_old_geographic_values=True,
    unrelated_dom_unchanged=True, site_production=False,
    simulated_error_and_delayed_response_are_tests_not_publication_proof=True)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

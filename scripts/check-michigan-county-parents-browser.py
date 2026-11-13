"""Verify two native Michigan county parents without fabricating the other 81."""

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
version = ROOT / "data/county-source-reviews/20261109-michigan-native-parents-01"
queries = json.loads(gzip.decompress((version / "queries.json.gz").read_bytes()))
expected = {row["fips"]: row for row in queries}
source_dir = ROOT / "data/precinct-source-reviews/20261105/MI-2026-native-county-counts-01"
with (source_dir / "precinct-participation.csv").open() as stream:
    native_units = list(csv.DictReader(stream))
url = base + "/voter-participation/?view=states&year=2026&state=Michigan&map-level=county&map-color=turnout"
cases = []


def activate_counties(page):
    expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
    page.locator("#state-select").select_option("Michigan")


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url, wait_until="domcontentloaded")
            activate_counties(page)
            expect(page.locator("#title")).to_have_text("Local participation in Michigan", timeout=90000)
            shapes = page.locator('.geographic-detail [data-level="county"]')
            expect(shapes).to_have_count(83, timeout=60000)
            actual = shapes.evaluate_all("""els => els.map(e=>({
                key:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,
                reference:e.dataset.referenceYear,fill:getComputedStyle(e).fill,
                margin:e.hasAttribute('data-margin')
            }))""")
            observed = {row["key"]: row for row in actual if row["count"] != ""}
            assert set(observed) == set(expected)
            assert sum(row["count"] == "" for row in actual) == 81
            assert all(row["rate"] == "" and row["reference"] == "2026" and not row["margin"] for row in actual)
            assert len({row["fill"] for row in actual}) >= 3
            expect(page.locator("#geography-note")).to_contain_text("Only 2 of 83")
            expect(page.locator("#geography-note")).to_contain_text("missing, not zero")
            for fips, query in expected.items():
                assert int(observed[fips]["count"]) == query["ballots"]
                shape = page.locator(f'[data-level="county"][data-geography="{fips}"]')
                shape.focus()
                shape.press("Enter")
                expect(page.locator("#current-county-select")).to_have_value(f'additional:MI:{query["identity"]}')
                expect(page.locator("#current-county-detail")).to_contain_text(f'{query["ballots"]:,}')
                expect(page.locator("#current-county-detail")).to_contain_text("Native whole-county ballots reported")
            missing = page.locator('[data-level="county"][data-count=""]').first
            missing.focus()
            missing.press("Enter")
            expect(page.locator("#current-county-detail")).to_contain_text("No matching county participation observation")
            expect(page.locator("#current-county-detail")).not_to_contain_text("26,288")
            expect(page.locator("#current-unit-select")).to_have_count(0)
            shape = page.locator('[data-level="county"][data-geography="26017"]')
            shape.focus()
            shape.press("Enter")
            expect(page.locator("#current-unit-select option")).to_have_count(36)
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-panel")).to_be_visible()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            expect(shapes).to_have_count(83, timeout=60000)
            expect(page.locator("#year")).to_have_value("2026")
            response = page.request.get(base + "/participation-local/MI.json.gz")
            assert response.ok
            exported = json.loads(gzip.decompress(response.body()))
            assert len(exported["counties"]) == 2 and len(exported["precincts"]) == 63
            assert [row["native_record"] for row in exported["precincts"]] == native_units
            assert all(row["denominator"] is None and row["reported_pct"] is None for row in exported["counties"])
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append({"mobile": mobile, "reference_counties": 83, "native_parents": 2,
                          "missing_counties_not_zero": 81, "native_unit_rows_unchanged": 63,
                          "missing_selection_clears_stale_detail": True, "all_rates_withheld": True})
            context.close()
        context = browser.new_context(viewport={"width": 1440, "height": 1100})

        def bad_scope(route):
            response = route.fetch()
            data = json.loads(gzip.decompress(response.body()))
            for row in data["counties"]:
                row["reference_geometry"]["partial_county_fips"] = ["26017"]
            route.fulfill(body=gzip.compress(json.dumps(data).encode(), mtime=0),
                          content_type="application/gzip")

        pattern = "**/participation-local/MI.json.gz"
        context.route(pattern, bad_scope)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        activate_counties(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified partial", timeout=90000)
        assert page.locator('.geographic-detail [data-level="county"]').count() == 0
        context.unroute(pattern)
        page.get_by_role("button", name="Retry geographic detail").click()
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(83, timeout=60000)
        context.close()
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        reference = queries[0]["reference"]["url"]
        context.route(reference, lambda route: route.fulfill(
            body=b"corrupted reference", content_type="application/gzip"))
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        activate_counties(page)
        expect(page.locator("#geography-note")).to_contain_text("checksum disagrees", timeout=90000)
        context.unroute(reference)
        page.get_by_role("button", name="Retry geographic detail").click()
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(83, timeout=60000)
        archive = ROOT / "public/participation-county-parents/20261109-02/complete-analysis.zip"
        response = page.request.get(base + "/participation-county-parents/20261109-02/complete-analysis.zip")
        assert response.ok and response.body() == archive.read_bytes()
        context.close()
    finally:
        browser.close()
proof = {"status": "PASS_MI_native_county_parents", "base_url": base, "cases": cases,
         "invalid_partial_scope_retry": True, "corrupted_reference_retry": True,
         "complete_query_download_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

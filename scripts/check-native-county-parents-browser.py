"""Verify all live native county ballot parents against their complete queries."""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
queries = json.loads(gzip.decompress(
    (ROOT / "data/county-source-reviews/20261109-native-county-parents-01/queries.json.gz").read_bytes()))
results = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(args.base_url.rstrip("/") + "/voter-participation/"
                      "?view=states&year=2026&map-level=county&map-color=turnout",
                      wait_until="domcontentloaded")
            expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
            for name, code, count, rates in (("Idaho", "ID", 44, 43), ("North Dakota", "ND", 53, 0)):
                page.select_option("#state-select", name)
                shapes = page.locator('.geographic-detail [data-level="county"]')
                expect(shapes).to_have_count(count, timeout=60000)
                expect(page.locator("#title")).to_have_text(f"Local participation in {name}")
                actual = shapes.evaluate_all("""els => els.map(e=>({
                    key:e.dataset.geography,ballots:e.dataset.count,rate:e.dataset.rate,
                    reference:e.dataset.referenceYear,fill:getComputedStyle(e).fill,
                    margin:e.getAttribute('data-margin')
                }))""")
                expected = {row["fips"]: row for row in queries if row["code"] == code}
                assert {row["key"] for row in actual} == set(expected)
                for row in actual:
                    native = expected[row["key"]]
                    assert int(row["ballots"]) == native["ballots"]
                    assert row["reference"] == "2026"
                    assert row["margin"] is None
                    if native["reported_pct"] is None:
                        assert row["rate"] == ""
                    else:
                        assert math.isclose(float(row["rate"]), native["reported_pct"], rel_tol=1e-14)
                assert sum(row["rate"] != "" for row in actual) == rates
                assert len({row["fill"] for row in actual}) > 1
                response = page.request.get(args.base_url.rstrip("/") + f"/participation-local/{code}.json.gz")
                assert response.ok
                exported = json.loads(gzip.decompress(response.body()))
                assert len(exported["counties"]) == count
                assert sum(row["ballots"] for row in exported["counties"]) == sum(row["ballots"] for row in expected.values())
                assert len(exported["precincts"]) == (986 if code == "ID" else 358)
                if code == "ID":
                    twin = next(row for row in actual if row["key"] == "16083")
                    assert twin["rate"] == "" and int(twin["ballots"]) == 28906
                shapes.first.focus()
                shapes.first.press("Enter")
                expect(page.locator("#current-local-navigation")).to_contain_text("Native whole-county ballots reported")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                results.append({"state": name, "county_shapes": count, "rates": rates,
                                "mobile": mobile, "every_native_count_matches": True,
                                "all_source_units_preserved": True, "reference_year": 2026})
            assert not errors, errors
            context.close()
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        reference = next(row["reference"]["url"] for row in queries if row["code"] == "ND")
        def corrupt(route):
            response = route.fetch()
            payload = bytearray(response.body())
            payload[-1] ^= 1
            route.fulfill(body=bytes(payload), content_type="application/gzip")
        context.route(reference, corrupt)
        page = context.new_page()
        page.goto(args.base_url.rstrip("/") + "/voter-participation/"
                  "?view=states&year=2026&state=North+Dakota&map-level=county",
                  wait_until="domcontentloaded")
        expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
        page.select_option("#state-select", "North Dakota")
        expect(page.locator("#geography-note")).to_contain_text("checksum disagrees", timeout=60000)
        assert page.locator(".geographic-detail .map-feature").count() == 0
        expect(page.locator("#selection-panel > h3")).to_have_text("North Dakota")
        context.unroute(reference)
        page.get_by_role("button", name="Retry geographic detail").click()
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(53, timeout=60000)
        context.close()
        response = browser.new_context().request.get(
            args.base_url.rstrip("/") + "/participation-county-parents/20261109-01/complete-analysis.zip")
        archive = ROOT / "public/participation-county-parents/20261109-01/complete-analysis.zip"
        assert response.ok and response.body() == archive.read_bytes()
    finally:
        browser.close()
proof = {"status": "PASS_native_county_parents_live", "base_url": args.base_url,
         "script_sha256": hashlib.sha256((ROOT / "public/scripts/participation-explorer.js").read_bytes()).hexdigest(),
         "complete_download_byte_identical": True, "tampered_reference_withheld_and_retry_recovers": True,
         "cases": results}
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

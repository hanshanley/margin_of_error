"""Verify exact native geographic ballots, partial scope, navigation and failed-source retry."""

import argparse
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
if args.proof.exists():
    raise ValueError("Refuse to replace an Alaska browser proof")
base = args.base_url.rstrip("/")
version = ROOT / "data/precinct-source-reviews/20261110-alaska-native-display-01"
native = json.loads(gzip.decompress((version / "originals/precincts-original.json.gz").read_bytes()))
house = native["contestNames"].index("U.S. Representative")
by_id = {r["number"]: next(c for c in r["contests"] if c["n"] == house)
         for r in native["precincts"]}
approved = {r["native_precinct_id"] for r in json.loads(
    (version / "held-topology-queries.json").read_bytes())["queries"]
    if r["topology_valid_without_repairs"]}
counts = json.loads(gzip.decompress((version / "qualified-source-count-queries.json.gz").read_bytes()))
expected = {r["key"]: r for r in counts
            if r["reporting_unit_kind"] == "geographic_precinct" and r["source_precinct_id"] in approved}
download = json.loads((version / "inputs.json").read_bytes())["complete_download_url"]
cases = []


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + "/voter-participation/?view=precincts&year=2026&state=Alaska&layer=participation",
                                 wait_until="domcontentloaded")
            assert response.ok
            shapes = page.locator('.geographic-detail [data-level="precinct"]')
            expect(shapes).to_have_count(81, timeout=90000)
            expect(page.locator("#precinct-state-select")).to_have_value("Alaska")
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#precinct-layer")).to_have_value("participation")
            actual = shapes.evaluate_all("""els=>els.map(e=>({key:e.dataset.geography,
              count:e.dataset.count,rate:e.dataset.rate,margin:e.getAttribute('data-margin'),
              path:e.getAttribute('d')}))""")
            assert set(r["key"] for r in actual) == set(expected)
            for row in actual:
                original = expected[row["key"]]
                assert int(row["count"]) == by_id[original["source_precinct_id"]]["b"]
                assert row["rate"] == "" and row["margin"] is None
                assert row["path"] and row["path"].startswith("M")
            assert shapes.evaluate_all("els=>new Set(els.map(e=>e.getAttribute('fill'))).size") > 1
            for text in ("402", "321", "523", "120", "overseas"):
                expect(page.locator("#coverage-note")).to_contain_text(text)
            expect(page.locator("#caption")).to_contain_text("not certified legal boundaries")
            expect(page.locator("#caption a")).to_have_attribute("href", download)
            expect(page.locator("#table-head")).to_contain_text("Native geographic-unit ballots")
            expect(page.locator("#table-head")).not_to_contain_text("Democratic")
            for key in list(expected)[:2]:
                shape = page.locator(f'[data-level="precinct"][data-geography="{key}"]')
                shape.focus()
                shape.press("Enter")
                expect(page.locator("#substate-detail")).to_contain_text(f'{expected[key]["ballots"]:,}')
                expect(page.locator("#substate-detail")).to_contain_text("not assigned to this shape")
                expect(page.locator("#substate-detail")).to_contain_text("11/04/2026 2:11 PM")
                expect(page.locator("#substate-detail")).to_contain_text("timezone not supplied")
                expect(page.locator("#substate-detail")).not_to_contain_text("%")
            for _ in range(2):
                page.locator("#tab-methods").click()
                expect(page.locator("#methods-panel")).to_be_visible()
                expect(page.locator("#methods-archive")).to_be_hidden()
                page.locator("#tab-precincts").click()
                expect(shapes).to_have_count(81, timeout=60000)
                expect(page.locator("#precinct-state-select")).to_have_value("Alaska")
                expect(page.locator("#year")).to_have_value("2026")
            page.select_option("#precinct-state-select", "Indiana")
            expect(shapes).to_have_count(83, timeout=60000)
            page.select_option("#precinct-state-select", "Alaska")
            expect(shapes).to_have_count(81, timeout=60000)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(mobile=mobile, native_ballot_checks=81, geometry_holds=321,
                all_rates_withheld=True, pooled_federal_not_allocated=True, methods_roundtrip=True,
                alternate_state_recovery=True, source_clock_preserved=True))
            context.close()
        context = browser.new_context()
        pattern = "**/participation-precincts/20261110-alaska-native-display-01/AK.geojson.gz"
        context.route(pattern, lambda route: route.fulfill(body=b"corrupted", content_type="application/gzip"))
        page = context.new_page()
        page.goto(base + "/voter-participation/?view=precincts&year=2026&state=Alaska&layer=participation",
                  wait_until="domcontentloaded")
        expect(page.locator("#coverage-note")).to_contain_text("checksum disagrees", timeout=90000)
        expect(page.locator('.geographic-detail [data-level="precinct"]')).to_have_count(0)
        context.unroute(pattern)
        page.get_by_role("button", name="Retry precinct source").click()
        expect(page.locator('.geographic-detail [data-level="precinct"]')).to_have_count(81, timeout=60000)
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_AK81_partial_native_geographic_ballot_display", base_url=base,
    cases=cases, checksum_failure_rejected_and_retried=True, valid_source_overrides=False,
    expected_geometry_sha256=hashlib.sha256(
        (ROOT / "public/participation-precincts/20261110-alaska-native-display-01/AK.geojson.gz").read_bytes()).hexdigest())
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

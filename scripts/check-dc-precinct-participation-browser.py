"""Verify every native DC precinct value on its existing official-app reference."""

import argparse
import gzip
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
source = json.loads(gzip.decompress(
    (ROOT / "data/precinct-results/20261105-dc-01/2026/DC.geojson.gz").read_bytes()))
expected = {row["properties"]["key"]: row["properties"] for row in source["features"]}
assert len(expected) == 144
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
            page.goto(base + "/voter-participation/?view=precincts&year=2026"
                      "&state=District+of+Columbia&layer=participation", wait_until="domcontentloaded")
            expect(page.locator("#title")).to_have_text("Precinct participation in District of Columbia", timeout=90000)
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#precinct-layer")).to_have_value("participation")
            shapes = page.locator('.geographic-detail [data-level="precinct"]')
            expect(shapes).to_have_count(144, timeout=60000)
            actual = shapes.evaluate_all("""els => els.map(e => ({
                key:e.dataset.geography,ballots:Number(e.dataset.count),
                registered:Number(e.dataset.registered),rate:Number(e.dataset.rate),
                year:e.dataset.year,fill:e.getAttribute('fill')
            }))""")
            assert {row["key"] for row in actual} == set(expected)
            for row in actual:
                native = expected[row["key"]]["participation"]
                assert row["year"] == "2026"
                assert row["ballots"] == native["ballots"]
                assert row["registered"] == native["registered"]
                assert abs(row["rate"] - native["reported_pct"]) < 1e-10
            assert len({row["fill"] for row in actual}) > 1
            expect(page.locator("#geography-note")).to_contain_text("2019")
            expect(page.locator("#geography-note")).to_contain_text("not newly surveyed")
            expect(page.locator("#caption").get_by_role(
                "link", name="Complete D.C. precinct counts and original sources (ZIP)")).to_have_attribute(
                    "href", "https://github.com/hanshanley/margin_of_error/releases/download/"
                    "voter-precinct-dc-maps-20261105/complete-dc-2026-precinct-maps.zip")
            first = shapes.first
            key = first.get_attribute("data-geography")
            first.focus()
            first.press("Enter")
            panel = page.locator("#substate-detail")
            native = expected[key]["participation"]
            expect(panel).to_contain_text(f'{native["ballots"]:,}')
            expect(panel).to_contain_text(f'{native["registered"]:,}')
            expect(panel).to_contain_text("Provisional election-night")
            expect(panel).to_contain_text("reference")
            expect(panel).to_contain_text(expected[key]["source_updated_at"])
            expect(page.locator("#table-head")).to_contain_text("Provisional source fraction")
            expect(page.locator("#table-head")).not_to_contain_text("Democratic")
            expect(page.locator("#table-head")).not_to_contain_text("Republican")
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-panel")).to_be_visible()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-precincts").click()
            expect(shapes).to_have_count(144, timeout=60000)
            expect(page.locator("#year")).to_have_value("2026")
            page.locator("#tab-states").click()
            page.select_option("#state-select", "District of Columbia")
            page.select_option("#year", "2026")
            page.locator("#show-matched-precinct-participation").click()
            expect(shapes).to_have_count(144, timeout=60000)
            expect(page.locator("#precinct-layer")).to_have_value("participation")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append({"mobile": mobile, "native_precincts_checked": 144,
                          "native_ballots": sum(row["ballots"] for row in actual),
                          "native_registrations": sum(row["registered"] for row in actual),
                          "source_fractions_not_final_turnout": True,
                          "official_app_reference_not_new_boundaries": True,
                          "methods_round_trip": True, "state_sidebar_navigation": True, "page_errors": errors})
            context.close()
        context = browser.new_context(viewport={"width": 1200, "height": 900})
        context.route("**/2026/DC.geojson.gz", lambda route: route.abort())
        page = context.new_page()
        page.goto(base + "/voter-participation/?view=precincts&year=2026"
                  "&state=District+of+Columbia&layer=participation", wait_until="domcontentloaded")
        retry = page.get_by_role("button", name="Retry precinct source")
        expect(retry).to_be_visible(timeout=90000)
        expect(page.locator("#selection-panel > h3")).to_have_text("District of Columbia")
        context.unroute("**/2026/DC.geojson.gz")
        retry.click()
        expect(page.locator('.geographic-detail [data-level="precinct"]')).to_have_count(144, timeout=60000)
        context.close()
    finally:
        browser.close()
proof = {"status": "PASS_DC_precinct_participation", "base_url": base,
         "failed_source_retry": True, "cases": cases}
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

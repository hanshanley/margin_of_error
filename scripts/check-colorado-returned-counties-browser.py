"""Verify all64 Colorado native returned counts on actual desktop/mobile map interactions."""

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
version = ROOT / "data/county-source-reviews/20261109-colorado-returned-01"
query = json.loads(gzip.decompress((version / "queries.json.gz").read_bytes()))
expected = {r["county_fips"]: r for r in query["counties"]}
cases = []


def choose_state(page):
    page.locator("#state-select").select_option("Colorado")
    path = page.locator('.map-feature[data-state="Colorado"]')
    path.focus()
    path.press("Enter")


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            assert response.ok
            expect(page.locator("#year")).to_have_value("2026", timeout=90000)
            expect(page.locator('.map-feature[data-state="Colorado"]')).to_have_count(1, timeout=90000)
            checks = []
            for mode in ("available", "official", "available"):
                page.locator("#mode").select_option(mode)
                choose_state(page)
                shapes = page.locator('.geographic-detail [data-level="county"]')
                expect(shapes).to_have_count(64, timeout=90000)
                expect(page.locator("#title")).to_have_text("Local participation in Colorado")
                actual = shapes.evaluate_all("els=>els.map(e=>({fips:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear}))")
                assert len({r["fips"] for r in actual}) == 64
                for row in actual:
                    assert int(row["count"]) == expected[row["fips"]]["source_count"]
                    assert row["rate"] == "" and row["year"] == "2026"
                assert shapes.evaluate_all("els=>new Set(els.map(e=>e.getAttribute('fill'))).size") > 1
                expect(page.locator("#table-head")).to_contain_text("Returned and processed")
                page.locator("#current-county-select").select_option("additional:CO:08001")
                detail = page.locator("#current-county-detail")
                expect(detail).to_contain_text("205,277")
                expect(detail).to_contain_text("Returned and processed")
                expect(detail).to_contain_text("November 5, 2026")
                expect(detail).to_contain_text("not cast")
                expect(detail.locator('a[href*="voter-county-colorado-returned-20261109-01/complete-analysis.zip"]').first).to_be_visible()
                page.locator("#tab-methods").click()
                expect(page.locator("#methods-archive")).to_be_hidden()
                page.locator("#tab-states").click()
                expect(page.locator("#mode")).to_have_value(mode)
                expect(page.locator("#state-select")).to_have_value("Colorado")
                expect(shapes).to_have_count(64, timeout=60000)
                checks.append(dict(mode=mode, all64native_values=True, no_rates=True, methods_roundtrip=True))
            response = page.request.get(base + "/participation-local/CO.json.gz")
            assert response.ok
            data = json.loads(gzip.decompress(response.body()))
            assert len(data["counties"]) == 64 and not data["precincts"]
            for row in data["counties"]:
                original = expected[row["county_fips"]]
                assert row["native_record"] == original["native_record"]
                assert row["ballots"] == original["source_count"]
                assert row["denominator"] is None and row["reported_pct"] is None
                assert row["cast_ballot_count_qualified"] is False
                assert row["unique_voter_count_qualified"] is False
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(mobile=mobile, native_checks=checks, all_original_mode_records_retained=True))
            context.close()
    finally:
        browser.close()
proof = dict(status="PASS_CO64_native_returned_counts_not_cast_or_people",
    base_url=base, cases=cases, valid_source_overrides=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

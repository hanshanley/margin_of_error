"""Verify four native Hawaii administrations without inventing separate Maui/Kalawao counts."""

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
version = ROOT / "data/county-source-reviews/20261109-hawaii-administrations-01"
grid = json.loads((version / "native-administration-grid.json").read_bytes())
expected = {r["source_administration_id"]: r for r in grid}
cases = []


def choose_state(page):
    page.locator("#state-select").select_option("Hawaii")
    path = page.locator('.map-feature[data-state="Hawaii"]')
    path.focus()
    path.press("Enter")


def verify_shapes(page):
    shapes = page.locator('.geographic-detail [data-level="county"]')
    expect(shapes).to_have_count(4, timeout=90000)
    rows = shapes.evaluate_all("els=>els.map(e=>({id:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear}))")
    assert set(r["id"] for r in rows) == set(expected)
    for row in rows:
        assert int(row["count"]) == expected[row["id"]]["native_values"]["TOTAL TURNOUT"]
        assert row["rate"] == "" and row["year"] == "2026"
    expect(page.locator('.geographic-detail [data-geography="HI-MAUI"]')).to_have_count(1)
    expect(page.locator('.geographic-detail [data-geography="15005"], .geographic-detail [data-geography="15009"]')).to_have_count(0)
    expect(page.locator("#caption")).to_contain_text("Maui includes Kalawao")
    expect(page.locator("#geography-note")).to_contain_text("4 election administrations")
    expect(page.locator("#geography-note")).to_contain_text("5 Census county components")
    expect(page.locator("#table-head")).to_contain_text("Election administration")


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
            expect(page.locator('.map-feature[data-state="Hawaii"]')).to_have_count(1, timeout=90000)
            checks = []
            for mode in ("available", "official", "available"):
                page.locator("#mode").select_option(mode)
                choose_state(page)
                verify_shapes(page)
                expect(page.locator("#title")).to_have_text("Local participation in Hawaii")
                expect(page.locator("#show-current-counties")).to_have_text("Show 4 election administrations")
                page.locator("#current-county-select").select_option("additional:HI:HI-MAUI")
                detail = page.locator("#current-county-detail")
                expect(detail).to_contain_text("50,324")
                expect(detail).to_contain_text("includes Kalawao")
                expect(detail).to_contain_text("TOTAL TURNOUT")
                expect(detail).to_contain_text("02:35:33 am")
                expect(detail.locator('a[href*="voter-county-hawaii-administrations-20261109-01/complete-analysis.zip"]').first).to_be_visible()
                page.locator("#tab-methods").click()
                expect(page.locator("#methods-archive")).to_be_hidden()
                page.locator("#tab-states").click()
                expect(page.locator("#mode")).to_have_value(mode)
                expect(page.locator("#state-select")).to_have_value("Hawaii")
                page.locator("#current-county-select").select_option("")
                verify_shapes(page)
                checks.append(dict(mode=mode, all4native_values=True, no_rates=True,
                    no_separate_Maui_Kalawao_allocation=True, methods_roundtrip=True))
            response = page.request.get(base + "/participation-local/HI.json.gz")
            assert response.ok
            data = json.loads(gzip.decompress(response.body()))
            assert len(data["counties"]) == 4 and not data["precincts"]
            for row in data["counties"]:
                original = expected[row["source_administration_id"]]
                assert row["native_record"] == original
                assert row["ballots"] == original["native_values"]["TOTAL TURNOUT"]
                assert row["county_fips"] is None
                assert row["component_county_fips"] == original["component_county_fips"]
                assert row["denominator"] is None and row["reported_pct"] is None
                assert row["cast_ballot_count_qualified"] is False
                assert row["unique_voter_count_qualified"] is False
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(mobile=mobile, native_checks=checks, all_original_records_retained=True))
            context.close()

        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        def malformed(route):
            response = route.fetch()
            body = json.loads(gzip.decompress(response.body()))
            next(r for r in body["counties"] if r["source_administration_id"] == "HI-MAUI")["component_county_fips"] = ["15009"]
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(body).encode()))
        page.route("**/participation-local/HI.json.gz", malformed)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="Hawaii"]')).to_have_count(1, timeout=90000)
        choose_state(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified election-administration reference", timeout=90000)
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(0)
        page.unroute("**/participation-local/HI.json.gz", malformed)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify_shapes(page)
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_HI4_native_administrations_no_Census_count_allocation",
    base_url=base, cases=cases, invalid_component_scope_rejected=True,
    actual_source_retry_recovered=True, valid_source_overrides=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

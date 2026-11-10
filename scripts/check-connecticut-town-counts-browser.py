"""Verify all169 native CT town cells, actual older reference labels, source failure and tab roundtrips."""

import argparse
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "data/county-source-reviews/20261110-connecticut-towns-01"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
native = json.loads(gzip.decompress((VERSION / "originals/voterTurnout_Electiondata.json.gz").read_bytes()))
expected = {f"CT-TOWN-{id.zfill(3)}": row for id, row in native.items() if id != "170"}
assert len(expected) == 169
cases = []


def open_towns(page):
    page.locator("#state-select").select_option("Connecticut")
    feature = page.locator('.map-feature[data-state="Connecticut"]')
    feature.focus()
    feature.press("Enter")


def verify(page):
    shapes = page.locator('.geographic-detail [data-level="municipality"]')
    expect(shapes).to_have_count(169, timeout=90000)
    expect(page.locator("#title")).to_have_text("Town participation in Connecticut")
    expect(page.locator("#caption")).to_contain_text("2024 contextual municipality")
    expect(page.locator("#table-head")).to_contain_text("Town")
    actual = shapes.evaluate_all("els=>els.map(e=>({id:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear}))")
    assert len({r["id"] for r in actual}) == 169
    for row in actual:
        assert int(row["count"]) == int(expected[row["id"]]["VV"])
        assert row["rate"] == "" and row["year"] == "2024"
    assert sum(int(r["count"]) for r in actual) == 1150127
    assert page.locator('.geographic-detail [data-level="county"]').count() == 0


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in [False, True]:
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            expect(page.locator('.map-feature[data-state="Connecticut"]')).to_have_count(1, timeout=90000)
            open_towns(page)
            verify(page)
            response = page.request.get(base + "/participation-local/CT.json.gz")
            assert response.ok
            data = json.loads(gzip.decompress(response.body()))
            assert len(data["counties"]) == 169 and data["precincts"] == []
            for row in data["counties"]:
                original = expected[row["source_administration_id"]]
                assert all(row["native_record"][k] == v for k, v in original.items())
                assert row["ballots"] == int(original["VV"])
                assert row["county_fips"] is None and row["source_election_id"] == "108"
                assert row["denominator"] is None and row["reported_pct"] is None
                assert row["native_election_id_qualified"] is True
                assert row["cast_ballot_count_qualified"] is False
                assert row["unique_voter_count_qualified"] is False
            assert sum(r["native_record"]["PR"] == "" for r in data["counties"]) == 13
            page.locator("#current-county-select").select_option("additional:CT:CT-TOWN-020")
            detail = page.locator("#current-county-detail")
            expect(detail).to_contain_text("Burlington")
            expect(detail).to_contain_text("Native town")
            expect(detail.locator('a[href*="voter-connecticut-native-towns-20261110-01/complete-analysis.zip"]').first).to_be_visible()
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            verify(page)
            page.locator("#mode").select_option("official")
            open_towns(page)
            verify(page)
            page.locator("#tab-precincts").click()
            expect(page.locator("#precinct-state-select")).to_have_value("Connecticut")
            expect(page.locator("#title")).to_have_text("Precinct data unavailable in Connecticut")
            page.locator("#show-state-county-data").click()
            verify(page)
            assert not errors, errors
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            cases.append(dict(mobile=mobile, native_town_counts=169, all_native_cells_preserved=True,
                native_sum_without_Total=1150127, blank_reporting_counters=13, real_boundary_year=2024,
                no_county_or_precinct_inference=True, no_rates=True, tab_and_precinct_recovery=True))
            context.close()
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        def malformed(route):
            response = route.fetch()
            data = json.loads(gzip.decompress(response.body()))
            data["counties"][0]["reference_geometry"]["boundary_year"] = 2026
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(data).encode()))
        page.route("**/participation-local/CT.json.gz", malformed)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="Connecticut"]')).to_have_count(1, timeout=90000)
        open_towns(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified Connecticut town reference", timeout=90000)
        expect(page.locator(".geographic-detail .map-feature")).to_have_count(0)
        page.unroute("**/participation-local/CT.json.gz", malformed)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify(page)
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_CT169_native_towns_separate_Total_older_context_not_precincts",
    base_url=base, cases=cases, false_reference_year_rejected=True, actual_retry_recovered=True,
    valid_source_overrides=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

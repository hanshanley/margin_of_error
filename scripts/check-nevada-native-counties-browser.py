"""Verify four actual counts, thirteen unknowns, real clicks and separate provider modes."""

import argparse
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/county-source-reviews/20261110-nevada-native-counties-01"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
data = json.loads(gzip.decompress((SOURCE / "queries.json.gz").read_bytes()))
rows = data["county_decisions"]
cases = []


def click_shape(path):
    path.scroll_into_view_if_needed()
    expression = """path => {
      const b=path.getBBox(),p=path.ownerSVGElement.createSVGPoint();
      for (const steps of [8,16,32,64])
        for (let iy=0;iy<steps;iy++) for(let ix=0;ix<steps;ix++) {
          p.x=b.x+b.width*(ix+.5)/steps;p.y=b.y+b.height*(iy+.5)/steps;
          if(path.isPointInFill(p)) {
            const q=p.matrixTransform(path.getScreenCTM());
            if(document.elementFromPoint(q.x,q.y)===path)return{x:q.x,y:q.y};
          }
        }
      return null;
    }"""
    for key in [None, "ArrowLeft", "ArrowUp", "ArrowRight", "ArrowDown"]:
        if key:
            path.page.locator("svg.turnout-map").press(key)
        point = path.evaluate(expression)
        if point is not None:
            path.page.mouse.click(point["x"], point["y"])
            return
    raise AssertionError("Native shape has no exposed interior after real panning")


def choose(page):
    page.locator("#map-reset").click()
    if page.locator('.geographic-detail [data-geography^="32"]').count():
        click_shape(page.locator('.map-feature[data-state="Iowa"]'))
        expect(page.locator('.geographic-detail [data-geography^="32"]')).to_have_count(0)
        page.locator("#map-reset").click()
    click_shape(page.locator('.map-feature[data-state="Nevada"]'))


def verify(page):
    paths = page.locator('.geographic-detail [data-level="county"]')
    expect(paths).to_have_count(17, timeout=90000)
    actual = paths.evaluate_all(
        "els=>els.map(e=>({id:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear}))")
    assert {row["id"]: int(row["count"]) if row["count"] else None for row in actual} == {
        row["county_fips"]: row["source_count"] for row in rows}
    assert all(row["rate"] == "" and row["year"] == "2026" for row in actual)
    assert sum(row["count"] == "" for row in actual) == 13
    expect(page.locator("#title")).to_have_text("Local participation in Nevada")
    expect(page.locator("#geography-note")).to_contain_text("4 available participation counts")
    expect(page.locator("#geography-note")).to_contain_text("13 source totals are withheld")
    assert page.locator('#current-county-select option:not([value=""])').count() == 17


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in [False, True]:
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            assert response.ok
            expect(page.locator('.map-feature[data-state="Nevada"]')).to_have_count(1, timeout=90000)
            choose(page)
            verify(page)
            response = page.request.get(base + "/participation-local/NV.json.gz")
            assert response.ok
            served = json.loads(gzip.decompress(response.body()))
            assert len(served["counties"]) == 17 and served["precincts"] == []
            for row in rows:
                record = next(value for value in served["counties"] if value["county_fips"] == row["county_fips"])
                page.select_option("#current-county-select", record["county_id"])
                detail = page.locator("#current-county-detail")
                if row["observed"]:
                    expect(detail).to_contain_text(f'{row["source_count"]:,}')
                    expect(detail).to_contain_text(row["native_record"]["source_clock_literal"])
                    expect(detail).to_contain_text(row["native_record"]["native_printed_pct"])
                else:
                    expect(detail).to_contain_text("County total not supplied")
                    expect(detail).to_contain_text("unknown is not zero")
                expect(detail).to_contain_text("withheld")
            for name in ["Clark", "Churchill", "White Pine", "Washoe", "Douglas"]:
                choose(page)
                row = next(row for row in rows if row["county"] == name)
                click_shape(page.locator(f'.geographic-detail [data-geography="{row["county_fips"]}"]'))
                detail = page.locator("#current-county-detail")
                expect(detail).to_contain_text(f'{row["source_count"]:,}' if row["observed"]
                                               else "County total not supplied")
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            verify(page)
            page.select_option("#mode", "official")
            verify(page)
            for mode in ["in_person_early", "mail_returned"]:
                page.select_option("#mode", mode)
                expect(page.locator("#table-head")).to_contain_text("Provider")
                paths = page.locator('.geographic-detail [data-level="county"]')
                expect(paths).to_have_count(17, timeout=90000)
                expected = {row["county_fips"]: row["ballots"] for row in served["county_frames"][mode]}
                actual = paths.evaluate_all("els=>els.map(e=>[e.dataset.geography,Number(e.dataset.count)])")
                assert dict(actual) == expected
            page.select_option("#mode", "available")
            verify(page)
            assert not errors, errors
            cases.append(dict(mobile=mobile, all17_native_map_values_and_selector_roundtrips=True,
                four_observed_thirteen_unknown=True, real_county_map_clicks=5,
                all_rates_withheld=True, distinct_native_clocks_and_printed_percentages_retained=True,
                methods_and_mode_roundtrips=True, existing_both_provider_frames_preserved=True))
            context.close()
        context = browser.new_context()
        page = context.new_page()

        def malformed(route):
            response = route.fetch()
            value = json.loads(gzip.decompress(response.body()))
            row = next(row for row in value["county_frames"]["native_county_followup"] if row["county"] == "Clark")
            row["ballots"] = 741970
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(value).encode()))

        page.route("**/participation-local/NV.json.gz", malformed)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="Nevada"]')).to_have_count(1, timeout=90000)
        choose(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified Nevada", timeout=90000)
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(0)
        page.unroute("**/participation-local/NV.json.gz", malformed)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify(page)
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_NV17_context_four_native_counts_thirteen_unknown_no_rates",
    base_url=base, cases=cases, substituted_candidate_count_rejected=True,
    actual_retry_restores_native_counties=True, valid_reference_requests_overridden=False,
    held_Washoe_count_clock_and_identity_preserved=True, new_precinct_map_claim=False,
    statewide_total_or_independently_unique_people_claim=False, nationwide_project_complete=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

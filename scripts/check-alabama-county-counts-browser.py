"""Verify all67 native county counts, real interactions and unsupported-mode recovery."""

import argparse
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/county-source-reviews/20261110-alabama-native-county-counts-02"
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
    find_point = """path => {
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
        point = path.evaluate(find_point)
        if point is not None:
            path.page.mouse.click(point["x"], point["y"])
            return
    raise AssertionError("Native shape has no exposed interior after real panning")


def choose(page):
    page.locator("#map-reset").click()
    if page.locator('.geographic-detail [data-geography^="01"]').count():
        click_shape(page.locator('.map-feature[data-state="Iowa"]'))
        expect(page.locator('.geographic-detail [data-geography^="01"]')).to_have_count(0)
        page.locator("#map-reset").click()
    click_shape(page.locator('.map-feature[data-state="Alabama"]'))


def verify(page):
    paths = page.locator('.geographic-detail [data-level="county"]')
    expect(paths).to_have_count(67, timeout=90000)
    actual = paths.evaluate_all(
        "els=>els.map(e=>({id:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear,margin:e.getAttribute('data-margin')}))")
    assert {row["id"]: int(row["count"]) for row in actual} == {row["county_fips"]: row["ballots"] for row in rows}
    assert all(row["rate"] == "" and row["year"] == "2026" and row["margin"] is None for row in actual)
    assert paths.evaluate_all("els=>new Set(els.map(e=>e.getAttribute('fill'))).size") > 1
    expect(page.locator("#title")).to_have_text("Local participation in Alabama")
    expect(page.locator("#table-head")).to_contain_text("Native Ballots Cast")
    assert page.locator('#current-county-select option:not([value=""])').count() == 67


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
            expect(page.locator('.map-feature[data-state="Alabama"]')).to_have_count(1, timeout=90000)
            choose(page)
            verify(page)
            for row in rows:
                page.select_option("#current-county-select", f'additional:AL:{row["native_county_code"]}')
                detail = page.locator("#current-county-detail")
                expect(detail).to_contain_text(f'{row["ballots"]:,}')
                expect(detail).to_contain_text(row["source_update_literal"])
                expect(detail).to_contain_text(row["native_printed_pct"])
                expect(detail).to_contain_text("withheld")
            for name in ["Jefferson", "Mobile", "Montgomery", "Autauga"]:
                choose(page)
                row = next(row for row in rows if row["county"] == name)
                click_shape(page.locator(f'.geographic-detail [data-geography="{row["county_fips"]}"]'))
                expect(page.locator("#current-county-select")).to_have_value(f'additional:AL:{row["native_county_code"]}')
                expect(page.locator("#current-county-detail")).to_contain_text(f'{row["ballots"]:,}')
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            verify(page)
            page.select_option("#mode", "official")
            verify(page)
            for mode in ["in_person_early", "mail_returned"]:
                page.select_option("#mode", mode)
                expect(page.locator('#current-county-select option:not([value=""])')).to_have_count(0, timeout=90000)
            page.select_option("#mode", "available")
            verify(page)
            response = page.request.get(base + "/participation-local/AL.json.gz")
            assert response.ok
            actual = json.loads(gzip.decompress(response.body()))
            assert len(actual["counties"]) == 67 and not actual["precincts"]
            assert all(row["source_snapshot"] == "20261110-alabama-native-county-counts-02"
                       and row["reported_pct"] is None for row in actual["counties"])
            assert not errors, errors
            cases.append(dict(mobile=mobile, all67_native_map_values_and_selector_roundtrips=True,
                real_county_map_clicks=["Jefferson", "Mobile", "Montgomery", "Autauga"],
                all_rates_withheld=True, native_clocks_and_printed_percentages_retained=True,
                source_ordinals_not_FIPS=True, methods_and_mode_roundtrips=True,
                unsupported_early_returned_not_filled_by_all_method_counts=True))
            context.close()
        context = browser.new_context()
        page = context.new_page()

        def malformed(route):
            response = route.fetch()
            value = json.loads(gzip.decompress(response.body()))
            value["county_frames"]["native_county_counts"][0]["ballots"] = 1
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(value).encode()))

        page.route("**/participation-local/AL.json.gz", malformed)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="Alabama"]')).to_have_count(1, timeout=90000)
        choose(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified Alabama", timeout=90000)
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(0)
        page.unroute("**/participation-local/AL.json.gz", malformed)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify(page)
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_AL67_native_county_counts_no_rates_or_precinct_inference",
    base_url=base, cases=cases, substituted_count_rejected=True,
    actual_retry_restores_native_counties=True, valid_reference_requests_overridden=False,
    old_county_ids_and_counts_preserved=True, new_precinct_map_claim=False,
    independently_unique_people_claim=False, nationwide_project_complete=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

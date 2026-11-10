"""Verify the actual84-county native follow-up, matching units and guarded recovery."""

import argparse
import csv
import gzip
import json
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from local_reference_staging import stage_local_minnesota_reference


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/county-source-reviews/20261110-minnesota-followup-02"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
data = json.loads(gzip.decompress((SOURCE / "queries.json.gz").read_bytes()))
new = list(csv.DictReader((SOURCE / "newly-complete-counties.csv").open()))
by_name = {row["county"]: row for row in data["complete_county_decisions"]}
cases = []
reference_staged = False


def click_shape(path):
    path.scroll_into_view_if_needed()
    find_point = """path => {
      const b=path.getBBox(),p=path.ownerSVGElement.createSVGPoint();
      for (const steps of [8,16,32,64])
        for (let iy=0;iy<steps;iy++) for(let ix=0;ix<steps;ix++) {
          const x=(ix+.5)/steps,y=(iy+.5)/steps;
          p.x=b.x+b.width*x;p.y=b.y+b.height*y;
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
    raise AssertionError("Native shape has no exposed interior after real map panning: " +
                         str(path.get_attribute("data-geography") or path.get_attribute("data-state")))


def choose(page):
    page.locator("#map-reset").click()
    if page.locator('.geographic-detail [data-geography^="27"]').count():
        click_shape(page.locator('.map-feature[data-state="Iowa"]'))
        expect(page.locator('.geographic-detail [data-geography^="27"]')).to_have_count(0)
        page.locator("#map-reset").click()
    click_shape(page.locator('.map-feature[data-state="Minnesota"]'))


def verify(page):
    paths = page.locator('.geographic-detail [data-level="county"]')
    expect(paths).to_have_count(87, timeout=90000)
    rows = paths.evaluate_all("els=>els.map(e=>({id:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear}))")
    expected = {row["county_fips"]: row["complete_total_number_voted"] for row in data["complete_county_decisions"]}
    assert {row["id"]: int(row["count"]) if row["count"] else None for row in rows} == expected
    assert sum(row["count"] != "" for row in rows) == 84
    assert sum(row["rate"] != "" for row in rows) == 71
    assert all(row["year"] == "2026" for row in rows)
    expect(page.locator("#title")).to_have_text("Local participation in Minnesota")
    assert page.locator('#current-county-select option:not([value=""])').count() == 87


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in [False, True]:
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            reference_staged = stage_local_minnesota_reference(context, base) or reference_staged
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            assert response.ok
            expect(page.locator('.map-feature[data-state="Minnesota"]')).to_have_count(1, timeout=90000)
            choose(page)
            verify(page)
            response = page.request.get(base + "/participation-local/MN.json.gz")
            assert response.ok
            actual = json.loads(gzip.decompress(response.body()))
            assert len(actual["precincts"]) == 4105
            assert sum(row["ballots"] is None for row in actual["precincts"]) == 26
            assert all(row["source_snapshot"] == "20261110-minnesota-followup-02"
                       and row["maps_approved"] is False for row in actual["precincts"])
            for native in new:
                choose(page)
                row = by_name[native["county_name"]]
                click_shape(page.locator(f'.geographic-detail [data-geography="{row["county_fips"]}"]'))
                expect(page.locator("#current-county-select")).to_have_value(
                    f'additional:MN:followup:{row["native_county_id"]}')
                expect(page.locator("#current-county-detail")).to_contain_text(
                    f'{row["complete_total_number_voted"]:,}')
                expect(page.locator("#current-county-detail")).to_contain_text("11/07/26 5:18 PM")
                print(json.dumps(dict(check="actual_new_county_click", mobile=mobile, county=row["county"])), flush=True)
            for name in ["Fillmore", "Hubbard", "Wright"]:
                row = by_name[name]
                page.select_option("#current-county-select", f'additional:MN:followup:{row["native_county_id"]}')
                expect(page.locator("#current-county-detail")).to_contain_text("not a complete county total")
                unit = next(unit for unit in data["all4105_native_precinct_decisions"]
                            if unit["county"] == name and not unit["reported_statistics"])
                page.select_option("#current-unit-select", unit["native_precinct_id"])
                expect(page.locator("#current-unit-detail")).to_contain_text("participation remains unknown")
                expect(page.locator("#current-unit-detail")).to_contain_text("not approved")
            page.locator("#tab-methods").click()
            page.locator("#tab-states").click()
            verify(page)
            for mode in ["in_person_early", "mail_returned"]:
                page.select_option("#mode", mode)
                expect(page.locator("#caption")).to_contain_text(re.compile("provider", re.I), timeout=90000)
                paths = page.locator('.geographic-detail [data-level="county"]')
                expect(paths).to_have_count(87)
                assert paths.evaluate_all("els=>els.every(e=>e.dataset.rate==='')")
                assert all(not value.startswith("additional:MN:followup:")
                           for value in page.locator("#current-county-select option").evaluate_all(
                               "els=>els.map(e=>e.value)"))
            page.select_option("#mode", "available")
            verify(page)
            page.locator("#tab-precincts").click()
            precincts = page.locator('.geographic-detail [data-level="precinct"]')
            expect(precincts).to_have_count(4105, timeout=90000)
            expect(page.locator("#title")).to_have_text("Native precinct counts in Minnesota")
            assert precincts.evaluate_all("els=>els.every(e=>e.dataset.rate==='')")
            assert precincts.evaluate_all("els=>els.filter(e=>e.dataset.count==='').length") == 26
            expect(page.locator("#coverage-note")).to_contain_text("original full native geometry")
            page.locator("#tab-states").click()
            verify(page)
            assert not errors, errors
            cases.append(dict(mobile=mobile, native_county_decisions=87, complete_counts=84,
                withheld_or_missing_fractions=16, all9_new_complete_county_map_clicks=True,
                all3_partial_counties_and_unreported_units_remain_unknown=True,
                same_snapshot4105_unit_tables=True, modes_separate=True,
                methods_and_geography_roundtrips=True, no_native_ID_as_FIPS=True,
                full_native4105_references_4079counts_26unknowns=True,
                invalid16_legacy_generalizations_not_reused=True))
            context.close()
        context = browser.new_context()
        reference_staged = stage_local_minnesota_reference(context, base) or reference_staged
        page = context.new_page()
        def malformed(route):
            response = route.fetch()
            value = json.loads(gzip.decompress(response.body()))
            value["county_frames"]["native_county_followup"][0]["ballots"] = 2852528
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(value).encode()))
        page.route("**/participation-local/MN.json.gz", malformed)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="Minnesota"]')).to_have_count(1, timeout=90000)
        choose(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified Minnesota", timeout=90000)
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(0)
        page.unroute("**/participation-local/MN.json.gz", malformed)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify(page)
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_MN84_complete3partial_4105same_snapshot_units_native_identity_modes_and_recovery",
    base_url=base, cases=cases, estimated_state_count_substitution_rejected=True,
    actual_retry_restores_native_counties=True, old75county_exports_preserved=True,
    unpublished_reference_locally_staged=reference_staged,
    certified2026_legal_precinct_claim=False, exact_statewide_count_claim=False,
    nationwide_project_complete=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

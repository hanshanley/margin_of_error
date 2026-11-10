"""Verify actual city counters, all ward rows, raw source conflicts and unknown municipal context."""

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
version = ROOT / "data/county-source-reviews/20261110-new-hampshire-cities-01"
readings = json.loads((version / "native-readings.json").read_bytes())
m = readings["manchester"]
c = readings["concord"]
manchester = sum(r["total"] for r in m["wards"])
concord = c["native_city_total_cast"]
cases = []


def choose(page):
    page.locator("#map-reset").click()
    shape = page.locator('.map-feature[data-state="New Hampshire"]')
    shape.scroll_into_view_if_needed()
    point = shape.evaluate("""path => {
      const b=path.getBBox(),p=path.ownerSVGElement.createSVGPoint();
      for (const y of [.5,.25,.75,.125,.375,.625,.875])
        for (const x of [.5,.25,.75,.125,.375,.625,.875]) {
          p.x=b.x+b.width*x;p.y=b.y+b.height*y;
          if(path.isPointInFill(p)) {
            const q=p.matrixTransform(path.getScreenCTM());
            if(document.elementFromPoint(q.x,q.y)===path)return{x:q.x,y:q.y};
          }
        }
      throw Error("No clickable New Hampshire interior");
    }""")
    page.mouse.click(point["x"], point["y"])


def verify(page):
    shapes = page.locator('.geographic-detail [data-level="municipality"]')
    expect(shapes).to_have_count(259, timeout=90000)
    actual = shapes.evaluate_all("els=>els.map(e=>({key:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear,margin:e.getAttribute('data-margin')}))")
    assert {r["key"]: int(r["count"]) for r in actual if r["count"]} == {
        "3345140": manchester, "3314200": concord}
    assert sum(r["count"] == "" for r in actual) == 257
    assert all(r["rate"] == "" and r["year"] == "2024" and r["margin"] is None for r in actual)
    expect(page.locator("#title")).to_have_text("City source counts in New Hampshire")
    expect(page.locator("#caption")).to_contain_text("257 areas remain unknown")
    expect(page.locator("#caption")).to_contain_text("22 ward rows remain in tables")
    page.select_option("#current-county-select", "additional:NH:city:3345140")
    expect(page.locator("#current-county-detail")).to_contain_text(f"{manchester:,}")
    expect(page.locator("#current-county-detail")).to_contain_text("85-ballot discrepancy")
    expect(page.locator("#current-county-detail")).to_contain_text("never added")
    units = page.locator("#current-unit-select")
    assert units.locator('option:not([value=""])').count() == 12
    units.select_option("Manchester:Ward:7")
    expect(page.locator("#current-unit-detail")).to_contain_text("2,712")
    expect(page.locator("#current-unit-detail")).to_contain_text("not approved as precinct geography")
    page.select_option("#current-county-select", "additional:NH:city:3314200")
    expect(page.locator("#current-county-detail")).to_contain_text("19,234")
    expect(page.locator("#current-county-detail")).to_contain_text("25879")
    expect(page.locator("#current-county-detail")).to_contain_text("27340")
    expect(page.locator("#current-county-detail")).to_contain_text("74.32%")
    expect(page.locator("#current-county-detail")).to_contain_text("Analysis fraction withheld")
    assert page.locator('#current-unit-select option:not([value=""])').count() == 10
    page.select_option("#current-unit-select", "Concord:Ward:1")
    expect(page.locator("#current-unit-detail")).to_contain_text("1,985")
    expect(page.locator("#current-unit-detail")).to_contain_text("school-district source cells")


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
            expect(page.locator('.map-feature[data-state="New Hampshire"]')).to_have_count(1, timeout=90000)
            choose(page)
            verify(page)
            api = page.request.get(base + "/participation-local/NH.json.gz")
            assert api.ok
            data = json.loads(gzip.decompress(api.body()))
            assert len(data["counties"]) == 2 and len(data["precincts"]) == 22
            assert all(r["denominator"] is None and r["reported_pct"] is None
                       for r in [*data["counties"], *data["precincts"]])
            assert all(not r["maps_approved"] for r in data["precincts"])
            by_ward = {r["unit_key"]: r for r in data["precincts"]}
            for native in m["wards"]:
                row = by_ward[f'Manchester:Ward:{native["ward"]}']
                assert row["native_record"] == native and row["ballots"] == native["total"]
            unknown = page.locator('.geographic-detail [data-level="municipality"][data-count=""]').first
            unknown.focus()
            unknown.press("Enter")
            expect(page.locator("#current-county-detail")).to_contain_text("unknown, not zero")
            expect(page.locator("#current-county-select")).to_have_value("")
            page.select_option("#mode", "official")
            verify(page)
            for mode in ("in_person_early", "mail_returned"):
                page.select_option("#mode", mode)
                expect(page.locator("#mode")).to_have_value(mode)
                expect(page.locator('.geographic-detail [data-level="municipality"][data-count]:not([data-count=""])')).to_have_count(0)
            page.select_option("#mode", "available")
            verify(page)
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-panel")).to_be_visible()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            expect(page.locator("#state-select")).to_have_value("New Hampshire")
            expect(page.locator("#year")).to_have_value("2026")
            verify(page)
            page.locator("#tab-precincts").click()
            expect(page.locator("#precinct-state-select")).to_have_value("New Hampshire")
            expect(page.locator('.geographic-detail [data-level="precinct"]')).to_have_count(0)
            expect(page.locator("#title")).to_have_text("Precinct data unavailable in New Hampshire")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(mobile=mobile, native_city_counts=2, native_ward_rows=22,
                full_context_areas=259, unknown_not_zero=257, source_conflicts_retained=True,
                federal_only_not_added=True, no_rates=True, no_old_shapes_as_2026_wards=True,
                native_registers_and_percent_separate=True, unsupported_modes_not_substituted=True,
                methods_roundtrip=True))
            context.close()
        context = browser.new_context()
        page = context.new_page()
        def malformed(route):
            response = route.fetch()
            data = json.loads(gzip.decompress(response.body()))
            for row in data["counties"]:
                row["reference_geometry"]["boundary_year"] = 2026
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(data).encode()))
        page.route("**/participation-local/NH.json.gz", malformed)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="New Hampshire"]')).to_have_count(1, timeout=90000)
        choose(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified New Hampshire native city", timeout=90000)
        expect(page.locator(".geographic-detail .map-feature")).to_have_count(0)
        page.unroute("**/participation-local/NH.json.gz", malformed)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify(page)
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_NH_two_native_city_sources_22ward_rows_on2024_context_NOT_county_or_precinct_totals",
    base_url=base, cases=cases, false_reference_rejected=True, actual_retry_restores_selectors=True,
    valid_source_overrides=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

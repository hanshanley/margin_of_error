"""Verify Indiana's native county counts, Monroe units, literal measures and source recovery."""

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
assert not args.proof.exists()
base = args.base_url.rstrip("/")
version = ROOT / "data/county-source-reviews/20261109-indiana-voter-statistics-01"
native = json.loads(gzip.decompress((version / "original-statewide-turnout.json.gz").read_bytes()))
roster = json.loads(gzip.decompress((version / "native-county-identity-control.json.gz").read_bytes()))
parents = {row["county_fips"]: row for row in json.loads((version / "independent-county-parents.json").read_bytes())}
statistics = {row["County"].lower(): row for row in native["root"]["CountyTurnout"][:-1]}
expected = {}
for identity in roster["rows"]:
    row = statistics[identity["native_county_name"].lower()]
    fips = identity["county_fips"]
    expected[fips] = parents[fips]["count"] if fips in parents else (
        row["VotersVoting"] if row["VotersVoting"] >= sum(identity["candidate_counts"]) else None)
source_units = {str(row["attributes"]["Precinct_ID"]): row["attributes"] for row in
    json.loads((version / "monroe-original-counts.json").read_bytes())["features"]}
mapped = json.loads(gzip.decompress(
    (ROOT / "public/participation-precincts/20261109-indiana-monroe-01/IN.geojson.gz").read_bytes()))
mapped_units = {row["properties"]["key"]: row["properties"] for row in mapped["features"]}
download = json.loads((version / "inputs.json").read_bytes())["complete_download_url"]
cases = []


def click_state(page):
    shape = page.locator('.map-feature[data-state="Indiana"]')
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
      throw Error("No clickable Indiana interior");
    }""")
    page.mouse.click(point["x"], point["y"])


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
            expect(page.locator('.map-feature[data-state="Indiana"]')).to_have_count(1, timeout=90000)
            click_state(page)
            expect(page.locator("#title")).to_have_text("Local participation in Indiana", timeout=90000)
            shapes = page.locator('.geographic-detail [data-level="county"]')
            expect(shapes).to_have_count(92, timeout=60000)
            actual = shapes.evaluate_all("els=>els.map(e=>({key:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear}))")
            assert set(row["key"] for row in actual) == set(expected)
            for row in actual:
                assert (int(row["count"]) if row["count"] else None) == expected[row["key"]]
                assert row["rate"] == "" and row["year"] == "2026"
            expect(page.locator("#table-head")).to_contain_text("Source participation count")
            expect(page.locator("#geography-note")).to_contain_text("75")
            for fips in ("18057", "18013", "18017", "18105"):
                page.locator("#current-county-select").select_option(f"additional:IN:{fips}")
                detail = page.locator("#current-county-detail")
                if fips == "18013":
                    expect(detail).to_contain_text("not zero turnout")
                else:
                    expect(detail).to_contain_text(f"{expected[fips]:,}")
                if fips == "18057":
                    expect(detail).to_contain_text("Native Voters Voting")
                    expect(detail).to_contain_text("15:03:29.353")
                if fips == "18017":
                    expect(detail).to_contain_text("not cast ballots")
            units = page.locator("#current-unit-select")
            assert units.locator('option:not([value=""])').count() == 103
            units.select_option("51")
            expect(page.locator("#current-unit-detail")).to_contain_text("241")
            expect(page.locator("#current-unit-detail")).to_contain_text("carrier")
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-panel")).to_be_visible()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            expect(shapes).to_have_count(92, timeout=60000)
            expect(page.locator("#state-select")).to_have_value("Indiana")
            page.locator("#tab-precincts").click()
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#precinct-state-select")).to_have_value("Indiana")
            expect(page.locator("#precinct-layer")).to_have_value("participation")
            precincts = page.locator('.geographic-detail [data-level="precinct"]')
            expect(precincts).to_have_count(83, timeout=90000)
            actual = precincts.evaluate_all("els=>els.map(e=>({key:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,margin:e.getAttribute('data-margin')}))")
            assert set(row["key"] for row in actual) == set(mapped_units)
            for row in actual:
                assert int(row["count"]) == source_units[mapped_units[row["key"]]["unit_key"]]["Ballots_Cast"]
                assert row["rate"] == "" and row["margin"] is None
            assert precincts.evaluate_all("els=>new Set(els.map(e=>e.getAttribute('fill'))).size") > 1
            expect(page.locator("#coverage-note")).to_contain_text("103")
            expect(page.locator("#coverage-note")).to_contain_text("Monroe")
            chosen = next(iter(mapped_units))
            shape = page.locator(f'[data-level="precinct"][data-geography="{chosen}"]')
            shape.focus()
            shape.press("Enter")
            expect(page.locator("#substate-detail")).to_contain_text("Partially Reporting")
            expect(page.locator("#substate-detail")).to_contain_text("clock and timezone not supplied")
            expect(page.locator("#caption a")).to_have_attribute("href", download)
            response = page.request.get(base + "/participation-local/IN.json.gz")
            assert response.ok
            data = json.loads(gzip.decompress(response.body()))
            assert len(data["counties"]) == 92 and len(data["precincts"]) == 103
            for row in data["counties"]:
                fips = row["county_fips"]
                assert row["ballots"] == expected[fips]
                assert row["denominator"] is None and row["reported_pct"] is None
                assert row["statewide_statistics_native_record"] == statistics[
                    row["statewide_statistics_native_record"]["County"].lower()]
            for row in data["precincts"]:
                assert row["native_record"] == source_units[row["unit_key"]]
                assert row["ballots"] == source_units[row["unit_key"]]["Ballots_Cast"]
                assert row["denominator"] is None and row["reported_pct"] is None
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(mobile=mobile, native_county_queries=92, available=75, held=17,
                native_unit_records=103, mapped_units=83, real_default_click=True,
                missing_not_zero=True, literal_measures=True, source_clocks=True,
                methods_roundtrip=True, all_rates_withheld=True))
            context.close()
        context = browser.new_context()
        pattern = "**/participation-precincts/20261109-indiana-monroe-01/IN.geojson.gz"
        context.route(pattern, lambda route: route.fulfill(body=b"corrupted", content_type="application/gzip"))
        page = context.new_page()
        page.goto(base + "/voter-participation/?view=precincts&year=2026&state=Indiana&layer=participation",
                  wait_until="domcontentloaded")
        expect(page.locator("#coverage-note")).to_contain_text("checksum disagrees", timeout=90000)
        expect(page.locator('.geographic-detail [data-level="precinct"]')).to_have_count(0)
        context.unroute(pattern)
        page.get_by_role("button", name="Retry precinct source").click()
        expect(page.locator('.geographic-detail [data-level="precinct"]')).to_have_count(83, timeout=60000)
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_IN_native_county_and_Monroe_counts", base_url=base,
    cases=cases, checksum_failure_rejected_and_retried=True, valid_source_overrides=False,
    expected_source_geometry_sha256=hashlib.sha256(
        (ROOT / "public/participation-precincts/20261109-indiana-monroe-01/IN.geojson.gz").read_bytes()).hexdigest())
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

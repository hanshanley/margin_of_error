"""Check all Maryland source cards, exact labels, state clicks and recoverable failures."""

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
version = ROOT / "data/county-source-reviews/20261109-maryland-cards-01"
queries = json.loads(gzip.decompress((version / "queries.json.gz").read_bytes()))
expected = {row["county_fips"]: row for row in queries["county_counts"]}
archive = ROOT / "public/participation-county-cards/20261109-01/complete-analysis.zip"
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
            response = page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            assert response.ok
            expect(page.locator("#year")).to_have_value("2026", timeout=90000)
            state = page.locator('.map-feature[data-state="Maryland"]')
            expect(state).to_have_count(1, timeout=90000)
            state.scroll_into_view_if_needed()
            point = state.evaluate("""path => {
                const b=path.getBBox(),p=path.ownerSVGElement.createSVGPoint();
                for (const y of [.5,.25,.75,.125,.375,.625,.875])
                  for (const x of [.5,.25,.75,.125,.375,.625,.875]) {
                    p.x=b.x+b.width*x;p.y=b.y+b.height*y;
                    if(path.isPointInFill(p)) {
                      const q=p.matrixTransform(path.getScreenCTM());
                      if(document.elementFromPoint(q.x,q.y)===path)return{x:q.x,y:q.y};
                    }
                  }
                throw Error("No clickable Maryland interior");
            }""")
            page.mouse.click(point["x"], point["y"])
            expect(page.locator("#title")).to_have_text("Local participation in Maryland", timeout=90000)
            shapes = page.locator('.geographic-detail [data-level="county"]')
            expect(shapes).to_have_count(24, timeout=60000)
            actual = shapes.evaluate_all("""els => els.map(e=>({
                key:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,
                reference:e.dataset.referenceYear,title:e.getAttribute('aria-label')
            }))""")
            assert set(row["key"] for row in actual) == set(expected)
            for row in actual:
                assert int(row["count"]) == expected[row["key"]]["cards_cast"]
                assert row["rate"] == "" and row["reference"] == "2026"
                assert "Cards Cast" in row["title"] and "not unique voters" in row["title"]
            expect(page.locator("#title")).not_to_contain_text("contest")
            expect(page.locator("#geography-note")).to_contain_text("24 county observations")
            for fips in ("24510", "24005", "24037"):
                shape = page.locator(f'[data-level="county"][data-geography="{fips}"]')
                shape.focus()
                shape.press("Enter")
                expect(page.locator("#current-county-select")).to_have_value(f"additional:MD:{fips}")
                detail = page.locator("#current-county-detail")
                expect(detail).to_contain_text(f'{expected[fips]["cards_cast"]:,}')
                expect(detail).to_contain_text("Cards Cast")
                expect(detail).to_contain_text("not unique voters")
                expect(detail).to_contain_text("MIB2")
                expect(detail).to_contain_text("11/8/2026 7:44 pm")
                expect(page.locator("#current-unit-select")).to_have_count(0)
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-panel")).to_be_visible()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            expect(shapes).to_have_count(24, timeout=60000)
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#state-select")).to_have_value("Maryland")
            response = page.request.get(base + "/participation-local/MD.json.gz")
            assert response.ok
            data = json.loads(gzip.decompress(response.body()))
            assert len(data["counties"]) == 24 and not data["precincts"]
            for row in data["counties"]:
                assert row["native_record"] == expected[row["county_fips"]]["native_record"]
                assert row["denominator"] is None and row["reported_pct"] is None
                assert row["cast_ballot_count_qualified"] is False
                assert row["unique_voter_count_qualified"] is False
            response = page.request.get(base + "/participation-county-cards/20261109-01/complete-analysis.zip")
            assert response.ok and response.body() == archive.read_bytes()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(mobile=mobile, native_county_cards=24, real_default_state_click=True,
                all_rates_withheld=True, city_county_distinct=True, explicit_saint_marys_alias=True,
                source_clock_and_measure_retained=True))
            context.close()
        context = browser.new_context()
        pattern = "**/participation-local/MD.json.gz"

        def incomplete(route):
            response = route.fetch()
            data = json.loads(gzip.decompress(response.body()))
            data["counties"].pop()
            route.fulfill(body=gzip.compress(json.dumps(data).encode(), mtime=0),
                          content_type="application/gzip")

        context.route(pattern, incomplete)
        page = context.new_page()
        page.goto(base + "/voter-participation/?view=states&year=2026&state=Maryland&map-level=county",
                  wait_until="domcontentloaded")
        expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
        page.locator("#state-select").select_option("Maryland")
        expect(page.locator("#geography-note")).to_contain_text("inventory disagrees", timeout=90000)
        assert page.locator('.geographic-detail [data-level="county"]').count() == 0
        context.unroute(pattern)
        page.get_by_role("button", name="Retry geographic detail").click()
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(24, timeout=60000)
        context.close()
        context = browser.new_context()
        reference = next(iter(expected.values()))["reference_geometry"]["url"]
        context.route(reference, lambda route: route.fulfill(body=b"corrupted", content_type="application/gzip"))
        page = context.new_page()
        page.goto(base + "/voter-participation/?view=states&year=2026&state=Maryland&map-level=county",
                  wait_until="domcontentloaded")
        expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
        page.locator("#state-select").select_option("Maryland")
        expect(page.locator("#geography-note")).to_contain_text("checksum disagrees", timeout=90000)
        context.unroute(reference)
        page.get_by_role("button", name="Retry geographic detail").click()
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(24, timeout=60000)
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_MD_native_cards_not_unique_voters", base_url=base, cases=cases,
    incomplete_inventory_retry=True, corrupted_reference_retry=True,
    complete_query_download_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

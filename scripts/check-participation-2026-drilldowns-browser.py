"""Exercise exact-year 2026 geographic coverage and real supported counts."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
if args.proof.exists():
    raise ValueError("Refuse to replace an existing proof")
base = args.base_url.rstrip("/") + "/voter-participation/"
results = []


def ready(page):
    expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)


def state_click(page, name):
    page.locator("#map-reset").click()
    path = page.locator(f'.map-feature[data-state="{name}"]')
    path.scroll_into_view_if_needed()
    point = path.evaluate("""path => {
      const b=path.getBBox(),p=path.ownerSVGElement.createSVGPoint();
      for (const y of [.5,.25,.75,.125,.375,.625,.875])
        for (const x of [.5,.25,.75,.125,.375,.625,.875]) {
          p.x=b.x+b.width*x;p.y=b.y+b.height*y;
          if(path.isPointInFill(p)) {
            const q=p.matrixTransform(path.getScreenCTM());
            if(document.elementFromPoint(q.x,q.y)===path)return{x:q.x,y:q.y};
          }
        }
      throw Error("No clickable interior point");
    }""")
    page.mouse.click(point["x"], point["y"])


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base + "?view=states&year=2026&state=Texas&map-level=county",
                  wait_until="domcontentloaded")
        script = page.request.get(args.base_url.rstrip("/") + "/scripts/participation-explorer.js")
        assert script.ok
        script_sha256 = hashlib.sha256(script.body()).hexdigest()
        ready(page)
        for name, count, native in (("California", 58, True), ("Florida", 67, True),
                                    ("Texas", 254, False), ("New York", 62, False)):
            state_click(page, name)
            shapes = page.locator('.geographic-detail [data-level="county"]')
            expect(shapes).to_have_count(count, timeout=60000)
            if native:
                expect(page.locator('.geographic-detail [data-count]:not([data-count=""])')).to_have_count(count)
            else:
                expect(page.locator("#title")).to_have_text(f"County contest counts in {name}")
                assert shapes.evaluate_all("els=>new Set(els.map(e=>e.getAttribute('fill'))).size") > 1
                assert shapes.evaluate_all("els=>els.every(e=>!e.hasAttribute('data-rate'))")
                assert shapes.evaluate_all("els=>els.every(e=>!e.hasAttribute('data-margin'))")
                expect(page.locator("#table-head")).not_to_contain_text("Democratic")
                shapes.first.focus()
                shapes.first.press("Enter")
                expect(page.locator("#substate-detail")).to_contain_text("not ballots cast or turnout")
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#selection-panel > h3")).to_have_text(name)
            results.append({"case": "actual_state_click", "state": name, "county_shapes": count,
                            "native_participation": native, "no_invented_rates": True})

        county_audit = []
        names = page.locator("#state-select option").evaluate_all("els=>els.map(e=>e.value)")
        assert len(names) == 51
        for name in names:
            page.select_option("#state-select", name)
            page.wait_for_timeout(150)
            page.wait_for_function(
                """() => !document.querySelector('#geography-note').textContent.startsWith('Loading ')""",
                timeout=90000)
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#selection-panel > h3")).to_have_text(name)
            expect(page.locator("svg.turnout-map")).to_be_visible()
            expect(page.locator("#visualization")).not_to_contain_text("Data unavailable.")
            shapes = page.locator(".geographic-detail .map-feature")
            if not shapes.count():
                expect(page.locator("#coverage-note")).to_contain_text("No loaded 2026 county")
            county_audit.append({"state": name, "shapes": shapes.count(),
                                 "coverage": page.locator("#geography-note").text_content()})
        results.append({"case": "all_state_county_drilldowns", "states": county_audit})

        page.select_option("#state-select", "Texas")
        page.locator("#tab-precincts").click()
        ready(page)
        expect(page.locator("#precinct-state-select")).to_have_value("Texas")
        expect(page.locator("#year")).to_have_value("2026")
        expect(page.locator("#precinct-layer")).to_have_value("participation")
        expect(page.locator("#title")).to_have_text("Precinct data unavailable in Texas")
        expect(page.locator("#substate-detail")).to_contain_text("statewide VEP turnout")
        assert page.locator(".geographic-detail .map-feature").count() == 0
        states = page.locator("#precinct-state-select option").evaluate_all("els=>els.map(e=>e.value)")
        assert len(states) == 51, len(states)
        for name in states:
            page.select_option("#precinct-state-select", name)
            ready(page)
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#precinct-layer")).to_have_value("participation")
            expect(page.locator("#selection-panel > h3")).to_have_text(name)
            expect(page.locator("#visualization")).not_to_contain_text("Data unavailable.")
        results.append({"case": "all_state_precinct_selections", "states": len(states),
                        "retained_2026": True, "no_silent_metric_switch": True})

        for name, count in (("Idaho", 448), ("North Dakota", 338), ("Minnesota", 4105),
                            ("Michigan", 58), ("New Mexico", 2177), ("District of Columbia", 144),
                            ("Virginia", 710)):
            page.select_option("#precinct-state-select", name)
            shapes = page.locator('.geographic-detail [data-level="precinct"]')
            expect(shapes).to_have_count(count, timeout=90000)
            expect(page.locator("#year")).to_have_value("2026")
            assert shapes.evaluate_all("els=>els.every(e=>!e.hasAttribute('data-margin'))")
            if name in ("North Dakota", "Michigan", "Virginia"):
                assert shapes.evaluate_all("els=>new Set(els.map(e=>e.getAttribute('fill'))).size") > 1
                assert shapes.evaluate_all("els=>els.every(e=>e.dataset.rate==='')")
            results.append({"case": "supported_2026_precincts", "state": name, "shapes": count})

        page.select_option("#precinct-state-select", "Texas")
        page.locator("#show-state-county-data").click()
        expect(page.locator("#year")).to_have_value("2026")
        expect(page.locator("#state-select")).to_have_value("Texas")
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(254, timeout=60000)
        for _ in range(2):
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-panel")).to_be_visible()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-precincts").click()
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#precinct-state-select")).to_have_value("Texas")
            page.locator("#tab-states").click()
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#state-select")).to_have_value("Texas")
        assert not errors, errors
        results.append({"case": "state_county_recovery_and_tab_roundtrips", "page_errors": errors})
        context.close()

        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            page.goto(base + "?view=precincts&year=2026&state=Texas&layer=participation",
                      wait_until="domcontentloaded")
            ready(page)
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#title")).to_have_text("Precinct data unavailable in Texas")
            page.locator("#substate-detail details > summary").click()
            page.locator('[data-precinct-coverage-state="ND"]').click()
            expect(page.locator('.geographic-detail [data-level="precinct"]')).to_have_count(338, timeout=60000)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            results.append({"case": "coverage_navigation", "mobile": mobile, "no_overflow": True})
            context.close()

        context = browser.new_context(viewport={"width": 1200, "height": 900})
        context.route("**/2026/ND.geojson.gz", lambda route: route.abort())
        page = context.new_page()
        page.goto(base + "?view=precincts&year=2026&state=North+Dakota&layer=participation",
                  wait_until="domcontentloaded")
        ready(page)
        retry = page.get_by_role("button", name="Retry precinct source")
        expect(retry).to_be_visible(timeout=60000)
        expect(page.locator("#selection-panel > h3")).to_have_text("North Dakota")
        context.unroute("**/2026/ND.geojson.gz")
        retry.click()
        expect(page.locator('.geographic-detail [data-level="precinct"]')).to_have_count(338, timeout=60000)
        results.append({"case": "failed_source_retry", "context_retained": True, "recovered": True})
        context.close()

        pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
        index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
        pattern = index["coverage"]["TX"]["file"]
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        context.route(pattern, lambda route: route.abort())
        page = context.new_page()
        page.goto(base + "?view=states&year=2026&state=Texas&map-level=county",
                  wait_until="domcontentloaded")
        ready(page)
        state_click(page, "Texas")
        retry = page.get_by_role("button", name="Retry geographic detail")
        expect(retry).to_be_visible(timeout=60000)
        expect(page.locator("#selection-panel > h3")).to_have_text("Texas")
        context.unroute(pattern)
        retry.click()
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(254, timeout=60000)
        results.append({"case": "failed_county_retry", "context_retained": True, "recovered": True})
        context.close()
    finally:
        browser.close()

proof = {"status": "PASS_2026_geographic_drilldowns", "base_url": args.base_url,
         "script_sha256": script_sha256,
         "cases": results}
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

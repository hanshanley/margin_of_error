"""Verify same-layer borders, primary modeled swings and useful precinct controls."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4398")
parser.add_argument("--proof", type=Path, required=True)
parser.add_argument("--smoke", action="store_true")
args = parser.parse_args()
pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
codes = sorted(index["coverage"])
state_names = {feature["properties"]["STUSAB"]: feature["properties"]["NAME"] for feature in
    json.loads((ROOT / "public/voter-participation/data/states.geojson").read_bytes())["features"]}
cases = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in (1440, 390):
            page = browser.new_page(viewport=dict(width=width, height=1000))
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(args.base_url.rstrip("/") +
                "/voter-participation/?view=states&year=2026&state=Florida&map-color=margin&map-level=county",
                wait_until="domcontentloaded", timeout=90000)
            assert response.ok
            expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
            selected_codes = ["FL"] if args.smoke else codes if width == 1440 else [
                c for c in ("FL", "CA", "TX", "MN", "VA", "HI") if c in codes]
            for code in selected_codes:
                state_name = state_names[code]
                page.locator("#state-select").select_option(state_name)
                outline = page.locator(f'.reference-selection-outline[data-state-code="{code}"]')
                expect(outline).to_have_count(1, timeout=90000)
                page.wait_for_function("""code => {
                    const svg = document.querySelector('#visualization svg');
                    const border = svg?.querySelector(`.reference-selection-outline[data-state-code="${code}"]`);
                    const layer = [...(svg?.querySelectorAll('.geographic-detail path[data-level="county"]') || [])];
                    return border && layer.length && layer.every(p =>
                      [...border.querySelectorAll('mask path')].some(m => m.getAttribute('d') === p.getAttribute('d')));
                }""", arg=code, timeout=90000)
                result = outline.evaluate("""node => {
                    const mask = [...node.querySelectorAll('mask path')].map(p => p.getAttribute('d'));
                    const stroke = [...node.querySelectorAll('g[mask] path')].map(p => p.getAttribute('d'));
                    return {features:mask.length, exact:JSON.stringify(mask) === JSON.stringify(stroke)};
                }""")
                assert result["exact"] and result["features"] > 0
                assert page.locator('path.state-selection-outline').get_attribute("d") == ""
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                cases.append(dict(width=width, state=code, exact_county_footprint_border=result["features"]))
                if width == 1440 and code == "FL":
                    page.locator("#visualization").screenshot(path=str(args.proof.with_suffix(".florida.png")))
            page.locator("#tab-effects").click()
            expect(page.locator("#swing-panel")).to_be_visible()
            expect(page.locator("#historical-explorer")).to_be_hidden()
            expect(page.locator("#participation-return-drivers .driver-row")).to_have_count(50)
            assert page.locator("#participation-research").get_attribute("open") is None
            page.goto(args.base_url.rstrip("/") + "/voter-participation/?view=precincts&year=2026&state=Minnesota",
                wait_until="domcontentloaded", timeout=90000)
            expect(page.locator("#precinct-source-summary")).to_contain_text("4,105 mapped source units", timeout=90000)
            expect(page.locator("#precinct-search")).to_be_visible()
            expect(page.locator("#precinct-county")).to_be_visible()
            expect(page.locator("#visualization path[data-level=county]")).to_have_count(0)
            zero = page.locator('#visualization path[data-count="0"]').first
            key = zero.get_attribute("data-geography")
            suggestion = page.locator("#precinct-options option").evaluate_all(
                "(nodes,key) => nodes.find(n=>n.value.endsWith(' · '+key))?.value", key)
            assert suggestion
            page.locator("#precinct-search").fill(suggestion)
            page.locator("#precinct-search").dispatch_event("change")
            expect(page.locator("#substate-detail .selection-rate")).to_have_text("0")
            expect(page.locator("#substate-detail")).to_contain_text("Total Number Voted")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            cases.append(dict(width=width, primary_swing_tab=True, native_4105_precincts=True,
                real_zero_selected_by_search=True, no_county_substitution=True))
            page.goto(args.base_url.rstrip("/") +
                "/voter-participation/?view=precincts&year=2026&state=Rhode%20Island",
                wait_until="domcontentloaded", timeout=90000)
            expect(page.locator("#title")).to_contain_text("unavailable", timeout=90000)
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#precinct-county")).to_contain_text("No mapped precincts")
            page.goto(args.base_url.rstrip("/") +
                "/voter-participation/?view=precincts&year=2024&state=North%20Carolina",
                wait_until="domcontentloaded", timeout=90000)
            expect(page.locator("#precinct-source-summary")).to_contain_text("North Carolina voter-history participants", timeout=90000)
            cases.append(dict(width=width, unsupported_2026_not_replaced_by_2024=True,
                historical_precinct_summary_not_stale=True))
            assert not errors, errors
            page.close()
    finally:
        browser.close()
proof = dict(status="PASS_same_layer_county_borders_primary_swings_and_precinct_search",
    base_url=args.base_url, county_states=len(codes), cases=cases)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

"""Verify participation tabs preserve view-specific controls and keep Methods usable."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def values(page, selector):
    return page.locator(f"{selector} option").evaluate_all(
        "options => options.map(option => option.value)")


def choose_group(page):
    choices = values(page, "#group")
    assert choices
    choice = next((value for value in reversed(choices)
                   if value not in {"All", "All groups", ""}), choices[0])
    page.select_option("#group", choice)
    return choice


def select_tab(page, view):
    page.locator(f"#tab-{view}").click()
    expect(page.locator(f"#tab-{view}")).to_have_attribute("aria-selected", "true")


def snapshot(page, ids):
    return {element_id: page.locator(f"#{element_id}").input_value() for element_id in ids}


def check_round_trip(page, mode, screenshots):
    expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
    states = snapshot(page, ["year", "mode", "map-color", "map-level", "state-select"])
    assert states == {
        "year": "2026", "mode": "official", "map-color": "margin",
        "map-level": "county", "state-select": "Texas",
    }

    select_tab(page, "national")
    page.select_option("#year", "2024")
    page.locator(".explorer-options > summary").click()
    page.select_option("#basis", "vap")
    page.select_option("#dimension", "education")
    demographic_group = choose_group(page)
    demographics = snapshot(page, ["year", "basis", "dimension", "group"])
    expect(page.locator("#visualization")).not_to_contain_text("Data unavailable")

    select_tab(page, "precincts")
    expect(page.locator("#precinct-state-select")).to_have_value("Texas")
    expect(page.locator("#year")).to_have_value("2024")
    expect(page.locator("#precinct-layer")).to_have_value("results")
    expect(page.locator("#title")).to_have_text("Precinct election results in Texas", timeout=90000)
    page.wait_for_function(
        "document.querySelectorAll('.geographic-detail [data-color-level=\"precinct\"]').length > 9000",
        timeout=90000)
    assert page.locator('.geographic-detail [data-color-level="precinct"]').count() > 9000
    texas_results = snapshot(page, ["precinct-state-select", "year", "precinct-layer"])

    page.select_option("#precinct-state-select", "North Carolina")
    page.select_option("#year", "2022")
    expect(page.locator("#precinct-layer")).to_have_value("participation")
    page.select_option("#dimension", "race")
    precinct_group = choose_group(page)
    expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
    county_values = values(page, "#precinct-county")
    county = "WAKE" if "WAKE" in county_values else next(value for value in county_values if value)
    page.select_option("#precinct-county", county)
    expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
    precincts = snapshot(page, ["precinct-state-select", "year", "precinct-layer",
                                "dimension", "group", "precinct-county"])

    select_tab(page, "methods")
    expect(page.locator("#historical-explorer")).to_be_hidden()
    expect(page.locator("#methods-panel")).to_be_visible()
    expect(page.locator(".methods-guide a")).to_have_count(4)
    expect(page.locator("#definitions")).not_to_have_attribute("open", "")
    expect(page.locator("#updates-panel")).not_to_have_attribute("open", "")
    expect(page.locator("#participation-model")).not_to_have_attribute("open", "")
    expect(page.locator(".download-ledger")).not_to_have_attribute("open", "")
    expect(page.locator("#participation-research")).not_to_have_attribute("open", "")
    expect(page.locator("#downloads a[download]")).to_have_count(
        page.locator("#downloads a[download]").count())
    assert page.locator("#downloads a[download]").count() >= 900

    for _ in range(2):
        select_tab(page, "states")
        expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
        assert snapshot(page, states.keys()) == states
        select_tab(page, "national")
        assert snapshot(page, demographics.keys()) == demographics
        select_tab(page, "precincts")
        expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
        assert snapshot(page, precincts.keys()) == precincts
        select_tab(page, "methods")
        expect(page.locator("#methods-panel")).to_be_visible()

    select_tab(page, "national")
    page.select_option("#year", "2026")
    page.select_option("#current-state-select", "GA")
    page.select_option("#mode", "in_person_early")
    page.select_option("#dimension", "race")
    current_group = choose_group(page)
    current = snapshot(page, ["year", "current-state-select", "mode", "dimension", "group"])
    expect(page.locator("#visualization")).not_to_contain_text("Data unavailable")
    select_tab(page, "states")
    assert snapshot(page, states.keys()) == states
    select_tab(page, "national")
    assert snapshot(page, current.keys()) == current

    select_tab(page, "precincts")
    page.select_option("#precinct-state-select", "Minnesota")
    page.select_option("#year", "2026")
    page.select_option("#precinct-layer", "participation")
    expect(page.locator("#title")).to_have_text("Precinct participation in Minnesota", timeout=90000)
    page.wait_for_function(
        "document.querySelectorAll('.geographic-detail [data-level=\"precinct\"][data-count]').length > 4000",
        timeout=90000)
    native_shapes = page.locator('.geographic-detail [data-level="precinct"][data-count]')
    assert native_shapes.count() > 4000
    expect(page.locator("#coverage-note")).to_contain_text("approved reporting-unit joins")
    current_precincts = snapshot(page, ["precinct-state-select", "year", "precinct-layer"])
    select_tab(page, "states")
    assert snapshot(page, states.keys()) == states
    select_tab(page, "precincts")
    assert snapshot(page, current_precincts.keys()) == current_precincts

    page.locator("#tab-precincts").focus()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#tab-methods")).to_be_focused()
    expect(page.locator("#tab-methods")).to_have_attribute("aria-selected", "true")
    page.keyboard.press("End")
    expect(page.locator("#tab-methods")).to_be_focused()
    expect(page.locator("#methods-panel")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if screenshots:
        page.screenshot(path=str(screenshots / f"tab-roundtrip-{mode}.png"), full_page=False)
    return {
        "mode": mode, "states": states, "historical_demographics": demographics,
        "texas_2024_results": texas_results, "north_carolina_participation": precincts,
        "minnesota_2026_participation": current_precincts, "current_demographics": current,
        "historical_group": demographic_group, "precinct_group": precinct_group,
        "current_group": current_group, "repeated_round_trips": 2,
        "keyboard_tabs": True, "methods_default_disclosures_closed": True,
        "research_default_closed": True, "no_horizontal_overflow": True,
    }


def check(base, proof, screenshots=None, explorer_script=None):
    if proof.exists():
        raise ValueError("Refuse to replace an existing tab-roundtrip proof")
    if screenshots:
        screenshots.mkdir(parents=True, exist_ok=True)
    base = base.rstrip("/")
    results = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            for mode, viewport in (("desktop", {"width": 1440, "height": 1000}),
                                   ("mobile", {"width": 390, "height": 844})):
                context = browser.new_context(viewport=viewport, is_mobile=mode == "mobile",
                                              has_touch=mode == "mobile")
                try:
                    if explorer_script:
                        context.route("**/scripts/participation-explorer.js",
                                      lambda route: route.fulfill(path=explorer_script))
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    response = page.goto(
                        base + "/voter-participation/?view=states&year=2026&state=Texas"
                        "&map-color=margin&map-level=county&mode=official",
                        wait_until="domcontentloaded")
                    assert response.ok
                    result = check_round_trip(page, mode, screenshots)
                    assert not errors, errors
                    result["page_errors"] = errors
                    results.append(result)
                finally:
                    context.close()

            unsupported = browser.new_context(viewport={"width": 1200, "height": 900})
            try:
                page = unsupported.new_page()
                if explorer_script:
                    unsupported.route("**/scripts/participation-explorer.js",
                                      lambda route: route.fulfill(path=explorer_script))
                page.goto(base + "/voter-participation/?view=precincts&state=Texas&year=2022"
                          "&layer=participation&dimension=education&group=unsupported",
                          wait_until="domcontentloaded")
                expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
                expect(page.locator("#year")).to_have_value("2024")
                expect(page.locator("#precinct-layer")).to_have_value("results")
                expect(page.locator("#dimension")).to_have_value("overall")
                assert page.locator("#group").input_value() in values(page, "#group")
                expect(page.locator("#notice")).to_contain_text(
                    "Other years' boundaries are not substituted")
                assert "year=2024" in page.url and "dimension=overall" in page.url
                results.append({"mode": "unsupported_deep_link", "year_fallback": "2024",
                                "layer_fallback": "results",
                                "dimension_fallback": "overall", "blank_view": False})
            finally:
                unsupported.close()

            deep_link = browser.new_context(viewport={"width": 1200, "height": 900})
            try:
                page = deep_link.new_page()
                page.goto(base + "/voter-participation/#definitions", wait_until="domcontentloaded")
                expect(page.locator("#tab-methods")).to_have_attribute("aria-selected", "true", timeout=90000)
                expect(page.locator("#methods-panel")).to_be_visible()
                expect(page.locator("#definitions")).to_have_attribute("open", "")
                results.append({"mode": "methods_deep_link", "selected_tab": "methods",
                                "target_disclosure_open": True})
            finally:
                deep_link.close()

            failed = browser.new_context(viewport={"width": 1200, "height": 900})
            try:
                failed.route("**/participation-methods/latest.json", lambda route: route.abort())
                page = failed.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/voter-participation/?view=states&year=2024",
                          wait_until="domcontentloaded")
                expect(page.locator("#method-observations")).to_contain_text(
                    "Historical voting methods could not be loaded", timeout=90000)
                select_tab(page, "methods")
                expect(page.locator("#definitions")).to_be_visible()
                assert page.locator("#downloads a[download]").count() >= 900
                assert not errors, errors
                results.append({"mode": "method_source_failure", "explicit_error": True,
                                "static_definitions_and_downloads_available": True})
            finally:
                failed.close()

            failed_precinct = browser.new_context(viewport={"width": 1200, "height": 900})
            try:
                failed_precinct.route("**/2024/TX.geojson.gz", lambda route: route.abort())
                page = failed_precinct.new_page()
                page.goto(base + "/voter-participation/?view=precincts&state=Texas"
                          "&year=2024&layer=results", wait_until="domcontentloaded")
                expect(page.locator("#notice")).to_contain_text(
                    "The saved data could not be loaded", timeout=90000)
                expect(page.locator("#notice")).to_contain_text("No values have been inferred")
                expect(page.locator("#visualization")).to_contain_text("Data unavailable")
                results.append({"mode": "precinct_source_failure", "explicit_error": True,
                                "no_inferred_values": True})
            finally:
                failed_precinct.close()

            no_js = browser.new_context(java_script_enabled=False,
                                         viewport={"width": 390, "height": 844})
            try:
                page = no_js.new_page()
                response = page.goto(base + "/voter-participation/#definitions",
                                     wait_until="domcontentloaded")
                assert response.ok
                expect(page.locator("#methods-panel")).to_be_visible()
                expect(page.locator("#definitions")).to_be_visible()
                expect(page.locator("#participation-research")).not_to_have_attribute("open", "")
                assert page.locator("#downloads a[download]").count() >= 900
                results.append({"mode": "mobile_no_javascript", "methods_visible": True,
                                "downloads_in_dom": True, "research_default_closed": True})
            finally:
                no_js.close()
        finally:
            browser.close()

    sources = [
        "public/scripts/participation-explorer.js",
        "src/pages/voter-participation.astro",
        "src/styles/voter-participation.css",
        "scripts/check-participation-tab-roundtrip-browser.py",
    ]
    payload = {
        "status": "PASS_participation_tab_round_trips",
        "base_url": base, "results": results,
        "source_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sources
        },
    }
    proof.parent.mkdir(parents=True, exist_ok=True)
    proof.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"status": payload["status"], "checks": len(results),
                      "desktop_mobile_round_trips": True, "source_failure": True,
                      "deep_link": True, "no_javascript": True}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4321")
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--explorer-script", type=Path)
    arguments = parser.parse_args()
    check(arguments.base_url, arguments.proof, arguments.screenshots, arguments.explorer_script)

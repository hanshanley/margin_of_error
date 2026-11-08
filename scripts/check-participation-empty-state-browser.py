"""Verify missing participation detail falls back to source-matched candidate counts."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def check(base, proof, override=False):
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    directory = ROOT / pointer["data_directory"]
    index = json.loads((directory / "index.json").read_bytes())
    native = json.loads((directory / "margins.json").read_bytes())
    results = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            for mode, width in (("desktop", 1440), ("mobile", 390), ("county_geometry_failure", 1440)):
                context = browser.new_context(viewport=dict(width=width, height=1000))
                try:
                    if override:
                        context.route("**/scripts/participation-explorer.js", lambda route: route.fulfill(
                            path=ROOT / "public/scripts/participation-explorer.js"))
                    if mode == "county_geometry_failure":
                        context.route(index["coverage"]["TX"]["file"], lambda route: route.abort())
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    response = page.goto(base.rstrip("/") + "/voter-participation/"
                                         "?view=states&year=2026&map-color=turnout&map-level=county&state=Texas",
                                         wait_until="domcontentloaded")
                    assert response.ok
                    expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
                    checked = []
                    for code, name in ([("TX", "Texas")] if mode == "county_geometry_failure"
                                       else [("TX", "Texas"), ("CO", "Colorado")]):
                        page.select_option("#state-select", name)
                        selected = page.locator(f'.map-feature[data-state="{name}"]')
                        selected.focus()
                        selected.press("Enter")
                        expect(page.locator("#title")).to_have_text(f"County candidate counts in {name}", timeout=90000)
                        expect(page.locator("#map-color")).to_have_value("turnout")
                        expect(page.locator("#show-county-candidate-results")).to_be_visible()
                        expected = {row["geography"]: row for row in native if row["state_code"] == code}
                        expect(page.locator("#table-head")).to_contain_text("Democratic votes")
                        expect(page.locator("#table-head")).to_contain_text("Republican votes")
                        actual_table = page.locator("#table-body tr").evaluate_all(
                            "rows => Object.fromEntries(rows.map(r => {const c=[...r.children].map(t=>t.textContent);"
                            "return [c[0],c.slice(1,5).map(v=>Number(v.replaceAll(',','')))];}))")
                        expected_table = {
                            key: [row[field] for field in ("democratic_votes", "republican_votes", "other_votes", "contest_votes")]
                            for key, row in sorted(expected.items())[:150]
                        }
                        assert actual_table == expected_table, code
                        expect(page.locator("#table-note")).to_contain_text(
                            f'{len(expected):,} observations')
                        expect(page.locator("#selection-panel")).to_contain_text("UF Initial Estimate")
                        if mode == "county_geometry_failure":
                            expect(page.locator("#geography-note")).to_contain_text("could not be loaded", timeout=90000)
                            assert page.locator(".geographic-detail .map-feature").count() == 0
                            checked.append(dict(state=code,table_rows=len(actual_table), geometry_failure_retains_counts=True))
                            continue
                        paths = page.locator('.geographic-detail [data-candidate-count-fallback="true"]')
                        expect(paths).to_have_count(index["coverage"][code]["counties"], timeout=90000)
                        actual = paths.evaluate_all(
                            "paths => Object.fromEntries(paths.map(p => [p.dataset.geography, "
                            "[Number(p.dataset.totalVotes),p.dataset.colorLevel,p.getAttribute('data-rate')]]))")
                        assert all(values == [expected[key]["contest_votes"], "none", None]
                                   for key, values in actual.items()), code
                        target = next(key for key in actual if expected[key]["contest_votes"] > 0)
                        path = page.locator(f'.geographic-detail [data-geography="{target}"]')
                        path.focus()
                        path.press("Enter")
                        expect(page.locator("#substate-detail")).to_contain_text(
                            f'{expected[target]["democratic_votes"]:,} Democratic')
                        expect(page.locator("#substate-detail")).to_contain_text(
                            f'{expected[target]["republican_votes"]:,} Republican')
                        expect(page.locator("#substate-detail")).to_contain_text("not precinct results")
                        page.locator("#show-county-candidate-results").click()
                        expect(page.locator("#map-color")).to_have_value("margin")
                        expect(page.locator("#map-level")).to_have_value("county")
                        expect(page.locator("#title")).to_have_text(f"County election results in {name}", timeout=90000)
                        colored = page.locator('.geographic-detail [data-color-level="county"]')
                        expect(colored).to_have_count(index["coverage"][code]["colored_counties"])
                        expect(page.locator("#caption")).to_contain_text("actual county")
                        page.select_option("#map-level", "precinct")
                        page.select_option("#map-color", "turnout")
                        expect(page.locator("#title")).to_have_text(f"County candidate counts in {name}", timeout=90000)
                        expect(page.locator("#geography-note")).to_contain_text("not county turnout or precinct results")
                        checked.append(dict(state=code,table_rows=len(actual_table),source_matched_counties=len(actual),
                                            explicit_results_switch=True,unsupported_precinct_fallback=True))
                        page.select_option("#map-level", "county")
                    if mode != "county_geometry_failure":
                        page.select_option("#state-select", "North Carolina")
                        page.locator("#show-current-counties").click()
                        expect(page.locator("#title")).to_have_text("Local participation in North Carolina", timeout=90000)
                        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(100)
                        expect(page.locator('[data-candidate-count-fallback="true"]')).to_have_count(0)
                        expect(page.locator("#table-head")).to_contain_text("Ballots reported")
                        page.locator("#map-reset").click()
                        expect(page.locator("#title")).to_have_text("Participation across the United States")
                        expect(page.locator(".geographic-detail .map-feature")).to_have_count(0)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    assert not errors, errors
                    if mode == "desktop":
                        page.select_option("#state-select", "Texas")
                        page.locator('.map-feature[data-state="Texas"]').focus()
                        page.locator('.map-feature[data-state="Texas"]').press("Enter")
                        expect(page.locator("#title")).to_have_text("County candidate counts in Texas", timeout=90000)
                        page.mouse.move(5, 5)
                        page.locator("#visualization").screenshot(path=str(proof.with_suffix(".desktop.png")))
                    results.append(dict(mode=mode,passed=True,checks=checked,
                                        qualified_participation_preserved=mode != "county_geometry_failure",
                                        page_errors=errors))
                finally:
                    context.close()
        finally:
            browser.close()
    proof.write_text(json.dumps(dict(
        passed=True,base_url=base,source_overrides=override,results=results,
        missing_rates_not_zero=True,candidate_votes_not_turnout=True),indent=2)+"\n")
    print(json.dumps(results,indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--source-overrides", action="store_true")
    args = parser.parse_args()
    check(args.base_url, args.proof, args.source_overrides)

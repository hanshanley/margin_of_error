"""Verify historical map values, district vintages and source-mode selection isolation."""

import argparse
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", required=True)
parser.add_argument("--count-runtime-root", type=Path, required=True)
parser.add_argument("--proof", type=Path, required=True)
parser.add_argument("--stylesheet", type=Path)
args = parser.parse_args()
assert not args.proof.exists()
historical = json.loads((ROOT / "public/voter-participation/data/states.json").read_bytes())
years = sorted({row["year"] for row in historical})
index = json.loads((args.count_runtime_root / "index.json").read_bytes())
nj = json.loads(gzip.decompress(
    (args.count_runtime_root / index["states"]["NJ"]["file"]).read_bytes()))
records = {row["id"]: row["view"] for row in nj["records"]}
precinct_pointer = json.loads((ROOT / "public/precinct-results.json").read_bytes())
precinct_root = ROOT / precinct_pointer["data_directory"]
precinct_index = json.loads((precinct_root / "index.json").read_bytes())
texas_frame = precinct_index["coverage"]["2024"]["TX"]
texas_features = json.loads(gzip.decompress(
    (precinct_root / texas_frame["file"]).read_bytes()))["features"]
texas_expected = {feature["properties"]["key"]: [
    feature["properties"]["margin_pp"], feature["properties"]["contest_votes"]]
    for feature in texas_features if feature["geometry"]
    and feature["properties"]["match_status"] == "matched"
    and feature["properties"]["margin_pp"] is not None}
cases = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in (1440, 390):
            page = browser.new_page(viewport={"width": width, "height": 1000})
            if args.stylesheet:
                page.add_init_script("document.addEventListener('DOMContentLoaded',()=>{"
                    "const style=document.createElement('style');style.textContent="
                    + json.dumps(args.stylesheet.read_text()) + ";document.head.append(style);});")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(args.base_url.rstrip("/") +
                "/voter-participation/?view=states&year=2024&map-color=turnout&state=Texas",
                wait_until="domcontentloaded", timeout=90000)
            assert response.ok
            expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
            ui_years = page.locator("#year option").evaluate_all(
                "nodes => nodes.map(node => Number(node.value)).filter(year => year < 2026)")
            assert ui_years and set(ui_years).issubset(years)
            page.locator(".explorer-options > summary").click()
            for basis in ("cvap", "vap"):
                page.locator("#basis").select_option(basis)
                for year in ui_years:
                    page.locator("#year").select_option(str(year))
                    paths = page.locator("#visualization .map-feature[data-state]")
                    expect(paths).to_have_count(51)
                    actual = paths.evaluate_all("""nodes => Object.fromEntries(nodes.map(node =>
                        [node.dataset.state, node.dataset.rate === '' ? null : Number(node.dataset.rate)]))""")
                    expected = {name: None for name in actual}
                    expected.update({row["state"]: row["turnout_pct"] for row in historical
                        if row["year"] == year and row["denominator"] == basis})
                    assert actual == expected, (width, year, basis)
                    expect(page.locator("#state-select")).to_have_value("Texas")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, year, basis)
                    cases.append({"width": width, "year": year, "basis": basis,
                        "all_51_source_values_or_missing_exact": True,
                        "selected_state_preserved": True})

            page.locator("#year").select_option("2024")
            page.locator("#map-color").select_option("margin")
            page.locator("#map-level").select_option("district")
            districts = page.locator('.geographic-detail path[data-level="district"]')
            expect(districts).to_have_count(38, timeout=90000)
            expect(page.locator("#geography-note")).to_contain_text("119th Congress")
            assert districts.evaluate_all("""nodes => nodes.every(node =>
                node.getTotalLength() > 0 && !/NaN|Infinity/.test(node.getAttribute('d')))""")
            districts.first.focus()
            districts.first.press("Enter")
            expect(page.locator("#substate-detail")).to_contain_text("U.S. House")
            page.locator("#map-level").select_option("precinct")
            precincts = page.locator('.geographic-detail path[data-color-level="precinct"]')
            expect(precincts).to_have_count(len(texas_expected), timeout=90000)
            actual = precincts.evaluate_all("""nodes => Object.fromEntries(nodes.map(node =>
                [node.dataset.geography, [Number(node.dataset.margin), Number(node.dataset.totalVotes)]]))""")
            assert actual == texas_expected
            precincts.first.focus()
            precincts.first.press("Enter")
            cases.append({"width": width, "year": 2024, "state": "Texas",
                "every_candidate_precinct_count_and_margin_exact": len(texas_expected),
                "historical_precinct_keyboard_selection": True})
            page.locator("#map-level").select_option("district")
            expect(districts).to_have_count(38, timeout=90000)
            page.locator("#visualization").screenshot(
                path=str(args.proof.with_suffix(f".district-{width}.png")))
            page.locator("#year").select_option("2026")
            expect(page.locator("#geography-note")).to_contain_text(
                "No verified 2026 congressional-district boundary/result pair", timeout=90000)
            expect(districts).to_have_count(0)
            cases.append({"width": width, "districts_2024": 38,
                "keyboard_district_selection": True, "unsupported_2026_not_given_2024_borders": True})

            page.locator("#map-color").select_option("turnout")
            page.locator("#map-level").select_option("county")
            page.locator("#state-select").select_option("New Jersey")
            for mode in ("available", "official", "uf_vep", "uf_vap", "in_person_early", "mail_returned"):
                page.locator("#mode").select_option(mode)
                expected_rows = [records[identity] for identity in nj["views"][mode]["counties"]]
                options = page.locator("#current-county-select option")
                expect(options).to_have_count(len(expected_rows) + 1 if expected_rows else 0,
                    timeout=90000)
                if expected_rows:
                    page.locator("#show-current-counties").click()
                shapes = page.locator('.geographic-detail path[data-level="county"][data-count]')
                expect(shapes).to_have_count(len(expected_rows), timeout=90000)
                actual = shapes.evaluate_all("""nodes => Object.fromEntries(nodes.map(node =>
                    [node.dataset.sourceCountyId, {
                        count:node.dataset.count === '' ? null : Number(node.dataset.count),
                        rate:node.dataset.rate === '' ? null : Number(node.dataset.rate)}]))""")
                expected = {row["county_id"]: {"count": row["ballots"],
                    "rate": row["reported_pct"]} for row in expected_rows}
                assert actual == expected, (width, mode)
                expect(page.locator("#mode")).to_have_value(mode)
                expect(page.locator("#state-select")).to_have_value("New Jersey")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                cases.append({"width": width, "mode": mode, "counties": len(expected_rows),
                    "all_source_counts_and_missing_rates_exact": True,
                    "unsupported_mode_cannot_retain_prior_mode_counts": True})
            assert not errors, errors
            page.close()
    finally:
        browser.close()
proof = {"status": "PASS_historical_values_district_vintages_and_mode_isolation",
    "base_url": args.base_url, "valid_source_data_mocked": False,
    "stylesheet_override": bool(args.stylesheet), "cases": cases,
    "historical_years": ui_years, "source_years_not_in_this_control": sorted(set(years) - set(ui_years)),
    "viewports": [1440, 390]}
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key != "cases"}))

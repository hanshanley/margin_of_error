"""Verify all 2026 source-model queries, holds, defaults, URLs and complete downloads."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-civic-group-rates/20261127-01"
RAW = (DATA / "viewer-data.json").read_bytes()
ROWS = json.loads(RAW)["groups"]
DOWNLOAD = json.loads((DATA / "download.json").read_bytes())
URL = ("https://raw.githubusercontent.com/hanshanley/voter-participation/"
       "83c072e58680e74ce57a34748c813549d99ef5da/data/civic-group-rates/20261127-01/viewer-data.json")
DIMS = {"overall": "overall", "age": "AGE6", "sex": "SEX", "gender": "GENDER3",
        "race": "RACETH5", "education": "EDUC", "income": "INCOME", "county_context": "RUCC"}


def check(base, proof, modes=None):
    assert not proof.exists()
    results = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            for mode, settings in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("mobile", {"viewport": {"width": 390, "height": 844}, "is_mobile": True}),
                ("no_javascript", {"java_script_enabled": False}),
                ("failed_source", {}), ("changed_checksum", {}), ("delayed_source_tab_race", {})]:
                if modes and mode not in modes:
                    continue
                proof.with_suffix(".progress.json").write_text(json.dumps(results, indent=2) + "\n")
                context = browser.new_context(**settings)
                try:
                    held = []
                    if mode == "failed_source":
                        context.route(URL, lambda route: route.abort())
                    elif mode == "changed_checksum":
                        context.route(URL, lambda route: route.fulfill(
                            body=RAW + b" ", content_type="application/json",
                            headers={"Access-Control-Allow-Origin": "*"}))
                    elif mode == "delayed_source_tab_race":
                        context.route(URL, lambda route: held.append(route))
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    response = page.goto(base.rstrip("/") + "/voter-participation/"
                                         "?view=national&year=2026&mode=civic_model&countState=TX",
                                         wait_until="domcontentloaded")
                    assert response.ok
                    if mode == "no_javascript":
                        page.locator("#civic-state-model-snapshot > summary").click()
                        actual = page.locator("#civic-state-model-snapshot tr[data-civic-state-model]").evaluate_all(
                            "rows => rows.map(row=>({state:row.dataset.civicStateModel,rate:row.dataset.rate,"
                            "n:row.dataset.sampleN,disposition:row.dataset.disposition}))")
                        expected = [dict(state=row["state_code"], rate=row["modeled_voter_pct"] or "",
                                         n=str(row["n"]) if row["n"] is not None else "",
                                         disposition=row["disposition"]) for row in ROWS if row["dimension"] == "overall"]
                        assert actual == expected and len(actual) == 51
                        results.append(dict(mode=mode, exact_state_model_and_dc_rows=51, passed=True))
                        continue
                    expect(page.locator("#mode")).to_have_value("civic_model", timeout=90000)
                    if mode == "delayed_source_tab_race":
                        page.wait_for_timeout(100)
                        assert held
                        page.locator("#tab-methods").click()
                        held[0].fulfill(body=RAW, content_type="application/json",
                                        headers={"Access-Control-Allow-Origin": "*"})
                        expect(page.locator("#methods-panel")).to_be_visible()
                        expect(page.locator("#historical-explorer")).to_be_hidden()
                        page.locator("#tab-national").click()
                        expect(page.locator('#visualization [data-civic-state="TX"]')).to_have_count(1)
                        results.append(dict(mode=mode, stale_model_render_cannot_replace_methods=True, passed=True))
                        continue
                    if mode in {"failed_source", "changed_checksum"}:
                        expect(page.locator("#visualization")).to_contain_text(
                            "2026 model source unavailable", timeout=90000)
                        expect(page.locator("#selection-panel")).to_contain_text("not administrative voting")
                        assert page.locator("#selection-panel .source-link").count() == 0
                        assert page.locator("#visualization [data-civic-state]").count() == 0
                        page.locator("#atlas-options > summary").click()
                        page.select_option("#mode", "in_person_early")
                        expect(page.locator("#measure")).to_contain_text("Reported source counts, not demographic turnout rates")
                        results.append(dict(mode=mode, reported_observations_and_full_downloads_preserved=True, passed=True))
                        continue
                    expect(page.locator('#visualization [data-civic-state="TX"]')).to_have_count(1, timeout=90000)
                    checked, selected = 0, 0
                    for state in sorted({row["state_code"] for row in ROWS}):
                        page.select_option("#current-state-select", state)
                        for dimension, native_dimension in DIMS.items():
                            page.select_option("#dimension", dimension)
                            page.select_option("#group", "All groups")
                            expected = [row for row in ROWS if row["state_code"] == state and row["dimension"] == native_dimension]
                            cards = page.locator(f'#visualization [data-civic-state="{state}"]')
                            expect(cards).to_have_count(len(expected))
                            actual = cards.evaluate_all(
                                "cards=>Object.fromEntries(cards.map(card=>[card.dataset.group,{rate:card.dataset.rate,"
                                "n:card.dataset.sampleN,disposition:card.dataset.disposition,text:card.textContent}]))")
                            for row in expected:
                                card = actual[row["group"]]
                                assert card["rate"] == (row["modeled_voter_pct"] or "")
                                assert card["n"] == (str(row["n"]) if row["n"] is not None else "")
                                assert card["disposition"] == row["disposition"]
                                if row["modeled_voter_pct"] is None:
                                    assert not card["rate"] and not card["n"]
                                    expect(page.locator(f'#visualization [data-civic-state="{state}"][data-group="{row["group"]}"]')).to_have_class("civic-group-held")
                                else:
                                    selected += 1
                                checked += 1
                    assert checked == 1530 and selected == 864
                    page.select_option("#current-state-select", "TX")
                    page.select_option("#dimension", "income")
                    page.select_option("#group", "100000_plus")
                    expect(page.locator("#visualization")).to_contain_text("$100,000")
                    before = {key: page.locator("#" + key).input_value() for key in ("year", "mode", "dimension", "group", "current-state-select")}
                    page.locator("#tab-methods").click()
                    assert len(page.locator(".methods-overview").inner_text().split()) == 106
                    expect(page.locator("#methods-archive")).to_be_hidden()
                    page.locator("#tab-states").click()
                    expect(page.locator("#mode")).not_to_have_value("civic_model")
                    page.locator("#tab-national").click()
                    for key, value in before.items():
                        expect(page.locator("#" + key)).to_have_value(value)
                    page.reload(wait_until="domcontentloaded")
                    expect(page.locator("#dimension")).to_have_value("income", timeout=90000)
                    expect(page.locator("#group")).to_have_value("100000_plus", timeout=90000)
                    page.select_option("#dimension", "county_context")
                    expect(page.locator("#notice")).to_contain_text("not measured individual residence")
                    page.select_option("#current-state-select", "DC")
                    expect(page.locator("#visualization")).to_contain_text("No D.C. survey sample")
                    assert not errors, errors
                    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth+1")
                    results.append(dict(mode=mode, all_query_values_and_holds_checked=checked,
                                        selected_models_checked=selected, native_counts_states_maps_and_history_preserved=True,
                                        income_county_context_url_tabs_and_dc_passed=True, passed=True))
                finally:
                    context.close()
            context = browser.new_context()
            try:
                for asset in DOWNLOAD["assets"]:
                    response = context.request.get(asset["url"], timeout=120000)
                    assert response.ok
                    body = response.body()
                    assert len(body) == asset["bytes"]
                    assert hashlib.sha256(body).hexdigest() == asset["sha256"]
                    if asset["name"].endswith(".zip"):
                        with zipfile.ZipFile(io.BytesIO(body)) as archive:
                            assert len(archive.namelist()) == 10
                            for name, receipt in json.loads(archive.read("checksums.json")).items():
                                member = archive.read(name)
                                assert len(member) == receipt["bytes"]
                                assert hashlib.sha256(member).hexdigest() == receipt["sha256"]
            finally:
                context.close()
        finally:
            browser.close()
    proof.write_text(json.dumps(dict(base_url=base, results=results,
                                    full_four_asset_bytes_and_archive_checksums_verified=True), indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--modes", nargs="+", choices=["desktop", "mobile", "no_javascript",
                        "failed_source", "changed_checksum", "delayed_source_tab_race"])
    args = parser.parse_args()
    check(args.base, args.proof, args.modes)

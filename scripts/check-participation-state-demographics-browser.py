"""Verify every state demographic rate, support flag, tab state and source fallback."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import io

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-state-demographics/20261108-01"
VIEWER = (DATA / "viewer-data.json").read_bytes()
ROWS = json.loads(VIEWER)["rows"]
RELEASE = json.loads((DATA / "download.json").read_bytes())
PIN = ("https://raw.githubusercontent.com/hanshanley/voter-participation/"
       "8910486e113366ca3d6db884ddebdef21b5ea21b/data/cps-state-demographics/20261108-01/viewer-data.json")
DIMENSIONS = {"overall": "overall", "age": "age_group", "sex": "sex",
              "education": "education", "race": "race_ethnicity"}


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
                ("failed_source", {}),
                ("changed_checksum", {}),
                ("delayed_source_tab_race", {}),
            ]:
                if modes and mode not in modes:
                    continue
                proof.with_suffix(".progress.json").write_text(json.dumps(results, indent=2) + "\n")
                context = browser.new_context(**settings)
                try:
                    if mode == "failed_source":
                        context.route(PIN, lambda route: route.abort())
                    elif mode == "changed_checksum":
                        context.route(PIN, lambda route: route.fulfill(
                            body=VIEWER + b" ", content_type="application/json",
                            headers={"Access-Control-Allow-Origin": "*"}))
                    elif mode == "delayed_source_tab_race":
                        held = []
                        context.route(PIN, lambda route: held.append(route))
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    response = page.goto(base.rstrip("/") + "/voter-participation/"
                                         "?view=national&year=2024&dimension=age&demographic-state=AL",
                                         wait_until="domcontentloaded")
                    assert response.ok
                    if mode == "no_javascript":
                        page.locator("#state-demographic-snapshot > summary").click()
                        native = page.locator("#state-demographic-snapshot [data-demographic-state]").evaluate_all(
                            "rows => rows.map(row => ({state:row.dataset.demographicState,year:row.dataset.year,"
                            "rate:row.dataset.rate,unknown:row.dataset.unknown,n:row.dataset.sampleN}))")
                        assert native == [
                            dict(state=row["state_code"], year=row["year"], rate=row["reported_voting_pct"],
                                 unknown=row["unknown_pct"], n=row["sample_n"])
                            for row in ROWS if row["dimension"] == "overall"]
                        assert len(native) == 102
                        results.append(dict(mode=mode, exact_overall_rows=102, passed=True))
                        continue
                    expect(page.locator("#demographic-state")).to_have_value("AL", timeout=90000)
                    assert page.locator("#demographic-state option").count() == 52
                    if mode == "delayed_source_tab_race":
                        page.wait_for_timeout(100)
                        assert held
                        page.locator("#tab-methods").click()
                        held[0].fulfill(body=VIEWER, content_type="application/json",
                                        headers={"Access-Control-Allow-Origin": "*"})
                        expect(page.locator("#methods-panel")).to_be_visible()
                        expect(page.locator("#historical-explorer")).to_be_hidden()
                        page.locator("#tab-national").click()
                        expect(page.locator('.demographic-card[data-state="AL"]')).to_have_count(4)
                        results.append(dict(mode=mode, stale_render_does_not_replace_methods=True, passed=True))
                        continue
                    if mode in {"failed_source", "changed_checksum"}:
                        expect(page.locator("#visualization")).to_contain_text(
                            "State demographic source unavailable", timeout=90000)
                        assert page.locator(".demographic-card").count() == 0
                        expect(page.locator("#selection-panel")).to_contain_text("Complete inputs")
                        page.select_option("#demographic-state", "US")
                        expect(page.locator("#visualization .demographic-card").first).to_be_visible()
                        expect(page.locator("#subtitle")).to_contain_text("National Census")
                        results.append(dict(mode=mode, national_recovery_and_full_downloads=True, passed=True))
                        continue
                    checked = 0
                    for code in sorted({row["state_code"] for row in ROWS}):
                        page.select_option("#demographic-state", code)
                        for year in ("2022", "2024"):
                            page.select_option("#year", year)
                            for dimension, native_dimension in DIMENSIONS.items():
                                page.select_option("#dimension", dimension)
                                page.select_option("#group", "All groups")
                                expected = [row for row in ROWS if row["state_code"] == code
                                            and row["year"] == year and row["dimension"] == native_dimension]
                                cards = page.locator(f'.demographic-card[data-state="{code}"][data-year="{year}"]')
                                expect(cards).to_have_count(len(expected))
                                actual = cards.evaluate_all(
                                    "cards => cards.map(card => ({group:card.dataset.group,rate:card.dataset.rate,"
                                    "unknown:card.dataset.unknown,n:card.dataset.sampleN,small:card.dataset.smallSample,"
                                    "text:card.textContent}))")
                                by_group = {row["group"]: row for row in actual}
                                for row in expected:
                                    rendered = by_group[row["group"]]
                                    assert rendered["rate"] == row["reported_voting_pct"]
                                    assert rendered["unknown"] == row["unknown_pct"]
                                    assert rendered["n"] == row["sample_n"]
                                    assert rendered["small"] == str(row["raw_case_count_under_30_diagnostic"] == "True").lower()
                                    if row["raw_case_count_under_30_diagnostic"] == "True":
                                        assert "Small sample" in rendered["text"]
                                    if not row["reported_voting_pct"]:
                                        assert "not zero participation" in rendered["text"]
                                    checked += 1
                    assert checked == 1734
                    page.select_option("#demographic-state", "ID")
                    page.select_option("#year", "2022")
                    page.select_option("#dimension", "race")
                    page.select_option("#group", "Black, non-Hispanic")
                    expect(page.locator("#visualization")).to_contain_text("not zero participation")
                    page.locator("#tab-methods").click()
                    expect(page.locator("#methods-archive")).to_be_hidden()
                    words = len(page.locator(".methods-overview").inner_text().split())
                    assert words == 106, words
                    page.locator("#tab-states").click()
                    expect(page.locator("#demographic-state-label")).to_be_hidden()
                    page.locator("#tab-national").click()
                    for field, value in {"demographic-state": "ID", "year": "2022",
                                         "dimension": "race", "group": "Black, non-Hispanic"}.items():
                        expect(page.locator("#" + field)).to_have_value(value)
                    page.reload(wait_until="domcontentloaded")
                    expect(page.locator("#visualization")).to_contain_text("not zero participation", timeout=90000)
                    page.locator(".explorer-options > summary").click()
                    page.select_option("#basis", "vap")
                    expect(page.locator("#visualization")).to_contain_text("no all-resident rate is inferred")
                    assert page.locator(".demographic-card").count() == 0
                    page.select_option("#basis", "cvap")
                    expect(page.locator("#visualization")).to_contain_text("not zero participation")
                    assert not errors, errors
                    overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                    assert not overflow
                    results.append(dict(mode=mode, every_state_group_value_checked=checked,
                                        all_51_jurisdictions=True, tabs_url_population_missing_and_sparse_passed=True,
                                        methods_overview_words=words, no_horizontal_overflow=True, passed=True))
                finally:
                    context.close()
            download_context = browser.new_context()
            try:
                for asset in RELEASE["assets"]:
                    if asset["name"] not in {"complete-analysis.zip", "complete-state-demographic-participation.csv"}:
                        continue
                    response = download_context.request.get(asset["url"], timeout=120000)
                    assert response.ok
                    body = response.body()
                    assert len(body) == asset["bytes"]
                    assert hashlib.sha256(body).hexdigest() == asset["sha256"]
                    if asset["name"].endswith(".zip"):
                        with zipfile.ZipFile(io.BytesIO(body)) as archive:
                            assert len(archive.namelist()) == 13
                            for name, receipt in json.loads(archive.read("checksums.json")).items():
                                member = archive.read(name)
                                assert len(member) == receipt["bytes"]
                                assert hashlib.sha256(member).hexdigest() == receipt["sha256"]
            finally:
                download_context.close()
        finally:
            browser.close()
    proof.write_text(json.dumps(dict(base_url=base, results=results,
                                    full_zip_csv_bytes_and_all_archive_checksums_verified=True), indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--modes", help="Comma-separated browser configurations; omit to check all six")
    args = parser.parse_args()
    check(args.base, args.proof, args.modes.split(",") if args.modes else None)

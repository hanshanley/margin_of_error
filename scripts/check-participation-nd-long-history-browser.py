"""Verify all six-election ND counts and complete downloads in four browser modes."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PATH = "/participation-nd-long-history/20261107-01/"


def check(base, proof):
    reference = json.loads((ROOT / ("public" + PATH) / "history.json").read_bytes())
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for mode, options in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("mobile", {"viewport": {"width": 390, "height": 844}}),
                ("no_javascript", {"java_script_enabled": False}), ("failed_json", {}),
            ]:
                context = browser.new_context(**options)
                try:
                    if mode == "failed_json":
                        context.route("**/participation-nd-long-history/**/*.json",
                                      lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/",
                              wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-nd-long-history")
                    expect(panel).to_be_visible()
                    expect(panel.locator("[data-nd-long-county]")).to_have_count(53)
                    for text in (
                            "2026 is an unofficial snapshot, not final turnout",
                            "not measured prior-voter drop-off or switching",
                            "not independent county controls", "not a fixed-person cohort",
                            "named reporting units, not numeric precinct IDs",
                            "at 01:30 UTC", "not metadata alone"):
                        expect(panel).to_contain_text(text)
                    panel.locator("#nd-long-history-counties > summary").click()
                    expected = [(panel.locator("[data-nd-long-state]"), reference["statewide"])]
                    expected += [
                        (panel.locator(f'[data-nd-long-county="{row["county_name"]}"]'), row)
                        for row in reference["counties"]]
                    cells = 0
                    for row, counts in expected:
                        for year in ("2016", "2018", "2020", "2022", "2024", "2026"):
                            expect(row.locator(f'[data-nd-long-year="{year}"]')).to_have_text(
                                f'{counts["ballots_by_year"][year]:,}')
                            cells += 1
                        for year in ("2018", "2020"):
                            value = counts["reported_count_change_since"][year]
                            expect(row.locator(f'[data-nd-long-change="{year}"]')).to_have_text(
                                ("+" if value > 0 else "") + f"{value:,}")
                            cells += 1
                    assert cells == 432
                    expect(page.locator("#participation-nd-history")).to_be_visible()
                    expect(page.locator("#participation-clark-history")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    links = panel.locator(".download-links a")
                    expect(links).to_have_count(4)
                    if mode == "desktop":
                        path = base.rstrip("/") + PATH
                        archive = context.request.get(path + "complete-analysis.zip")
                        metadata = context.request.get(path + "download.json")
                        assert archive.ok and metadata.ok
                        body, info = archive.body(), metadata.json()
                        assert body == (ROOT / ("public" + PATH) / "complete-analysis.zip").read_bytes()
                        assert len(body) == info["bytes"]
                        assert hashlib.sha256(body).hexdigest() == info["sha256"]
                        assert info["selected_reporting_unit_observations"] == 2419
                        with zipfile.ZipFile(io.BytesIO(body)) as contents:
                            assert contents.testzip() is None
                            inventory = json.loads(contents.read("checksums.json"))
                            assert len(contents.namelist()) == info["members"]
                            assert set(contents.namelist()) == {*inventory, "checksums.json"}
                            for name, receipt in inventory.items():
                                raw = contents.read(name)
                                assert len(raw) == receipt["bytes"]
                                assert hashlib.sha256(raw).hexdigest() == receipt["sha256"]
                    results.append({"mode": mode, "passed": True, "county_rows_verified": 53,
                                    "numeric_cells_verified": cells})
                finally:
                    context.close()
        finally:
            browser.close()
    if proof:
        with proof.open("x") as target:
            target.write(json.dumps({"base_url": base, "checks": results}, indent=2) + "\n")
    print(json.dumps(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4365")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    check(args.base_url, args.proof)

"""Verify all selected county counts, snapshot labels and complete downloads in four modes."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PATH = "/participation-nd-ballot-history/20261107-01/"


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
                        context.route("**/participation-nd-ballot-history/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    panel = page.locator("#participation-nd-history")
                    expect(panel).to_be_visible()
                    expect(panel.locator("[data-nd-county]")).to_have_count(53)
                    for text in ("unofficial 2026 snapshot", "not measured prior-voter drop-off or switching",
                                 "not an estimate of final 2026 turnout", "No cross-year precinct match",
                                 "not independent county controls", "not registered voters",
                                 "at 01:30 UTC"):
                        expect(panel).to_contain_text(text)
                    panel.locator("#nd-history-counties > summary").click()
                    expected = [(panel.locator("[data-nd-state]"), reference["statewide"])]
                    expected += [(panel.locator(f'[data-nd-county="{row["county_name"]}"]'), row)
                                 for row in reference["counties"]]
                    for row, counts in expected:
                        for year in ("2022", "2024", "2026"):
                            expect(row.locator(f'[data-nd-year="{year}"]')).to_have_text(
                                f'{counts["ballots_by_year"][year]:,}')
                        for year in ("2022", "2024"):
                            value = counts[f"reported_ballot_count_change_since_{year}"]
                            expect(row.locator(f'[data-nd-change="{year}"]')).to_have_text(
                                ("+" if value > 0 else "") + f"{value:,}")
                    expect(page.locator("#participation-house-intentions")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        path = base.rstrip("/") + PATH
                        raw = context.request.get(path + "complete-analysis.zip")
                        metadata = context.request.get(path + "download.json")
                        assert raw.ok and metadata.ok
                        body, info = raw.body(), metadata.json()
                        assert len(body) == info["bytes"]
                        assert hashlib.sha256(body).hexdigest() == info["sha256"]
                        assert info["selected_precinct_observations"] == 1141
                        assert info["county_comparisons"] == 53
                    results.append({"mode": mode, "passed": True, "county_rows_verified": 53})
                finally:
                    context.close()
        finally:
            browser.close()
    if proof:
        proof.write_text(json.dumps({"base_url": base, "checks": results}, indent=2) + "\n")
    print(json.dumps(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4331")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    check(args.base_url, args.proof)

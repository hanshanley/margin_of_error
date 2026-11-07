"""Verify newer 2026 observations and current-register diagnostics without relabeling their scope."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-2026-evidence/20261107-01"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--proof", type=Path)
args = parser.parse_args()
if args.proof and args.proof.exists():
    raise ValueError("Refuse to replace an existing proof")
summary = json.loads((DATA / "summary.json").read_text())
download = json.loads((DATA / "download.json").read_text())
results = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    try:
        for mode, options in [
            ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
            ("mobile", {"viewport": {"width": 390, "height": 844}}),
            ("no_javascript", {"java_script_enabled": False}),
        ]:
            context = browser.new_context(**options)
            try:
                page = context.new_page()
                response = page.goto(args.base_url.rstrip("/") + "/voter-participation/",
                                     wait_until="domcontentloaded")
                assert response.ok
                if mode != "no_javascript":
                    page.wait_for_function("document.querySelector('#year').options.length > 1")
                    page.locator("#tab-methods").click()
                page.locator("#updates-panel > summary").click()
                expect(page.locator("[data-evidence-as-of]")).to_contain_text(summary["as_of_label"])
                expect(page.locator("[data-2026-evidence]")).to_have_count(len(summary["observations"]))
                for row in summary["observations"]:
                    element = page.locator(f'[data-2026-evidence="{row["id"]}"]')
                    expect(element).to_contain_text(row["jurisdiction"])
                    expect(element.locator("td").nth(0)).to_contain_text(f'{row["numerator"]:,}')
                    expect(element.locator("td").nth(0)).to_contain_text(row["measure"])
                    expect(element.locator("td").nth(0)).to_contain_text(row["comparison_note"])
                    denominator = element.locator("td").nth(1)
                    expect(denominator).to_contain_text(row["denominator_label"])
                    expect(denominator).to_contain_text("Not qualified / supplied" if row["denominator"] is None
                                                       else f'{row["denominator"]:,}')
                    expect(element.locator("td").nth(2)).to_contain_text(row["source_time_label"])
                    expect(element.locator("td").nth(2)).to_contain_text(row["status"])
                    expect(element.get_by_role("link", name="Native source")).to_have_attribute("href", row["source_url"])
                    expect(element.locator("td").nth(3)).to_contain_text(row["coverage_note"])
                    expect(element.locator("td").nth(3)).to_contain_text(row["history_note"])
                composition = page.locator("#colorado-2026-composition")
                composition.locator(":scope > summary").click()
                for dimension in ("age", "gender"):
                    elements = composition.locator(f'[data-colorado-composition="{dimension}"]')
                    groups = summary["colorado_composition"][dimension]
                    expect(elements).to_have_count(len(groups))
                    for index, row in enumerate(groups):
                        expect(elements.nth(index).locator("th")).to_have_text(row["group"])
                        expect(elements.nth(index).locator("td")).to_have_text(f'{row["returned_ballots"]:,}')
                expect(composition).to_contain_text("not demographic turnout rates")
                expect(composition).to_contain_text("do not add them together")
                diagnostic = page.locator("#butler-2026-record-diagnostic")
                diagnostic.locator(":scope > summary").click()
                expect(diagnostic.locator("[data-butler-credit-cell]")).to_have_count(4)
                for row in summary["butler"]["cells"]:
                    key = f'{int(row["prior_credit"])}{int(row["current_credit"])}'
                    expect(diagnostic.locator(f'[data-butler-credit-cell="{key}"]')).to_contain_text(
                        f'{row["records"]:,}')
                expect(diagnostic).to_contain_text("not measured abstention")
                expect(diagnostic).to_contain_text("not candidate-choice cohorts")
                for year in (2024, 2026):
                    gap = summary["butler"][f"current_{year}_credits"] - summary["butler"][f"official_{year}_ballots"]
                    expect(diagnostic).to_contain_text(f"{gap:,}")
                link = page.get_by_role("link", name="Complete 2026 aggregate queries, source records, county tables and verification (ZIP)")
                expect(link).to_have_attribute("href", download["url"])
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                if mode == "desktop":
                    response = context.request.get(link.get_attribute("href"))
                    assert response.ok
                    body = response.body()
                    assert len(body) == download["bytes"]
                    assert hashlib.sha256(body).hexdigest() == download["sha256"]
                if mode != "no_javascript":
                    page.locator("#tab-states").click()
                    expect(page.locator("#visualization svg")).to_be_visible()
                results.append({"mode": mode, "observations": len(summary["observations"]),
                                "butler_cells": 4, "colorado_groups": 12, "passed": True})
            finally:
                context.close()
    finally:
        browser.close()
if args.proof:
    args.proof.write_text(json.dumps({"base_url": args.base_url, "checks": results}, indent=2) + "\n")
print(json.dumps(results))

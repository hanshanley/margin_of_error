"""Verify suppression of unsupported scalars and retention of qualified source classes."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--proof", type=Path)
args = parser.parse_args()
if args.proof and args.proof.exists():
    raise ValueError("Refuse to replace an existing proof")
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
                page.locator("#participation-research > summary").click()
                for selector in [
                    "[data-estimated-state]", "[data-estimated-composition-state]",
                    "[data-coalition-state]", "[data-age-coalition]", "[data-state-age-coalition]",
                    "[data-age-stress-absence]", "[data-state-age-stress]",
                ]:
                    expect(page.locator(selector)).to_have_count(0)
                expect(page.locator("[data-estimated-coverage]")).to_have_count(51)
                expect(page.locator("[data-state-age-coverage]")).to_have_count(51)
                expect(page.locator("#participation-estimated-coalitions")).to_contain_text(
                    "Historical evidence decision")
                expect(page.locator("#participation-estimated-coalitions")).to_contain_text("Initial Estimate")
                expect(page.locator("#participation-coalition-scenarios")).to_contain_text("reported ballots")
                assert page.locator('[data-publication-class="unscaled-qualified-survey-shares"]').count() > 0
                expect(page.locator("[data-age-diagnostics]")).to_have_count(6)
                expect(page.locator("[data-state-age-support]")).to_have_count(16)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                results.append({"mode": mode, "passed": True})
            finally:
                context.close()
    finally:
        browser.close()
if args.proof:
    args.proof.write_text(json.dumps({"base_url": args.base_url, "checks": results}, indent=2) + "\n")
print(json.dumps(results))

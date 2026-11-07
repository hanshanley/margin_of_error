"""Verify withheld historical scalars, retained provider totals and complete archives."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright


def check(base, proof, version="20261107-03"):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for mode, options in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("mobile", {"viewport": {"width": 390, "height": 844}}),
                ("no_javascript", {"java_script_enabled": False}),
                ("failed_json", {}),
            ]:
                context = browser.new_context(**options)
                try:
                    if mode == "failed_json":
                        context.route("**/participation-estimated-coalitions/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-estimated-coalitions")
                    expect(panel).to_contain_text("43 states · 61 separate contests, plus national House")
                    expect(panel).to_contain_text("Initial Estimate")
                    expect(panel).to_contain_text("not official observed or certified counts")
                    expect(panel).to_contain_text("Apparent absence is not measured staying home")
                    expect(panel).to_contain_text("response selection remains unverified")
                    expect(panel).to_contain_text("excludes D.C. from both 2024 coalitions and 2026 estimated totals")
                    expect(panel).to_contain_text("123,317,000" if version == "20261107-03" else "123,267,000")
                    expect(panel).to_contain_text("Historical evidence decision")
                    expect(panel.locator("[data-estimated-state]")).to_have_count(0)
                    expect(panel.locator("[data-estimated-composition-state]")).to_have_count(0)
                    if version == "20261107-03":
                        expect(panel).to_contain_text("separately dated, frozen inputs")
                    panel.get_by_text("Estimated-total coverage: all 50 states and D.C.", exact=True).click()
                    expect(panel.locator("[data-estimated-coverage]")).to_have_count(51)
                    expect(panel.locator('[data-estimated-coverage="DC"]')).to_contain_text("223,000")
                    if version == "20261107-03":
                        expect(panel.locator('[data-estimated-coverage="WA"]')).to_contain_text("3,250,000")
                        expect(panel.locator('[data-estimated-coverage="WA"]')).to_contain_text("no national allocation")
                    expect(panel.locator('[data-estimated-coverage="DC"]')).to_contain_text("no national allocation")
                    expect(panel.locator('[data-estimated-coverage="NH"]')).to_contain_text("withheld_unreconciled_prior_composition")
                    expect(page.locator("#participation-coalition-scenarios")).to_contain_text("8 states · 12 separate contests")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        link = panel.locator(f'a[href$="/{version}/complete-analysis.zip"]')
                        response = context.request.get(urljoin(base, link.get_attribute("href")))
                        metadata = context.request.get(
                            base.rstrip("/") + f"/participation-estimated-coalitions/{version}/download.json")
                        assert response.ok and metadata.ok
                        raw, info = response.body(), metadata.json()
                        assert len(raw) == info["bytes"]
                        assert hashlib.sha256(raw).hexdigest() == info["sha256"]
                    results.append({"mode": mode, "passed": True})
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
    parser.add_argument("--version", choices=("20261107-02", "20261107-03"), default="20261107-03")
    args = parser.parse_args()
    check(args.base_url, args.proof, args.version)

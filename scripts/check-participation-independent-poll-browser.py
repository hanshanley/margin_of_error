"""Verify the separate source's conditional denominators and complete downloads."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright


def check(base, proof):
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
                        context.route("**/participation-mevp/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-independent-poll")
                    expect(panel.locator("[data-mevp-group]")).to_have_count(5)
                    for group, n, rd, dr, first in [
                        ("latino", "819", "17%", "3%", "17%"),
                        ("aapi", "621", "17%", "6%", "12%"),
                        ("white", "800", "7%", "4%", "8%"),
                        ("black", "298", "35%", "3%", "14%"),
                        ("native-american", "468", "13%", "5%", "10%"),
                    ]:
                        row = panel.locator(f'[data-mevp-group="{group}"]')
                        for attribute, value in [("trump-base", n), ("trump-switch", rd),
                                                 ("harris-switch", dr), ("first-november", first)]:
                            expect(row.locator(f"[data-mevp-{attribute}]")).to_have_text(value)
                    expect(panel).to_contain_text("among current participants recalling each prior vote")
                    expect(panel).to_contain_text("First November does not mean first-ever voting")
                    expect(panel).to_contain_text("No population drop-off is released here")
                    expect(panel).to_contain_text("not an effective sample size")
                    expect(panel).to_contain_text("not an additional SSRS sample")
                    expect(page.locator("#participation-demographic-counts")).to_contain_text("299 qualified")
                    expect(page.locator("#participation-estimated-coalitions")).to_contain_text("43 states")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        link = panel.get_by_role("link", name="Complete independent-poll inputs + code + results (ZIP)")
                        response = context.request.get(urljoin(base, link.get_attribute("href")))
                        metadata = context.request.get(base.rstrip("/") + "/participation-mevp/20261107-01/download.json")
                        assert response.ok and metadata.ok
                        raw, info = response.body(), metadata.json()
                        assert len(raw) == info["bytes"] and hashlib.sha256(raw).hexdigest() == info["sha256"]
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
    args = parser.parse_args()
    check(args.base_url, args.proof)

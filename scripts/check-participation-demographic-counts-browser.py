"""Verify matched demographic counts, withholding and complete downloads in four modes."""

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
                        context.route("**/participation-demographic-counts/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-demographic-counts")
                    expect(panel).to_contain_text("299 qualified group comparisons across 34 states plus national House")
                    expect(panel).to_contain_text("Group drop-off remains unavailable")
                    expect(panel).to_contain_text("not an unchanged 2024 cohort")
                    expect(panel).to_contain_text("not confidence intervals")
                    expect(panel).to_contain_text("No county/precinct estimates")
                    expect(panel).to_contain_text("123,267,000")
                    expect(panel.locator("[data-demographic-state]")).to_have_count(299)
                    expect(panel.locator('[data-demographic-state="US"]')).to_have_count(10)
                    age = panel.locator('[data-demographic-state="US"][data-demographic-subset="54"]')
                    expect(age.locator("[data-demographic-share]")).to_have_text("30%")
                    expect(age.locator("[data-demographic-population]")).to_have_text("36,980,000")
                    panel.locator('[data-demographic-jurisdiction="NC"] > summary').click()
                    nc = panel.locator('[data-demographic-state="NC"][data-demographic-contest="SG"][data-demographic-subset="20"]')
                    expect(nc.locator("[data-demographic-population]")).to_have_text("1,910,000")
                    expect(nc.locator("[data-demographic-trump-flow]")).to_contain_text("75,000")
                    expect(nc.locator("[data-demographic-harris-flow]")).to_contain_text("8,000")
                    missing = panel.locator('[data-demographic-composition-state="NC"][data-demographic-composition-subset="54"]')
                    expect(missing.locator("[data-demographic-other-flows]")).to_have_text("Unavailable / Unavailable")
                    expect(panel.locator("[data-demographic-coverage]")).to_have_count(51)
                    expect(panel.locator('[data-demographic-coverage="DC"]')).to_contain_text("no allocation")
                    expect(page.locator("#participation-estimated-coalitions")).to_contain_text("43 states")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        link = panel.get_by_role("link", name="Complete demographic counts + selected inputs + code (ZIP)")
                        response = context.request.get(urljoin(base, link.get_attribute("href")))
                        metadata = context.request.get(base.rstrip("/") + "/participation-demographic-counts/20261107-01/download.json")
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

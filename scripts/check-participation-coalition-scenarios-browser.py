"""Verify conditional scaling, explicit qualification, coverage and complete downloads."""

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
                        context.route("**/participation-coalition-scenarios/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    panel = page.locator("#participation-coalition-scenarios")
                    expect(panel).to_contain_text("6 states · 9 separate contests")
                    expect(panel).to_contain_text("conditional estimates, not measured staying home")
                    expect(panel).to_contain_text("response selection remains unverified")
                    expect(panel).to_contain_text("not current live or certified totals")
                    expect(panel.locator("[data-coalition-state]")).to_have_count(18)
                    row = panel.locator('[data-coalition-state="NC"][data-coalition-prior="R"]')
                    expect(row.locator("td").nth(1)).to_have_text("2,898,423")
                    expect(row.locator("td").nth(2)).to_have_text("1,816,000")
                    expect(row.locator("td").nth(3)).to_have_text("182,0006.3%")
                    expect(row.locator("td").nth(4)).to_have_text("1,082,00037.3%")
                    details = panel.locator("details").nth(1)
                    details.locator(":scope > summary").click()
                    expect(panel.locator("[data-coalition-coverage]")).to_have_count(51)
                    expect(panel.locator('[data-coalition-coverage="ND"]')).to_contain_text("Seek applicable joint choice evidence")
                    expect(panel.locator('[data-coalition-coverage="DC"]')).to_contain_text("Not yet in these qualified inputs")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        link = panel.get_by_role("link", name="Complete coalition scenarios + official inputs + code (ZIP)")
                        response = context.request.get(urljoin(base, link.get_attribute("href")))
                        metadata = context.request.get(base.rstrip("/") + "/participation-coalition-scenarios/20261107-01/download.json")
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
    args = parser.parse_args()
    check(args.base_url, args.proof)

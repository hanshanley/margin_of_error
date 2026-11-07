"""Check published intentions, unknown nonresponse, no-scaling labels and complete bytes."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def check(base, proof):
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
                        context.route("**/participation-pew-intentions/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    panel = page.locator("#participation-panel-intentions")
                    expect(panel.locator("[data-pew-prior]")).to_have_count(2)
                    for prior, values in [
                        ("Trump 2024 voters", ["5%", "77%", "5%", "13%"]),
                        ("Harris 2024 voters", ["87%", "3%", "3%", "7%"]),
                    ]:
                        row = panel.locator(f'[data-pew-prior="{prior}"]')
                        for party, value in zip(("D", "R", "Other", "Not sure"), values):
                            expect(row.locator(f'[data-pew-choice="{party}"]')).to_have_text(value)
                        expect(row.locator("[data-pew-nonresponse]")).to_have_text("Not published")
                    for text in (
                        "record-validated 2024 participation", "not completed November 2026 voting or turnout",
                        "No population switching or drop-off counts",
                        "not percentages of the full original 2024 coalitions",
                        "not administratively observed candidate choice",
                        "not multiplied by November ballot totals", "September 28–October 4, 2026"):
                        expect(panel).to_contain_text(text)
                    details = panel.locator("details")
                    details.locator("summary").click()
                    for text in ("month after", "week after", "does not make it the SSRS",
                                 "overall registered-voter margin of error is not reused"):
                        expect(details).to_contain_text(text)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    expect(page.locator("#participation-house-intentions")).to_be_visible()
                    expect(page.locator("#participation-nd-history")).to_be_attached()
                    if mode == "desktop":
                        path = base.rstrip("/") + "/participation-pew-intentions/20261107-01/"
                        response = context.request.get(path + "complete-analysis.zip")
                        metadata = context.request.get(path + "download.json")
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

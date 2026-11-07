"""Check intent-only labels, full conditional denominators and complete downloads."""

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
                        context.route("**/participation-slu-intentions/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-house-intentions")
                    expect(panel.locator("[data-slu-prior]")).to_have_count(2)
                    for prior, n, kish, values in [
                        ("Trump", "418", "299.5", ["4.2%", "87.7%", "1.8%", "6.2%"]),
                        ("Harris", "383", "236.6", ["93.5%", "1.0%", "1.2%", "4.2%"]),
                    ]:
                        row = panel.locator(f'[data-slu-prior="{prior}"]')
                        expect(row.locator("[data-slu-base]")).to_have_text(n)
                        expect(row.locator("[data-slu-kish]")).to_have_text(kish)
                        for party, value in zip(("D", "R", "Other", "Not sure"), values):
                            expect(row.locator(f'[data-slu-choice="{party}"]')).to_have_text(value)
                    for text in ("not observed November switching or turnout",
                                 "No drop-off estimate from this sample",
                                 "not percentages of the original 2024 coalitions",
                                 "No subgroup confidence intervals", "August 13–24, 2026"):
                        expect(panel).to_contain_text(text)
                    expect(page.locator("#participation-state-age-scenarios")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        path = base.rstrip("/") + "/participation-slu-intentions/20261107-01/"
                        raw = context.request.get(path + "complete-analysis.zip")
                        metadata = context.request.get(path + "download.json")
                        assert raw.ok and metadata.ok
                        body, info = raw.body(), metadata.json()
                        assert len(body) == info["bytes"]
                        assert hashlib.sha256(body).hexdigest() == info["sha256"]
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

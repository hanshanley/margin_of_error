"""Verify server-rendered survey cells, qualified gaps and complete downloads."""

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
                        context.route("**/participation-survey/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-survey")
                    expect(panel).to_contain_text("433 qualified tables across 43 states")
                    expect(panel).to_contain_text("not all of the original Trump or Harris coalition")
                    expect(panel).to_contain_text("Population drop-off")
                    expect(panel.locator("[data-survey-jurisdiction]")).to_have_count(52)
                    expect(panel.locator("[data-survey-status]")).to_have_count(936)
                    expect(panel.locator("[data-survey-status=published_joint_question_reviewed]")).to_have_count(433)
                    for code, expected in [("NC", ["10%", "1%", "4.30", "0.49"]),
                                           ("TX", ["11%", "1%", "5.17", "0.42"])]:
                        section = panel.locator(f"#survey-{code}")
                        section.locator(":scope > summary").click()
                        row = section.locator("[data-survey-contest=SG] [data-survey-subset='0']")
                        for index, value in enumerate(expected):
                            expect(row.locator("td").nth(index)).to_have_text(value)
                        young = section.locator("[data-survey-contest=SG] [data-survey-subset='53']")
                        expect(young.locator("td").first).to_have_text("19%" if code == "NC" else "30%")
                    nh = panel.locator("#survey-NH")
                    nh.locator(":scope > summary").click()
                    row = nh.locator("[data-survey-contest=SG] [data-survey-subset='0']")
                    expect(row).to_have_attribute("data-survey-status", "withheld_unreconciled_prior_composition")
                    expect(row.locator("td").nth(2)).to_have_text("Withheld")
                    nd = panel.locator("#survey-ND")
                    nd.locator(":scope > summary").click()
                    expect(nd).to_contain_text("not a zero switching rate")
                    expect(panel.locator("#survey-DC")).to_contain_text("D.C. was not sampled")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        link = panel.get_by_role("link", name="Complete survey tables + inputs + code (ZIP)")
                        response = context.request.get(urljoin(base, link.get_attribute("href")))
                        metadata = context.request.get(
                            base.rstrip("/") + "/participation-survey/20261107-02/download.json")
                        assert response.ok and metadata.ok
                        raw = response.body()
                        info = metadata.json()
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

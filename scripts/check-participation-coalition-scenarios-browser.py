"""Verify withheld coalition scalars, retained source observations and complete downloads."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright


def check(base, proof, version):
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
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-coalition-scenarios")
                    states, contests = (6, 9) if version == "20261107-01" else (8, 12)
                    expect(panel).to_contain_text(f"{states} states · {contests} separate contests")
                    expect(panel).to_contain_text("conditional estimates, not measured staying home")
                    expect(panel).to_contain_text("response selection remains unverified")
                    expect(panel).to_contain_text("not current live or certified totals")
                    expect(panel).to_contain_text("Historical evidence decision")
                    expect(panel.locator("[data-coalition-state]")).to_have_count(0)
                    details = panel.locator("details").nth(1)
                    details.locator(":scope > summary").click()
                    expect(panel.locator("[data-coalition-coverage]")).to_have_count(51)
                    expect(panel.locator('[data-coalition-coverage="ND"]')).to_contain_text("Seek applicable joint choice evidence")
                    expect(panel.locator('[data-coalition-coverage="DC"]')).to_contain_text("Not yet in these qualified inputs")
                    if version == "20261107-02":
                        expect(panel).to_contain_text("Additional Georgia and Delaware scope assumption")
                        expect(panel).to_contain_text("not newly approved all-mode counts")
                        expect(panel.locator('[data-coalition-coverage="GA"]')).to_contain_text("scope assumed")
                        expect(panel.locator('[data-coalition-coverage="DE"]')).to_contain_text("scope assumed")
                        survey = page.locator("#participation-survey")
                        expect(survey).to_contain_text("not demographic turnout rates")
                        nc = survey.locator("#survey-NC")
                        nc.locator(":scope > summary").click()
                        main = nc.locator("[data-survey-contest=SG] [data-survey-subset='0']")
                        expect(main.locator("[data-survey-prior-nonvoter-share]")).to_have_text("4%")
                        expect(main.locator("[data-survey-prior-other-share]")).to_have_text("2%")
                        missing = survey.locator("[data-survey-status=withheld_source_disabled]").first
                        expect(missing.locator("[data-survey-prior-nonvoter-share]")).to_have_text("Unavailable")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        link = panel.locator(f'a[href$="/{version}/complete-analysis.zip"]')
                        response = context.request.get(urljoin(base, link.get_attribute("href")))
                        assert f"/{version}/" in link.get_attribute("href")
                        metadata = context.request.get(base.rstrip("/") + f"/participation-coalition-scenarios/{version}/download.json")
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
    parser.add_argument("--version", choices=["20261107-01", "20261107-02"], default="20261107-02")
    args = parser.parse_args()
    check(args.base_url, args.proof, args.version)

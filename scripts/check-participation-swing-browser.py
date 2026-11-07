"""Verify experimental scenarios, descriptive controls and accessible build fallbacks."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright


def check(base_url, proof):
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for name, options, fail_inputs in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}, False),
                ("mobile", {"viewport": {"width": 390, "height": 844}}, False),
                ("no_javascript", {"java_script_enabled": False}, False),
                ("failed_inputs", {}, True),
            ]:
                context = browser.new_context(**options)
                try:
                    if fail_inputs:
                        context.route("**/participation-swing/**/aggregate-cohort.json",
                                      lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base_url.rstrip("/") + "/voter-participation/",
                              wait_until="domcontentloaded")
                    panel = page.locator("#participation-swing")
                    model = panel.locator("[data-conditional-swing]")
                    expect(model).to_contain_text("Experimental model")
                    expect(model).to_contain_text("Durham, North Carolina")
                    expect(model).to_contain_text("86 model scenarios")
                    expect(model).to_contain_text("not measured individual switching")
                    expect(model).to_contain_text("not confidence or identification intervals")
                    expect(model).to_contain_text("6.9 pp")
                    expect(model.locator("tbody").first.locator("tr")).to_have_count(5)
                    expect(model.locator("[data-model-dimension]")).to_have_count(4)
                    for details in model.locator("[data-model-dimension]").all():
                        details.evaluate("element => element.open = true")
                        expect(details.locator("tbody tr").first).to_be_visible()
                    original = model.inner_text()
                    county = panel.locator("[data-swing-county]")
                    if fail_inputs:
                        expect(panel.locator("[data-swing-status]")).to_contain_text(
                            "Interactive inputs could not be loaded")
                        expect(county).to_be_disabled()
                    elif options.get("java_script_enabled") is not False:
                        expect(county).to_be_enabled()
                        county.select_option("WAKE")
                        expect(panel.locator("[data-swing-status]")).to_contain_text("WAKE")
                        panel.locator("[data-swing-dimension]").select_option("education")
                        expect(panel.locator("[data-swing-rows] tr")).to_have_count(0)
                        expect(panel.locator("[data-swing-status]")).to_contain_text(
                            "Absent from this cohort source")
                        panel.locator("[data-swing-dimension]").select_option("race")
                        panel.locator("[data-swing-method]").select_option("MAIL")
                        expect(panel.locator("[data-swing-status]")).to_contain_text("MAIL")
                        assert panel.locator("[data-swing-rows] tr").count() > 0
                    else:
                        expect(county).to_be_disabled()
                        assert panel.locator("[data-swing-rows] tr").count() > 0
                    assert model.inner_text() == original, "Controls changed the fixed Durham model"
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                        f"Horizontal page overflow in {name}")
                    if name == "desktop":
                        panel.locator("details").last.evaluate("element => element.open = true")
                        link = panel.get_by_role("link", name="Complete aggregate analysis")
                        response = context.request.get(urljoin(base_url, link.get_attribute("href")))
                        assert response.ok
                        metadata = context.request.get(
                            urljoin(base_url, panel.get_attribute("data-base") + "download.json")).json()
                        data = response.body()
                        assert len(data) == metadata["bytes"]
                        assert hashlib.sha256(data).hexdigest() == metadata["sha256"]
                    results.append({"scenario": name, "passed": True})
                finally:
                    context.close()
        finally:
            browser.close()
    if proof:
        proof.write_text(json.dumps({"base_url": base_url, "checks": results}, indent=2) + "\n")
    print(json.dumps(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4331")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    check(args.base_url, args.proof)

"""Verify every broad native-group intention in four browser modes and full ZIP bytes."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PATH = "/participation-slu-demographic-intentions/20261107-01/"


def check(base, proof):
    expected = json.loads((ROOT / "public" / PATH.lstrip("/") / "intentions.json").read_bytes())
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
                        context.route("**/participation-slu-demographic-intentions/**/*.json",
                                      lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-house-demographic-intentions")
                    panel.locator("summary").click()
                    expect(panel.locator("[data-slu-demographic]")).to_have_count(10)
                    for group in expected["groups"]:
                        for row in group["rows"]:
                            identity = f'{group["native_variable"]}:{group["native_code"]}:{row["reported_2024_choice"]}'
                            rendered = panel.locator(f'[data-slu-demographic="{identity}"]')
                            expect(rendered).to_contain_text(group["display_label"])
                            expect(rendered.locator("[data-demographic-base]")).to_have_text(str(row["raw_prior_base"]))
                            expect(rendered.locator("[data-demographic-kish]")).to_have_text(
                                f'{row["kish_weight_concentration_base"]:.1f}')
                            for party, value in row["intended_house_pct"].items():
                                expect(rendered.locator(f'[data-demographic-choice="{party}"]')).to_have_text(
                                    f"{value:.1f}%")
                    for text in ("not a precision guarantee", "not additive", "not measured individual residence type",
                                 "does not establish population absence", "No November scaling",
                                 "No subgroup design confidence intervals", "August intentions only"):
                        expect(panel).to_contain_text(text)
                    expect(page.locator("#participation-house-intentions [data-slu-prior]")).to_have_count(2)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        for prefix in (PATH, "/participation-slu-intentions/20261107-01/"):
                            url = base.rstrip("/") + prefix
                            response = context.request.get(url + "complete-analysis.zip")
                            metadata = context.request.get(url + "download.json")
                            assert response.ok and metadata.ok
                            body, info = response.body(), metadata.json()
                            assert len(body) == info["bytes"]
                            assert hashlib.sha256(body).hexdigest() == info["sha256"]
                            assert body == (ROOT / "public" / prefix.lstrip("/") / "complete-analysis.zip").read_bytes()
                    results.append({"mode": mode, "passed": True, "joint_choices_verified": 40})
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

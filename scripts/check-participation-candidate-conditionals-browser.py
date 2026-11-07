"""Verify unscaled state choices and preserved composition/candidate gates."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


def check(base, proof):
    results = []
    prefix = "/participation-candidate-conditionals/20261107-01/"
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
                        context.route("**/participation-candidate-conditionals/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    panel = page.locator("#participation-candidate-conditionals")
                    expect(panel.locator("[data-candidate-contest]")).to_have_count(4)
                    expect(panel.locator("[data-current-candidate]")).to_have_count(12)
                    alaska = panel.locator('[data-candidate-contest="AK-SG"]')
                    expect(alaska.locator('[data-current-candidate="70718"] [data-prior-trump]')).to_have_text("5%")
                    expect(alaska.locator('[data-current-candidate="64262"]')).to_contain_text("Dan S. Sullivan")
                    expect(alaska.locator('[data-current-candidate="64262"] [data-prior-trump]')).to_have_text("90%")
                    expect(alaska.locator('[data-current-candidate="177716"]')).to_contain_text("Daniel J. Sullivan")
                    expect(alaska.locator('[data-current-candidate="177716"] [data-candidate-party]')).to_have_text("Independent (I)")
                    expect(alaska.locator('[data-current-candidate="177716"] [data-prior-trump]')).to_have_text("1%")
                    expect(panel.locator('[data-candidate-contest="NH-SG"] [data-current-candidate="56360"] [data-prior-trump]')).to_have_text("7%")
                    expect(panel.locator('[data-candidate-contest="NH-GG"] [data-candidate-gap]')).to_contain_text(
                        "95%: an unexplained gap of 5 percentage points")
                    for text in ("original comparison gates remain withheld", "not renormalize",
                                 "Republican candidates are not pooled", "not reassigned",
                                 "not proof of zero switching", "No measured staying home"):
                        expect(panel).to_contain_text(text)
                    expect(page.locator("#participation-age-scenarios [data-age-coalition]")).to_have_count(6)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        response = context.request.get(base.rstrip("/") + prefix + "complete-analysis.zip")
                        metadata = context.request.get(base.rstrip("/") + prefix + "download.json")
                        assert response.ok and metadata.ok
                        raw, info = response.body(), metadata.json()
                        assert len(raw) == info["bytes"] and hashlib.sha256(raw).hexdigest() == info["sha256"]
                        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                            for name, item in json.loads(archive.read("checksums.json")).items():
                                member = archive.read(name)
                                assert len(member) == item["bytes"]
                                assert hashlib.sha256(member).hexdigest() == item["sha256"]
                            full = json.loads(archive.read("public" + prefix + "candidate-conditionals.json"))
                            assert not full["population_or_original_coalition_scaling_performed"]
                            assert all(row[field] is None for row in full["contests"] for field in (
                                "estimated_switcher_count", "apparent_absence_count", "share_of_total_swing"))
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

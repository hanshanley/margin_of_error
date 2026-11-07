"""Verify withheld age scalars, retained support and complete archived calculations."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


def check(base, proof):
    results = []
    prefix = "/participation-age-cohort-scenarios/20261107-01/"
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
                        context.route("**/participation-age-cohort-scenarios/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-age-scenarios")
                    expect(panel.locator("[data-age-coalition]")).to_have_count(0)
                    expect(panel.locator("[data-age-stress-absence]")).to_have_count(0)
                    expect(panel).to_contain_text("Historical evidence decision")
                    expect(panel.locator("[data-age-diagnostics]")).to_have_count(6)
                    expect(panel.locator('[data-age-diagnostics="53-R"] [data-age-raw-base]')).to_have_text("194")
                    expect(panel.locator('[data-age-diagnostics="53-R"] [data-age-effective-base]')).to_have_text("114.2")
                    for text in ("No measured staying-home rate is identified", "not a linked panel",
                                 "50 states excluding D.C.",
                                 "No state, county or precinct allocation"):
                        expect(panel).to_contain_text(text)
                    expect(page.locator("#participation-demographic-counts")).to_contain_text("299 qualified")
                    expect(page.locator("#participation-independent-poll [data-mevp-group]")).to_have_count(5)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        response = context.request.get(base.rstrip("/") + prefix + "complete-analysis.zip")
                        metadata = context.request.get(base.rstrip("/") + prefix + "download.json")
                        assert response.ok and metadata.ok
                        raw, info = response.body(), metadata.json()
                        assert len(raw) == info["bytes"] and hashlib.sha256(raw).hexdigest() == info["sha256"]
                        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                            for name, row in json.loads(archive.read("checksums.json")).items():
                                member = archive.read(name)
                                assert len(member) == row["bytes"]
                                assert hashlib.sha256(member).hexdigest() == row["sha256"]
                            full = json.loads(archive.read("public" + prefix + "complete-scenarios.json"))
                            assert sum(len(row["sensitivity_scenarios"]) for row in full["estimates"]) == 2916
                            assert all(row[field] is None for row in full["estimates"] for field in (
                                "measured_staying_home_count", "identified_new_or_returning_count",
                                "demographic_turnout_rate", "share_of_total_swing", "design_confidence_interval"))
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

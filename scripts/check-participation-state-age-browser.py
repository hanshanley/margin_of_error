"""Verify withheld state-age scalars, retained support and complete archive bytes."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "/participation-state-age-scenarios/20261107-01/"


def check(base, proof):
    expected = json.loads((ROOT / ("public" + PREFIX) / "summary.json").read_text())
    checks = []
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
                        context.route("**/participation-state-age-scenarios/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-state-age-scenarios")
                    expect(panel.locator("[data-state-age-coalition]")).to_have_count(0)
                    expect(panel.locator("[data-state-age-stress]")).to_have_count(0)
                    expect(panel).to_contain_text("Historical evidence decision")
                    expect(panel.locator("[data-state-age-support]")).to_have_count(16)
                    expect(panel.locator("[data-state-age-coverage]")).to_have_count(51)
                    for index, row in enumerate(expected["estimates"]):
                        support = panel.locator("[data-state-age-support]").nth(index)
                        expect(support.locator("td").nth(1)).to_have_text(
                            f'{row["historical_certain_group_raw_n"]:,}')
                        expect(support.locator("td").nth(2)).to_have_text(
                            f'{row["historical_certain_group_effective_n"]:.1f}')
                    for text in ("Six states, eight separate", "not measured staying home or turnout rates",
                                 "especially consequential for older cohorts",
                                 "not a precision", "all 7,776 scenarios", "not zero turnout",
                                 "No national estimate is allocated"):
                        expect(panel).to_contain_text(text)
                    expect(page.locator("#participation-age-scenarios [data-age-coalition]")).to_have_count(0)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        metadata = context.request.get(base.rstrip("/") + PREFIX + "download.json")
                        response = context.request.get(base.rstrip("/") + PREFIX + "complete-analysis.zip")
                        assert metadata.ok and response.ok
                        raw, info = response.body(), metadata.json()
                        assert len(raw) == info["bytes"] and hashlib.sha256(raw).hexdigest() == info["sha256"]
                        assert raw == (ROOT / ("public" + PREFIX) / "complete-analysis.zip").read_bytes()
                        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                            for name, row in json.loads(archive.read("checksums.json")).items():
                                member = archive.read(name)
                                assert len(member) == row["bytes"]
                                assert hashlib.sha256(member).hexdigest() == row["sha256"]
                            full = json.loads(archive.read("public" + PREFIX + "complete-scenarios.json"))
                            assert sum(len(row["sensitivity_scenarios"]) for row in full["estimates"]) == 7776
                            assert len(full["jurisdiction_coverage"]) == 51
                            assert all(row[field] is None for row in full["estimates"] for field in (
                                "measured_staying_home_count", "identified_new_or_returning_count",
                                "demographic_turnout_rate", "share_of_total_swing", "design_confidence_interval"))
                    checks.append({"mode": mode, "passed": True})
                finally:
                    context.close()
        finally:
            browser.close()
    if proof:
        proof.write_text(json.dumps({"base_url": base, "checks": checks}, indent=2) + "\n")
    print(json.dumps(checks))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4331")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    check(args.base_url, args.proof)

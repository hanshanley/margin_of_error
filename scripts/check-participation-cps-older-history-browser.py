"""Verify earlier Census native cells, unavailable age bins and immutable full downloads."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-cps-older-history/20261107-01/output"
STATUSES = {-1: "Not published (B or (B))", -2: "Withheld: small population base",
            -3: "Zero or rounds to zero", -4: "Age group not supplied this year"}


def check(base, proof, verify_downloads=True):
    reference = json.loads((DATA / "display.json").read_bytes())
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
                        context.route("**/*.json*", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-cps-older-history")
                    expect(panel).to_be_visible()
                    for text in ("all 50 states and D.C.", "90% margin of error", "Missing is not zero.",
                                 "not candidate preference", "not fixed-person cohorts"):
                        expect(panel).to_contain_text(text)
                    rows = panel.locator("[data-cps-older-state]")
                    expect(rows).to_have_count(52)
                    select = panel.locator("#cps-older-group")
                    interactive = mode in ("desktop", "mobile")
                    if interactive:
                        expect(select).to_be_visible(timeout=30000)
                        expect(select.locator("option")).to_have_count(19)
                    elif mode == "failed_json":
                        expect(panel.locator("#cps-older-selection")).to_contain_text("Demographic controls unavailable.")
                        expect(select).not_to_be_visible()
                    else:
                        expect(select).not_to_be_visible()
                    cells = unavailable = 0
                    for group in range(len(reference["groups"]) if interactive else 1):
                        if interactive:
                            select.select_option(str(group))
                            expect(panel.locator("#cps-older-selection")).to_contain_text(
                                "All adult citizens" if group == 0 else reference["groups"][group])
                        actual = rows.evaluate_all(
                            "(rows) => rows.map(row => ({name: row.querySelector('th').textContent,"
                            " values: [...row.querySelectorAll('td')].map(cell => cell.textContent)}))")
                        for state_index, state in enumerate(reference["states"]):
                            assert actual[state_index]["name"] == state
                            for year_index in range(4):
                                value = reference["values"][state_index][group][year_index]
                                expected = (f"{value[0]:.1f}% +/- {value[1]:.1f} pp"
                                            if len(value) == 2 else STATUSES[value[0]])
                                assert actual[state_index]["values"][year_index] == expected, (
                                    mode, state, reference["groups"][group], year_index, expected)
                                cells += 1
                                unavailable += value == [-4]
                    assert cells == (3952 if interactive else 208)
                    assert unavailable == (624 if interactive else 0)
                    panel.locator("[data-cps-older-methods] > summary").click()
                    for text in ("not a legal-eligibility count", "population, not sample size",
                                 "100,000 citizens", "No suppressed rate is recovered",
                                 "in thousands", "all 3,328 unique observations", "No 2026 switching",
                                 "requirements-cps-older-history.txt"):
                        expect(panel).to_contain_text(text)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    for old in ("#participation-cps-state-history", "#participation-columbia-wisconsin-history",
                                "#participation-hamilton-indiana-history", "#participation-ces-classification"):
                        expect(page.locator(old)).to_be_visible()
                    expect(panel.locator("[data-cps-older-download]")).to_have_count(2)
                    downloads = []
                    if mode == "desktop" and verify_downloads:
                        for kind, filename in (("complete", "complete-analysis.zip"),
                                               ("observations", "observations.csv")):
                            url = panel.locator(f'[data-cps-older-download="{kind}"]').get_attribute("href")
                            response = context.request.get(url, timeout=60000)
                            assert response.ok, (url, response.status)
                            raw = response.body()
                            assert raw == (DATA / filename).read_bytes()
                            downloads.append({"file": filename, "bytes": len(raw),
                                              "sha256": hashlib.sha256(raw).hexdigest()})
                            if kind == "complete":
                                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                                    inventory = json.loads(archive.read("checksums.json"))
                                    assert len(archive.namelist()) == 22 and len(inventory) == 21
                                    assert set(archive.namelist()) == {*inventory, "checksums.json"}
                                    for name, receipt in inventory.items():
                                        member = archive.read(name)
                                        assert len(member) == receipt["bytes"]
                                        assert hashlib.sha256(member).hexdigest() == receipt["sha256"]
                    checks.append({"mode": mode, "passed": True, "verified_cells": cells,
                                   "unsupported_age_year_cells": unavailable, "all_groups": interactive,
                                   "downloads": downloads, "source_limits_and_preserved_panels": True})
                finally:
                    context.close()
        finally:
            browser.close()
    result = {"base_url": base, "checks": checks}
    if proof:
        with proof.open("x") as target:
            json.dump(result, target, indent=2)
            target.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4373")
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--skip-downloads", action="store_true", help="Pre-release local UI check only")
    args = parser.parse_args()
    check(args.base_url, args.proof, not args.skip_downloads)

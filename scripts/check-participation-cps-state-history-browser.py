"""Verify every Census display value, native suppression and complete release assets."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-cps-state-history/20261107-01/output"
STATUSES = {-1: "Not published (B)", -2: "Withheld: small population base",
            -3: "Zero or rounds to zero"}


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
                    panel = page.locator("#participation-cps-state-history")
                    expect(panel).to_be_visible()
                    for text in ("all 50 states and D.C.", "90% margin of error",
                                 "Missing is not zero.", "population, not sample size",
                                 "not candidate preference", "not fixed-person cohorts"):
                        expect(panel).to_contain_text(text)
                    rows = panel.locator("[data-cps-state]")
                    expect(rows).to_have_count(52)
                    select = panel.locator("#cps-state-group")
                    cells = 0
                    for group in range(1 if mode == "no_javascript" else len(reference["groups"])):
                        if mode != "no_javascript":
                            expect(select).to_be_visible()
                            select.select_option(str(group))
                            expect(panel.locator("#cps-state-selection")).to_contain_text(
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
                    if mode == "no_javascript":
                        expect(select).not_to_be_visible()
                    panel.locator("[data-cps-methods] > summary").click()
                    for text in ("not a legal-eligibility count", "views overlap",
                                 "No suppressed rate is recovered", "in thousands",
                                 "all 3,328 unique observations", "No 2026 switching"):
                        expect(panel).to_contain_text(text)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    for old in ("#participation-hamilton-indiana-history", "#participation-ces-classification",
                                "#participation-nd-long-history", "#participation-clark-history"):
                        expect(page.locator(old)).to_be_visible()
                    links = panel.locator("[data-cps-download]")
                    expect(links).to_have_count(2)
                    downloads = []
                    if mode == "desktop" and verify_downloads:
                        for kind, filename in (("complete", "complete-analysis.zip"),
                                               ("observations", "observations.csv")):
                            url = panel.locator(f'[data-cps-download="{kind}"]').get_attribute("href")
                            response = context.request.get(url, timeout=60000)
                            assert response.ok, (url, response.status)
                            raw, native = response.body(), (DATA / filename).read_bytes()
                            assert raw == native
                            downloads.append({"file": filename, "bytes": len(raw),
                                              "sha256": hashlib.sha256(raw).hexdigest()})
                            if kind == "complete":
                                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                                    inventory = json.loads(archive.read("checksums.json"))
                                    assert set(archive.namelist()) == {*inventory, "checksums.json"}
                                    for name, receipt in inventory.items():
                                        member = archive.read(name)
                                        assert len(member) == receipt["bytes"]
                                        assert hashlib.sha256(member).hexdigest() == receipt["sha256"]
                    checks.append({"mode": mode, "passed": True, "verified_cells": cells,
                                   "all_groups": mode != "no_javascript", "downloads": downloads,
                                   "source_limits_and_preserved_panels": True})
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
    parser.add_argument("--base-url", default="http://127.0.0.1:4367")
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--skip-downloads", action="store_true", help="Pre-release local UI check only")
    args = parser.parse_args()
    check(args.base_url, args.proof, not args.skip_downloads)

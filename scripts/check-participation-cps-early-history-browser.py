"""Verify every early Census native display observation and separate denominators."""

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-cps-early-history/20261107-01/output"
STATUSES = {
    "native_B_not_published": "Not published (B)",
    "withheld_unlabeled_native_geography": "Withheld: unlabeled geography",
    "withheld_conflicting_same_year_total": "Withheld: conflicting native totals",
    "withheld_conflicting_extra_native_label": "Withheld: conflicting extra label",
    "withheld_native_out_of_range_metric": "Withheld: native out-of-range metric",
    "withheld_small_rounded_population_base": "Withheld: small population base",
}


def check(base, proof, verify_downloads=True):
    source = (DATA / "display.json").read_bytes()
    reference = json.loads(source)
    indexed = {(r["geography"], r["year"], r["role"] + "|" + r["native_group"].strip()): r
               for r in reference}
    assert len(indexed) == len(reference) == 2375
    views = list(dict.fromkeys(r["role"] + "|" + r["native_group"].strip() for r in reference))
    expected_statuses = Counter(r["display"]["status"] for r in reference)
    assert len(views) == 25
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
                    else:
                        context.route("**/8e3c850e99e22750ae55362e8d188654e58d527c/**/display.json",
                                      lambda route: route.fulfill(body=source, content_type="application/json",
                                                                  headers={"Access-Control-Allow-Origin": "*"}))
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    panel = page.locator("#participation-cps-early-history")
                    expect(panel).to_be_visible()
                    assert panel.get_attribute("data-display-sha256") == hashlib.sha256(source).hexdigest()
                    assert "/8e3c850e99e22750ae55362e8d188654e58d527c/" in panel.get_attribute("data-display-url")
                    for text in ("all 50 states and D.C.", "not one comparable rate series",
                                 "90% margin of error", "not candidate preference", "Missing is not zero."):
                        expect(panel).to_contain_text(text)
                    for table, years in (("adults", [2004]), ("citizens", [2006, 2008])):
                        block = panel.locator(f'[data-cps-early-table="{table}"]')
                        expect(block.locator("tbody tr")).to_have_count(53)
                        actual_years = block.locator("td").evaluate_all(
                            "(cells) => [...new Set(cells.map(cell => Number(cell.dataset.cpsEarlyYear)))]")
                        assert actual_years == years
                        expect(block.locator("caption")).to_contain_text(
                            "All adults 18+" if table == "adults" else "Adult citizens 18+")
                    select = panel.locator("#cps-early-group")
                    interactive = mode in ("desktop", "mobile")
                    if interactive:
                        expect(select).to_be_visible(timeout=30000)
                        assert select.locator("option").evaluate_all("(xs) => xs.map(x => x.value)") == views
                    else:
                        expect(select).not_to_be_visible()
                        if mode == "failed_json":
                            expect(panel.locator("#cps-early-selection")).to_contain_text("Demographic controls unavailable.")
                    cells = missing = 0
                    statuses = Counter()
                    visited = set()
                    for view in views if interactive else ["sex_race|.Total"]:
                        if interactive:
                            select.select_option(view)
                            expect(panel.locator("#cps-early-selection")).to_contain_text(
                                "2004: all adults; 2006/2008: adult citizens.")
                        actual = panel.locator("[data-cps-early-year]").evaluate_all(
                            "(xs) => xs.map(x => [x.dataset.cpsEarlyGeography, Number(x.dataset.cpsEarlyYear), x.textContent.trim()])")
                        assert len(actual) == 159
                        for geography, year, value in actual:
                            key = (geography, year, view)
                            assert key not in visited
                            visited.add(key)
                            row = indexed.get(key)
                            if row is None:
                                expected = "Not supplied for this geography/view"
                                missing += 1
                            else:
                                display = row["display"]
                                status = display["status"]
                                statuses[status] += 1
                                assert display["denominator"] == (
                                    "all_adults_18_plus" if year == 2004 else "citizen_adults_18_plus")
                                expected = (f'{display["rate_pct"]:.1f}% +/- {display["native_moe90_pp"]:.1f} pp'
                                            if status == "published_native_rate" else STATUSES[status])
                            assert value == expected, (mode, key, expected, value)
                            cells += 1
                    assert cells == (3975 if interactive else 159)
                    if interactive:
                        assert set(indexed) <= visited and statuses == expected_statuses
                        assert missing == 1600
                    panel.locator("[data-cps-early-methods] > summary").click()
                    for text in ("not fixed-person cohorts", "not a legal-eligibility count",
                                 "101 agree and three conflict", "All six conflicting totals are withheld",
                                 "registration percentage 423", "all 22 rows", "no suppressed rate is recovered",
                                 "not sample sizes", "all 2,375 observations", "No 2026 switching",
                                 "requirements-cps-older-history.txt"):
                        expect(panel).to_contain_text(text)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    for old in ("#participation-cps-older-history", "#participation-cps-state-history",
                                "#participation-columbia-wisconsin-history", "#participation-ces-classification"):
                        expect(page.locator(old)).to_be_visible()
                    expect(panel.locator("[data-cps-early-download]")).to_have_count(2)
                    downloads = []
                    if mode == "desktop" and verify_downloads:
                        for kind, filename in (("complete", "complete-analysis.zip"),
                                               ("observations", "observations.csv")):
                            url = panel.locator(f'[data-cps-early-download="{kind}"]').get_attribute("href")
                            response = context.request.get(url, timeout=60000)
                            assert response.ok, (url, response.status)
                            raw = response.body()
                            assert raw == (DATA / filename).read_bytes()
                            downloads.append({"file": filename, "bytes": len(raw),
                                              "sha256": hashlib.sha256(raw).hexdigest()})
                            if kind == "complete":
                                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                                    inventory = json.loads(archive.read("checksums.json"))
                                    assert len(archive.namelist()) == 19 and len(inventory) == 18
                                    assert set(archive.namelist()) == {*inventory, "checksums.json"}
                                    for name, receipt in inventory.items():
                                        member = archive.read(name)
                                        assert len(member) == receipt["bytes"]
                                        assert hashlib.sha256(member).hexdigest() == receipt["sha256"]
                    checks.append({"mode": mode, "passed": True, "verified_cells": cells,
                                   "verified_native_observations": sum(statuses.values()),
                                   "native_dispositions": dict(statuses), "unavailable_cells": missing,
                                   "all_groups": interactive, "downloads": downloads,
                                   "separate_denominators_and_preserved_panels": True})
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
    parser.add_argument("--base-url", default="http://127.0.0.1:4375")
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--skip-downloads", action="store_true", help="Pre-release local UI check only")
    args = parser.parse_args()
    check(args.base_url, args.proof, not args.skip_downloads)

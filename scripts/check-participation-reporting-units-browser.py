"""Verify held-boundary source counts remain accessible without fabricated precinct maps."""

import argparse
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
results = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            for name, code, count in (("Alaska", "AK", 523), ("Hawaii", "HI", 496)):
                source = json.loads(gzip.decompress(
                    (ROOT / f"data/precinct-source-reviews/20261105/{code}/participation.json.gz").read_bytes()))
                page.goto(base + f"/voter-participation/?view=precincts&year=2026&state={name}&layer=participation",
                          wait_until="domcontentloaded")
                expect(page.locator("#title")).to_have_text(f"Reported participation counts in {name}", timeout=90000)
                expect(page.locator("#year")).to_have_value("2026")
                expect(page.locator("#precinct-layer")).to_have_value("participation")
                assert page.locator(".geographic-detail .map-feature").count() == 0
                expect(page.locator("#coverage-note")).to_contain_text(f"{count:,} source reporting-unit observations")
                select = page.locator("#source-reporting-unit-select")
                expect(select.locator("option")).to_have_count(count)
                assert set(select.locator("option").evaluate_all("els=>els.map(e=>e.value)")) == {row["key"] for row in source}
                choices = [source[0], source[-1]]
                choices.append(next(row for row in source if row["reporting_unit_kind"]
                                    == ("federal_overseas" if code == "AK" else "native_vsc_split")))
                for row in choices:
                    select.select_option(row["key"])
                    expect(page.locator("#source-reporting-unit-detail .selection-rate")).to_have_text(f'{row["ballots"]:,}')
                    expect(page.locator("#source-reporting-unit-detail")).to_contain_text("no participation rate")
                page.get_by_role("button", name=f"View all {count:,} source observations").click()
                expect(page.locator("#table-panel")).to_have_attribute("open", "")
                page.locator("#search").fill(source[0]["precinct"])
                expect(page.locator("#table-body")).to_contain_text(source[0]["precinct"])
                page.locator("#tab-methods").click()
                expect(page.locator("#methods-panel")).to_be_visible()
                expect(page.locator("#methods-archive")).to_be_hidden()
                page.locator("#tab-precincts").click()
                expect(page.locator("#title")).to_have_text(f"Reported participation counts in {name}", timeout=90000)
                expect(select).to_have_value(choices[-1]["key"])
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                results.append({"state": name, "rows": count, "mobile": mobile,
                                "exact_unit_ids": True, "native_counts_checked": len(choices),
                                "no_invented_rates_or_geometry": True})
            assert not errors, errors
            context.close()
        context = browser.new_context(viewport={"width": 1200, "height": 900})
        pointer = json.loads((ROOT / "public/participation-reporting-units.json").read_bytes())
        url = pointer["sources"]["AK"]["data_url"]
        context.route(url, lambda route: route.abort())
        page = context.new_page()
        page.goto(base + "/voter-participation/?view=precincts&year=2026&state=Alaska&layer=participation",
                  wait_until="domcontentloaded")
        retry = page.get_by_role("button", name="Retry precinct source")
        expect(retry).to_be_visible(timeout=90000)
        expect(page.locator("#selection-panel > h3")).to_have_text("Alaska")
        context.unroute(url)
        retry.click()
        expect(page.locator("#source-reporting-unit-select option")).to_have_count(523, timeout=60000)
        context.close()
    finally:
        browser.close()
proof = {"status": "PASS_source_reporting_units", "base_url": base, "source_failure_recovers": True,
         "cases": results}
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

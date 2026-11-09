"""Verify held-boundary source counts remain accessible without fabricated precinct maps."""

import argparse
import gzip
import hashlib
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
pointer = json.loads((ROOT / "public/participation-reporting-units.json").read_bytes())
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            for name, code, count in (("Alaska", "AK", 523), ("Hawaii", "HI", 496),
                                      ("Arizona", "AZ", 1763), ("Arkansas", "AR", 2768),
                                      ("Wyoming", "WY", 432)):
                descriptor = pointer["sources"][code]
                path = (f"data/precinct-source-reviews/20261105/{code}/participation.json.gz"
                        if code in ("AK", "HI") else descriptor["data_url"].replace("/", "public/", 1))
                raw = (ROOT / path).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == descriptor["sha256"]
                source = json.loads(gzip.decompress(raw))
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
                kind = {"AK": "federal_overseas", "HI": "native_vsc_split",
                        "AZ": "native_virtual_reporting_unit"}.get(code)
                if kind:
                    choices.append(next(row for row in source if row["reporting_unit_kind"] == kind))
                choices.extend(next(row for row in source if row["ballots"] == value)
                               for value in (None, 0) if any(row["ballots"] == value for row in source))
                for row in choices:
                    select.select_option(row["key"])
                    expect(page.locator("#source-reporting-unit-detail .selection-rate")).to_have_text(
                        "Not supplied" if row["ballots"] is None else f'{row["ballots"]:,}')
                    expect(page.locator("#source-reporting-unit-detail")).to_contain_text("no participation rate")
                    registrations = f'{row["registered"]:,}' if row["registered"] is not None else "—"
                    expect(page.locator("#source-reporting-unit-detail")).to_contain_text(
                        f"Native registrations: {registrations}")
                    if row["ballots"] is None:
                        expect(page.locator("#source-reporting-unit-detail")).to_contain_text("missing, not zero")
                expect(page.get_by_role("link", name="Complete original sources and every reporting-unit query (ZIP)")).to_have_attribute(
                    "href", descriptor["complete_download_url"])
                expect(page.get_by_role("link", name="All native reporting-unit observations (JSON · gzip)")).to_have_attribute(
                    "href", descriptor["data_url"])
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
                page.reload(wait_until="domcontentloaded")
                expect(page.locator("#source-reporting-unit-select")).to_have_value(choices[-1]["key"], timeout=90000)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                results.append({"state": name, "rows": count, "mobile": mobile,
                                "exact_unit_ids": True, "native_counts_checked": len(choices),
                                "missing_ballots": sum(row["ballots"] is None for row in source),
                                "native_zeros_preserved": any(row["ballots"] == 0 for row in choices),
                                "complete_download_links": True, "deep_link_preserved": True,
                                "no_invented_rates_or_geometry": True})
            assert not errors, errors
            context.close()
        context = browser.new_context(viewport={"width": 1200, "height": 900})
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
        context = browser.new_context(viewport={"width": 1200, "height": 900})
        url = base + pointer["sources"]["AZ"]["data_url"]
        context.route(url, lambda route: route.fulfill(body=b"corrupted source", content_type="application/gzip"))
        page = context.new_page()
        page.goto(base + "/voter-participation/?view=precincts&year=2026&state=Arizona&layer=participation",
                  wait_until="domcontentloaded")
        expect(page.get_by_role("button", name="Retry precinct source")).to_be_visible(timeout=90000)
        expect(page.locator("#coverage-note")).to_contain_text("checksum disagrees")
        assert page.locator("#source-reporting-unit-select").count() == 0
        context.unroute(url)
        page.get_by_role("button", name="Retry precinct source").click()
        expect(page.locator("#source-reporting-unit-select option")).to_have_count(1763, timeout=60000)
        context.close()
    finally:
        browser.close()
proof = {"status": "PASS_source_reporting_units", "base_url": base, "source_failure_recovers": True,
         "checksum_failure_recovers": True,
         "cases": results}
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

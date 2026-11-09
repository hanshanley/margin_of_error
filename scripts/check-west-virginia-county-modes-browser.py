"""Verify exact WV native counts and explicit method separation on desktop/mobile."""

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
version = ROOT / "data/county-source-reviews/20261109-west-virginia-modes-01"
native = json.loads(gzip.decompress((version / "native-mode-queries.json.gz").read_bytes()))
full = {row["county_fips"]: row["source_count"] for row in
        json.loads((version / "native-county-parents.json").read_bytes())}
expected = {mode: {row["county_fips"]: row["native_record"] for row in source["counties"]}
            for mode, source in native.items()}
cases = []


def choose_state(page):
    select = page.locator("#state-select")
    select.select_option("West Virginia")
    path = page.locator('.map-feature[data-state="West Virginia"]')
    path.focus()
    path.press("Enter")


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            assert response.ok
            expect(page.locator("#year")).to_have_value("2026", timeout=90000)
            expect(page.locator('.map-feature[data-state="West Virginia"]')).to_have_count(1, timeout=90000)
            choose_state(page)
            shapes = page.locator('.geographic-detail [data-level="county"]')
            expect(shapes).to_have_count(55, timeout=90000)
            expect(page.locator("#title")).to_have_text("Local participation in West Virginia")
            checks = []
            for mode in ("available", "in_person_early", "mail_returned", "official", "in_person_early"):
                page.locator("#mode").select_option(mode)
                choose_state(page)
                expect(shapes).to_have_count(55, timeout=90000)
                expect(page.locator("#year")).to_have_value("2026")
                actual = shapes.evaluate_all("els=>els.map(e=>({fips:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear}))")
                assert len({row["fips"] for row in actual}) == 55
                for row in actual:
                    value = expected[mode][row["fips"]]["TOTAL VOTERS"] if mode in expected else full.get(row["fips"])
                    assert (int(row["count"]) if row["count"] else None) == value, (mode, row, value)
                    assert row["rate"] == "" and row["year"] == "2026"
                if mode in expected:
                    expect(page.locator("#caption")).to_contain_text("October 31")
                    expect(page.locator("#table-head")).to_contain_text(
                        "Early in-person" if mode == "in_person_early" else "Absentee returned")
                    assert shapes.evaluate_all("els=>new Set(els.map(e=>e.getAttribute('fill'))).size") > 1
                else:
                    expect(page.locator("#geography-note")).to_contain_text("3 available")
                    expect(page.locator("#geography-note")).to_contain_text("52 source totals")
                page.locator("#current-county-select").select_option("additional:WV:54107")
                count = {"in_person_early": 9828, "mail_returned": 340}.get(mode, 22935)
                expect(page.locator("#current-county-detail")).to_contain_text(f"{count:,}")
                if mode == "mail_returned":
                    expect(page.locator("#current-county-detail")).to_contain_text("not qualified cast ballots")
                if mode == "in_person_early":
                    expect(page.locator("#current-county-detail")).to_contain_text("not candidate choices")
                    page.locator("#tab-methods").click()
                    expect(page.locator("#methods-archive")).to_be_hidden()
                    page.locator("#tab-states").click()
                    expect(page.locator("#mode")).to_have_value(mode)
                    expect(page.locator("#state-select")).to_have_value("West Virginia")
                    expect(shapes).to_have_count(55, timeout=60000)
                checks.append(dict(mode=mode, all_native_values=True, counties=55))
            response = page.request.get(base + "/participation-local/WV.json.gz")
            assert response.ok
            data = json.loads(gzip.decompress(response.body()))
            assert len(data["counties"]) == 55 and not data["precincts"]
            for mode in ("in_person_early", "mail_returned"):
                assert len(data["county_frames"][mode]) == 55
                for row in data["county_frames"][mode]:
                    assert row["native_record"] == expected[mode][row["county_fips"]]
                    assert row["ballots"] == expected[mode][row["county_fips"]]["TOTAL VOTERS"]
                    assert row["denominator"] is None and row["reported_pct"] is None
                    assert row["cast_ballot_count_qualified"] is False
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(mobile=mobile, native_mode_checks=checks,
                all_method_holds_not_zero=True, methods_roundtrip=True, no_rates=True))
            context.close()
        context = browser.new_context()
        pattern = "**/participation-local/WV.json.gz"

        def broken_mode(route):
            response = route.fetch()
            data = json.loads(gzip.decompress(response.body()))
            data["county_frames"]["mail_returned"].pop()
            route.fulfill(body=gzip.compress(json.dumps(data).encode(), mtime=0),
                          content_type="application/gzip")

        context.route(pattern, broken_mode)
        page = context.new_page()
        page.goto(base + "/voter-participation/?view=states&year=2026&state=West+Virginia&mode=mail_returned&map-level=county",
                  wait_until="domcontentloaded")
        expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
        choose_state(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified WV county source mode", timeout=90000)
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(0)
        context.unroute(pattern)
        page.get_by_role("button", name="Retry geographic detail").click()
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(55, timeout=60000)
        expect(page.locator("#mode")).to_have_value("mail_returned")
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_WV_native_county_frames_not_additive", base_url=base, cases=cases,
    missing_mode_rejected_not_replaced_with_all_method=True,
    incomplete_mode_retry_recovered=True, valid_source_overrides=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

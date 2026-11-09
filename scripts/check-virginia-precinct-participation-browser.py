"""Verify literal native ballotsCast on Virginia's existing 710 reference joins."""

import argparse
import csv
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
pointer = json.loads((ROOT / "public/precinct-results.json").read_bytes())
descriptor = next(row for row in pointer["additional_snapshots"]
                  if row["data_directory"].endswith("virginia-02"))
raw = (ROOT / descriptor["data_directory"] / "2026/VA.geojson.gz").read_bytes()
assert hashlib.sha256(raw).hexdigest() == descriptor["participation_count_sha256"]
source = json.loads(gzip.decompress(raw))
with (ROOT / "data/precinct-source-reviews/20261105/VA-2026-native-locality-counts/precinct-turnout.csv").open() as stream:
    native = {(row["locality_code"], row["precinct_uuid"]): row for row in csv.DictReader(stream)}
expected = {}
for feature in source["features"]:
    p = feature["properties"]
    row = native[p["county_code"], p["precinct_uuid"]]
    assert p["precinct"] == row["precinct"]
    assert p["participation"]["ballots"] == int(row["ballots_cast"])
    assert p["participation"]["registered"] == int(row["registered_voters"])
    assert p["participation"]["reported_pct"] is None
    expected[p["key"]] = row
assert len(expected) == 710
different = next(key for key, row in expected.items() if row["ballots_cast"] != row["voter_turnout"])
cases = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/voter-participation/?view=precincts&year=2026&state=Virginia"
                      "&layer=participation", wait_until="domcontentloaded")
            expect(page.locator("#title")).to_have_text("Precinct participation counts in Virginia", timeout=90000)
            expect(page.locator("#year")).to_have_value("2026")
            shapes = page.locator('.geographic-detail [data-level="precinct"]')
            expect(shapes).to_have_count(710, timeout=60000)
            actual = shapes.evaluate_all("""els => els.map(e => ({
                key:e.dataset.geography,ballots:Number(e.dataset.count),
                registered:Number(e.dataset.registered),rate:e.dataset.rate,
                measure:e.dataset.countMeasure,fill:e.getAttribute('fill'),
                candidateMargin:e.hasAttribute('data-margin')
            }))""")
            assert {row["key"] for row in actual} == set(expected)
            for row in actual:
                original = expected[row["key"]]
                assert row["ballots"] == int(original["ballots_cast"])
                assert row["registered"] == int(original["registered_voters"])
                assert row["rate"] == ""
                assert row["measure"] == "native_ballotsCast"
                assert not row["candidateMargin"]
            assert len({row["fill"] for row in actual}) > 1
            expect(page.locator("#geography-note")).to_contain_text("not certified election-day")
            expect(page.locator("#table-head")).not_to_contain_text("Democratic")
            expect(page.locator("#caption").get_by_role(
                "link", name="Complete Virginia precinct counts and original sources (ZIP)")).to_have_attribute(
                    "href", descriptor["complete_download_url"])
            selected = page.locator(f'[data-geography="{different}"][data-level="precinct"]')
            selected.focus()
            selected.press("Enter")
            panel = page.locator("#substate-detail")
            expect(panel.locator(".selection-rate")).to_have_text(f'{int(expected[different]["ballots_cast"]):,}')
            expect(panel).to_contain_text("Literal native ballotsCast")
            expect(panel).to_contain_text("no precinct electorate denominator or participation rate")
            expect(panel).to_contain_text("not a qualified rate denominator")
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-panel")).to_be_visible()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-precincts").click()
            expect(shapes).to_have_count(710, timeout=60000)
            page.locator("#tab-states").click()
            page.select_option("#state-select", "Virginia")
            page.select_option("#year", "2026")
            page.locator("#show-matched-precinct-participation").click()
            expect(shapes).to_have_count(710, timeout=60000)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append({"mobile": mobile, "native_precincts_checked": 710,
                          "different_native_measures": sum(row["ballots_cast"] != row["voter_turnout"]
                                                          for row in expected.values()),
                          "all_rates_withheld": True, "state_sidebar_navigation": True,
                          "complete_download": True, "reference_not_certified_geometry": True,
                          "page_errors": errors})
            context.close()
        context = browser.new_context(viewport={"width": 1200, "height": 900})
        context.route("**/2026/VA.geojson.gz",
                      lambda route: route.fulfill(body=b"corrupted source", content_type="application/gzip"))
        page = context.new_page()
        page.goto(base + "/voter-participation/?view=precincts&year=2026&state=Virginia"
                  "&layer=participation", wait_until="domcontentloaded")
        retry = page.get_by_role("button", name="Retry precinct source")
        expect(retry).to_be_visible(timeout=90000)
        expect(page.locator("#coverage-note")).to_contain_text("checksum disagrees")
        assert page.locator('.geographic-detail [data-level="precinct"]').count() == 0
        context.unroute("**/2026/VA.geojson.gz")
        retry.click()
        expect(page.locator('.geographic-detail [data-level="precinct"]')).to_have_count(710, timeout=60000)
        context.close()
    finally:
        browser.close()
proof = {"status": "PASS_VA_literal_precinct_ballots", "base_url": base,
         "checksum_failure_recovers": True, "cases": cases}
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

"""Verify reviewed county participation and preserve previous records and downloads."""

import argparse
from collections import Counter
import csv
import datetime
import gzip
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--proof", type=Path, required=True)
batch_args = parser.add_mutually_exclusive_group()
batch_args.add_argument("--lebanon", action="store_true")
batch_args.add_argument("--blair", action="store_true")
batch_args.add_argument("--armstrong", action="store_true")
batch_args.add_argument("--wayne", action="store_true")
args = parser.parse_args()
assert not args.proof.exists()
root = Path(__file__).resolve().parents[1]
base = args.base_url.rstrip("/")
reviews = json.loads((root / "public/participation-source-reviews.json").read_text())["reviews"]
county = "Wayne" if args.wayne else "Armstrong" if args.armstrong else "Blair" if args.blair else "Lebanon" if args.lebanon else "Adams"
batch = county.lower()
review = next(row for row in reviews if row["id"] == f"pennsylvania-{batch}-20261106-01")
baseline = json.loads((root / f"data/county-source-reviews/20261106-{batch}-publication-01/baseline.json").read_text())
record_count = {"Adams": 14, "Lebanon": 15, "Blair": 16, "Armstrong": 17, "Wayne": 18}[county]
added = [review["complete_download_url"]] + [review["base_url"] + table["file"] for table in review["tables"]]
assert len(set(added)) == (8 if args.armstrong or args.wayne else 9) and not set(added) & set(baseline["expected_download_urls"])
expected_links = Counter(baseline["expected_download_urls"]) + Counter(added)
assert len(expected_links) == {"Adams": 315, "Lebanon": 334, "Blair": 343, "Armstrong": 351, "Wayne": 359}[county]
assert sum(expected_links.values()) == {"Adams": 318, "Lebanon": 337, "Blair": 346, "Armstrong": 354, "Wayne": 362}[county]
with (root / review["data_directory"] / "county-participation.csv").open() as source:
    native = next(csv.DictReader(source))
proof = {"base_url": base, "modes": [], "checks": []}
errors = []


def verify_detail(page):
    select = page.locator("#current-county-select")
    expect(select.locator("option")).to_have_count(record_count)
    select.select_option("42001" if county == "Adams" else f"reviewed:PA:{county}")
    detail = page.locator("#current-county-detail")
    expect(detail.locator(".selection-rate")).to_have_text(
        {"Adams": "42,660", "Lebanon": "51,268", "Blair": "43,898", "Armstrong": "24,039", "Wayne": "21,707"}[county])
    if args.armstrong:
        expect(detail.locator(".selection-basis")).to_have_text("2026 Voters Cast · not final/certified")
        expect(page.locator("#reviewed-county-overview button")).to_have_count(0)
        expect(detail).to_contain_text("24,039")
    texts = ("36,885 native registered voters", "58.85%", "2026 General Election Unofficial Results",
             "county_report: 2026-11-05 15:08:51 (timezone not declared)",
             "18-ballot scope difference", "Candidate parties are not supplied",
             "not mode-level ballots or registrations",
             "Result status comes from the declaring county page",
             "County mapping is not approved") if args.wayne else (
             "43,750 native registered voters", "54.95%", "w/o PROV",
             "county_report: 11/3/2026 10:26:30 PM (timezone not declared)",
             "Native participation is Voters Cast", "Provisional participation is absent, not zero",
             "not measured party turnout or zero participation",
             "County mapping is not approved") if args.armstrong else (
             "Native printed fraction: 0.00%", "Analysis fraction withheld / not supplied",
             "UNOFFICIAL RESULTS", "county: 11/05/2026 12:16 PM (timezone not declared)",
             "unit: 11/05/2026 1:02 PM (timezone not declared)",
             "268 provisionals still to process", "0/60 complete and 60/60 partially reported",
             "registrations are explicitly zero alongside positive ballots",
             "County mapping is not approved") if args.lebanon else (
                 "81,846 native registered voters", "53.63%", "UNOFFICIAL RESULTS",
                 "current: 11/03/2026 10:45 PM (timezone not declared)",
                 "pre_election_zero: 11/03/2026 6:00 AM (timezone not declared)",
                 "Zero Report is a 6:00 AM pre-election snapshot, not current zero participation",
                 "Blank ballots and pending ballots are not supplied, not zero",
                 "County mapping is not approved") if args.blair else (
                 "77,163 native registered voters", "55.29%", "UNOFFICIAL RESULTS",
                 "summary: 11/03/2026 10:23PM (timezone not declared)",
                 "precinct: 11/03/2026 10:23PM (timezone not declared)",
                 "0 of 53 complete and all 53 partially reported",
                 "10,320, not the index's separately scoped 10,348",
                 "Native provisional zeros remain explicit", "County mapping is not approved")
    for text in texts:
        expect(detail).to_contain_text(text)
    for url in (review["complete_download_url"], review["base_url"] + "county-participation.csv"):
        assert detail.locator('a[href="' + url + '"]').count() == 1


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for mobile in (False, True):
        for javascript in (True, False):
            context = browser.new_context(
                viewport={"width": 390 if mobile else 1440, "height": 844 if mobile else 1100},
                java_script_enabled=javascript, is_mobile=mobile, has_touch=mobile)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/voter-participation/?year=2026&state=Pennsylvania&mode=available&map-level=county&map-color=turnout",
                      wait_until="domcontentloaded")
            table = page.locator("table[data-reviewed-county-participation]")
            records = json.loads(table.get_attribute("data-reviewed-county-participation"))
            assert len(records) == record_count
            assert [row for row in records if row["county"] != county] == baseline["previous_reviewed_county_records"]
            selected = next(row for row in records if row["county"] == county)
            assert selected["native_record"] == native and selected["maps_approved"] is False
            if args.lebanon:
                assert selected["denominator"] is None and selected["reported_pct"] is None
                assert selected["native_record"]["native_registered_voters"] == "0"
            if args.armstrong:
                assert selected["participation_measure_literal"] == "Voters Cast"
                assert selected["ballots"] == 24039 and selected["denominator"] == 43750
                assert selected["native_record"]["provisional_voters_cast"] == ""
            if args.wayne:
                assert selected["ballots"] == 21707 and selected["denominator"] == 36885
                assert selected["source_status_literal"] == "2026 General Election Unofficial Results"
                assert selected["native_record"]["native_status_literal"] == ""
                for field in ("election_day_ballots", "mail_ballots", "provisional_ballots"):
                    assert selected["native_record"][field] == ""
            expect(table.locator("tbody tr")).to_have_count(record_count)
            cells = table.locator("tbody tr").filter(has_text=f"{county}, Pennsylvania").locator("td").all_text_contents()
            expected_cells = {
                "Adams": ["42,660", "77,163", "55.29%", "55.29%", "UNOFFICIAL RESULTS"],
                "Lebanon": ["51,268", "Withheld (native zero)", "Withheld", "0.00%", "UNOFFICIAL RESULTS"],
                "Blair": ["43,898", "81,846", "53.63%", "53.63%", "UNOFFICIAL RESULTS"],
                "Armstrong": ["24,039 · Voters Cast", "43,750", "54.95%", "54.95%",
                              "2026 General Election Unofficial Results w/o PROV"],
                "Wayne": ["21,707", "36,885", "58.85%", "58.85%", "2026 General Election Unofficial Results"],
            }[county]
            assert [text.strip() for text in cells[:5]] == expected_cells
            links = Counter(page.locator("#downloads a[download]").evaluate_all(
                "links => links.map(link => link.getAttribute('href'))"))
            assert links == expected_links
            expect(page.locator('table[data-uf-turnout="2026"] tbody tr')).to_have_count(52)
            assert [text.strip() for text in page.locator("table[data-historical-house] tbody tr th").all_text_contents()] == baseline["historical_years"]
            if javascript:
                for previous in baseline["unchanged_imports"]:
                    response = context.request.get(base + "/" + previous["path"])
                    assert response.ok
                    body = gzip.decompress(response.body())
                    assert len(body) == previous["json_bytes"]
                    assert hashlib.sha256(body).hexdigest() == previous["json_sha256"]
                verify_detail(page)
                page.locator('button[aria-controls="methods-panel"]').click()
            expect(page.locator("#downloads")).to_be_visible()
            expect(page.locator('[aria-labelledby="reviewed-county-participation-title"]')).to_contain_text(
                f"{record_count - 1} Pennsylvania county observations")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            proof["modes"].append({
                "mobile": mobile, "javascript": javascript, "reviewed_native_records": record_count,
                "county": county, "complete_native_record_equality": True,
                "all_previous_records_entirely_unchanged": True,
                "previous_reviewed_records": len(baseline["previous_reviewed_county_records"]),
                "all_previous_import_fingerprints_unchanged": javascript,
                "previous_complete_imports": len(baseline["unchanged_imports"]),
                "unique_download_urls": len(links), "download_anchors": sum(links.values()),
                "all_previous_download_anchors_preserved": True,
                "previous_download_anchors": len(baseline["expected_download_urls"]),
                "uf_rows": 52, "historical_years": baseline["historical_years"], "horizontal_overflow": False,
            })
            context.close()
        context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 844})
        page = context.new_page()
        page.route("**/participation-current/**", lambda route: route.abort())
        page.goto(base + "/voter-participation/?year=2026&state=Pennsylvania&mode=available&map-level=county&map-color=turnout")
        verify_detail(page)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        proof["checks"].append({"mobile": mobile, "county": county, "failed_current_feed_keeps_county": True})
        context.close()
    browser.close()
assert not errors, errors
proof["expected_download_urls"] = sorted(expected_links.elements())
proof["verified_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key != "expected_download_urls"}, indent=2))

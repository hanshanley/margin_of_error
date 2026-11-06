"""Verify Adams participation and preserve every previously published native record and download."""

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
args = parser.parse_args()
assert not args.proof.exists()
root = Path(__file__).resolve().parents[1]
base = args.base_url.rstrip("/")
reviews = json.loads((root / "public/participation-source-reviews.json").read_text())["reviews"]
review = next(row for row in reviews if row["id"] == "pennsylvania-adams-20261106-01")
baseline = json.loads((root / "data/county-source-reviews/20261106-adams-publication-01/baseline.json").read_text())
added = [review["complete_download_url"]] + [review["base_url"] + table["file"] for table in review["tables"]]
assert len(set(added)) == 9 and not set(added) & set(baseline["expected_download_urls"])
expected_links = Counter(baseline["expected_download_urls"]) + Counter(added)
assert len(expected_links) == 315 and sum(expected_links.values()) == 318
with (root / review["data_directory"] / "county-participation.csv").open() as source:
    native = next(csv.DictReader(source))
proof = {"base_url": base, "modes": [], "checks": []}
errors = []


def verify_detail(page):
    select = page.locator("#current-county-select")
    expect(select.locator("option")).to_have_count(14)
    select.select_option("42001")
    detail = page.locator("#current-county-detail")
    expect(detail.locator(".selection-rate")).to_have_text("42,660")
    for text in ("77,163 native registered voters", "55.29%", "UNOFFICIAL RESULTS",
                 "summary: 11/03/2026 10:23PM (timezone not declared)",
                 "precinct: 11/03/2026 10:23PM (timezone not declared)",
                 "0 of 53 complete and all 53 partially reported",
                 "10,320, not the index's separately scoped 10,348",
                 "Native provisional zeros remain explicit", "County mapping is not approved"):
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
            assert len(records) == 14
            assert [row for row in records if row["county"] != "Adams"] == baseline["previous_reviewed_county_records"]
            adams = next(row for row in records if row["county"] == "Adams")
            assert adams["native_record"] == native and adams["maps_approved"] is False
            expect(table.locator("tbody tr")).to_have_count(14)
            cells = table.locator("tbody tr").filter(has_text="Adams, Pennsylvania").locator("td").all_text_contents()
            assert [text.strip() for text in cells[:5]] == [
                "42,660", "77,163", "55.29%", "55.29%", "UNOFFICIAL RESULTS"]
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
                "13 Pennsylvania county observations")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            proof["modes"].append({
                "mobile": mobile, "javascript": javascript, "reviewed_native_records": 14,
                "complete_adams_native_record_equality": True, "all_thirteen_prior_records_entirely_unchanged": True,
                "all_fifteen_prior_import_fingerprints_unchanged": javascript,
                "unique_download_urls": len(links), "download_anchors": sum(links.values()),
                "all_309_previous_download_anchors_preserved": True,
                "uf_rows": 52, "historical_years": baseline["historical_years"], "horizontal_overflow": False,
            })
            context.close()
        context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 844})
        page = context.new_page()
        page.route("**/participation-current/**", lambda route: route.abort())
        page.goto(base + "/voter-participation/?year=2026&state=Pennsylvania&mode=available&map-level=county&map-color=turnout")
        verify_detail(page)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        proof["checks"].append({"mobile": mobile, "failed_current_feed_keeps_adams": True})
        context.close()
    browser.close()
assert not errors, errors
proof["expected_download_urls"] = sorted(expected_links.elements())
proof["verified_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key != "expected_download_urls"}, indent=2))

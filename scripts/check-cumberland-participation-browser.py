"""Verify Cumberland participation, existing native records and complete download preservation."""

import argparse
from collections import Counter
import csv
import datetime
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
review = next(row for row in reviews if row["id"] == "pennsylvania-cumberland-20261106-01")
baseline = json.loads((root / "data/county-source-reviews/20261106-bulk-participation-01/production-downloads.json").read_text())
added = [review["complete_download_url"]] + [review["base_url"] + table["file"] for table in review["tables"]]
assert len(set(added)) == 9 and not set(added) & set(baseline["expected_download_urls"])
expected_links = Counter(baseline["expected_download_urls"]) + Counter(added)
assert len(expected_links) == 306 and sum(expected_links.values()) == 309
with (root / review["data_directory"] / "county-participation.csv").open() as source:
    native = next(csv.DictReader(source))
proof = {"base_url": base, "modes": [], "checks": []}
errors = []


def verify_detail(page):
    select = page.locator("#current-county-select")
    expect(select.locator("option")).to_have_count(13)
    select.select_option("42041")
    detail = page.locator("#current-county-detail")
    expect(detail.locator(".selection-rate")).to_have_text(f'{int(native["ballots_cast"]):,}')
    for text in ("185,538 native registered voters", "63.24%", "UNOFFICIAL RESULTS",
                 "summary: 11/04/2026 12:37PM (timezone not declared)",
                 "precinct: 11/04/2026 12:31PM (timezone not declared)",
                 "Under/overvotes and a separate provisional count are absent, not zero",
                 "UPPER ALLEN 6 prints 65.36%", "County mapping is not approved"):
        expect(detail).to_contain_text(text)
    assert detail.locator('a[href="' + review["complete_download_url"] + '"]').count() == 1
    assert detail.locator('a[href="' + review["base_url"] + 'county-participation.csv"]').count() == 1


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
            assert len(records) == 13
            assert next(row for row in records if row["county"] == "Cumberland")["native_record"] == native
            for record in records:
                source_review = next(row for row in reviews if row["id"] == record["review_id"])
                with (root / source_review["data_directory"] / "county-participation.csv").open(encoding="utf-8-sig") as source:
                    originals = list(csv.DictReader(source))
                assert record["native_record"] in originals
                assert record["maps_approved"] is False
            expect(table.locator("tbody tr")).to_have_count(13)
            row = table.locator("tbody tr").filter(has_text="Cumberland, Pennsylvania")
            cells = row.locator("td").all_text_contents()
            assert [text.strip() for text in cells[:5]] == [
                "117,334", "185,538", "63.24%", "63.24%", "UNOFFICIAL RESULTS"]
            links = Counter(page.locator("#downloads a[download]").evaluate_all(
                "links => links.map(link => link.getAttribute('href'))"))
            assert links == expected_links
            expect(page.locator('table[data-uf-turnout="2026"] tbody tr')).to_have_count(52)
            assert [text.strip() for text in page.locator("table[data-historical-house] tbody tr th").all_text_contents()] == baseline["modes"][0]["historical_years"]
            if javascript:
                verify_detail(page)
                page.locator('button[aria-controls="methods-panel"]').click()
            expect(page.locator("#downloads")).to_be_visible()
            expect(page.locator('[aria-labelledby="reviewed-county-participation-title"]')).to_contain_text(
                "12 Pennsylvania county observations")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            proof["modes"].append({
                "mobile": mobile, "javascript": javascript, "reviewed_native_records": 13,
                "complete_native_record_equality": True, "unique_download_urls": len(links),
                "download_anchors": sum(links.values()), "all_297_previous_urls_preserved": True,
                "uf_rows": 52, "historical_years": baseline["modes"][0]["historical_years"],
                "horizontal_overflow": False,
            })
            context.close()
        context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 844})
        page = context.new_page()
        page.route("**/participation-current/**", lambda route: route.abort())
        page.goto(base + "/voter-participation/?year=2026&state=Pennsylvania&mode=available&map-level=county&map-color=turnout")
        verify_detail(page)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        proof["checks"].append({"mobile": mobile, "failed_current_feed_keeps_cumberland": True})
        context.close()
    browser.close()
assert not errors, errors
proof["expected_download_urls"] = sorted(expected_links.elements())
proof["verified_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key != "expected_download_urls"}, indent=2))

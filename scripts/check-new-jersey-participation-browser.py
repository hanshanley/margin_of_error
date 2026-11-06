"""Verify New Jersey participation scopes and preservation of the live baseline."""

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
parser.add_argument("--proof", required=True, type=Path)
args = parser.parse_args()
assert not args.proof.exists()
root = Path(__file__).resolve().parents[1]
base = args.base_url.rstrip("/")
publication = root / "data/county-source-reviews/20261106-nj-participation-publication-02"
baseline = json.loads((publication / "baseline.json").read_text())
reviews = json.loads((root / "public/participation-source-reviews.json").read_text())["reviews"]
review = next(row for row in reviews if row["id"] == "new-jersey-periodic-participation-20261106-02")
with (root / review["data_directory"] / "county-participation.csv").open() as source:
    native = {row["county"]: row for row in csv.DictReader(source)}
added = [review["complete_download_url"]] + [review["base_url"] + row["file"] for row in review["tables"]]
assert len(added) == 5 and not set(added) & set(baseline["expected_download_urls"])
expected_links = Counter(baseline["expected_download_urls"]) + Counter(added)
assert len(expected_links) == 364 and sum(expected_links.values()) == 367
proof = {"base_url": base, "modes": [], "checks": []}
errors = []
url = base + "/voter-participation/?year=2026&state=New%20Jersey&mode=available&map-level=county&map-color=turnout"


def verify_detail(page):
    select = page.locator("#current-county-select")
    expect(select.locator("option")).to_have_count(20)
    options = select.locator("option").all_text_contents()
    assert not any(name in option for name in ("Essex", "Hudson") for option in options)
    detail = page.locator("#current-county-detail")
    for county, total in (("Bergen", "319,503"), ("Cape May", "41,278"), ("Union", "176,356")):
        select.select_option(f"reviewed:NJ:{county}")
        expect(detail.locator(".selection-rate")).to_have_text(total)
        expect(detail).to_contain_text("timezone not declared")
        expect(detail).to_contain_text("not approved")
        expect(detail).to_contain_text("Issued, received and pending ballots are separate")
        if county == "Cape May":
            expect(detail.locator(".selection-basis")).to_have_text("2026 Ballots Cast - Total · not final/certified")
            expect(detail).to_contain_text("76,899 native registered voters")
            expect(detail).to_contain_text("Native printed fraction: 53.68%")
            expect(detail).to_contain_text("attached summary, PDF page 2")
            expect(detail).to_contain_text("attached_participation_summary page 2: not supplied")
        else:
            expect(detail.locator(".selection-basis")).to_contain_text("Derived EV + ED + mail-tallied subtotal")
            expect(detail).to_contain_text("Analysis fraction withheld / not supplied")
            expect(detail).to_contain_text("Registrations and turnout rate are not supplied")
            assert "Native printed fraction: 0" not in detail.inner_text()
        if county == "Union":
            expect(detail).to_contain_text("405 overseas ballots tallied")
        for href in (review["complete_download_url"], review["base_url"] + "county-participation.csv"):
            expect(detail.locator('a[href="' + href + '"]')).to_have_count(1)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for mobile in (False, True):
        for javascript in (True, False):
            context = browser.new_context(
                viewport={"width": 390 if mobile else 1440, "height": 844 if mobile else 1100},
                java_script_enabled=javascript, is_mobile=mobile, has_touch=mobile)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url, wait_until="domcontentloaded")
            table = page.locator("table[data-reviewed-county-participation]")
            records = json.loads(table.get_attribute("data-reviewed-county-participation"))
            assert len(records) == 37
            assert [row for row in records if row["state_code"] != "NJ"] == baseline["previous_reviewed_county_records"]
            nj = [row for row in records if row["state_code"] == "NJ"]
            assert len(nj) == 19
            for row in nj:
                assert row["native_record"] == native[row["county"]]
                assert row["maps_approved"] is False
                assert row["county_id"] == f"reviewed:NJ:{row['county']}"
                if row["county"] != "Cape May":
                    assert row["denominator"] is None and row["reported_pct"] is None
                    assert row["native_printed_pct"] is None
            assert not {"Essex", "Hudson"} & {row["county"] for row in nj}
            expect(table.locator("tbody tr")).to_have_count(37)
            cells = table.locator("tbody tr").filter(has_text="Bergen, New Jersey").locator("td").all_text_contents()
            assert cells[0].startswith("319,503 · Derived ")
            assert [text.strip() for text in cells[1:5]] == ["Not supplied", "Withheld", "Not supplied", "UNOFFICIAL"]
            links = Counter(page.locator("#downloads a[download]").evaluate_all(
                "links => links.map(link => link.getAttribute('href'))"))
            assert links == expected_links
            expect(page.locator('table[data-uf-turnout="2026"] tbody tr')).to_have_count(52)
            assert [cell.strip() for cell in page.locator("table[data-historical-house] tbody tr th").all_text_contents()] == baseline["historical_years"]
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
                "19 usable New Jersey county observations")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            proof["modes"].append(dict(
                mobile=mobile, javascript=javascript, reviewed_native_records=37,
                usable_new_jersey_counties=19, withheld_counties=["Essex", "Hudson"],
                all_nineteen_complete_native_records_equal=True, all_previous_eighteen_records_unchanged=True,
                all_previous_full_import_fingerprints_unchanged=javascript, previous_complete_imports=18,
                previous_download_anchors_preserved=362, download_anchors=367, unique_download_urls=364,
                missing_registrations_and_rates_not_zero=True, uf_rows=52,
                historical_years=baseline["historical_years"], horizontal_overflow=False))
            context.close()
        context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 844})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/participation-current/**", lambda route: route.abort())
        page.goto(url, wait_until="domcontentloaded")
        verify_detail(page)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        proof["checks"].append(dict(mobile=mobile, failed_current_feed_keeps_nj_counties=True))
        context.close()
    browser.close()
assert not errors, errors
proof["expected_download_urls"] = sorted(expected_links.elements())
proof["verified_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key != "expected_download_urls"}, indent=2))

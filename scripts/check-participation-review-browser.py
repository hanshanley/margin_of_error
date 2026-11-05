"""Verify limited official participation tables and preservation of full downloads."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import requests
from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--baseline-downloads", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
base = args.base_url.rstrip("/")
registry = json.loads((root / "public/participation-source-reviews.json").read_text())
baseline = set(json.loads(args.baseline_downloads.read_text()))
new_links = {review["complete_download_url"] for review in registry["reviews"]}
new_links.update(review["base_url"] + table["file"]
                 for review in registry["reviews"] for table in review["tables"])
assert len(baseline) == 61 and len(new_links) == 4 and not baseline & new_links
proof = dict(base_url=base, source_matched=True, full_csv_endpoints=[], modes=[])

for name in ["participation-source-reviews.json", "county-results.json",
             "precinct-coverage.csv", "scripts/participation-explorer.js"]:
    response = requests.get(base + "/" + name, timeout=90)
    response.raise_for_status()
    assert response.content == (root / "public" / name).read_bytes(), name
ledger = list(csv.DictReader((root / "public/precinct-coverage.csv").open()))
assert len(ledger) == 1632 and all(row["complete"] == "no" for row in ledger)

for review in registry["reviews"]:
    directory = root / review["data_directory"]
    assert not review["maps_approved"]
    for table in review["tables"]:
        response = requests.get(review["base_url"] + table["file"], timeout=90)
        response.raise_for_status()
        assert response.content == (directory / table["file"]).read_bytes()
        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert rows, table["file"]
        proof["full_csv_endpoints"].append(dict(
            file=table["file"], rows=len(rows), bytes=len(response.content),
            sha256=hashlib.sha256(response.content).hexdigest()))

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for mobile in (False, True):
        for javascript in (True, False):
            context = browser.new_context(java_script_enabled=javascript,
                viewport=dict(width=390 if mobile else 1440, height=844 if mobile else 1000),
                is_mobile=mobile, has_touch=mobile)
            page = context.new_page()
            page.goto(base + "/voter-participation/", wait_until="networkidle", timeout=120000)
            if javascript:
                expect(page.locator("#year")).to_have_value("2026")
                page.locator("#tab-methods").click()
            links = page.locator("#downloads a[download]").evaluate_all(
                "links => links.map(a => a.getAttribute('href'))")
            assert len(links) == len(set(links)) == 65
            assert set(links) == baseline | new_links
            city_count = 0
            for review in registry["reviews"]:
                table = page.locator(f'table[data-participation-review="{review["id"]}"]')
                details = table.locator("xpath=ancestor::details[1]")
                details.locator("summary").click()
                expect(table).to_be_visible()
                expected = json.loads((root / review["data_directory"] / review["city_file"]).read_text())
                actual = table.locator("tbody tr").evaluate_all(
                    "rows => rows.map(row => [...row.cells].map(cell => cell.textContent.trim()))")
                assert actual == [[str(row["year"]), f'{row["voters"]:,}',
                    "Not reported" if row["registered_voters"] is None else f'{row["registered_voters"]:,}',
                    "Not reported" if row["registered_turnout_pct"] is None
                    else f'{row["registered_turnout_pct"]:.1f}%'] for row in expected]
                assert [row["year"] for row in expected] == list(range(2026, 2001, -2))
                city_count += len(actual)
                expect(page.locator("#downloads")).to_contain_text(review["scope_note"])
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            proof["modes"].append(dict(mobile=mobile, javascript=javascript,
                complete_downloads=len(links), city_rows=city_count, no_overflow=True))
            context.close()
    browser.close()

args.output.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))

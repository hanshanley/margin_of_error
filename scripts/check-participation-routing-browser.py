"""Verify complete historical reads after relocating duplicate Pages payloads."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "dist/participation-downloads.json").read_text())
tables = {int(row["path"].split("/")[-1][:4]): row for row in manifest["files"]
          if row["path"].startswith("/voter-participation/data/nc/") and row["path"].endswith(".json")}
assert set(tables) == set(range(2002, 2025, 2))
proof = {"base_url": base, "checks": []}
errors = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for mobile in (False, True):
        context = browser.new_context(
            viewport={"width": 390 if mobile else 1440, "height": 844 if mobile else 1100},
            is_mobile=mobile, has_touch=mobile)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        with page.expect_response(tables[2024]["url"], timeout=60000) as captured:
            page.goto(base + "/voter-participation/?view=precincts&year=2024&county=WAKE"
                      "&precinct=01-01&dimension=overall&map-color=turnout")
        initial_response = captured.value
        for year in reversed(sorted(tables)):
            if year == 2024:
                expect(page.locator(".map-feature.selected")).to_have_attribute("data-key", "WAKE|01-01")
                download_count = page.locator("#downloads a[download]").count()
                assert download_count >= 900
                reviewed_rows = page.locator("table[data-reviewed-county-participation] tbody tr").all_text_contents()
                assert reviewed_rows
                response = initial_response
            else:
                with page.expect_response(tables[year]["url"], timeout=60000) as captured:
                    page.locator("#year").select_option(str(year))
                response = captured.value
            assert response.status == 200
            body = response.body()
            assert len(body) == tables[year]["bytes"]
            assert hashlib.sha256(body).hexdigest() == tables[year]["sha256"]
            original = json.loads((root / f"public/voter-participation/data/nc/{year}.json").read_text())
            native = next(row for row in original["records"] if row["county"] == "WAKE"
                          and row["precinct"] == "01-01" and row["dimension"] == "overall")
            expect(page.locator("#selection-panel .selection-rate")).to_have_text(f'{native["turnout_pct"]:.1f}%')
            expect(page.locator(".selection-stats")).to_contain_text(f'{native["participants"]:,}')
            expect(page.locator(".selection-stats")).to_contain_text(f'{native["registered"]:,}')
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            proof["checks"].append({"mobile": mobile, "year": year,
                                    "source_matched_counts_and_rate": True,
                                    "full_response_byte_match": True})
        page.locator("#year").select_option("2024")
        expect(page.locator(".map-feature.selected")).to_have_attribute("data-key", "WAKE|01-01")
        legacy = context.request.get(base + "/voter-participation/app.js")
        assert legacy.status == 200
        legacy_counts = page.evaluate("""async script => {
          const prefix = script.slice(0, script.indexOf('const $ = id =>'));
          const reader = script.match(/async function get\\(path\\) \\{[\\s\\S]*?return response.json\\(\\);\\n\\}/)[0];
          return await new Function('return ' + prefix + reader
            + '\\nreturn get("nc/2004.json");\\n})();')();
        }""", legacy.text())
        assert legacy_counts == json.loads((root / "public/voter-participation/data/nc/2004.json").read_text())
        proof["checks"].append({"mobile": mobile, "adapted_legacy_reader_complete_2004_equality": True,
                                "return_to_2024_selection_preserved": True})
        context.close()
        context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 844})
        page = context.new_page()
        page.route(tables[2004]["url"], lambda route: route.abort())
        page.goto(base + "/voter-participation/?view=precincts&year=2004&county=WAKE")
        expect(page.locator("#notice")).to_contain_text("The saved data could not be loaded:")
        expect(page.locator("#notice")).to_contain_text("No values have been inferred.")
        reviewed_table = page.locator("table[data-reviewed-county-participation] tbody tr")
        expect(reviewed_table).to_have_count(len(reviewed_rows))
        assert reviewed_table.all_text_contents() == reviewed_rows
        assert page.locator("#downloads a[download]").count() == download_count
        proof["checks"].append({"mobile": mobile, "failed_historical_read_is_explicit": True,
                                "reviewed_counties_and_all_downloads_preserved": True})
        context.close()
    browser.close()
assert not errors, errors
proof["relocated_tables"] = [tables[year] for year in sorted(tables)]
proof["verified_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
args.proof.parent.mkdir(parents=True, exist_ok=True)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key != "relocated_tables"}, indent=2))

"""Verify bulk participation navigation against the independently read source tables."""

import argparse
import csv
import datetime
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
base = args.base_url.rstrip("/")
url = base + "/voter-participation/"
expected = {
    "AL": ("Alabama", 67, 0), "AZ": ("Arizona", 15, 0), "AR": ("Arkansas", 75, 0),
    "VA": ("Virginia", 133, 0), "IA": ("Iowa", 1, 0), "KY": ("Kentucky", 1, 0),
    "MN": ("Minnesota", 87, 4105), "ND": ("North Dakota", 53, 358),
    "ID": ("Idaho", 44, 986), "VT": ("Vermont", 247, 0),
    "RI": ("Rhode Island", 39, 0), "MI": ("Michigan", 2, 63),
}
pointer = json.loads((root / "public/precinct-results.json").read_text())
native_units = {}
for code, suffix in [("MN", "expansion-01"), ("ND", "north-dakota-02"), ("ID", "idaho-01")]:
    review = next(row for row in pointer["additional_snapshots"] if row["data_directory"].endswith(suffix))
    rows = json.loads(gzip.decompress((root / review["data_directory"] / "participation.json.gz").read_bytes()))
    native_units[code] = {row["key"]: row for row in rows}
mi = next(row for row in json.loads((root / "public/participation-source-reviews.json").read_text())["reviews"]
          if row["id"] == "michigan-native-counties-20261105-01")
with (root / mi["data_directory"] / "precinct-participation.csv").open() as source:
    native_units["MI"] = {row["source_row_id"]: row for row in csv.DictReader(source)}

proof = {"base_url": base, "checks": []}
errors = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for mobile in (False, True):
        context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 844 if mobile else 1100})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        for code, (name, locality_count, unit_count) in expected.items():
            response = context.request.get(base + f"/participation-local/{code}.json.gz")
            assert response.ok
            data = json.loads(gzip.decompress(response.body()))
            assert len(data["counties"]) == locality_count and len(data["precincts"]) == unit_count
            assert all(row["state_code"] == code and row["maps_approved"] is False
                       for row in data["counties"] + data["precincts"])
            for row in data["precincts"]:
                native = native_units[code][row["unit_key"]]
                assert row["native_record"] == native
                ballots = native.get("ballots_cast_total") if code == "MI" else native["ballots"]
                assert row["ballots"] == (None if ballots in ("", None) else int(ballots))
            if code in ("MN", "ND", "ID", "MI"):
                assert all(row["ballots"] is None and row["reported_pct"] is None for row in data["counties"])
            if code == "RI":
                assert len(data["nongeographic"]) == 1 and data["nongeographic"][0]["ballots"] == 756
                assert all(row["county"] != "Federal" for row in data["counties"])
            page.goto(url + f"?year=2026&state={name.replace(' ', '+')}&mode=available&map-level=county&map-color=turnout")
            select = page.locator("#current-county-select")
            expect(select.locator("option")).to_have_count(locality_count + 1)
            row = data["counties"][0]
            select.select_option(row["county_id"])
            detail = page.locator("#current-county-detail")
            if row["ballots"] is not None:
                expect(detail.locator(".selection-rate")).to_have_text(f'{row["ballots"]:,}')
            else:
                expect(detail).to_contain_text("County total not supplied")
                units = [unit for unit in data["precincts"] if unit["county_id"] == row["county_id"]]
                expect(page.locator("#current-unit-select option")).to_have_count(len(units) + 1)
                unit = units[0]
                page.locator("#current-unit-select").select_option(unit["unit_key"])
                if unit["ballots"] is not None:
                    expect(page.locator("#current-unit-detail .selection-rate")).to_have_text(f'{unit["ballots"]:,}')
            if row["reported_pct"] is None:
                expect(detail).to_contain_text("Analysis fraction withheld / not supplied")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                code, mobile, page.evaluate("[innerWidth, document.documentElement.scrollWidth]"))
            proof["checks"].append({"mobile": mobile, "state": code, "localities": locality_count,
                                    "reporting_units": unit_count, "native_records_and_missingness": True})
        page.goto(url + "?year=2026&state=Idaho&mode=available&map-level=county&map-color=turnout")
        data = json.loads(gzip.decompress(context.request.get(base + "/participation-local/ID.json.gz").body()))
        pooled = next(row for row in data["precincts"]
                      if "pooled_nongeographic_reporting_unit" in row["native_record"]["quality_flags"])
        page.locator("#current-county-select").select_option(pooled["county_id"])
        page.locator("#current-unit-select").select_option(pooled["unit_key"])
        expect(page.locator("#current-unit-detail")).to_contain_text("pooled absentee or early unit")
        expect(page.locator("#current-unit-detail")).to_contain_text("pooled_nongeographic_reporting_unit")
        context.close()
        static_context = browser.new_context(java_script_enabled=False,
                                            viewport={"width": 390 if mobile else 1440, "height": 844})
        static = static_context.new_page()
        static.goto(url)
        section = static.locator('[aria-labelledby="additional-participation-title"]')
        expect(section.locator(":scope > details")).to_have_count(12)
        expect(section.locator("tbody tr")).to_have_count(764)
        assert static.evaluate("document.documentElement.scrollWidth <= innerWidth")
        proof["checks"].append({"mobile": mobile, "javascript": False, "native_localities": 764,
                                "complete_state_json_links": 12})
        static_context.close()
    broken = browser.new_page()
    broken.route("**/participation-local/KY.json.gz", lambda route: route.abort())
    broken.goto(url + "?year=2026&state=Kentucky&mode=available")
    expect(broken.locator("#current-local-navigation")).to_contain_text("complete downloads remain in Methods & data")
    expect(broken.locator("#current-local-navigation")).not_to_contain_text("No verified full-election")
    proof["checks"].append({"failed_state_import_explicit": True})
    broken.close()
    browser.close()
assert not errors, errors
proof["verified_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
args.proof.parent.mkdir(parents=True, exist_ok=True)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({"checks": len(proof["checks"]), "passed": True}))

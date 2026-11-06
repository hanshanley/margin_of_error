"""Verify bulk participation navigation against the independently read source tables."""

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
parser.add_argument("--states", nargs="+")
parser.add_argument("--baseline", type=Path)
args = parser.parse_args()
assert not args.proof.exists()
root = Path(__file__).resolve().parents[1]
base = args.base_url.rstrip("/")
url = base + "/voter-participation/"
expected = {
    "AL": ("Alabama", 67, 0), "AZ": ("Arizona", 15, 0), "AR": ("Arkansas", 75, 0),
    "VA": ("Virginia", 133, 0), "IA": ("Iowa", 1, 0), "KY": ("Kentucky", 1, 0),
    "MN": ("Minnesota", 87, 4105), "ND": ("North Dakota", 53, 358),
    "ID": ("Idaho", 44, 986), "VT": ("Vermont", 247, 0),
    "RI": ("Rhode Island", 39, 0), "MI": ("Michigan", 2, 63),
    "FL": ("Florida", 1, 0), "MO": ("Missouri", 1, 0), "WY": ("Wyoming", 23, 0),
    "WA": ("Washington", 39, 0),
    "NV": ("Nevada", 1, 0),
    "OR": ("Oregon", 36, 0),
}
all_states = expected.copy()
if args.states:
    if set(args.states) - set(expected):
        parser.error("Unknown imported participation state")
    expected = {code: expected[code] for code in args.states}
baseline = json.loads(args.baseline.read_text()) if args.baseline else None
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
source_files = {
    "FL": "data/precinct-source-reviews/20261105/FL-2026-MON/participation.json.gz",
    "MO": "data/precinct-source-reviews/20261105/MO-2026-CHRISTIAN/audit.json",
    "WY": "data/precinct-source-reviews/20261105/WY-2026-native-counts/counts-review.json",
    "WA": "data/county-source-reviews/20261106-washington-participation-01/county-participation.csv",
    "NV": "data/county-source-reviews/20261106-washoe-participation-01/county-participation.csv",
    "OR": "data/county-source-reviews/20261106-oregon-participation-01/county-participation.csv",
}
native_counties = {
    "FL": json.loads(gzip.decompress((root / source_files["FL"]).read_bytes())),
    "MO": [json.loads((root / source_files["MO"]).read_text())],
    "WY": json.loads((root / source_files["WY"]).read_text())["counties"],
}
for code in ("WA", "NV", "OR"):
    with (root / source_files[code]).open() as source:
        native_counties[code] = list(csv.DictReader(source))


def verify_preservation(page):
    if not baseline or "previous_reviewed_county_records" not in baseline:
        return
    table = page.locator("table[data-reviewed-county-participation]")
    assert json.loads(table.get_attribute("data-reviewed-county-participation")) == baseline[
        "previous_reviewed_county_records"]
    expect(page.locator('table[data-uf-turnout="2026"] tbody tr')).to_have_count(52)
    assert [text.strip() for text in page.locator(
        "table[data-historical-house] tbody tr th").all_text_contents()] == baseline["historical_years"]

proof = {"base_url": base, "checks": []}
errors = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for mobile in (False, True):
        context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 844 if mobile else 1100})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        if baseline:
            for previous in baseline["unchanged_imports"]:
                response = context.request.get(base + f'/participation-local/{previous["state_code"]}.json.gz')
                assert response.ok
                body = gzip.decompress(response.body())
                assert len(body) == previous["json_bytes"]
                assert hashlib.sha256(body).hexdigest() == previous["json_sha256"]
            proof["checks"].append({"mobile": mobile, "all_previous_imports_entirely_unchanged": True,
                                    "previous_complete_imports": len(baseline["unchanged_imports"])})
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
            if code in native_counties:
                assert [row["native_record"] for row in data["counties"]] == native_counties[code]
                for row in data["counties"]:
                    native = row["native_record"]
                    if code in ("WA", "NV", "OR"):
                        assert row["ballots"] == int(native["ballots_counted" if code == "OR" else "ballots_cast"])
                        assert row["denominator"] == int(native[
                            "active_registered_voters" if code == "OR" else "registered_voters"])
                        assert row["reported_pct"] == (float(native["registered_turnout_percent"])
                                                       if code == "WA" else None)
                        continue
                    assert row["ballots"] == native[
                        "ballots" if code == "FL" else "county_ballots" if code == "MO" else "printed_county_ballots"]
                    assert row["denominator"] == (native["registered"] if code == "FL"
                                                  else native["county_registered"] if code == "MO" else None)
                    assert row["reported_pct"] is None
                original = context.request.get(data["counties"][0]["source_url"])
                assert original.ok and original.body() == (root / source_files[code]).read_bytes()
            page.goto(url + f"?year=2026&state={name.replace(' ', '+')}&mode=available&map-level=county&map-color=turnout")
            select = page.locator("#current-county-select")
            expect(select.locator("option")).to_have_count(locality_count + 1)
            for row in data["counties"] if code in native_counties else data["counties"][:1]:
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
                if code in ("FL", "MO"):
                    expect(detail).to_contain_text(f'{row["denominator"]:,} native registered voters')
                    expect(detail).to_contain_text(f'Native printed fraction: {row["native_printed_pct"]}')
                if code == "MO":
                    expect(detail).to_contain_text("centralized absentee")
                if code == "NV":
                    expect(detail).to_contain_text(f'{row["denominator"]:,} native registered voters')
                    expect(detail).to_contain_text("Native printed fraction: 58.17%")
                    expect(detail).to_contain_text("REPORT 6 - UNOFFICIAL RESULTS")
                    expect(detail).to_contain_text("11/4/2026 6:13:35 PM")
                    expect(detail).to_contain_text("must not be summed")
                if code == "OR":
                    expect(detail).to_contain_text(f'{row["denominator"]:,} native active registered voters')
                    expect(detail).to_contain_text(f'Native printed fraction: {row["native_printed_pct"]}')
                    expect(detail).to_contain_text("Unofficial")
                    expect(detail).to_contain_text(row["native_record"]["source_updated_at"])
                    expect(detail).to_contain_text("11/5/2026 | 8:30 PM PT")
                    expect(detail).to_contain_text("IsReported false")
                if code == "WY":
                    expect(detail).to_contain_text("electorate not supplied")
                    expect(detail).to_contain_text("Washakie candidate-category conflict")
                if code == "WA":
                    expect(detail).to_contain_text(f'{row["denominator"]:,} native registered voters')
                    expect(detail).to_contain_text("separate native statewide ballot field is zero")
                    for field in ("source_as_of", "source_last_updated", "source_publish_date",
                                  "state_locality_source_as_of", "state_locality_source_last_updated"):
                        expect(detail).to_contain_text(row["native_record"][field])
                    if row["native_record"]["source_short_name"] == "king-county-wa":
                        expect(detail).to_contain_text("not zero participation")
                        expect(detail).to_contain_text("remain unallocated")
            verify_preservation(page)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                code, mobile, page.evaluate("[innerWidth, document.documentElement.scrollWidth]"))
            proof["checks"].append({"mobile": mobile, "state": code, "localities": locality_count,
                                    "reporting_units": unit_count, "native_records_and_missingness": True})
        if "ID" in expected:
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
        expect(section.locator(":scope > details")).to_have_count(len(all_states))
        expect(section.locator("tbody tr")).to_have_count(sum(row[1] for row in all_states.values()))
        if baseline:
            assert Counter(static.locator("#downloads a[download]").evaluate_all(
                "links => links.map(link => link.getAttribute('href'))")) == Counter(
                    baseline["expected_download_urls"] + baseline.get("added_download_urls", []))
        for code in set(expected) & set(native_counties):
            details = section.locator(":scope > details").filter(
                has=static.locator("summary", has_text=all_states[code][0] + ":"))
            expect(details.locator("tbody tr")).to_have_count(all_states[code][1])
            cells = details.locator("tbody tr").evaluate_all(
                "rows => rows.map(row => [...row.cells].map(cell => cell.textContent.trim()))")
            for row, native in zip(cells, native_counties[code]):
                if code in ("WA", "NV", "OR"):
                    assert row[2] == f'{int(native["ballots_counted" if code == "OR" else "ballots_cast"]):,}'
                    assert row[3] == f'{int(native["active_registered_voters" if code == "OR" else "registered_voters"]):,}'
                    assert row[4] == (f'{float(native["registered_turnout_percent"]):.2f}%'
                                      if code == "WA" else "Withheld / not supplied")
                else:
                    ballots = native["ballots" if code == "FL" else "county_ballots" if code == "MO" else "printed_county_ballots"]
                    assert row[2] == f"{ballots:,}" and row[4] == "Withheld / not supplied"
        verify_preservation(static)
        assert static.evaluate("document.documentElement.scrollWidth <= innerWidth")
        proof["checks"].append({"mobile": mobile, "javascript": False,
                                "native_localities": sum(row[1] for row in all_states.values()),
                                "complete_state_json_links": len(all_states),
                                "all_previous_download_anchors_preserved": bool(baseline)})
        static_context.close()
    broken = browser.new_page()
    failed_code = next(iter(expected))
    broken.route(f"**/participation-local/{failed_code}.json.gz", lambda route: route.abort())
    broken.goto(url + f"?year=2026&state={expected[failed_code][0].replace(' ', '+')}&mode=available")
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

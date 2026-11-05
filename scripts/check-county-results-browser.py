"""Verify county integration against pinned counts in local or production Pages."""

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

import requests
from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--baseline-downloads", type=Path)
parser.add_argument("--tables-only", action="store_true",
                    help="Check table/download changes without repeating the unchanged map suite")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
base = args.base_url.rstrip("/")
url = base + "/voter-participation/"
pointer = json.loads((root / "public/county-results.json").read_text())
directory = root / pointer["data_directory"]
index = json.loads((directory / "index.json").read_text())
rows = json.loads((directory / "margins.json").read_text())
uf_pointer_path = root / "public/uf-turnout.json"
uf_pointer = json.loads(uf_pointer_path.read_bytes()) if uf_pointer_path.exists() else None
uf_rows = json.loads((root / uf_pointer["data_directory"] / "turnout.json").read_bytes()) if uf_pointer else []
historical_audit_path = root / "data/county-source-reviews/20261105-historical-bulk-01/audit.json"
historical_audit = json.loads(historical_audit_path.read_bytes()) if historical_audit_path.exists() else None
house_pointer_path = root / "public/historical-house-counties.json"
house_pointer = json.loads(house_pointer_path.read_bytes()) if house_pointer_path.exists() else None
house_audit = json.loads((root / house_pointer["data_directory"] / "audit.json").read_bytes()) if house_pointer else None
if house_pointer:
    house_coverage = list(csv.DictReader(gzip.open(
        root / house_pointer["data_directory"] / "state-coverage.csv.gz", "rt")))
    expected_cells = 51 * len(house_audit["years"])
    assert len(house_coverage) == expected_cells
    assert len({(row["year"], row["state_code"]) for row in house_coverage}) == expected_cells
    assert all(row["fully_complete"] == row["map_approved"] == "False" for row in house_coverage)
if historical_audit:
    with (root / "public/county-candidate-coverage.csv").open(newline="") as stream:
        county_ledger = list(csv.DictReader(stream))
    assert len(county_ledger) == 4896
    assert len({(row["year"], row["office"], row["state_code"]) for row in county_ledger}) == 4896
    assert all(row["fully_complete"] == "False" for row in county_ledger)
    if house_pointer:
        assert {(row["year"], row["state_code"]) for row in house_coverage} == {
            (year["year"], code) for year in house_audit["years"]
            for code in {row["state_code"] for row in county_ledger}}
precinct_pointer = json.loads((root / "public/precinct-results.json").read_text())
precinct_coverage = {}
for snapshot in [precinct_pointer, *precinct_pointer.get("additional_snapshots", [])]:
    location = root / snapshot["data_directory"]
    for year, states in json.loads((location / "index.json").read_text())["coverage"].items():
        precinct_coverage.setdefault(year, {}).update({
            code: (location, item) for code, item in states.items()
        })
baseline = set(json.loads(args.baseline_downloads.read_text())) if args.baseline_downloads else set()
participation_reviews_path = root / "public/participation-source-reviews.json"
participation_reviews = json.loads(participation_reviews_path.read_text())["reviews"] if participation_reviews_path.exists() else []
download_count = (18 + len(precinct_pointer["source_reviews"]) + len(precinct_pointer["source_batches"])
                  + sum(3 if s.get("participation_available", True) else 2
                        for s in precinct_pointer["additional_snapshots"])
                  + 3 * (1 + len(pointer.get("previous_snapshots", [])))
                  + sum(1 + len(review["tables"]) for review in participation_reviews))
for name in ["county-results.json", "precinct-results.json", "precinct-coverage.csv",
             *(["participation-source-reviews.json"] if participation_reviews else []),
             *(["county-candidate-coverage.csv"] if historical_audit else []),
             *(["historical-house-counties.json"] if house_pointer else []),
             "scripts/participation-explorer.js"] + (["uf-turnout.json"] if uf_pointer else []):
    response = requests.get(base + "/" + name, timeout=90)
    response.raise_for_status()
    assert response.content == (root / "public" / name).read_bytes(), f"Not current source: {name}"


def color(margin):
    weight = min(1, abs(margin) / 35)
    end = [137, 40, 45] if margin < 0 else [37, 75, 120]
    return "rgb(" + ",".join(str(math.floor(a + weight * (b - a) + .5))
                            for a, b in zip([237, 232, 220], end)) + ")"


def values(page, level):
    paths = page.locator(f'.substate-feature[data-color-level="{level}"]')
    return paths.evaluate_all(
        "paths => Object.fromEntries(paths.map(p => [p.dataset.geography,"
        "[+p.dataset.margin,+p.dataset.totalVotes,p.getAttribute('fill'),+p.dataset.year]]))")


def county(page, code, name):
    page.locator("#state-select").select_option(name)
    expected = {}
    for row in rows:
        if row["state_code"] != code or row["margin_pp"] is None:
            continue
        total = row["democratic_votes"] + row["republican_votes"] + row["other_votes"]
        margin = 100 * (row["democratic_votes"] - row["republican_votes"]) / total
        assert total == row["contest_votes"] and math.isclose(margin, row["margin_pp"], abs_tol=1e-12)
        expected[row["geography"]] = [row["margin_pp"], total, color(margin), 2026]
    expect(page.locator("#title")).to_have_text(f"County election results in {name}", timeout=90000)
    expect(page.locator('.substate-feature[data-color-level="county"]')).to_have_count(len(expected))
    assert values(page, "county") == expected, code
    expect(page.locator('.substate-feature[data-color-level="precinct"]')).to_have_count(0)
    expect(page.locator("#key")).to_contain_text("U.S. House aggregate")
    expect(page.locator("#geography-note")).to_contain_text("2026 Census")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), code
    assert page.locator('.substate-feature[data-color-level="county"]').evaluate_all(
        "paths => paths.every(p => p.getAttribute('d')?.length > 20)")
    return len(expected)


def precinct(page, year, code):
    location, coverage = precinct_coverage[str(year)][code]
    features = json.loads(gzip.decompress((location / coverage["file"]).read_bytes()))["features"]
    expected = {p["key"]: [p["margin_pp"], p["contest_votes"], color(p["margin_pp"]), year]
                for feature in features for p in [feature["properties"]]
                if feature["geometry"] and p["match_status"] == "matched" and p["margin_pp"] is not None}
    expect(page.locator('.substate-feature[data-color-level="precinct"]')).to_have_count(len(expected), timeout=90000)
    assert values(page, "precinct") == expected, (year, code)
    return len(expected)


def width(page):
    return float(page.locator("svg.turnout-map").get_attribute("viewBox").split()[2])


proof = {"base_url": base, "county_states": len(index["coverage"]), "modes": [], "failures_tested": []}
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    for mobile in [False, True]:
        for javascript in [True, False]:
            context = browser.new_context(
                viewport={"width": 390, "height": 844} if mobile else {"width": 1360, "height": 1000},
                is_mobile=mobile, has_touch=mobile, java_script_enabled=javascript)
            page = context.new_page()
            if mobile and javascript:
                context.route("**/county-results-overview.geojson.gz", lambda route: route.fulfill(
                    status=200, content_type="application/gzip",
                    body=(root / "public/county-results-overview.geojson.gz").read_bytes()))
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            links = page.locator("#downloads a[download]")
            assert links.count() >= download_count, "A complete source download is missing"
            downloads = set(links.evaluate_all("links => links.map(a => a.getAttribute('href'))"))
            assert baseline <= downloads, f"Lost complete downloads: {baseline - downloads}"
            if "complete_download_urls" in proof:
                assert downloads == set(proof["complete_download_urls"]), "Downloads differ between display modes"
            else:
                proof["complete_download_urls"] = sorted(downloads)
            assert pointer["complete_download_url"] in downloads
            for review in participation_reviews:
                assert review["complete_download_url"] in downloads
                assert {review["base_url"] + table["file"] for table in review["tables"]} <= downloads
                expect(page.locator("#downloads")).to_contain_text(review["scope_note"])
            if historical_audit:
                assert "/county-candidate-coverage.csv" in downloads
                assert historical_audit["complete_original_url"] in downloads
                expect(page.locator("#downloads")).to_contain_text("fractional vote count is withheld")
            if pointer.get("party_votes"):
                parties = pointer["party_votes"]
                assert parties["complete_download_url"] in downloads
                assert {parties["base_url"] + table["file"] for table in parties["tables"]} <= downloads
                expect(page.locator("#downloads")).to_contain_text("test data are withheld")
            if house_pointer:
                for snapshot in [house_pointer, *house_pointer.get("previous_snapshots", [])]:
                    assert snapshot["complete_download_url"] in downloads
                    assert {snapshot["base_url"] + table["file"] for table in snapshot["tables"]} <= downloads
                table_rows = page.locator("table[data-historical-house] tbody tr")
                expect(table_rows).to_have_count(len(house_audit["years"]))
                actual = table_rows.evaluate_all("rows => rows.map(row => "
                    "[...row.querySelectorAll('th,td')].map(cell => cell.textContent.trim()))")
                expected = [[row["year"], str(row["reviewed_states"]), f'{row["reviewed_counties"]:,}',
                    f'{row["reviewed_candidate_rows"]:,}', str(row["withheld_counties"])] for row in house_audit["years"]]
                assert actual == expected, "Historical House coverage differs from scoped source review"
                expect(page.locator("#downloads")).to_contain_text("not certified statewide totals")
                if "native_auxiliary_no_ballot_records" in house_audit:
                    expect(page.locator("#downloads")).to_contain_text(
                        f'{house_audit["native_auxiliary_gap_records"]} native source coverage gaps')
                    expect(page.locator("#downloads")).to_contain_text(
                        f'{house_audit["native_auxiliary_no_ballot_records"]} no-ballot observations')
                    expect(page.locator("#downloads")).to_contain_text("not invented zero-vote candidates")
            if uf_pointer:
                assert uf_pointer["complete_download_url"] in downloads
                assert uf_pointer["base_url"] + "originals/turnout.csv" in downloads
                table_rows = page.locator('table[data-uf-turnout="2026"] tbody tr')
                expect(table_rows).to_have_count(len(uf_rows))
                expected_uf = [[row["STATE_ABV"],
                    "Not reported" if row["TOTAL_BALLOTS_COUNTED"] is None else f'{row["TOTAL_BALLOTS_COUNTED"]:,}',
                    row["SOURCE"], "Not reported" if row["VEP"] is None else f'{row["VEP"]:,}',
                    "Not reported" if row["VEP_TURNOUT_RATE"] is None else f'{row["VEP_TURNOUT_RATE"]:.2f}%',
                    "Not reported" if row["VAP_TURNOUT_RATE"] is None else f'{row["VAP_TURNOUT_RATE"]:.2f}%']
                    for row in uf_rows]
                actual_uf = table_rows.evaluate_all("rows => rows.map(row => [row.dataset.stateCode,"
                    "...[...row.querySelectorAll('td')].map(cell => cell.textContent.trim())])")
                assert actual_uf == expected_uf, "UF table differs from source counts, statuses or own-denominator rates"
            expect(page.locator("#downloads")).to_contain_text(f"{len(index['coverage'])} states")
            expect(page.locator("#downloads")).to_contain_text("not precinct results")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            mode = {"mobile": mobile, "javascript": javascript, "complete_downloads": len(downloads)}
            if uf_pointer:
                mode["uf_rows_source_matched"] = len(uf_rows)
            if historical_audit:
                mode["county_candidate_ledger_rows"] = len(county_ledger)
            if house_pointer:
                mode["historical_house_years_source_matched"] = [row["year"] for row in house_audit["years"]]
                mode["historical_house_scope_cells"] = len(house_coverage)
            if javascript:
                mode["overview_transport"] = "raw gzip" if mobile else "server response"
            if not javascript or args.tables_only:
                if args.tables_only:
                    mode["map_checks"] = "not_repeated"
                context.close()
                proof["modes"].append(mode)
                continue
            expect(page.locator("#year")).to_have_value("2026")
            expect(page.locator("#map-level")).to_have_value("county")
            expect(page.locator("#map-color")).to_have_value("margin")
            overview = page.locator('.county-overview-feature[data-color-level="county"]')
            expect(overview).to_have_count(index["colored_counties"], timeout=90000)
            expected_overview = {row["geography"]: [row["margin_pp"], row["contest_votes"], color(row["margin_pp"]), 2026]
                                 for row in rows if row["margin_pp"] is not None}
            actual_overview = overview.evaluate_all(
                "paths => Object.fromEntries(paths.map(p => [p.dataset.geography,"
                "[+p.dataset.margin,+p.dataset.totalVotes,p.getAttribute('fill'),+p.dataset.year]]))")
            assert actual_overview == expected_overview
            assert math.isclose(width(page), 1000), "Default county map must stay at national scale"
            names = dict(page.locator("#state-select option").evaluate_all(
                "options => options.map(o => [o.textContent, o.value])"))
            state_pointer = json.loads((root / "public/participation-current/latest.json").read_text())
            national = json.loads((root / "public/participation-current" /
                                   state_pointer["snapshot_id"] / "snapshot.json").read_text())
            names = {r["state_code"]: names[r["state"]] for r in national["coverage"]}
            # County colors must already be visible before a state is selected.
            county(page, "NV", names["NV"])
            page.locator("#map-level").select_option("county")
            mapped = {code: county(page, code, names[code]) for code in sorted(index["coverage"])}
            assert sum(mapped.values()) == index["colored_counties"]
            for code in [*index["withheld_states"], "DC"]:
                page.locator("#state-select").select_option(names[code])
                expect(page.locator(".substate-feature")).to_have_count(0)
                expect(page.locator("#geography-note")).to_contain_text("No verified 2026 county")
            page.locator("#map-level").select_option("precinct")
            page.locator("#state-select").select_option(names["WA"])
            precinct(page, 2026, "WA")
            expect(page.locator('.substate-feature[data-color-level="county"]')).to_have_count(
                index["coverage"]["WA"]["colored_counties"])
            order = page.locator(".substate-feature").evaluate_all("paths => paths.map(p => p.dataset.colorLevel)")
            assert order == sorted(order), "County backdrop must be below actual precincts"
            expect(page.locator("#title")).to_have_text("Precinct election results in Washington")
            page.locator('.substate-feature[data-color-level="precinct"]').first.dispatch_event("click")
            expect(page.locator("#substate-detail")).to_contain_text("not turnout")
            before = width(page)
            page.locator("#map-zoom-out").click()
            assert width(page) > before
            page.locator("#map-zoom-in").click()
            assert math.isclose(width(page), before, abs_tol=.001)
            county_count = county(page, "NV", names["NV"])
            page.locator('.substate-feature[data-color-level="county"]').first.dispatch_event("click")
            expect(page.locator("#substate-detail")).to_contain_text("Democratic")
            expect(page.locator("#substate-detail")).to_contain_text("Explicit overseas")
            before = width(page)
            page.locator("#map-zoom-in").click()
            assert width(page) < before
            page.locator("#map-zoom-out").click()
            assert math.isclose(width(page), before, abs_tol=.001)
            page.locator("svg.turnout-map").scroll_into_view_if_needed()
            rect = page.locator("svg.turnout-map").bounding_box()
            x, y = rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2
            before = width(page)
            if mobile:
                cdp = context.new_cdp_session(page)
                touches = lambda d: [{"x": x - d / 2, "y": y, "id": 31},
                                     {"x": x + d / 2, "y": y, "id": 32}]
                cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": touches(40)})
                for distance in [48, 60, 72, 80]:
                    cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": touches(distance)})
                cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            else:
                page.mouse.move(x, y)
                page.mouse.wheel(0, -250)
            page.wait_for_function(
                "w => document.querySelector('svg.turnout-map').viewBox.baseVal.width < w", arg=before)
            assert page.locator('.substate-feature[data-color-level="county"]').count() == county_count
            page.locator("#state-select").select_option(names["NC"])
            for year in [2024, 2020]:
                page.locator("#year").select_option(str(year))
                precinct(page, year, "NC")
                expect(page.locator('.substate-feature[data-color-level="county"]')).to_have_count(0)
            page.locator("#year").select_option("2018")
            page.locator("#state-select").select_option(names["NV"])
            expect(page.locator(".substate-feature")).to_have_count(0)
            mode.update(colored_counties=sum(mapped.values()), states=mapped, precinct_priority=True,
                        county_zoom=True, historical_year_isolation=True)
            proof["modes"].append(mode)
            print(json.dumps(mode), flush=True)
            context.close()
    for pattern in ([] if args.tables_only else ["**/county-results.json", "**/geometry/WA.geojson.gz"]):
        context = browser.new_context()
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route(pattern, lambda route: route.abort())
        page.goto(url)
        page.locator("#map-level").select_option("precinct")
        expect(page.locator("#state-select")).to_be_enabled()
        page.locator("#state-select").select_option("Washington")
        precinct(page, 2026, "WA")
        expect(page.locator('.substate-feature[data-color-level="county"]')).to_have_count(0)
        proof["failures_tested"].append(pattern)
        context.close()
    browser.close()
assert not errors, errors
proof.update(status="passed", renderer_sha256=hashlib.sha256(
    (root / "public/scripts/participation-explorer.js").read_bytes()).hexdigest())
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(proof, indent=2) + "\n")
print("Passed: source-matched tables and complete downloads in four display modes." if args.tables_only else
      "Passed: county counts/colors, precinct priority, zoom, historical isolation, four display modes and failure fallbacks.")

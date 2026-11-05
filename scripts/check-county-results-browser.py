"""Verify county integration against pinned counts in local or production Pages."""

import argparse
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
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
base = args.base_url.rstrip("/")
url = base + "/voter-participation/"
pointer = json.loads((root / "public/county-results.json").read_text())
directory = root / pointer["data_directory"]
index = json.loads((directory / "index.json").read_text())
rows = json.loads((directory / "margins.json").read_text())
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
             "scripts/participation-explorer.js"]:
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
            assert pointer["complete_download_url"] in downloads
            if pointer.get("party_votes"):
                parties = pointer["party_votes"]
                assert parties["complete_download_url"] in downloads
                assert {parties["base_url"] + table["file"] for table in parties["tables"]} <= downloads
                expect(page.locator("#downloads")).to_contain_text("test data are withheld")
            expect(page.locator("#downloads")).to_contain_text(f"{len(index['coverage'])} states")
            expect(page.locator("#downloads")).to_contain_text("not precinct results")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            mode = {"mobile": mobile, "javascript": javascript, "complete_downloads": len(downloads)}
            if javascript:
                mode["overview_transport"] = "raw gzip" if mobile else "server response"
            if not javascript:
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
    for pattern in ["**/county-results.json", "**/geometry/WA.geojson.gz"]:
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
print("Passed: county counts/colors, precinct priority, zoom, historical isolation, four display modes and failure fallbacks.")

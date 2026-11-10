"""Verify actual Massachusetts source counts, native references, navigation and failure recovery."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PRIOR_VERSION = "20261110-massachusetts-native-local-counts-01"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
parser.add_argument("--city-reference-extension", action="store_true")
args = parser.parse_args()
VERSION = "20261110-massachusetts-city-precinct-reference-02" if args.city_reference_extension else PRIOR_VERSION
assert not args.proof.exists()
base = args.base_url.rstrip("/")
source = ROOT / "data/county-source-reviews" / PRIOR_VERSION
queries = json.loads((source / "native-count-review-01/complete-native-count-queries.json").read_bytes())
expected_units = {
    f'Boston:Ward:{row["ward"]}:Precinct:{row["precinct"]}': row["times_cast_literal"]
    for row in queries["boston_all_times_cast_frames"]["SENATOR IN CONGRESS (Vote for 1)"]
}
expected_units.update({
    f'Somerville:Ward:{row["ward"]}:Precinct:{row["precinct"]}': row["ballots_cast_literal"]
    for row in queries["somerville_native_counts"] if row["native_level"] == "precinct"
})
held = set() if args.city_reference_extension else {
    f"Somerville:Ward:{ward}:Precinct:{precinct}"
    for ward, precinct in [(1, 4), (2, 1), (4, 2), (6, 3)]}
mapped = 307-len(held)
assert len(expected_units) == 307
cases = []


def choose(page):
    page.locator("#map-reset").click()
    shape = page.locator('.map-feature[data-state="Massachusetts"]')
    shape.scroll_into_view_if_needed()
    point = shape.evaluate("""path => {
      const b=path.getBBox(),p=path.ownerSVGElement.createSVGPoint();
      for (const y of [.5,.25,.75,.125,.375,.625,.875])
        for (const x of [.5,.25,.75,.125,.375,.625,.875]) {
          p.x=b.x+b.width*x;p.y=b.y+b.height*y;
          if(path.isPointInFill(p)) {
            const q=p.matrixTransform(path.getScreenCTM());
            if(document.elementFromPoint(q.x,q.y)===path)return{x:q.x,y:q.y};
          }
        }
      throw Error("No clickable Massachusetts interior");
    }""")
    page.mouse.click(point["x"], point["y"])


def verify_cities(page):
    shapes = page.locator('.geographic-detail [data-level="municipality"]')
    expect(shapes).to_have_count(350, timeout=90000)
    values = shapes.evaluate_all("""els=>els.map(e=>({key:e.dataset.geography,count:e.dataset.count,
      rate:e.dataset.rate,year:e.dataset.referenceYear,margin:e.getAttribute('data-margin')}))""")
    assert {row["key"]: int(row["count"]) for row in values if row["count"]} == {
        "MA:TOWN:035": 185569, "MA:TOWN:274": 64597}
    assert sum(row["count"] == "" for row in values) == 348
    assert not any(row["key"] == "MA:TOWN:315" for row in values)
    assert all(row["rate"] == "" and row["year"] == "current" and row["margin"] is None for row in values)
    expect(page.locator("#title")).to_have_text("City source counts in Massachusetts")
    expect(page.locator("#caption")).to_contain_text("Other 349 source areas have no count")
    expect(page.locator("#caption")).to_contain_text("invalid Wayland geometry is held")
    page.select_option("#current-county-select", "additional:MA:city:MA:TOWN:035")
    expect(page.locator("#current-county-detail")).to_contain_text("185,569")
    expect(page.locator("#current-county-detail")).to_contain_text("556,369")
    expect(page.locator("#current-county-detail")).to_contain_text("not substituted")
    assert page.locator('#current-unit-select option:not([value=""])').count() == 275
    page.select_option("#current-unit-select", "Boston:Ward:1:Precinct:15")
    expect(page.locator("#current-unit-detail .selection-rate")).to_have_text("0")
    page.select_option("#current-county-select", "additional:MA:city:MA:TOWN:274")
    expect(page.locator("#current-county-detail")).to_contain_text("64,597")
    expect(page.locator("#current-county-detail")).to_contain_text("56,008")
    expect(page.locator("#current-county-detail")).to_contain_text("UnOfficial")
    assert page.locator('#current-unit-select option:not([value=""])').count() == 32
    page.select_option("#current-unit-select", "Somerville:Ward:1:Precinct:4")
    expect(page.locator("#current-unit-detail")).to_contain_text("1,136")
    expect(page.locator("#current-unit-detail")).to_contain_text(
        "All 32 reporting units join direct city reference polygons" if args.city_reference_extension
        else "not clipped or inferred")


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in [False, True]:
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            assert response.ok
            expect(page.locator('.map-feature[data-state="Massachusetts"]')).to_have_count(1, timeout=90000)
            choose(page)
            verify_cities(page)
            raw = page.request.get(base + "/participation-local/MA.json.gz")
            assert raw.ok
            data = json.loads(gzip.decompress(raw.body()))
            assert len(data["counties"]) == 2 and len(data["precincts"]) == 307
            assert {row["unit_key"]: row["ballots"] for row in data["precincts"]} == expected_units
            assert all(row["denominator"] is None and row["reported_pct"] is None
                       for row in [*data["counties"], *data["precincts"]])
            assert all(not row["maps_approved"] for row in data["precincts"])
            unknown = page.locator('.geographic-detail [data-level="municipality"][data-count=""]').first
            unknown.focus()
            unknown.press("Enter")
            expect(page.locator("#current-county-select")).to_have_value("")
            expect(page.locator("#current-county-detail")).to_contain_text("unknown, not zero")
            page.select_option("#mode", "official")
            verify_cities(page)
            for mode in ["in_person_early", "mail_returned"]:
                page.select_option("#mode", mode)
                expect(page.locator("#mode")).to_have_value(mode)
                expect(page.locator('.geographic-detail [data-level="municipality"][data-count]:not([data-count=""])')).to_have_count(0)
            page.select_option("#mode", "available")
            verify_cities(page)
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-panel")).to_be_visible()
            expect(page.locator("#methods-archive")).to_be_hidden()
            assert len(page.locator("#methods-panel").inner_text()) < 4500
            page.locator("#tab-states").click()
            expect(page.locator("#state-select")).to_have_value("Massachusetts")
            expect(page.locator("#year")).to_have_value("2026")
            verify_cities(page)
            page.locator("#tab-precincts").click()
            expect(page.locator("#precinct-state-select")).to_have_value("Massachusetts")
            shapes = page.locator('.geographic-detail [data-level="precinct"], .geographic-detail [data-level="subprecinct"]')
            expect(shapes).to_have_count(mapped, timeout=90000)
            actual = shapes.evaluate_all("""els=>els.map(e=>({key:e.dataset.geography,count:e.dataset.count,
              rate:e.dataset.rate,year:e.dataset.referenceYear,level:e.dataset.level,
              city:e.dataset.sourceCity,revision:e.dataset.referenceRevision}))""")
            assert {row["key"].removeprefix("MA|"): int(row["count"]) for row in actual} == {
                key: value for key, value in expected_units.items() if key not in held}
            assert sum(row["level"] == "subprecinct" for row in actual) == 4
            assert all(row["rate"] == "" and row["year"] == (
                "current" if args.city_reference_extension and row["city"] == "Somerville" else "2022")
                for row in actual)
            if args.city_reference_extension:
                assert all(row["revision"] == "2023-09-22" for row in actual if row["city"] == "Somerville")
            expect(page.locator("#title")).to_have_text("Native reporting-unit counts in Boston and Somerville")
            expect(page.locator("#coverage-note")).to_contain_text(
                "Four former split-parent holds now use actual city polygons" if args.city_reference_extension
                else "Four Somerville split-parent counts remain table-only")
            first = page.locator('[data-source-city="Boston"][data-source-ward="1"][data-source-precinct="1"]')
            first.focus()
            first.press("Enter")
            expect(page.locator("#substate-detail")).to_contain_text("802")
            expect(page.locator("#substate-detail")).to_contain_text("Native Times Cast")
            chart = page.locator("#visualization svg.turnout-map")
            zoom = float(chart.get_attribute("data-zoom"))
            page.locator("#map-zoom-in").click()
            page.wait_for_function("previous => +document.querySelector('.turnout-map').dataset.zoom === previous*2", arg=zoom)
            chart.focus()
            before = chart.get_attribute("viewBox")
            chart.press("ArrowRight")
            assert chart.get_attribute("viewBox") != before
            retained = chart.get_attribute("viewBox")
            viewport = page.viewport_size
            page.set_viewport_size(dict(width=viewport["width"]-20, height=viewport["height"]))
            expect(shapes).to_have_count(mapped, timeout=90000)
            page.wait_for_timeout(350)
            expect(page.locator("#visualization svg.turnout-map")).to_have_attribute("viewBox", retained)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("#tab-states").click()
            expect(page.locator("#current-county-select")).to_have_value("additional:MA:city:MA:TOWN:035")
            expect(page.locator("#current-unit-select")).to_have_value("Boston:Ward:1:Precinct:1")
            expect(page.locator("#current-unit-detail")).to_contain_text("subsequent review qualifies")
            page.locator("#tab-precincts").click()
            sub = page.locator('[data-source-city="Somerville"][data-source-ward="1"][data-source-precinct="4A"]')
            expect(sub).to_have_count(1, timeout=90000)
            sub.focus()
            sub.press("Enter")
            expect(page.locator("#substate-detail")).to_contain_text("652")
            page.locator("#tab-states").click()
            expect(page.locator("#current-county-select")).to_have_value("additional:MA:city:MA:TOWN:274")
            expect(page.locator("#current-unit-select")).to_have_value("Somerville:Ward:1:Precinct:4A")
            page.select_option("#current-unit-select", "Somerville:Ward:1:Precinct:4")
            expect(page.locator("#current-unit-detail")).to_contain_text(
                "All 32 reporting units join direct city reference polygons" if args.city_reference_extension
                else "not clipped or inferred")
            if args.city_reference_extension:
                for ward, precinct in [(1, 4), (2, 1), (4, 2), (6, 3)]:
                    page.locator("#tab-precincts").click()
                    direct = page.locator(f'[data-source-city="Somerville"][data-source-ward="{ward}"]'
                                          f'[data-source-precinct="{precinct}"]')
                    expect(direct).to_have_count(1, timeout=90000)
                    direct.focus()
                    direct.press("Enter")
                    unit = f"Somerville:Ward:{ward}:Precinct:{precinct}"
                    expect(page.locator("#substate-detail")).to_contain_text(f"{expected_units[unit]:,}")
                    page.locator("#tab-states").click()
                    expect(page.locator("#current-unit-select")).to_have_value(unit)
                    expect(page.locator("#current-unit-detail")).not_to_contain_text("Native parent geometry contains")
            assert not errors, errors
            cases.append(dict(mobile=mobile, native_city_sources=2, all_source_reporting_rows=307,
                mapped_reporting_references=mapped, municipal_display_references=350,
                invalid_Wayland_held=True, split_parent_holds=len(held), literal_zeros_preserved=True,
                native_field_disagreements_retained=True, no_rates=True,
                unsupported_modes_not_substituted=True, unknown_clears_previous_detail=True,
                methods_roundtrip=True, both_city_selection_roundtrips=True,
                native_subprecinct_labels_preserved=True, zoom_pan_resize_preserved=True,
                former_four_holds_direct_clicks_verified=args.city_reference_extension,
                explicit_city_reference_revision_verified=args.city_reference_extension))
            context.close()

        context = browser.new_context()
        page = context.new_page()
        def malformed_city(route):
            response = route.fetch()
            data = json.loads(gzip.decompress(response.body()))
            for row in data["counties"]:
                row["reference_geometry"]["boundary_year"] = 2026
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(data).encode()))
        page.route("**/participation-local/MA.json.gz", malformed_city)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="Massachusetts"]')).to_have_count(1, timeout=90000)
        choose(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified Massachusetts native city", timeout=90000)
        page.unroute("**/participation-local/MA.json.gz", malformed_city)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify_cities(page)
        context.close()

        precinct_path = f"/participation-precincts/{VERSION}/"
        original = (ROOT / ("public"+precinct_path) / "MA.geojson.gz").read_bytes()
        for valid_checksum in [False, True]:
            context = browser.new_context()
            page = context.new_page()
            altered = json.loads(gzip.decompress(original))
            target = next(feature for feature in altered["features"]
                          if feature["properties"]["county"] == "Somerville") if args.city_reference_extension else altered["features"][0]
            target["properties"]["reference_geometry"]["rest_layer_id"] = 1
            bad = gzip.compress(json.dumps(altered).encode(), mtime=0)
            def corrupt_geometry(route):
                response = route.fetch()
                headers = dict(response.headers)
                headers.pop("content-length", None)
                headers.pop("content-encoding", None)
                route.fulfill(status=200, headers=headers, body=bad)
            def matching_checksum(route):
                response = route.fetch()
                data = response.json()
                data["state_metadata"]["MA"].update(bytes=len(bad), sha256=hashlib.sha256(bad).hexdigest())
                route.fulfill(response=response, json=data)
            page.route("**"+precinct_path+"MA.geojson.gz", corrupt_geometry)
            if valid_checksum:
                page.route("**"+precinct_path+"index.json", matching_checksum)
            page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            expect(page.locator('.map-feature[data-state="Massachusetts"]')).to_have_count(1, timeout=90000)
            choose(page)
            page.locator("#tab-precincts").click()
            expect(page.locator("#coverage-note")).to_contain_text(
                "Unqualified Massachusetts native reporting reference" if valid_checksum else "checksum disagrees",
                timeout=90000)
            expect(page.locator('.geographic-detail [data-source-city]')).to_have_count(0)
            page.unroute("**"+precinct_path+"MA.geojson.gz", corrupt_geometry)
            if valid_checksum:
                page.unroute("**"+precinct_path+"index.json", matching_checksum)
                page.reload(wait_until="domcontentloaded")
            else:
                page.get_by_role("button", name="Retry precinct source").click()
            expect(page.locator('.geographic-detail [data-level="precinct"], .geographic-detail [data-level="subprecinct"]')).to_have_count(mapped, timeout=90000)
            context.close()
    finally:
        browser.close()

proof = dict(status=f"PASS_MA_two_city_sources307rows{mapped}native_references350valid_municipalities",
    base_url=base, cases=cases, false_reference_rejected=True, actual_city_retry_restores_selectors=True,
    source_checksum_rejected_and_retry_restores_map=True,
    wrong_reference_role_rejected_after_valid_checksum=True, complete_native_inputs_retained=True,
    source_counts_repaired=False, legal_2026_precinct_certification=False, nationwide_project_complete=False)
args.proof.write_text(json.dumps(proof, indent=2)+"\n")
print(json.dumps(proof))

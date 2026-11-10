"""Verify actual city counters, all ward rows, raw source conflicts and unknown municipal context."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
parser.add_argument("--dover-reference-extension", action="store_true")
args = parser.parse_args()
ward_count = 37 if args.dover_reference_extension else 31
assert not args.proof.exists()
base = args.base_url.rstrip("/")
version = ROOT / "data/county-source-reviews/20261110-new-hampshire-cities-01"
readings = json.loads((version / "native-readings.json").read_bytes())
m = readings["manchester"]
c = readings["concord"]
manchester = sum(r["total"] for r in m["wards"])
concord = c["native_city_total_cast"]
extension = ROOT / "data/county-source-reviews/20261110-new-hampshire-cities-02"
n = json.loads((extension / "nashua-native-readings.json").read_bytes())
d = json.loads((extension / "dover-native-readings.json").read_bytes())
nashua = sum(row["total"] for row in n["wards"])
dover = d["native_ballot_rows"][-1]["total"]
cases = []


def choose(page):
    page.locator("#map-reset").click()
    shape = page.locator('.map-feature[data-state="New Hampshire"]')
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
      throw Error("No clickable New Hampshire interior");
    }""")
    page.mouse.click(point["x"], point["y"])


def verify(page):
    shapes = page.locator('.geographic-detail [data-level="municipality"]')
    expect(shapes).to_have_count(259, timeout=90000)
    actual = shapes.evaluate_all("els=>els.map(e=>({key:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear,margin:e.getAttribute('data-margin')}))")
    assert {r["key"]: int(r["count"]) for r in actual if r["count"]} == {
        "3345140": manchester, "3314200": concord, "3350260": nashua, "3318820": dover}
    assert sum(r["count"] == "" for r in actual) == 255
    assert all(r["rate"] == "" and r["year"] == "2024" and r["margin"] is None for r in actual)
    expect(page.locator("#title")).to_have_text("City source counts in New Hampshire")
    expect(page.locator("#caption")).to_contain_text("255 areas remain unknown")
    expect(page.locator("#caption")).to_contain_text("All37 ward rows remain available in tables")
    page.select_option("#current-county-select", "additional:NH:city:3345140")
    expect(page.locator("#current-county-detail")).to_contain_text(f"{manchester:,}")
    expect(page.locator("#current-county-detail")).to_contain_text("85-ballot discrepancy")
    expect(page.locator("#current-county-detail")).to_contain_text("never added")
    units = page.locator("#current-unit-select")
    assert units.locator('option:not([value=""])').count() == 12
    units.select_option("Manchester:Ward:7")
    expect(page.locator("#current-unit-detail")).to_contain_text("2,712")
    expect(page.locator("#current-unit-detail")).to_contain_text("not approved as precinct geography")
    page.select_option("#current-county-select", "additional:NH:city:3314200")
    expect(page.locator("#current-county-detail")).to_contain_text("19,234")
    expect(page.locator("#current-county-detail")).to_contain_text("25879")
    expect(page.locator("#current-county-detail")).to_contain_text("27340")
    expect(page.locator("#current-county-detail")).to_contain_text("74.32%")
    expect(page.locator("#current-county-detail")).to_contain_text("Analysis fraction withheld")
    assert page.locator('#current-unit-select option:not([value=""])').count() == 10
    page.select_option("#current-unit-select", "Concord:Ward:1")
    expect(page.locator("#current-unit-detail")).to_contain_text("1,985")
    expect(page.locator("#current-unit-detail")).to_contain_text("school-district source cells")
    page.select_option("#current-county-select", "additional:NH:city:3350260")
    expect(page.locator("#current-county-detail")).to_contain_text("33,849")
    expect(page.locator("#current-county-detail")).to_contain_text("+1/-2/-1")
    expect(page.locator("#current-county-detail")).to_contain_text("cancelled3264/3489")
    expect(page.locator("#current-county-detail")).to_contain_text("federal-only92 is never added")
    assert page.locator('#current-unit-select option:not([value=""])').count() == 9
    page.select_option("#current-unit-select", "Nashua:Ward:4")
    expect(page.locator("#current-unit-detail")).to_contain_text("2,086")
    page.select_option("#current-county-select", "additional:NH:city:3318820")
    expect(page.locator("#current-county-detail")).to_contain_text("15,941")
    expect(page.locator("#current-county-detail")).to_contain_text("20972")
    expect(page.locator("#current-county-detail")).to_contain_text("22456")
    expect(page.locator("#current-county-detail")).to_contain_text("71.0%")
    expect(page.locator("#current-county-detail")).to_contain_text("not ballot choice or group turnout")
    assert page.locator('#current-unit-select option:not([value=""])').count() == 6
    page.select_option("#current-unit-select", "Dover:Ward:1")
    expect(page.locator("#current-unit-detail")).to_contain_text("2,577")
    expect(page.locator("#current-unit-detail")).to_contain_text("68.2%")
    expect(page.locator("#current-unit-detail")).to_contain_text("Checklist3447")


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in (False, True):
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            assert response.ok
            expect(page.locator('.map-feature[data-state="New Hampshire"]')).to_have_count(1, timeout=90000)
            choose(page)
            verify(page)
            api = page.request.get(base + "/participation-local/NH.json.gz")
            assert api.ok
            data = json.loads(gzip.decompress(api.body()))
            assert len(data["counties"]) == 4 and len(data["precincts"]) == 37
            assert all(r["denominator"] is None and r["reported_pct"] is None
                       for r in [*data["counties"], *data["precincts"]])
            assert all(not r["maps_approved"] for r in data["precincts"])
            by_ward = {r["unit_key"]: r for r in data["precincts"]}
            for native in m["wards"]:
                row = by_ward[f'Manchester:Ward:{native["ward"]}']
                assert row["native_record"] == native and row["ballots"] == native["total"]
            for native in n["wards"]:
                row = by_ward[f'Nashua:Ward:{native["ward"]}']
                assert row["native_record"] == native and row["ballots"] == native["total"]
            for native, register in zip(d["native_ballot_rows"][:-1], d["native_register_rows"][:-1]):
                row = by_ward[f'Dover:Ward:{native["ward"]}']
                assert row["native_record"] == {"ballots": native, "registrations": register}
                assert row["ballots"] == native["total"] and row["native_printed_pct"] == native["printed_turnout"]
            unknown = page.locator('.geographic-detail [data-level="municipality"][data-count=""]').first
            unknown.focus()
            unknown.press("Enter")
            expect(page.locator("#current-county-detail")).to_contain_text("unknown, not zero")
            expect(page.locator("#current-county-select")).to_have_value("")
            page.select_option("#mode", "official")
            verify(page)
            for mode in ("in_person_early", "mail_returned"):
                page.select_option("#mode", mode)
                expect(page.locator("#mode")).to_have_value(mode)
                expect(page.locator('.geographic-detail [data-level="municipality"][data-count]:not([data-count=""])')).to_have_count(0)
            page.select_option("#mode", "available")
            verify(page)
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-panel")).to_be_visible()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            expect(page.locator("#state-select")).to_have_value("New Hampshire")
            expect(page.locator("#year")).to_have_value("2026")
            verify(page)
            page.locator("#tab-precincts").click()
            expect(page.locator("#precinct-state-select")).to_have_value("New Hampshire")
            expect(page.locator('.geographic-detail [data-level="precinct"]')).to_have_count(0)
            ward_shapes = page.locator('.geographic-detail [data-level="ward"]')
            expect(ward_shapes).to_have_count(ward_count, timeout=90000)
            expect(page.locator("#title")).to_have_text(
                "Native ward counts in four New Hampshire cities" if args.dover_reference_extension
                else "Native ward counts in three New Hampshire cities")
            ward_values = ward_shapes.evaluate_all("els=>els.map(e=>({city:e.dataset.sourceCity,ward:e.dataset.sourceWard,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear}))")
            assert {int(row["ward"]):int(row["count"]) for row in ward_values if row["city"] == "Manchester"} == {
                row["ward"]:row["total"] for row in m["wards"]}
            assert sum(int(row["count"]) for row in ward_values if row["city"] == "Concord") == 19234
            assert {int(row["ward"]):int(row["count"]) for row in ward_values if row["city"] == "Nashua"} == {
                row["ward"]:row["total"] for row in n["wards"]}
            if args.dover_reference_extension:
                assert {int(row["ward"]): int(row["count"]) for row in ward_values if row["city"] == "Dover"} == {
                    row["ward"]: row["total"] for row in d["native_ballot_rows"][:-1]}
            assert all(row["rate"] == "" and row["year"] == (
                "2022" if row["city"] == "Manchester" or args.dover_reference_extension and row["city"] == "Dover"
                else "current") for row in ward_values)
            expect(page.locator("#geography-note")).to_contain_text("fourteen Concord native overlaps")
            ward7 = page.locator('[data-level="ward"][data-source-city="Manchester"][data-source-ward="7"]')
            ward7.focus()
            ward7.press("Enter")
            expect(page.locator("#substate-detail")).to_contain_text("2,712")
            expect(page.locator("#substate-detail")).to_contain_text("component-minus-printed total85")
            expect(ward7).to_have_class("map-feature substate-feature selected")
            chart = page.locator("#visualization svg.turnout-map")
            zoom = float(chart.get_attribute("data-zoom"))
            page.locator("#map-zoom-in").click()
            page.wait_for_function("previous => +document.querySelector('.turnout-map').dataset.zoom === previous * 2",
                                   arg=zoom)
            chart.focus()
            before_pan = chart.get_attribute("viewBox")
            chart.press("ArrowRight")
            assert chart.get_attribute("viewBox") != before_pan
            box = chart.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.wheel(0, -180)
            page.wait_for_function("previous => +document.querySelector('.turnout-map').dataset.zoom > previous",
                                   arg=zoom * 2)
            retained = chart.get_attribute("viewBox")
            viewport = page.viewport_size
            page.set_viewport_size(dict(width=viewport["width"] - 20, height=viewport["height"]))
            expect(page.locator('.geographic-detail [data-level="ward"]')).to_have_count(ward_count)
            page.wait_for_timeout(350)
            expect(page.locator("#visualization svg.turnout-map")).to_have_attribute("viewBox", retained)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("#tab-states").click()
            expect(page.locator("#current-county-select")).to_have_value("additional:NH:city:3345140")
            expect(page.locator("#current-unit-select")).to_have_value("Manchester:Ward:7")
            expect(page.locator("#current-unit-detail")).to_contain_text("current Manchester municipal ward context")
            page.locator("#tab-precincts").click()
            concord1 = page.locator('[data-level="ward"][data-source-city="Concord"][data-source-ward="1"]')
            expect(concord1).to_have_count(1, timeout=90000)
            concord1.focus()
            concord1.press("Enter")
            expect(page.locator("#substate-detail")).to_contain_text("1,985")
            expect(page.locator("#substate-detail")).to_contain_text("not an analysis rate")
            page.locator("#tab-states").click()
            expect(page.locator("#current-county-select")).to_have_value("additional:NH:city:3314200")
            expect(page.locator("#current-unit-select")).to_have_value("Concord:Ward:1")
            expect(page.locator("#current-unit-detail")).to_contain_text("current Concord municipal ward context")
            page.locator("#tab-precincts").click()
            nashua8 = page.locator('[data-level="ward"][data-source-city="Nashua"][data-source-ward="8"]')
            expect(nashua8).to_have_count(1, timeout=90000)
            nashua8.focus()
            nashua8.press("Enter")
            expect(page.locator("#substate-detail")).to_contain_text("3,575")
            expect(page.locator("#substate-detail")).to_contain_text("component-minus-printed total-1")
            page.locator("#tab-states").click()
            expect(page.locator("#current-county-select")).to_have_value("additional:NH:city:3350260")
            expect(page.locator("#current-unit-select")).to_have_value("Nashua:Ward:8")
            expect(page.locator("#current-unit-detail")).to_contain_text("current Nashua municipal ward context")
            if args.dover_reference_extension:
                for native in d["native_ballot_rows"][:-1]:
                    page.locator("#tab-precincts").click()
                    direct = page.locator(f'[data-level="ward"][data-source-city="Dover"][data-source-ward="{native["ward"]}"]')
                    expect(direct).to_have_count(1, timeout=90000)
                    direct.focus()
                    direct.press("Enter")
                    expect(page.locator("#substate-detail")).to_contain_text(f'{native["total"]:,}')
                    expect(page.locator("#substate-detail")).to_contain_text("not an analysis rate")
                    page.locator("#tab-states").click()
                    expect(page.locator("#current-county-select")).to_have_value("additional:NH:city:3318820")
                    expect(page.locator("#current-unit-select")).to_have_value(f'Dover:Ward:{native["ward"]}')
                    expect(page.locator("#current-unit-detail")).to_contain_text("current Dover municipal ward context")
            assert not errors, errors
            cases.append(dict(mobile=mobile, native_city_counts=4, native_ward_rows=37,
                full_context_areas=259, unknown_not_zero=255, source_conflicts_retained=True,
                federal_only_not_added=True, no_rates=True, no_old_shapes_as_2026_wards=True,
                native_registers_and_percent_separate=True, unsupported_modes_not_substituted=True,
                dover_native_date_not_filename=True, nashua_source_amendments_retained=True,
                native_manchester_ward_counts=12, native_concord_ward_counts=10, native_nashua_ward_counts=9,
                native_dover_ward_counts=6 if args.dover_reference_extension else 0,
                mapped_native_ward_references=ward_count,
                all_six_Dover_click_roundtrips=args.dover_reference_extension,
                nashua_adopted_not_proposed_or_point_parcel_geometry=True,
                concord_vintage_not_inferred_from_2020_service_name=True, ward_reference_year=2022,
                no_certified2026_legal_precinct_claim=True, native_ward_source_conflict_preserved=True,
                methods_roundtrip=True, ward_zoom_pan_and_resize_preserved=True))
            context.close()
        context = browser.new_context()
        page = context.new_page()
        def malformed(route):
            response = route.fetch()
            data = json.loads(gzip.decompress(response.body()))
            for row in data["counties"]:
                row["reference_geometry"]["boundary_year"] = 2026
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(data).encode()))
        page.route("**/participation-local/NH.json.gz", malformed)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="New Hampshire"]')).to_have_count(1, timeout=90000)
        choose(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified New Hampshire native city", timeout=90000)
        expect(page.locator(".geographic-detail .map-feature")).to_have_count(0)
        page.unroute("**/participation-local/NH.json.gz", malformed)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify(page)
        context.close()
        ward_path = ("/participation-precincts/20261110-new-hampshire-ward-reference-04/"
                     if args.dover_reference_extension else
                     "/participation-precincts/20261110-new-hampshire-ward-reference-03/")
        original = (ROOT / ("public" + ward_path) / "NH.geojson.gz").read_bytes()
        for invalid_scope in (False, True):
            context = browser.new_context()
            page = context.new_page()
            bad = json.loads(gzip.decompress(original))
            bad["features"][0]["properties"]["reference_geometry"]["rest_layer_id"] = 0
            if invalid_scope:
                bad = json.loads(gzip.decompress(original))
                next(f for f in bad["features"] if f["properties"]["county"] == (
                    "Dover" if args.dover_reference_extension else "Nashua"))[
                    "properties"]["reference_geometry"]["rest_layer_id"] = 5 if args.dover_reference_extension else 6
            altered = gzip.compress(json.dumps(bad).encode(), mtime=0)
            def corrupt_geometry(route):
                response = route.fetch()
                headers = dict(response.headers)
                headers.pop("content-length", None)
                headers.pop("content-encoding", None)
                route.fulfill(status=200, headers=headers, body=altered)
            def matching_checksum(route):
                response = route.fetch()
                data = response.json()
                data["state_metadata"]["NH"].update(bytes=len(altered),
                    sha256=hashlib.sha256(altered).hexdigest())
                route.fulfill(response=response, json=data)
            page.route("**" + ward_path + "NH.geojson.gz", corrupt_geometry)
            if invalid_scope:
                page.route("**" + ward_path + "index.json", matching_checksum)
            page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            expect(page.locator('.map-feature[data-state="New Hampshire"]')).to_have_count(1, timeout=90000)
            choose(page)
            page.locator("#tab-precincts").click()
            expect(page.locator("#coverage-note")).to_contain_text(
                "Unqualified New Hampshire native ward" if invalid_scope else "checksum disagrees", timeout=90000)
            expect(page.locator('.geographic-detail [data-level="ward"]')).to_have_count(0)
            page.unroute("**" + ward_path + "NH.geojson.gz", corrupt_geometry)
            if invalid_scope:
                page.unroute("**" + ward_path + "index.json", matching_checksum)
                page.reload(wait_until="domcontentloaded")
            else:
                page.get_by_role("button", name="Retry precinct source").click()
            expect(page.locator('.geographic-detail [data-level="ward"]')).to_have_count(ward_count, timeout=90000)
            context.close()
    finally:
        browser.close()
proof = dict(status="PASS_NH_four_native_city_sources_37ward_rows_on2024_context_NOT_county_or_precinct_totals",
    base_url=base, cases=cases, false_reference_rejected=True, actual_retry_restores_selectors=True,
    ward_checksum_rejected_and_retry_restores_map=True, wrong_rest_layer_rejected_after_valid_checksum=True,
    valid_source_overrides=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

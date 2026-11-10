"""Verify Illinois source-region activity without whole-county or city-allocation claims."""

import argparse
import gzip
import json
from pathlib import Path
import re

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
version = ROOT / "data/county-source-reviews/20261110-illinois-county-context-01"
inputs = json.loads((version / "inputs.json").read_bytes())
native = {category: json.loads((ROOT / row["path"]).read_bytes())
          for category, row in inputs["responses"].items()}
reference = json.loads(gzip.decompress((ROOT / inputs["reference"]["path"]).read_bytes()))


def key(name):
    return re.sub("[^a-z0-9]", "", re.sub(r" County$", "", name).lower())


by_name = {key(f["properties"]["name"]): f["properties"]["key"] for f in reference["features"]}
expected, cities = {}, {}
for category, source in native.items():
    expected[category] = {by_name[key(name)]: sum(c["votes"] for c in categories.values())
        for name, categories in source["regions"].items() if not name.startswith("City of ")}
    cities[category] = {name: sum(c["votes"] for c in categories.values())
        for name, categories in source["regions"].items() if name.startswith("City of ")}
cases = []


def choose(page):
    page.locator("#map-reset").click()
    shape = page.locator('.map-feature[data-state="Illinois"]')
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
      throw Error("No clickable Illinois interior");
    }""")
    page.mouse.click(point["x"], point["y"])


def verify(page, category):
    shapes = page.locator('.geographic-detail [data-level="county"]')
    expect(shapes).to_have_count(102, timeout=90000)
    expect(page.locator('[data-level="county"][data-geography="17031"]')).to_have_attribute(
        "data-count", str(expected[category]["17031"]), timeout=60000)
    actual = shapes.evaluate_all("els=>els.map(e=>({key:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,margin:e.getAttribute('data-margin')}))")
    assert set(r["key"] for r in actual) == set(expected[category])
    for row in actual:
        assert int(row["count"]) == expected[category][row["key"]]
        assert row["rate"] == "" and row["margin"] is None
    expect(page.locator("#title")).to_have_text("Source-region activity in Illinois")
    expect(page.locator("#caption")).to_contain_text("not whole-county totals")
    expect(page.locator("#caption")).to_contain_text("not qualified electoral-authority territories")
    expect(page.locator("#table-head")).to_contain_text("County-named source region")
    expect(page.locator("#table-head")).not_to_contain_text("Democratic")
    expect(page.locator("#geography-note")).to_contain_text("six city-named records")
    held = page.locator("#source-region-holds")
    expect(held).to_be_visible()
    assert held.get_attribute("open") is None
    held.locator("summary").click()
    expect(held.locator("li")).to_have_count(6)
    for name, count in cities[category].items():
        expect(held).to_contain_text(f"{name}: {count:,}")
    held.locator("summary").click()
    page.select_option("#current-county-select", "additional:IL:source-region:17031")
    expect(page.locator("#current-county-detail")).to_contain_text(f'{expected[category]["17031"]:,}')
    expect(page.locator("#current-county-detail")).to_contain_text("never assigned or added into counties")
    expect(page.locator("#current-county-detail")).to_contain_text("2026-11-04")
    expect(page.locator("#current-county-detail")).not_to_contain_text("%")


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
            expect(page.locator('.map-feature[data-state="Illinois"]')).to_have_count(1, timeout=90000)
            choose(page)
            verify(page, "inperson")
            for mode, category in [("mail_returned", "returned"), ("in_person_early", "inperson")]:
                page.select_option("#mode", mode)
                verify(page, category)
            api = page.request.get(base + "/participation-local/IL.json.gz")
            assert api.ok
            data = json.loads(gzip.decompress(api.body()))
            for mode, category in [("in_person_early", "inperson"), ("mail_returned", "returned")]:
                rows, held = data["county_frames"][mode], data["county_frame_holds"][mode]
                assert len(rows) == 102 and len(held) == 6
                assert all(not r["whole_county_count_qualified"] and not r["source_authority_territory_qualified"]
                           and r["reported_pct"] is None and r["denominator"] is None for r in rows)
                assert {r["source_region"]: r["source_count"] for r in held} == cities[category]
                assert all(r["contextual_county_fips"] is None for r in held)
            page.select_option("#mode", "official")
            expect(page.locator("#title")).to_have_text("County contest counts in Illinois", timeout=60000)
            expect(page.locator("#source-region-holds")).to_have_count(0)
            page.select_option("#mode", "available")
            verify(page, "inperson")
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-panel")).to_be_visible()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            expect(page.locator("#state-select")).to_have_value("Illinois")
            expect(page.locator("#year")).to_have_value("2026")
            verify(page, "inperson")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(mobile=mobile, both_modes_exact102=True, six_city_records_retained=True,
                whole_county_and_authority_claims_false=True, no_city_allocation=True, no_rates=True,
                official_excludes_provider=True, methods_roundtrip=True, actual_state_click=True))
            context.close()
        context = browser.new_context()
        page = context.new_page()
        def malformed(route):
            response = route.fetch()
            data = json.loads(gzip.decompress(response.body()))
            data["county_frames"]["in_person_early"][0]["whole_county_count_qualified"] = True
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(data).encode()))
        page.route("**/participation-local/IL.json.gz", malformed)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="Illinois"]')).to_have_count(1, timeout=90000)
        choose(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified Illinois source-region context", timeout=90000)
        expect(page.locator(".geographic-detail .map-feature")).to_have_count(0)
        page.unroute("**/participation-local/IL.json.gz", malformed)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify(page, "inperson")
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_IL102_source_region_county_context_NOT_whole_county_totals",
    base_url=base, cases=cases, false_full_county_frame_rejected=True,
    actual_retry_recovered=True, valid_source_overrides=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

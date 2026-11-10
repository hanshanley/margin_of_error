"""Verify compact sidebars, actual map clicks and accessible county selection."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
cases = []


def click_shape(path):
    path.scroll_into_view_if_needed()
    point = path.evaluate("""path => {
      const b=path.getBBox(),p=path.ownerSVGElement.createSVGPoint();
      for (const steps of [8,16,32,64])
        for(let iy=0;iy<steps;iy++)for(let ix=0;ix<steps;ix++){
          p.x=b.x+b.width*(ix+.5)/steps;p.y=b.y+b.height*(iy+.5)/steps;
          if(path.isPointInFill(p)){
            const q=p.matrixTransform(path.getScreenCTM());
            if(document.elementFromPoint(q.x,q.y)===path)return{x:q.x,y:q.y};
          }
        }
      return null;
    }""")
    assert point is not None, "No exposed county interior for an actual pointer click"
    path.page.mouse.click(point["x"], point["y"])


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in [390, 1440]:
            page = browser.new_page(viewport=dict(width=width, height=1000))
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(args.base_url.rstrip("/") + "/voter-participation/"
                "?year=2026&state=Florida&mode=available&map-level=county&map-color=turnout",
                wait_until="domcontentloaded", timeout=90000)
            assert response.ok
            select = page.locator("#current-county-select")
            expect(select.locator("option")).to_have_count(68, timeout=90000)
            expect(page.locator("#reviewed-county-overview button")).to_have_count(0)
            expect(page.locator("#reviewed-county-overview")).to_contain_text("Click a place on the map")
            click_shape(page.locator('.map-feature[data-state="Florida"]'))
            paths = page.locator('.geographic-detail [data-level="county"]')
            expect(paths).to_have_count(67, timeout=90000)
            for fips, name in [("12105", "Polk"), ("12031", "Duval")]:
                page.locator("#map-reset").click()
                path = page.locator(f'.geographic-detail [data-geography="{fips}"]')
                expected_count = int(path.get_attribute("data-count"))
                county_id = path.get_attribute("data-source-county-id")
                click_shape(path)
                expect(select).to_have_value(county_id)
                detail = page.locator("#current-county-detail")
                expect(detail.locator("h4")).to_have_text(name)
                expect(detail.locator(".selection-rate")).to_have_text(f"{expected_count:,}")
            select.select_option(label="Sarasota")
            expect(page.locator("#current-county-detail h4")).to_have_text("Sarasota")
            selected_id = select.input_value()
            page.locator("#tab-methods").click()
            page.locator("#tab-states").click()
            expect(page.locator("#reviewed-county-overview button")).to_have_count(0)
            expect(page.locator("#current-county-select")).to_have_value(selected_id)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(width=width, hidden_full_button_list=True, county_choices=67,
                actual_map_clicks=2, compact_selector=True, tab_roundtrip=True, horizontal_overflow=False))
            page.close()
    finally:
        browser.close()
proof = dict(status="PASS_compact_sidebar_map_clicks_and_accessible_selection",
    base_url=args.base_url, cases=cases)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

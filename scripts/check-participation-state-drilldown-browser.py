"""Check real state clicks against the active, approved county bindings."""

import argparse
import json

from playwright.sync_api import expect, sync_playwright


def click_state(page, name, touch, keyboard=False):
    page.locator("#map-reset").click()
    page.wait_for_function("""() =>
      Number(document.querySelector('svg.turnout-map').getAttribute('viewBox').split(' ')[2]) === 1000
      && document.querySelectorAll('.geographic-detail .map-feature').length === 0""")
    path = page.locator(f'path.map-feature[data-state="{name}"]')
    path.scroll_into_view_if_needed()
    if keyboard:
        path.press("Enter")
        return
    point = path.evaluate("""path => {
      const box = path.getBBox(), point = path.ownerSVGElement.createSVGPoint();
      for (const y of [.5, .25, .75, .125, .375, .625, .875])
        for (const x of [.5, .25, .75, .125, .375, .625, .875]) {
          point.x = box.x + box.width * x; point.y = box.y + box.height * y;
          if (!path.isPointInFill(point)) continue;
          const screen = point.matrixTransform(path.getScreenCTM());
          if (document.elementFromPoint(screen.x, screen.y) === path)
            return {x: screen.x, y: screen.y};
        }
      throw new Error('No clickable interior point in selected state');
    }""")
    if touch:
        page.touchscreen.tap(point["x"], point["y"])
    else:
        page.mouse.click(point["x"], point["y"])


def check(base):
    cases = [("TX", "Texas", "available"), ("TX", "Texas", "official"),
             ("TX", "Texas", "in_person_early"), ("TX", "Texas", "mail_returned"),
             ("MI", "Michigan", "available"), ("PA", "Pennsylvania", "official"),
             ("TN", "Tennessee", "official"), ("WI", "Wisconsin", "available"),
             ("WI", "Wisconsin", "official"), ("NC", "North Carolina", "available")]
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            for width in (1280, 390):
                touch = width == 390
                page = browser.new_page(viewport={"width": width, "height": 950},
                                        has_touch=touch, is_mobile=touch)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                response = page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                assert response.ok
                expect(page.locator("svg.turnout-map")).to_be_visible(timeout=45000)
                previous = None
                for code, name, mode in cases:
                    expected = page.evaluate("""async ({code, mode}) => {
                      const c = await import('/scripts/participation-counts.js');
                      const n = await import('/scripts/participation-native-bindings.js');
                      const [state, binding] = await Promise.all([c.loadCountState(code), n.loadCountyBinding(code, mode)]);
                      const sources = c.countFrame(state, mode).counties;
                      const ids = new Set(binding ? binding.rows.map(row => row.county_id) : sources.map(row => row.county_id));
                      return {features: binding?.features ?? sources.length,
                        mapped: sources.filter(row => ids.has(row.county_id)).map(row => ({
                          id: row.county_id, count: row.ballots, rate: row.reported_pct ?? null})),
                        held_count: sources.filter(row => row.maps_approved === false && !ids.has(row.county_id)).length,
                        held: sources.filter(row => row.maps_approved === false && !ids.has(row.county_id))
                          .map(row => row.county_fips).filter(Boolean)};
                    }""", {"code": code, "mode": mode})
                    options = page.locator("#atlas-options")
                    if not options.evaluate("e => e.open"):
                        options.locator(":scope > summary").click()
                    page.locator("#mode").select_option(mode)
                    options.locator(":scope > summary").click()
                    click_state(page, name, touch, keyboard=previous == name)
                    previous = name
                    shapes = page.locator('.geographic-detail [data-level="county"]')
                    expect(shapes).to_have_count(expected["features"], timeout=45000)
                    expect(page.locator("#state-select")).to_have_value(name)
                    expect(page.locator("#geography-note")).not_to_contain_text("could not be loaded")
                    actual = shapes.evaluate_all("""els => els.map(e => ({
                      fips: e.dataset.geography, id: e.dataset.sourceCountyId,
                      count: e.dataset.count, rate: e.dataset.rate}))""")
                    painted = {row["id"]: row for row in actual if row["id"]}
                    approved = {row["id"]: row for row in expected["mapped"]}
                    assert painted.keys() == approved.keys(), (name, mode, painted.keys() ^ approved.keys())
                    for identity, source in approved.items():
                        for field in ("count", "rate"):
                            value = painted[identity][field]
                            assert (float(value) if value else None) == source[field], (name, identity, field)
                    held = {row["fips"]: row for row in actual if row["fips"] in expected["held"]}
                    assert all(not row["id"] and row["count"] == row["rate"] == "" for row in held.values())
                    if code == "TX" and mode in ("available", "official"):
                        assert len(held) == len(expected["held"]), (name, mode, held)
                    note = page.locator("#geography-note").text_content()
                    assert f"{len(approved)} county observations" in note, (name, mode, note)
                    if code == "TX" and mode == "available":
                        known = next(row for row in actual if row["id"] and row["count"])
                        page.locator(f'.geographic-detail [data-geography="{known["fips"]}"]').press("Enter")
                        expect(page.locator("#selection-panel > .selection-more")).to_have_attribute("open", "")
                        expect(page.locator("#current-county-detail")).to_be_visible()
                        missing = next(iter(held.values()))
                        page.locator(f'.geographic-detail [data-geography="{missing["fips"]}"]').press("Enter")
                        expect(page.locator("#current-county-detail")).to_contain_text("No approved map observation")
                    assert page.evaluate("document.documentElement.scrollWidth") == width
                    print(json.dumps({"width": width, "state": code, "mode": mode,
                                      "outlines": len(actual), "approved": len(painted),
                                      "held_rows_not_mapped": expected["held_count"]}), flush=True)
                assert not errors, errors
                page.close()
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8436")
    args = parser.parse_args()
    check(args.base)

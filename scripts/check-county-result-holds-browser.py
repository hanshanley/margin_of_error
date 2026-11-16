"""Check explicitly held county results using the actual explorer and public references."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
QUERY = ("?view=states&year=2026&basis=cvap&dimension=overall&group=All+groups"
         "&map-color=margin&map-level=county&mode=available&state=Maine")
HELD = '.substate-feature[data-results-status="withheld"]'


def county_values(page):
    return page.locator(HELD).evaluate_all("""paths => paths.map(p => ({
      key:p.dataset.geography, label:p.getAttribute('aria-label'),
      year:p.dataset.year, boundary:p.dataset.boundaryYear,
      fill:p.getAttribute('fill'), color:p.dataset.colorLevel,
      numeric:['data-count','data-rate','data-margin','data-total-votes']
        .some(name => p.hasAttribute(name)), focus:p.getAttribute('tabindex'),
      drawn:p.getAttribute('d').length > 20
    })).sort((a,b) => a.key.localeCompare(b.key))""")


def ready(page):
    expect(page.locator("#state-select option")).to_have_count(51, timeout=120000)
    expect(page.locator("svg.turnout-map")).to_be_visible(timeout=120000)


def held(page, expected, reason, download):
    expect(page.locator("#title")).to_have_text("County results unavailable in Maine", timeout=90000)
    expect(page.locator(HELD)).to_have_count(len(expected), timeout=90000)
    actual = county_values(page)
    assert [row["key"] for row in actual] == sorted(expected)
    for row in actual:
        assert row["label"].startswith(expected[row["key"]] + " "), row
        assert row["year"] == "2026" and row["boundary"] == "2024", row
        assert row["fill"] == "#d6d3cb" and row["color"] == "none", row
        assert not row["numeric"] and row["drawn"] and row["focus"] == "0", row
    expect(page.locator("#geography-note")).to_contain_text(reason)
    expect(page.locator("#geography-note")).to_contain_text("not verified 2026 election boundaries")
    expect(page.locator("#geography-note")).to_contain_text("Missing is not zero")
    expect(page.locator("#substate-detail")).to_contain_text("results are unavailable")
    expect(page.locator('#substate-detail a').filter(has_text="Complete county results")).to_have_attribute(
        "href", download)
    assert page.locator('path.map-feature[data-state="Maine"]').evaluate_all(
        "paths => paths.length > 0 && paths.every(p => p.style.opacity === '0')")
    table = page.locator("#table-body tr").evaluate_all(
        "rows => rows.map(row => [...row.cells].map(cell => cell.textContent))")
    assert len(table) == len(expected)
    for row in table:
        assert row[1] == expected[row[0]] and row[2:7] == ["2026", "2024", "\u2014", "\u2014", "withheld"], row
        assert row[7] == reason, row
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    return actual


def viewbox(page):
    return [float(value) for value in page.locator("svg.turnout-map").get_attribute("viewBox").split()]


def pointer_point(path):
    return path.evaluate("""p => {
      const box = p.getBoundingClientRect(), matrix = p.getScreenCTM().inverse();
      for (let y=1; y<20; y++) for (let x=1; x<20; x++) {
        const px=box.x+box.width*x/20, py=box.y+box.height*y/20;
        if (px<0 || py<0 || px>=innerWidth || py>=innerHeight) continue;
        if (p.isPointInFill(new DOMPoint(px,py).matrixTransform(matrix))
          && document.elementFromPoint(px,py) === p) return [px,py];
      }
      throw new Error('No visible county interior for pointer selection');
    }""")


def normal(browser, base, expected, reason, download, output):
    cases = []
    for width in (1440, 390):
        page = browser.new_page(viewport={"width": width, "height": 1100})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base + "/voter-participation/" + QUERY, wait_until="domcontentloaded", timeout=120000)
        ready(page)
        initial = held(page, expected, reason, download)
        initial_width = viewbox(page)[2]
        assert initial_width < 1000, "The initial Maine route must focus the selected state"
        for index, (key, name) in enumerate(sorted(expected.items())):
            path = page.locator(HELD + f'[data-geography="{key}"]')
            path.focus()
            path.press("Enter" if index % 2 else "Space")
            expect(page.locator("#substate-detail h4")).to_have_text(name)
            expect(page.locator(HELD + ".selected")).to_have_attribute("data-geography", key)
        page.locator("#state-select").select_option("Maine")
        expect(page.locator(HELD)).to_have_count(16)
        page.locator("svg.turnout-map").scroll_into_view_if_needed()
        path = page.locator(HELD + '[data-geography="23003"]')
        point = pointer_point(path)
        page.mouse.click(*point)
        expect(page.locator("#substate-detail h4")).to_have_text(expected["23003"])
        page.locator("#map-zoom-out").click()
        held(page, expected, reason, download)
        page.locator("#map-reset").click()
        page.wait_for_timeout(250)
        assert viewbox(page) == [0, 0, 1000, 610], viewbox(page)
        held(page, expected, reason, download)
        page.wait_for_timeout(250)
        assert viewbox(page) == [0, 0, 1000, 610], "Do not continually recenter after Reset"
        page.locator("#state-select").select_option("Florida")
        expect(page.locator("#title")).to_have_text("County election results in Florida", timeout=90000)
        expect(page.locator('.substate-feature[data-color-level="county"]')).to_have_count(67)
        expect(page.locator(HELD)).to_have_count(0)
        expect(page.locator("#table-head")).not_to_contain_text("Hold reason")
        page.locator("#state-select").select_option("Maine")
        held(page, expected, reason, download)
        page.locator("#year").select_option("2024")
        expect(page.locator("#year")).to_have_value("2024")
        expect(page.locator("#geography-note")).to_contain_text("2024")
        assert page.locator(".substate-feature").evaluate_all(
            "paths => paths.every(p => !p.getAttribute('aria-label').includes('2026'))")
        expect(page.locator(HELD)).to_have_count(0)
        expect(page.locator("#table-head")).not_to_contain_text("Hold reason")
        page.locator("#year").select_option("2026")
        held(page, expected, reason, download)
        page.locator("#map-level").select_option("district")
        expect(page.locator(HELD)).to_have_count(0)
        expect(page.locator("#table-head")).not_to_contain_text("Hold reason")
        page.locator("#map-level").select_option("county")
        held(page, expected, reason, download)
        page.locator("#map-color").select_option("turnout")
        expect(page.locator(HELD)).to_have_count(0)
        expect(page.locator("#table-head")).not_to_contain_text("Hold reason")
        page.locator("#map-color").select_option("margin")
        held(page, expected, reason, download)
        page.locator("svg.turnout-map").scroll_into_view_if_needed()
        image = output.with_name(output.stem + f"-{width}.png")
        page.screenshot(path=str(image))
        assert not errors, errors
        cases.append({"width": width, "initial_counties": initial,
                      "keyboard_selections": len(expected), "real_pointer_county": "23003",
                      "reset_preserved": True, "supported_state_and_year_transitions": True,
                      "missing_value_table": True, "page_errors": errors,
                      "image": {"file": image.name, "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}})
        page.close()
    return cases


def faults(browser, base, geometry_path, expected, reason, download):
    outcomes = []
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    page.route("**/" + geometry_path, lambda route: route.fulfill(status=503, body="Unavailable"))
    page.goto(base + "/voter-participation/" + QUERY, wait_until="domcontentloaded", timeout=120000)
    ready(page)
    retry = page.get_by_role("button", name="Retry geographic detail", exact=True)
    expect(retry).to_be_visible(timeout=90000)
    expect(page.locator(HELD)).to_have_count(0)
    page.unroute("**/" + geometry_path)
    retry.click()
    held(page, expected, reason, download)
    outcomes.append("HTTP 503 keeps missing values and retries the original source")
    page.close()
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    pending = []
    page.route("**/" + geometry_path, lambda route: pending.append(route))
    page.goto(base + "/voter-participation/" + QUERY, wait_until="domcontentloaded", timeout=120000)
    ready(page)
    page.wait_for_function("() => document.querySelector('#state-select').value === 'Maine'")
    for _ in range(100):
        if pending:
            break
        page.wait_for_timeout(100)
    assert pending, "The delayed reference must actually be requested"
    page.locator("#state-select").select_option("Florida")
    expect(page.locator("#title")).to_have_text("County election results in Florida", timeout=90000)
    for route in pending:
        route.continue_()
    page.wait_for_timeout(500)
    expect(page.locator('.substate-feature[data-color-level="county"]')).to_have_count(67)
    expect(page.locator(HELD)).to_have_count(0)
    expect(page.locator("#table-head")).not_to_contain_text("Hold reason")
    outcomes.append("Late Maine reference cannot replace selected Florida")
    page.close()
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4321")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--faults", action="store_true", help="Also inject explicit source outages/delays")
    args = parser.parse_args()
    assert not args.output.exists(), "Keep prior acceptance receipts"
    base = args.base_url.rstrip("/")
    pointer = json.loads((ROOT / "public/participation-context/latest.json").read_bytes())
    context_root = ROOT / "public/participation-context" / pointer["snapshot_id"]
    context = json.loads((context_root / "index.json").read_bytes())
    reference = context["geometry"]["county"]["ME"]
    geometry = json.loads((context_root / reference).read_bytes())
    expected = {f["properties"]["key"]: f["properties"]["name"] for f in geometry["features"]}
    assert len(expected) == 16
    county_pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    county_index = json.loads((ROOT / county_pointer["data_directory"] / "index.json").read_bytes())
    reason = county_index["withheld_states"]["ME"]["error"]
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            cases = normal(browser, base, expected, reason, county_pointer["complete_download_url"], args.output)
            injected = faults(browser, base, reference, expected, reason, county_pointer["complete_download_url"]) if args.faults else []
        finally:
            browser.close()
    receipt = {"passed": True, "base_url": base, "production": urlparse(base).hostname == "www.themarginoferror.com",
               "normal_valid_data_script_style_overrides": False, "cases": cases,
               "explicit_availability_injection_cases": injected}
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()

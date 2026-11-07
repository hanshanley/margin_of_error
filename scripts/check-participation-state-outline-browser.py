"""Verify shape-following state selection above detail layers and without focus boxes."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--proof", type=Path)
parser.add_argument("--screenshots", type=Path)
parser.add_argument("--source-overrides", action="store_true")
args = parser.parse_args()
if args.proof and args.proof.exists():
    raise ValueError("Refuse to replace an existing outline proof")
if args.screenshots:
    args.screenshots.mkdir(parents=True, exist_ok=True)


def check_outline(page, name):
    svg = page.locator("svg.turnout-map")
    outline = svg.locator(".state-selection-outline")
    selected = svg.locator(".map-feature.selected[data-state]")
    expect(outline).to_have_count(1)
    expect(selected).to_have_count(1)
    expect(selected).to_have_attribute("data-state", name)
    expect(outline).to_have_attribute("data-selected-state", name)
    assert outline.get_attribute("d") == selected.get_attribute("d")
    result = outline.evaluate("""outline => {
      const svg = outline.ownerSVGElement;
      const selected = svg.querySelector('.map-feature.selected[data-state]');
      const style = getComputedStyle(outline), selectedStyle = getComputedStyle(selected);
      return {
        state: outline.dataset.selectedState, length: outline.getTotalLength(),
        lastPainted: svg.lastElementChild === outline,
        aboveDetail: [...svg.querySelectorAll('.geographic-detail')].every(detail =>
          !!(detail.compareDocumentPosition(outline) & Node.DOCUMENT_POSITION_FOLLOWING)),
        vectorEffect: style.vectorEffect, strokeWidth: style.strokeWidth,
        pointerEvents: style.pointerEvents, fill: style.fill,
        ariaHidden: outline.getAttribute('aria-hidden'), tabbable: outline.hasAttribute('tabindex'),
        selectedOutlineStyle: selectedStyle.outlineStyle,
        stroke: style.stroke, focusedStroke: selectedStyle.stroke,
        keyboardFocus: selected.matches(':focus-visible'),
        detailFeatures: svg.querySelectorAll('.geographic-detail .map-feature').length,
        zoom: Number(svg.dataset.zoom)
      };
    }""")
    assert result["length"] > 0
    assert result["lastPainted"] and result["aboveDetail"]
    assert result["vectorEffect"] == "non-scaling-stroke"
    assert result["strokeWidth"] == "2px"
    assert result["pointerEvents"] == "none" and result["fill"] == "none"
    assert result["ariaHidden"] == "true" and not result["tabbable"]
    assert result["selectedOutlineStyle"] == "none", "Native SVG focus box still appears"
    return result


results = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    try:
        for mode, viewport in (("desktop", {"width": 1440, "height": 1100}),
                               ("mobile", {"width": 390, "height": 844})):
            context = browser.new_context(viewport=viewport)
            try:
                if args.source_overrides:
                    context.route("**/scripts/participation-explorer.js",
                                  lambda route: route.fulfill(path=ROOT / "public/scripts/participation-explorer.js"))
                    css = (ROOT / "src/styles/voter-participation.css").read_text()
                    context.add_init_script(
                        "document.addEventListener('DOMContentLoaded',()=>{"
                        "const style=document.createElement('style');style.textContent="
                        + json.dumps(css) + ";document.head.append(style);});")
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                response = page.goto(args.base_url.rstrip("/") + "/voter-participation/"
                                     "?view=states&year=2024&map-color=turnout&map-level=auto&state=North+Carolina",
                                     wait_until="domcontentloaded")
                assert response.ok
                expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
                page.locator('.map-feature[data-state="North Carolina"]').click()
                page.wait_for_function(
                    "document.querySelectorAll('.geographic-detail .map-feature').length > 0",
                    timeout=60000)
                checks = [check_outline(page, "North Carolina")]
                assert checks[0]["detailFeatures"] > 0
                page.mouse.move(5, 5)
                if args.screenshots:
                    page.locator("svg.turnout-map").screenshot(
                        path=str(args.screenshots / f"north-carolina-{mode}.png"))
                names = page.locator("#state-select option").evaluate_all(
                    "options=>options.map(option=>option.value)")
                assert len(names) == len(set(names)) == 51
                for name in names if mode == "desktop" else ["Alaska", "Hawaii", "Rhode Island"]:
                    page.select_option("#state-select", name)
                    checks.append(check_outline(page, name))
                for name in ("Texas", "Rhode Island"):
                    page.select_option("#state-select", name)
                    selected = page.locator(".map-feature.selected[data-state]")
                    selected.focus()
                    selected.press("Enter")
                    keyboard_check = check_outline(page, name)
                    assert keyboard_check["keyboardFocus"]
                    assert keyboard_check["stroke"] == keyboard_check["focusedStroke"]
                    checks.append(keyboard_check)
                page.select_option("#year", "2022")
                checks.append(check_outline(page, "Rhode Island"))
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                results.append({"mode": mode, "checks": checks, "page_errors": errors})
            finally:
                context.close()
    finally:
        browser.close()
proof = {
    "status": "PASS_shape_following_noninteractive_state_outline",
    "base_url": args.base_url, "source_overrides": args.source_overrides, "results": results,
    "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        "public/scripts/participation-explorer.js", "src/styles/voter-participation.css",
        "scripts/check-participation-state-outline-browser.py")},
}
if args.proof:
    args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({"status": proof["status"],
                  "checks": sum(len(result["checks"]) for result in results),
                  "desktop_states": 51, "mobile": True, "keyboard": True, "year_change": True}))

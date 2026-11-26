"""Verify the turnout and swing layouts in desktop and touch Chromium."""

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def swipe(session, x, y, distance):
    session.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for step in range(1, 9):
        session.send("Input.dispatchTouchEvent", {
            "type": "touchMove", "touchPoints": [{"x": x, "y": y + distance * step / 8}],
        })
    session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def check(base, screenshots):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (320, 390, 768, 1280):
            mobile = width < 700
            page = browser.new_page(viewport={"width": width, "height": 900}, has_touch=mobile, is_mobile=mobile)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
            assert response.ok
            map_view = page.locator("svg.turnout-map")
            expect(map_view).to_be_visible(timeout=45000)
            page.evaluate("document.fonts.ready")
            assert page.evaluate("document.documentElement.scrollWidth") == width
            turnout_top = round(map_view.bounding_box()["y"])
            assert turnout_top < 630
            options, color, touch = (page.locator(selector) for selector in (
                "#atlas-options", "#map-color-label", "#map-touch",
            ))
            expect(color).to_be_hidden()
            expect(options).to_be_visible()
            options.locator("summary").click()
            expect(color).to_be_visible()
            options.locator("summary").click()
            expect(color).to_be_hidden()
            more = page.locator("#selection-panel > .selection-more")
            expect(more).not_to_have_attribute("open", "")
            expect(page.locator("#state-history")).to_be_hidden()
            expect(page.locator("#selection-panel > .selection-rate")).to_be_visible()
            assert len(page.locator("#selection-panel").inner_text()) < 220
            assert page.locator("#desktop-turnout-controls .explorer-toolbar").count() == 1
            assert page.locator("#state-select").bounding_box()["y"] < map_view.bounding_box()["y"]
            if width <= 880:
                assert map_view.bounding_box()["width"] > width * .85
                assert page.locator("#selection-panel").bounding_box()["y"] >= map_view.bounding_box()["y"] + map_view.bounding_box()["height"]
            if screenshots:
                page.screenshot(path=screenshots / f"after-states-{width}.png")
            if mobile:
                expect(touch).to_be_visible()
                assert map_view.evaluate("(e) => getComputedStyle(e).touchAction") == "pan-y pinch-zoom"
                if width == 390:
                    cdp = page.context.new_cdp_session(page)
                    map_view.evaluate("(e) => e.scrollIntoView({block: 'center'})")
                    start = page.evaluate("scrollY")
                    box = map_view.bounding_box()
                    swipe(cdp, box["x"] + box["width"] / 2, box["y"] + box["height"] * .7, -105)
                    page.wait_for_function("(top) => scrollY > top + 40", arg=start)
                    page.locator("#map-zoom-in").tap()
                    zoomed = map_view.get_attribute("viewBox")
                    touch.tap()
                    expect(touch).to_have_attribute("aria-pressed", "true")
                    assert map_view.evaluate("(e) => getComputedStyle(e).touchAction") == "none"
                    map_view.evaluate("(e) => e.scrollIntoView({block: 'center'})")
                    box = map_view.bounding_box()
                    swipe(cdp, box["x"] + box["width"] / 2, box["y"] + box["height"] * .55, -65)
                    expect(map_view).not_to_have_attribute("viewBox", zoomed)
                    touch.tap()
                    expect(touch).to_have_attribute("aria-pressed", "false")
                    page.locator("#map-reset").tap()
            else:
                expect(touch).to_be_hidden()
                if width == 1280:
                    assert abs(map_view.bounding_box()["y"] - page.locator("#selection-panel").bounding_box()["y"]) < 2
            more.locator(":scope > summary").click()
            expect(page.locator("#state-history")).to_be_visible()
            more.locator(":scope > summary").click()
            page.locator("#state-select").select_option(label="Pennsylvania")
            expect(page.locator("#selection-panel > h3")).to_have_text("Pennsylvania")
            expect(page.locator("#selection-panel > .selection-more")).not_to_have_attribute("open", "")
            page.locator("#tab-effects").click()
            swing = page.locator("[data-driver-map] svg")
            expect(swing).to_be_visible(timeout=45000)
            page.locator("#tab-effects").focus()
            page.evaluate("scrollTo(0,0)")
            swing_top = round(swing.bounding_box()["y"])
            assert swing_top < 700
            geography = page.locator("[data-driver-geography]")
            expect(geography).to_be_hidden()
            expect(page.locator("[data-driver-view]")).to_be_visible()
            expect(page.locator("[data-driver-map] path[data-state-code]")).to_have_count(51)
            expect(page.locator("[data-driver-summary] .driver-value")).to_be_visible(timeout=45000)
            expect(page.locator(".driver-overview-result > details")).not_to_have_attribute("open", "")
            assert len(page.locator("[data-driver-summary]").inner_text()) < 450
            assert page.evaluate("document.documentElement.scrollWidth") == width
            if screenshots:
                page.screenshot(path=screenshots / f"after-swings-{width}.png")
            if width <= 880:
                assert swing.bounding_box()["width"] > width * .85
                assert page.locator(".driver-overview-result").bounding_box()["y"] > swing.bounding_box()["y"] + swing.bounding_box()["height"]
            page.locator("[data-driver-view]").select_option("reported_counts")
            expect(geography).to_be_visible()
            geography.select_option("district")
            expect(swing.locator("path[data-district]")).to_have_count(435, timeout=45000)
            expect(page.locator("[data-driver-summary] .comparison-more")).not_to_have_attribute("open", "")
            page.locator(".driver-overview-result > details > summary").click()
            expect(page.locator("[data-driver-detail] table").first).to_be_visible()
            page.locator(".driver-options > summary").click()
            expect(page.locator("[data-driver-view]")).to_be_visible()
            geography.select_option("state")
            page.locator("[data-driver-state]").select_option("PA")
            page.locator("[data-driver-view]").select_option("switching")
            expect(page.locator("[data-driver-summary] .comparison-more")).not_to_have_attribute("open", "")
            expect(page.locator("[data-driver-summary] table").first).to_be_visible(timeout=45000)
            page.locator("[data-driver-view]").select_option("reported_counts")
            page.locator(".driver-options > summary").click()
            page.locator(".driver-research > summary").click()
            notes = page.locator(".driver-sources")
            notes.locator("summary").click()
            expect(notes.locator(".download-links a")).to_have_count(0)
            expect(page.locator("#downloads, [data-participation-archive], .participation-page a[download]")).to_have_count(0)
            congress = page.locator("[data-congressional-results]")
            congress.locator("summary").click()
            expect(congress.locator("[data-congress-race]").first).to_be_visible(timeout=45000)
            expect(congress.locator("[data-congress-downloads] a")).to_have_count(0)
            page.locator("#tab-national").click()
            page.locator("#year").select_option("2024")
            expect(page.locator(".demographic-card").first).to_be_visible(timeout=45000)
            assert page.evaluate("document.documentElement.scrollWidth") == width
            page.locator("#tab-methods").click()
            expect(page.locator(".methods-overview")).to_be_visible()
            if screenshots:
                page.locator("#tab-national").click()
                page.evaluate("scrollTo(0,0)")
                page.screenshot(path=screenshots / f"after-demographics-{width}.png")
            assert page.evaluate("document.documentElement.scrollWidth") == width
            assert not errors, (width, errors)
            print(f"{width}px: turnout map at {turnout_top}px, swing map at {swing_top}px; controls and archive removal passed",
                  flush=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:4321")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    check(args.base, args.screenshots)

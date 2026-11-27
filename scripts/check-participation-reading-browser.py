"""Check understandable group denominators and Results units on real data."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def fits(page, width):
    assert page.evaluate("document.documentElement.scrollWidth") <= width + 1
    for node in page.locator(".participation-page select:visible").all():
        box = node.bounding_box()
        assert box["height"] >= 44
        assert box["x"] >= 0 and box["x"] + box["width"] <= width + 1, box


def snapshot(page, args, name, width):
    if args.images:
        page.screenshot(path=args.images / f"{name}-{width}.png")


def check(args):
    results = []
    base = args.base.rstrip("/") + "/voter-participation/"
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        for width in [320, 390, 768, 1280]:
            context = browser.new_context(viewport={"width": width, "height": 1000},
                                          is_mobile=width < 700, has_touch=width < 700)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            assert page.goto(base + "?view=national&year=2026&mode=civic_model&countState=MO&dimension=sex").ok
            expect(page.locator(".civic-group-row")).to_have_count(2, timeout=60000)
            expect(page.locator(".group-reading")).to_contain_text("within each group")
            expect(page.locator(".group-reading")).to_contain_text("not that group's share of all voters")
            expect(page.locator('[data-civic-state="MO"][data-group="male"] .civic-group-value')).to_have_text("53.3%")
            expect(page.locator('[data-civic-state="MO"][data-group="female"] .civic-group-value')).to_have_text("49.1%")
            expect(page.locator(".civic-group-withheld summary")).to_have_text("Unavailable groups (1)")
            expect(page.locator(".civic-group-held")).to_have_attribute("data-group", "unknown")
            expect(page.locator(".civic-group-held .count-track")).to_have_count(0)
            expect(page.locator(".civic-group-table thead th")).to_have_count(2)
            page.evaluate("document.fonts.ready")
            page.locator(".participation-heading").scroll_into_view_if_needed()
            snapshot(page, args, "groups-missouri", width)
            page.locator(".civic-group-withheld summary").click()
            expect(page.locator(".civic-group-held")).to_be_visible()
            assert page.locator(".civic-group-held").get_attribute("data-rate") == ""
            page.locator("#dimension").select_option("age")
            expect(page.locator(".civic-group-table")).to_be_visible()
            for row in page.locator(".civic-group-row").all():
                percent = float(row.get_attribute("data-rate"))
                assert row.locator(".count-track i").get_attribute("style") == f"width: {percent:g}%;"
                assert row.get_attribute("data-sample-n") == ""
            tracks = page.locator(".civic-group-row .count-track").evaluate_all("es=>es.map(e=>e.getBoundingClientRect().width)")
            assert max(tracks) - min(tracks) < 1
            page.locator(".participation-heading").scroll_into_view_if_needed()
            snapshot(page, args, "groups-age", width)
            page.locator("#dimension").select_option("gender")
            expect(page.locator(".civic-group-row")).to_have_count(0)
            expect(page.locator(".group-empty")).to_be_visible()
            page.locator("#current-state-select").select_option("DC")
            expect(page.locator(".group-empty")).to_contain_text("no survey sample")
            page.locator("#current-state-select").select_option("MO")
            page.locator("#dimension").select_option("sex")
            fits(page, width)
            page.locator("#tab-effects").click()
            root = page.locator("#participation-return-drivers")
            expect(root.locator("[data-driver-view]")).to_have_value("reported_counts", timeout=60000)
            expect(root.locator("[data-driver-summary]")).to_have_attribute("data-recorded-source", "current-congressional-counts", timeout=60000)
            root.locator(".driver-options > summary").click()
            root.locator("[data-driver-view]").select_option("source_total")
            expect(root.locator("[data-driver-summary]")).to_have_attribute("data-source-model-state", "TX", timeout=60000)
            expect(root.locator("[data-driver-model-warning]")).to_be_visible()
            reading = root.locator("[data-driver-reading]")
            expect(reading).to_be_visible()
            expect(reading).to_contain_text("not the percentage who switched parties or stayed home")
            expect(reading).to_contain_text("D ÷ (D + R)")
            expect(root.locator(".driver-value-label")).to_contain_text("modeled change in Democratic share of D+R choices")
            expect(root.locator("[data-driver-summary]")).to_contain_text("46.21%")
            expect(root.locator("[data-driver-summary]")).to_contain_text("53.10%")
            original = float(root.locator(".driver-value").inner_text().split()[0])
            root.scroll_into_view_if_needed()
            snapshot(page, args, "results", width)
            root.locator("[data-driver-summary]").scroll_into_view_if_needed()
            snapshot(page, args, "results-definition", width)
            if root.locator(".driver-options").get_attribute("open") is None:
                root.locator(".driver-options > summary").click()
            selector = root.locator("[data-driver-view]")
            for view, meaning in [("source_switching", "not the percentage of people who switched"),
                                  ("source_participation", "entry into and exit"),
                                  ("source_entry", "does not identify first-ever"),
                                  ("source_exit", "does not prove someone stayed home"),
                                  ("source_other", "not nonvoting"),
                                  ("source_unresolved", "Unknown responses are not counted as staying home")]:
                selector.select_option(view)
                expect(root.locator("[data-driver-map]")).to_have_attribute("data-driver-map", view)
                expect(reading).to_contain_text(meaning)
                expect(root.locator(".driver-value")).to_contain_text("pp")
                expect(root.locator("[data-driver-map] path.driver-state")).to_have_count(51)
            selector.select_option("source_total")
            root.locator("[data-driver-units]").select_option("margin")
            expect(root.locator("[data-driver-map]")).to_have_attribute("data-source-model-units", "margin")
            expect(reading).to_contain_text("(D − R) ÷ (D + R)")
            margin = float(root.locator(".driver-value").inner_text().split()[0])
            assert abs(margin - 2 * original) < .02
            root.locator("[data-driver-group]").select_option(index=1)
            expect(reading).to_contain_text("statewide denominator, not a within-group turnout rate")
            root.locator("[data-driver-group]").select_option("")
            selector.select_option("source_retaining")
            expect(reading).to_contain_text("denominator is previous Democratic or Republican House source choices")
            expect(root.locator(".driver-value")).to_contain_text("%")
            selector.select_option("scenario_switching")
            expect(root.locator("[data-driver-map]")).to_have_attribute("data-driver-map", "scenario_switching", timeout=60000)
            expect(reading).to_contain_text("recalling a 2024 Democratic or Republican presidential choice")
            expect(reading).not_to_contain_text("Percentage-point contribution")
            fits(page, width)
            if width == 320:
                page.locator("#tab-national").click()
                page.add_style_tag(content="html{font-size:200% !important}")
                expect(page.locator(".civic-group-table")).to_be_visible()
                fits(page, width)
            assert not errors, errors
            results.append(dict(width=width, recovered_missouri_comparison=True, held_cells_not_zero=True,
                                aligned_common_scale=True, all_eight_source_views=True,
                                units_and_denominators_match=True, physical_layout_fits=True))
            context.close()
        browser.close()
    proof = dict(status="passed", base=args.base, results=results)
    args.output.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--images", type=Path)
    args = parser.parse_args()
    if args.images:
        args.images.mkdir(parents=True, exist_ok=True)
    check(args)

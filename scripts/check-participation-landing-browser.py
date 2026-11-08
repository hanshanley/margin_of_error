"""Verify the primary atlas, opt-in research, native deep links and complete downloads."""

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


class Inventory(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids = Counter()
        self.downloads = []
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if attributes.get("id"):
            self.ids[attributes["id"]] += 1
        if tag == "a" and "download" in attributes:
            self.downloads.append(attributes["href"])


def check(base, proof=None, baseline_html=None):
    if proof and proof.exists():
        raise ValueError("Refuse to replace an existing landing-page proof")
    baseline = Inventory(baseline_html.read_text()) if baseline_html else None
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for mode, options in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("mobile", {"viewport": {"width": 390, "height": 844},
                            "is_mobile": True, "has_touch": True}),
                ("no_javascript", {"java_script_enabled": False}),
                ("mobile_no_javascript", {"java_script_enabled": False,
                                          "viewport": {"width": 390, "height": 844}}),
                ("failed_atlas_json", {}),
            ]:
                print("Checking landing mode:", mode, flush=True)
                context = browser.new_context(**options)
                try:
                    if mode == "failed_atlas_json":
                        context.route("**/national.json", lambda route: route.abort())
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    response = page.goto(base.rstrip("/") + "/voter-participation/",
                                         wait_until="domcontentloaded")
                    assert response.ok
                    research = page.locator("#participation-research")
                    summary = research.locator(":scope > summary")
                    expect(summary).to_be_visible()
                    expect(research).not_to_have_attribute("open", "")
                    panels = research.locator(":scope > section[id]")
                    panel_ids = panels.evaluate_all("panels => panels.map(panel => panel.id)")
                    assert len(panel_ids) >= 21, panel_ids
                    for panel in panels.all():
                        expect(panel).not_to_be_visible()
                    assert page.locator(".participation-heading a").count() == 0
                    javascript = options.get("java_script_enabled", True)
                    if javascript:
                        expect(page.locator("#historical-explorer")).to_be_visible()
                        if mode == "failed_atlas_json":
                            expect(page.locator("#visualization")).to_contain_text(
                                "Historical inputs could not be loaded.", timeout=90000)
                        else:
                            expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
                            expect(page.locator("#year")).to_have_value("2026")
                            expect(page.locator("#mode")).to_have_value("available")
                    if baseline:
                        actual = Inventory(response.text())
                        additions = Counter({
                            key: 1 for key in (
                                "precinct-state-select", "precinct-layer-label", "precinct-layer",
                                "participation-research", "methods-archive", "methods-github-link",
                            ) if not baseline.ids[key]
                        })
                        assert actual.ids == baseline.ids + additions
                        assert actual.downloads == baseline.downloads, "A complete download changed"
                    downloads = page.locator("#downloads a[download]").evaluate_all(
                        "links => links.map(link => link.getAttribute('href'))")
                    assert len(downloads) >= 948, len(downloads)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    if proof and mode in ("desktop", "mobile"):
                        page.screenshot(path=str(proof.with_suffix(f".{mode}.png")))

                    summary.focus()
                    page.keyboard.press("Enter")
                    expect(research).to_have_attribute("open", "")
                    for panel in panels.all():
                        expect(panel).to_be_visible()
                    expect(research).to_contain_text("Local findings do not establish nationwide coverage")
                    expect(research).to_contain_text("modeled switching is not observed individual persuasion")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    summary.focus()
                    page.keyboard.press("Space")
                    expect(research).not_to_have_attribute("open", "")
                    expect(page.locator("#participation-mecklenburg-scenarios")).not_to_be_visible()

                    deep_links = [
                        "participation-columbia-wisconsin-history",
                        "participation-mecklenburg-scenarios",
                        "participation-survey",
                    ]
                    for target in deep_links:
                        page.goto(base.rstrip("/") + "/voter-participation/#" + target,
                                  wait_until="domcontentloaded")
                        expect(research).to_have_attribute("open", "")
                        expect(page.locator("#" + target)).to_be_visible()
                        assert page.evaluate("location.hash") == "#" + target
                        summary.focus()
                        page.keyboard.press("Space")
                        expect(research).not_to_have_attribute("open", "")
                    page.reload(wait_until="domcontentloaded")
                    assert page.evaluate("location.hash") == "#participation-survey"
                    # Reload may restore scrolling instead of repeating fragment navigation.
                    if research.get_attribute("open") is None:
                        summary.focus()
                        page.keyboard.press("Space")
                    expect(research).to_have_attribute("open", "")
                    expect(page.locator("#participation-survey")).to_be_visible()
                    assert page.locator("#downloads a[download]").evaluate_all(
                        "links => links.map(link => link.getAttribute('href'))") == downloads
                    assert not errors, (mode, errors)
                    results.append({"mode": mode, "passed": True, "research_panels": len(panel_ids),
                                    "default_research_closed": True, "keyboard_open_close": True,
                                    "native_deep_links": deep_links, "reload_target_preserved": True,
                                    "reload_target_accessible": True,
                                    "complete_downloads": len(downloads),
                                    "baseline_ids_and_downloads_preserved": bool(baseline)})
                finally:
                    context.close()
        finally:
            browser.close()
    result = {"base_url": base, "checks": results}
    if proof:
        with proof.open("x") as handle:
            json.dump(result, handle, indent=2)
            handle.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:4321")
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--baseline-html", type=Path)
    arguments = parser.parse_args()
    check(arguments.base, arguments.proof, arguments.baseline_html)

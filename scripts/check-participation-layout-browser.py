"""Verify that the atlas and masthead share the same margins at every breakpoint."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4392")
parser.add_argument("--proof", type=Path, required=True)
parser.add_argument("--stylesheet", type=Path)
args = parser.parse_args()
assert not args.proof.exists()
cases = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        page = browser.new_page()
        if args.stylesheet:
            page.add_init_script("document.addEventListener('DOMContentLoaded',()=>{"
                "const style=document.createElement('style');style.textContent="
                + json.dumps(args.stylesheet.read_text()) + ";document.head.append(style);});")
        for width in [320, 390, 700, 760, 761, 1024, 1440, 2000]:
            page.set_viewport_size(dict(width=width, height=1000))
            response = page.goto(args.base_url.rstrip("/") + "/voter-participation/",
                                 wait_until="domcontentloaded", timeout=90000)
            assert response.ok
            for view in ["states", "national", "effects", "methods"]:
                button = page.locator("#tab-" + view)
                button.click()
                expect(button).to_have_attribute("aria-selected", "true", timeout=90000)
                dimensions = page.evaluate("""() => {
                    const h=document.querySelector('.site-header').getBoundingClientRect();
                    const p=document.querySelector('.participation-page').getBoundingClientRect();
                    return {headerLeft:h.left,headerRight:h.right,pageLeft:p.left,pageRight:p.right,
                      viewport:innerWidth,documentWidth:document.documentElement.scrollWidth};
                }""")
                assert abs(dimensions["headerLeft"] - dimensions["pageLeft"]) < 1, dimensions
                assert abs(dimensions["headerRight"] - dimensions["pageRight"]) < 1, dimensions
                assert dimensions["documentWidth"] <= dimensions["viewport"], dimensions
                cases.append(dict(width=width, view=view, **dimensions))
                if view in ("states", "national"):
                    page.locator("#year").select_option("2024")
                    options = page.locator(".explorer-options")
                    if not options.get_attribute("open") == "":
                        options.locator("summary").click()
                    expect(page.locator("#basis")).to_be_visible()
                    dimensions = options.locator(".controls").evaluate("""node => {
                        const r=node.getBoundingClientRect();
                        return {left:r.left,right:r.right,viewport:innerWidth,
                            documentWidth:document.documentElement.scrollWidth};
                    }""")
                    assert dimensions["left"] >= 0 and dimensions["right"] <= dimensions["viewport"], dimensions
                    assert dimensions["documentWidth"] <= dimensions["viewport"], dimensions
                    cases.append(dict(width=width, view=view, historical_options_open=True, **dimensions))
    finally:
        browser.close()
proof = dict(status="PASS_shared_masthead_atlas_margins_all_breakpoints_and_tabs",
    base_url=args.base_url, stylesheet_override=bool(args.stylesheet), cases=cases,
    horizontal_document_overflow=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

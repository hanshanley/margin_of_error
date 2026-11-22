"""Render the two checked SVG editions without network access (Playwright 1.60)."""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("figures", type=Path)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for name in ("house-district-map", "house-district-map-substack"):
                page = browser.new_page(viewport={"width": 1200, "height": 960}, java_script_enabled=False)
                page.route("http**://**/*", lambda route: route.abort())
                page.goto((args.figures / (name + ".svg")).resolve().as_uri())
                page.locator("svg").screenshot(path=args.figures / (name + ".png"))
                page.close()
        finally:
            browser.close()


if __name__ == "__main__":
    main()

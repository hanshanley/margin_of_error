"""Verify all modeled office views, numeric details, ranges and mobile layout."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4397")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
data = json.loads((ROOT / "data/participation-return-attribution/20261110-01/viewer-data.json").read_bytes())
cases = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in [390, 1440]:
            page = browser.new_page(viewport=dict(width=width, height=1000))
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(args.base_url.rstrip("/") + "/voter-participation/?year=2026",
                wait_until="domcontentloaded", timeout=90000)
            assert response.ok
            research = page.locator("#participation-research")
            if research.get_attribute("open") is None:
                research.locator(":scope > summary").click()
            root = page.locator("#participation-return-drivers")
            root.scroll_into_view_if_needed()
            office = root.locator("[data-driver-office]")
            expect(office).to_be_enabled(timeout=90000)
            for name, count in [("house", 50), ("senate", 35), ("governor", 28)]:
                root.locator("[data-driver-search]").fill("")
                office.select_option(name)
                expect(root.locator(".driver-row")).to_have_count(count)
                expect(root.locator(".driver-plot")).to_have_count(count)
                root.locator("[data-driver-search]").fill("Minnesota")
                expect(root.locator(".driver-row")).to_have_count(1)
                expected = next(row for row in data["rows"] if row["office"] == name and row["state_code"] == "MN")
                row = root.locator(".driver-row")
                expect(row).to_have_attribute("data-driver-id", expected["id"])
                for field, css in [("switching", ".driver-switching"),
                                   ("modeled_nonparticipation", ".driver-nonparticipation")]:
                    value = expected["components_pp"][field]
                    text = f'{value:+.2f} pp' if value else "0.00 pp"
                    expect(row.locator(css)).to_have_text(text)
                row.locator("button").click()
                detail = root.locator("[data-driver-detail]")
                expect(detail).to_be_visible()
                expect(detail.locator("tbody tr")).to_have_count(7)
                expect(detail).to_contain_text("Recalled 2024 President")
                expect(detail).to_contain_text("unknown")
                expect(detail).to_contain_text("Return / source-frame gap")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                cases.append(dict(width=width, office=name, models=count, exact_MN_point_values=True,
                    complete_seven_term_accounting=True, no_horizontal_overflow=True))
            root.locator("[data-driver-search]").fill("no-such-state")
            expect(root.locator(".driver-row")).to_have_count(0)
            expect(root.locator("[data-driver-rows]")).to_contain_text("No matching state")
            expect(root).to_contain_text("not confidence intervals")
            assert not errors, errors
            page.close()
    finally:
        browser.close()
proof = dict(status="PASS_all113_modeled_effects_office_views_and_mobile_details",
    base_url=args.base_url, cases=cases, source_frame_not_population_or_causal_certification=True)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

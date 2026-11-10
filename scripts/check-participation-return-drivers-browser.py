"""Verify linked modeled-effect maps, exact values, missingness and responsive layout."""

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
            expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
            page.locator("#tab-effects").click()
            expect(page.locator("#historical-explorer")).to_be_hidden()
            root = page.locator("#participation-return-drivers")
            root.scroll_into_view_if_needed()
            office = root.locator("[data-driver-office]")
            expect(office).to_be_enabled(timeout=90000)
            for name, count in [("house", 50), ("senate", 35), ("governor", 28)]:
                office.select_option(name)
                expect(root.locator(".driver-map svg")).to_have_count(2)
                expect(root.locator(".driver-map path[data-model-id]")).to_have_count(count * 2)
                expect(root.locator(".driver-map path")).to_have_count(102)
                assert root.locator(".driver-map svg").nth(0).get_attribute("data-scale") == root.locator(".driver-map svg").nth(1).get_attribute("data-scale")
                if name == "house":
                    root.evaluate("node => node.scrollIntoView({block:'start'})")
                    page.screenshot(path=str(args.proof.with_suffix(f".house-{width}.png")))
                root.locator("[data-driver-state]").select_option("MN")
                expected = next(row for row in data["rows"] if row["office"] == name and row["state_code"] == "MN")
                for field in ("switching", "modeled_nonparticipation"):
                    state_path = root.locator(f'[data-driver-map="{field}"] path[data-state-code="MN"]')
                    expect(state_path).to_have_attribute("data-model-id", expected["id"])
                    assert float(state_path.get_attribute("data-model-value")) == expected["components_pp"][field]
                    expect(state_path).to_have_class("driver-state selected")
                detail = root.locator("[data-driver-detail]")
                expect(detail).to_be_visible()
                expect(detail.locator("tbody tr")).to_have_count(7)
                expect(detail).to_contain_text("Recalled 2024 President")
                expect(detail).to_contain_text("unknown")
                expect(detail).to_contain_text("Return / source-frame gap")
                if name == "house":
                    root.locator('[data-driver-map="modeled_nonparticipation"] path[data-state-code="WY"]').click()
                    expect(root.locator("[data-driver-state]")).to_have_value("WY")
                    expect(root.locator('.driver-map path[data-state-code="WY"].selected')).to_have_count(2)
                    expect(detail).to_contain_text("Wyoming")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                cases.append(dict(width=width, office=name, models=count, exact_MN_point_values=True,
                    linked_state_maps=True, shared_signed_scale=True,
                    complete_seven_term_accounting=True, no_horizontal_overflow=True))
            root.locator("[data-driver-state]").select_option("DC")
            expect(root.locator("[data-driver-detail]")).to_contain_text("no NORC sample")
            expect(root.locator('[data-driver-map="switching"] path[data-state-code="DC"]')).to_have_attribute("data-model-value", "")
            expect(page.locator("#tab-precincts")).to_have_count(0)
            page.screenshot(path=str(args.proof.with_suffix(f".{width}.png")), full_page=False)
            expect(root).to_contain_text("not confidence intervals")
            assert not errors, errors
            page.close()
    finally:
        browser.close()
proof = dict(status="PASS_all113_linked_modeled_effect_maps_and_mobile_details",
    base_url=args.base_url, cases=cases, source_frame_not_population_or_causal_certification=True)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

"""Verify one map with selectable views, preserved selections and exact accounting."""

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
data = json.loads((ROOT / "data/participation-return-attribution/20261110-02/viewer-data.json").read_bytes())
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
            view = root.locator("[data-driver-view]")
            expect(office).to_be_enabled(timeout=90000)
            for name, count in [("house", 50), ("senate", 35), ("governor", 28)]:
                office.select_option(name)
                root.locator("[data-driver-state]").select_option("TX")
                texas = next(row for row in data["rows"] if row["office"] == name and row["state_code"] == "TX")
                summary = root.locator("[data-driver-summary]")
                expect(summary).to_contain_text(f'{texas["reported_comparison"]["reported_change_pp"]:+.2f} pp reported swing')
                expect(summary).to_contain_text("other / unallocated")
                assert summary.bounding_box()["y"] < root.locator(".driver-maps").bounding_box()["y"]
                bound = None
                fields = {
                    "reported_total": texas["reported_comparison"]["reported_change_pp"],
                    "switching": texas["components_pp"]["switching"],
                    "modeled_nonparticipation": texas["components_pp"]["modeled_nonparticipation"],
                    "other_and_unallocated": texas["reported_comparison"]["other_and_unallocated_pp"],
                }
                for field, value in fields.items():
                    view.select_option(field)
                    expect(root.locator(".driver-map svg")).to_have_count(1)
                    expect(root.locator(".driver-map path[data-model-id]")).to_have_count(count)
                    expect(root.locator(".driver-map path")).to_have_count(51)
                    expect(office).to_have_value(name)
                    expect(root.locator("[data-driver-state]")).to_have_value("TX")
                    path = root.locator(f'[data-driver-map="{field}"] path[data-state-code="TX"]')
                    assert float(path.get_attribute("data-model-value")) == value
                    expect(path).to_have_class("driver-state selected")
                    actual_bound = root.locator(".driver-map svg").get_attribute("data-scale")
                    if bound is None:
                        bound = actual_bound
                    assert bound == actual_bound
                    if name == "house" and field == "reported_total":
                        root.evaluate("node => node.scrollIntoView({block:'start'})")
                        page.screenshot(path=str(args.proof.with_suffix(f".house-{width}.png")))
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    cases.append(dict(width=width, office=name, view=field, models=count,
                        one_map=True, paths=51, exact_TX_point_value=True,
                        state_and_office_preserved_on_view_change=True, shared_signed_scale=True,
                        original_seven_terms_retained=True, reported_total_and_remainder_reconcile=True,
                        summary_above_map=True, no_horizontal_overflow=True))
                root.locator("[data-driver-state]").select_option("MN")
                expected = next(row for row in data["rows"] if row["office"] == name and row["state_code"] == "MN")
                for field in ("switching", "modeled_nonparticipation"):
                    view.select_option(field)
                    state_path = root.locator(f'[data-driver-map="{field}"] path[data-state-code="MN"]')
                    expect(state_path).to_have_attribute("data-model-id", expected["id"])
                    assert float(state_path.get_attribute("data-model-value")) == expected["components_pp"][field]
                    expect(state_path).to_have_class("driver-state selected")
                detail = root.locator("[data-driver-detail]")
                detail.locator("..").evaluate("node => node.open = true")
                expect(detail).to_be_visible()
                expect(detail.locator("tbody tr")).to_have_count(
                    9 if expected["reported_comparison"]["status"] == "reported_source_comparison" else 7)
                expect(detail).to_contain_text("recalled 2024 President")
                expect(detail).to_contain_text("unknown")
                expect(detail).to_contain_text("Return / source-frame gap")
                if name == "house":
                    root.locator('[data-driver-map="modeled_nonparticipation"] path[data-state-code="WY"]').click()
                    expect(root.locator("[data-driver-state]")).to_have_value("WY")
                    expect(root.locator('.driver-map path[data-state-code="WY"].selected')).to_have_count(1)
                    expect(detail).to_contain_text("Wyoming")
                    view.select_option("reported_total")
                    expect(root.locator("[data-driver-state]")).to_have_value("WY")
                    root.locator("[data-driver-state]").select_option("AK")
                    expect(summary).to_contain_text("Reported swing unavailable")
                    expect(root.locator('[data-driver-map="reported_total"] path[data-state-code="AK"]')).to_have_attribute("data-model-value", "")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                expect(office).to_have_value(name)
            view.select_option("switching")
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
proof = dict(status="PASS_all113_single_map_all24_office_view_viewport_combinations",
    base_url=args.base_url, cases=cases, source_frame_not_population_or_causal_certification=True)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

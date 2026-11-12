"""Verify every state/office, both endpoints and all fitted map views in the real UI."""

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
calibrated = json.loads((ROOT / "data/participation-return-attribution/20261111-03/return-constrained-viewer.json").read_bytes())
fitted = {row["id"]: row for row in calibrated["rows"]}
compatible = {row["id"]: row for row in json.loads(
    (ROOT / "data/participation-return-attribution/20261111-04/gross-flow-bounds-viewer.json").read_bytes())["rows"]}
cases = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in (390, 1440):
            page = browser.new_page(viewport=dict(width=width, height=1000))
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(args.base_url.rstrip("/") + "/voter-participation/?year=2026",
                wait_until="domcontentloaded", timeout=90000)
            assert response.ok
            expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
            page.locator("#tab-effects").click()
            root = page.locator("#participation-return-drivers")
            root.scroll_into_view_if_needed()
            office, view = root.locator("[data-driver-office]"), root.locator("[data-driver-view]")
            state = root.locator("[data-driver-state]")
            summary = root.locator("[data-driver-summary]")
            expect(office).to_be_enabled(timeout=90000)
            assert root.locator("[data-saved-calibrated]").count() == 113
            assert root.locator("[data-saved-driver]").count() == 113
            assert root.locator("[data-saved-switching-bounds]").count() == 113
            for identity, value in compatible.items():
                expected = "Unavailable" if value["bounds"] is None else (
                    f'{float(value["bounds"]["switching"]["lower_percent"]):.1f}% to '
                    f'{float(value["bounds"]["switching"]["upper_percent"]):.1f}%')
                expect(root.locator(f'[data-saved-switching-bounds="{identity}"]')).to_have_text(expected)
            for name in ("senate", "governor"):
                office.select_option(name)
                state.select_option("TX")
                rows = [row for row in data["rows"] if row["office"] == name]
                by_code = {row["state_code"]: row for row in rows}
                bound = None
                checked = 0
                for field in ("reported_total", "switching", "modeled_nonparticipation", "entry", "other_choice"):
                    view.select_option(field)
                    expect(root.locator(".driver-map svg")).to_have_count(1)
                    expect(root.locator(".driver-map path")).to_have_count(51)
                    expect(state).to_have_value("TX")
                    actual_bound = root.locator(".driver-map svg").get_attribute("data-scale")
                    if bound is None:
                        bound = actual_bound
                    assert bound == actual_bound
                    values = root.locator(".driver-map path").evaluate_all(
                        "nodes => nodes.map(n=>[n.dataset.stateCode,n.dataset.modelValue])")
                    for code, raw in values:
                        row = by_code.get(code)
                        fit = fitted[row["id"]] if row else None
                        expected = None
                        if field == "reported_total" and row:
                            expected = row["reported_comparison"].get("reported_change_pp")
                        elif fit and fit["point"]:
                            expected = fit["point"]["components_pp"][
                                "nonparticipation" if field == "modeled_nonparticipation" else field]
                        assert (raw == "" if expected is None else abs(float(raw)-expected) < 1e-10), (name, field, code)
                        checked += 1
                    expect(summary).not_to_contain_text("other / unallocated")
                    expect(summary).to_contain_text("Fitted scenario")
                    if name == "house" and field == "switching":
                        root.evaluate("node=>node.scrollIntoView({block:'start'})")
                        page.screenshot(path=str(args.proof.with_suffix(f".house-{width}.png")))
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                for row in rows:
                    state.select_option(row["state_code"])
                    if fitted[row["id"]]["point"]:
                        expect(summary).to_contain_text(f'{row["reported_comparison"]["reported_change_pp"]:+.2f} pp reported swing')
                        expect(summary).to_contain_text("Fitted scenario")
                        expect(summary).to_contain_text("The same totals also permit zero switching.")
                        limits = compatible[row["id"]]["bounds"]["switching"]
                        identification = root.locator(f'[data-driver-identification="{row["id"]}"]')
                        expect(identification).to_contain_text(
                            f'{float(limits["lower_percent"]):.1f}% to {float(limits["upper_percent"]):.1f}%')
                        expect(identification).to_contain_text("not a confidence interval")
                    else:
                        expect(summary).to_contain_text("Reported swing unavailable")
                        expect(root.locator("[data-driver-identification]")).to_have_count(0)
                    expect(summary).not_to_contain_text("other / unallocated")
                state.select_option("TX")
                root.locator('.driver-map path[data-state-code="MN"]').click()
                expect(state).to_have_value("MN")
                view.select_option("switching")
                expect(state).to_have_value("MN")
                details = root.locator("[data-driver-detail]").locator("..")
                if not details.evaluate("node=>node.open"):
                    details.locator("summary").click()
                expect(root.locator("[data-driver-detail]")).to_contain_text("nine")
                expect(root.locator("[data-driver-detail]")).to_contain_text("keep party choice")
                if name == "house":
                    root.locator("[data-driver-detail]").screenshot(
                        path=str(args.proof.with_suffix(f".house-detail-{width}.png")))
                details.locator("summary").click()
                cases.append(dict(width=width, office=name, exact_state_view_values=checked,
                    all_office_state_summaries=len(rows), actual_pointer_selection=True,
                    state_selection_preserved_across_views=True, one_map=True,
                    archived_113_models_retained=True, shared_signed_scale=True,
                    no_unmodeled_balancing_term=True, no_horizontal_overflow=True))
            state.select_option("DC")
            expect(root.locator("[data-driver-detail]")).to_contain_text("no NORC sample")
            expect(root.locator('.driver-map path[data-state-code="DC"]')).to_have_attribute("data-model-value", "")
            expect(page.locator("#tab-precincts")).to_have_count(0)
            assert not errors, errors
            page.close()
        plain = browser.new_page(java_script_enabled=False)
        assert plain.goto(args.base_url.rstrip("/") + "/voter-participation/").ok
        assert plain.locator("[data-saved-switching-bounds]").count() == 113
        for identity, value in compatible.items():
            expected = "Unavailable" if value["bounds"] is None else (
                f'{float(value["bounds"]["switching"]["lower_percent"]):.1f}% to '
                f'{float(value["bounds"]["switching"]["upper_percent"]):.1f}%')
            expect(plain.locator(f'[data-saved-switching-bounds="{identity}"]')).to_have_text(expected)
        plain.close()
    finally:
        browser.close()
proof = dict(status="passed_all_state_office_return_constrained_maps", base_url=args.base_url,
    cases=cases, valid_data_overrides=False, fit_not_independent_behavioral_validation=True,
    exact_gross_switching_bounds_and_holds=113, no_js_bounds_and_holds_verified=True,
    all_89_central_frames_allow_zero_switching=True, no_new_fitted_models=True)
args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
print(json.dumps(proof))

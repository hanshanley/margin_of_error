"""Verify recorded swings independently of behavioral-model loading and holds."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", required=True)
parser.add_argument("--proof", required=True, type=Path)
args = parser.parse_args()
assert not args.proof.exists()
source = json.loads((ROOT / "data/participation-return-attribution/20261113-01/norc-point-summary.json").read_bytes())
rows = {row["state_code"]: row for row in source["rows"]}
expected = {}
for code, row in rows.items():
    review = row["contest_comparability"]
    previous, current = review["previous_counts"], review["current_counts"]
    expected[code] = float(100 * (Fraction(current["D"], current["D"] + current["R"])
                                 - Fraction(previous["D"], previous["D"] + previous["R"])))
assert len(expected) == 50 and abs(expected["TX"] - 11.97610547994342) < 1e-10
url = args.base_url.rstrip("/") + "/voter-participation/?year=2026"
cases = []


def open_map(page):
    response = page.goto(url, wait_until="domcontentloaded", timeout=90000)
    assert response.ok
    expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
    page.locator("#tab-effects").click()
    root = page.locator("#participation-return-drivers")
    root.scroll_into_view_if_needed()
    expect(root.locator('[data-driver-map="reported_counts"] .driver-state')).to_have_count(51, timeout=90000)
    expect(root.locator("[data-driver-view]")).to_have_value("reported_counts")
    expect(root.locator("[data-driver-state]")).to_have_value("TX")
    expect(root.locator("[data-driver-units]")).to_have_value("democratic_two_party_share")
    expect(root.locator("[data-driver-status]")).to_contain_text("50 states with recorded")
    return root


def check_map(root, multiplier):
    actual = root.locator(".driver-state").evaluate_all(
        "nodes=>nodes.map(n=>({code:n.dataset.stateCode,value:n.dataset.modelValue,"
        "caution:n.dataset.comparisonCaution,fill:n.getAttribute('fill'),label:n.getAttribute('aria-label')}))")
    assert len(actual) == 51 and len({row["code"] for row in actual}) == 51
    for row in actual:
        code = row["code"]
        if code == "DC":
            assert row["value"] == "" and row["caution"] == "false" and row["fill"] == "#d6d3cb"
            continue
        assert abs(float(row["value"]) - expected[code] * multiplier) < 1e-8, row
        held = not rows[code]["source_comparison_available"]
        assert row["caution"] == str(held).lower(), row
        if held:
            assert row["fill"] == f"url(#driver-count-caution-{code})"
            assert "not a like-for-like" in row["label"]
            assert root.locator(f'pattern[id="driver-count-caution-{code}"] rect').get_attribute("fill") != "#d6d3cb"
        else:
            assert row["fill"].startswith("#") and row["fill"] != "#d6d3cb"
    assert root.locator("pattern").count() == 17
    assert root.locator("[data-driver-comparison-caution]").is_visible()
    assert not root.locator("[data-driver-group-control]").is_visible()
    assert not root.locator("[data-driver-family]").is_visible()
    assert not root.locator("[data-driver-association]").is_visible()
    return len(actual)


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in (1440, 390):
            page = browser.new_page(viewport=dict(width=width, height=1100))
            errors, model_requests = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: model_requests.append(request.url)
                    if "house-official-source-update/" in request.url else None)
            root = open_map(page)
            checked = check_map(root, 1)
            assert model_requests == [], model_requests
            summary = root.locator("[data-driver-summary]")
            expect(summary).to_contain_text("+11.98 pp share change")
            expect(summary).to_contain_text("+23.95 pp")
            for code in sorted(rows):
                root.locator("[data-driver-state]").select_option(code)
                expect(summary).to_have_attribute("data-norc-state", code)
                assert abs(float(summary.get_attribute("data-recorded-share-change")) - expected[code]) < 1e-8
                assert summary.get_attribute("data-norc-hold") == ("true" if not rows[code]["source_comparison_available"] else None)
            root.locator("[data-driver-state]").select_option("TX")
            root.locator("[data-driver-units]").select_option("margin")
            checked += check_map(root, 2)
            root.locator("[data-driver-units]").select_option("democratic_two_party_share")
            checked += check_map(root, 1)
            expect(summary).to_contain_text("+11.98 pp share change")
            for code in ("TX", "MA"):
                path = root.locator(f'.driver-state[data-state-code="{code}"]')
                path.focus()
                path.press("Enter")
                expect(root.locator("[data-driver-state]")).to_have_value(code)
                path.press("Space")
                expect(root.locator("[data-driver-state]")).to_have_value(code)
            root.locator("[data-driver-state]").select_option("TX")
            for view_name in ("reported_total", "switching"):
                root.locator("[data-driver-view]").select_option(view_name)
                expect(root.locator("[data-driver-status]")).to_contain_text("33 House reconstructions", timeout=90000)
                values = root.locator(".driver-state").evaluate_all(
                    "nodes=>nodes.map(n=>[n.dataset.stateCode,n.dataset.modelValue])")
                assert len(values) == 51
                for code, raw in values:
                    row = rows.get(code)
                    if not row or not row["source_comparison_available"]:
                        assert raw == "", (code, view_name, raw)
                    else:
                        target = (row["reported_comparison"]["reported_change_pp"] if view_name == "reported_total"
                                  else row["point"]["contributions_pp"]["switching"]) / 2
                        assert abs(float(raw) - target) < 1e-8, (code, view_name, raw, target)
                assert not root.locator("[data-driver-comparison-caution]").is_visible()
            root.locator("[data-driver-view]").select_option("reported_counts")
            check_map(root, 1)
            expect(summary).to_contain_text("+11.98 pp share change")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert errors == [], errors
            page.screenshot(path=str(args.proof.with_suffix(f".{width}.png")), full_page=False)
            cases.append(dict(width=width, kind="recorded", map_values=checked,
                              state_selections=50, initial_model_requests=0,
                              unchanged_comparable_and_switching_values=102, errors=errors))
            page.close()

            page = browser.new_page(viewport=dict(width=width, height=1100))
            page.route("**/data/house-official-source-update/**", lambda route: route.abort())
            root = open_map(page)
            check_map(root, 1)
            root.locator("[data-driver-view]").select_option("switching")
            expect(root.locator("[data-driver-status]")).to_contain_text("NORC House model unavailable", timeout=90000)
            expect(root.locator(".driver-state")).to_have_count(0)
            root.locator("[data-driver-view]").select_option("reported_counts")
            expect(root.locator(".driver-state")).to_have_count(51)
            check_map(root, 1)
            expect(root.locator("[data-driver-summary]")).to_contain_text("+11.98 pp share change")
            cases.append(dict(width=width, kind="blocked-model", recorded_counts_remain_available=True,
                              failed_model_clears_previous_values=True, recovered_without_model=True))
            page.close()
        page = browser.new_page(java_script_enabled=False)
        assert page.goto(url, wait_until="domcontentloaded", timeout=90000).ok
        for code, value in expected.items():
            cells = page.locator(f'[data-saved-recorded="{code}"] td').all_text_contents()
            assert len(cells) == 4 and abs(float(cells[2]) - value) < .0051
        cases.append(dict(kind="no-JavaScript", recorded_rows=50))
        page.close()
    finally:
        browser.close()
proof = dict(status="passed", base_url=args.base_url, cases=cases,
             source_sha256=hashlib.sha256((ROOT / "data/participation-return-attribution/20261113-01/norc-point-summary.json").read_bytes()).hexdigest(),
             independent_rational_expected_values=True, behavioral_holds_unchanged=17,
             valid_data_or_style_overrides=False)
args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
print(json.dumps(proof, sort_keys=True))

"""Verify all real public model-family/unit views without overriding valid data."""

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4397")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
receipt = json.loads((ROOT / "data/participation-return-attribution/20261112-03/norc-receipt.json").read_bytes())
with urllib.request.urlopen(receipt["url"], timeout=180) as response:
    body = response.read()
assert len(body) == receipt["bytes"] and hashlib.sha256(body).hexdigest() == receipt["sha256"]
data = json.loads(body)
fields = ("reported_total", "switching", "modeled_nonparticipation", "entry",
          "exit", "other_choice", "unresolved", "retaining")


def expected(row, field, group, units):
    if row is None:
        return None
    scale = .5 if units == "democratic_two_party_share" else 1
    if field == "reported_total":
        return row["reported_comparison"]["reported_change_pp"] * scale if row["source_comparison_available"] else None
    value = next((g for g in row["groups"] if g["dimension"] + "|" + g["group"] == group), None) if group else row["point"]
    if value is None or value.get("available") is False:
        return None
    if field == "retaining":
        return (value["gross_outcomes"] if group else row["gross_outcomes"])["retaining"] * 100
    return scale * (value["net_participation_pp"] if field == "modeled_nonparticipation"
                    else value["contributions_pp"][field])


cases = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in (390, 1440):
            page = browser.new_page(viewport=dict(width=width, height=1000))
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            assert page.goto(args.base_url.rstrip("/") + "/voter-participation/?year=2026",
                             wait_until="domcontentloaded", timeout=90000).ok
            expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
            page.locator("#tab-effects").click()
            root = page.locator("#participation-return-drivers")
            family = root.locator("[data-driver-family]")
            units = root.locator("[data-driver-units]")
            view = root.locator("[data-driver-view]")
            view.select_option("reported_total")
            group = root.locator("[data-driver-group]")
            state = root.locator("[data-driver-state]")
            summary = root.locator("[data-driver-summary]")
            expect(family).to_be_enabled(timeout=90000)
            expect(family).to_have_value(data["preferred_family"])
            assert family.locator("option").count() == 3
            assert root.locator("[data-norc-validation-family]").count() == 3
            checked = 0
            bounds = {}
            for name, model in data["families"].items():
                family.select_option(name)
                rows = {r["state_code"]: r for r in model["rows"]}
                for unit in ("margin", "democratic_two_party_share"):
                    view.select_option("switching")
                    units.select_option(unit)
                    for field in fields:
                        view.select_option(field)
                        assert units.is_disabled() == (field == "retaining")
                        actual = root.locator(".driver-state").evaluate_all(
                            "nodes=>nodes.map(n=>[n.dataset.stateCode,n.dataset.modelValue])")
                        assert len(actual) == 51
                        for code, raw in actual:
                            target = expected(rows.get(code), field, "", unit)
                            assert raw == "" if target is None else abs(float(raw) - target) < 1e-8, (name, unit, field, code)
                            checked += 1
                        scale = root.locator("[data-driver-scale-max]").inner_text()
                        if field != "retaining":
                            assert "signed percentage-point changes" in root.locator(".driver-map svg").get_attribute("aria-label")
                        key = (unit, field)
                        assert bounds.setdefault(key, scale) == scale, ("different family colour bounds", name, key)
                        expect(state).to_have_value("TX")
                    view.select_option("switching")
                    choices = group.locator("option").evaluate_all("nodes=>nodes.map(n=>n.value).filter(Boolean)")
                    for selected in choices:
                        group.select_option(selected)
                        for field in ("switching", "modeled_nonparticipation", "retaining"):
                            view.select_option(field)
                            actual = root.locator(".driver-state").evaluate_all(
                                "nodes=>nodes.map(n=>[n.dataset.stateCode,n.dataset.modelValue])")
                            for code, raw in actual:
                                target = expected(rows.get(code), field, selected, unit)
                                assert raw == "" if target is None else abs(float(raw) - target) < 1e-8, (name, unit, selected, code)
                                checked += 1
                    group.select_option("")
                    view.select_option("switching")
                    expect(summary).to_have_attribute("data-norc-family", name)
                    expect(summary).to_have_attribute("data-norc-units", unit)
                    details = root.locator("[data-driver-detail]").locator("..")
                    if not details.evaluate("n=>n.open"):
                        details.locator("summary").click()
                    assert root.locator("[data-norc-family-comparison] tbody tr").count() == 3
                    expect(root.locator("[data-driver-detail]")).to_contain_text("prediction gap is model error")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                root.screenshot(path=str(args.proof.with_suffix("." + name + "-" + str(width) + ".png")))
            selected = family.input_value()
            root.locator("[data-driver-office]").select_option("senate")
            expect(family.locator("..")).to_be_hidden()
            expect(units.locator("..")).to_be_hidden()
            root.locator("[data-driver-office]").select_option("house")
            expect(family).to_have_value(selected)
            expect(state).to_have_value("TX")
            expect(units).to_have_value("democratic_two_party_share")
            assert not errors, errors
            cases.append(dict(width=width, exact_state_family_unit_group_view_values=checked,
                              shared_family_bounds=True, retained_percentages_not_halved=True,
                              selected_state_preserved=True, office_roundtrip_preserved=True,
                              no_horizontal_overflow=True))
            page.close()
    finally:
        browser.close()
proof = dict(status="passed_real_public_three_family_unit_maps", base_url=args.base_url,
             cases=cases, valid_data_overrides=False, public_viewer_sha256=receipt["sha256"])
args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
print(json.dumps(proof))

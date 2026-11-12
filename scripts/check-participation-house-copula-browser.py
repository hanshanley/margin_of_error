"""Verify real immutable association profiles, selections, scaling, cache and faults."""

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
receipt = json.loads((ROOT/"data/participation-return-attribution/20261112-04/copula-receipt.json").read_bytes())
original = json.loads((ROOT/"data/participation-return-attribution/20261112-03/norc-receipt.json").read_bytes())
datasets = {}
for profile, pin in receipt["profiles"].items():
    with urllib.request.urlopen(pin["url"], timeout=180) as response:
        body = response.read()
    assert len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"]
    datasets[profile] = json.loads(body)
url = args.base_url.rstrip("/")+"/voter-participation/?year=2026"
fields = ("reported_total", "switching", "modeled_nonparticipation", "entry", "exit", "other_choice", "unresolved", "retaining")


def expected(row, field, group, units):
    if row is None:
        return None
    scale = .5 if units == "democratic_two_party_share" else 1
    if field == "reported_total":
        return row["reported_comparison"]["reported_change_pp"]*scale if row["source_comparison_available"] else None
    value = next((g for g in row["groups"] if g["dimension"]+"|"+g["group"] == group), None) if group else row["point"]
    if value is None or value.get("available") is False:
        return None
    if field == "retaining":
        return (value["gross_outcomes"] if group else row["gross_outcomes"])["retaining"]*100
    return scale*(value["net_participation_pp"] if field == "modeled_nonparticipation" else value["contributions_pp"][field])


def open_map(page):
    assert page.goto(url, wait_until="domcontentloaded", timeout=90000).ok
    expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
    page.locator("#tab-effects").click()
    root = page.locator("#participation-return-drivers")
    expect(root.locator("[data-driver-family]")).to_be_enabled(timeout=90000)
    return root


cases = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in (390, 1440):
            page = browser.new_page(viewport=dict(width=width, height=1000))
            errors, requests = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append(request.url))
            root = open_map(page)
            association = root.locator("[data-driver-association]")
            family = root.locator("[data-driver-family]")
            units = root.locator("[data-driver-units]")
            view = root.locator("[data-driver-view]")
            group = root.locator("[data-driver-group]")
            state = root.locator("[data-driver-state]")
            summary = root.locator("[data-driver-summary]")
            expect(association).to_have_value("original")
            bounds, checked, backed_off = {}, 0, 0
            for profile, data in datasets.items():
                association.select_option(profile)
                expect(summary).to_have_attribute("data-norc-association", profile, timeout=90000)
                for name, model in data["families"].items():
                    family.select_option(name)
                    rows = {row["state_code"]: row for row in model["rows"]}
                    for unit in ("margin", "democratic_two_party_share"):
                        view.select_option("switching")
                        units.select_option(unit)
                        for selected in ["", *group.locator("option").evaluate_all("nodes=>nodes.map(n=>n.value).filter(Boolean)")]:
                            group.select_option(selected)
                            for field in fields if not selected else ("switching", "modeled_nonparticipation", "retaining"):
                                view.select_option(field)
                                assert units.is_disabled() == (field == "retaining")
                                actual = root.locator(".driver-state").evaluate_all("nodes=>nodes.map(n=>[n.dataset.stateCode,n.dataset.modelValue])")
                                assert len(actual) == 51
                                for code, raw in actual:
                                    target = expected(rows.get(code), field, selected, unit)
                                    assert raw == "" if target is None else abs(float(raw)-target) < 1e-8, (profile, name, unit, field, selected, code)
                                    checked += 1
                                scale = root.locator("[data-driver-scale-max]").inner_text()
                                key = (unit, selected, field == "retaining")
                                assert bounds.setdefault(key, scale) == scale, ("different profile/family bounds", key)
                                expect(state).to_have_value("TX")
                        group.select_option("")
                        view.select_option("switching")
                        expect(summary).to_have_attribute("data-norc-family", name)
                        expect(summary).to_have_attribute("data-norc-units", unit)
                        mae = model["preconditioning_margin_MAE_pp"]*(.5 if unit == "democratic_two_party_share" else 1)
                        expect(root.locator("[data-driver-association-note]")).to_contain_text(f"{mae:.2f} pp")
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    details = root.locator("[data-driver-detail]").locator("..")
                    if not details.evaluate("n=>n.open"):
                        details.locator("summary").click()
                    expect(root.locator("[data-driver-detail]")).to_contain_text("applied")
                    assert root.locator("[data-norc-association-comparison] tbody tr").count() == 2
                    for code, parameter in model["historical_association_stress"]["state_parameters"].items():
                        if parameter["feasibility_exponent"] < 1:
                            state.select_option(code)
                            expect(root.locator("[data-driver-detail]")).to_contain_text(f"applied {parameter['effective_theta']:.3f}")
                            backed_off += 1
                    state.select_option("TX")
                    root.screenshot(path=str(args.proof.with_suffix(f".{profile}-{name}-{width}.png")))
            group.select_option("AGE6|65_plus")
            selected = family.input_value()
            for profile in ("original", "attenuated", "full"):
                association.select_option(profile)
                expect(summary).to_have_attribute("data-norc-association", profile, timeout=90000)
                expect(family).to_have_value(selected)
                expect(group).to_have_value("AGE6|65_plus")
                expect(state).to_have_value("TX")
                expect(units).to_have_value("democratic_two_party_share")
            root.locator("[data-driver-office]").select_option("senate")
            expect(association.locator("..")).to_be_hidden()
            root.locator("[data-driver-office]").select_option("house")
            expect(summary).to_have_attribute("data-norc-association", "full")
            for pin in [original, *receipt["profiles"].values()]:
                assert requests.count(pin["url"]) == 1, ("profile redownloaded", pin["url"], requests.count(pin["url"]))
            assert backed_off == 2 and not errors, (backed_off, errors)
            cases.append(dict(width=width, exact_state_profile_family_unit_group_values=checked,
                profile_and_family_bounds_shared=True, selection_and_units_preserved=True,
                actual_backoff_strengths_displayed=backed_off, per_pin_single_download=True,
                active_prediction_errors_displayed=True, no_horizontal_overflow=True))
            page.close()
        for fault in ("failure", "checksum", "late-profile", "late-office"):
            page = browser.new_page(viewport=dict(width=390, height=1000))
            root = open_map(page)
            pending = []
            def intercept(route):
                if fault == "failure":
                    route.abort()
                elif fault == "checksum":
                    response = route.fetch()
                    route.fulfill(response=response, body=response.body()+b" ")
                else:
                    pending.append(route)
            pin = receipt["profiles"]["full"]
            page.route(pin["url"], intercept)
            root.locator("[data-driver-association]").select_option("full")
            status = root.locator("[data-driver-status]")
            if fault.startswith("late"):
                expect(status).to_contain_text("Loading the checksum-verified")
                if fault == "late-profile":
                    root.locator("[data-driver-association]").select_option("original")
                    expect(root.locator("[data-driver-summary]")).to_have_attribute("data-norc-association", "original")
                else:
                    root.locator("[data-driver-office]").select_option("senate")
                assert pending
                for route in pending:
                    response = route.fetch()
                    route.fulfill(response=response)
                if fault == "late-profile":
                    expect(root.locator("[data-driver-summary]")).to_have_attribute("data-norc-association", "original")
                else:
                    expect(root.locator("[data-driver-summary]")).to_contain_text("Fitted scenario")
                    expect(root.locator("[data-driver-association]").locator("..")).to_be_hidden()
            else:
                expect(status).to_contain_text("NORC House model unavailable", timeout=90000)
                expect(root.locator(".driver-map svg")).to_have_count(0)
                expect(root.locator("[data-driver-association-note]")).to_be_hidden()
                page.unroute(pin["url"], intercept)
                root.get_by_role("button", name="Retry NORC model").click()
                expect(root.locator("[data-driver-summary]")).to_have_attribute("data-norc-association", "full", timeout=90000)
            page.close()
    finally:
        browser.close()
proof = dict(status="passed_real_public_association_stress_maps", base_url=args.base_url, cases=cases,
    valid_data_overrides=False, checksum_failure_retry_and_late_profile_office_isolation=True,
    public_profile_pins={key: value["sha256"] for key, value in receipt["profiles"].items()})
args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True)+"\n")
print(json.dumps(proof))

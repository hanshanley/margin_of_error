"""Verify every selected county count, prior-choice destination and range in four browser modes."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {
    "20261107-01": ("participation-county-scenarios", 216),
    "20261107-02": ("participation-mecklenburg-scenarios", 195),
}


def count(value):
    return f"{math.floor(value / 100 + .5) * 100:,}"


def interval(value):
    return f'{count(value["minimum"])}–{count(value["maximum"])}'


def text(locator):
    return " ".join(locator.inner_text().split())


def check(base, proof, version="20261107-01"):
    if proof and proof.exists():
        raise ValueError("Refuse to replace an existing county browser receipt")
    path = f"/participation-county-scenarios/{version}/"
    panel_id, units = VERSIONS[version]
    expected = json.loads((ROOT / f"public{path}summary.json").read_text())
    audit = json.loads((ROOT / f"data/participation-county-scenarios/{version}/linkage-audit.json").read_text())
    reference = expected["default_conditional_scenario"]
    diagnostics = expected["turnout_temporal_diagnostics"]
    ballots = sum(reference["after"][key] for key in ("D", "R", "O", "B"))
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for mode, options in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("mobile", {"viewport": {"width": 390, "height": 844}}),
                ("no_javascript", {"java_script_enabled": False}),
                ("failed_json", {}),
            ]:
                context = browser.new_context(**options)
                try:
                    if mode == "failed_json":
                        context.route("**/participation-county-scenarios/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#" + panel_id)
                    expect(panel).to_be_visible()
                    expect(panel.locator("[data-county-dimension]")).to_have_count(5)
                    for details in panel.locator("details").all():
                        details.locator("summary").click()
                    for phrase in (
                        f'{reference["swing_margin_pp"]:+.2f} points toward Democrats',
                        "conditional scenarios, not observed individual persuasion",
                        "sensitivity ranges are not confidence intervals",
                        f'{diagnostics["validation_calibration_error_pp"]:+.2f} percentage points',
                        f'subgroup errors reached {diagnostics["known_total_conditioned_max_group_error_pp_n_at_least_100"]:.2f}',
                        f'{round(ballots):,} ballots and {units} of {units}',
                        "not final 2026 totals", "Measured staying home",
                        "Selected rows are not exhaustive partitions",
                        f'{audit["baseline_without_registration"]:,} prior participants',
                        "exit fractions are assumed", "not silently deleted", "several race categories",
                        "A fresh latent fit needs excluded private records and fine joint cells",
                        "not completed nationwide or precinct coverage"):
                        assert phrase.casefold() in text(panel).casefold(), (mode, phrase)
                    if version == "20261107-02":
                        for phrase in ("all modeled age predictors unknown", "birthdays are not imputed",
                                       "No calibrated subgroup error interval"):
                            assert phrase.casefold() in text(panel).casefold(), (mode, phrase)
                    numeric_cells = 0
                    for group in reference["demographics"]:
                        dimension, label = group["dimension"], group["group"]
                        scope = panel.locator(f'[data-county-dimension="{dimension}"]')
                        activity = scope.locator(f'[data-county-group="{label}"][data-county-kind="activity"]')
                        values = dict(group["modeled_cohort_counts"],
                                      modeled_2024_county_participants=group["modeled_2024_county_participants"],
                                      modeled_2026_participants=group["modeled_2026_participants"])
                        ranges = next(row for row in expected["demographic_sensitivity_range_margin_pp"]
                                      if (row["dimension"], row["group"]) == (dimension, label))
                        endpoints = dict(ranges["modeled_cohort_counts"],
                                         modeled_2024_county_participants=ranges["modeled_2024_county_participants"],
                                         modeled_2026_participants=ranges["modeled_2026_participants"])
                        for cell in activity.locator("[data-county-count]").all():
                            key = cell.get_attribute("data-county-count")
                            assert abs(float(cell.get_attribute("data-value")) - values[key]) < .000001
                            assert text(cell) == count(values[key]) + " " + interval(endpoints[key])
                            numeric_cells += 1
                        for prior in ("D", "R"):
                            row = scope.locator(f'[data-county-group="{label}"][data-county-prior="{prior}"]')
                            expect(row).to_have_count(1)
                            for cell in row.locator("[data-county-flow]").all():
                                key = cell.get_attribute("data-county-flow")
                                value = group["modeled_prior_choice_transitions"][prior][key]
                                assert abs(float(cell.get_attribute("data-value")) - value) < .000001
                                assert text(cell) == count(value) + " " + interval(
                                    ranges["modeled_prior_choice_transitions"][prior][key])
                                numeric_cells += 1
                        row = scope.locator(f'[data-county-group="{label}"][data-county-kind="contribution"]')
                        for cell in row.locator("[data-county-contribution]").all():
                            key = cell.get_attribute("data-county-contribution")
                            value = group["margin_pp_contributions"][key]
                            endpoint = ranges["margin_pp_contributions"][key]
                            assert text(cell) == f'{value:+.2f} {endpoint["minimum"]:+.2f} to {endpoint["maximum"]:+.2f}'
                            numeric_cells += 1
                    assert numeric_cells == 324, (mode, numeric_cells)
                    expect(panel.locator('[data-county-group="NATIVE HAWAIIAN or PACIFIC ISLANDER"]')).to_have_count(0)
                    for key, value in reference["margin_pp_contributions"].items():
                        row = panel.locator(f'[data-county-component="{key}"]')
                        endpoint = expected["sensitivity_range_margin_pp"][key]
                        assert text(row.locator("td").nth(0)) == f"{value:+.2f}"
                        assert text(row.locator("td").nth(1)) == f'{endpoint["minimum"]:+.2f} to {endpoint["maximum"]:+.2f}'
                    if mode == "failed_json":
                        assert page.evaluate("""async path => {
                            try { await fetch(path); return false; } catch { return true; }
                        }""", path + "summary.json")
                        expect(panel.locator('[data-county-kind="activity"]')).to_have_count(12)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    expect(page.locator("#participation-panel-intentions")).to_be_attached()
                    expect(page.locator("#participation-survey")).to_be_attached()
                    if mode == "desktop":
                        for name in ("summary.json", "download.json", "complete-analysis.zip"):
                            response = context.request.get(base.rstrip("/") + path + name)
                            assert response.ok
                            raw = response.body()
                            assert raw == (ROOT / f"public{path}{name}").read_bytes()
                        info = json.loads((ROOT / f"public{path}download.json").read_text())
                        assert len(raw) == info["bytes"] and hashlib.sha256(raw).hexdigest() == info["sha256"]
                    results.append({"mode": mode, "passed": True, "numeric_cells_checked": numeric_cells})
                finally:
                    context.close()
        finally:
            browser.close()
    if proof:
        proof.write_text(json.dumps({"base_url": base, "version": version, "checks": results}, indent=2) + "\n")
    print(json.dumps(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4331")
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--version", choices=VERSIONS, default="20261107-01")
    args = parser.parse_args()
    check(args.base_url, args.proof, args.version)

"""Verify real published scenario maps, demographic holds and isolated data failures."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4397")
parser.add_argument("--proof", type=Path, required=True)
parser.add_argument("--width", type=int, action="append")
parser.add_argument("--faults-only", action="store_true")
parser.add_argument("--skip-faults", action="store_true")
args = parser.parse_args()
assert not args.proof.exists()
data = json.loads((ROOT / "data/participation-transition-simulation/20261111-01/viewer-data.json").read_bytes())
old = json.loads((ROOT / "data/participation-return-attribution/20261110-02/viewer-data.json").read_bytes())
fields = dict(scenario_retaining="synthetic_retaining_share_of_recalled_major_party",
    scenario_switching="synthetic_switching_share_of_recalled_major_party",
    scenario_nonparticipation="synthetic_nonparticipation_share_of_recalled_major_party")
groups = {}
for row in data["complete_demographic_decisions"]:
    if row["point"] and row["dimension"] != "overall":
        groups.setdefault(row["dimension"], row["dimension"] + "|" + str(row["group"]))
decisions = {(r["state_code"], r["dimension"] + "|" + str(r["group"])): r
    for r in data["complete_demographic_decisions"]}
cases, errors = [], []


def open_page(browser, width):
    page = browser.new_page(viewport=dict(width=width, height=1000))
    page.on("pageerror", lambda error: errors.append(str(error)))
    response = page.goto(args.base_url.rstrip("/") + "/voter-participation/?year=2026",
        wait_until="domcontentloaded", timeout=90000)
    assert response.ok
    expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
    page.locator("#tab-effects").click()
    root = page.locator("#participation-return-drivers")
    root.scroll_into_view_if_needed()
    expect(root.locator("[data-driver-view]")).to_be_enabled(timeout=90000)
    return page, root


def scenario_ready(root, view):
    expect(root.locator(f'[data-driver-map="{view}"] path')).to_have_count(51, timeout=90000)
    expect(root.locator("[data-driver-status]")).to_contain_text("source scenarios")


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        if not args.faults_only:
            for width in args.width or [390, 1440]:
                page, root = open_page(browser, width)
                office, view = root.locator("[data-driver-office]"), root.locator("[data-driver-view]")
                group = root.locator("[data-driver-group]")
                view.select_option("scenario_retaining")
                scenario_ready(root, "scenario_retaining")
                expect(group).to_be_enabled()
                for name in ("house", "senate", "governor"):
                    office.select_option(name)
                    office_codes = {r["state_code"] for r in old["rows"] if r["office"] == name}
                    for category in ["", *groups.values()]:
                        group.select_option(category)
                        for metric, field in fields.items():
                            view.select_option(metric)
                            scenario_ready(root, metric)
                            actual = root.locator(".driver-map path").evaluate_all(
                                "nodes => nodes.map(n => ({code:n.dataset.stateCode,value:n.dataset.modelValue,fill:n.getAttribute('fill')}))")
                            assert len(actual) == 51
                            for item in actual:
                                source = decisions.get((item["code"], category)) if category else data["state_scenarios"].get(item["code"])
                                point = source and source["point"] if item["code"] in office_codes else None
                                if point is None:
                                    assert item["value"] == "" and item["fill"] == "#d6d3cb", item
                                else:
                                    assert abs(float(item["value"]) - point[field]) < 1e-12, item
                                    assert item["fill"] != "#d6d3cb", item
                            expect(root.locator("[data-driver-group-control]")).to_be_visible()
                            assert "%" in root.locator("[data-driver-scale-max]").inner_text()
                            assert "pp" not in root.locator("[data-driver-scale-max]").inner_text()
                            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                            cases.append(dict(width=width, office=name, view=metric, group=category,
                                all51_exact_points_or_qualified_missing=True, sequential_share_units=True,
                                one_map=True, no_horizontal_overflow=True))
                office.select_option("house")
                group.select_option("")
                view.select_option("scenario_nonparticipation")
                root.locator("[data-driver-state]").select_option("TX")
                expect(root.locator("[data-driver-summary]")).to_contain_text("Half/double-persistence")
                root.locator("[data-driver-detail]").locator("..").evaluate("node => node.open = true")
                expect(root.locator("[data-driver-detail] tbody tr")).to_have_count(5)
                expect(root.locator("[data-driver-detail]")).to_contain_text("Both residuals remain unallocated")
                root.evaluate("node => node.scrollIntoView({block:'start'})")
                page.screenshot(path=str(args.proof.with_suffix(f".scenario-{width}.png")))
                root.locator("[data-driver-state]").select_option("DC")
                expect(root.locator("[data-driver-summary]")).to_contain_text("no Civic sample")
                view.select_option("reported_total")
                expect(root.locator("[data-driver-group-control]")).to_be_hidden()
                root.locator("[data-driver-state]").select_option("TX")
                expect(root.locator("[data-driver-summary]")).to_contain_text("+25.16 pp reported swing")
                expect(root.locator(".driver-map-key")).to_have_attribute("aria-label", "Shared signed margin-point scale")
                expect(root.locator(".driver-map-directions")).to_contain_text("Republican direction")
                expect(root.locator(".driver-map-note strong")).to_contain_text("signed percentage-point")
                expect(page.locator("#tab-precincts")).to_have_count(0)
                page.close()
        if not args.skip_faults:
            page, root = open_page(browser, 1440)
            pattern = "**/datasets/transition-scenarios-2026/**/viewer-data.json.gz"

            def corrupt(route):
                response = route.fetch()
                body = bytearray(response.body())
                body[-1] ^= 1
                route.fulfill(response=response, body=bytes(body))

            page.route(pattern, corrupt)
            root.locator("[data-driver-view]").select_option("scenario_retaining")
            expect(root.locator("[data-driver-status]")).to_contain_text("Dataset checksum differs", timeout=90000)
            expect(root.locator(".driver-map path")).to_have_count(0)
            expect(root.locator("[data-driver-summary]")).to_be_hidden()
            page.unroute(pattern, corrupt)
            root.get_by_role("button", name="Retry scenario data").click()
            scenario_ready(root, "scenario_retaining")
            cases.append(dict(fault="corrupted_actual_public_bytes", rejected_without_stale_values=True,
                retry_loaded_actual_public_data=True))
            page.close()
            page, root = open_page(browser, 1440)
            pending = []
            page.route(pattern, lambda route: pending.append(route))
            with page.expect_request(pattern, timeout=90000):
                root.locator("[data-driver-view]").select_option("scenario_nonparticipation")
            root.locator("[data-driver-view]").select_option("reported_total")
            expect(root.locator('[data-driver-map="reported_total"] path')).to_have_count(51)
            assert pending
            with page.expect_response(pattern, timeout=90000):
                for route in pending:
                    route.continue_()
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            expect(root.locator("[data-driver-view]")).to_have_value("reported_total")
            expect(root.locator('[data-driver-map="reported_total"] path')).to_have_count(51)
            expect(root.locator("[data-driver-scale-max]")).to_contain_text("pp")
            expect(root.locator("[data-driver-group-control]")).to_be_hidden()
            cases.append(dict(fault="late_actual_public_response_after_legacy_view_change",
                old_signed_view_preserved=True))
            page.close()
        assert not errors, errors
    finally:
        browser.close()
proof = dict(status="PASS_actual_public_transition_scenarios", base_url=args.base_url,
    cases=cases, source_version="6d90035b93c21e859b8a5172b490628f460d9455b3a2db09f1cd7071fef2d24a",
    public_data_not_fixture=True, no_population_or_individual_history_certification=True)
args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
print(json.dumps(dict(status=proof["status"], cases=len(cases), base_url=args.base_url)))

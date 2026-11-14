"""Verify changed automatic House data reaches the existing map and controls."""

import argparse
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", required=True)
parser.add_argument("--fixture", type=Path, required=True)
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()

run = json.loads((args.fixture / "run.json").read_bytes())
version, commit = "f" * 64, "e" * 40
raw_base = (
    f"https://raw.githubusercontent.com/hanshanley/margin_of_error/"
    f"{commit}/automatic/versions/{version}/"
)
house = json.loads(json.dumps(run["house_sources"]))
house["base_url"] = raw_base
house["publication_bound"] = True
house["participation_state_projections"]["contract"] = \
    "participation.registered_control_display.v2"


def bind(value):
    if isinstance(value, dict):
        if value.get("path"):
            value["url"] = raw_base + value["path"]
        for child in value.values():
            bind(child)
    elif isinstance(value, list):
        for child in value:
            bind(child)


bind(house)
complete = {
    "required": True,
    "path": "complete-results.zip",
    "url": "https://github.com/hanshanley/margin_of_error/releases/download/"
           "automatic-runtime-browser-fixture/complete-results.zip",
    "bytes": 1,
    "sha256": "a" * 64,
    "media_type": "application/zip",
}
house["complete_download"] = complete
manifest = {
    "contract": "participation.automatic_runtime.v1",
    "version": version,
    "election_date": "2026-11-03",
    "processing_version": "browser-fixture-v1",
    "input_results_version": "b" * 64,
    "checked_at": "2026-11-14T15:00:00+00:00",
    "house_sources": house,
    "source_models_refitted": False,
    "geographic_joins_changed": False,
    "all_states_certified_or_precinct_complete": False,
    "complete_download": {
        **complete, "immutable": True, "verified_anonymously": True,
    },
}
profiles = {}
for profile in ("original", "attenuated", "full"):
    path = args.fixture / house["profile_viewers"][profile]["viewer_data"]["path"]
    profiles[profile] = json.loads(gzip.decompress(path.read_bytes()))


def expected(profile, family, field):
    rows = profiles[profile]["families"][family]["rows"]
    row = next(item for item in rows if item["state_code"] == "AR")
    return row["point"]["contributions_pp"][field]


def route_fixture(route, corrupt=False):
    url = route.request.url
    if url.endswith("/participation-data/automatic/latest.json"):
        route.fulfill(json=manifest)
    elif url.startswith(raw_base):
        path = args.fixture / url.removeprefix(raw_base)
        body = path.read_bytes()
        if corrupt and url.endswith("/house/viewer-original.json.gz"):
            body += b"x"
        route.fulfill(body=body, content_type="application/gzip")
    else:
        route.continue_()


results = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        page = browser.new_page(viewport={"width": 1360, "height": 1000})
        page.route("**/*", lambda route: route_fixture(route))
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        assert page.goto(args.base_url.rstrip("/") + "/voter-participation/?year=2026",
                         wait_until="domcontentloaded", timeout=90000).ok
        expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
        page.locator("#tab-effects").click()
        root = page.locator("#participation-return-drivers")
        status = root.locator("[data-driver-status]")
        state = root.locator("[data-driver-state]")
        view = root.locator("[data-driver-view]")
        family = root.locator("[data-driver-family]")
        association = root.locator("[data-driver-association]")
        units = root.locator("[data-driver-units]")
        summary = root.locator("[data-driver-summary]")
        expect(root).to_have_attribute("data-automatic-runtime", version)
        runtime_status = root.locator("[data-automatic-runtime-status]")
        expect(runtime_status).to_have_attribute("data-state", "active", timeout=90000)
        state.select_option("AR")
        expect(summary).to_contain_text("349,637")
        expect(summary).to_contain_text("+8.58 pp share change")
        assert abs(float(root.locator(
            '.driver-state[data-state-code="AR"]').get_attribute("data-model-value"))
            - 17.162564645808168 / 2) < 1e-8
        view.select_option("switching")
        expect(family).to_be_enabled(timeout=90000)
        units.select_option("margin")
        checked = 0
        for profile in ("original", "attenuated", "full"):
            association.select_option(profile)
            for model in ("accepted_ridge_multinomial",
                          "histogram_gradient_boosting", "extra_randomized_trees"):
                family.select_option(model)
                target = expected(profile, model, "switching")
                actual = float(root.locator(
                    '.driver-state[data-state-code="AR"]').get_attribute("data-model-value"))
                assert abs(actual - target) < 1e-8, (profile, model, actual, target)
                expect(summary).to_have_attribute("data-norc-state", "AR")
                checked += 1
        assert not errors, errors
        results.append({
            "case": "changed-runtime",
            "recorded_AR_margin_change_pp": 17.162564645808168,
            "profile_family_controls_checked": checked,
            "visible_dynamic_candidate_total": 349637,
            "sensitivity_source_browser_assertion": "covered by focused reader test, not this map proof",
            "errors": errors,
        })
        page.close()

        page = browser.new_page(viewport={"width": 390, "height": 900})
        page.route("**/*", lambda route: route_fixture(route, corrupt=True))
        assert page.goto(args.base_url.rstrip("/") + "/voter-participation/?year=2026",
                         wait_until="domcontentloaded", timeout=90000).ok
        expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
        page.locator("#tab-effects").click()
        root = page.locator("#participation-return-drivers")
        runtime_status = root.locator("[data-automatic-runtime-status]")
        expect(runtime_status).to_contain_text("accepted website sources retained", timeout=90000)
        root.locator("[data-driver-view]").select_option("switching")
        expect(root.locator("[data-driver-family]")).to_be_enabled(timeout=90000)
        root.locator("[data-driver-view]").select_option("reported_counts")
        root.locator("[data-driver-state]").select_option("AR")
        expect(root.locator("[data-driver-summary]")).to_contain_text("348,637")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        results.append({
            "case": "corrupt-runtime-fallback",
            "accepted_build_candidate_total": 348637,
            "whole_house_session_fell_back": True,
            "no_horizontal_overflow": True,
        })
        page.close()
    finally:
        browser.close()

proof = {
    "contract": "participation.automatic_runtime_browser_proof.v1",
    "fixture": str(args.fixture),
    "production_override": False,
    "results": results,
}
args.proof.parent.mkdir(parents=True, exist_ok=True)
args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
print(json.dumps(proof, sort_keys=True))

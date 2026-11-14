"""Verify automatic registered controls replace the existing Civic table atomically."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", required=True)
parser.add_argument("--fixture", type=Path, required=True)
parser.add_argument("--rolling-proof", type=Path, required=True)
parser.add_argument("--proof", type=Path, required=True)
parser.add_argument("--retained", action="store_true")
args = parser.parse_args()
assert not args.proof.exists()

run = json.loads((args.fixture / "run.json").read_bytes())
rolling = json.loads(args.rolling_proof.read_bytes())["OR_changed_R_projection"]
projection_path = args.fixture / run["house_sources"]["participation_state_projections"]["path"]
projection = json.loads(gzip.decompress(projection_path.read_bytes()))
scenario = next(row for row in projection["scenarios"] if row["control_id"] == "reporting-OR")
scenario.update(rolling["run1_scenario"])
next(row for row in projection["states"] if row["state_code"] == "OR")[
    "control_registered_denominator"] = rolling["run1_denominator"]
decision = dict(rolling["run1_decision"])
projection["automatic_update"] = {
    "contract": "participation.automatic_registered_control_update.v1",
    "base_native_control_version": 35,
    "accepted_state_decisions_retained": 51,
    "accepted_scenarios_retained": 34,
    "fresh_compatible_scenarios": 1,
    "changed_registered_frames": 1,
    "fresh_jurisdictions": ["OR"],
    "decisions": [decision],
    "new_scenarios_created": 0,
    "source_weights_probabilities_or_fits_changed": False,
    "frame_exchangeability_or_observed_staying_home_qualified": False,
    "native_outcome_fitting_applied": False,
    "unsupported_local_or_demographic_estimates_created": False,
    "coverage_claim": "Only Oregon's explicitly compatible registered frame changed.",
}
if args.retained:
    projection["automatic_update"].update({
        "fresh_compatible_scenarios": 0,
        "changed_registered_frames": 0,
        "fresh_jurisdictions": [],
        "decisions": [{
            "state_code": "AL", "decision": "native_registered_reference_only",
            "native_registered_denominator": 3852947,
            "denominator_basis": "different_registered_frame",
            "matching_accepted_scenarios": [],
            "local_or_demographic_estimate": False,
        }],
    })
decoded = (json.dumps(projection, sort_keys=True, separators=(",", ":")) + "\n").encode()
projection_body = gzip.compress(decoded, compresslevel=9, mtime=0)

version, commit = "d" * 64, "c" * 40
raw_base = (
    f"https://raw.githubusercontent.com/hanshanley/margin_of_error/"
    f"{commit}/automatic/versions/{version}/"
)
house = json.loads(json.dumps(run["house_sources"]))
house["base_url"] = raw_base
house["publication_bound"] = True
house["participation_state_projections"].update({
    "bytes": len(projection_body),
    "sha256": hashlib.sha256(projection_body).hexdigest(),
    "decoded_bytes": len(decoded),
    "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
})


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
           "automatic-civic-browser-fixture/complete-results.zip",
    "bytes": 123456,
    "sha256": "a" * 64,
    "media_type": "application/zip",
}
house["complete_download"] = complete
manifest = {
    "contract": "participation.automatic_runtime.v1",
    "version": version,
    "election_date": "2026-11-03",
    "processing_version": "civic-browser-fixture-v1",
    "input_results_version": "b" * 64,
    "checked_at": "2026-11-14T15:30:00+00:00",
    "house_sources": house,
    "source_models_refitted": False,
    "geographic_joins_changed": False,
    "all_states_certified_or_precinct_complete": False,
    "complete_download": {
        **complete, "immutable": True, "verified_anonymously": True,
    },
}
projection_url = house["participation_state_projections"]["url"]


def route_fixture(route, corrupt=False):
    url = route.request.url
    if url.endswith("/participation-data/automatic/latest.json"):
        route.fulfill(json=manifest)
    elif url == projection_url:
        route.fulfill(body=projection_body + (b"x" if corrupt else b""),
                      content_type="application/gzip")
    elif url.startswith(raw_base):
        route.fulfill(body=(args.fixture / url.removeprefix(raw_base)).read_bytes(),
                      content_type="application/gzip")
    else:
        route.continue_()


def open_page(browser, width, *, corrupt=False, javascript=True):
    context = browser.new_context(viewport={"width": width, "height": 1000},
                                  java_script_enabled=javascript)
    if javascript:
        context.route("**/*", lambda route: route_fixture(route, corrupt))
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    assert page.goto(args.base_url.rstrip("/") + "/voter-participation/?year=2026",
                     wait_until="domcontentloaded", timeout=90000).ok
    return context, page, errors


results = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in (1360, 390):
            context, page, errors = open_page(browser, width)
            panel = page.locator("[data-native-registered-controls]")
            expect(panel.locator("[data-native-automatic-status]")).to_have_attribute(
                "data-state", "active", timeout=90000)
            expect(panel.locator("[data-native-summary]")).to_contain_text(
                "34 conditional scenarios")
            expect(panel.locator("[data-native-registered-scenario]")).to_have_count(34)
            expect(panel.locator("[data-native-registered-state]")).to_have_count(51)
            ore = panel.locator('[data-native-registered-scenario="reporting-OR"]')
            expect(ore.locator("[data-native-registered]")).to_have_text("3,109,133")
            expect(ore.locator("[data-native-modeled-voter]")).to_have_text("2,083,353")
            expect(ore.locator("[data-native-modeled-nonvoter]")).to_have_text("1,025,780")
            expect(ore.locator("[data-native-time]")).to_have_text(
                "Native source clock not supplied")
            expect(panel.locator('[data-native-registered-state="OR"] '
                                 '[data-native-state-registered]')).to_have_text("3,109,133")
            expect(panel.locator("[data-native-automatic-decision]")).to_have_count(
                0 if args.retained else 1)
            if args.retained:
                expect(panel.locator("[data-native-automatic-reference]")).to_have_count(1)
                expect(panel.locator("[data-native-automatic-reference]")).to_contain_text(
                    "No registered-control scenario")
            else:
                expect(panel.locator("[data-native-automatic-decision]")).to_contain_text(
                    "No native source clock was supplied")
            expect(panel.locator("[data-native-reference-change]")).to_have_count(0)
            expect(panel.locator('[data-native-registered-scenario="reporting-AL"] '
                                 '[data-native-registered]')).to_have_text("3,852,947")
            fresh_counts = (
                panel.locator('[data-native-registered-scenario][data-native-fresh="true"]').count(),
                panel.locator('[data-native-registered-state][data-native-fresh="true"]').count(),
                panel.locator('[data-native-registered-scenario][data-native-fresh="false"]').count(),
                panel.locator('[data-native-registered-state][data-native-fresh="false"]').count(),
            )
            assert fresh_counts == ((0, 0, 34, 51) if args.retained
                                    else (2, 1, 32, 50)), fresh_counts
            expect(panel.locator("[data-native-automatic-download]")).to_have_attribute(
                "href", complete["url"])
            expect(panel.locator("[data-native-runtime-fingerprint]")).to_contain_text(
                "123,456 bytes")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            results.append({"case": "retained-registered-frame" if args.retained
                            else "changed-registered-frame", "width": width,
                            "OR_registered": 3109133, "scenarios": 34, "states": 51,
                            "fresh_DOM_nodes": 0 if args.retained else 3, "errors": errors})
            context.close()

        context, page, errors = open_page(browser, 390, corrupt=True)
        panel = page.locator("[data-native-registered-controls]")
        expect(panel.locator("[data-native-automatic-status]")).to_have_attribute(
            "data-state", "error", timeout=90000)
        expect(panel.locator('[data-native-registered-scenario="reporting-OR"] '
                             '[data-native-registered]')).to_have_text("3,109,123")
        expect(panel.locator('[data-native-registered-state="OR"] '
                             '[data-native-state-registered]')).to_have_text("3,109,123")
        expect(panel.locator("[data-native-reference-change]")).to_have_count(2)
        expect(panel.locator("[data-native-automatic-decision]")).to_have_count(0)
        assert not errors, errors
        results.append({"case": "corrupt-body-fallback", "accepted_OR_registered": 3109123,
                        "accepted_reference_change_rows": 2, "errors": errors})
        context.close()

        context, page, errors = open_page(browser, 390, javascript=False)
        panel = page.locator("[data-native-registered-controls]")
        expect(panel.locator('[data-native-registered-scenario="reporting-OR"] '
                             '[data-native-registered]')).to_have_text("3,109,123")
        expect(panel.locator("[data-native-registered-scenario]")).to_have_count(34)
        expect(panel.locator("[data-native-registered-state]")).to_have_count(51)
        expect(panel.locator("[data-native-automatic-download]")).to_be_hidden()
        assert not errors, errors
        results.append({"case": "no-javascript-static-fallback",
                        "accepted_OR_registered": 3109123, "scenarios": 34, "states": 51})
        context.close()
    finally:
        browser.close()

proof = {
    "contract": "participation.automatic_registered_control_browser_proof.v1",
    "production_override": False,
    "results": results,
}
args.proof.parent.mkdir(parents=True, exist_ok=True)
args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
print(json.dumps(proof, sort_keys=True))

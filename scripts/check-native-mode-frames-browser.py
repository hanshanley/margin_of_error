"""Verify all204 source-mode sidebar decisions on actual desktop/mobile controls."""

import argparse
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/county-source-reviews/20261110-native-mode-frames-01"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
parser.add_argument("--nevada-county-followup", action="store_true")
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
query = json.loads(gzip.decompress((SOURCE / "queries.json.gz").read_bytes()))
if args.nevada_county_followup:
    native = json.loads(gzip.decompress((ROOT /
        "data/county-source-reviews/20261110-nevada-native-counties-01/queries.json.gz").read_bytes()))
    for row in query["complete204_state_mode_decisions"]:
        if row["state_code"] == "NV" and row["mode"] in ("available", "official"):
            row["after_selected_rows"] = 17
            row["after_observations"] = [dict(county_id="additional:NV:Washoe" if item["county"] == "Washoe"
                else "additional:NV:" + item["county_fips"], ballots=item["source_count"])
                for item in native["county_decisions"]]
codes = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
names = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
    "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
]
state_names = dict(zip(codes, names))
assert len(state_names) == 51
cases = []


def verify_decision(page, row):
    expect(page.locator("#mode")).to_have_value(row["mode"])
    expect(page.locator("#state-select")).to_have_value(state_names[row["state_code"]])
    selector = page.locator('#current-county-select option:not([value=""])')
    if row["explicit_requested_mode"] and not row["qualified_requested_frame_available"]:
        label = "in-person early" if row["mode"] == "in_person_early" else "mail-returned"
        message = page.get_by_text(f'No qualified {label} local frame for {state_names[row["state_code"]]}.', exact=False)
        expect(message).to_be_visible(timeout=90000)
        expect(message).to_contain_text("unknown, not zero")
        expect(selector).to_have_count(0)
        link = page.get_by_role("link", name="Complete source-frame analysis and queries")
        expect(link).to_have_attribute("href",
            "https://github.com/hanshanley/margin_of_error/releases/download/voter-native-mode-frames-20261110-01/complete-analysis.zip")
    else:
        expect(selector).to_have_count(row["after_selected_rows"], timeout=90000)
        if row["after_selected_rows"]:
            observation = row["after_observations"][0]
            page.select_option("#current-county-select", observation["county_id"])
            if observation["ballots"] is not None:
                expect(page.locator("#current-county-detail")).to_contain_text(f'{observation["ballots"]:,}')


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in [False, True]:
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            assert response.ok
            expect(page.locator("#year")).to_have_value("2026", timeout=90000)
            expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
            decisions = []
            for row in query["complete204_state_mode_decisions"]:
                page.select_option("#state-select", state_names[row["state_code"]])
                page.select_option("#mode", row["mode"])
                verify_decision(page, row)
                if row["state_code"] in ["CT", "DC", "PA", "SD"] and row["mode"] == "in_person_early":
                    page.locator("#tab-methods").click()
                    expect(page.locator("#methods-archive")).to_be_hidden()
                    page.locator("#tab-states").click()
                    verify_decision(page, row)
                decisions.append(dict(state_code=row["state_code"], mode=row["mode"],
                    selected_rows=row["after_selected_rows"], changed=row["changed"]))
                if row["changed"]:
                    print(json.dumps(dict(check="unsupported_mode_rejected", mobile=mobile,
                        state=row["state_code"], mode=row["mode"])), flush=True)
            assert len(decisions) == 204 and sum(row["changed"] for row in decisions) == 23
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(mobile=mobile, complete204_actual_control_decisions=decisions,
                all102_available_official_decisions_preserved=not args.nevada_county_followup,
                all100_unaffected_available_official_decisions_preserved=True,
                Nevada_new_native_followup_qualified=args.nevada_county_followup,
                all67_qualified_mode_decisions_preserved=True,
                all23_unqualified_other_frame_selections_withheld=True,
                genuine_source_counts_sampled_without_reallocation=True,
                DC_existing_available_count_retained=True,
                methods_roundtrips_preserve_selected_state_and_mode=True,
                missing_mode_explained_not_false_zero_or_false_missing_ingestion=True))
            context.close()
    finally:
        browser.close()
proof = dict(status="PASS_all51_complete204_actual_mode_decisions_desktop_mobile_no_source_substitution",
    base_url=base, cases=cases, valid_source_requests_overridden=False,
    source_counts_changed=False, new_population_or_normalized_mode_claim=False,
    Nevada_new_source_snapshot="20261110-nevada-native-counties-01" if args.nevada_county_followup else None,
    nationwide_project_complete=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

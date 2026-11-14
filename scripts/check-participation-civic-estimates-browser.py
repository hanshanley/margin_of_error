"""Verify every selected Civic estimate, source-frame label and complete download."""

import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-civic-estimates/20261108-01/output"
NATIVE = ROOT / "data/participation-registered-controls/20261114-35/display-model.json"


def pct(value):
    return f"{float(value):.2f}%"


def pp(value):
    return ("+" if float(value) > 0 else "") + f"{float(value):.2f}"


def source_units(value):
    return format(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP), ",")


def check(base, proof, focus_state="NM"):
    expected = json.loads((DATA / "summary.json").read_text())
    metadata = json.loads((DATA / "download.json").read_text())
    native = json.loads(NATIVE.read_bytes())
    native_changes = native["native_reference_changes"]
    focus_control = next(row["control_id"] for row in native["scenarios"]
                         if row["state_code"] == focus_state)
    modes = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
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
                        context.route("**/participation-civic-estimates/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    drawer = page.locator("#participation-research")
                    assert not drawer.evaluate("element => element.open"), mode
                    drawer.locator(":scope > summary").click()
                    panel = page.locator("#participation-civic-estimates")
                    drawer.get_by_text("Additional survey tables and model assumptions", exact=True).click()
                    expect(panel).to_be_visible()
                    expect(panel.locator("[data-civic-state]")).to_have_count(51)
                    for row in expected["participation"]:
                        if row["scope"] != "POOLED_SOURCE":
                            selector = f'[data-civic-state="{row["scope"]}"]'
                        elif row["dimension"] == "overall":
                            selector = "[data-civic-overall]"
                        else:
                            selector = f'[data-civic-demographic="{row["dimension"]}:{row["group"]}"]'
                        target = panel.locator(selector)
                        for attribute, field in (
                            ("voter", "modeled_voter_pct"), ("nonvoter", "modeled_nonvoter_pct"),
                            ("reported", "already_voted_self_report_pct"),
                        ):
                            expect(target.locator(f"[data-civic-{attribute}]")).to_have_text(pct(row[field]))
                    expect(panel.locator('[data-civic-state="DC"]')).to_contain_text("Not sampled; no estimate allocated")
                    frame = panel.locator("[data-native-registered-controls]")
                    expect(frame).to_have_attribute("data-native-version", str(native["native_control_version"]))
                    expect(frame.locator("[data-native-registered-scenario]")).to_have_count(len(native["scenarios"]))
                    expect(frame.locator("[data-native-registered-state]")).to_have_count(51)
                    for native_change in native_changes:
                        change = frame.locator(
                            f'[data-native-reference-change={json.dumps(native_change["control_id"])}]')
                        expect(change).to_have_attribute(
                            "data-native-reference-current", str(native_change["current_native_numerator"]))
                        expect(change).to_have_attribute(
                            "data-native-reference-clock", native_change["current_native_clock"])
                        expect(change).to_have_attribute(
                            "data-native-reference-diagnostic",
                            native_change["current_native_minus_model_diagnostic"])
                        expect(change).to_have_attribute(
                            "data-native-registered-difference",
                            str(native_change["registered_denominator_difference"]))
                        expect(change).to_have_attribute(
                            "data-native-modeled-voter-difference",
                            native_change["conditional_modeled_voter_unit_difference"])
                        if native_change["registered_denominator_difference"] == 0:
                            expect(change).to_contain_text(
                                "Civic weights and conditional modeled units do not change")
                        else:
                            expect(change).to_contain_text(
                                "Under unchanged Civic probabilities")
                            expect(change).to_contain_text("change mechanically")
                        expect(change).to_contain_text(
                            "not validated model error or observed nonparticipation")
                    for row in native["scenarios"]:
                        target = frame.locator(
                            f'[data-native-registered-scenario={json.dumps(row["control_id"])}]')
                        expect(target).to_contain_text(row["source_time_label"])
                        for attribute, field in (
                                ("registered", "native_registered_denominator"),
                                ("modeled-voter", "conditional_modeled_voter_count"),
                                ("modeled-nonvoter", "conditional_modeled_nonvoter_count")):
                            cell = target.locator(f"[data-native-{attribute}]")
                            expect(cell).to_have_attribute("data-native-" + attribute, row[field])
                            expect(cell).to_have_text(source_units(row[field]))
                    for row in native["states"]:
                        target = frame.locator(f'[data-native-registered-state="{row["state_code"]}"]')
                        cells = target.locator("td")
                        expect(cells.nth(0)).to_have_text(
                            source_units(row["control_registered_denominator"])
                            if row["control_registered_denominator"] else "Not supplied")
                        scenarios = sum(item["state_code"] == row["state_code"] for item in native["scenarios"])
                        expect(cells.nth(1)).to_have_text(str(scenarios) if scenarios else "No source-frame scenario")
                        expect(cells.nth(2)).to_have_text(row["civic_source_n"] or "Not sampled")
                    expect(frame).to_contain_text("not observed voters, confirmed staying home or certified turnout")
                    expect(frame).to_contain_text("overlapping frames must not be added")
                    groups = native.get("source_group_downloads", {})
                    if native["publication_status"]["status"] == "verified_immutable":
                        assert native["count_publication_status"]["status"] == "verified_immutable"
                        expect(frame.locator('[data-native-publication-status="verified_immutable"]')).to_contain_text(
                            "Verified immutable releases")
                        expect(frame.locator('[data-native-registered-download="model-zip"]')).to_have_attribute(
                            "href", native["complete_download"]["url"])
                        expect(frame.locator('[data-native-registered-download="count-zip"]')).to_have_attribute(
                            "href", native["count_download"]["url"])
                    else:
                        assert native["count_publication_status"]["status"] == "planned_immutable"
                        expect(frame.locator('[data-native-publication-status="planned_immutable"]')).to_contain_text(
                            "not yet both immutable-published and anonymously")
                        expect(frame.locator('[data-native-registered-download]')).to_have_count(0)
                    expect(frame.locator("[data-native-member-inventory] code")).to_have_count(
                        len(native["query_downloads"]) + len(native["source_group_downloads"]))
                    if groups:
                        expect(frame).to_contain_text("not full demographic turnout")
                    for kind, filename in (
                            ("zip", "complete-analysis.zip"),
                            ("states", "complete-state-control-query.csv"),
                            ("controls", "complete-native-control-dispositions.csv"),
                            ("scenarios", "complete-conditional-registered-scenarios.csv"),
                            ("groups", "complete-native-participation-group-controls.csv"),
                            ("queries", "complete-current-native-source-queries.json.gz")):
                        expect(frame.locator(
                            f'[data-native-previous-download="{kind}"]')).to_have_attribute(
                            "href", "https://github.com/hanshanley/margin_of_error/releases/download/"
                            f"participation-state-controls-20261113-34/{filename}")
                    frame.locator(":scope > summary").click()
                    focus_row = frame.locator(
                        f'[data-native-registered-scenario={json.dumps(focus_control)}]')
                    expect(focus_row).to_be_visible()
                    if proof and mode in ("desktop", "mobile"):
                        focus_row.scroll_into_view_if_needed()
                        page.screenshot(path=str(proof.with_suffix(f".{mode}.png")))
                    frame.get_by_text("Every state and D.C. source-frame decision", exact=True).click()
                    expect(frame.locator('[data-native-registered-state="DC"]')).to_be_visible()
                    expect(panel.locator("[data-civic-flow]")).to_have_count(112)
                    for row in expected["conditional_flows"]:
                        selector = f'[data-civic-flow="{row["prior_election"]}:{row["dimension"]}:{row["group"]}:{row["prior_choice"]}"]'
                        target = panel.locator(selector)
                        for index, field in enumerate(("D_pct", "R_pct", "O_U_pct", "N_pct")):
                            expect(target.locator("td").nth(index)).to_have_text(pct(row[field]))
                    for row in expected["margin_components"]:
                        target = panel.locator(f'[data-civic-margin="{row["prior_election"]}"]')
                        for index, field in enumerate((
                            "switching_pp", "modeled_nonparticipation_pp",
                            "no_prior_contest_vote_entry_pp", "other_or_unresolved_pp",
                            "denominator_pp", "total_within_source_margin_change_pp",
                        )):
                            expect(target.locator("td").nth(index)).to_have_text(pp(row[field]))
                    for text in (
                        "not administratively observed turnout or measured staying home",
                        "not a certified national population estimate", "exact target, calibration and field period",
                        "not all", "113,020", "not fixed 2024 cohorts", "not a precision guarantee",
                        "Eligibility, death and migration remain unknown", "not first-ever voting",
                        "No state survey estimate is allocated to counties or precincts",
                    ):
                        if text != "not all":
                            expect(panel).to_contain_text(text)
                    panel.get_by_text("All 50 state source estimates; D.C. not sampled", exact=True).click()
                    expect(panel.locator('[data-civic-state="AK"]')).to_be_visible()
                    panel.get_by_text("Within-source switching and participation components", exact=True).click()
                    expect(panel.locator('[data-civic-margin="2024"]')).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    expect(page.locator("#participation-survey [data-survey-status]")).to_have_count(936)
                    assert not errors, (mode, errors)
                    if mode == "desktop" and native["publication_status"]["status"] == "verified_immutable":
                        response = context.request.get(native["complete_download"]["url"])
                        assert response.ok, "model complete-analysis.zip"
                        model_body = response.body()
                        assert len(model_body) == native["complete_download"]["bytes"]
                        assert hashlib.sha256(model_body).hexdigest() == native["complete_download"]["sha256"]
                        with zipfile.ZipFile(io.BytesIO(model_body)) as archive:
                            assert archive.testzip() is None
                            for filename, item in {**native["query_downloads"], **groups}.items():
                                member_body = archive.read(item["member"])
                                assert len(member_body) == item["bytes"], filename
                                assert hashlib.sha256(member_body).hexdigest() == item["sha256"], filename
                        response = context.request.get(native["count_download"]["url"])
                        assert response.ok, "count complete-analysis.zip"
                        count_body = response.body()
                        assert len(count_body) == native["count_download"]["bytes"]
                        assert hashlib.sha256(count_body).hexdigest() == native["count_download"]["sha256"]
                        with zipfile.ZipFile(io.BytesIO(count_body)) as archive:
                            assert archive.testzip() is None
                            count_dataset = json.loads(
                                archive.read("queries/reference-counts/dataset.json"))
                            assert count_dataset["version"] == native["count_download"]["version"]
                        for key, filename, count in (
                            ("zip", "complete-analysis.zip", None),
                            ("participation", "participation.csv", 79),
                            ("flows", "conditional-flows.csv", 112),
                            ("margins", "margin-components.csv", 2),
                        ):
                            href = panel.locator(f'[data-civic-download="{key}"]').get_attribute("href")
                            response = context.request.get(href)
                            assert response.ok, filename
                            body = response.body()
                            assert body == (DATA / filename).read_bytes(), filename
                            if count is not None:
                                assert len(list(csv.DictReader(io.StringIO(body.decode())))) == count
                            else:
                                assert len(body) == metadata["bytes"]
                                assert hashlib.sha256(body).hexdigest() == metadata["sha256"]
                                with zipfile.ZipFile(io.BytesIO(body)) as archive:
                                    assert archive.testzip() is None
                                    for member, item in json.loads(archive.read("checksums.json")).items():
                                        original = archive.read(member)
                                        assert len(original) == item["bytes"]
                                        assert hashlib.sha256(original).hexdigest() == item["sha256"]
                    modes.append({
                        "mode": mode, "passed": True, "participation_rows": 79,
                        "conditional_rows": 112, "margin_rows": 2,
                        "default_closed_research_preserved": True,
                        "native_registered_scenarios": len(native["scenarios"]),
                        "native_source_frame_decisions": 51,
                        "native_complete_download_matches_verified_immutable_asset": True,
                        "native_source_group_downloads": len(groups),
                        "native_reference_changed_states": [
                            item["state_code"] for item in native_changes],
                        "native_reference_currents": {
                            item["state_code"]: item["current_native_numerator"]
                            for item in native_changes},
                        "planned_unverified_downloads_not_requested": (
                            native["publication_status"]["status"] == "planned_immutable"),
                        "all_other_scenario_means_checked": True,
                    })
                finally:
                    context.close()
        finally:
            browser.close()
    result = {"base_url": base, "checks": modes}
    if proof:
        proof.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--focus-state", default="NM")
    args = parser.parse_args()
    check(args.base_url, args.proof, args.focus_state)

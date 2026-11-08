"""Verify every selected Civic estimate, source-frame label and complete download."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-civic-estimates/20261108-01/output"


def pct(value):
    return f"{float(value):.2f}%"


def pp(value):
    return ("+" if float(value) > 0 else "") + f"{float(value):.2f}"


def check(base, proof):
    expected = json.loads((DATA / "summary.json").read_text())
    metadata = json.loads((DATA / "download.json").read_text())
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
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    drawer = page.locator("#participation-research")
                    assert not drawer.evaluate("element => element.open"), mode
                    drawer.locator(":scope > summary").click()
                    panel = page.locator("#participation-civic-estimates")
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
                    if mode == "desktop":
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
    args = parser.parse_args()
    check(args.base_url, args.proof)

"""Verify selected Indiana tables, source limits and complete downloads in four modes."""

import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PATH = "/participation-hamilton-indiana-history/20261107-01/"


def signed(value, precision=0):
    number = Decimal(str(value)).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    return ("+" if number > 0 else "") + format(number, f",.{precision}f")


def check(base, proof):
    reference = json.loads((ROOT / ("public" + PATH) / "history.json").read_bytes())
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for mode, options in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("mobile", {"viewport": {"width": 390, "height": 844}}),
                ("no_javascript", {"java_script_enabled": False}), ("failed_json", {}),
            ]:
                context = browser.new_context(**options)
                try:
                    if mode == "failed_json":
                        context.route("**/participation-hamilton-indiana-history/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-hamilton-indiana-history")
                    expect(panel).to_be_visible()
                    for text in (
                        "2026 is an unofficial snapshot, not final turnout",
                        "Count changes do not identify who stayed home", "not a fixed-person cohort",
                        "not metadata alone", "No timezone is supplied", "unclassified",
                        "No new longitudinal precinct map", "not forced into either party",
                    ):
                        expect(panel).to_contain_text(text)
                    cells = 0
                    for item in reference["elections"]:
                        row = panel.locator(f'[data-hamilton-year="{item["year"]}"]')
                        for field in ("registered_voters", "election_day", "paper_absentee", "walk_in_absentee",
                                      "total_votes_cast", "precinct_count", "native_turnout_percent"):
                            value = f'{item[field]}%' if field == "native_turnout_percent" else f'{item[field]:,}'
                            expect(row.locator(f'[data-hamilton-field="{field}"]')).to_have_text(value)
                            cells += 1
                    for item in reference["reported_count_comparisons"]:
                        expect(panel.locator(f'[data-hamilton-change="{item["baseline_year"]}"]')).to_have_text(signed(item["reported_count_change"]))
                        cells += 1
                    panel.locator("#hamilton-indiana-contests > summary").click()
                    for index, item in enumerate(reference["contests"]):
                        row = panel.locator(f'[data-hamilton-contest="{index}"]')
                        for field in ("reported_public_count", "candidate_total", "unclassified_reported_count_gap", "two_party_margin_pp"):
                            value = signed(item[field], 2) if field == "two_party_margin_pp" else f'{item[field]:,}'
                            expect(row.locator(f'[data-hamilton-field="{field}"]')).to_have_text(value)
                            cells += 1
                        for candidate, item_candidate in enumerate(item["candidates"]):
                            candidate_row = panel.locator(f'[data-hamilton-candidate="{index}-{candidate}"]')
                            expect(candidate_row).to_contain_text(item_candidate["native_label"])
                            for field in ("election_day", "paper_absentee", "walk_in_absentee", "total_votes", "native_percent"):
                                value = item_candidate[field] if field == "native_percent" else f'{item_candidate[field]:,}'
                                expect(candidate_row.locator(f'[data-hamilton-field="{field}"]')).to_have_text(value)
                                cells += 1
                    for index, item in enumerate(reference["descriptive_contest_comparisons"]):
                        expect(panel.locator(f'[data-hamilton-margin-change="{index}"]')).to_have_text(
                            signed(item["two_party_margin_change_pp"], 2) + " pp")
                        cells += 1
                    panel.locator("#hamilton-indiana-native-anomalies > summary").click()
                    expect(panel.locator("[data-hamilton-anomaly]")).to_have_count(10)
                    for index, item in enumerate(reference["native_total_cell_discrepancies"]):
                        row = panel.locator(f'[data-hamilton-anomaly="{index}"]')
                        for field in ("native_total_votes_cast", "derived_precinct_and_mode_sum"):
                            expect(row.locator(f'[data-hamilton-field="{field}"]')).to_have_text(f'{item[field]:,}')
                            cells += 1
                    assert cells == 130
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    for old in ("#participation-ces-classification", "#participation-nd-long-history", "#participation-clark-history"):
                        expect(page.locator(old)).to_be_visible()
                    links = panel.locator(".download-links a")
                    expect(links).to_have_count(3)
                    if mode == "desktop":
                        response = context.request.get(base.rstrip("/") + PATH + "complete-analysis.zip")
                        info_response = context.request.get(base.rstrip("/") + PATH + "download.json")
                        assert response.ok and info_response.ok
                        body, metadata = response.body(), info_response.json()
                        assert body == (ROOT / ("public" + PATH) / "complete-analysis.zip").read_bytes()
                        assert len(body) == metadata["bytes"] and hashlib.sha256(body).hexdigest() == metadata["sha256"]
                        with zipfile.ZipFile(io.BytesIO(body)) as archive:
                            assert archive.testzip() is None
                            inventory = json.loads(archive.read("checksums.json"))
                            assert len(archive.namelist()) == metadata["members"] and set(archive.namelist()) == {*inventory, "checksums.json"}
                            for name, receipt in inventory.items():
                                raw = archive.read(name)
                                assert len(raw) == receipt["bytes"] and hashlib.sha256(raw).hexdigest() == receipt["sha256"]
                    checks.append({"mode": mode, "passed": True, "numeric_cells_verified": cells,
                                   "all_literal_candidates_and_source_limits_verified": True})
                finally:
                    context.close()
        finally:
            browser.close()
    if proof:
        with proof.open("x") as target:
            json.dump({"base_url": base, "checks": checks}, target, indent=2)
            target.write("\n")
    print(json.dumps(checks))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4367")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    check(args.base_url, args.proof)

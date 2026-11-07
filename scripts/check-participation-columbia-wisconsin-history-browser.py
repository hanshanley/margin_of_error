"""Verify Columbia source-qualified counts and complete external downloads in four modes."""

import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-columbia-wisconsin-history/20261107-01"
PUBLIC = "participation-columbia-wisconsin-history/20261107-01/download.json"


def signed(value, precision=0):
    number = Decimal(str(value)).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    return ("+" if number > 0 else "") + format(number, f",.{precision}f")


def check(base, proof):
    reference = json.loads((DATA / "output/history.json").read_bytes())
    receipt_raw = (ROOT / "public" / PUBLIC).read_bytes()
    receipt = json.loads(receipt_raw)
    selected = json.loads((DATA / "selected-observations.json").read_bytes())
    assert receipt["immutable"] and receipt["release_id"] == 437560232
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
                        context.route("**/*.json*", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    panel = page.locator("#participation-columbia-wisconsin-history")
                    expect(panel).to_be_visible()
                    for text in (
                        "Both elections are unofficial snapshots here", "not measured prior-voter drop-off",
                        "not a fixed-person cohort", "not 37 proven individual precincts",
                        "No registration denominator", "unique-person N26",
                    ):
                        expect(panel).to_contain_text(text)
                    cells = 0
                    for item in reference["elections"]:
                        row = panel.locator(f'[data-columbia-year="{item["year"]}"]')
                        for field in ("ballots", "native_local_reporting_units", "native_unit_contest_vectors", "native_contests"):
                            expect(row.locator(f'[data-columbia-field="{field}"]')).to_have_text(f'{item[field]:,}')
                            cells += 1
                    expect(panel.locator("[data-columbia-ballot-change]")).to_have_text(
                        signed(reference["reported_ballot_count_change_2026_minus_2024"]))
                    cells += 1
                    panel.locator("#columbia-wisconsin-contests > summary").click()
                    for text in ("unclassified", "independents are not reassigned",
                                 "not measured abstention", "not additive effects"):
                        expect(panel).to_contain_text(text)
                    for index, item in enumerate(reference["contest_context"]):
                        row = panel.locator(f'[data-columbia-contest="{index}"]')
                        expect(row).to_contain_text(f'{item["year"]} {item["native_contest"]}')
                        for field in ("county_ballots", "candidate_votes", "unclassified_ballot_minus_contest_votes", "two_party_margin_pp"):
                            value = signed(item[field], 2) if field == "two_party_margin_pp" else f'{item[field]:,}'
                            expect(row.locator(f'[data-columbia-field="{field}"]')).to_have_text(value)
                            cells += 1
                        for answer, candidate in enumerate(item["candidates"]):
                            candidate_row = panel.locator(f'[data-columbia-candidate="{index}-{answer}"]')
                            expect(candidate_row).to_contain_text(candidate["native_label"])
                            expect(candidate_row.locator('[data-columbia-field="votes"]')).to_have_text(f'{candidate["votes"]:,}')
                            cells += 1
                    expect(panel.locator("[data-columbia-candidate]")).to_have_count(18)
                    for index, item in enumerate(reference["descriptive_comparisons"]):
                        expect(panel.locator(f'[data-columbia-margin-change="{index}"]')).to_have_text(
                            signed(item["two_party_margin_change_pp"], 2) + " pp")
                        cells += 1
                    assert cells == 41
                    panel.locator("#columbia-wisconsin-methods > summary").click()
                    for index, item in enumerate(reference["elections"]):
                        row = panel.locator(f'[data-columbia-clock="{item["year"]}"]')
                        for field in ("local_report_clock", "county_report_clock", "status"):
                            expect(row).to_contain_text(item[field])
                        expect(row.locator("a")).to_have_attribute("href", selected["elections"][index]["source_receipts"][0]["requested_url"])
                    for text in (
                        "No timezone is supplied", "838 local contest vectors", "44 county contest controls",
                        "Matching unit names do not establish unchanged precinct boundaries",
                        "No new longitudinal precinct map", "not metadata alone",
                        "all 76 ballot cells", "2,647 candidate/answer cells", "six sanitized original source receipts",
                        "seven tests", "does not rerun native PDF extraction", "personal records are not redistributed",
                        "not a native-document redistribution license",
                    ):
                        expect(panel).to_contain_text(text)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    for old in ("#participation-cps-state-history", "#participation-hamilton-indiana-history",
                                "#participation-ces-classification", "#participation-nd-long-history"):
                        expect(page.locator(old)).to_be_visible()
                    expect(panel.locator(".download-links a")).to_have_count(4)
                    downloads = []
                    for item in receipt["assets"]:
                        expect(panel.locator(f'[data-columbia-download="{item["file"]}"]')).to_have_attribute("href", item["url"])
                        if mode != "desktop":
                            continue
                        response = context.request.get(item["url"], timeout=60000)
                        assert response.ok, (item["file"], response.status)
                        raw = response.body()
                        assert raw == (DATA / "output" / item["file"]).read_bytes()
                        assert len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
                        if item["file"] == "complete-analysis.zip":
                            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                                inventory = json.loads(archive.read("checksums.json"))
                                assert archive.testzip() is None
                                assert len(archive.namelist()) == 10 and len(inventory) == 9
                                assert set(archive.namelist()) == {*inventory, "checksums.json"}
                                for name, row in inventory.items():
                                    member = archive.read(name)
                                    assert len(member) == row["bytes"] and hashlib.sha256(member).hexdigest() == row["sha256"]
                        downloads.append({**item, "complete_public_bytes_verified": True})
                    if mode == "desktop":
                        response = context.request.get(base.rstrip("/") + "/" + PUBLIC)
                        assert response.ok and response.body() == receipt_raw
                    checks.append({"mode": mode, "passed": True, "numeric_cells_verified": cells,
                                   "all_literal_candidates_four_clocks_and_source_limits_verified": True,
                                   "downloads": downloads})
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
    parser.add_argument("--base-url", default="http://127.0.0.1:4371")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    check(args.base_url, args.proof)

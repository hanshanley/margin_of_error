"""Verify exact county participation joins, source preservation and missingness."""

import argparse
from collections import Counter
import datetime
import gzip
import hashlib
import json
import math
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--proof", required=True, type=Path)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
root = Path(__file__).resolve().parents[1]
facts = root / "public/participation-county-context/20261106-05"
review = json.loads((facts / "review.json").read_text())
records = json.loads(gzip.decompress((facts / "complete-source-records.json.gz").read_bytes()))
pointer = json.loads((root / "public/participation-county-context.json").read_text())
previous = root / "data/county-source-reviews/20261106-elk-forest-explorer-01"
baseline = json.loads((previous / "baseline.json").read_text())
sources = [row for row in json.loads((root / "public/participation-source-reviews.json").read_text())["reviews"]
           if row["id"] in {"pennsylvania-elk-20261106-01", "pennsylvania-forest-20261106-01"}]
assert len(sources) == 2
source_ids = {row["id"] for row in sources}
old_links = Counter(baseline["previous_download_urls"])
links = old_links + Counter(row["url"] for row in pointer["downloads"] if row["url"] not in old_links)
for source in sources:
    links += Counter([source["complete_download_url"]] + [source["base_url"] + row["file"] for row in source["tables"]])
names = dict(AL="Alabama", AR="Arkansas", AZ="Arizona", DC="District of Columbia",
             FL="Florida", IA="Iowa", KY="Kentucky", MO="Missouri", NJ="New Jersey",
             NV="Nevada", OR="Oregon", PA="Pennsylvania", VA="Virginia",
             WA="Washington", WY="Wyoming")
errors, modes, failures = [], [], []


def url(name="Washington"):
    return base + "/voter-participation/?year=2026&view=states&mode=available&map-level=county&map-color=turnout&state=" + name.replace(" ", "%20")


def check_static(page):
    observed = json.loads(page.locator("table[data-reviewed-county-participation]").get_attribute("data-reviewed-county-participation"))
    assert observed == records[-43:]
    assert [row for row in observed if row["review_id"] not in source_ids] == baseline["previous_entire_reviewed_records"]
    clarion = next(row for row in observed if row["county"] == "Clarion")
    assert clarion["ballots"] == 12975 and clarion["denominator"] == 23306
    assert clarion["native_record"]["provisional_count"] == ""
    assert clarion["participation_measure_literal"] == "Voters Cast"
    assert clarion["source_status_literal"] == "UNOFFICIAL ELECTION RESULTS"
    expect(page.locator('table[data-uf-turnout="2026"] tbody tr')).to_have_count(52)
    assert [cell.strip() for cell in page.locator("table[data-historical-house] tbody tr th").all_text_contents()] == baseline["historical_years"]
    actual = Counter(page.locator("#downloads a[download]").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))"))
    assert actual == links
    expect(page.locator("#county-context-review")).to_contain_text("436 whole-county participation observations")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def check_counties(page, code):
    expected = {row["contextual_geoid"]: row for row in review["observations"] if row["state_code"] == code}
    expect(page.locator(".substate-feature[data-context-review='20261106-05']")).to_have_count(len(expected), timeout=30000)
    actual = page.locator(".substate-feature[data-level='county']").evaluate_all(
        "paths => paths.map(path => Object.fromEntries([...path.attributes].map(attr => [attr.name, attr.value])))")
    assert len(actual) == review["geometry"][code]["features"]
    counts = rates = 0
    for path in actual:
        native = expected.get(path["data-geography"])
        if native is None:
            assert path["data-count"] == "" and path["data-rate"] == ""
            assert path["fill"] == "#edf0f3"
            continue
        assert path["data-source-county-id"] == native["county_id"]
        assert int(path["data-count"]) == native["ballots"]
        assert path["data-context-review"] == "20261106-05"
        counts += 1
        rate = native["reported_pct"]
        if rate is None:
            assert path["data-rate"] == "" and path["fill"] == "#edf0f3"
        else:
            assert math.isclose(float(path["data-rate"]), rate, rel_tol=1e-14)
            t = max(0, min(1, (rate - 20) / 65))
            fill = "rgb(" + ",".join(str(math.floor(a + t * (b - a) + .5))
                                    for a, b in zip([240, 244, 249], [40, 71, 102])) + ")"
            assert path["fill"] == fill
            rates += 1
    sample = next(iter(expected.values()))
    page.locator("#current-county-select").select_option(sample["county_id"])
    expect(page.locator("#current-county-detail .selection-rate")).to_have_text(f"{sample['ballots']:,}")
    expect(page.locator("#caption")).to_contain_text("Counts with missing or withheld rates remain gray")
    expect(page.locator("#geography-note")).to_contain_text(f"{len(expected)} independently audited identity joins")
    if code == "PA":
        page.locator(".substate-feature[data-geography='42065']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:PA:Jefferson")
        detail = page.locator("#current-county-detail")
        expect(detail.locator(".selection-rate")).to_have_text("15,205")
        for text in ("Voters Cast", "28,226 native registered voters", "53.87%",
                     "summary: 11/4/2026 3:47:13 PM", "statement: 11/4/2026 3:47:52 PM",
                     "timezone not declared"):
            expect(detail).to_contain_text(text)
        page.locator(".substate-feature[data-geography='42031']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:PA:Clarion")
        expect(detail.locator(".selection-rate")).to_have_text("12,975")
        for text in ("Voters Cast", "23,306 native registered voters", "55.67%",
                     "county_report: 11/3/2026 9:49:20 PM", "timezone not declared",
                     "UNOFFICIAL ELECTION RESULTS", "missing mode counts are not zero",
                     "Foxburg referendum Times Cast 82/116", "does not establish completed ballot counting"):
            expect(detail).to_contain_text(text)
        for geoid, county, count, texts in (
            ("42023", "Cameron", "1,624", (
                "Ballots Cast - Total", "2,885 native registered voters", "56.29%",
                "UNOFFICIAL RESULTS", "summary: 11/03/2026 9:13 PM", "timezone not declared",
                "zero complete and ten partially reported", "provisional participation is absent, not zero",
                "returned 324 / recorded 320 are not counted Mail 319", "Federal Voter filter",
                "12:01 link label does not supply one", "Not Assigned is nested within Write-In Totals")),
            ("42025", "Carbon", "24,840", (
                "Voters Cast", "45,896 native registered voters", "54.12%", "Unofficial Results",
                "summary: 11/3/2026 10:36:36 PM", "zero: 11/3/2026 7:05:24 PM",
                "statement: 11/3/2026 10:19:13 PM", "timezone not declared", "explicit zero Provisional",
                "Official Zero Report is a separate observation", "Kidder referendum Times Cast 807/1,457",
                "Mode-specific registrations and native overvotes/undervotes are absent",
                "350/381/288/30 participation-minus-choice residuals remain unclassified")),
            ("42047", "Elk", "11,742", (
                "Ballots Cast - Total", "20,533 native registered voters", "57.19%",
                "UNOFFICIAL RESULTS", "summary: 11/03/2026 22:08 PM", "timezone not declared",
                "2,017 Absentee/Mail-In + explicit zero Provisional",
                "All 29 units are partially reported and zero complete",
                "ST MARYS 4TH prints 55.10%", "319/579 fraction rounds to 55.09%",
                "returned 2,035 / recorded 2,018 are not counted mail 2,017",
                "differences 18/1 remain unexplained", "Act88 scan is visually reviewed")),
            ("42053", "Forest", "1,877", (
                "Ballots Cast - Total", "3,275 native registered voters", "57.31%",
                "UNOFFICIAL RESULTS", "summary: 11/03/2026 20:56 PM", "timezone not declared",
                "physical summary page 2", "physical page 1 prints Page 2 of 2",
                "All nine units are partially reported and zero complete",
                "mail and provisional participation are absent, not zero",
                "311 mail-in absentee receipts", "both full text engines are empty",
                "derived residuals remain unclassified")),
        ):
            page.locator(f".substate-feature[data-geography='{geoid}']").dispatch_event("click")
            expect(page.locator("#current-county-select")).to_have_value(f"reviewed:PA:{county}")
            expect(detail.locator(".selection-rate")).to_have_text(count)
            for text in texts:
                expect(detail).to_contain_text(text)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    return counts, rates


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for mobile in (False, True):
        context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 1000},
                                      is_mobile=mobile, has_touch=mobile)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url(), wait_until="domcontentloaded")
        for item in baseline["unchanged_imports"]:
            response = context.request.get(base + "/" + item["path"])
            assert response.ok
            body = gzip.decompress(response.body())
            assert len(body) == item["json_bytes"] and hashlib.sha256(body).hexdigest() == item["json_sha256"]
        totals = [0, 0]
        for code, name in names.items():
            page.locator("#state-select").select_option(label=name)
            expect(page.locator("#show-current-counties")).to_be_visible(timeout=30000)
            page.locator("#show-current-counties").click()
            counts, rates = check_counties(page, code)
            totals[0] += counts; totals[1] += rates
        assert totals == [436, 64]
        page.locator("#state-select").select_option(label="Vermont")
        expect(page.locator("#current-county-select option")).to_have_count(248)
        expect(page.locator("#geography-note")).to_contain_text("no whole-county participation joins are approved", timeout=30000)
        expect(page.locator(".substate-feature[data-context-review='20261106-05']")).to_have_count(0)
        page.locator("#state-select").select_option(label="New Jersey")
        page.locator("#show-current-counties").click()
        check_counties(page, "NJ")
        page.locator(".substate-feature[data-geography='34009']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:NJ:Cape May")
        expect(page.locator("#current-county-detail")).to_contain_text("76,899 native registered voters")
        expect(page.locator("#current-county-detail")).to_contain_text("attached summary, PDF page 2")
        page.locator('button[aria-controls="methods-panel"]').click()
        check_static(page)
        modes.append(dict(mobile=mobile, javascript=True, complete_native_records_unchanged=906,
                          complete_current_native_records=908, new_elk_forest_native_records_verified=True,
                          previous_jefferson_clarion_cameron_carbon_selection_preserved=True,
                          exact_county_count_matches=436, exact_county_rate_fills=64, missing_rates_gray=372,
                          complete_imports_unchanged=18, excluded_municipalities=286,
                          excluded_missing_county_containers=186, previous_download_anchors_preserved=sum(old_links.values()),
                          download_anchors=sum(links.values()),
                          unique_download_urls=len(links), horizontal_overflow=False))
        context.close()
        context = browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 1000},
                                      java_script_enabled=False)
        page = context.new_page(); page.goto(url(), wait_until="domcontentloaded")
        check_static(page)
        modes.append(dict(mobile=mobile, javascript=False, complete_downloads_preserved=True,
                          all_previous_reviewed_records_unchanged=True, horizontal_overflow=False))
        context.close()
    for scenario in ("failed-review", "changed-review", "failed-current"):
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        if scenario == "failed-current":
            page.route("**/participation-current/**", lambda route: route.abort())
        else:
            page.route("**/participation-county-context/20261106-05/review.json",
                       lambda route: route.fulfill(status=503 if scenario == "failed-review" else 200,
                                                   content_type="application/json", body='{"changed":true}'))
        page.goto(url("Pennsylvania"), wait_until="domcontentloaded")
        page.locator("#show-current-counties").click()
        if scenario == "failed-current":
            assert check_counties(page, "PA") == (23, 22)
        else:
            expect(page.locator("#geography-note")).to_contain_text(
                "Independently reviewed county joins are withheld", timeout=30000)
            expect(page.locator(".substate-feature[data-context-review='20261106-05']")).to_have_count(0)
            page.locator("#current-county-select").select_option("reviewed:PA:Clarion")
            expect(page.locator("#current-county-detail .selection-rate")).to_have_text("12,975")
        failures.append(dict(scenario=scenario, source_counts_preserved=True,
                             invalid_review_never_approves_join=scenario != "failed-current"))
        context.close()
    browser.close()
assert not errors, errors
args.proof.write_text(json.dumps(dict(
    base_url=base, verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    modes=modes, failure_scenarios=failures, expected_download_urls=sorted(links.elements()),
    original_flags_and_missing_rates_unchanged=True, no_native_fips_or_new_rates_invented=True), indent=2) + "\n")
print(json.dumps(dict(modes=modes, failure_scenarios=failures), indent=2))

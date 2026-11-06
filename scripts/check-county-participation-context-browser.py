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
facts = root / "public/participation-county-context/20261106-14"
review = json.loads((facts / "review.json").read_text())
records = json.loads(gzip.decompress((facts / "complete-source-records.json.gz").read_bytes()))
pointer = json.loads((root / "public/participation-county-context.json").read_text())
previous = root / "data/county-source-reviews/20261106-lycoming-explorer-01"
baseline = json.loads((previous / "baseline.json").read_text())
sources = [row for row in json.loads((root / "public/participation-source-reviews.json").read_text())["reviews"]
           if row["id"] == "pennsylvania-lycoming-20261106-01"]
assert len(sources) == 1
source_ids = {row["id"] for row in sources}
old_links = Counter(baseline["previous_download_urls"])
links = old_links + Counter(row["url"] for row in pointer["downloads"] if row["url"] not in old_links)
for source in sources:
    links += Counter([source["complete_download_url"]] + [source["base_url"] + row["file"] for row in source["tables"]])
names = dict(AL="Alabama", AR="Arkansas", AZ="Arizona", CA="California", DC="District of Columbia",
             FL="Florida", GA="Georgia", IA="Iowa", KY="Kentucky", MO="Missouri", NJ="New Jersey",
             NV="Nevada", OR="Oregon", PA="Pennsylvania", VA="Virginia",
             WA="Washington", WY="Wyoming")
errors, modes, failures = [], [], []


def url(name="Washington"):
    return base + "/voter-participation/?year=2026&view=states&mode=available&map-level=county&map-color=turnout&state=" + name.replace(" ", "%20")


def check_static(page):
    observed = json.loads(page.locator("table[data-reviewed-county-participation]").get_attribute("data-reviewed-county-participation"))
    assert observed == records[-269:]
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
    statewide = json.loads(page.locator("[data-reviewed-state-participation]").get_attribute("data-reviewed-state-participation"))
    assert len(statewide) == 2
    assert statewide[0]["geography_level"] == "statewide"
    assert statewide[0]["ballots"] == 8928966 and statewide[0]["denominator"] == 23273590
    assert statewide[0]["native_record"]["native_county_code"] == "59"
    expect(page.locator("[data-reviewed-state-participation]")).to_contain_text("8,928,966 voterTurnout / 23,273,590 totalRegisteredVoters")
    assert statewide[1]["ballots"] == 4210155 and statewide[1]["validated_pct"] is None
    assert statewide[1]["native_record"]["original_conflicting_api_root_ballots"] == "0"
    expect(page.locator("[data-reviewed-state-participation]")).to_contain_text("4,210,155 Ballots Cast / 7,516,484 Voters")
    expect(page.locator("[data-reviewed-state-participation]")).to_contain_text("not used as an analysis rate")
    for county in ("Screven County", "Jeff Davis County"):
        row = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
            has=page.locator("th", has_text=county))
        expect(row).to_contain_text("Withheld (native zero)")
        expect(row.locator("td").nth(2)).to_have_text("Withheld")
        expect(row.locator("td").nth(3)).to_have_text("Not supplied")
    expect(page.locator("#county-context-review")).to_contain_text("662 whole-county participation observations")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def check_statewide(page):
    page.locator("#mode").select_option("uf_vep")
    observed = page.locator("#official-state-counts")
    expect(observed).to_contain_text("8,928,966 Native voterTurnout (reported participation)")
    expect(observed).to_contain_text("23,273,590")
    expect(observed).to_contain_text("38.4%")
    expect(observed).to_contain_text("Not the UF population denominator")
    page.locator("#mode").select_option("official")
    expect(page.locator("#selection-panel > .selection-rate")).to_have_text("38.4%")
    expect(page.locator("#selection-panel")).to_contain_text("8,928,966 Native voterTurnout")
    expect(page.locator("#selection-panel")).to_contain_text("native registered voters (23,273,590)")
    expect(page.locator("#selection-panel")).to_contain_text("not CVAP, VAP, VEP, CPS or demographic turnout")
    page.locator("#mode").select_option("uf_vep")
    expect(page.locator("#official-state-counts")).to_contain_text("8,928,966 Native voterTurnout")


def check_georgia_statewide(page):
    page.locator("#mode").select_option("uf_vep")
    observed = page.locator("#official-state-counts")
    expect(observed).to_contain_text("4,210,155 Native Ballots Cast (reported ballots)")
    expect(observed).to_contain_text("Printed statewide 56.01% is retained, not an approved analysis rate")
    expect(observed).to_contain_text("two county registration denominators are missing")
    page.locator("#mode").select_option("official")
    expect(page.locator("#selection-panel > .selection-rate")).to_have_text("4,210,155")
    expect(page.locator("#selection-panel")).to_contain_text("Original API root ballotsCast=0")
    expect(page.locator("#selection-panel")).to_contain_text("not CVAP, VAP, VEP, CPS or demographic turnout")
    page.locator("#mode").select_option("uf_vep")


def check_counties(page, code):
    expected = {row["contextual_geoid"]: row for row in review["observations"] if row["state_code"] == code}
    expect(page.locator(".substate-feature[data-context-review='20261106-14']")).to_have_count(len(expected), timeout=30000)
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
        assert path["data-context-review"] == "20261106-14"
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
    if code == "CA":
        page.locator(".substate-feature[data-geography='06001']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:CA:1")
        detail = page.locator("#current-county-detail")
        expect(detail.locator(".selection-rate")).to_have_text("314,951")
        for text in ("voterTurnout", "983,846 native registered voters", "32.01%",
                     "reportType: U; reportTypeCode: U", "202611040219", "timezone not declared",
                     "does not establish completed counting or certification",
                     "not CVAP, VAP, VEP, CPS or demographic turnout"):
            expect(detail).to_contain_text(text)
    if code == "GA":
        for geoid, county, ballots in (("13251", "Screven County", 5236), ("13161", "Jeff Davis County", 4180)):
            page.locator(f".substate-feature[data-geography='{geoid}']").dispatch_event("click")
            native = expected[geoid]
            expect(page.locator("#current-county-select")).to_have_value(native["county_id"])
            detail = page.locator("#current-county-detail")
            expect(detail.locator(".selection-rate")).to_have_text(f"{ballots:,}")
            expect(detail).to_contain_text("ballotsCast")
            expect(detail).to_contain_text("blank rates, not zero turnout")
            expect(detail).to_contain_text("not completed counting or certification")
            path = page.locator(f".substate-feature[data-geography='{geoid}']")
            assert path.get_attribute("data-rate") == "" and path.get_attribute("fill") == "#edf0f3"
        page.locator(".substate-feature[data-geography='13319']").dispatch_event("click")
        expect(page.locator("#current-county-detail")).to_contain_text("Native isOfficialResults=true")
    if code == "PA":
        page.locator(".substate-feature[data-geography='42081']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:PA:Lycoming")
        detail = page.locator("#current-county-detail")
        expect(detail.locator(".selection-rate")).to_have_text("40,596")
        for text in ("Total Ballots Cast", "73,009 native registered voters", "55.60%",
                     "Unofficial Results", "2026-11-05 10:37:43", "timezone not declared",
                     "80 of 80 reporting is not completed counting",
                     "ED/MI/PR are candidate-vote columns",
                     "5,770 Act88 mail receipts are not added", "weekday/date conflict is retained",
                     "parties are missing and are not inferred"):
            expect(detail).to_contain_text(text)
        path = page.locator(".substate-feature[data-geography='42081']")
        assert math.isclose(float(path.get_attribute("data-rate")), 100 * 40596 / 73009)
        assert path.get_attribute("fill") != "#edf0f3"
        page.locator(".substate-feature[data-geography='42059']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:PA:Greene")
        detail = page.locator("#current-county-detail")
        expect(detail.locator(".selection-rate")).to_have_text("11,105")
        for text in ("Ballots Cast - Total", "Unofficial Results with MI and Absentee",
                     "Registrations and the turnout rate are not supplied, not zero",
                     "five blank ballots", "not added to the total",
                     "42 of 42 reported precincts does not establish completed counting",
                     "No report-update clock or timezone is supplied"):
            expect(detail).to_contain_text(text)
        path = page.locator(".substate-feature[data-geography='42059']")
        assert path.get_attribute("data-rate") == ""
        assert path.get_attribute("fill") == "#edf0f3"
        page.locator(".substate-feature[data-geography='42037']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:PA:Columbia")
        detail = page.locator("#current-county-detail")
        expect(detail.locator(".selection-rate")).to_have_text("22,583")
        for text in ("Total Ballots", "40,797 native registered voters", "55.35%",
                     "11/3/2026 10:37:16 PM EST", "UNOFFICIAL ELECTION RESULTS",
                     "mail returned 3,785 and votes recorded 3,772",
                     "no Election Day remainder is inferred", "registration parties are not candidate parties"):
            expect(detail).to_contain_text(text)
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
            ("42087", "Mifflin", "14,439", (
                "Ballots Cast - Total", "UNOFFICIAL RESULTS",
                "summary: 11/03/2026 09:28PM", "statement: 11/03/2026 09:26PM",
                "timezone not declared", "12,017 Election Day + 2,422 Mail + explicit zero Provisional",
                "six blank ballots are already included", "calculated registration-based rate is unavailable",
                "All 26 units are partially reported and zero complete",
                "4,409/10,030-ballot subsets", "Primary Election Day, November 3, 2026",
                "2,435 receipts are not counted mail 2,422", "difference 13 remains unexplained")),
            ("42099", "Perry", "18,064", (
                "Total Ballots Cast", "31,391 native registered voters", "57.55%", "Unofficial",
                "summary: 2026-11-03 22:49:06", "statement: 2026-11-03 22:30:24",
                "timezone not declared", "four All Precincts aggregate headers are separate",
                "31 of 31 reported precincts does not establish completed ballot counting",
                "zero PR votes do not establish zero provisional ballots",
                "unresolved unit candidate cells are explicitly outside this query",
                "Native party labels are absent and not inferred",
                "Unofficial status comes from the declaring county page")),
            ("42067", "Juniata", "8,258", (
                "Ballots Cast - Total", "14,095 native registered voters", "58.59%",
                "UNOFFICIAL RESULTS", "summary: 11/03/2026 10:31 PM",
                "statement: 11/03/2026 10:34 PM", "timezone not declared",
                "1,977/6,281 ballots", "zero complete and 18 partially reported",
                "1,098 Mail Votes", "blank ballots are already included")),
            ("42085", "Mercer", "39,121", (
                "Ballots Cast - Total", "72,238 native registered voters", "54.16%",
                "UNOFFICIAL RESULTS", "summary: 11/05/2026 11:05 AM",
                "statement: 11/05/2026 11:07 AM", "timezone not declared",
                "7,178 native Absentee", "overvotes and undervotes are absent",
                "16,437/22,684 ballots", "Sandy Lake Borough question has 226 ballots",
                "Mill Creek Township prints 58.36%", "307/526 rounds to 58.37%")),
            ("42093", "Montour", "7,008", (
                "Ballots Cast - Total", "12,418 native registered voters", "56.43%",
                "UNOFFICIAL RESULTS", "summary: 11/05/2026 10:14AM",
                "statement: 11/05/2026 10:16AM", "timezone not declared",
                "25 Provisional Votes", "zero complete and 15 partial overall",
                "Election Day complete 15", "No counter is repaired into completed counting")),
            ("42105", "Potter", "6,244", (
                "Ballots Cast - Total", "11,041 native registered voters", "56.55%",
                "UNOFFICIAL RESULTS", "summary: 11/04/2026 2:44 PM",
                "statement: 11/04/2026 2:45 PM", "timezone not declared",
                "5,389 Election Day + 855 Mail + explicit zero Provisional",
                "two blank ballots are already included", "All 32 units are partially reported and zero complete",
                "Election Day complete column nevertheless says 32",
                "871 mail-in/absentee receipts", "not counted mail 855",
                "difference 16 remains unexplained and unallocated",
                "unit named breakdowns are absent, not zero",
                "Total Votes Cast and Contest Totals rows are absent")),
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
            body = response.body()
            if body.startswith(b"\x1f\x8b"):
                body = gzip.decompress(body)
            assert len(body) == item["json_bytes"] and hashlib.sha256(body).hexdigest() == item["json_sha256"]
        totals = [0, 0]
        for code, name in names.items():
            page.locator("#state-select").select_option(label=name)
            expect(page.locator("#show-current-counties")).to_be_visible(timeout=30000)
            page.locator("#show-current-counties").click()
            counts, rates = check_counties(page, code)
            if code == "CA":
                check_statewide(page)
            if code == "GA":
                check_georgia_statewide(page)
            totals[0] += counts; totals[1] += rates
        assert totals == [662, 286]
        page.locator("#state-select").select_option(label="Vermont")
        expect(page.locator("#current-county-select option")).to_have_count(248)
        expect(page.locator("#geography-note")).to_contain_text("no whole-county participation joins are approved", timeout=30000)
        expect(page.locator(".substate-feature[data-context-review='20261106-14']")).to_have_count(0)
        page.locator("#state-select").select_option(label="New Jersey")
        page.locator("#show-current-counties").click()
        check_counties(page, "NJ")
        page.locator(".substate-feature[data-geography='34009']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:NJ:Cape May")
        expect(page.locator("#current-county-detail")).to_contain_text("76,899 native registered voters")
        expect(page.locator("#current-county-detail")).to_contain_text("attached summary, PDF page 2")
        page.locator('button[aria-controls="methods-panel"]').click()
        check_static(page)
        modes.append(dict(mobile=mobile, javascript=True, complete_native_records_unchanged=1133,
                          complete_current_native_records=1134, lycoming_native_participation_verified=True,
                          all_58_california_native_records_verified=True,
                          all_159_georgia_native_records_verified=True, two_georgia_missing_rates_gray=True,
                          greene_native_count_missing_denominator_and_clock_verified=True,
                          columbia_native_participation_and_separate_mail_qualifications_verified=True,
                          separate_native_statewide_count_and_registered_fraction_verified=True,
                          previous_jefferson_clarion_cameron_carbon_elk_forest_selection_preserved=True,
                          exact_county_count_matches=662, exact_county_rate_fills=286, missing_rates_gray=376,
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
            page.route("**/participation-county-context/20261106-14/review.json",
                       lambda route: route.fulfill(status=503 if scenario == "failed-review" else 200,
                                                   content_type="application/json", body='{"changed":true}'))
        page.goto(url("Pennsylvania"), wait_until="domcontentloaded")
        page.locator("#show-current-counties").click()
        if scenario == "failed-current":
            assert check_counties(page, "PA") == (32, 29)
            page.locator("#state-select").select_option(label="California")
            page.locator("#show-current-counties").click()
            assert check_counties(page, "CA") == (58, 58)
            check_statewide(page)
            page.locator("#state-select").select_option(label="Georgia")
            page.locator("#show-current-counties").click()
            assert check_counties(page, "GA") == (159, 157)
            check_georgia_statewide(page)
        else:
            expect(page.locator("#geography-note")).to_contain_text(
                "Independently reviewed county joins are withheld", timeout=30000)
            expect(page.locator(".substate-feature[data-context-review='20261106-13']")).to_have_count(0)
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

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
facts = root / "public/participation-county-context/20261106-01"
review = json.loads((facts / "review.json").read_text())
records = json.loads(gzip.decompress((facts / "complete-source-records.json.gz").read_bytes()))
pointer = json.loads((root / "public/participation-county-context.json").read_text())
previous = root / "data/county-source-reviews/20261106-nj-participation-publication-02"
baseline = json.loads((previous / "baseline.json").read_text())
old_browser = json.loads((previous / "production-browser.json").read_text())
links = Counter(old_browser["expected_download_urls"]) + Counter(row["url"] for row in pointer["downloads"])
names = dict(AL="Alabama", AR="Arkansas", AZ="Arizona", DC="District of Columbia",
             FL="Florida", IA="Iowa", KY="Kentucky", MO="Missouri", NJ="New Jersey",
             NV="Nevada", OR="Oregon", PA="Pennsylvania", VA="Virginia",
             WA="Washington", WY="Wyoming")
errors, modes, failures = [], [], []


def url(name="Washington"):
    return base + "/voter-participation/?year=2026&view=states&mode=available&map-level=county&map-color=turnout&state=" + name.replace(" ", "%20")


def check_static(page):
    observed = json.loads(page.locator("table[data-reviewed-county-participation]").get_attribute("data-reviewed-county-participation"))
    assert observed == records[-37:]
    expect(page.locator('table[data-uf-turnout="2026"] tbody tr')).to_have_count(52)
    assert [cell.strip() for cell in page.locator("table[data-historical-house] tbody tr th").all_text_contents()] == baseline["historical_years"]
    actual = Counter(page.locator("#downloads a[download]").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))"))
    assert actual == links
    expect(page.locator("#county-context-review")).to_contain_text("430 whole-county participation observations")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def check_counties(page, code):
    expected = {row["contextual_geoid"]: row for row in review["observations"] if row["state_code"] == code}
    expect(page.locator(".substate-feature[data-context-review='20261106-01']")).to_have_count(len(expected), timeout=30000)
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
        assert path["data-context-review"] == "20261106-01"
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
        assert totals == [430, 58]
        page.locator("#state-select").select_option(label="Vermont")
        expect(page.locator("#current-county-select option")).to_have_count(248)
        expect(page.locator("#geography-note")).to_contain_text("no whole-county participation joins are approved", timeout=30000)
        expect(page.locator(".substate-feature[data-context-review='20261106-01']")).to_have_count(0)
        page.locator("#state-select").select_option(label="New Jersey")
        page.locator("#show-current-counties").click()
        check_counties(page, "NJ")
        page.locator(".substate-feature[data-geography='34009']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:NJ:Cape May")
        expect(page.locator("#current-county-detail")).to_contain_text("76,899 native registered voters")
        expect(page.locator("#current-county-detail")).to_contain_text("attached summary, PDF page 2")
        page.locator('button[aria-controls="methods-panel"]').click()
        check_static(page)
        modes.append(dict(mobile=mobile, javascript=True, complete_native_records_unchanged=902,
                          exact_county_count_matches=430, exact_county_rate_fills=58, missing_rates_gray=372,
                          complete_imports_unchanged=18, excluded_municipalities=286,
                          excluded_missing_county_containers=186, previous_download_anchors_preserved=367,
                          download_anchors=371, unique_download_urls=368, horizontal_overflow=False))
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
            page.route("**/participation-county-context/20261106-01/review.json",
                       lambda route: route.fulfill(status=503 if scenario == "failed-review" else 200,
                                                   content_type="application/json", body='{"changed":true}'))
        page.goto(url("New Jersey"), wait_until="domcontentloaded")
        page.locator("#show-current-counties").click()
        if scenario == "failed-current":
            assert check_counties(page, "NJ") == (19, 1)
        else:
            expect(page.locator("#geography-note")).to_contain_text(
                "Independently reviewed county joins are withheld", timeout=30000)
            expect(page.locator(".substate-feature[data-context-review='20261106-01']")).to_have_count(0)
            page.locator("#current-county-select").select_option("reviewed:NJ:Bergen")
            expect(page.locator("#current-county-detail .selection-rate")).to_have_text("319,503")
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

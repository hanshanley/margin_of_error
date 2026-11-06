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
facts = root / "public/participation-county-context/20261106-25"
review = json.loads((facts / "review.json").read_text())
records = json.loads(gzip.decompress((facts / "complete-source-records.json.gz").read_bytes()))
pointer = json.loads((root / "public/participation-county-context.json").read_text())
previous = root / "data/county-source-reviews/20261106-wisconsin-rock-explorer-01"
baseline = json.loads((previous / "baseline.json").read_text())
sources = [row for row in json.loads((root / "public/participation-source-reviews.json").read_text())["reviews"]
           if row["id"] == "wisconsin-rock-turnout-20261106-01"]
assert len(sources) == 1
source_ids = {row["id"] for row in sources}
old_links = Counter(baseline["previous_download_urls"])
links = old_links + Counter(row["url"] for row in pointer["downloads"] if row["url"] not in old_links)
for source in sources:
    links += Counter([source["complete_download_url"]] + [source["base_url"] + row["file"] for row in source["tables"]])
for pointer_file, tables in (
    ("uf-turnout.json", ("turnout.csv", "originals/turnout.csv", "originals/documentation.txt")),
    ("county-results.json", ("county-results.csv", "county-results.json.gz")),
):
    source_pointer = json.loads((root / "public" / pointer_file).read_text())
    for snapshot in [source_pointer, *source_pointer.get("previous_snapshots", [])]:
        if snapshot["complete_download_url"] not in old_links:
            links += Counter([snapshot["complete_download_url"]]
                             + [snapshot["base_url"] + table for table in tables])
            if pointer_file == "county-results.json" and snapshot.get("party_votes"):
                party = snapshot["party_votes"]
                links += Counter([party["complete_download_url"]]
                                 + [party["base_url"] + table["file"] for table in party["tables"]])
names = dict(AL="Alabama", AR="Arkansas", AZ="Arizona", CA="California", DC="District of Columbia",
             FL="Florida", GA="Georgia", IA="Iowa", KY="Kentucky", MN="Minnesota", MO="Missouri", NJ="New Jersey",
             NV="Nevada", OR="Oregon", PA="Pennsylvania", UT="Utah", VA="Virginia",
             WA="Washington", WI="Wisconsin", WY="Wyoming")
errors, modes, failures = [], [], []


def url(name="Washington"):
    return base + "/voter-participation/?year=2026&view=states&mode=available&map-level=county&map-color=turnout&state=" + name.replace(" ", "%20")


def check_static(page):
    observed = json.loads(page.locator("table[data-reviewed-county-participation]").get_attribute("data-reviewed-county-participation"))
    assert observed == records[-464:]
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
    native_mn = [row for row in observed if row["review_id"] == "minnesota-bulk-participation-20261106-01"]
    assert len(native_mn) == 87 and sum(row["ballots"] is None for row in native_mn) == 12
    for native in native_mn:
        row = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
            has=page.get_by_role("rowheader", name=native["county"] + ", Minnesota",
                                 exact=True, include_hidden=True))
        expect(row).to_have_count(1)
        if native["ballots"] is None:
            expect(row.locator("td").nth(0)).to_contain_text("Not supplied (incomplete native statistics)")
            expect(row.locator("td").nth(1)).to_have_text("Not supplied")
        else:
            expect(row.locator("td").nth(0)).to_contain_text(f"{native['ballots']:,}")
        if native["reported_pct"] is None:
            expect(row.locator("td").nth(2)).to_have_text("Withheld")
    checksum = page.locator("#downloads a", has_text="Minnesota: complete native participation statistics").filter(
        has_text="complete data and original-source checksums")
    mn_source = next(row for row in json.loads(
        (root / "public/participation-source-reviews.json").read_text())["reviews"]
        if row["id"] == "minnesota-bulk-participation-20261106-01")
    assert checksum.get_attribute("href") == mn_source["base_url"] + "checksums.sha256"
    lawrence = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
        has=page.get_by_role("rowheader", name="Lawrence, Pennsylvania", exact=True, include_hidden=True))
    for text in ("31,401", "57,470", "54.64%", "UNOFFICIAL RESULTS"):
        expect(lawrence).to_contain_text(text)
    huntingdon = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
        has=page.get_by_role("rowheader", name="Huntingdon, Pennsylvania", exact=True, include_hidden=True))
    for text in ("16,024", "27,917", "57.40%", "UNOFFICIAL RESULTS"):
        expect(huntingdon).to_contain_text(text)
    for county, texts in (
        ("Indiana", ("28,095", "49,255", "57.04%")),
        ("Lackawanna", ("87,067", "151,015", "57.65%")),
        ("Schuylkill", ("48,402", "92,875", "52.12%")),
    ):
        row = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
            has=page.get_by_role("rowheader", name=f"{county}, Pennsylvania", exact=True, include_hidden=True))
        for text in (*texts, "UNOFFICIAL RESULTS"):
            expect(row).to_contain_text(text)
    somerset = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
        has=page.get_by_role("rowheader", name="Somerset, Pennsylvania", exact=True, include_hidden=True))
    for text in ("27,019", "48,578", "55.62%", "UNOFFICIAL RESULTS"):
        expect(somerset).to_contain_text(text)
    susquehanna = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
        has=page.get_by_role("rowheader", name="Susquehanna, Pennsylvania", exact=True, include_hidden=True))
    for text in ("15,317", "27,504", "55.69%", "UNOFFICIAL RESULTS"):
        expect(susquehanna).to_contain_text(text)
    for county, texts in (
        ("Sullivan", ("2,712", "4,501", "60.25%", "UNOFFICIAL Election Results")),
        ("Wyoming", ("10,542", "18,565", "56.78%", "Unofficial (source file name; not printed PDF status)")),
    ):
        row = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
            has=page.get_by_role("rowheader", name=f"{county}, Pennsylvania", exact=True, include_hidden=True))
        for text in texts:
            expect(row).to_contain_text(text)
    for county, texts in (
        ("Bedford", ("19,041", "33,079", "57.56%", "Unofficial")),
        ("Northumberland", ("28,341", "55,540", "51.03%", "UNOFFICIAL RESULTS")),
    ):
        row = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
            has=page.get_by_role("rowheader", name=f"{county}, Pennsylvania", exact=True, include_hidden=True))
        for text in texts:
            expect(row).to_contain_text(text)
    for county in ("Cache", "Garfield", "Iron", "Kane", "Millard", "San Juan"):
        row = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
            has=page.get_by_role("rowheader", name=f"{county} County, Utah", exact=True, include_hidden=True))
        expect(row.locator("td").nth(0)).to_contain_text("Withheld (native counting scope)")
        expect(row.locator("td").nth(2)).to_have_text("Withheld")
    for county in ("Daggett", "Morgan", "Piute", "Wasatch"):
        row = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
            has=page.get_by_role("rowheader", name=f"{county} County, Utah", exact=True, include_hidden=True))
        expect(row.locator("td").nth(0)).to_contain_text("Not supplied (no declared county report)")
    florida = [row for row in observed if row["review_id"] == "florida-consolidated-turnout-20261106-01"]
    assert len(florida) == 67
    for native in florida:
        row = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
            has=page.get_by_role("rowheader", name=f"{native['county']}, Florida", exact=True, include_hidden=True))
        expect(row.locator("td").nth(0)).to_contain_text(f"{native['ballots']:,}")
        expect(row.locator("td").nth(1)).to_contain_text(f"{native['denominator']:,}")
        expect(row.locator("td").nth(2)).to_contain_text(f"{native['reported_pct']:.2f}%")
        expect(row.locator("td").nth(3)).to_contain_text(native["native_printed_pct"])
        assert native["native_source_updates"] == []
    rock = page.locator("table[data-reviewed-county-participation] tbody tr").filter(
        has=page.get_by_role("rowheader", name="Rock County, Wisconsin", exact=True, include_hidden=True))
    for text in ("67,812", "97,950", "69.23%"):
        expect(rock).to_contain_text(text)
    for text in ("November 03, 2026 at 10:56 PM has no declared timezone",
                 "Not statewide Wisconsin coverage, final unique voters, certified or proven complete all-mode counting"):
        expect(page.locator("main")).to_contain_text(text)
    expect(page.locator("#county-context-review")).to_contain_text("834 whole-county participation observations")
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
    expect(page.locator(".substate-feature[data-context-review='20261106-25']")).to_have_count(len(expected), timeout=30000)
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
        assert path["data-context-review"] == "20261106-25"
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
    if code == "MN":
        for native in [row for row in records if row["review_id"] == "minnesota-bulk-participation-20261106-01"]:
            if native["ballots"] is None or native["reported_pct"] is None:
                page.locator("#current-county-select").select_option(native["county_id"])
                detail = page.locator("#current-county-detail")
                expect(detail.locator(".selection-rate")).to_have_text(
                    "—" if native["ballots"] is None else f"{native['ballots']:,}")
                expect(detail).to_contain_text("Analysis fraction withheld / not supplied")
                if native["ballots"] is None:
                    expect(detail).to_contain_text("County total not supplied · incomplete native statistics")
                    expect(detail).to_contain_text("partial subtotal is not the county total")
                else:
                    expect(detail).to_contain_text("native component conflicts")
        page.locator("#current-county-select").select_option(sample["county_id"])
        detail = page.locator("#current-county-detail")
        for text in ("Total Number Voted", "native registered voters", "7AM registrations",
                     "Election Day registrations", "not CVAP, VAP, VEP, CPS or demographic turnout",
                     "fetch receipts are not report updates", "not inferred ballot modes"):
            expect(detail).to_contain_text(text)
    if code == "FL":
        native_rows = [row for row in records if row["review_id"] == "florida-consolidated-turnout-20261106-01"]
        assert len(native_rows) == 67 and (counts, rates) == (67, 67)
        options = page.locator("#current-county-select option").evaluate_all(
            "rows => rows.map(row => row.value).filter(Boolean)")
        assert len(options) == 67 and set(options) == {row["county_id"] for row in native_rows}
        assert "additional:FL:12087" not in options
        for native in native_rows:
            page.locator("#current-county-select").select_option(native["county_id"])
            detail = page.locator("#current-county-detail")
            expect(detail.locator(".selection-rate")).to_have_text(f"{native['ballots']:,}")
            for text in ("Eligible Active Registered Voters", native["source_update_label"],
                         native["native_printed_pct"], f"{native['denominator']:,} native registered voters",
                         "not certification or proof of finished counting",
                         f"Reviewed fraction from these counts: {native['reported_pct']:.2f}%"):
                expect(detail).to_contain_text(text)
            for key, value in native["native_record"].items():
                if key.endswith("_completed"):
                    expect(detail).to_contain_text(f"{key}={value}")
        retained = next(row for row in records if row["county_id"] == "additional:FL:12087")
        assert retained["reported_pct"] is None and retained["ballots"] == 32506
        assert len(review["source_selections"]) == 1
        assert any(row["county_id"] == retained["county_id"] for row in review["excluded"])
    if code == "WI":
        assert (counts, rates, len(actual)) == (1, 1, 72)
        options = page.locator("#current-county-select option").evaluate_all(
            "rows => rows.map(row => row.value).filter(Boolean)")
        assert options == ["reviewed:WI:Rock County"]
        page.locator(".substate-feature[data-geography='55105']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:WI:Rock County")
        detail = page.locator("#current-county-detail")
        expect(detail.locator(".selection-rate")).to_have_text("67,812")
        for text in ("Ballots Cast", "97,950 native registered voters", "69.23%",
                     "November 03, 2026 at 10:56 PM", "timezone not declared",
                     "not certification, final counting or proof of complete all-mode coverage",
                     "Governor selections 67418 are not the 67812 Ballots Cast count",
                     "not CVAP, VAP, VEP, CPS or demographic turnout"):
            expect(detail).to_contain_text(text)
    if code == "UT":
        native_rows = [row for row in records if row["review_id"] == "utah-ballot-statistics-20261106-01"]
        assert len(native_rows) == 29 and (counts, rates) == (19, 18)
        for native in native_rows:
            page.locator("#current-county-select").select_option(native["county_id"])
            detail = page.locator("#current-county-detail")
            expect(detail.locator(".selection-rate")).to_have_text(
                "—" if native["ballots"] is None else f"{native['ballots']:,}")
            expect(detail).to_contain_text(native["source_update_label"])
            expect(detail).to_contain_text(native["quality"][-1])
            if native["ballots"] is None:
                scope = native["native_record"]["source_scope_review"]
                expect(detail).to_contain_text("native counting scope unresolved" if scope.startswith("withheld_")
                                               else "no declared county report")
            if native["reported_pct"] is None:
                expect(detail).to_contain_text("Analysis fraction withheld / not supplied")
            else:
                expect(detail).to_contain_text(f"Reviewed fraction from these counts: {native['reported_pct']:.2f}%")
            if native["county"] in ("Juab County", "Tooele County"):
                expect(detail).to_contain_text("Approx # Active Registered Voters")
            if native["county"] == "Wayne County":
                for text in ("1109 counted versus 1209 credited", "100 discrepancy", "no source clock"):
                    expect(detail).to_contain_text(text)
            if native["county"] == "Uintah County":
                expect(detail).to_contain_text("11/03/2026 11:18 a.m. (timezone not declared)")
                expect(detail).to_contain_text("Do not promote the upload time to the numerical cutoff")
    if code == "PA":
        for geoid, county, ballots, registrations, printed, measure, clock, qualification in (
            ("42009", "Bedford", 19041, 33079, "57.56%", "Voters Cast",
             "11/3/2026 9:53:30 PM", "unresolved write-ins 8/23/34/339; do not add them again"),
            ("42097", "Northumberland", 28341, 55540, "51.03%", "Ballots Cast - Total",
             "11/03/2026 22:18 PM", "9,450 Contest Totals / 5,588 Total Votes Cast are not county ballots or unique city voters"),
        ):
            path = page.locator(f".substate-feature[data-geography='{geoid}']")
            path.dispatch_event("click")
            expect(page.locator("#current-county-select")).to_have_value(f"reviewed:PA:{county}")
            detail = page.locator("#current-county-detail")
            expect(detail.locator(".selection-rate")).to_have_text(f"{ballots:,}")
            for text in (measure, f"{registrations:,} native registered voters", printed, clock,
                         "timezone not declared", "not candidate selections", qualification,
                         "not CVAP, VAP, VEP, CPS or demographic turnout",
                         "do not establish completed counting or certification",
                         "does not certify 2026 election reporting boundaries"):
                expect(detail).to_contain_text(text)
            assert math.isclose(float(path.get_attribute("data-rate")), 100 * ballots / registrations)
            assert path.get_attribute("fill") != "#edf0f3"
        for geoid, county, ballots, registrations, printed, clock, reporting in (
            ("42113", "Sullivan", 2712, 4501, "60.25%", "2026-11-06 10:36:27",
             "Precinct reporting not printed"),
            ("42131", "Wyoming", 10542, 18565, "56.78%", "2026-11-06 09:15:07",
             "28/28 precincts reported, not completed counting"),
        ):
            path = page.locator(f".substate-feature[data-geography='{geoid}']")
            path.dispatch_event("click")
            expect(page.locator("#current-county-select")).to_have_value(f"reviewed:PA:{county}")
            detail = page.locator("#current-county-detail")
            expect(detail.locator(".selection-rate")).to_have_text(f"{ballots:,}")
            for text in ("Total Ballots Cast", f"{registrations:,} native registered voters", printed,
                         clock, reporting, "clocks lack native timezones", "not candidate selections",
                         "not a printed PDF status", "0/4/25 unallocated", "unclassified, not undervotes",
                         "841 blank matrix cells remain missing", "16 printed zeros remain zero",
                         "candidate columns, not ballot-mode counts", "not added twice",
                         "do not certify 2026 election reporting boundaries"):
                expect(detail).to_contain_text(text)
            assert math.isclose(float(path.get_attribute("data-rate")), 100 * ballots / registrations)
            assert path.get_attribute("fill") != "#edf0f3"
        path = page.locator(".substate-feature[data-geography='42115']")
        path.dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:PA:Susquehanna")
        detail = page.locator("#current-county-detail")
        expect(detail.locator(".selection-rate")).to_have_text("15,317")
        for text in ("Total Ballots", "27,504 native registered voters", "55.69%", "UNOFFICIAL RESULTS",
                     "summary: 11/3/2026 10:25:47 PM EST", "precinct: 11/3/2026 10:25:23 PM EST",
                     "precinct: 11/3/2026 10:25:24 PM EST", "precinct: 11/3/2026 10:25:25 PM EST",
                     "canvass: 11/3/2026 10:26:02 PM EST", "41/41 reporting do not establish",
                     "absent, not zero", "unclassified, not native undervotes", "lack native parties",
                     "not CVAP, VAP, VEP, CPS, demographic turnout"):
            expect(detail).to_contain_text(text)
        assert math.isclose(float(path.get_attribute("data-rate")), 100 * 15317 / 27504)
        assert path.get_attribute("fill") != "#edf0f3"
        path = page.locator(".substate-feature[data-geography='42111']")
        path.dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:PA:Somerset")
        detail = page.locator("#current-county-detail")
        expect(detail.locator(".selection-rate")).to_have_text("27,019")
        for text in ("Ballots Cast - Total", "48,578 native registered voters", "55.62%",
                     "UNOFFICIAL RESULTS", "summary: 11/03/2026 11:03 PM",
                     "statement: 11/03/2026 11:08 PM", "statistics: 11/03/2026 11:11PM",
                     "timezone not declared", "do not establish completed counting or certification",
                     "0/67 complete and 67/67 partial", "65/67 with 67 in its mail column",
                     "three blank ballots are already included", "absent, not zero",
                     "not CVAP, VAP, VEP, CPS, demographic turnout"):
            expect(detail).to_contain_text(text)
        assert math.isclose(float(path.get_attribute("data-rate")), 100 * 27019 / 48578)
        assert path.get_attribute("fill") != "#edf0f3"
        for geoid, county, ballots, registrations, printed, texts in (
            ("42063", "Indiana", 28095, 49255, "57.04%", (
                "summary: 11/03/2026 10:03 PM", "statement: 11/03/2026 10:04 PM",
                "Election Day, mail and provisional breakdowns", "absent, not zero",
                "sum to 70, not the county 69")),
            ("42069", "Lackawanna", 87067, 151015, "57.65%", (
                "summary: 11/03/2026 10:02PM", "statement: 11/03/2026 10:02PM",
                "Contradictory native reporting-mode counters", "restricted",
                "county registrations are not their denominators")),
            ("42107", "Schuylkill", 48402, 92875, "52.12%", (
                "summary: 11/04/2026 11:01 AM", "statement: 11/04/2026 11:02 AM",
                "0/125 complete and 125/125 partial", "overvotes and undervotes are absent",
                "137 Pine Grove Township 1st prints 55.42%", "802 ballots / 1447 registrations")),
        ):
            path = page.locator(f".substate-feature[data-geography='{geoid}']")
            path.dispatch_event("click")
            expect(page.locator("#current-county-select")).to_have_value(f"reviewed:PA:{county}")
            detail = page.locator("#current-county-detail")
            expect(detail.locator(".selection-rate")).to_have_text(f"{ballots:,}")
            for text in ("Ballots Cast - Total", f"{registrations:,} native registered voters", printed,
                         "UNOFFICIAL RESULTS", "timezone not declared",
                         "do not establish completed counting or certification",
                         "not CVAP, VAP, VEP, CPS, demographic turnout", *texts):
                expect(detail).to_contain_text(text)
            assert math.isclose(float(path.get_attribute("data-rate")), 100 * ballots / registrations)
            assert path.get_attribute("fill") != "#edf0f3"
        page.locator(".substate-feature[data-geography='42061']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:PA:Huntingdon")
        detail = page.locator("#current-county-detail")
        expect(detail.locator(".selection-rate")).to_have_text("16,024")
        for text in ("Ballots Cast - Total", "27,917 native registered voters", "57.40%",
                     "UNOFFICIAL RESULTS", "11/03/2026 9:56 PM", "timezone not declared",
                     "58/58 complete", "do not establish certification", "not a verified geographic partition"):
            expect(detail).to_contain_text(text)
        path = page.locator(".substate-feature[data-geography='42061']")
        assert math.isclose(float(path.get_attribute("data-rate")), 100 * 16024 / 27917)
        assert path.get_attribute("fill") != "#edf0f3"
        page.locator(".substate-feature[data-geography='42073']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:PA:Lawrence")
        detail = page.locator("#current-county-detail")
        expect(detail.locator(".selection-rate")).to_have_text("31,401")
        for text in ("Ballots Cast - Total", "57,470 native registered voters", "54.64%",
                     "UNOFFICIAL RESULTS", "county: 11/03/2026 9:27 PM",
                     "mail_only: 11/03/2026 8:21 PM", "unit: 11/03/2026 9:39 PM",
                     "timezone not declared", "0/74 complete and 74/74 partially reported",
                     "not another all-mode county total", "usable rates are withheld",
                     "District 50 includes only 58 reporting units"):
            expect(detail).to_contain_text(text)
        path = page.locator(".substate-feature[data-geography='42073']")
        assert math.isclose(float(path.get_attribute("data-rate")), 100 * 31401 / 57470)
        assert path.get_attribute("fill") != "#edf0f3"
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
        assert totals == [834, 447]
        page.locator("#state-select").select_option(label="Vermont")
        expect(page.locator("#current-county-select option")).to_have_count(248)
        expect(page.locator("#geography-note")).to_contain_text("no whole-county participation joins are approved", timeout=30000)
        expect(page.locator(".substate-feature[data-context-review='20261106-25']")).to_have_count(0)
        page.locator("#state-select").select_option(label="New Jersey")
        page.locator("#show-current-counties").click()
        check_counties(page, "NJ")
        page.locator(".substate-feature[data-geography='34009']").dispatch_event("click")
        expect(page.locator("#current-county-select")).to_have_value("reviewed:NJ:Cape May")
        expect(page.locator("#current-county-detail")).to_contain_text("76,899 native registered voters")
        expect(page.locator("#current-county-detail")).to_contain_text("attached summary, PDF page 2")
        page.locator('button[aria-controls="methods-panel"]').click()
        check_static(page)
        modes.append(dict(mobile=mobile, javascript=True, complete_native_records_unchanged=1328,
                          complete_current_native_records=1329,
                          rock_snapshot_and_same_report_registered_fraction_verified=True,
                          wisconsin_71_other_counties_remain_missing_not_zero=True,
                          all_67_florida_counties_and_registered_fractions_verified=True,
                          retained_monroe_observation_not_duplicated_or_redated=True,
                          florida_literal_unfinished_flags_and_missing_clocks_preserved=True,
                          utah_29_inventories_19_counted_snapshots_18_fractions_verified=True,
                          sullivan_wyoming_native_participation_verified=True,
                          bedford_northumberland_native_participation_verified=True,
                          susquehanna_native_participation_verified=True,
                          somerset_native_participation_verified=True,
                          indiana_lackawanna_schuylkill_native_participation_verified=True,
                          huntingdon_native_participation_verified=True,
                          lawrence_native_participation_verified=True,
                          lycoming_native_participation_verified=True,
                          all_87_minnesota_inventories_verified=True, complete_minnesota_counts=75,
                          missing_minnesota_totals=12, eleven_minnesota_conflict_rates_withheld=True,
                          all_58_california_native_records_verified=True,
                          all_159_georgia_native_records_verified=True, two_georgia_missing_rates_gray=True,
                          greene_native_count_missing_denominator_and_clock_verified=True,
                          columbia_native_participation_and_separate_mail_qualifications_verified=True,
                          separate_native_statewide_count_and_registered_fraction_verified=True,
                          previous_jefferson_clarion_cameron_carbon_elk_forest_selection_preserved=True,
                          exact_county_count_matches=834, exact_county_rate_fills=447, missing_rates_gray=387,
                          complete_imports_unchanged=18, excluded_municipalities=286,
                          excluded_missing_county_totals=208, previous_download_anchors_preserved=sum(old_links.values()),
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
            page.route("**/participation-county-context/20261106-25/review.json",
                       lambda route: route.fulfill(status=503 if scenario == "failed-review" else 200,
                                                   content_type="application/json", body='{"changed":true}'))
        page.goto(url("Pennsylvania"), wait_until="domcontentloaded")
        page.locator("#show-current-counties").click()
        if scenario == "failed-current":
            assert check_counties(page, "PA") == (43, 40)
            page.locator("#state-select").select_option(label="California")
            page.locator("#show-current-counties").click()
            assert check_counties(page, "CA") == (58, 58)
            check_statewide(page)
            page.locator("#state-select").select_option(label="Georgia")
            page.locator("#show-current-counties").click()
            assert check_counties(page, "GA") == (159, 157)
            check_georgia_statewide(page)
            page.locator("#state-select").select_option(label="Minnesota")
            page.locator("#show-current-counties").click()
            assert check_counties(page, "MN") == (75, 64)
            page.locator("#state-select").select_option(label="Utah")
            page.locator("#show-current-counties").click()
            assert check_counties(page, "UT") == (19, 18)
            page.locator("#state-select").select_option(label="Florida")
            page.locator("#show-current-counties").click()
            assert check_counties(page, "FL") == (67, 67)
            page.locator("#state-select").select_option(label="Wisconsin")
            page.locator("#show-current-counties").click()
            assert check_counties(page, "WI") == (1, 1)
        else:
            expect(page.locator("#geography-note")).to_contain_text(
                "Independently reviewed county joins are withheld", timeout=30000)
            expect(page.locator(".substate-feature[data-context-review]")).to_have_count(0)
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

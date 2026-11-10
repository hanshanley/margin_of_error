"""Verify partial Maine source activity, complete contextual shapes and explicit ambiguous/missing holds."""

import argparse
import collections
import gzip
import json
from pathlib import Path
import re
import unicodedata

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "data/county-source-reviews/20261110-maine-locality-activity-01"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
inputs = json.loads((VERSION / "inputs.json").read_bytes())
original = json.loads(gzip.decompress((ROOT / inputs["reference"]["path"]).read_bytes()))["features"]
history = json.loads(gzip.decompress((ROOT / inputs["historical_identity_path"]).read_bytes()))
key = lambda s: re.sub("[^a-z0-9]", "", unicodedata.normalize("NFKD", s).lower())
source_key = lambda s: key(re.sub(r" (?:Twp|Plt)$", "", s))
by_id = {f["properties"]["key"]: f for f in original}
by_name = collections.defaultdict(list)
for f in original:
    by_name[key(f["properties"]["name"])].append(f["properties"]["key"])
qualified = collections.defaultdict(set)
for row in history:
    g = row.get("geography")
    if (row["year"] == 2024 and g and g["level"] == "municipality" and g["key"] in by_id
            and not row["statewide_unit"] and not row["supplemental_unit"]
            and source_key(row["jurisdiction"]) == key(by_id[g["key"]]["properties"]["name"])):
        qualified[key(row["jurisdiction"])].add(g["key"])
expected = {}
for mode, category in [("in_person_early", "inperson"), ("mail_returned", "returned")]:
    source = json.loads((ROOT / inputs["responses"][category]["path"]).read_bytes())
    names = collections.defaultdict(list)
    for name in source["regions"]:
        names[source_key(name)].append(name)
    assignments = {}
    for name in source["regions"]:
        q, plain = qualified.get(key(name), set()), by_name.get(source_key(name), [])
        if len(q) == 1:
            assignments[name] = next(iter(q))
        elif len(names[source_key(name)]) == 1 and len(plain) == 1:
            assignments[name] = plain[0]
    duplicates = collections.Counter(assignments.values())
    values = {identity: sum(r["votes"] for r in source["regions"][name].values())
              for name, identity in assignments.items() if duplicates[identity] == 1}
    assert len(values) == 480
    expected[mode] = values
assert "2339422" not in expected["in_person_early"]
cases = []


def choose(page, mode="available"):
    page.locator("#mode").select_option(mode)
    page.locator("#state-select").select_option("Maine")
    feature = page.locator('.map-feature[data-state="Maine"]')
    feature.focus()
    feature.press("Enter")


def verify(page, mode):
    shapes = page.locator('.geographic-detail [data-level="municipality"]')
    expect(shapes).to_have_count(528, timeout=90000)
    expect(page.locator("#title")).to_have_text("Local source activity in Maine")
    expect(page.locator("#caption")).to_contain_text("104 source regions and 48 reference areas")
    actual = shapes.evaluate_all("els=>els.map(e=>({key:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear}))")
    assert len({r["key"] for r in actual}) == 528
    for row in actual:
        assert row["rate"] == "" and row["year"] == "2024"
        assert row["count"] == (str(expected[mode][row["key"]]) if row["key"] in expected[mode] else "")
    assert sum(r["count"] == "" for r in actual) == 48
    assert page.locator('.geographic-detail [data-level="county"]').count() == 0


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in [False, True]:
            context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                          else {"width": 1440, "height": 1100})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            expect(page.locator('.map-feature[data-state="Maine"]')).to_have_count(1, timeout=90000)
            for mode in ["in_person_early", "mail_returned"]:
                choose(page, mode)
                verify(page, mode)
                response = page.request.get(base + "/participation-local/ME.json.gz")
                assert response.ok
                data = json.loads(gzip.decompress(response.body()))
                assert data["counties"] == [] and data["precincts"] == []
                rows = data["county_frames"][mode]
                assert len(rows) == 480
                for row in rows:
                    assert row["ballots"] == expected[mode][row["reference_municipality_key"]]
                    assert row["county_fips"] is None
                    assert row["denominator"] is None and row["reported_pct"] is None
                    assert row["native_election_id_qualified"] is False
                    assert row["cast_ballot_count_qualified"] is False and row["unique_voter_count_qualified"] is False
            choose(page)
            verify(page, "in_person_early")
            select = page.locator("#current-county-select")
            select.select_option(index=1)
            expect(page.locator("#current-county-detail")).not_to_be_empty()
            unknown = page.locator('.geographic-detail [data-geography="2339422"]')
            unknown.focus()
            unknown.press("Enter")
            expect(select).to_have_value("")
            expect(page.locator("#current-county-detail")).to_contain_text("No uniquely matched source activity count")
            choose(page, "mail_returned")
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            verify(page, "mail_returned")
            choose(page, "official")
            expect(page.locator("#title")).to_have_text("County turnout unavailable in Maine")
            expect(page.locator(".geographic-detail .map-feature")).to_have_count(0)
            choose(page)
            verify(page, "in_person_early")
            assert not errors, errors
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            cases.append(dict(mobile=mobile, source_modes=2, all_mapped_values_checked=True,
                mapped_per_mode=480, reference_shapes=528, source_held_per_mode=104,
                reference_held_per_mode=48, true_contextual_year=2024, official_not_provider=True,
                unknown_clears_stale_detail=True, methods_roundtrip=True, no_rates=True))
            context.close()
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        def malformed(route):
            response = route.fetch()
            data = json.loads(gzip.decompress(response.body()))
            data["county_frames"]["in_person_early"].pop()
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(data).encode()))
        page.route("**/participation-local/ME.json.gz", malformed)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="Maine"]')).to_have_count(1, timeout=90000)
        choose(page)
        expect(page.locator("#geography-note")).to_contain_text("Unqualified Maine locality activity frame", timeout=90000)
        expect(page.locator(".geographic-detail .map-feature")).to_have_count(0)
        page.unroute("**/participation-local/ME.json.gz", malformed)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify(page, "in_person_early")
        context.close()
    finally:
        browser.close()
proof = dict(status="PASS_ME_partial_locality_activity_not_county_or_precinct_turnout",
    base_url=base, cases=cases, invalid_frame_rejected=True, actual_retry_recovered=True,
    valid_source_overrides=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

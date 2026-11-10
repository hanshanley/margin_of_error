"""Verify deployed county activity frames against held raw provider counts, not full-election turnout."""

import argparse
import gzip
import json
from pathlib import Path
import re
import unicodedata

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "data/county-source-reviews/20261109-provider-county-frames-01"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4387")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
inputs = json.loads((VERSION / "inputs.json").read_bytes())
context = json.loads((VERSION / "source-context.json").read_bytes())
scopes_text = (ROOT / "public/scripts/provider-county-scopes.js").read_text()
scopes = json.loads(scopes_text.removeprefix("export const providerCountyScopes = ").strip().removesuffix(";"))
names = {r["state_code"]: r["state"] for r in context["states"]}


def name_key(value):
    value = unicodedata.normalize("NFKD", value).lower()
    value = re.sub(r"^st\.?\s+", "saint ", value)
    value = re.sub(r" (?:county|parish|municipality)$", "", value)
    return re.sub(r"[^a-z0-9]", "", value)


expected = {}
for code, scope in scopes.items():
    if code == "WV":
        continue
    geometry = json.loads(gzip.decompress((ROOT / inputs["references"][code]["path"]).read_bytes()))
    identities = {name_key(f["properties"]["name"]): f["properties"]["key"] for f in geometry["features"]}
    for mode in scope["modes"]:
        category = "inperson" if mode == "in_person_early" else "returned"
        source = json.loads((ROOT / inputs["responses"][code + "-" + category]["path"]).read_bytes())
        values = {identities[name_key(region)]: sum(bucket["votes"] for bucket in buckets.values())
                  for region, buckets in source["regions"].items()}
        assert len(values) == scope["counties"]
        expected[(code, mode)] = dict(values=values, date=source["snapshot_date"], source=source)
assert len(expected) == 61
cases = []


def choose_state(page, code):
    page.locator("#state-select").select_option(names[code])
    path = page.locator(f'.map-feature[data-state="{names[code]}"]')
    path.focus()
    path.press("Enter")


def verify(page, code, mode):
    source = expected[(code, mode)]
    shapes = page.locator('.geographic-detail [data-level="county"]')
    expect(shapes).to_have_count(len(source["values"]), timeout=90000)
    expect(page.locator("#title")).to_have_text(f"Local participation in {names[code]}")
    expect(page.locator("#caption")).to_contain_text(re.compile("provider", re.I))
    actual = shapes.evaluate_all("els=>els.map(e=>({fips:e.dataset.geography,count:e.dataset.count,rate:e.dataset.rate,year:e.dataset.referenceYear}))")
    assert len({r["fips"] for r in actual}) == len(source["values"])
    for row in actual:
        assert int(row["count"]) == source["values"][row["fips"]], (code, mode, row)
        assert row["rate"] == "" and row["year"] == "2026"
    expect(page.locator("#table-head")).to_contain_text("Provider")
    return actual


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for mobile in (False, True):
            browser_context = browser.new_context(viewport={"width": 390, "height": 844} if mobile
                                                  else {"width": 1440, "height": 1100})
            page = browser_context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
            assert response.ok
            expect(page.locator("#year")).to_have_value("2026", timeout=90000)
            expect(page.locator('.map-feature[data-state="Texas"]')).to_have_count(1, timeout=90000)
            frames = []
            for code, mode in sorted(expected):
                page.locator("#mode").select_option(mode)
                choose_state(page, code)
                verify(page, code, mode)
                response = page.request.get(base + f"/participation-local/{code}.json.gz")
                assert response.ok
                data = json.loads(gzip.decompress(response.body()))
                rows = data["county_frames"][mode]
                assert len(rows) == len(expected[(code, mode)]["values"])
                for row in rows:
                    assert row["ballots"] == expected[(code, mode)]["values"][row["county_fips"]]
                    assert row["source_provider"] == "civicAPI early activity"
                    assert row["source_date"] == expected[(code, mode)]["date"]
                    assert row["native_election_id_qualified"] is False
                    assert row["denominator"] is None and row["reported_pct"] is None
                    assert row["cast_ballot_count_qualified"] is False
                    assert row["unique_voter_count_qualified"] is False
                frames.append(dict(state_code=code, mode=mode, all_raw_values=True, counties=len(rows)))
            for code in ["DE", "KS", "LA", "MS", "MT", "NY", "OH", "OK", "SC", "TN", "TX"]:
                page.locator("#mode").select_option("available")
                choose_state(page, code)
                mode = "in_person_early" if (code, "in_person_early") in expected else "mail_returned"
                verify(page, code, mode)
            page.locator("#mode").select_option("mail_returned")
            choose_state(page, "TX")
            page.locator("#current-county-select").select_option("additional:TX:48001")
            detail = page.locator("#current-county-detail")
            expect(detail).to_contain_text(expected[("TX", "mail_returned")]["date"])
            expect(detail).to_contain_text("not independently qualified")
            expect(detail.locator('a[href*="voter-provider-county-frames-20261109-01/complete-analysis.zip"]').first).to_be_visible()
            page.locator("#tab-methods").click()
            expect(page.locator("#methods-archive")).to_be_hidden()
            page.locator("#tab-states").click()
            expect(page.locator("#mode")).to_have_value("mail_returned")
            expect(page.locator("#state-select")).to_have_value("Texas")
            verify(page, "TX", "mail_returned")
            page.locator("#mode").select_option("official")
            choose_state(page, "DE")
            expect(page.locator("#title")).to_have_text("County contest counts in Delaware")
            page.locator("#mode").select_option("available")
            choose_state(page, "HI")
            expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(4, timeout=90000)
            expect(page.locator("#caption")).to_contain_text("Maui includes Kalawao")
            for mode in ["in_person_early", "mail_returned"]:
                page.locator("#mode").select_option(mode)
                choose_state(page, "WV")
                expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(55, timeout=90000)
                response = page.request.get(base + "/participation-local/WV.json.gz")
                data = json.loads(gzip.decompress(response.body()))
                assert all(row.get("source_provider") is None
                           and row["ballots"] == row["native_record"]["TOTAL VOTERS"]
                           for row in data["county_frames"][mode])
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            cases.append(dict(mobile=mobile, source_frames=frames,
                provider_frames=len(frames), source_county_values=sum(r["counties"] for r in frames),
                available_fallback_states=11, official_mode_not_provider=True,
                native_HI_and_WV_priority_preserved=True, methods_roundtrip=True))
            browser_context.close()

        browser_context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = browser_context.new_page()
        def malformed(route):
            response = route.fetch()
            data = json.loads(gzip.decompress(response.body()))
            data["county_frames"]["mail_returned"].pop()
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            route.fulfill(status=200, headers=headers, body=gzip.compress(json.dumps(data).encode()))
        page.route("**/participation-local/TX.json.gz", malformed)
        page.goto(base + "/voter-participation/", wait_until="domcontentloaded")
        expect(page.locator('.map-feature[data-state="Texas"]')).to_have_count(1, timeout=90000)
        page.locator("#mode").select_option("mail_returned")
        choose_state(page, "TX")
        expect(page.locator("#geography-note")).to_contain_text("Unqualified provider county activity frame", timeout=90000)
        expect(page.locator('.geographic-detail [data-level="county"]')).to_have_count(0)
        page.unroute("**/participation-local/TX.json.gz", malformed)
        page.get_by_role("button", name="Retry geographic detail").click()
        verify(page, "TX", "mail_returned")
        browser_context.close()
    finally:
        browser.close()
proof = dict(status="PASS_provider_county_activity_frames_separate_from_native_turnout",
    base_url=base, cases=cases, invalid_frame_rejected_without_full_count_fallback=True,
    actual_source_retry_recovered=True, valid_source_overrides=False)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

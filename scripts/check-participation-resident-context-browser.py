"""Verify resident context separately from participation and against exact reference identities."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4398")
parser.add_argument("--dataset-root", type=Path, required=True)
parser.add_argument("--proof", type=Path, required=True)
parser.add_argument("--actual-catalog", action="store_true")
parser.add_argument("--county-only", action="store_true")
parser.add_argument("--matched-references", action="store_true")
args = parser.parse_args()
assert not args.proof.exists()
index_body = (args.dataset_root / "index.json").read_bytes()
index = json.loads(index_body)
root = Path(__file__).resolve().parents[1]
state_names = {feature["properties"]["NAME"]: feature["properties"]["STUSAB"]
    for feature in json.loads((root / "dist/voter-participation/data/states.geojson").read_bytes())["features"]}
version = json.loads((args.dataset_root / "dataset.json").read_bytes())["version"]
catalog_url = "https://raw.githubusercontent.com/hanshanley/margin_of_error/participation-data/catalog.json"
fixture_base = "https://raw.githubusercontent.com/hanshanley/margin_of_error/" + "f" * 40 + "/datasets/resident-context/" + version + "/"
catalog = dict(contract="participation.dataset_catalog.v1", datasets={
    "resident-context": dict(contract="participation.dataset.v1", id="resident-context",
        status="loaded", version=version, base_url=fixture_base,
        index=dict(file="index.json", bytes=len(index_body), sha256=hashlib.sha256(index_body).hexdigest()),
        complete_download=dict(immutable=True, verified_anonymously=True, sha256="a" * 64,
            url="https://github.com/hanshanley/margin_of_error/releases/download/participation-resident-local-context-20261110-02/complete-resident-dataset.zip"))})
cases = []


def fixture(route):
    path = route.request.url.removeprefix(fixture_base)
    if ".." in Path(path).parts:
        raise ValueError("Unqualified fixture path")
    file = args.dataset_root / path
    route.fulfill(status=200, body=file.read_bytes(),
                  content_type="application/gzip" if path.endswith(".gz") else "application/json",
                  headers={"Access-Control-Allow-Origin": "*"})


with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in (1440, 390):
            page = browser.new_page(viewport=dict(width=width, height=1000))
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            if not args.actual_catalog:
                page.route(catalog_url, lambda route: route.fulfill(json=catalog,
                    headers={"Access-Control-Allow-Origin": "*"}))
                page.route(fixture_base + "**", fixture)
            page.goto(args.base_url.rstrip("/") + "/voter-participation/?year=2026",
                      wait_until="domcontentloaded", timeout=90000)
            expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
            host = page.locator("#resident-context")
            expect(host).to_have_attribute("data-dataset-version", version, timeout=90000)
            host.evaluate("node => node.open = true")
            detail = host.locator("[data-resident-detail]")
            select = host.locator("select")
            if width == 1440:
                options = page.locator("#state-select option").all_text_contents()
                for name in options:
                    code = state_names[name]
                    source = json.loads(gzip.decompress(
                        (args.dataset_root / index["states"][code]["file"]).read_bytes()))
                    page.locator("#state-select").select_option(label=name)
                    expect(select.locator("option").nth(1)).to_have_attribute("value",
                        source["counties"][0]["geography"]["census_geoid"], timeout=90000)
                    expect(select).to_be_enabled(timeout=90000)
                    actual = select.locator("option").count() - 1
                    assert actual == index["states"][code]["counties"]
                    cases.append(dict(width=width, state=name, native_county_options=actual))
            for name, code in (("Florida", "FL"), ("New Mexico", "NM")):
                page.locator("#state-select").select_option(label=name)
                expect(select).to_be_enabled(timeout=90000)
                expect(select.locator("option")).to_have_count(index["states"][code]["counties"] + 1)
                key = "12087" if code == "FL" else "35011"
                select.select_option(key)
                expect(detail).to_have_attribute("data-census-geoid", key, timeout=90000)
                expect(detail).to_contain_text("not a 2026 voter profile")
                if key == "35011":
                    expect(detail).to_contain_text("Not available")
                cases.append(dict(width=width, county=key, direct_context=True,
                                  unknown_income_preserved=key == "35011"))
            local_sources = [("Minnesota", "MN"), ("New Hampshire", "NH"),
                               ("New Mexico", "NM"), ("Michigan", "MI"),
                               ("Massachusetts", "MA"), ("Alaska", "AK"), ("Indiana", "IN")]
            if args.matched_references:
                local_sources.extend([("Idaho", "ID"), ("Virginia", "VA"),
                    ("North Dakota", "ND"), ("District of Columbia", "DC")])
            for name, code in local_sources:
                if args.county_only:
                    continue
                if width == 390 and code not in (("MN", "NH", "ID", "VA", "ND", "DC")
                        if args.matched_references else ("MN", "NH")):
                    continue
                page.locator("#state-select").select_option(label=name)
                expect(select).to_be_enabled(timeout=90000)
                source = json.loads(gzip.decompress(
                    (args.dataset_root / index["states"][code]["file"]).read_bytes()))
                profile = source["precincts"][0]
                key = profile["geography"]["reference_key"]
                page.locator("#map-level").select_option("precinct")
                button = page.locator("#show-matched-precinct-participation")
                if button.count():
                    button.click()
                path = page.locator(f'#visualization [data-geography="{key}"]')
                expect(path).to_be_attached(timeout=90000)
                path.dispatch_event("click")
                host.evaluate("node => node.open = true")
                expect(detail).to_have_attribute("data-reference-key", key, timeout=90000)
                expect(detail).to_have_attribute("data-context-status", profile["context_status"])
                expect(detail).to_contain_text("How this local estimate is made")
                expect(detail).to_contain_text("not an exact median or confidence interval")
                assert detail.get_attribute("data-census-geoid") is None
                cases.append(dict(width=width, state=code, exact_reference_key=key,
                    conditional_profile=True, verified_actual_geometry_hash=True,
                    county_not_substituted=True))
                if args.matched_references and code in ("ND", "DC"):
                    excluded = source["precinct_reference_holds"][0]
                    held_path = page.locator(f'#visualization [data-geography="{excluded["key"]}"]')
                    expect(held_path).to_be_attached(timeout=90000)
                    held_path.dispatch_event("click")
                    expect(detail).to_contain_text("No qualified resident profile", timeout=90000)
                    if "display_excludes_part_of_whole_source_unit" in excluded["reason"]:
                        expect(detail).to_contain_text("displayed shape excludes part")
                    assert detail.get_attribute("data-reference-key") is None
                    assert detail.get_attribute("data-census-geoid") is None
                    cases.append(dict(width=width, state=code, held_reference=excluded["key"],
                        source_scope_hold_retained=True, whole_unit_not_clipped_area=True,
                        no_stale_profile_or_county_substitution=True))
                    path.dispatch_event("click")
                    expect(detail).to_have_attribute("data-reference-key", key, timeout=90000)
            detail.locator("details").first.evaluate("node => node.open = true")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("#resident-context").scroll_into_view_if_needed()
            page.screenshot(path=str(args.proof.with_suffix(f".{width}.png")))
            if not args.county_only:
                page.locator("#year").select_option("2024")
                expect(detail).not_to_have_attribute("data-reference-key", key, timeout=90000)
                assert detail.get_attribute("data-reference-key") is None
                cases.append(dict(width=width, prior_year_cannot_retain_current_reference=True))
            assert not errors, errors
            page.close()
    finally:
        browser.close()
proof = dict(status="PASS_actual_public_catalog_integrated_resident_reader" if args.actual_catalog
    else "PASS_local_resident_reader_with_explicit_unpublished_dataset_fixture",
    dataset_version=version, cases=cases, production=args.actual_catalog and args.base_url.startswith("https://www.themarginoferror.com"),
    fixture_is_publication_proof=False, test_fixture_used=not args.actual_catalog,
    no_resident_values_used_as_voter_composition=True, native_participation_values_unchanged=True)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

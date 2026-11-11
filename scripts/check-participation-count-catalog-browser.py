"""Verify real common-catalog counts, mode bindings and legacy-route isolation."""

import argparse
import gzip
import json
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4399")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
runtime_root = ROOT / "data/participation-counts/20261110-02/runtime"
descriptor = json.loads((runtime_root / "dataset.json").read_bytes())
index = json.loads((runtime_root / "index.json").read_bytes())
expected = {}
for code, declaration in index["states"].items():
    data = json.loads(gzip.decompress((runtime_root / declaration["file"]).read_bytes()))
    records = {row["id"]: row["view"] for row in data["records"]}
    expected[code] = {
        mode: {key: [records[identity] for identity in frame[key]]
            for key in ("counties", "precincts", "nongeographic")}
        for mode, frame in data["views"].items()}
cases = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    try:
        page = browser.new_page(viewport=dict(width=1440, height=1000))
        requests, errors = [], []
        page.on("request", lambda request: requests.append(request.url))
        page.on("pageerror", lambda error: errors.append(str(error)))
        response = page.goto(args.base_url.rstrip("/") +
            "/voter-participation/?year=2026&state=Florida&mode=available&map-level=county",
            wait_until="domcontentloaded", timeout=90000)
        assert response.ok
        expect(page.locator("#current-county-select option")).to_have_count(68, timeout=90000)
        result = page.evaluate("""async expected => {
          const module = await import('/scripts/participation-counts.js');
          const {entry,index} = await module.loadCountIndex();
          const cases=[];
          for(const [code,modes] of Object.entries(expected)){
            const data=await module.loadCountState(code);
            for(const [mode,partitions] of Object.entries(modes)){
              const actual=module.countFrame(data,mode);
              for(const [key,rows] of Object.entries(partitions)){
                if(JSON.stringify(actual[key])!==JSON.stringify(rows))
                  throw new Error(`Count differs: ${code}/${mode}/${key}`);
              }
              cases.push({code,mode,counties:actual.counties.length,units:actual.precincts.length});
            }
          }
          const current=await module.loadCurrentCountSnapshot();
          return {version:entry.version,base_url:entry.base_url,cases,
            reporting:current.snapshot.reporting.length,early:current.snapshot.early_voting.length};
        }""", expected)
        assert result["version"] == descriptor["version"]
        assert len(result["cases"]) == 306
        assert result["reporting"] == 7 and result["early"] == 6450
        cases.extend(result["cases"])
        state_names = {feature["properties"]["NAME"]: feature["properties"]["STUSAB"] for feature in
            json.loads((ROOT / "public/voter-participation/data/states.geojson").read_bytes())["features"]
            if feature["properties"]["STUSAB"] in expected}
        assert len(state_names) == 51
        for state_name, code in state_names.items():
            page.locator("#state-select").select_option(state_name)
            page.wait_for_function("""() => {
              const note=document.querySelector('#current-local-navigation');
              return note && !note.textContent.includes('Loading 2026 local counts');
            }""", timeout=90000)
            assert not page.locator("#current-local-navigation").inner_text().startswith("Dataset:")
            choices = len(expected[code]["available"]["counties"])
            expect(page.locator("#current-county-select option")).to_have_count(choices + 1 if choices else 0)
            assert page.locator("#reviewed-county-overview button").count() == 0
        for width in (1440, 390):
            page.set_viewport_size(dict(width=width, height=1000))
            page.goto(args.base_url.rstrip("/") +
                "/voter-participation/?year=2026&state=Minnesota&mode=official&map-level=county",
                wait_until="domcontentloaded", timeout=90000)
            expect(page.locator("#current-county-select option")).to_have_count(88, timeout=90000)
            page.locator("#current-county-select").select_option(label="Aitkin")
            expect(page.locator("#current-county-detail .selection-rate")).to_have_text("9,019")
            parent = next(row for row in expected["MN"]["official"]["counties"] if row["county"] == "Aitkin")
            units = [row for row in expected["MN"]["official"]["precincts"] if row["county_id"] == parent["county_id"]]
            expect(page.locator("#current-unit-select option")).to_have_count(len(units) + 1)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.locator("#participation-research").get_attribute("open") is None
            page.locator("#historical-explorer").screenshot(path=str(args.proof.with_suffix(f".{width}.png")))
            cases.append(dict(width=width, state="Minnesota", county_count=9019,
                native_county_choices=87, compact_sidebar=True, no_overflow=True))
        assert not errors, errors
        assert not [url for url in requests if re.search(r"/participation-local/[A-Z]{2}\.json\.gz(?:\?|$)", url)], \
            "Active legacy 2026 county export request"
        assert not [url for url in requests if "/public/participation-current/" in url], "Active legacy state snapshot request"
        proof = dict(status="PASS_actual_public_catalog_all_306_bindings_state_UI_and_phone",
            base_url=args.base_url, production=args.base_url.startswith("https://www.themarginoferror.com"),
            test_fixture_used=False, version=result["version"], immutable_base=result["base_url"],
            reporting_rows=result["reporting"], retained_early_rows=result["early"],
            all_state_UI_cases=len(state_names), cases=cases, active_legacy_count_requests=0)
        args.proof.write_text(json.dumps(proof, indent=2) + "\n")
        print(json.dumps({key: value for key, value in proof.items() if key != "cases"}))
    finally:
        browser.close()

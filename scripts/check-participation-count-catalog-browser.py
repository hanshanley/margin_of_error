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
parser.add_argument("--runtime-root", type=Path,
    default=ROOT / "data/participation-counts/20261110-02/runtime")
parser.add_argument("--native-runtime-root", type=Path)
args = parser.parse_args()
assert not args.proof.exists()
runtime_root = args.runtime_root
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
        page.on("requestfailed", lambda request: print(json.dumps(
            dict(failed_request=request.url, reason=request.failure)), flush=True)
            if "raw.githubusercontent.com/hanshanley/margin_of_error/" in request.url else None)
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
            let data;
            for(let attempt=0;attempt<3;attempt++){
              try { data=await module.loadCountState(code); break; }
              catch(error){
                if(error.name!=='TypeError'||error.message!=='Failed to fetch'||attempt===2)
                  throw new Error(`${code}: ${error.message}`);
                await new Promise(resolve=>setTimeout(resolve,1000*(attempt+1)));
              }
            }
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
            towns = [row for row in expected["VT"]["available"]["counties"]
                if row["geography_level"] == "municipality"]
            rates = sum(row["reported_pct"] is not None for row in towns)
            page.goto(args.base_url.rstrip("/") +
                "/voter-participation/?year=2026&state=Vermont&mode=available&map-level=county",
                wait_until="domcontentloaded", timeout=90000)
            expect(page.locator("#current-county-select option")).to_have_count(len(towns) + 1, timeout=90000)
            page.locator('#visualization path.map-feature[data-state="Vermont"]').dispatch_event("click")
            expect(page.locator('#visualization [data-level="municipality"]')).to_have_count(
                len(towns), timeout=90000)
            mapped = page.evaluate("""() => [...document.querySelectorAll(
                '#visualization [data-level="municipality"]')].map(path => ({
                  id:path.dataset.sourceCountyId,count:Number(path.dataset.count),
                  registered:Number(path.dataset.registered),
                  rate:path.dataset.rate===""?null:Number(path.dataset.rate)
                }))""")
            assert {row["id"]: row for row in mapped} == {row["county_id"]: dict(
                id=row["county_id"], count=row["ballots"], registered=row["denominator"],
                rate=row["reported_pct"]) for row in towns}
            expect(page.locator("#coverage-note")).to_contain_text(
                f"{rates} reviewed rates and {len(towns)-rates} withheld")
            expect(page.locator("#geography-note")).to_contain_text(f"{rates} approved rates")
            selected = towns[0]
            page.locator("#current-county-select").select_option(selected["county_id"])
            detail = page.locator("#current-county-detail")
            expect(detail.locator("a", has_text="Native participation source")).to_have_attribute(
                "href", selected["source_url"])
            downloads = {row["complete_download_url"] for row in towns if row.get("complete_download_url")}
            if len(downloads) == 1:
                expect(page.locator("#caption a", has_text="Complete current municipality counts")).to_have_attribute(
                    "href", downloads.pop())
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("#historical-explorer").screenshot(
                path=str(args.proof.with_suffix(f".vt.{width}.png")))
            cases.append(dict(width=width, state="Vermont", municipality_counts_bound=len(mapped),
                reviewed_registered_fractions=rates, withheld_rates=len(towns)-rates,
                native_source_label_correct=True, current_complete_queries_linked=True, no_overflow=True))
            if args.native_runtime_root:
                native_root = args.native_runtime_root
                native_descriptor = json.loads((native_root / "dataset.json").read_bytes())
                native_index = json.loads((native_root / "index.json").read_bytes())
                native_table = native_index["reporting_tables"]["WY"]
                native_records = json.loads(gzip.decompress(
                    (native_root / native_table["file"]).read_bytes()))["records"]
                native_rows = [row["properties"] for row in native_records]
                native_source = native_index["reporting_sources"]["WY"]
                actual = page.evaluate("""async () => {
                  const module = await import('/scripts/participation-native-bindings.js');
                  const {entry,index} = await module.loadNativeIndex();
                  return {version:entry.version,rows:await module.loadReportingRows('WY'),
                    source:index.reporting_sources.WY};
                }""")
                assert actual == dict(version=native_descriptor["version"],
                    rows=native_rows, source=native_source)
                assert len(native_rows) == 432 and sum(row["ballots"] for row in native_rows) == 191713
                page.goto(args.base_url.rstrip("/") +
                    "/voter-participation/?view=precincts&year=2026&state=Wyoming&precinct-layer=participation",
                    wait_until="domcontentloaded", timeout=90000)
                select = page.locator("#source-reporting-unit-select")
                expect(select.locator("option")).to_have_count(len(native_rows), timeout=90000)
                for row in native_rows:
                    select.select_option(row["key"])
                    expect(page.locator("#source-reporting-unit-detail .selection-rate")).to_have_text(
                        f'{row["ballots"]:,}')
                detail = page.locator("#source-reporting-unit-detail")
                expect(detail).to_contain_text("Not supplied; retrieval time is separate")
                expect(detail).not_to_contain_text("Source label: null")
                expect(detail).to_contain_text("no participation rate")
                expect(page.locator("#geography-note")).to_contain_text("No geographic overlays")
                expect(page.locator("#substate-detail a", has_text="All native reporting-unit observations")).to_have_attribute(
                    "href", native_source["data_url"])
                expect(page.locator("#substate-detail a", has_text="Complete original sources")).to_have_attribute(
                    "href", native_source["complete_download_url"])
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.locator("#historical-explorer").screenshot(
                    path=str(args.proof.with_suffix(f".wy.{width}.png")))
                cases.append(dict(width=width, state="Wyoming", native_units_checked=len(native_rows),
                    reported_ballots=191713, all_native_properties_exact=True,
                    unknown_clock_explicit=True, geographic_and_rate_holds_preserved=True,
                    complete_numerical_downloads_linked=True, no_overflow=True))
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

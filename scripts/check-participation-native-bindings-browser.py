"""Verify public native bindings, complete reporting tables and scoped coverage."""

import argparse
import gzip
import json
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4399")
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
base = args.base_url.rstrip("/")
runtime = ROOT / "data/participation-native-bindings/20261111-05/runtime"
descriptor = json.loads((runtime / "dataset.json").read_bytes())
index = json.loads((runtime / "index.json").read_bytes())
layers = {}
for identity, declaration in index["layers"].items():
    data = json.loads(gzip.decompress((runtime / declaration["file"]).read_bytes()))
    layers[identity] = dict(sha256=data["geometry"]["sha256"],
        properties=[row["properties"] for row in data["rows"]])
tables = {code: [row["properties"] for row in json.loads(
    gzip.decompress((runtime / declaration["file"]).read_bytes()))["records"]]
    for code, declaration in index["reporting_tables"].items()}
names = {f["properties"]["STUSAB"]: f["properties"]["NAME"] for f in json.loads(
    (ROOT / "public/voter-participation/data/states.geojson").read_bytes())["features"]}
cases = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    try:
        page = browser.new_page(viewport=dict(width=1440, height=1000))
        page.set_default_timeout(90000)
        errors, requests = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append(request.url))
        response = page.goto(base + "/voter-participation/?year=2026&state=Florida&map-level=county",
            wait_until="domcontentloaded", timeout=90000)
        assert response.ok
        expect(page.locator("#current-county-select option")).to_have_count(68)
        result = page.evaluate("""async expected => {
          const native=await import('/scripts/participation-native-bindings.js');
          const counts=await import('/scripts/participation-counts.js');
          const {entry,index}=await native.loadNativeIndex(), cases=[];
          const retry=async run=>{
            for(let attempt=0;attempt<3;attempt++){
              try{return await run();}
              catch(error){
                if(error.name!=='TypeError'||error.message!=='Failed to fetch'||attempt===2)throw error;
                await new Promise(resolve=>setTimeout(resolve,1000*(attempt+1)));
              }
            }
          };
          for(const [identity,previous] of Object.entries(expected.layers)){
            const result=await retry(()=>native.loadBoundNative(identity));
            if(result.verified_geometry_sha256!==previous.sha256||
                JSON.stringify(result.data.features.map(f=>f.properties))!==JSON.stringify(previous.properties))
              throw new Error('Original native rows/reference changed: '+identity);
            cases.push({identity,features:result.data.features.length,exact_properties:true,reference_sha256:previous.sha256});
          }
          for(const [code,previous] of Object.entries(expected.tables)){
            const rows=await retry(()=>native.loadReportingRows(code));
            if(JSON.stringify(rows)!==JSON.stringify(previous))throw new Error('Reporting table differs: '+code);
            cases.push({table:code,rows:rows.length,unknown:rows.filter(r=>r.ballots===null).length,all_rates_withheld:true});
          }
          const references=new Map();
          for(const [code,modes] of Object.entries(index.county_bindings)){
            const state=await retry(()=>counts.loadCountState(code));
            for(const [mode,binding] of Object.entries(modes)){
              const rows=counts.countFrame(state,mode).counties, reference=rows[0].reference_geometry;
              if(!references.has(binding.sha256)){
                const data=await retry(async()=>{
                  const response=await fetch(reference.url);
                  if(!response.ok)throw new Error('Reference HTTP '+response.status);
                  const body=await response.arrayBuffer();
                  const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',body))]
                    .map(v=>v.toString(16).padStart(2,'0')).join('');
                  if(hash!==binding.sha256)throw new Error('County reference hash differs');
                  return new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream('gzip'))).json();
                });
                references.set(binding.sha256,data);
              }
              const bound=native.bindCountyReference(rows,references.get(binding.sha256),reference,binding);
              if(bound.size!==rows.length)throw new Error('County inventory differs');
              cases.push({county:code,mode,joined:bound.size});
            }
          }
          for(const [code,modes] of Object.entries(index.municipal_bindings)){
            const state=await retry(()=>counts.loadCountState(code));
            for(const mode of Object.keys(modes)){
              const rows=counts.countFrame(state,mode).counties;
              const reference=await retry(()=>native.loadMunicipalReference(code,mode));
              const bound=native.bindCountyReference(rows,reference.data,reference.reference,reference.binding);
              if(bound.size!==rows.length)throw new Error('Municipal inventory differs');
              cases.push({municipal:code,mode,joined:bound.size});
            }
          }
          return {version:entry.version,base_url:entry.base_url,cases};
        }""", dict(layers=layers, tables=tables))
        assert result["version"] == descriptor["version"]
        assert len(result["cases"]) == 11 + 5 + 134 + 8
        cases.extend(result["cases"])
        for identity, expected in layers.items():
            code = identity.split("/")[1]
            page.goto(base + "/voter-participation/?view=precincts&year=2026&state=" + quote(names[code]),
                wait_until="domcontentloaded", timeout=90000)
            paths = page.locator('#visualization path:is([data-level="precinct"],[data-level="ward"],[data-level="subprecinct"])')
            expect(paths).to_have_count(len(expected["properties"]))
            actual = paths.evaluate_all("(nodes)=>Object.fromEntries(nodes.map(n=>[n.dataset.geography,n.dataset.count]))")
            for p in expected["properties"]:
                value = p.get("participation", p)["ballots"]
                assert actual[p["key"]] == ("" if value is None else str(value)), (identity, p["key"])
            cases.append(dict(map=identity, exact_count_attributes=len(actual)))
        for code in ("AZ", "AR", "WY", "HI"):
            page.goto(base + "/voter-participation/?view=precincts&year=2026&state=" + quote(names[code]),
                wait_until="domcontentloaded", timeout=90000)
            expect(page.locator("#source-reporting-unit-select option")).to_have_count(len(tables[code]))
            missing = next((row for row in tables[code] if row["ballots"] is None), None)
            selected = missing or tables[code][0]
            page.locator("#source-reporting-unit-select").select_option(selected["key"])
            expect(page.locator("#source-reporting-unit-detail .selection-rate")).to_have_text(
                "Not supplied" if missing else f'{selected["ballots"]:,}')
            expect(page.locator("#geography-note")).to_contain_text("No geographic overlays")
            cases.append(dict(table_UI=code, options=len(tables[code]), unknown_not_zero=bool(missing)))
        for width in (1440, 390):
            page.set_viewport_size(dict(width=width, height=1000))
            page.goto(base + "/voter-participation/?year=2026&state=Minnesota&mode=available&map-level=county",
                wait_until="domcontentloaded", timeout=90000)
            coverage = page.locator("#participation-coverage")
            expect(coverage.locator("tbody tr")).to_have_count(51)
            assert coverage.get_attribute("open") is None
            row = coverage.locator('tr[data-state-code="MN"]')
            expect(row.locator("td").nth(1)).to_have_text("87")
            page.locator("#map-level").select_option("precinct")
            page.wait_for_function("""() => document.querySelector('#participation-coverage').dataset.level==='precinct'
              && document.querySelector('#participation-coverage tr[data-state-code="AZ"]')?.dataset.status==='Loaded (table only)'""")
            expect(coverage.locator('tr[data-state-code="AZ"] td').nth(1)).to_have_text("1763")
            expect(coverage.locator('tr[data-state-code="AZ"] td').nth(5)).to_have_text("1")
            expect(coverage.locator('tr[data-state-code="AK"] td').nth(1)).to_have_text("523")
            expect(coverage.locator('tr[data-state-code="AK"] td').nth(3)).to_have_text("81")
            coverage.locator("summary").click()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            coverage.screenshot(path=str(args.proof.with_suffix(f".{width}.png")))
            page.locator("#year").select_option("2024")
            expect(coverage.locator("tbody tr")).to_have_count(0)
            expect(coverage.locator("[data-coverage-caption]")).to_contain_text("separate source readers")
            cases.append(dict(coverage_width=width, jurisdictions=51, county_badge=87,
                table_only_not_missing=True, historical_not_misclassified=True, no_overflow=True))
        assert not errors, errors
        assert not [url for url in requests if url.endswith("/participation-precincts.json")
            or url.endswith("/participation-reporting-units.json")], "Active legacy native-count pointer"
        fault = browser.new_page()
        fault.goto(base + "/voter-participation/", wait_until="domcontentloaded", timeout=90000)
        fault.route("**/counts/precinct-AK.json.gz", lambda route: route.fulfill(body=b"explicit test corruption"))
        message = fault.evaluate("""async()=>{
          const m=await import('/scripts/participation-native-bindings.js');
          try{await m.loadBoundNative('precinct/AK');return 'UNEXPECTED';}catch(error){return error.message;}
        }""")
        assert "checksum differs" in message, message
        fault.unroute("**/counts/precinct-AK.json.gz")
        assert fault.evaluate("""async()=>{const m=await import('/scripts/participation-native-bindings.js');
          return (await m.loadBoundNative('precinct/AK')).data.features.length;}""") == 81
        fault.close()
        late = browser.new_page()
        pending = []
        late.route("**/counts/precinct-MN.json.gz", lambda route: pending.append(route))
        late.goto(base + "/voter-participation/?year=2026&state=Minnesota&mode=available&map-level=precinct",
            wait_until="domcontentloaded", timeout=90000)
        for _ in range(900):
            if pending:
                break
            late.wait_for_timeout(100)
        assert len(pending) == 1
        late.locator("#state-select").select_option("Florida")
        late.locator("#map-level").select_option("county")
        pending[0].fulfill(response=pending[0].fetch())
        expect(late.locator("#current-county-select option")).to_have_count(68)
        late.wait_for_timeout(500)
        expect(late.locator('#visualization path[data-level="precinct"]')).to_have_count(0)
        expect(late.locator("#state-select")).to_have_value("Florida")
        late.close()
        cases.append(dict(explicit_test_faults=True, corrupt_native_rejected=True,
            failed_shard_cache_recovers=True, late_state_response_isolated=True))
    finally:
        browser.close()
proof = dict(status="PASS_actual_public_native_bindings_tables_maps_coverage_and_fault_isolation",
    base_url=base, production=base.startswith("https://www.themarginoferror.com"),
    public_data_fixture_used=False, version=result["version"], immutable_base=result["base_url"],
    cases=cases, active_legacy_native_count_pointer_requests=0)
args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key != "cases"}))

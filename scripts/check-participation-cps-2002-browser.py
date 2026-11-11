"""Verify every 2002 history selection against science, without overriding valid data."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://raw.githubusercontent.com/hanshanley/voter-participation/043ece3c29e501f4f691cb87fc497da7e90d159d/data/participation-cps-2002/20261111-01/observations.json"
BODY = (ROOT / "data/participation-cps-2002/20261111-01/points.json").read_bytes()
SCIENCE = json.loads(BODY)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", required=True)
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
cases = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    try:
        for mode, options in [
                ("desktop", dict(viewport=dict(width=1440, height=1000))),
                ("phone", dict(viewport=dict(width=390, height=844))),
                ("no_javascript", dict(java_script_enabled=False)),
                ("failed_points", {}), ("corrupt_points", {}), ("late_points", {})]:
            context = browser.new_context(**options)
            errors, requests, held = [], [], []
            try:
                context.on("request", lambda request: requests.append(request.url))
                if mode == "failed_points":
                    context.route(SOURCE, lambda route: route.abort())
                elif mode == "corrupt_points":
                    context.route(SOURCE, lambda route: route.fulfill(body="{}", content_type="application/json",
                        headers={"Access-Control-Allow-Origin": "*"}))
                elif mode == "late_points":
                    context.route(SOURCE, lambda route: held.append(route))
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(args.base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded", timeout=90000)
                archive = page.locator("#participation-research")
                assert archive.get_attribute("open") is None
                assert SOURCE not in requests
                archive.locator(":scope > summary").click()
                archive.locator(":scope > details").first.locator(":scope > summary").click()
                panel = page.locator("#participation-cps-unified-history")
                table = panel.locator("[data-cps-2002-table]")
                adult = table.locator('[data-cps-2002-frame="vap"]')
                citizen = table.locator('[data-cps-2002-frame="cvap"]')
                expect(table).to_be_visible()
                if mode == "no_javascript":
                    expect(adult.locator("td")).to_contain_text("workbook margin not qualified")
                    expect(citizen.locator("td")).to_contain_text("46.1%")
                    result = dict(SSR_source_points=True, controls_hidden=True)
                else:
                    expect(panel.locator("[data-cps-unified-controls]")).to_be_visible(timeout=90000)
                    if mode == "late_points":
                        assert len(held) == 1
                        panel.locator("#cps-unified-state").select_option(label="California")
                        panel.locator("#cps-unified-group").select_option(label="Male")
                        expect(adult.locator("td")).to_contain_text("Loading")
                        expect(adult).to_have_attribute("data-rate", "")
                        held[0].continue_()
                        expected = next(row for row in SCIENCE["records"] if row["native"]["geography"] == "CALIFORNIA"
                            and row["native"]["native_label"] == ".Male")
                        expect(adult).to_have_attribute("data-source-key", expected["source_key"], timeout=90000)
                        expect(adult).to_have_attribute("data-rate", str(expected["selected_voted_pct"]))
                        result = dict(late_response_uses_latest_state_and_group=True, valid_data_override=False)
                    elif mode in ("failed_points", "corrupt_points"):
                        expect(adult.locator("td")).to_contain_text("source unavailable", timeout=90000)
                        expect(adult).to_have_attribute("data-rate", "")
                        expect(citizen).to_have_attribute("data-rate", "")
                        expect(panel.locator('[data-cps-unified-point="2024"]')).to_have_count(1)
                        result = dict(old_chart_survives_new_source_failure=True, failure_override_only=True)
                    else:
                        expect(citizen.locator("td")).to_contain_text("46.1%", timeout=90000)
                        result = panel.evaluate("""(section,science)=>{
                          const state=section.querySelector('#cps-unified-state'),group=section.querySelector('#cps-unified-group');
                          const election=section.querySelector('#cps-unified-election');
                          const require=(ok,message)=>{if(!ok)throw new Error(message)};
                          const lookup=new Map(science.records.map(row=>[
                            [row.native.geography,row.native.role,row.native.native_label].join('|'),row]));
                          let cells=0,selected=0;
                          for(let s=0;s<state.options.length;s++)for(let g=0;g<group.options.length;g++){
                            state.value=String(s);group.value=String(g);group.dispatchEvent(new Event('change'));
                            const geography=s===0?'UNITED STATES':state.options[s].text.toUpperCase();
                            const label=group.options[g].dataset.historyGroup;
                            let role=null,nativeLabel=null;
                            if(['Total','Male','Female'].includes(label)){role='sex_race';nativeLabel='.'+label}
                            else if(label==='Hispanic (any race)'){role='sex_race';nativeLabel='.Hispanic (of any race)'}
                            else if(['18 to 24','25 to 44','45 to 64','65 to 74','75+'].includes(label)){
                              role='age';nativeLabel='.'+label;
                            }else if(label.endsWith(' (2002 native category)')){
                              role='sex_race';nativeLabel='.'+label.slice(0,-' (2002 native category)'.length);
                            }
                            for(const frame of ['vap','cvap']){
                              let expected=null;
                              if(frame==='cvap'&&label==='Total')
                                expected=science.records.find(r=>r.native.geography===geography&&r.native.role==='citizen_overall');
                              else if(frame==='vap'&&role)expected=lookup.get([geography,role,nativeLabel].join('|'));
                              const row=section.querySelector(`[data-cps-2002-frame="${frame}"]`);
                              const rate=expected?.decision==='selected_reported_point_only'?expected.selected_voted_pct:null;
                              require(row.dataset.rate===(rate===null?'':String(rate)),[s,g,frame,'rate']);
                              require(row.dataset.sourceKey===(expected?.source_key||''),[s,g,frame,'source']);
                              if(rate!==null){require(row.textContent.includes('margin not qualified'),'Invented margin');selected++}
                              cells++;
                            }
                            require(!section.querySelector('[data-cps-unified-point="2002"]'),'2002 spliced into citizen graph');
                          }
                          require(selected===642,'Selected source inventory differs');
                          for(const value of ['presidential','midterm','all']){
                            election.value=value;election.dispatchEvent(new Event('change'));
                            require(section.querySelector('[data-cps-2002-table]').hidden===(value==='presidential'),'2002 election scope differs');
                          }
                          state.value='0';group.value='0';group.dispatchEvent(new Event('change'));
                          return {verified_point_cells:cells,selected_source_points:selected,geographies:state.options.length,
                            groups:group.options.length,no_invented_margins:true,no_chart_splice:true};
                        }""", SCIENCE)
                        assert result["verified_point_cells"] == 2912 and result["geographies"] == 52
                        page.wait_for_timeout(100)
                        panel.screenshot(path=str(args.proof.with_suffix(f".{mode}.png")))
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                assert panel.locator('[data-cps-2002-download="complete"]').get_attribute("href").endswith(
                    "/participation-cps-2002-reported-points-20261111-01/complete-analysis.zip")
                cases.append(dict(mode=mode, **result, no_overflow=True, console_errors=errors))
                print(json.dumps(cases[-1]), flush=True)
            finally:
                context.close()
    finally:
        browser.close()
proof = dict(status="passed_real_2002_historical_point_integration", base_url=args.base,
    source_sha256=hashlib.sha256(BODY).hexdigest(), valid_data_overrides=False, cases=cases)
args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")

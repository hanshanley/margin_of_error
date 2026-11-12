"""Verify every early-source selection, denominator and asynchronous failure boundary."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://raw.githubusercontent.com/hanshanley/voter-participation/e6e85ce7e8b371ebd952f5173b60df43869e8832/data/participation-cps-1996-state-points/20261112-01/complete-result.json"
BODY = (ROOT / "data/participation-cps-1996/20261112-01/points.json").read_bytes()
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
                rows = panel.locator("[data-cps-1996-frame]")
                expect(rows).to_have_count(2)
                adult, citizen = panel.locator('[data-cps-1996-frame="vap"]'), panel.locator('[data-cps-1996-frame="cvap"]')
                expect(adult).to_be_visible()
                if mode == "no_javascript":
                    expect(adult.locator("td")).to_contain_text("54.2%")
                    expect(citizen.locator("td")).to_contain_text("58.4%")
                    expect(citizen.locator("td")).to_contain_text("voting nonresponse 7.4%")
                    expect(panel.locator("[data-cps-unified-controls]")).to_be_hidden()
                    result = dict(SSR_both_frames=True, source_nonresponse_not_nonvote=True)
                else:
                    expect(panel.locator("[data-cps-unified-controls]")).to_be_visible(timeout=90000)
                    if mode == "late_points":
                        expect(adult.locator("td")).to_contain_text("54.2%")
                        assert len(held) == 1
                        panel.locator("#cps-unified-state").select_option(label="California")
                        panel.locator("#cps-unified-group").select_option(label="Female")
                        for row in (adult, citizen):
                            expect(row.locator("td")).to_contain_text("Loading")
                            expect(row).to_have_attribute("data-rate", "")
                            expect(row).to_have_attribute("data-voting-nonresponse", "")
                        held[0].continue_()
                        for row, table, group in ((adult, "B", "FEMALE"), (citizen, "C", "Female")):
                            expected = next(value for value in SCIENCE["records"] if value["geography"] == "CALIFORNIA"
                                            and value["table"] == table and value["native_group"] == group
                                            and value["age"] == "18_plus")
                            expect(row).to_have_attribute("data-source-key", expected["source_key"], timeout=90000)
                            expect(row).to_have_attribute("data-rate", format(float(expected["measures"]["voted"]["selected_percentage"]), "g"))
                        result = dict(late_response_uses_latest_state_and_group=True, stale_values_cleared=True)
                    elif mode in ("failed_points", "corrupt_points"):
                        for row in (adult, citizen):
                            expect(row.locator("td")).to_contain_text("source unavailable", timeout=90000)
                            expect(row).to_have_attribute("data-rate", "")
                            expect(row).to_have_attribute("data-voting-nonresponse", "")
                        expect(panel.locator('[data-cps-1998-frame] td')).to_contain_text("41.9%", timeout=90000)
                        expect(panel.locator('[data-cps-2002-frame="cvap"] td')).to_contain_text("46.1%", timeout=90000)
                        expect(panel.locator('[data-cps-unified-point="2024"]')).to_have_count(1)
                        result = dict(old_points_and_chart_survive_new_source_failure=True, failure_override_only=True)
                    else:
                        expect(adult.locator("td")).to_contain_text("54.2%", timeout=90000)
                        result = panel.evaluate("""(section,science)=>{
                          const state=section.querySelector('#cps-unified-state'),group=section.querySelector('#cps-unified-group');
                          const election=section.querySelector('#cps-unified-election');
                          const require=(ok,message)=>{if(!ok)throw new Error(JSON.stringify(message))};
                          const lookup=new Map(science.records.map(row=>[[row.geography,row.table,row.native_group,row.age].join('|'),row]));
                          const definitions={'Total':['A','ALL RACES','18_plus'],'Male':['B','MALE','18_plus'],
                            'Female':['B','FEMALE','18_plus'],'Hispanic (any race)':['A','HISPANIC ORIGIN','18_plus'],
                            'White (1998/2002 native category)':['A','WHITE','18_plus'],
                            'Black (1998/2002 native category)':['A','BLACK','18_plus'],
                            '18 to 24':['A','ALL RACES','18_24'],'25 to 44':['A','ALL RACES','25_44'],
                            '45 to 64':['A','ALL RACES','45_64'],'65+':['A','ALL RACES','65_plus']};
                          let cells=0,adults=0,citizens=0;
                          for(let s=0;s<state.options.length;s++)for(let g=0;g<group.options.length;g++){
                            state.value=String(s);group.value=String(g);group.dispatchEvent(new Event('change'));
                            const geography=s===0?'TOTAL':state.options[s].text.toUpperCase();
                            const label=group.options[g].dataset.historyGroup;
                            for(const frame of ['vap','cvap']){
                              const definition=frame==='vap'?definitions[label]:label==='Total'?['C','ALL','18_plus']:
                                ['Male','Female'].includes(label)?['C',label,'18_plus']:null;
                              const expected=definition?lookup.get([geography,...definition].join('|')):null;
                              const measure=expected?.measures.voted;
                              const rate=measure?.disposition==='selected_native_percentage'?Number(measure.selected_percentage):null;
                              const unknown=frame==='cvap'&&expected?Number(expected.measures.unknown_voting.selected_percentage):null;
                              const row=section.querySelector(`[data-cps-1996-frame="${frame}"]`);
                              require(row.dataset.rate===(rate===null?'':String(rate)),[s,g,frame,'rate']);
                              require(row.dataset.sourceKey===(expected?.source_key||''),[s,g,frame,'source']);
                              require(row.dataset.votingNonresponse===(unknown===null?'':String(unknown)),[s,g,frame,'unknown']);
                              if(rate!==null){require(row.textContent.includes('uncertainty not supplied'),'Invented uncertainty');
                                if(frame==='vap')adults++;else citizens++}
                              cells++;
                            }
                            require(!section.querySelector('[data-cps-unified-point="1996"]'),'Early point chart splice');
                          }
                          require(adults===520&&citizens===103,[adults,citizens,'inventory']);
                          for(const value of ['presidential','midterm','all']){
                            election.value=value;election.dispatchEvent(new Event('change'));
                            require(section.querySelector('[data-cps-1996-table]').hidden===(value==='midterm'),'1996 election scope');
                            require(section.querySelector('[data-cps-2002-table]').hidden===(value==='presidential'),'Older midterm scope');
                          }
                          state.value='0';group.value='0';group.dispatchEvent(new Event('change'));
                          return {verified_point_cells:cells,selected_adult_points:adults,selected_citizen_points:citizens,
                            geographies:state.options.length,groups:group.options.length,no_chart_splice:true};
                        }""", SCIENCE)
                        assert result["verified_point_cells"] == 3016
                        page.mouse.move(0, 0)
                        page.evaluate("document.activeElement?.blur()")
                        panel.screenshot(path=str(args.proof.with_suffix(f".{mode}.png")))
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                assert panel.locator('[data-cps-1996-download="complete"]').get_attribute("href").endswith(
                    "/participation-cps-1996-state-points-20261112-01/complete-analysis.zip")
                cases.append(dict(mode=mode, **result, no_overflow=True, console_errors=errors))
                print(json.dumps(cases[-1]), flush=True)
            finally:
                context.close()
    finally:
        browser.close()
args.proof.write_text(json.dumps(dict(status="passed_real_1996_historical_point_integration",
    base_url=args.base, source_sha256=hashlib.sha256(BODY).hexdigest(),
    valid_data_overrides=False, cases=cases), indent=2, sort_keys=True) + "\n")

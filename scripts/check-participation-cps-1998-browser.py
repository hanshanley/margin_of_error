"""Verify every 1998 native history selection and asynchronous source isolation."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://raw.githubusercontent.com/hanshanley/voter-participation/2b6cbcb3218b492e3391bb7d73b384cf28ff45be/data/participation-cps-1998-state-points/20261111-01/complete-result.json"
BODY = (ROOT / "data/participation-cps-1998/20261111-01/points.json").read_bytes()
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
                row = panel.locator('[data-cps-1998-frame="vap"]')
                expect(row).to_be_visible()
                if mode == "no_javascript":
                    expect(row.locator("td")).to_contain_text("41.9%")
                    expect(row.locator("td")).to_contain_text("source SE 0.20 pp (not a margin)")
                    result = dict(SSR_source_point=True, controls_hidden=True)
                else:
                    expect(panel.locator("[data-cps-unified-controls]")).to_be_visible(timeout=90000)
                    if mode == "late_points":
                        assert len(held) == 1
                        panel.locator("#cps-unified-state").select_option(label="California")
                        panel.locator("#cps-unified-group").select_option(label="Male")
                        expect(row.locator("td")).to_contain_text("Loading")
                        expect(row).to_have_attribute("data-rate", "")
                        held[0].continue_()
                        expected = next(value for value in SCIENCE["records"] if value["geography"] == "CALIFORNIA"
                            and value["native_group"] == "Male")
                        expect(row).to_have_attribute("data-source-key", expected["source_key"], timeout=90000)
                        expect(row).to_have_attribute("data-rate", str(float(expected["measures"]["voted"]["selected_percentage"])))
                        result = dict(late_response_uses_latest_state_and_group=True, valid_data_override=False)
                    elif mode in ("failed_points", "corrupt_points"):
                        expect(row.locator("td")).to_contain_text("source unavailable", timeout=90000)
                        expect(row).to_have_attribute("data-rate", "")
                        expect(row).to_have_attribute("data-source-se", "")
                        expect(panel.locator('[data-cps-2002-frame="cvap"] td')).to_contain_text("46.1%", timeout=90000)
                        expect(panel.locator('[data-cps-unified-point="2024"]')).to_have_count(1)
                        result = dict(old_points_and_chart_survive_new_source_failure=True, failure_override_only=True)
                    else:
                        expect(row.locator("td")).to_contain_text("41.9%", timeout=90000)
                        result = panel.evaluate("""(section,science)=>{
                          const state=section.querySelector('#cps-unified-state'),group=section.querySelector('#cps-unified-group');
                          const election=section.querySelector('#cps-unified-election');
                          const require=(ok,message)=>{if(!ok)throw new Error(message)};
                          const lookup=new Map(science.records.map(row=>[[row.geography,row.native_group].join('|'),row]));
                          const labels={'Total':'Total','Male':'Male','Female':'Female','Hispanic (any race)':'Hispanic',
                            'White (1998/2002 native category)':'White',
                            'Non-Hispanic White (1998/2002 native category)':'N-H White',
                            'Black (1998/2002 native category)':'Black',
                            'Non-Hispanic Black (1998/2002 native category)':'N-H Black',
                            'Non-Hispanic Asian and Pacific Islander (1998 native category)':'N-H API'};
                          let cells=0,selected=0;
                          for(let s=0;s<state.options.length;s++)for(let g=0;g<group.options.length;g++){
                            state.value=String(s);group.value=String(g);group.dispatchEvent(new Event('change'));
                            const geography=s===0?'UNITED STATES':state.options[s].text.toUpperCase();
                            const label=group.options[g].dataset.historyGroup,expected=lookup.get([geography,labels[label]].join('|'));
                            const measure=expected?.measures.voted;
                            const rate=measure?.disposition==='selected_reported_native_point'?Number(measure.selected_percentage):null;
                            const error=rate===null?null:Number(measure.selected_source_standard_error_pp);
                            const row=section.querySelector('[data-cps-1998-frame]');
                            require(row.dataset.rate===(rate===null?'':String(rate)),[s,g,'rate']);
                            require(row.dataset.sourceSe===(error===null?'':String(error)),[s,g,'error']);
                            require(row.dataset.sourceKey===(expected?.source_key||''),[s,g,'source']);
                            if(rate!==null){require(row.textContent.includes('source SE '+measure.selected_source_standard_error_pp+' pp (not a margin)'),'Changed source SE');selected++}
                            require(!section.querySelector('[data-cps-unified-point="1998"]'),'1998 spliced into citizen graph');
                            cells++;
                          }
                          require(selected===355,'Selected 1998 source inventory differs');
                          for(const value of ['presidential','midterm','all']){
                            election.value=value;election.dispatchEvent(new Event('change'));
                            require(section.querySelector('[data-cps-2002-table]').hidden===(value==='presidential'),'Early-midterm scope differs');
                          }
                          state.value='0';group.value='0';group.dispatchEvent(new Event('change'));
                          return {verified_point_cells:cells,selected_source_points:selected,geographies:state.options.length,
                            groups:group.options.length,native_SEs_not_margins:true,no_chart_splice:true};
                        }""", SCIENCE)
                        assert result["verified_point_cells"] == 1508 and result["geographies"] == 52
                        page.wait_for_timeout(100)
                        panel.screenshot(path=str(args.proof.with_suffix(f".{mode}.png")))
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                assert panel.locator('[data-cps-1998-download="complete"]').get_attribute("href").endswith(
                    "/participation-cps-1998-state-points-20261111-01/complete-analysis.zip")
                cases.append(dict(mode=mode, **result, no_overflow=True, console_errors=errors))
                print(json.dumps(cases[-1]), flush=True)
            finally:
                context.close()
    finally:
        browser.close()
proof = dict(status="passed_real_1998_historical_point_integration", base_url=args.base,
    source_sha256=hashlib.sha256(BODY).hexdigest(), valid_data_overrides=False, cases=cases)
args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")

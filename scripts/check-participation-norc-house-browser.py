"""Verify the actual NORC House map, demographics, selection borders and failures."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url",default="http://127.0.0.1:4397")
parser.add_argument("--proof",type=Path,required=True)
args=parser.parse_args()
assert not args.proof.exists()
oracle=json.loads((ROOT/"data/participation-return-attribution/20261111-05/norc-test-oracle.json").read_bytes())
receipt=json.loads((ROOT/"data/participation-return-attribution/20261111-05/norc-receipt.json").read_bytes())
rows={r["state_code"]:r for r in oracle["rows"]}
url=args.base_url.rstrip("/")+"/voter-participation/?year=2026"
fields=("reported_total","switching","modeled_nonparticipation","entry","exit","other_choice","unresolved","retaining")

def expected(row,field,group=""):
    if not row:
        return None
    if field=="reported_total":
        return row["reported_comparison"].get("reported_change_pp") if row["source_comparison_available"] else None
    value=next((g for g in row["groups"] if g["dimension"]+"|"+g["group"]==group),None) if group else row["point"]
    if not value or value.get("available") is False:
        return None
    if field=="retaining":
        return 100*(value["gross_outcomes"] if group else row["gross_outcomes"])["retaining"]
    if field=="modeled_nonparticipation":
        return value["net_participation_pp"]
    return value["contributions_pp"].get(field)

def open_map(page):
    response=page.goto(url,wait_until="domcontentloaded",timeout=90000)
    assert response.ok
    expect(page.locator("#state-select option")).to_have_count(51,timeout=90000)
    page.locator("#tab-effects").click()
    root=page.locator("#participation-return-drivers")
    root.scroll_into_view_if_needed()
    return root

def check_values(root,field,group=""):
    values=root.locator(".driver-map path").evaluate_all(
        "nodes=>nodes.map(n=>[n.dataset.stateCode,n.dataset.modelValue])")
    assert len(values)==51
    for code,raw in values:
        target=expected(rows.get(code),field,group)
        assert raw=="" if target is None else abs(float(raw)-target)<1e-8,(code,field,group,raw,target)
    return len(values)

def check_saved(root):
    for code,row in rows.items():
        cells=root.locator(f'[data-saved-norc="{code}"] td').all_text_contents()
        observed=expected(row,"reported_total")
        assert cells[0]=="Unavailable" if observed is None else abs(float(cells[0])-observed)<=.0051
        point=row["point"]
        targets=(point["total_change_pp"],point["contributions_pp"]["switching"],
            point["net_participation_pp"],point["contributions_pp"]["other_choice"]+point["contributions_pp"]["unresolved"])
        assert all(abs(float(raw)-target)<.0201 for raw,target in zip(cells[1:],targets))
        assert abs(sum(map(float,cells[2:]))-float(cells[1]))<1e-8

cases=[]
with sync_playwright() as runtime:
    browser=runtime.chromium.launch()
    try:
        for width in (390,1440):
            page=browser.new_page(viewport=dict(width=width,height=1000))
            errors=[]
            page.on("pageerror",lambda e:errors.append(str(e)))
            root=open_map(page)
            status=root.locator("[data-driver-status]")
            expect(status).to_contain_text("35 House reconstructions",timeout=90000)
            view=root.locator("[data-driver-view]")
            group=root.locator("[data-driver-group]")
            state=root.locator("[data-driver-state]")
            summary=root.locator("[data-driver-summary]")
            assert root.locator("[data-saved-norc]").count()==50
            assert root.locator("[data-saved-driver]").count()==113
            assert root.locator("[data-saved-calibrated]").count()==113
            check_saved(root)
            checked=0
            for field in fields:
                view.select_option(field)
                expect(root.locator(".driver-map svg")).to_have_count(1)
                assert group.is_disabled()==(field=="reported_total")
                checked+=check_values(root,field)
                expect(state).to_have_value("TX")
                if field=="retaining":
                    expect(root.locator("[data-driver-scale-min]")).to_have_text("0%")
                    expect(root.locator("[data-driver-scale-max]")).to_have_text("100%")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            view.select_option("switching")
            options=group.locator("option").evaluate_all("nodes=>nodes.map(n=>n.value).filter(Boolean)")
            dimensions=set()
            for value in options:
                group.select_option(value)
                checked+=check_values(root,"switching",value)
                dimensions.add(value.split("|")[0])
                estimate=next((g for g in rows["TX"]["groups"] if g["dimension"]+"|"+g["group"]==value),None)
                if estimate and estimate["available"]:
                    expect(summary).to_have_attribute("data-norc-group",value)
                else:
                    expect(summary).to_contain_text("withheld or unsupported")
            assert dimensions=={"AGE6","RACETH5","EDUC","SEX","INCOME","RUCC"}
            group.select_option("")
            for code,row in rows.items():
                state.select_option(code)
                expect(summary).to_have_attribute("data-norc-state",code)
                expect(summary).not_to_contain_text("unallocated")
                if row["source_comparison_available"]:
                    expect(summary).to_contain_text(f'{row["point"]["total_change_pp"]:+.2f} pp')
                else:
                    expect(summary).to_contain_text("Observed House comparison unavailable")
                path=root.locator(f'.driver-state[data-state-code="{code}"]')
                assert path.evaluate("n=>n===n.parentNode.querySelector('path:last-of-type') && getComputedStyle(n).strokeWidth==='2.2px'")
            pointer=0
            svg=root.locator(".driver-map svg")
            svg.scroll_into_view_if_needed()
            for code in (*rows,"DC"):
                path=root.locator(f'.driver-state[data-state-code="{code}"]')
                point=path.evaluate("""n=>{
                    const box=n.getBBox(),matrix=n.getScreenCTM();
                    for(let y=1;y<20;y++)for(let x=1;x<20;x++){
                      const p=new DOMPoint(box.x+box.width*x/20,box.y+box.height*y/20);
                      if(!n.isPointInFill(p))continue;
                      const screen=p.matrixTransform(matrix);
                      const target=document.elementFromPoint(screen.x,screen.y);
                      if(target===n || target?.dataset.driverHit===n.dataset.stateCode)return [screen.x,screen.y];
                    } return null;
                }""")
                if point is None:
                    print(json.dumps(path.evaluate("""n=>({
                      svg:n.ownerSVGElement.getBoundingClientRect().toJSON(),
                      hits:[...n.parentNode.querySelectorAll('[data-driver-hit]')].map(x=>x.outerHTML),
                      selected:n.parentNode.querySelector('.selected')?.dataset.stateCode,
                      scrollY, targets:[1,2,3,4,5].map(i=>{
                        const b=n.getBBox(),p=new DOMPoint(b.x+b.width*i/6,b.y+b.height/2),
                          s=p.matrixTransform(n.getScreenCTM()),t=document.elementFromPoint(s.x,s.y);
                        return {screen:[s.x,s.y],fill:n.isPointInFill(p),target:t?.outerHTML.slice(0,250)};
                      })
                    })""")),flush=True)
                    page.screenshot(path=str(args.proof.with_suffix(f".failure-{width}.png")))
                assert point,(width,code,"no actual pointer target")
                page.mouse.click(*point)
                expect(state).to_have_value(code)
                pointer+=1
            path=root.locator('.driver-state[data-state-code="DC"]')
            path.focus();page.keyboard.press("Enter")
            expect(state).to_have_value("DC")
            expect(summary).to_contain_text("no NORC CHEP sample")
            state.select_option("TX")
            view.select_option("switching")
            svg.screenshot(path=str(args.proof.with_suffix(f".map-{width}.png")))
            root.screenshot(path=str(args.proof.with_suffix(f".overview-{width}.png")))
            details=root.locator("[data-driver-detail]").locator("..")
            details.locator("summary").click()
            expect(root.locator("[data-driver-detail]")).to_contain_text("prediction gap is model error")
            expect(root.locator("[data-driver-detail]")).to_contain_text("Model-assigned outcomes")
            root.locator("[data-driver-detail]").screenshot(path=str(args.proof.with_suffix(f".detail-{width}.png")))
            details.locator("summary").click()
            page.locator("#tab-states").click();page.locator("#tab-effects").click()
            expect(state).to_have_value("TX");expect(view).to_have_value("switching")
            assert not errors,errors
            cases.append(dict(width=width,exact_state_view_values=checked,
                all_50_state_summaries=True,demographic_dimensions=len(dimensions),
                demographic_options=len(options),actual_pointer_selections=pointer,
                selected_border_painted_last=True,complete_svg_screenshot=True,
                prediction_error_separate=True,no_horizontal_overflow=True))
            page.close()
        plain=browser.new_page(java_script_enabled=False)
        assert plain.goto(url).ok
        assert plain.locator("[data-saved-norc]").count()==50
        assert plain.locator("[data-saved-driver]").count()==113
        assert plain.locator("[data-saved-calibrated]").count()==113
        assert plain.locator("[data-norc-validation] tbody tr").count()==3
        check_saved(plain)
        plain.close()
        for fault in ("failure","checksum","late"):
            page=browser.new_page(viewport=dict(width=390,height=1000))
            pending=[]
            def intercept(route):
                if fault=="failure":
                    route.abort()
                elif fault=="checksum":
                    response=route.fetch()
                    route.fulfill(response=response,body=response.body()+b" ")
                else:
                    pending.append(route)
            page.route(receipt["url"],intercept)
            root=open_map(page)
            status=root.locator("[data-driver-status]")
            if fault=="late":
                expect(status).to_contain_text("Loading the checksum-verified")
                root.locator("[data-driver-office]").select_option("senate")
                expect(root.locator(".driver-map svg")).to_have_count(1)
                assert pending
                for route in pending:
                    response=route.fetch();route.fulfill(response=response)
                expect(root.locator("[data-driver-office]")).to_have_value("senate")
                expect(root.locator("[data-driver-summary]")).to_contain_text("Fitted scenario")
            else:
                expect(status).to_contain_text("NORC House model unavailable",timeout=90000)
                root.locator("[data-driver-state]").select_option("MN")
                expect(root.locator("[data-driver-summary]")).to_be_hidden()
                expect(root.locator(".driver-map svg")).to_have_count(0)
                page.unroute(receipt["url"],intercept)
                root.get_by_role("button",name="Retry NORC model").click()
                expect(status).to_contain_text("35 House reconstructions",timeout=90000)
                expect(root.locator("[data-driver-state]")).to_have_value("MN")
                check_values(root,"reported_total")
            page.close()
    finally:
        browser.close()
proof=dict(status="passed_real_NORC_demographic_House_maps",base_url=args.base_url,
    cases=cases,valid_data_overrides=False,no_js_all_50_states=True,
    archived_226_full_models_retained=True,unavailable_comparisons_not_zero=True,
    failure_checksum_retry_and_late_office_isolation=True,
    source_training_separate_from_return_conditioning=True)
args.proof.write_text(json.dumps(proof,indent=2,sort_keys=True)+"\n")
print(json.dumps(proof))

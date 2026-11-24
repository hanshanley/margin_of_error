"""Verify actual all-state source maps, qualified legacy views and reader failures."""

import argparse
import asyncio
import gzip
import hashlib
import json
import math
from pathlib import Path

from playwright.async_api import async_playwright, expect

METRICS={"source_total":"total_change","source_switching":"switching",
    "source_participation":"net_participation","source_entry":"entry","source_exit":"exit",
    "source_other":"other_choice","source_unresolved":"unresolved","source_retaining":"retaining"}
ROOT="#participation-return-drivers"

def metric(row,key,group):
    if row is None:return None
    item=next((g for g in row["groups"] if g["dimension"]+"|"+g["group"]==group),None) if group else row
    if not item or not item["available"]:return None
    if key=="retaining":return (item["gross_outcomes"] or {}).get("retaining")
    if key=="total_change":return item["point"]["allocated_change_pp"]
    if key=="net_participation":return item["point"]["net_participation_pp"]
    return item["point"]["contributions_pp"][key]

async def boot(page,base):
    response=await page.goto(base+"/voter-participation/?view=effects",wait_until="domcontentloaded")
    assert response.ok
    await page.locator("#tab-effects").click()

async def ready(page):
    await expect(page.locator(ROOT+" [data-driver-map] path.driver-state")).to_have_count(51,timeout=60000)
    await expect(page.locator(ROOT+" [data-driver-family]")).to_be_enabled(timeout=60000)

async def choose(page,control,value):
    node=page.locator(ROOT+f" [data-driver-{control}]")
    if await node.input_value()!=value:
        await node.select_option(value)
        await ready(page)

async def map_values(page,profiles,profile,family,units,view,group=""):
    await page.wait_for_function("""wanted=>{
      const e=document.querySelector('[data-driver-map]'),d=e.dataset;
      return d.sourceModelProfile===wanted.profile && d.sourceModelFamily===wanted.family
        && d.sourceModelUnits===wanted.units && d.driverMap===wanted.view
        && d.sourceModelGroup===wanted.group && e.querySelectorAll('path.driver-state').length===51;
    }""",arg={"profile":profile,"family":family,"units":units,"view":view,"group":group},timeout=60000)
    actual=await page.locator(ROOT+" [data-driver-map] path.driver-state").evaluate_all(
        "es=>Object.fromEntries(es.map(e=>[e.dataset.stateCode,e.dataset.modelValue]))")
    rows={r["state_code"]:r for r in profiles[profile]["models"][family]["rows"]}
    assert set(actual)==set(rows)|{"DC"}
    scale=100 if view=="source_retaining" else .5 if units=="democratic_two_party_share" else 1
    known=0
    for code,value in actual.items():
        expected=metric(rows.get(code),METRICS[view],group)
        if expected is None:assert value=="",(code,view,group,value)
        else:
            assert value!="" and math.isfinite(float(value))
            assert abs(float(value)-expected*scale)<3e-8,(code,profile,family,units,view,group,value,expected*scale)
            known+=1
    if not group:assert known==50
    return len(actual)

async def normal(browser,args,profiles,width):
    context=await browser.new_context(viewport={"width":width,"height":1000},
        is_mobile=width<500,has_touch=width<500)
    page=await context.new_page();errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
    await boot(page,args.base);await ready(page)
    await expect(page.locator(ROOT+" [data-driver-view]")).to_have_value("source_total")
    assert await page.locator(ROOT+" [data-driver-geography]").is_hidden()
    assert await page.locator(ROOT+" [data-driver-map] svg").count()==1
    await expect(page.locator("[data-statewide-source-state]")).to_have_count(50)
    await page.locator(ROOT).scroll_into_view_if_needed()
    image=args.output.with_name(args.output.stem+f"-{width}.png")
    await page.screenshot(path=str(image),full_page=False)
    await page.locator(ROOT+" .driver-options").evaluate("e=>e.open=true")
    cases=values=0
    for profile in profiles:
        await choose(page,"association",profile)
        for family in profiles[profile]["models"]:
            await choose(page,"family",family)
            for units in ("democratic_two_party_share","margin"):
                await choose(page,"units",units)
                for view in METRICS:
                    await choose(page,"view",view)
                    values+=await map_values(page,profiles,profile,family,units,view);cases+=1
        print(json.dumps({"width":width,"profile":profile,"map_cases_passed":cases,"exact_values":values}),flush=True)
    await choose(page,"association","original")
    family="accepted_ridge_multinomial"
    await choose(page,"family",family);await choose(page,"units","democratic_two_party_share")
    groups=await page.locator(ROOT+" [data-driver-group] option").evaluate_all("es=>es.map(e=>e.value)")
    for group in groups:
        await choose(page,"group",group)
        for view in ("source_switching","source_retaining"):
            await choose(page,"view",view)
            values+=await map_values(page,profiles,"original",family,"democratic_two_party_share",view,group);cases+=1
    await choose(page,"group","");await choose(page,"view","source_total")
    states=list(profiles["original"]["models"][family]["rows"])
    for row in states:
        code=row["state_code"];await page.locator(ROOT+" [data-driver-state]").select_option(code)
        await expect(page.locator(ROOT+" [data-driver-summary]")).to_have_attribute("data-source-model-state",code)
        await expect(page.locator(ROOT+" [data-driver-summary]")).to_contain_text("source-model estimate")
        text=await page.locator(ROOT+" [data-driver-summary] .driver-equation > p").first.inner_text()
        assert abs(float(text.split(" pp")[0])-row["point"]["allocated_change_pp"]/2)<=.0050000001
    for code in ("TX","CA","WI"):
        await page.locator(ROOT+f' path.driver-state[data-state-code="{code}"]').click()
        await choose(page,"view","source_participation")
        await expect(page.locator(ROOT+" [data-driver-state]")).to_have_value(code)
        await expect(page.locator(ROOT+" [data-driver-summary]")).to_have_attribute("data-source-model-state",code)
        await choose(page,"view","source_total")
    await choose(page,"view","source_retaining")
    await expect(page.locator(ROOT+" [data-driver-summary]")).to_contain_text("%")
    assert all("%" not in text and " pp" in text for text in await page.locator(ROOT+" [data-driver-detail] td").all_text_contents())
    await choose(page,"view","switching")
    await expect(page.locator(ROOT+" [data-driver-map]")).to_have_attribute("data-driver-map","switching")
    await expect(page.locator(ROOT+" [data-driver-map] path.driver-state")).to_have_count(51)
    held=await page.locator(ROOT+" path.driver-state").evaluate_all("es=>es.filter(e=>e.dataset.modelValue==='').map(e=>e.dataset.stateCode).sort()")
    assert held==sorted("AK AL CA FL IL KY LA MA ME MS NC NJ NV OK TX WA WI DC".split()),held
    await choose(page,"view","source_total")
    for office in ("senate","governor"):
        await page.locator(ROOT+" [data-driver-office]").select_option(office)
        await expect(page.locator(ROOT+" [data-driver-map]")).to_have_attribute("data-driver-map","reported_total")
        await page.locator(ROOT+" [data-driver-office]").select_option("house")
        await expect(page.locator(ROOT+" [data-driver-view]")).to_have_value("source_total")
        await ready(page)
    await page.locator(ROOT+" [data-driver-state]").select_option("DC")
    await expect(page.locator(ROOT+" [data-driver-summary]")).to_contain_text("no CHEP sample")
    assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
    assert not errors,errors
    await context.close()
    context=await browser.new_context(java_script_enabled=False,viewport={"width":width,"height":1000})
    page=await context.new_page();await page.goto(args.base+"/voter-participation/#participation-return-drivers")
    table=page.locator("[data-statewide-source-table]")
    await page.evaluate("document.fonts.ready")
    await expect(table.locator("summary")).to_be_visible()
    await table.locator("summary").press("Enter");await expect(table.locator("tbody tr")).to_have_count(50)
    await expect(table.locator("tbody")).to_be_visible()
    saved=await table.locator("tbody tr").evaluate_all("es=>Object.fromEntries(es.map(e=>[e.dataset.statewideSourceState,[...e.querySelectorAll('td')].map(e=>e.textContent)]))")
    for row in states:
        expected=[row["point"]["allocated_change_pp"],row["point"]["contributions_pp"]["switching"],
            row["point"]["net_participation_pp"],row["point"]["contributions_pp"]["other_choice"],row["point"]["contributions_pp"]["unresolved"]]
        assert all(abs(float(text)-value/2)<=.0050000001 for text,value in zip(saved[row["state_code"]],expected))
    assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
    await context.close()
    return {"width":width,"cases":cases,"exact_map_values":values,"state_selections":50,
        "physical_state_clicks":3,"legacy_hold_mask_preserved":True,"nojs_saved_rows":50,
        "screenshot":image.name,"screenshot_sha256":hashlib.sha256(image.read_bytes()).hexdigest()}

async def faults(browser,args):
    context=await browser.new_context(viewport={"width":390,"height":900})
    page=await context.new_page();errors=[];page.on("pageerror",lambda e:errors.append(str(e)))
    async def unavailable(route):await route.fulfill(status=503,body="Injected source-only outage")
    pattern="**/house/statewide-source/*.json.gz"
    await page.route(pattern,unavailable);await boot(page,args.base)
    await expect(page.get_by_role("button",name="Retry statewide source model")).to_be_visible(timeout=60000)
    assert await page.locator(ROOT+" [data-driver-map] path").count()==0
    await page.locator("[data-statewide-source-table] summary").click()
    await expect(page.locator("[data-statewide-source-table] tbody tr")).to_have_count(50)
    await page.unroute(pattern,unavailable)
    await page.get_by_role("button",name="Retry statewide source model").click();await ready(page)
    assert await page.locator(ROOT+" [data-source-model=true]").count()==50
    await context.close()
    context=await browser.new_context();page=await context.new_page()
    started=asyncio.Event()
    async def delayed(route):
        started.set();await asyncio.sleep(2);await route.continue_()
    await page.route("**/house/statewide-source/original.json.gz",delayed)
    await boot(page,args.base);await asyncio.wait_for(started.wait(),60)
    await page.locator(ROOT+" [data-driver-state]").select_option("CA")
    await page.locator(ROOT+" [data-driver-view]").select_option("source_participation")
    await page.locator(ROOT+" [data-driver-office]").select_option("senate")
    await expect(page.locator(ROOT+" [data-driver-map]")).to_have_attribute("data-driver-map","reported_total",timeout=60000)
    await page.locator(ROOT+" [data-driver-office]").select_option("house");await ready(page)
    await expect(page.locator(ROOT+" [data-driver-view]")).to_have_value("source_participation")
    await expect(page.locator(ROOT+" [data-driver-state]")).to_have_value("CA")
    await context.close()
    assert not errors,errors
    context=await browser.new_context();page=await context.new_page()
    async def bad_optional(route):
        response=await route.fetch();value=await response.json()
        value["house_sources"]["statewide_source_models"]={"contract":"injected-invalid-optional-source"}
        await route.fulfill(status=200,json=value)
    await page.route("**/automatic/latest.json",bad_optional)
    await boot(page,args.base);await ready(page)
    assert await page.locator(ROOT+" [data-source-model=true]").count()==50
    assert await page.locator(ROOT).get_attribute("data-automatic-runtime")!="fallback"
    await page.locator(ROOT+" .driver-options").evaluate("e=>e.open=true")
    await choose(page,"view","switching")
    assert await page.locator(ROOT).get_attribute("data-automatic-runtime")!="fallback"
    await context.close()
    context=await browser.new_context();page=await context.new_page();saved_requests=[];corrupted=[]
    page.on("request",lambda request:saved_requests.append(request.url) if "/voter-participation/" in request.url and "/house/statewide-source/" in request.url else None)
    async def corrupt_automatic(route):
        if "/automatic/versions/" in route.request.url:
            corrupted.append(route.request.url)
            await route.fulfill(status=200,body=b"Injected wrong-hash profile body")
        else:await route.continue_()
    await page.route("**/house/statewide-source/original.json.gz",corrupt_automatic)
    await boot(page,args.base);await ready(page)
    assert await page.locator(ROOT+" [data-source-model=true]").count()==50
    assert corrupted,"The active automatic runtime does not yet expose the new source profile"
    assert saved_requests,"The full saved source bundle was not fetched after automatic-profile rejection"
    await context.close()
    return {"source_outage_clears_map":True,"saved_table_retained":True,"retry_recovers_50_states":True,
        "late_source_cannot_overwrite_office":True,"early_state_selection_retained":True,
        "invalid_optional_source_does_not_poison_comparisons":True,"wrong_hash_uses_whole_saved_bundle":True}

async def main(args):
    profiles={key:json.loads(gzip.decompress((args.product/f"house/statewide-source/{key}.json.gz").read_bytes()))
              for key in ("original","attenuated","full")}
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        results=[]
        if not args.faults_only:
            for width in args.widths:results.append(await normal(browser,args,profiles,width))
        failures=await faults(browser,args) if not args.skip_faults else None
        await browser.close()
    proof={"status":"passed","base":args.base,"production":args.base.startswith("https://www.themarginoferror.com"),
        "normal_cases_use_source_or_script_overrides":False,"normal":results,"injected_faults":failures}
    args.output.write_text(json.dumps(proof,indent=2)+"\n");print(json.dumps(proof))

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base",default="http://127.0.0.1:8436")
    parser.add_argument("--product",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--widths",nargs="+",type=int,default=[1280,390])
    parser.add_argument("--skip-faults",action="store_true")
    parser.add_argument("--faults-only",action="store_true")
    asyncio.run(main(parser.parse_args()))

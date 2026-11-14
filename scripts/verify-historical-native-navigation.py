"""Exercise real state-navigation events against an explicit private data fixture."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", required=True)
parser.add_argument("--dataset", type=Path, required=True)
parser.add_argument("--download", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--expected-stale", action="store_true")
args = parser.parse_args()
assert not args.output.exists()
description = json.loads((args.dataset / "dataset.json").read_bytes())
catalog_url = "https://raw.githubusercontent.com/hanshanley/margin_of_error/participation-data/catalog.json"
with urlopen(catalog_url, timeout=180) as response:
    catalog = json.loads(response.read())
prefix = ("https://raw.githubusercontent.com/hanshanley/margin_of_error/"
          "b7710197a3c5e019e68666e871f290356adbfd57/datasets/"
          + description["id"] + "/" + description["version"] + "/")
description.update(status="loaded", base_url=prefix,
                   staged_commit="b7710197a3c5e019e68666e871f290356adbfd57",
                   complete_download=json.loads(args.download.read_bytes()))
catalog["datasets"][description["id"]] = description
fixtures = {}
for name, declaration in description["files"].items():
    body = (args.dataset / name).read_bytes()
    assert len(body) == declaration["bytes"]
    assert hashlib.sha256(body).hexdigest() == declaration["sha256"]
    fixtures[prefix + name] = body
records = {
    code: {row["id"]: row for row in json.loads(gzip.decompress(
        fixtures[prefix + "states/" + code + ".json.gz"]))["records"]}
    for code in ("AL", "CA")
}
errors, cases = [], []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in (1440, 390):
            context = browser.new_context(viewport={"width": width, "height": 1000})
            try:
                pending = []

                def fulfill(route):
                    url = route.request.url.split("?")[0]
                    headers = {"access-control-allow-origin": "*", "content-type": "application/octet-stream"}
                    if url == catalog_url:
                        route.fulfill(status=200, body=json.dumps(catalog).encode(), headers=headers)
                    elif url == prefix + "states/AL.json.gz" and not pending:
                        pending.append(route)
                    elif url in fixtures:
                        route.fulfill(status=200, body=fixtures[url], headers=headers)
                    else:
                        route.continue_()

                context.route("https://raw.githubusercontent.com/**", fulfill)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.set_default_timeout(90000)
                page.goto(args.base.rstrip("/") + "/voter-participation/"
                          "?view=states&year=2018&state=Alabama&mode=available",
                          wait_until="domcontentloaded", timeout=90000)
                panel = page.locator("#historical-native-counts")
                expect(panel).to_be_visible()
                with page.expect_request(lambda request: request.url == prefix + "states/AL.json.gz"):
                    panel.locator(":scope > summary").click()
                for _ in range(100):
                    if pending:
                        break
                    page.wait_for_timeout(10)
                assert len(pending) == 1
                page.locator("#state-select").select_option("California")
                expect(page.locator("#state-select")).to_have_value("California")
                if args.expected_stale:
                    expect(panel.locator(":scope > summary")).to_contain_text("Alabama")
                else:
                    expect(panel.locator(":scope > summary")).to_contain_text("California")
                    expect(panel.locator("tbody tr")).not_to_have_count(0)
                    ids = panel.locator("tbody tr").evaluate_all("rows => rows.map(row => row.dataset.recordId)")
                    assert set(ids) <= set(records["CA"])
                pending[0].fulfill(status=200, body=fixtures[prefix + "states/AL.json.gz"], headers={
                    "access-control-allow-origin": "*", "content-type": "application/octet-stream",
                })
                expect(panel.locator("tbody tr")).not_to_have_count(0)
                page.wait_for_timeout(250)
                ids = panel.locator("tbody tr").evaluate_all("rows => rows.map(row => row.dataset.recordId)")
                expected_code = "AL" if args.expected_stale else "CA"
                assert set(ids) <= set(records[expected_code])
                assert not set(ids) & set(records["CA" if args.expected_stale else "AL"])
                if not args.expected_stale:
                    page.get_by_role("button", name="Reset map view", exact=True).click()
                    shape = page.locator('#visualization path[data-state="Alabama"]')
                    shape.scroll_into_view_if_needed()
                    point = shape.evaluate("""node => {
                        const b=node.getBBox(),m=node.getScreenCTM();
                        for(let y=1;y<20;y++)for(let x=1;x<20;x++){
                            const q=new DOMPoint(b.x+b.width*x/20,b.y+b.height*y/20);
                            if(!node.isPointInFill(q))continue;
                            const p=q.matrixTransform(m);
                            if(p.x>0&&p.x<innerWidth&&p.y>0&&p.y<innerHeight
                                &&document.elementFromPoint(p.x,p.y)===node)return {x:p.x,y:p.y};
                        }
                        throw new Error('No visible Alabama interior point');
                    }""")
                    page.mouse.click(point["x"], point["y"])
                    expect(page.locator("#state-select")).to_have_value("Alabama")
                    expect(panel.locator(":scope > summary")).to_contain_text("Alabama")
                    expect(panel.locator("tbody tr")).not_to_have_count(0)
                    ids = panel.locator("tbody tr").evaluate_all("rows => rows.map(row => row.dataset.recordId)")
                    assert set(ids) <= set(records["AL"])
                    page.locator("#year").select_option("2026")
                    expect(panel).to_be_hidden()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                cases.append({"width": width, "selected_state": "California",
                              "stale_alabama_response_released": True,
                              "rendered_state": expected_code,
                              "real_dropdown_and_map_navigation": not args.expected_stale})
            finally:
                context.close()
    finally:
        browser.close()
assert not errors, errors
proof = {
    "passed": not args.expected_stale, "expected_stale_bug_confirmed": args.expected_stale,
    "actual_production_acceptance": False, "explicit_private_candidate_data_fixture": True,
    "source_or_dom_or_style_overrides": False,
    "candidate_dataset_routes_overridden": True,
    "download_metadata_is_verified_predecessor_for_ui_schema_only": True,
    "dataset_version": description["version"], "cases": cases,
    "browser_errors": errors, "all_browsers_closed": True,
}
with args.output.open("x") as stream:
    json.dump(proof, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps(proof))

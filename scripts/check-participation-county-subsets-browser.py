import argparse
import asyncio
import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import async_playwright, expect


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ".substate-feature[data-results-status]"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    descriptor = json.loads((ROOT / "public/county-candidate-subsets.json").read_bytes())["states"]["ME"]
    body = (ROOT / "data/county-candidate-subsets/20261117-maine-01/county-subsets.json.gz").read_bytes()
    assert len(body) == descriptor["bytes"] and hashlib.sha256(body).hexdigest() == descriptor["sha256"]
    data = json.loads(gzip.decompress(body))
    expected = {row["geography"]: row for row in data["rows"]}
    query = urlencode({"view": "states", "year": 2026, "basis": "cvap", "dimension": "overall",
        "group": "All groups", "map-color": "margin", "map-level": "county",
        "mode": "available", "state": "Maine"})
    url = args.base.rstrip("/") + "/voter-participation/?" + query
    outcomes = []
    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch()
        try:
            for width in (1440, 390):
                page = await browser.new_page(viewport={"width": width, "height": 1100})
                errors, requests = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: requests.append(request.url))
                await page.goto(url, wait_until="domcontentloaded", timeout=120000)
                await expect(page.locator(SELECTOR + '[data-color-level="county-margin-bound"]')).to_have_count(16, timeout=120000)
                await expect(page.locator("#title")).to_have_text("County election results in Maine")
                actual = await page.locator(SELECTOR).evaluate_all("""paths => paths.map(p => ({
                    ...p.dataset, fill:p.getAttribute('fill'), label:p.getAttribute('aria-label')
                }))""")
                assert {row["geography"] for row in actual} == set(expected)
                for item in actual:
                    row = expected[item["geography"]]
                    assert int(item["democraticVotes"]) == row["democratic_votes"]
                    assert int(item["republicanVotes"]) == row["republican_votes"]
                    assert int(item["knownCandidateVotes"]) == row["known_candidate_votes"]
                    assert int(item["unlocatedOtherBound"]) == row["unlocated_other_upper_bound"]
                    assert abs(float(item["marginLower"]) - row["margin_bounds_pp"][0]) < 1e-10
                    assert abs(float(item["marginUpper"]) - row["margin_bounds_pp"][1]) < 1e-10
                    assert item["sourceRound"] == "1" and item["boundaryYear"] == "2026"
                    assert item["resultsStatus"] == ("dated_complete_vector" if row["complete_vector_qualified"]
                                                     else "partial_candidate_coverage")
                    assert item["fill"] not in (None, "#d6d3cb", "none")
                    assert "retained round 1" in item["label"]
                await expect(page.locator("#table-body tr")).to_have_count(16)
                await expect(page.locator("#subtitle")).to_contain_text("2026-11-07")
                await expect(page.locator("#measure")).to_contain_text("incomplete Other remains unallocated")
                await expect(page.locator("#substate-detail")).to_contain_text("not latest/final")
                for label, field in (("Complete county counts", "complete_download_url"),
                                     ("All county results (CSV)", "csv_url")):
                    await expect(page.locator("#substate-detail").get_by_role("link", name=label, exact=False)).to_have_attribute("href", descriptor[field])
                assert "All county results (CSV) Original complete-result hold" in await page.locator("#substate-detail").text_content()
                await page.locator("svg.turnout-map").scroll_into_view_if_needed()
                await page.wait_for_timeout(700)
                screenshot = args.output.with_name(args.output.stem + "-" + str(width) + ".png")
                await page.screenshot(path=str(screenshot))
                point = await page.locator(SELECTOR + '[data-geography="23005"]').evaluate("""p => {
                    const b=p.getBBox(), matrix=p.getScreenCTM();
                    for(let i=1;i<20;i++) for(let j=1;j<20;j++) {
                      const q=new DOMPoint(b.x+b.width*i/20,b.y+b.height*j/20);
                      if(p.isPointInFill(q)) { const s=q.matrixTransform(matrix);
                        if(s.x>0&&s.x<innerWidth&&s.y>0&&s.y<innerHeight
                          && document.elementFromPoint(s.x,s.y)?.closest('[data-geography]')===p)
                          return {x:s.x,y:s.y}; }
                    }
                    throw Error('No visible county interior');
                }""")
                await page.mouse.click(point["x"], point["y"])
                await expect(page.locator("#substate-detail h4")).to_have_text(expected["23005"]["geography_name"])
                detail_image = args.output.with_name(args.output.stem + "-detail-" + str(width) + ".png")
                await page.locator("#substate-detail").scroll_into_view_if_needed()
                await page.screenshot(path=str(detail_image))
                for key, row in expected.items():
                    shape = page.locator(SELECTOR + f'[data-geography="{key}"]')
                    await shape.focus()
                    await page.keyboard.press("Enter")
                    await expect(page.locator("#substate-detail h4")).to_have_text(row["geography_name"])
                    await expect(page.locator("#substate-detail")).to_contain_text(f'{row["democratic_votes"]:,} Democratic')
                    await expect(page.locator("#substate-detail")).to_contain_text(f'{row["republican_votes"]:,} Republican')
                    if row["unlocated_other_upper_bound"]:
                        await expect(page.locator("#substate-detail")).to_contain_text("total and Other are not fully located")
                await page.locator("#state-select").select_option("California")
                await expect(page.locator('.substate-feature[data-geography^="06"]')).not_to_have_count(0, timeout=120000)
                await expect(page.locator(SELECTOR + '[data-geography^="23"]')).to_have_count(0)
                await page.locator("#state-select").select_option("Maine")
                await expect(page.locator(SELECTOR + '[data-color-level="county-margin-bound"]')).to_have_count(16, timeout=120000)
                assert requests.count(descriptor["url"]) == 1
                assert not errors, errors
                assert not await page.evaluate("document.documentElement.scrollWidth > innerWidth")
                outcomes.append({"width": width, "counties": 16, "native_count_cells": 32,
                    "physical_county_click": True, "keyboard_selections": 16, "cached_reload": True,
                    "page_errors": errors, "image": screenshot.name,
                    "image_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                    "detail_image": detail_image.name,
                    "detail_image_sha256": hashlib.sha256(detail_image.read_bytes()).hexdigest()})
                await page.close()
            for fault in ("http503", "checksum", "delayed"):
                page = await browser.new_page(viewport={"width": 1440, "height": 1100})
                arrived, release = asyncio.Event(), asyncio.Event()

                async def intercept(route):
                    if fault == "http503":
                        await route.fulfill(status=503, body="Temporarily unavailable")
                    elif fault == "checksum":
                        await route.fulfill(status=200, body=b"changed body",
                                            content_type="application/octet-stream")
                    else:
                        response = await route.fetch()
                        arrived.set()
                        await release.wait()
                        await route.fulfill(response=response)

                await page.route(descriptor["url"], intercept)
                await page.goto(url, wait_until="domcontentloaded", timeout=120000)
                if fault == "delayed":
                    await asyncio.wait_for(arrived.wait(), timeout=120)
                    await page.locator("#state-select").select_option("California")
                    await expect(page.locator('.substate-feature[data-geography^="06"]')).not_to_have_count(0, timeout=120000)
                    release.set()
                    await page.wait_for_timeout(1500)
                    await expect(page.locator(SELECTOR + '[data-geography^="23"]')).to_have_count(0)
                    assert "state=California" in page.url
                else:
                    await expect(page.locator(SELECTOR + '[data-results-status="withheld"]')).to_have_count(16, timeout=120000)
                    await expect(page.locator(SELECTOR + "[data-democratic-votes]")).to_have_count(0)
                    await page.unroute(descriptor["url"], intercept)
                    await page.get_by_role("button", name="Retry dated county results", exact=True).click()
                    await expect(page.locator(SELECTOR + '[data-color-level="county-margin-bound"]')).to_have_count(16, timeout=120000)
                outcomes.append({"fault": fault, "passed": True,
                    "valid_source_data_replaced": False, "availability_or_corruption_injected": True})
                await page.close()
        finally:
            await browser.close()
    args.output.write_text(json.dumps({"passed": True, "base": args.base,
        "production": args.base.startswith("https://www.themarginoferror.com"),
        "normal_cases_use_actual_published_data": True, "outcomes": outcomes},
        indent=2, sort_keys=True) + "\n")
    print(args.output.read_text())


if __name__ == "__main__":
    asyncio.run(main())

"""Acquire aggregate QVF observations using only Michigan's declared public report UI."""

import argparse
import asyncio
import datetime
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mi_qvf", HERE / "review-michigan-qvf-counties.py")
mi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mi)


def county_filters(request):
    values = []
    for node in mi.tree(request):
        clause = node.get("In", {})
        if any(expression.get("Column", {}).get("Property") == "COUNTY_NAME"
               for expression in clause.get("Expressions", [])):
            values.extend(cell["Literal"]["Value"] for row in clause["Values"] for cell in row)
    return set(values)


def matching_card(root, records, name, first_sequence):
    matches = []
    for record in records:
        if (record["sequence"] < first_sequence or record["phase"] != "county:" + name
                or record["status"] != 200):
            continue
        response = mi.original(root, record["response"])
        if not any(set(item["Name"] for item in data["descriptor"]["Select"]) == set(mi.FIELDS)
                   for data in mi.packets(mi.unpack(response))):
            continue
        request = mi.original(root, record["native_request"])
        if county_filters(mi.unpack(request)) != {"'" + name + "'"}:
            continue
        values = mi.card(dict(request=request, response=response), name)
        matches.append(dict(evidence=record, native_fields=values))
    mi.require(len(matches) == 1, "Expected exactly one fully scoped native county card")
    return matches[0]


async def acquire(output, resume):
    from playwright.async_api import async_playwright, expect

    output = output.resolve()
    checkout = HERE.parent
    mi.require(not (checkout / ".git").exists()
               or (output != checkout and checkout not in output.parents),
               "Original report templates must stay outside the published repository")
    output.mkdir(parents=True, exist_ok=resume)
    queries, errors, pending, selections = [], [], [], []
    phase, sequence, attempt = "initial-statewide", 0, 0
    if resume:
        receipts = list(output.glob("acquisition-resume-*-receipt.json"))
        attempt = 1 + max([int(path.name.split("-")[2]) for path in receipts] + [0])
        previous_path = (output / ("acquisition-resume-%02d-receipt.json" % (attempt - 1))
                         if receipts else output / "acquisition-receipt.json")
        previous = json.loads(previous_path.read_text())
        mi.require(previous["declared_url"] == mi.REPORT
                   and previous["ignore_https_errors"] is False
                   and not previous["page_errors"], "Unreviewed prior acquisition")
        queries, selections = previous["native_query_responses"], previous["completed_counties"]
        sequence = max(record["sequence"] for record in queries)
        for record in queries:
            for key in ("response", "native_request"):
                if key in record:
                    mi.original(output, record[key])
    else:
        mi.require(not any(output.iterdir()), "Original output must be empty")

    def save(name, body):
        with (output / name).open("xb") as target:
            target.write(body)
        return dict(file=name, bytes=len(body), sha256=mi.sha(body))

    counties = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(ignore_https_errors=False)
        page = await context.new_page()

        async def capture(response, number, observed_phase):
            try:
                body = await response.body()
                record = dict(sequence=number, phase=observed_phase, url=response.url,
                    status=response.status, response=save("native-response-%04d.json" % number, body))
                if response.request.post_data is not None:
                    record["native_request"] = save("native-request-%04d.json" % number,
                                                  response.request.post_data.encode())
                queries.append(record)
            except Exception as error:
                errors.append(type(error).__name__ + ": " + str(error))

        def received(response):
            nonlocal sequence
            if "querydata" in response.url.lower():
                sequence += 1
                pending.append(asyncio.create_task(capture(response, sequence, phase)))

        page.on("response", received)
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            initial_sequence = sequence + 1
            async with page.expect_response(
                lambda response: "querydata" in response.url.lower() and response.ok,
                timeout=90000,
            ):
                await page.goto(mi.REPORT, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_load_state("networkidle", timeout=45000)
            if pending:
                await asyncio.gather(*pending)
            inventory_candidates = []
            for record in queries:
                if (record["phase"] != "initial-statewide" or record["status"] != 200
                        or record["sequence"] < initial_sequence):
                    continue
                evidence = mi.original(output, record["response"])
                try:
                    inventory_candidates.append((mi.native_inventory(evidence), evidence))
                except ValueError:
                    continue
            mi.require(inventory_candidates, "No complete native 83-county inventory")
            counties, inventory = inventory_candidates[0]
            mi.require([row["county"] for row in selections] == counties[:len(selections)],
                       "Prior county scope does not match the complete current inventory")
            if resume:
                prior = (output / "native-county-inventory.json").read_bytes()
                prior = dict(text=prior.decode(), bytes=len(prior), sha256=mi.sha(prior))
                mi.require(mi.native_inventory(prior) == counties,
                           "Changed complete native county inventory")
            else:
                save("native-county-inventory.json", inventory["text"].encode())
            text = await page.locator("body").inner_text()
            mi.require(mi.ELECTION in text and len(mi.CLOCK.findall(text)) == 1,
                       "Wrong rendered election or missing numeric data clock")
            save(("resume-%02d-" % attempt if resume else "") + "initial-statewide-visible-text.txt",
                 text.encode())
            county = page.get_by_role("combobox", name="Select county", exact=True)
            slicer = county.locator("xpath=ancestor::div[contains(@class,'slicer-container')][1]")
            for index, name in enumerate(counties):
                if index < len(selections):
                    continue
                if (await county.inner_text()).strip() != "All":
                    phase = "clear-before:" + name
                    if await county.get_attribute("aria-expanded") == "true":
                        await county.click()
                    await slicer.hover()
                    await slicer.get_by_role("button", name="Clear selections", exact=True).click()
                    await expect(county).to_have_text("All")
                    await page.wait_for_load_state("networkidle", timeout=45000)
                phase, first_sequence = "county:" + name, sequence + 1
                await county.click()
                await expect(county).to_have_attribute("aria-expanded", "true")
                popup = page.locator("#" + await county.get_attribute("aria-controls"))
                await popup.locator(".slicerItemContainer").first.wait_for(
                    state="visible", timeout=45000)
                search = popup.get_by_role("textbox", name="Search", exact=True)
                await search.fill("")
                await search.press_sequentially(name, delay=35)
                await expect(search).to_have_value(name)
                choice = popup.get_by_text(name, exact=True)
                await choice.wait_for(state="visible", timeout=45000)
                async with page.expect_response(
                    lambda response: "querydata" in response.url.lower() and response.ok
                    and ("'" + name + "'") in (response.request.post_data or ""), timeout=90000,
                ):
                    await choice.click()
                await expect(county).to_have_text(name)
                await page.wait_for_load_state("networkidle", timeout=45000)
                await page.get_by_text(name + " County", exact=True).wait_for(
                    state="visible", timeout=30000)
                if pending:
                    await asyncio.gather(*pending)
                selected = matching_card(output, queries, name, first_sequence)
                text = await page.locator("body").inner_text()
                mi.require(mi.ELECTION in text and len(mi.CLOCK.findall(text)) == 1,
                           "Wrong actual rendered county election or clock")
                selected.update(county=name, received_at_utc=datetime.datetime.now(
                    datetime.timezone.utc).isoformat(),
                    visible_text=save("county-%02d-visible-text.txt" % (index + 1), text.encode()),
                    dom=save("county-%02d-dom.html" % (index + 1), (await page.content()).encode()))
                selections.append(selected)
                save("county-%02d-selection.json" % (index + 1), mi.encoded(selected))
                print("%d/83 %s: %s" % (
                    index + 1, name, selected["native_fields"][mi.FIELDS[6]]), flush=True)
        finally:
            if pending:
                await asyncio.gather(*pending)
            save("final-attempt-%02d-dom.html" % attempt, (await page.content()).encode())
            save("final-attempt-%02d-visible-text.txt" % attempt,
                 (await page.locator("body").inner_text()).encode())
            save(("acquisition-resume-%02d-receipt.json" % attempt if resume
                  else "acquisition-receipt.json"), mi.encoded(dict(
                received_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                declared_url=mi.REPORT, ignore_https_errors=False, expected_counties=counties,
                completed_counties=selections, native_query_responses=sorted(
                    queries, key=lambda row: row["sequence"]), page_errors=errors,
                scope="Only ordinary public native selector/search/clear controls. Full "
                      "request/response bodies retained without headers. No custom server queries "
                      "or suppressed-cell reconstruction. QVF history is not tabulator results; "
                      "native totals can exclude unavailable modes. County exact registration "
                      "denominators are not supplied by statewide cards.")))
            await browser.close()
    mi.require(len(selections) == 83 and not errors, "Incomplete native county acquisition")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    asyncio.run(acquire(args.output, args.resume))

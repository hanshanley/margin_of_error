"""Verify the corrected public House comparisons, controls, holds and map selections."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", required=True)
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
assert not args.proof.exists()
directory = ROOT/"data/participation-return-attribution/20261112-06"
receipts = {"original": json.loads((directory/"norc-receipt.json").read_bytes()),
            **json.loads((directory/"copula-receipt.json").read_bytes())["profiles"]}
datasets = {}
for profile, receipt in receipts.items():
    with urllib.request.urlopen(receipt["url"], timeout=180) as response:
        body = response.read()
    assert len(body) == receipt["bytes"] and hashlib.sha256(body).hexdigest() == receipt["sha256"]
    datasets[profile] = json.loads(body)
fields = ("reported_total", "switching", "modeled_nonparticipation", "entry",
          "exit", "other_choice", "unresolved", "retaining")


def expected(row, field, group, units):
    if not row or not row["source_comparison_available"]:
        return None
    scale = .5 if units == "democratic_two_party_share" else 1
    if field == "reported_total":
        return row["reported_comparison"]["reported_change_pp"]*scale
    value = next((g for g in row["groups"] if g["dimension"]+"|"+g["group"] == group), None) if group else row["point"]
    if value is None or value.get("available") is False:
        return None
    if field == "retaining":
        return (value["gross_outcomes"] if group else row["gross_outcomes"])["retaining"]*100
    return scale*(value["net_participation_pp"] if field == "modeled_nonparticipation"
                  else value["contributions_pp"][field])


def check_map(root, rows, field, group, units):
    values = root.locator(".driver-state").evaluate_all(
        "nodes=>nodes.map(node=>[node.dataset.stateCode,node.dataset.modelValue])")
    assert len(values) == 51
    for code, raw in values:
        target = expected(rows.get(code), field, group, units)
        assert raw == "" if target is None else abs(float(raw)-target) < 1e-8, (code, field, group, units, raw, target)
    return len(values)


def open_map(page):
    assert page.goto(args.base_url.rstrip("/")+"/voter-participation/?year=2026",
                     wait_until="domcontentloaded", timeout=90000).ok
    expect(page.locator("#state-select option")).to_have_count(51, timeout=90000)
    page.locator("#tab-effects").click()
    root = page.locator("#participation-return-drivers")
    return root


cases = []
with sync_playwright() as runtime:
    browser = runtime.chromium.launch()
    try:
        for width in (1440, 390):
            page = browser.new_page(viewport=dict(width=width, height=1000))
            errors, requests = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append(request.url))
            root = open_map(page)
            family = root.locator("[data-driver-family]")
            association = root.locator("[data-driver-association]")
            units, view = root.locator("[data-driver-units]"), root.locator("[data-driver-view]")
            group, state = root.locator("[data-driver-group]"), root.locator("[data-driver-state]")
            summary = root.locator("[data-driver-summary]")
            expect(family).to_be_enabled(timeout=90000)
            state.select_option("PA")
            checked = 0
            for profile, data in datasets.items():
                association.select_option(profile)
                expect(summary).to_have_attribute("data-norc-association", profile, timeout=90000)
                for name, model in data["families"].items():
                    family.select_option(name)
                    rows = {row["state_code"]: row for row in model["rows"]}
                    view.select_option("switching")
                    group.select_option("")
                    for unit in ("margin", "democratic_two_party_share"):
                        view.select_option("switching")
                        units.select_option(unit)
                        for field in fields:
                            view.select_option(field)
                            checked += check_map(root, rows, field, "", unit)
                        view.select_option("switching")
                        group.select_option("AGE6|65_plus")
                        checked += check_map(root, rows, "switching", "AGE6|65_plus", unit)
                        group.select_option("")
                    expect(summary).to_have_attribute("data-norc-family", name)
                    expect(summary).to_have_attribute("data-norc-state", "PA")
            association.select_option("original")
            expect(summary).to_have_attribute("data-norc-association", "original")
            family.select_option("accepted_ridge_multinomial")
            view.select_option("switching")
            units.select_option("margin")
            model = datasets["original"]["families"]["accepted_ridge_multinomial"]
            rows = {row["state_code"]: row for row in model["rows"]}
            for selected in group.locator("option").evaluate_all("nodes=>nodes.map(n=>n.value)"):
                group.select_option(selected)
                for field in ("switching", "modeled_nonparticipation", "retaining"):
                    view.select_option(field)
                    checked += check_map(root, rows, field, selected, "margin")
            group.select_option("")
            view.select_option("reported_total")
            for code, row in rows.items():
                state.select_option(code)
                expect(summary).to_have_attribute("data-norc-state", code)
                if row["source_comparison_available"]:
                    assert summary.locator("[data-norc-mechanism]").count() == 5
                else:
                    expect(summary).to_have_attribute("data-norc-hold", "true")
                    assert summary.locator("[data-norc-mechanism]").count() == 0
                    expect(root.locator("[data-driver-detail]")).to_be_hidden()
                    expect(root.locator(f'[data-saved-norc="{code}"]')).to_contain_text("Unavailable")
            state.select_option("PA")
            root.screenshot(path=str(args.proof.with_suffix(f".PA-{width}.png")))
            path = root.locator('.driver-state[data-state-code="MA"]')
            path.scroll_into_view_if_needed()
            point = path.evaluate("""node=>{
              const b=node.getBBox(),p=node.ownerSVGElement.createSVGPoint(),m=node.getScreenCTM();
              for(let i=1;i<20;i++)for(let j=1;j<20;j++){
                p.x=b.x+b.width*i/20;p.y=b.y+b.height*j/20;
                if(node.isPointInFill(p)){const q=p.matrixTransform(m);return {x:q.x,y:q.y};}
              }throw new Error("No Massachusetts interior point");
            }""")
            page.mouse.click(point["x"], point["y"])
            expect(state).to_have_value("MA")
            expect(summary).to_contain_text("2/9")
            expect(summary).to_contain_text("5/9")
            assert "22.91" not in summary.inner_text()
            assert "5.65" not in summary.inner_text()
            root.locator('.driver-state[data-state-code="PA"]').press("Enter")
            expect(state).to_have_value("PA")
            root.locator('.driver-state[data-state-code="MA"]').press("Space")
            expect(state).to_have_value("MA")
            root.screenshot(path=str(args.proof.with_suffix(f".MA-{width}.png")))
            view.select_option("scenario_switching")
            expect(summary).to_contain_text("No archived scenario is substituted")
            assert root.locator('.driver-state[data-state-code="MA"]').get_attribute("data-model-value") == ""
            view.select_option("reported_total")
            root.locator("[data-driver-office]").select_option("senate")
            root.locator("[data-driver-office]").select_option("house")
            expect(state).to_have_value("MA")
            expect(summary).to_have_attribute("data-norc-hold", "true")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            for receipt in receipts.values():
                assert requests.count(receipt["url"]) == 1
            assert root.locator('a[href$="participation-house-comparability-20261112-01/complete-profile-family-state-comparisons.csv"]').count() == 1
            assert root.locator('a[href$="/complete-state-family-comparisons.csv"]').count() == 0
            assert not errors, errors
            cases.append(dict(width=width, exact_map_values=checked, state_selections=50,
                true_Massachusetts_pointer_selection=True, incompatible_states_unavailable_in_every_view=True,
                keyboard_enter_space_selection=True,
                corrected_CSV_not_superseded_targets=True,
                original_full_download_link_present=root.locator('a[href$="participation-house-comparability-20261112-01/complete-analysis.zip"]').count()>0,
                no_horizontal_overflow=True, per_pin_single_download=True))
            page.close()
        page = browser.new_page(viewport=dict(width=390, height=1000))
        page.route(receipts["original"]["url"], lambda route: route.abort())
        root = open_map(page)
        expect(root.locator("[data-driver-status]")).to_contain_text("No older fitted model is substituted", timeout=90000)
        assert root.locator(".driver-state").count() == 0
        page.close()
        page = browser.new_page(viewport=dict(width=390, height=1000))
        def broken_scale(route):
            response = route.fetch()
            html = response.text()
            match = re.search(r'(<script\b[^>]*\bdata-driver-data\b[^>]*>)(.*?)(</script>)', html, re.S)
            assert match
            payload = json.loads(match[2])
            payload["norc_association_sources"]["shared_max_abs_margin"]["AGE6|65_plus"] = 0
            html = html[:match.start(2)]+json.dumps(payload).replace("<", "\\u003c")+html[match.end(2):]
            route.fulfill(response=response, body=html)
        page.route("**/voter-participation/?year=2026", broken_scale)
        root = open_map(page)
        expect(root.locator("[data-driver-family]")).to_be_enabled(timeout=90000)
        root.locator("[data-driver-view]").select_option("switching")
        root.locator("[data-driver-group]").select_option("AGE6|65_plus")
        expect(root.locator("[data-driver-status]")).to_contain_text("Previous values were cleared")
        assert root.locator(".driver-state").count() == 0
        expect(root.locator("[data-driver-summary]")).to_be_hidden()
        root.locator("[data-driver-group]").select_option("")
        expect(root.locator(".driver-state")).to_have_count(51)
        page.close()
    finally:
        browser.close()
proof = dict(status="passed_corrected_House_comparability_desktop_phone", base_url=args.base_url,
    valid_data_overrides=False, intentional_source_failure_fails_closed=True,
    intentional_bad_scale_clears_and_recovers=True, cases=cases)
args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True)+"\n")
print(json.dumps(proof))

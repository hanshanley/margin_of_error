"""Exercise the built participation atlas against its saved source observations."""

import argparse
import gzip
import json
import math
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--screenshots", type=Path)
args = parser.parse_args()
url = args.base_url.rstrip("/") + "/voter-participation/"
data = Path(__file__).resolve().parents[1] / "public/voter-participation/data"
states = json.loads((data / "states.json").read_text())
national = json.loads((data / "national.json").read_text())
records = json.loads((data / "nc/2024.json").read_text())["records"]
current_pointer = json.loads((data / "current/latest.json").read_text())
current = json.loads((data / "current" / current_pointer["snapshot_id"] / "snapshot.json").read_text())
current_ballots = next(row["ballots_cast"] for row in current["reporting"] if row["county_id"] == "0")
public = data.parents[1]
context_pointer = json.loads((public / "participation-context/latest.json").read_text())
context_root = public / "participation-context" / context_pointer["snapshot_id"]
supplement_pointer = json.loads((public / "participation-current/latest.json").read_text())
supplement_root = public / "participation-current" / supplement_pointer["snapshot_id"]
nationwide = json.loads((supplement_root / "snapshot.json").read_text())
current_local = json.loads((supplement_root / "local.json").read_text())
margins = json.loads((context_root / "margins.json").read_text())
results_pointer = json.loads((public / "participation-results/latest.json").read_text())
results_root = public / "participation-results" / results_pointer["snapshot_id"]
result_rows = json.loads((results_root / "margins.json").read_text())
precinct_results_pointer = json.loads((public / "precinct-results.json").read_text())
expected_downloads = (18 + len(precinct_results_pointer.get("source_reviews", []))
                      + len(precinct_results_pointer.get("source_batches", []))
                      + 3 * len(precinct_results_pointer.get("additional_snapshots", [])))
precinct_results_root = public.parent / precinct_results_pointer["data_directory"]
precinct_results_index = json.loads((precinct_results_root / "index.json").read_text())
for snapshot in precinct_results_pointer.get("additional_snapshots", []):
    additional = json.loads((public.parent / snapshot["data_directory"] / "index.json").read_text())
    for year, codes in additional["coverage"].items():
        precinct_results_index["coverage"].setdefault(year, {}).update({
            code: dict(coverage, data_directory=snapshot["data_directory"]) for code, coverage in codes.items()
        })
margins = [row for row in margins if row["year"] != 2026] + result_rows
methods_pointer = json.loads((public / "participation-methods/latest.json").read_text())
methods_root = public / "participation-methods" / methods_pointer["snapshot_id"]
method_states = json.loads((methods_root / "states.json").read_text())
method_national = json.loads((methods_root / "national.json").read_text())
local_pointer = json.loads((public / "participation-local.json").read_text())
local_root = data.parents[2] / "data" / local_pointer["base_url"].split("/data/", 1)[1]
precinct_pointer = json.loads((public / "participation-precincts.json").read_text())
precinct_root = data.parents[2] / "data" / precinct_pointer["base_url"].split("/data/", 1)[1]
precinct_index = json.loads((precinct_root / "index.json").read_text())
current_shapes = json.loads(gzip.decompress((precinct_root / "NM.geojson.gz").read_bytes()))["features"]
selected = next(row for row in records if row["county"] == "WAKE"
                and row["precinct"] == "01-01" and row["dimension"] == "overall")
key = selected["county"] + "|" + selected["precinct"]


def screenshot(page, name):
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
        page.evaluate("document.activeElement?.blur(); window.scrollTo({top: 0, behavior: 'instant'})")
        page.screenshot(path=str(args.screenshots / name), full_page=True)


def viewport(page):
    return [float(v) for v in page.locator("svg.turnout-map").get_attribute("viewBox").split()]


def tab(page, name):
    page.get_by_role("tab", name=name, exact=True).click()


def no_overflow(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Page overflows horizontally"

def observed_ticks(page, selector):
    for chart in page.locator(selector).all():
        years = set(chart.locator(".chart-point").evaluate_all("points => points.map(p => +p.dataset.year)"))
        ticks = {int(value) for value in chart.locator(".year-tick").all_text_contents()}
        assert ticks <= years, f"Chart labels unobserved years: {ticks - years}"

def connected(page, selector, *years):
    chart = page.locator(selector)
    points = [chart.locator(f'.chart-point[data-year="{year}"]').evaluate(
        "p => p.getAttribute('cx') + ',' + p.getAttribute('cy')") for year in years]
    segments = chart.locator(".chart-line").evaluate_all(
        "paths => paths.map(p => p.getAttribute('d').match(/[ML][^ML]+/g).map(s => s.slice(1).trim()))")
    return any(all(point in segment for point in points) for segment in segments)


def result_color(margin):
    t = min(1, abs(margin) / 35)
    destination = [137, 40, 45] if margin < 0 else [37, 75, 120]
    rgb = [math.floor(c + t * (end - c) + .5) for c, end in zip([237, 232, 220], destination)]
    return "rgb(" + ",".join(map(str, rgb)) + ")"


def check_precinct_results(page, year, code):
    coverage = precinct_results_index["coverage"][str(year)][code]
    root = public.parent / coverage.get("data_directory", precinct_results_pointer["data_directory"])
    features = json.loads(gzip.decompress((root / coverage["file"]).read_bytes()))["features"]
    expected = {p["key"]: [p["margin_pp"], p["contest_votes"], result_color(p["margin_pp"])]
                for feature in features for p in [feature["properties"]]
                if feature["geometry"] and p["match_status"] == "matched" and p["margin_pp"] is not None}
    paths = page.locator('.substate-feature[data-color-level="precinct"]')
    expect(paths).to_have_count(len(expected), timeout=60000)
    actual = paths.evaluate_all(
        "paths => Object.fromEntries(paths.map(p => [p.dataset.geography, "
        "[+p.dataset.margin, +p.dataset.totalVotes, p.getAttribute('fill')]]))")
    assert actual == expected, f"{year} {code}: candidate counts/margins/colors differ from audited precinct results"
    return features


with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1360, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(url)
    expect(page.locator("#year")).to_have_value("2026")
    expect(page.locator("#provisional-status")).to_be_visible()
    expect(page.locator("#map-level")).to_have_value("precinct")
    expect(page.locator("#map-color")).to_have_value("margin")
    expect(page.locator("#map-color option[value=margin]")).to_be_enabled()
    expect(page.locator(".map-feature[data-state]")).to_have_count(51)
    check_precinct_results(page, 2026, "NC")
    names = {row["state_code"]: row["state"] for row in nationwide["coverage"]}
    expected_colors = {}
    for row in result_rows:
        if row["level"] != "state":
            continue
        expected_colors[names[row["state_code"]]] = result_color(row["margin_pp"])
    expected_colors["District of Columbia"] = "#d6d3cb"
    def result_colors(target):
        return target.locator(".map-feature[data-state]").evaluate_all(
            "paths => Object.fromEntries(paths.map(p => [p.dataset.state, p.getAttribute('fill')]))")
    assert result_colors(page) == expected_colors, "State colors must match all 50 actual election-result margins"
    expect(page.locator("#key")).to_contain_text("R+35")
    expect(page.locator("#key")).to_contain_text("D+35")
    current_codes = precinct_results_index["coverage"]["2026"]
    expect(page.locator("#coverage-note")).to_contain_text(f'{len(set(current_codes) - {"DC"})} states')
    expect(page.locator("#caption")).to_contain_text("excludes separately reported")
    screenshot(page, "participation-default-red-blue-results.png")
    page.locator("#state-select").select_option("New Mexico")
    check_precinct_results(page, 2026, "NM")
    assert result_colors(page) == expected_colors
    for detail in ["county", "district"]:
        page.locator("#map-level").select_option(detail)
        expect(page.locator("#map-color")).to_have_value("margin")
        expect(page.locator(".substate-feature")).to_have_count(0)
        assert result_colors(page) == expected_colors, f"Unavailable {detail} returns must retain whole-state result colors"
        expect(page.locator("#key")).to_contain_text("D+35")
    for detail in ["auto", "precinct"]:
        page.locator("#map-level").select_option(detail)
        check_precinct_results(page, 2026, "NM")
        assert result_colors(page) == expected_colors
    before = viewport(page)
    page.locator("#map-zoom-in").click()
    assert viewport(page)[2] < before[2]
    check_precinct_results(page, 2026, "NM")
    page.locator('.substate-feature[data-color-level="precinct"]').first.dispatch_event("click")
    expect(page.locator("#substate-detail")).to_contain_text("Democratic")
    expect(page.locator("#substate-detail")).to_contain_text("not turnout")
    assert page.locator("#substate-detail").bounding_box()["y"] < page.locator("#selection-panel h3").first.bounding_box()["y"]
    screenshot(page, "participation-2026-actual-precinct-results.png")
    for code in sorted(set(current_codes) - {"NC", "NM"}):
        page.locator("#state-select").select_option(names[code])
        shapes = check_precinct_results(page, 2026, code)
        if code == "DC":
            path = page.locator('.substate-feature[data-color-level="precinct"]').first
            bounds = path.evaluate("p => { const b = p.getBBox(); return [b.width, b.height]; }")
            path.dispatch_event("click")
            fitted = viewport(page)
            assert fitted[2] <= 1.25 * max(bounds[0], bounds[1] * fitted[2] / fitted[3]), (
                "The national zoom cap prevents fitting the selected DC precinct")
            expect(page.locator("#substate-detail")).to_contain_text("D.C. Council chair")
            expect(page.locator("#substate-detail")).to_contain_text("not final turnout")
            page.locator("#map-zoom-out").click()
            before = viewport(page)
            page.locator("#map-zoom-in").click()
            assert viewport(page)[2] < before[2]
            check_precinct_results(page, 2026, code)
        if code == "MN":
            page.locator('.substate-feature[data-color-level="precinct"]').first.dispatch_event("click")
            expect(page.locator("#substate-detail")).to_contain_text("Separate participation statistics")
            screenshot(page, "participation-2026-minnesota.png")
            missing = next(f["properties"] for f in shapes if f["properties"]["margin_pp"] is not None
                           and not f["properties"]["participation"]["reported"])
            page.locator(f'.substate-feature[data-geography="{missing["key"]}"]').dispatch_event("click")
            expect(page.locator("#substate-detail")).to_contain_text("not yet reported for this precinct")
        if code == "ND":
            page.locator('.substate-feature[data-color-level="precinct"]').first.dispatch_event("click")
            expect(page.locator("#substate-detail")).to_contain_text("ballots reported")
            expect(page.locator("#substate-detail")).to_contain_text("No precinct electorate denominator")
            expect(page.locator("#substate-detail")).not_to_contain_text("registered at opening")
            before = viewport(page)
            page.locator("#map-zoom-in").click()
            assert viewport(page)[2] < before[2]
            check_precinct_results(page, 2026, code)
            screenshot(page, "participation-2026-north-dakota.png")
        if code == "VT":
            page.locator('.substate-feature[data-color-level="precinct"]').first.dispatch_event("click")
            expect(page.locator("#substate-detail")).to_contain_text("town-legislative reporting splits")
            expect(page.locator("#substate-detail")).to_contain_text("Municipal registration and participation remain separate")
            expect(page.locator("#substate-detail")).not_to_contain_text("Separate participation statistics")
            assert all("participation" not in feature["properties"] for feature in shapes)
            page.locator("#map-zoom-out").click()
            before = viewport(page)
            page.locator("#map-zoom-in").click()
            assert viewport(page)[2] < before[2]
            check_precinct_results(page, 2026, code)
            screenshot(page, "participation-2026-vermont.png")
    for year in sorted((year for year in precinct_results_index["coverage"] if int(year) < 2024), reverse=True):
        page.locator("#year").select_option(year)
        for code in sorted(precinct_results_index["coverage"][year]):
            page.locator("#state-select").select_option(names[code])
            check_precinct_results(page, int(year), code)
        print(f"PASS: actual candidate counts and exact red/blue fills in every acquired {year} state/DC layer", flush=True)
    page.locator("#year").select_option("2024")
    for code in sorted(precinct_results_index["coverage"]["2024"]):
        page.locator("#state-select").select_option(names[code])
        check_precinct_results(page, 2024, code)
    print("PASS: actual candidate counts and exact red/blue fills in every acquired 2024 state/DC layer", flush=True)
    page.locator("#state-select").select_option("Alaska")
    expect(page.locator(".substate-feature")).to_have_count(0)
    expect(page.locator("#geography-note")).to_contain_text("Whole-state red/blue")
    page.goto(url + "?map-color=turnout")
    expect(page.locator("#map-color")).to_have_value("turnout")
    expect(page.locator('.substate-feature[data-level="precinct"]')).to_have_count(len(current_shapes), timeout=30000)
    expected_rates = {f["properties"]["key"]: f["properties"]["reported_pct"] for f in current_shapes}
    actual_rates = page.locator('.substate-feature[data-level="precinct"]').evaluate_all(
        "paths => Object.fromEntries(paths.map(p => [p.dataset.geography, p.dataset.rate === '' ? null : +p.dataset.rate]))")
    assert actual_rates == expected_rates, "Rendered precinct rates differ from the audited source join"
    assert set(page.locator(".map-feature[data-state]").evaluate_all(
        "paths => paths.map(p => p.getAttribute('fill'))")) == {"#d6d3cb"}
    neutral = page.locator('.substate-feature[data-match="county_precinct_set_mismatch"], .substate-feature[data-match="rate_withheld"]')
    assert set(neutral.evaluate_all("paths => paths.map(p => p.getAttribute('fill'))")) == {"#edf0f3"}
    assert len(set(page.locator('.substate-feature[data-match="matched"]').evaluate_all(
        "paths => paths.map(p => p.getAttribute('fill'))"))) > 10
    expect(page.locator('.substate-feature[data-level="county"]')).to_have_count(0)
    expect(page.locator("#coverage-note")).to_contain_text(f'{precinct_index["colored_precincts"]:,} colored precincts')
    screenshot(page, "participation-default-precinct-coverage.png")
    default_demographics = context.new_page()
    default_demographics.on("pageerror", lambda error: errors.append(str(error)))
    default_demographics.goto(url + "?view=national")
    expect(default_demographics.locator("#year")).to_have_value("2026")
    expect(default_demographics.locator("#provisional-status")).to_be_visible()
    tab(default_demographics, "Precincts")
    expect(default_demographics.locator("#year")).to_have_value("2024")
    default_demographics.close()
    page.goto(url + "?year=2024&map-level=auto&map-color=margin")
    expect(page.locator("#year")).to_have_value("2024")
    expect(page.locator(".map-feature[data-state]")).to_have_count(51)
    expect(page.locator("#selection-panel h3")).to_have_text("North Carolina")
    assert page.locator("#state-history .chart-point").count() > 15
    assert connected(page, "#state-history", 1994, 1996)
    assert not connected(page, "#state-history", 1992, 1994)
    bridge = page.locator('#state-history .chart-definition-break[data-from-year="1992"][data-to-year="1994"]')
    expect(bridge).to_have_count(1)
    expect(bridge).to_have_attribute("aria-label", "1992–1994: Citizenship measurement changed in 1994. Estimates are not directly comparable.")
    assert bridge.evaluate("p => getComputedStyle(p).strokeDasharray") != "none"
    endpoints = page.locator('#state-history .chart-point[data-year="1992"], #state-history .chart-point[data-year="1994"]').evaluate_all(
        "points => points.map(p => p.getAttribute('cx') + ',' + p.getAttribute('cy'))")
    assert all(point in bridge.get_attribute("d") for point in endpoints)
    assert page.locator("#visualization").bounding_box()["y"] < 570
    assert not page.locator("#updates-panel").is_visible()
    no_overflow(page)
    # North must be above south, including after fitting the Albers projection.
    north = page.locator('[data-state="North Dakota"]').bounding_box()
    south = page.locator('[data-state="South Dakota"]').bounding_box()
    assert north["y"] < south["y"]
    alaska = page.locator('[data-state="Alaska"]').bounding_box()
    assert 1.8 < alaska["width"] / alaska["height"] < 1.95, "Alaska is distorted"
    anchors = page.locator(".state-label").evaluate_all("""labels => labels.map(label => {
        const path = [...document.querySelectorAll('.map-feature[data-state]')]
            .find(path => path.dataset.state === label.dataset.labelState);
        return [label.dataset.labelState, path.isPointInFill(new DOMPoint(+label.getAttribute('x'), +label.getAttribute('y')))];
    })""")
    assert all(inside for _, inside in anchors), f"State label outside its boundary: {anchors}"
    labels = page.locator(".state-label, .external-label").all()
    for index, label in enumerate(labels):
        a = label.bounding_box()
        for other in labels[index + 1:]:
            b = other.bounding_box()
            assert not (a["x"] < b["x"] + b["width"] and a["x"] + a["width"] > b["x"]
                        and a["y"] < b["y"] + b["height"] and a["y"] + a["height"] > b["y"]), \
                f"Overlapping state labels: {label.text_content()}, {other.text_content()}"
    page.locator('.external-label[data-label-state="Rhode Island"]').focus()
    page.keyboard.press("Enter")
    expect(page.locator("#state-select")).to_have_value("Rhode Island")
    page.locator("#state-select").select_option("North Carolina")
    page.locator("#map-reset").click()
    screenshot(page, "participation-redesign-states.png")

    page.locator('[data-state="Washington"]').click()
    expect(page.locator("#state-select")).to_have_value("Washington")
    page.locator("#state-select").select_option("California")
    expect(page.locator("#selection-panel h3")).to_have_text("California")
    expected = next(row for row in states if row["state"] == "California"
                    and row["year"] == 2024 and row["denominator"] == "cvap")
    expect(page.locator("#selection-panel .selection-rate")).to_have_text(f'{expected["turnout_pct"]:.1f}%')
    points = page.locator("#state-history .chart-point").evaluate_all(
        "points => points.map(p => [+p.dataset.year, +p.dataset.rate])")
    expected_points = sorted((row["year"], row["turnout_pct"]) for row in states
                             if row["state"] == "California" and row["denominator"] == "cvap"
                             and row["turnout_pct"] is not None)
    assert sorted(tuple(point) for point in points) == expected_points
    observed_ticks(page, "#state-history svg")
    page.locator('#state-history [data-year="2020"]').focus()
    page.keyboard.press("Enter")
    expect(page.locator("#year")).to_have_value("2020")

    before_zoom = viewport(page)[2]
    page.locator("#map-zoom-in").click()
    assert abs(viewport(page)[2] - before_zoom / 2) < .001
    map_svg = page.locator("svg.turnout-map")
    map_svg.focus()
    page.keyboard.press("+")
    assert abs(viewport(page)[2] - before_zoom / 4) < .001
    before = viewport(page)
    page.keyboard.press("ArrowRight")
    assert viewport(page)[0] > before[0]
    rect = map_svg.bounding_box()
    before = viewport(page)
    page.mouse.move(rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)
    page.mouse.down()
    page.mouse.move(rect["x"] + rect["width"] / 2 + 60, rect["y"] + rect["height"] / 2, steps=6)
    page.mouse.up()
    assert viewport(page)[0] < before[0]
    expect(page.locator("#state-select")).to_have_value("California")
    page.locator("#map-reset").click()
    assert viewport(page) == [0, 0, 1000, 610]
    map_svg = page.locator("svg.turnout-map")
    # Finish any smooth page scroll from earlier focus/clicks before measuring wheel behavior.
    page.evaluate("window.scrollTo({top: scrollY, behavior: 'instant'})")
    rect = map_svg.bounding_box()
    page.mouse.move(rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)
    map_svg.evaluate("svg => svg.addEventListener('wheel', e => window.mapWheelPrevented = e.defaultPrevented, {once: true})")
    page.mouse.wheel(0, -300)
    page.wait_for_function("document.querySelector('svg.turnout-map').viewBox.baseVal.width < 900")
    assert viewport(page)[2] < 1000
    assert page.evaluate("window.mapWheelPrevented")
    after_wheel = map_svg.bounding_box()
    assert abs(after_wheel["y"] - rect["y"]) <= 1, (rect, after_wheel)
    page.locator("#map-reset").click()
    page.locator('[data-state="California"]').click()
    fitted = viewport(page)
    map_svg.dispatch_event("dblclick", {"clientX": rect["x"] + rect["width"] * .2,
                                      "clientY": rect["y"] + rect["height"] / 2})
    zoomed = viewport(page)
    assert abs(zoomed[2] - fitted[2] / 2) < .001
    assert abs(zoomed[0] + zoomed[2] / 2 - fitted[0] - fitted[2] / 2) < .001
    page.locator("#map-reset").click()
    page.locator("#year").select_option("2022")
    expect(page.locator("#year")).to_have_value("2022")
    assert {2020, 2022, 2024} <= set(page.locator("#state-history .chart-point").evaluate_all(
        "points => points.map(p => +p.dataset.year)"))
    page.locator(".explorer-options summary").click()
    page.locator("#basis").select_option("vap")
    assert connected(page, "#state-history", 1992, 1994, 1996)
    expect(page.locator('#state-history .chart-definition-break[data-to-year="1994"]')).to_have_count(0)
    expected = next(row for row in states if row["state"] == "California"
                    and row["year"] == 2022 and row["denominator"] == "vap")
    expect(page.locator("#selection-panel .selection-rate")).to_have_text(f'{expected["turnout_pct"]:.1f}%')
    page.locator("#basis").select_option("cvap")
    page.locator(".explorer-options summary").click()

    # Methods preserve matched reporting coverage, real missingness and definition breaks.
    page.locator("#year").select_option("2024")
    page.locator("#state-select").select_option("California")
    expected_method = next(row for row in method_states if row["year"] == 2024
                           and row["state_code"] == "CA" and row["mode"] == "early_in_person")
    method_row = page.locator('#method-observations tr[data-method="early_in_person"]')
    expect(method_row).to_have_attribute("data-share", str(expected_method["share_pct"]))
    expect(method_row).to_contain_text(f'{expected_method["reported_count"]:,}')
    expect(method_row).to_contain_text(f'{expected_method["matched_units"]}/{expected_method["total_units"]}')
    assert page.locator("#method-history .method-point").count() == 9
    assert page.locator("#method-history .chart-line").count() == 0
    page.locator("#map-level").select_option("county")
    expect(page.locator('.substate-feature[data-level="county"]')).to_have_count(58)
    expect(page.locator("#geography-note")).to_contain_text("58 with party-margin returns")
    page.locator('.substate-feature[data-geography="06037"]').dispatch_event("click")
    expect(page.locator("#substate-detail")).to_contain_text("Los Angeles")
    page.locator("#state-select").select_option("California")
    page.locator("#map-level").select_option("district")
    expect(page.locator('.substate-feature[data-level="district"]')).to_have_count(52)
    screenshot(page, "participation-final-districts-methods.png")
    page.locator("#year").select_option("2026")
    expect(page.locator("#geography-note")).to_contain_text("not substituted for 2026")
    expect(page.locator(".substate-feature")).to_have_count(0)
    page.locator("#year").select_option("1994")
    page.locator("#map-reset").click()
    assert page.locator('[data-state="North Carolina"]').get_attribute("fill") != "#d6d3cb"
    expect(page.locator("#method-observations")).to_contain_text("State reporting begins in 2008")
    page.locator("#year").select_option("2010")
    assert page.locator('[data-state="North Carolina"]').get_attribute("fill") != "#d6d3cb"
    page.locator("#year").select_option("2000")
    assert page.locator('[data-state="New York"]').get_attribute("fill") == "#d6d3cb"
    assert page.locator('[data-state="California"]').get_attribute("fill") != "#d6d3cb"
    page.locator("#year").select_option("2024")
    page.locator("#state-select").select_option("North Carolina")
    page.locator("#map-level").select_option("auto")
    page.locator("#map-zoom-in").click()
    check_precinct_results(page, 2024, "NC")
    expect(page.locator("#map-color")).to_have_value("margin")
    page.locator("#map-color").select_option("turnout")
    expect(page.locator('.substate-feature[data-level="precinct"]')).to_have_count(2656)
    expect(page.locator("#title")).to_have_text("Precinct participation in North Carolina")
    expect(page.locator("#measure")).to_contain_text("registered voters")
    expect(page.locator("#caption")).to_contain_text("not CPS")
    page.locator(f'.substate-feature[data-geography="{key}"]').dispatch_event("click")
    expect(page.locator("#selection-panel")).to_contain_text("Wake")
    expect(page.locator("#state-history")).to_have_count(0)
    expect(page.locator("#precinct-history .chart-point").first).to_be_visible()
    history_expected = []
    for year in range(2002, 2025, 2):
        source = json.loads((data / f"nc/{year}.json").read_text())["records"]
        history_expected.extend((year, row["turnout_pct"], row["participants"], row["registered"])
                                for row in source if row["county"] == "WAKE" and row["precinct"] == "01-01"
                                and row["dimension"] == "overall" and row["turnout_pct"] is not None
                                and row["registered"] >= 25)
    actual = page.locator("#precinct-history .chart-point").evaluate_all(
        "points => points.map(p => [+p.dataset.year, +p.dataset.rate])")
    assert sorted(tuple(row) for row in actual) == sorted((year, rate) for year, rate, _, _ in history_expected)
    expect(page.locator("#selection-panel")).to_contain_text("not a boundary crosswalk")
    screenshot(page, "participation-inline-precinct-history.png")
    page.locator("#map-reset").click()
    expect(page.locator("#state-history")).to_be_visible()
    expect(page.locator("#title")).to_have_text("Participation across the United States")
    expect(page.locator("#measure")).to_contain_text("adult citizens")
    page.locator("#state-select").select_option("North Carolina")
    page.locator("#map-zoom-in").click()
    expect(page.locator('.substate-feature[data-level="precinct"]')).to_have_count(2656)
    page.locator(f'.substate-feature[data-geography="{key}"]').dispatch_event("click")
    expect(page.locator("#precinct-history .chart-point").first).to_be_visible()
    page.get_by_role("button", name="Open precinct participation", exact=True).click()
    expect(page.locator(".map-feature.selected")).to_have_attribute("data-key", key)
    expect(page.locator("#selection-panel .selection-rate")).to_have_text(f'{selected["turnout_pct"]:.1f}%')
    page.locator("#precinct-county").select_option("")
    tab(page, "States")
    page.locator("#map-level").select_option("auto")

    method_example = browser.new_page(viewport={"width": 1360, "height": 1000})
    method_example.goto(url + "?state=Mississippi&year=2024")
    expect(method_example.locator("#method-history-mode")).to_have_value("election_day")
    missing = method_example.locator(".method-missing")
    expect(missing).to_contain_text("methods not reported")
    assert missing.get_attribute("open") is None
    assert method_example.locator("#method-observations > table tbody tr").count() == 2
    method_example.locator("#method-history-mode").select_option("early_in_person")
    expect(method_example.locator("#method-history .method-point").first).to_be_visible()
    assert float(method_example.locator("#method-history svg").get_attribute("data-scale-max")) < 25
    screenshot(method_example, "participation-compact-mississippi-methods.png")
    missing.locator("summary").click()
    expect(missing.locator('tr[data-method="early_in_person"]')).to_be_visible()
    no_overflow(method_example)

    tab(page, "Demographics")
    page.locator("#year").select_option("2024")
    page.locator("#dimension").select_option("overall")
    assert connected(page, ".demographic-card svg", 1994, 1996)
    assert not connected(page, ".demographic-card svg", 1992, 1994)
    expect(page.locator('.demographic-card .chart-definition-break[data-from-year="1992"][data-to-year="1994"]')).to_have_count(1)
    page.locator("#dimension").select_option("race")
    expect(page.locator("#visualization .chart-point").first).to_be_visible()
    race_rows = [row for row in national if row["year"] == 2024
                 and row["dimension"] == "race" and row["age_group"] == "All ages"
                 and row["denominator"] == "cvap"]
    assert page.locator(".group-snapshot li").count() == len(race_rows)
    for row in race_rows:
        expect(page.locator(".group-snapshot")).to_contain_text(f'{row["turnout_pct"]:.1f}%')
    observed_ticks(page, ".demographic-card svg")
    screenshot(page, "participation-redesign-demographics.png")
    overall_method = next(row for row in method_national if row["year"] == 2024 and row["category"] == "Overall")
    expect(page.locator('#method-observations tr[data-method="mail"]')).to_have_attribute(
        "data-share", str(overall_method["methods"]["mail"]))
    page.locator("#method-history-mode").select_option("early_in_person")
    assert page.locator("#method-history .method-point").count() == 15
    assert page.locator("#method-history .chart-line").count() == 3
    page.locator("#method-group").select_option(label="Age · 18 to 24 years")
    assert page.locator("#method-history .method-point").count() == 4
    screenshot(page, "participation-final-demographic-methods.png")
    page.locator("#dimension").select_option("education")
    education = [row for row in national if row["dimension"] == "education"
                 and row["age_group"] == "All ages" and row["denominator"] == "cvap"]
    expect(page.locator(".demographic-card")).to_have_count(len({row["group"] for row in education}))
    assert "1972" not in page.locator(".year-tick").all_text_contents()
    assert page.locator('#year option[value="1994"]').count() == 1
    for name in {row["group"] for row in education}:
        card = page.locator(".demographic-card").filter(has=page.get_by_role("heading", name=name, exact=True))
        value = next(row["turnout_pct"] for row in education if row["year"] == 2024 and row["group"] == name)
        expect(card.locator(".demographic-value")).to_have_text(f"{value:.1f}%")
        rendered = card.locator(".chart-point").evaluate_all("points => points.map(p => [+p.dataset.year, +p.dataset.rate])")
        assert sorted(tuple(point) for point in rendered) == sorted(
            (row["year"], row["turnout_pct"]) for row in education if row["group"] == name and row["turnout_pct"] is not None)
    observed_ticks(page, ".demographic-card svg")
    screenshot(page, "participation-refined-education.png")
    page.locator("#year").select_option("1994")
    expect(page.locator(".observation-gap")).to_contain_text("1994")
    expect(page.locator("#method-observations")).to_contain_text("National history begins in 1996")
    page.get_by_role("button", name="Show overall participation in 1994").click()
    expect(page.locator("#dimension")).to_have_value("overall")
    expect(page.locator(".group-snapshot")).to_contain_text("48.3%")
    page.locator("#dimension").select_option("education")

    # Provisional observations belong to the normal controls, but never masquerade as CPS rates.
    page.locator("#year").select_option("2026")
    expect(page.locator("#provisional-status")).to_be_visible()
    expect(page.locator("#visualization")).to_contain_text("No 2026 education breakdown")
    page.locator("#dimension").select_option("race")
    expect(page.locator("#current-state-select")).to_have_value("GA")
    ga_race = [row for row in nationwide["demographics"] if row["state_code"] == "GA"
               and row["mode"] == "in_person_early" and row["dimension"] == "race"]
    expect(page.locator(".provisional-bars li")).to_have_count(len(ga_race))
    for row in ga_race:
        item = page.locator(".provisional-bars li").filter(has=page.get_by_text(row["group"], exact=True))
        expect(item.locator("strong")).to_have_text(f'{row["ballots"]:,}')
    assert page.locator("#visualization .chart-point").count() == 0
    expect(page.locator(".count-source")).to_contain_text(ga_race[0]["source_date"])
    screenshot(page, "participation-refined-provisional-demographics.png")
    provisional_link = page.url
    page.reload()
    expect(page.locator(".provisional-bars li")).to_have_count(len(ga_race))
    expect(page.locator("#year")).to_have_value("2026")
    page.locator("#mode").select_option("mail_returned")
    returned = [row for row in nationwide["demographics"] if row["state_code"] == "GA"
                and row["mode"] == "mail_returned" and row["dimension"] == "race"]
    expect(page.locator(".provisional-bars li")).to_have_count(len(returned))
    assert sorted(page.locator(".provisional-bars li").evaluate_all("items => items.map(i => +i.dataset.ballots)")) == sorted(row["ballots"] for row in returned)
    page.locator("#current-state-select").select_option("AL")
    expect(page.locator("#visualization")).to_contain_text("No 2026")
    page.locator("#year").select_option("2024")
    expect(page.locator("#provisional-status")).not_to_be_visible()
    expect(page.locator(".demographic-card").first).to_be_visible()
    tab(page, "States")
    page.locator("#year").select_option("2026")
    page.locator("#mode").select_option("official")
    page.locator("#state-select").select_option("North Carolina")
    official = next(row for row in nationwide["reporting"] if row["state_code"] == "NC")
    expect(page.locator("#selection-panel .selection-rate")).to_have_text(f'{official["ballots"]:,}')
    expect(page.locator("#selection-panel")).to_contain_text("not final turnout")
    expect(page.locator("#selection-panel")).to_contain_text(official["source_update_label"])
    assert all(year <= 2024 for year in page.locator("#state-history .chart-point").evaluate_all(
        "points => points.map(p => +p.dataset.year)"))
    assert "20%" not in page.locator("#key").inner_text()
    screenshot(page, "participation-refined-provisional-states.png")
    page.locator("#state-select").select_option("Georgia")
    expect(page.locator("#selection-panel .selection-rate")).to_have_text("Not reported")
    page.locator("#mode").select_option("in_person_early")
    ga_total = next(row for row in nationwide["early_voting"] if row["state_code"] == "GA" and row["mode"] == "in_person_early")
    expect(page.locator("#selection-panel .selection-rate")).to_have_text(f'{ga_total["ballots"]:,}')

    tab(page, "Precincts")
    expect(page.locator('#year option[value="2026"]')).to_have_count(0)
    page.locator("#dimension").select_option("overall")
    expect(page.locator(".map-feature[data-key]")).to_have_count(2656)
    page.locator("#precinct-county").select_option("WAKE")
    expect(page.locator('.map-feature:not([data-county="WAKE"])')).to_have_count(0)
    expect(page.locator('[data-key="WAKE|01-01"]')).to_have_count(1)
    assert viewport(page)[2] < 1000
    option = next(value for value in page.locator("#precinct-options option").evaluate_all(
        "options => options.map(o => o.value)") if value.startswith("WAKE · 01-01 ·"))
    page.locator("#precinct-search").fill(option)
    page.locator("#precinct-search").dispatch_event("change")
    expect(page.locator(".map-feature.selected")).to_have_attribute("data-key", key)
    expect(page.locator("#selection-panel .selection-rate")).to_have_text(f'{selected["turnout_pct"]:.1f}%')
    expect(page.locator(".selection-stats")).to_contain_text(f'{selected["participants"]:,}')
    expect(page.locator(".selection-stats")).to_contain_text(f'{selected["registered"]:,}')
    expect(page.locator("#precinct-history .chart-point").first).to_be_visible()
    history_rows = page.locator("#precinct-history .chart-point").evaluate_all(
        "points => points.map(p => [+p.dataset.year, +p.dataset.rate])")
    assert sorted(tuple(row) for row in history_rows) == sorted((year, rate) for year, rate, _, _ in history_expected)
    history_year = page.locator("#precinct-history .chart-point[data-year='2022']")
    history_year.evaluate("point => point.scrollIntoView({block: 'center', behavior: 'instant'})")
    history_year.click()
    expect(page.locator("#year")).to_have_value("2022")
    expect(page.locator(".map-feature.selected")).to_have_attribute("data-key", key)
    page.locator("#precinct-history .chart-point[data-year='2024']").click()
    expect(page.locator("#year")).to_have_value("2024")
    expect(page.locator(".map-feature.selected")).to_have_attribute("data-key", key)
    expect(page.locator("#precinct-history .chart-point").first).to_be_visible()
    for year, rate, participants, registered in history_expected:
        count_row = page.locator(f'#precinct-history tr[data-year="{year}"]')
        expect(count_row).to_contain_text(f"{participants:,}")
        expect(count_row).to_contain_text(f"{registered:,}")
    assert page.locator(".precinct-label").evaluate(
        "label => parseFloat(getComputedStyle(label).strokeWidth) * label.getScreenCTM().a") < 3
    detail_view = viewport(page)
    page.locator("#map-zoom-out").click()
    assert viewport(page)[2] > detail_view[2]
    page.locator("#map-zoom-in").click()
    assert abs(viewport(page)[2] - detail_view[2]) < 0.001
    screenshot(page, "participation-redesign-precincts.png")
    deep_link = page.url
    page.reload()
    expect(page.locator(".map-feature.selected")).to_have_attribute("data-key", key)
    expect(page.locator("#precinct-county")).to_have_value("WAKE")
    tab(page, "States")
    tab(page, "Precincts")
    expect(page.locator(".map-feature.selected")).to_have_attribute("data-key", key)
    assert abs(viewport(page)[2] - detail_view[2]) < 0.001
    page.locator(".explorer-options summary").click()
    page.locator("#minimum").select_option("100")
    page.locator("#precinct-search").fill("")
    page.locator("#dimension").select_option("race")
    low = next(row for row in records if row["county"] == "WAKE" and row["dimension"] == "race"
               and row["precinct"] and 0 < row["registered"] < 100 and row["turnout_pct"] is not None)
    page.locator("#group").select_option(low["group"])
    page.locator("#precinct-search").fill(low["precinct"])
    page.locator("#precinct-search").dispatch_event("change")
    expect(page.locator("#selection-panel .selection-rate")).to_have_text("Not available")
    expect(page.locator("#selection-panel")).to_contain_text("rate withheld")
    expect(page.locator("#precinct-history table")).to_be_attached()
    expect(page.locator('#precinct-history .chart-point[data-year="2024"]')).to_have_count(0)
    page.locator(".explorer-options summary").click()
    page.locator("#dimension").select_option("overall")
    page.locator("#precinct-search").fill("01-01")
    page.locator("#precinct-search").dispatch_event("change")
    page.locator("#year").select_option("2022")
    expect(page.locator(".map-feature.selected")).to_have_attribute("data-key", key)
    expect(page.locator("#precinct-search")).not_to_have_value("")
    page.locator("#precinct-county").select_option("")
    expect(page.locator(".map-feature[data-key]")).to_have_count(2652)
    page.locator("#year").select_option("2018")
    expect(page.locator("#visualization")).to_contain_text("No verified 2018 precinct boundary snapshot")
    expect(page.locator("svg.turnout-map")).to_have_count(0)
    expect(page.locator("#table-note")).to_contain_text("observations")
    assert not page.locator("#map-tools").is_visible()

    tab(page, "Methods & data")
    page.locator("#updates-panel > summary").click()
    expect(page.locator("#national-current-state")).to_be_enabled()
    expect(page.locator("#nc-current-ballots")).to_have_text(f"{current_ballots:,}")
    page.locator("#participation-model summary").click()
    expect(page.locator("#model-summary")).to_contain_text("98")
    page.locator("#participation-cps summary").click()
    expect(page.locator("#cps-summary")).to_contain_text("34 of 34")
    assert page.locator('#downloads a[download]').count() == expected_downloads
    for link in page.locator('#downloads a[download]').all():
        response = context.request.head(link.get_attribute("href") if link.get_attribute("href").startswith("http")
                                        else args.base_url + link.get_attribute("href"))
        assert response.ok, f"Download failed: {response.url}"
    assert not errors, errors

    mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    mobile.on("pageerror", lambda error: errors.append(str(error)))
    mobile.goto(url)
    expect(mobile.locator("#year")).to_have_value("2026")
    expect(mobile.locator("#provisional-status")).to_be_visible()
    expect(mobile.locator("#map-color")).to_have_value("margin")
    check_precinct_results(mobile, 2026, "NC")
    assert result_colors(mobile) == expected_colors
    no_overflow(mobile)
    screenshot(mobile, "participation-latest-election-mobile.png")
    mobile.locator("#year").select_option("2024")
    expect(mobile.locator(".map-feature[data-state]")).to_have_count(51)
    no_overflow(mobile)
    mobile.locator("svg.turnout-map").scroll_into_view_if_needed()
    mobile.evaluate("window.scrollTo({top: scrollY, behavior: 'instant'})")
    rect = mobile.locator("svg.turnout-map").bounding_box()
    cx, cy = rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2
    cdp = mobile.context.new_cdp_session(mobile)
    before_pinch = viewport(mobile)
    touches = lambda distance: [{"x": cx - distance / 2, "y": cy, "id": 31},
                                {"x": cx + distance / 2, "y": cy, "id": 32}]
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": touches(40)})
    for distance in [48, 60, 72, 80]:
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": touches(distance)})
    mobile.wait_for_function("""width =>
        Math.abs(document.querySelector('svg.turnout-map').viewBox.baseVal.width - width) < .01""",
        arg=before_pinch[2] / 2)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": [touches(80)[1]]})
    before_pan = viewport(mobile)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchMove",
                                        "touchPoints": [{"x": cx - 20, "y": cy, "id": 31}]})
    mobile.wait_for_function("x => document.querySelector('svg.turnout-map').viewBox.baseVal.x < x",
                             arg=before_pan[0])
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": touches(80)})
    for distance in [72, 60, 48, 40]:
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": touches(distance)})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    mobile.wait_for_function("""width =>
        Math.abs(document.querySelector('svg.turnout-map').viewBox.baseVal.width - width) < .01""",
        arg=before_pinch[2])
    assert mobile.locator("#state-select").input_value() == "North Carolina"
    mobile.locator("#map-reset").click()
    screenshot(mobile, "participation-redesign-mobile.png")
    tab(mobile, "Demographics")
    mobile.locator("#dimension").select_option("education")
    expect(mobile.locator(".demographic-card").first).to_be_visible()
    no_overflow(mobile)
    screenshot(mobile, "participation-refined-mobile-education.png")
    mobile.goto(url + "?state=Mississippi&year=2024")
    expect(mobile.locator("#method-history-mode")).to_have_value("election_day")
    no_overflow(mobile)
    screenshot(mobile, "participation-compact-mobile-methods.png")
    mobile.goto(provisional_link)
    expect(mobile.locator(".provisional-bars li")).to_have_count(len(ga_race))
    no_overflow(mobile)
    screenshot(mobile, "participation-refined-mobile-provisional.png")
    mobile.goto(deep_link)
    expect(mobile.locator(".map-feature.selected")).to_have_attribute("data-key", key)
    expect(mobile.locator("#precinct-history .chart-point").first).to_be_visible()
    no_overflow(mobile)
    mobile.locator("#map-zoom-out").click()
    assert viewport(mobile)[2] > detail_view[2]
    mobile.locator("#map-zoom-in").click()
    assert abs(viewport(mobile)[2] - detail_view[2]) < 0.001
    screenshot(mobile, "participation-redesign-mobile-precinct.png")

    local_page = context.new_page()
    local_page.on("pageerror", lambda error: errors.append(str(error)))
    local_page.goto(url + "?state=Wisconsin&year=2024&map-color=turnout&map-level=county")
    local_page.locator('[data-state="Wisconsin"]').click()
    wi_rows = json.loads(gzip.decompress((local_root / "states/WI.json.gz").read_bytes()))
    wi = next(row for row in wi_rows if row["year"] == 2024 and row["jurisdiction_id"] == "00100")
    expect(local_page.locator('.substate-feature[data-level="municipality"]')).to_have_count(1850)
    expect(local_page.locator("#title")).to_have_text("Local participation in Wisconsin")
    expect(local_page.locator("#geography-note")).to_contain_text("1,845 matched reporting units")
    local_page.locator("#local-unit-select").select_option(wi["history_key"])
    expect(local_page.locator("#local-detail .selection-rate")).to_have_text(f'{wi["turnout_pct"]:.1f}%')
    expected_history = [r for r in wi_rows if r["history_key"] == wi["history_key"] and r["turnout_pct"] is not None]
    expect(local_page.locator("#local-history .chart-point")).to_have_count(len(expected_history))
    local_page.locator('.substate-feature[data-geography="5500100"]').dispatch_event("click")
    expect(local_page.locator("#local-detail")).to_contain_text("748 participants; 886 registrations")
    screenshot(local_page, "participation-national-wisconsin.png")
    local_page.locator("#year").select_option("2004")
    appleton = [row for row in wi_rows if row["year"] == 2004 and row["jurisdiction"] == "APPLETON"]
    assert len(appleton) == 2 and len({row["history_key"] for row in appleton}) == 2
    for row in appleton:
        option = local_page.locator("#local-unit-select option").filter(
            has_text=f'APPLETON · 2004 source row {row["source_details"]["source_row"]}')
        expect(option).to_have_count(1)
        local_page.locator("#local-unit-select").select_option(row["history_key"])
        expect(local_page.locator("#local-detail")).to_contain_text("No source jurisdiction ID")
        observed = local_page.locator("#local-detail tr[data-year]")
        expect(observed).to_have_count(1)
        expect(observed).to_contain_text(f'{row["total_participation"]:,}')
    local_page.locator("#year").select_option("2006")
    expect(local_page.locator("#local-detail")).to_contain_text("No verified observation for this election.")
    local_page.locator("#year").select_option("2024")
    local_page.locator("#state-select").select_option("Alabama")
    expect(local_page.locator('.substate-feature[data-level="county"]')).to_have_count(67)
    al_rows = json.loads(gzip.decompress((local_root / "states/AL.json.gz").read_bytes()))
    al = next(row for row in al_rows if row["year"] == 2024 and row["jurisdiction_id"] == "0100100000")
    local_page.locator('.substate-feature[data-geography="01001"]').dispatch_event("click")
    expect(local_page.locator("#local-detail .selection-rate")).to_have_text(f'{al["turnout_pct"]:.1f}%')
    local_page.locator("#local-history .chart-point[data-year='2014']").click()
    expect(local_page.locator("#year")).to_have_value("2014")
    expect(local_page.locator("#local-unit-select")).to_have_value(al["history_key"])
    expect(local_page.locator('.substate-feature[data-level="county"]')).to_have_count(67)
    local_page.locator("#year").select_option("2008")
    al_2008 = next(row for row in al_rows if row["year"] == 2008 and row["history_key"] == al["history_key"])
    expect(local_page.locator("#local-detail .selection-rate")).to_have_text(f'{al_2008["turnout_pct"]:.1f}%')
    expect(local_page.locator('.substate-feature[data-level="county"]')).to_have_count(67)
    local_page.locator("#year").select_option("2004")
    expect(local_page.locator("#geography-note")).to_contain_text("No verified 2004 local boundary collection")
    expect(local_page.locator(".substate-feature")).to_have_count(0)
    al_2004 = next(row for row in al_rows if row["year"] == 2004 and row["jurisdiction_id"] == "0100100000")
    local_page.locator("#local-unit-select").select_option(al_2004["history_key"])
    expect(local_page.locator("#local-detail .selection-rate")).to_have_text(f'{al_2004["turnout_pct"]:.1f}%')
    expect(local_page.locator("#local-detail")).to_contain_text("2004/2006 count ballots counted")
    expect(local_page.locator('#local-history .chart-definition-break[data-from-year="2006"][data-to-year="2008"]')).to_have_count(1)
    expect(local_page.locator('#local-history .chart-definition-break[data-from-year="2018"][data-to-year="2020"]')).to_have_count(1)
    expect(local_page.locator("#local-detail")).to_contain_text("Reported voting-method counts")
    local_page.locator("#local-unit-select").select_option(al["history_key"])
    local_page.locator("#year").select_option("1994")
    expect(local_page.locator("#local-navigation")).to_contain_text("No verified local observations for 1994")
    expect(local_page.locator("#local-history .chart-point")).to_have_count(sum(
        row["history_key"] == al["history_key"] and row["turnout_pct"] is not None for row in al_rows))
    local_page.locator("#state-select").select_option("Alaska")
    expect(local_page.locator("#local-unit-select option")).to_have_count(2)
    expect(local_page.locator("#local-navigation")).to_contain_text("No verified local observations for 1994")
    local_page.locator("#year").select_option("2024")
    expect(local_page.locator("#geography-note")).to_contain_text("0 matched reporting units")
    mobile.goto(url + "?state=Wisconsin&year=2024&map-color=turnout&map-level=county")
    mobile.locator('[data-state="Wisconsin"]').click()
    expect(mobile.locator('.substate-feature[data-level="municipality"]')).to_have_count(1850)
    mobile.locator("#local-unit-select").select_option(wi["history_key"])
    expect(mobile.locator("#local-detail .selection-rate")).to_have_text(f'{wi["turnout_pct"]:.1f}%')
    no_overflow(mobile)
    screenshot(mobile, "participation-national-local-mobile.png")
    broken_local = browser.new_page()
    broken_local.route("**/states/WI.json.gz", lambda route: route.abort())
    broken_local.goto(url + "?state=Wisconsin&year=2024")
    expect(broken_local.locator(".map-feature[data-state]")).to_have_count(51)
    expect(broken_local.locator("#local-navigation")).to_contain_text("No values inferred")

    current_page = context.new_page()
    current_page.on("pageerror", lambda error: errors.append(str(error)))
    current_page.goto(url + "?state=New+Mexico&year=2026&mode=official&map-color=turnout")
    expect(current_page.locator('.substate-feature[data-level="precinct"]')).to_have_count(len(current_shapes), timeout=30000)
    mapped = next(f["properties"] for f in current_shapes if f["properties"]["reported_pct"] is not None
                  and f["properties"]["county"] == "Dona Ana")
    mapped_row = next(row for row in current_local["precincts"] if row["state_code"] == "NM"
                      and row["unit_key"] == mapped["unit_key"])
    current_page.locator(f'.substate-feature[data-geography="{mapped["key"]}"]').dispatch_event("click")
    expect(current_page.locator("#current-unit-select")).to_have_value(mapped["unit_key"])
    expect(current_page.locator("#current-unit-detail .selection-rate")).to_have_text(f'{mapped_row["ballots"]:,}')
    expect(current_page.locator("#substate-detail .selection-rate")).to_have_text(f'{mapped["reported_pct"]:.1f}%')
    expect(current_page.locator("#substate-detail")).to_contain_text("source-defined eligible voters")
    screenshot(current_page, "participation-2026-colored-precinct.png")
    current_page.locator("#state-select").select_option("New Mexico")
    unmatched = next(f["properties"] for f in current_shapes if f["properties"]["match_status"] == "county_precinct_set_mismatch")
    current_page.locator(f'.substate-feature[data-geography="{unmatched["key"]}"]').dispatch_event("click")
    expect(current_page.locator("#substate-detail")).to_contain_text("county boundary and reporting precinct sets differ")
    expect(current_page.locator("#substate-detail .selection-rate")).to_have_text("Not available")
    current_page.locator("#state-select").select_option("Nebraska")
    expect(current_page.locator("#geography-note")).to_contain_text("No matched 2026 precinct participation")
    expect(current_page.locator(".substate-feature")).to_have_count(0)
    assert set(current_page.locator(".map-feature[data-state]").evaluate_all(
        "paths => paths.map(p => p.getAttribute('fill'))")) == {"#d6d3cb"}
    current_page.goto(url + "?year=2024&map-color=turnout")
    expect(current_page.locator('.substate-feature[data-level="precinct"]')).to_have_count(2656)
    expect(current_page.locator("#title")).to_have_text("Precinct participation in North Carolina")
    for name in ["NM.geojson.gz", "originals/NM-precincts-20260717.zip", "checksums.json"]:
        response = context.request.head(precinct_pointer["base_url"] + name)
        assert response.ok, f"Complete precinct download failed: {response.url}"
    current_page.goto(url + "?state=New+Mexico&year=2026&mode=official&map-color=turnout&map-level=county")
    nm_county = next(row for row in current_local["counties"] if row["state_code"] == "NM" and row["county"] == "Bernalillo")
    nm_unit = next(row for row in current_local["precincts"] if row["state_code"] == "NM"
                   and row["county_id"] == nm_county["county_id"] and row["reported_pct"] is not None)
    expect(current_page.locator("#current-county-select option")).to_have_count(34)
    current_page.locator("#current-county-select").select_option(nm_county["county_id"])
    current_page.locator("#current-unit-select").select_option(nm_unit["unit_key"])
    expect(current_page.locator("#current-unit-detail .selection-rate")).to_have_text(f'{nm_unit["ballots"]:,}')
    expect(current_page.locator("#current-unit-detail")).to_contain_text(f'{nm_unit["reported_pct"]:.1f}%')
    expect(current_page.locator("#current-unit-detail")).to_contain_text("eligible voters source definition")
    current_page.locator('[data-state="New Mexico"]').click()
    expect(current_page.locator('.substate-feature[data-level="county"]')).to_have_count(33)
    expect(current_page.locator("#geography-note")).to_contain_text("33 uniquely name-matched")
    current_page.locator('.substate-feature[data-geography="35001"]').dispatch_event("click")
    expect(current_page.locator("#current-county-select")).to_have_value(nm_county["county_id"])
    expect(current_page.locator("#current-county-detail .selection-rate")).to_have_text(f'{nm_county["ballots"]:,}')
    current_page.locator("#map-reset").click()
    expect(current_page.locator("#key")).to_contain_text("Count reported")
    current_page.locator('[data-state="New Mexico"]').click()
    current_page.locator("#mode").select_option("mail_returned")
    expect(current_page.locator("#title")).not_to_have_text("Local participation in New Mexico")
    current_page.locator("#mode").select_option("official")
    current_page.locator("#state-select").select_option("Nebraska")
    ne_unit = next(row for row in current_local["precincts"] if row["state_code"] == "NE" and row["unit_kind"] == "precinct")
    current_page.locator("#current-county-select").select_option(ne_unit["county_id"])
    current_page.locator("#current-unit-select").select_option(ne_unit["unit_key"])
    expect(current_page.locator("#current-unit-detail .selection-rate")).to_have_text(f'{ne_unit["ballots"]:,}')
    expect(current_page.locator("#current-unit-detail")).to_contain_text("Not available")
    expect(current_page.locator("#current-unit-detail")).to_contain_text("County allocation does not reconcile")
    current_page.locator("#state-select").select_option("South Dakota")
    duplicate = [row for row in current_local["precincts"] if row["state_code"] == "SD"
                 and row["unit"] == "Sacred Heart Church Hall"]
    assert len(duplicate) == 2
    current_page.locator("#current-county-select").select_option(duplicate[0]["county_id"])
    option_labels = []
    for row in duplicate:
        current_page.locator("#current-unit-select").select_option(row["unit_key"])
        expect(current_page.locator("#current-unit-detail .selection-rate")).to_have_text(f'{row["ballots"]:,}')
        expect(current_page.locator("#current-unit-detail")).to_contain_text("vote center")
        expect(current_page.locator("#current-unit-detail")).to_contain_text("Not available")
        option_labels.append(current_page.locator("#current-unit-select option:checked").inner_text())
    assert len(set(option_labels)) == 2
    current_page.locator("#state-select").select_option("North Carolina")
    current_page.locator("#current-county-select").select_option(label="WAKE")
    expect(current_page.locator("#current-unit-navigation")).to_contain_text("County counts only")
    mobile.goto(url + "?state=New+Mexico&year=2026&mode=official&map-color=turnout")
    expect(mobile.locator('.substate-feature[data-level="precinct"]')).to_have_count(len(current_shapes), timeout=30000)
    mobile.locator(f'.substate-feature[data-geography="{mapped["key"]}"]').dispatch_event("click")
    expect(mobile.locator("#current-unit-select")).to_have_value(mapped["unit_key"])
    no_overflow(mobile)
    screenshot(mobile, "participation-2026-colored-precinct-mobile.png")
    mobile.locator("#current-county-select").select_option(nm_county["county_id"])
    mobile.locator("#current-unit-select").select_option(nm_unit["unit_key"])
    expect(mobile.locator("#current-unit-detail .selection-rate")).to_have_text(f'{nm_unit["ballots"]:,}')
    no_overflow(mobile)
    screenshot(mobile, "participation-2026-mobile-precinct-counts.png")
    broken_local_current = browser.new_page()
    broken_local_current.route("**/participation-current/**/local.json", lambda route: route.abort())
    broken_local_current.goto(url + "?state=New+Mexico&year=2026")
    expect(broken_local_current.locator("#selection-panel")).to_contain_text("No local counts inferred")
    broken_precinct_current = browser.new_page()
    broken_precinct_current.route("**/NM.geojson.gz", lambda route: route.abort())
    broken_precinct_current.goto(url + "?state=New+Mexico&year=2026&map-color=turnout")
    expect(broken_precinct_current.locator("#geography-note")).to_contain_text("Geographic detail could not be loaded")
    expect(broken_precinct_current.locator(".substate-feature")).to_have_count(0)
    assert set(broken_precinct_current.locator(".map-feature[data-state]").evaluate_all(
        "paths => paths.map(p => p.getAttribute('fill'))")) == {"#d6d3cb"}

    offline = browser.new_page(java_script_enabled=False)
    offline.goto(url)
    expect(offline.locator("#national-snapshot")).to_be_visible()
    expect(offline.locator("#downloads")).to_be_visible()
    assert offline.locator("#national-snapshot tbody tr").count() == 13
    assert offline.locator("#method-reference tbody tr").count() == 15
    assert offline.locator('#downloads a[download]').count() == expected_downloads
    broken_precinct_results = browser.new_page()
    broken_precinct_results.route("**/2026/NM.geojson.gz", lambda route: route.abort())
    broken_precinct_results.goto(url + "?state=New+Mexico&year=2026")
    expect(broken_precinct_results.locator("#geography-note")).to_contain_text("Geographic detail could not be loaded")
    expect(broken_precinct_results.locator(".substate-feature")).to_have_count(0)
    assert result_colors(broken_precinct_results) == expected_colors
    broken_results = browser.new_page()
    broken_results.route("**/participation-results/**/margins.json", lambda route: route.abort())
    broken_results.goto(url)
    expect(broken_results.locator("#notice")).to_contain_text("previously saved result context is retained")
    assert len([color for color in result_colors(broken_results).values() if color != "#d6d3cb"]) == 50
    broken = browser.new_page()
    broken.route("**/data/states.json", lambda route: route.abort())
    broken.goto(url)
    expect(broken.locator("#notice")).to_contain_text("Cannot load")
    tab(broken, "Methods & data")
    expect(broken.locator("#downloads")).to_be_visible()
    assert not broken.locator("#map-tools").is_visible()
    broken_geometry = browser.new_page()
    broken_geometry.route("**/nc/geometry-2024.geojson", lambda route: route.abort())
    broken_geometry.goto(url + "?view=precincts&year=2024")
    expect(broken_geometry.locator("#notice")).to_contain_text("could not be loaded")
    expect(broken_geometry.locator("#selection-panel")).to_contain_text("No selection data available")
    assert not broken_geometry.locator("#map-tools").is_visible()
    broken_history = browser.new_page()
    broken_history.route("**/participation-precinct-history/**", lambda route: route.abort())
    broken_history.goto(deep_link)
    expect(broken_history.locator("#precinct-history")).to_contain_text("No values have been inferred")
    expect(broken_history.locator("#selection-panel .selection-rate")).to_have_text(f'{selected["turnout_pct"]:.1f}%')
    broken_current = browser.new_page()
    broken_current.route("**/nationwide/latest.json", lambda route: route.abort())
    broken_current.route("**/nationwide/snapshot.json", lambda route: route.abort())
    broken_current.route("**/participation-current/**/snapshot.json", lambda route: route.abort())
    broken_current.goto(url)
    expect(broken_current.locator(".map-feature[data-state]")).to_have_count(51)
    broken_current.locator("#year").select_option("2026")
    expect(broken_current.locator("#notice")).to_contain_text("2026 observations could not be loaded")
    expect(broken_current.locator("#selection-panel .selection-rate")).to_have_text("Not reported")
    broken_context = browser.new_page()
    broken_context.route("**/participation-context/latest.json", lambda route: route.abort())
    broken_context.goto(url)
    expect(broken_context.locator(".map-feature[data-state]")).to_have_count(51)
    broken_context.locator("#year").select_option("2026")
    broken_context.locator("#mode").select_option("official")
    broken_context.locator("#state-select").select_option("Nebraska")
    nebraska = next(row for row in nationwide["reporting"] if row["state_code"] == "NE")
    expect(broken_context.locator("#selection-panel .selection-rate")).to_have_text(f'{nebraska["ballots"]:,}')
    broken_methods = browser.new_page()
    broken_methods.route("**/participation-methods/**/national.json", lambda route: route.abort())
    broken_methods.goto(url + "?year=2024")
    expect(broken_methods.locator(".map-feature[data-state]")).to_have_count(51)
    expect(broken_methods.locator("#method-observations")).to_contain_text("Historical voting methods could not be loaded")
    tab(broken_methods, "Methods & data")
    expect(broken_methods.locator("#downloads")).to_be_visible()
    assert not errors, errors
    browser.close()

print("PASS: source-matched state histories, demographics, precinct search, zoom/pan, "
      "deep links, suppression, boundary gaps, observed-year axes, geographic labels/Alaska, "
      "historical methods, 1994/2010 context, county/district/precinct drilldown, nationwide local histories, "
      "integrated provisional counts, downloads, mobile and no-JS/fetch-error fallbacks.")

"""Verify all permitted historical AP views and the static/failure fallbacks."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-ap-history/20261108-01"


def expected_cells(row):
    return [
        row["dimension"] + ": " + row["native_labels"],
        f'{float(row["modeled_voter_pct"]):.2f}%',
        f'{float(row["modeled_nonvoter_pct"]):.2f}%',
        f'{float(row["already_voted_self_report_pct"]):.2f}%',
        f'{int(row["n"]):,}',
    ]


def check(base, proof, only_mode=None):
    summary = json.loads((DATA / "summary.json").read_bytes())
    metadata = json.loads((DATA / "download.json").read_bytes())
    with urllib.request.urlopen(metadata["viewer"]["url"], timeout=120) as response:
        original = response.read()
        assert response.status == 200 and response.headers["Access-Control-Allow-Origin"] == "*"
    assert hashlib.sha256(original).hexdigest() == metadata["viewer"]["sha256"]
    rows = json.loads(original)["rows"]
    assert len(rows) == 602
    results = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            for mode, options in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("mobile", {"viewport": {"width": 390, "height": 844}}),
                ("no_javascript", {"java_script_enabled": False}),
                ("failed_source", {}),
                ("changed_source_hash", {}),
            ]:
                if only_mode is not None and mode != only_mode:
                    continue
                context = browser.new_context(**options)
                try:
                    if mode == "failed_source":
                        context.route(metadata["viewer"]["url"], lambda route: route.abort())
                    elif mode == "changed_source_hash":
                        context.route(metadata["viewer"]["url"], lambda route:
                                      route.fulfill(status=200, content_type="application/json",
                                                    headers={"Access-Control-Allow-Origin": "*"},
                                                    body=original.decode() + " "))
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    drawer = page.locator("#participation-research")
                    assert not drawer.evaluate("element => element.open")
                    drawer.locator(":scope > summary").click()
                    panel = page.locator("#participation-ap-history")
                    expect(panel).to_be_visible()
                    expect(panel.locator("[data-ap-overall]")).to_have_count(8)
                    for row in summary["national_overall"]:
                        target = panel.locator(f'[data-ap-overall="{row["year"]}:{row["weight_field"]}"]')
                        for attribute, field in (
                            ("voter", "modeled_voter_pct"), ("nonvoter", "modeled_nonvoter_pct"),
                            ("reported", "already_voted_self_report_pct"),
                        ):
                            expect(target.locator(f"[data-ap-{attribute}]")).to_have_text(
                                f'{float(row[field]):.2f}%')
                    assert panel.locator("[data-ap-scope] option").count() == 51
                    assert panel.locator('[data-ap-scope] option[value="DC"]').count() == 0
                    for text in (
                        "not administratively observed turnout or a linked panel",
                        "47 inference states despite sampling all 50", "2022 state inference is withheld",
                        "raw per-model-class support is not available", "not an anonymity or precision guarantee",
                        "No cross-study turnout change", "602 participation rows and all 710 broad-query",
                    ):
                        expect(panel).to_contain_text(text)
                    verified_rows = 0
                    if mode in {"desktop", "mobile"}:
                        expect(panel.locator("[data-ap-year]")).to_be_enabled(timeout=30000)
                        panel.locator("[data-ap-scope]").select_option("AL")
                        expect(panel.locator("[data-ap-weight]")).to_have_text("FINALVOTE_STATE_WEIGHT")
                        states = panel.locator("[data-ap-scope] option").evaluate_all(
                            "options => options.map(option => option.value)")
                        if mode == "desktop":
                            for year in ("2018", "2020", "2022", "2024"):
                                for frame in ("FINALVOTE", "POLLCLOSE"):
                                    for scope in states:
                                        actual = panel.evaluate("""(root, view) => {
                                            root.querySelector('[data-ap-year]').value = view.year;
                                            root.querySelector('[data-ap-frame]').value = view.frame;
                                            const scope = root.querySelector('[data-ap-scope]');
                                            scope.value = view.scope;
                                            scope.dispatchEvent(new Event('change', {bubbles:true}));
                                            return [...root.querySelectorAll('[data-ap-view-row]')].map(
                                                row => [...row.cells].map(cell => cell.textContent));
                                        }""", dict(year=year, frame=frame, scope=scope))
                                        field = frame + ("_NATIONAL_WEIGHT" if scope == "US50_SOURCE" else "_STATE_WEIGHT")
                                        expected = [r for r in rows if r["year"] == year and
                                                    r["weight_field"] == field and r["scope"] == scope]
                                        assert actual == [expected_cells(r) for r in expected], (year, frame, scope)
                                        verified_rows += len(expected)
                                        if year == "2022" and scope in {"DE", "WV"}:
                                            expect(panel.locator("[data-ap-qualification]")).to_contain_text("Not zero")
                                        if year == "2018" and scope != "US50_SOURCE":
                                            expect(panel.locator("[data-ap-qualification]")).to_contain_text("47 inference states")
                            assert verified_rows == 602
                        else:
                            panel.locator("[data-ap-year]").select_option("2022")
                            panel.locator("[data-ap-scope]").select_option("WV")
                            expect(panel.locator("[data-ap-rows] tr")).to_have_count(0)
                            expect(panel.locator("[data-ap-qualification]")).to_contain_text("withheld")
                    else:
                        expect(panel.locator("[data-ap-year]")).to_be_disabled()
                        if mode != "no_javascript":
                            expect(panel.locator("[data-ap-status]")).to_contain_text(
                                "unavailable or changed", timeout=30000)
                    expect(page.locator("#participation-survey [data-survey-status]")).to_have_count(936)
                    expect(page.locator("#participation-civic-estimates [data-civic-flow]")).to_have_count(112)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        for asset in metadata["assets"]:
                            href = panel.locator(f'[data-ap-download="{asset["name"]}"]').get_attribute("href")
                            assert href == asset["url"]
                            response = context.request.get(href)
                            assert response.ok
                            body = response.body()
                            assert len(body) == asset["bytes"]
                            assert hashlib.sha256(body).hexdigest() == asset["sha256"]
                            if asset["name"] == "participation.csv":
                                assert len(list(csv.DictReader(io.StringIO(body.decode())))) == 602
                            if asset["name"] == "selection-dispositions.csv":
                                assert len(list(csv.DictReader(io.StringIO(body.decode())))) == 710
                            if asset["name"] == "complete-analysis.zip":
                                with zipfile.ZipFile(io.BytesIO(body)) as archive:
                                    assert archive.testzip() is None
                                    for member, receipt in json.loads(archive.read("checksums.json")).items():
                                        content = archive.read(member)
                                        assert len(content) == receipt["bytes"]
                                        assert hashlib.sha256(content).hexdigest() == receipt["sha256"]
                    results.append(dict(mode=mode, passed=True, static_national_rows=8,
                                        every_public_row_verified=verified_rows,
                                        default_closed_research_preserved=True))
                finally:
                    context.close()
        finally:
            browser.close()
    result = dict(base_url=base, checks=results)
    if proof:
        proof.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--mode", choices=("desktop", "mobile", "no_javascript",
                                          "failed_source", "changed_source_hash"))
    args = parser.parse_args()
    check(args.base_url, args.proof, args.mode)

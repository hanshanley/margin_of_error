"""Verify every unified state/group/year cell, chart gaps and failure fallbacks."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-cps-unified-history/20261107-01/output"
SOURCE = "https://raw.githubusercontent.com/hanshanley/margin_of_error/28cd230b42e9e550356acb78d4947118529b35ab/data/participation-cps-unified-history/20261107-01/output/display.json"
RELEASE = "https://github.com/hanshanley/margin_of_error/releases/download/participation-cps-unified-history-20261107-01"


def check(base, proof, live_data=False, downloads=True):
    source = (DATA / "display.json").read_bytes()
    reference = json.loads(source)
    modes = [
        ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
        ("mobile", {"viewport": {"width": 390, "height": 844}}),
        ("no_javascript", {"java_script_enabled": False}),
        ("failed_json", {}),
        ("checksum_mismatch", {}),
    ]
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for mode, options in modes:
                context = browser.new_context(**options)
                try:
                    if mode == "failed_json":
                        context.route(SOURCE, lambda route: route.abort())
                    elif mode == "checksum_mismatch":
                        context.route(SOURCE, lambda route: route.fulfill(body=b"{}",
                            content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}))
                    elif not live_data:
                        context.route(SOURCE, lambda route: route.fulfill(body=source,
                            content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}))
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    page.locator("#participation-research > summary").click()
                    page.locator("#participation-research > details").first.locator(":scope > summary").click()
                    panel = page.locator("#participation-cps-unified-history")
                    expect(panel).to_be_visible()
                    assert panel.get_attribute("data-display-url") == SOURCE
                    assert panel.get_attribute("data-display-sha256") == hashlib.sha256(source).hexdigest()
                    for text in ("all 50 states and D.C.", "not fixed-person cohorts",
                                 "across 2002–2024", "Missing is not zero.", "native 90%"):
                        expect(panel).to_contain_text(text)
                    for name, count, label in (("adults", 1, "all adults 18+"),
                                               ("citizens", 10, "Adult citizens 18+")):
                        table = panel.locator(f'[data-cps-unified-table="{name}"]')
                        expect(table.locator("tbody tr")).to_have_count(count)
                        expect(table.locator("caption")).to_contain_text(label)
                    interactive = mode in ("desktop", "mobile")
                    controls = panel.locator("[data-cps-unified-controls]")
                    if interactive:
                        expect(controls).to_be_visible(timeout=30000)
                        assert panel.locator("#cps-unified-state option").all_text_contents() == reference["states"]
                        actual_groups = panel.locator("#cps-unified-group option").all_text_contents()
                        assert actual_groups[:len(reference["groups"])] == [
                            "Overall" if v == "Total" else v for v in reference["groups"]]
                        assert len(actual_groups) == len(reference["groups"]) + 5
                        assert all(label.endswith("(2002 native category)")
                            for label in actual_groups[len(reference["groups"]):])
                        result = panel.evaluate("""(section, data) => {
                            const state = section.querySelector('#cps-unified-state');
                            const group = section.querySelector('#cps-unified-group');
                            const election = section.querySelector('#cps-unified-election');
                            const labels = {
                                '-1': 'Not published (B or (B))', '-2': 'Withheld: small population base',
                                '-3': 'Zero or rounds to zero', '-4': 'Not supplied for this geography/year/bin',
                                '-5': 'Withheld: conflicting native totals', '-6': 'Withheld: native out-of-range metric',
                                '-7': 'Withheld: conflicting extra label', '-8': 'Withheld: unlabeled geography'
                            };
                            let cells = 0, points = 0, segments = 0;
                            const require = (condition, message) => { if (!condition) throw new Error(message); };
                            for (let s = 0; s < data.states.length; s++) {
                                for (let g = 0; g < data.groups.length; g++) {
                                    state.value = String(s); group.value = String(g);
                                    group.dispatchEvent(new Event('change'));
                                    const values = data.values[s][g];
                                    for (let i = 0; i < data.years.length; i++) {
                                        const year = data.years[i], v = values[i];
                                        const cell = section.querySelector(`[data-cps-unified-year="${year}"] td`);
                                        const expected = v.length === 2 ? `${v[0].toFixed(1)}% +/- ${v[1].toFixed(1)} pp` : labels[v[0]];
                                        require(cell.textContent.trim() === expected, [s, g, year, expected, cell.textContent]);
                                        require(!cell.closest('tr').hidden, 'All-election row hidden');
                                        cells++;
                                    }
                                    const expectedYears = data.years.filter((y, i) => y !== 2004 && values[i].length === 2);
                                    const actualPoints = [...section.querySelectorAll('[data-cps-unified-point]')];
                                    require(actualPoints.length === expectedYears.length, 'Wrong point count');
                                    const expectedExtents = values.filter((v, i) => i > 0 && v.length === 2);
                                    const low = Math.min(0, ...expectedExtents.map(v => v[0] - v[1]));
                                    const high = Math.max(100, ...expectedExtents.map(v => v[0] + v[1]));
                                    const y = r => 16 + (high - r) / (high - low) * 224;
                                    actualPoints.forEach(point => {
                                        const year = Number(point.dataset.cpsUnifiedPoint), v = values[data.years.indexOf(year)];
                                        require(year !== 2004 && expectedYears.includes(year), 'Unqualified plotted year');
                                        require(point.textContent === `${year}: ${v[0].toFixed(1)}% +/- ${v[1].toFixed(1)} pp`, 'Point title');
                                        require(Math.abs(Number(point.getAttribute('cy')) - y(v[0])) < 0.00001, 'Wrong rate coordinate');
                                        const bar = section.querySelector(`[data-cps-unified-margin="${year}"]`);
                                        require(Math.abs(Number(bar.getAttribute('y1')) - y(v[0] - v[1])) < 0.00001, 'Clipped/changed lower margin');
                                        require(Math.abs(Number(bar.getAttribute('y2')) - y(v[0] + v[1])) < 0.00001, 'Clipped/changed upper margin');
                                    });
                                    points += actualPoints.length;
                                    const width = Number(section.querySelector('svg').getAttribute('width'));
                                    for (const type of ['presidential', 'midterm']) {
                                        const expected = []; let segment = [];
                                        for (let i = 1; i < data.years.length; i++) {
                                            const year = data.years[i];
                                            if ((year % 4 === 0 ? 'presidential' : 'midterm') !== type) continue;
                                            if (values[i].length === 2) segment.push(year);
                                            else { if (segment.length > 1) expected.push(segment); segment = []; }
                                        }
                                        if (segment.length > 1) expected.push(segment);
                                        const lines = [...section.querySelectorAll(`polyline[data-series="${type}"]`)];
                                        require(lines.length === expected.length, 'Missing gap in line');
                                        lines.forEach((line, j) => {
                                            const coords = line.getAttribute('points').split(' ');
                                            require(coords.length === expected[j].length, 'Bridged unavailable election');
                                            coords.forEach((point, k) => require(
                                                Math.abs(Number(point.split(',')[0]) - (46 + (expected[j][k] - 2006) / 18 * (width - 66))) < 0.00001,
                                                'Wrong year coordinate'));
                                        });
                                        segments += lines.length;
                                    }
                                }
                            }
                            state.value = '1'; group.value = '0'; state.dispatchEvent(new Event('change'));
                            require(section.querySelector('#cps-unified-selection').textContent.includes(data.states[1]), 'State control unwired');
                            for (const type of ['presidential', 'midterm']) {
                                election.value = type; election.dispatchEvent(new Event('change'));
                                const visible = [...section.querySelectorAll('[data-cps-unified-table="citizens"] tbody tr')].filter(row => !row.hidden);
                                require(visible.length === (type === 'presidential' ? 5 : 5), 'Filter rows');
                                visible.forEach(row => require((Number(row.dataset.cpsUnifiedYear) % 4 === 0 ? 'presidential' : 'midterm') === type, 'Wrong filtered year'));
                                [...section.querySelectorAll('[data-cps-unified-point]')].forEach(point => require(point.dataset.series === type, 'Wrong filtered point'));
                                require(!section.querySelector('[data-cps-unified-year="2004"]').hidden, 'Separate baseline lost');
                            }
                            state.value = '0'; group.value = '0'; election.value = 'all'; group.dispatchEvent(new Event('change'));
                            return { verified_cells: cells, plotted_points: points, verified_gap_safe_segments: segments,
                                     source_views: data.states.length * data.groups.length, election_filters: 2 };
                        }""", reference)
                        assert result["verified_cells"] == 13156 and result["source_views"] == 1196
                        assert not panel.locator('[data-cps-unified-point="2004"]').count()
                    else:
                        expect(controls).not_to_be_visible()
                        expect(panel.locator("[data-cps-unified-chart]")).not_to_be_visible()
                        if mode != "no_javascript":
                            expect(panel.locator("#cps-unified-selection")).to_contain_text("History controls unavailable.")
                        result = {"verified_cells": 11, "source_views": 1}
                        for i, year in enumerate(reference["years"]):
                            value = reference["values"][0][0][i]
                            actual = panel.locator(f'[data-cps-unified-year="{year}"] td').inner_text()
                            if len(value) == 2:
                                assert actual == f"{value[0]:.1f}% +/- {value[1]:.1f} pp"
                            else:
                                assert actual == "Not supplied for this geography/year/bin"
                    page.locator("#participation-research > details").nth(1).locator(":scope > summary").click()
                    for old in ("#participation-cps-early-history", "#participation-cps-older-history",
                                "#participation-cps-state-history", "#participation-columbia-wisconsin-history",
                                "#participation-ces-classification"):
                        expect(page.locator(old)).to_be_visible()
                    panel.locator("[data-cps-unified-methods] > summary").click()
                    for text in ("13,156", "all three original complete packages", "population, not respondent counts",
                                 "only the explicitly labeled 2008", "offline using only the Python standard library"):
                        expect(panel).to_contain_text(text)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    assets = []
                    for kind, filename in (("complete", "complete-analysis.zip"), ("observations", "observations.csv")):
                        link = panel.locator(f'[data-cps-unified-download="{kind}"]')
                        assert link.get_attribute("href") == f"{RELEASE}/{filename}"
                        if mode == "desktop" and downloads:
                            response = context.request.get(link.get_attribute("href"), timeout=60000)
                            assert response.ok, response.status
                            raw = response.body()
                            assert raw == (DATA / filename).read_bytes()
                            assets.append({"file": filename, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
                            if kind == "complete":
                                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                                    inventory = json.loads(archive.read("checksums.json"))
                                    assert set(archive.namelist()) == {*inventory, "checksums.json"}
                                    assert len(inventory) == 12
                                    for name, metadata in inventory.items():
                                        member = archive.read(name)
                                        assert len(member) == metadata["bytes"]
                                        assert hashlib.sha256(member).hexdigest() == metadata["sha256"]
                                    assert sum(name.endswith("/complete-analysis.zip") for name in inventory) == 3
                    if proof and interactive:
                        panel.screenshot(path=str(proof.with_suffix(f".{mode}.png")))
                    checks.append({"mode": mode, "passed": True, **result, "downloads": assets,
                                   "denominators_and_preserved_panels": True})
                finally:
                    context.close()
        finally:
            browser.close()
    result = {"base_url": base, "live_public_data": live_data, "checks": checks}
    if proof:
        with proof.open("x") as target:
            json.dump(result, target, indent=2)
            target.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:4321")
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--live-data", action="store_true")
    parser.add_argument("--no-downloads", action="store_true")
    args = parser.parse_args()
    check(args.base, args.proof, args.live_data, not args.no_downloads)

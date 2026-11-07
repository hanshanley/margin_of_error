"""Verify qualified local participation layers without substituting candidate votes."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:4321")
parser.add_argument("--proof", type=Path)
parser.add_argument("--source-overrides", action="store_true")
parser.add_argument("--mobile", action="store_true")
args = parser.parse_args()
if args.proof and args.proof.exists():
    raise ValueError("Refuse to replace an existing proof")


def original_features(snapshot, code):
    path = ROOT / f"data/precinct-results/{snapshot}/2026/{code}.geojson.gz"
    return json.loads(gzip.decompress(path.read_bytes()))["features"]


def number(value):
    return None if value in ("", "null", None) else float(value)


cases = [
    ("Idaho", "ID", "20261105-idaho-01", 448, 435),
    ("North Dakota", "ND", "20261105-north-dakota-02", 338, 0),
    ("Minnesota", "MN", "20261105-expansion-01", 4105, 2370),
    ("Rhode Island", "RI", None, 39, 0),
    ("Michigan", "MI", None, 58, 0),
    ("Vermont", "VT", None, 247, 241),
]
results = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    try:
        context = browser.new_context(viewport={"width": 390, "height": 844} if args.mobile
                                      else {"width": 1440, "height": 1100})
        if args.source_overrides:
            context.route("**/scripts/participation-explorer.js",
                          lambda route: route.fulfill(path=ROOT / "public/scripts/participation-explorer.js"))
            context.route("**/participation-precincts.json",
                          lambda route: route.fulfill(path=ROOT / "public/participation-precincts.json"))
        for name, code, snapshot, count, rates in cases:
            page = context.new_page()
            try:
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                response = page.goto(args.base_url.rstrip("/") + "/voter-participation/"
                                     "?view=states&year=2026&map-color=turnout&map-level=auto",
                                     wait_until="domcontentloaded")
                assert response.ok
                expect(page.locator("svg.turnout-map")).to_be_visible(timeout=90000)
                page.locator("#map-reset").click()
                page.locator("svg.turnout-map").scroll_into_view_if_needed()
                position = page.locator(f'.map-feature[data-state="{name}"]').evaluate("""path => {
                  const box = path.getBBox(), point = path.ownerSVGElement.createSVGPoint();
                  for (const y of [.5, .25, .75, .125, .375, .625, .875])
                    for (const x of [.5, .25, .75, .125, .375, .625, .875]) {
                      point.x = box.x + box.width * x; point.y = box.y + box.height * y;
                      if (path.isPointInFill(point)) {
                        const screen = point.matrixTransform(path.getScreenCTM());
                        if (document.elementFromPoint(screen.x, screen.y) === path)
                          return {x: screen.x, y: screen.y};
                      }
                    }
                  throw new Error('No interior state click point');
                }""")
                page.mouse.click(position["x"], position["y"])
                if code == "MN":
                    page.wait_for_function(
                        "document.querySelectorAll('.geographic-detail [data-level=\"county\"][data-rate]:not([data-rate=\"\"])').length === 64",
                        timeout=60000)
                    page.locator("#show-matched-precinct-participation").click()
                level = "municipality" if code in ("RI", "VT") else "precinct"
                features = page.locator(f'.geographic-detail .map-feature[data-level="{level}"]')
                expect(features).to_have_count(count, timeout=60000)
                actual = features.evaluate_all("""features => features.map(path => ({
                  key: path.dataset.geography, countyId: path.dataset.sourceCountyId,
                  ballots: path.dataset.count, registered: path.dataset.registered,
                  rate: path.dataset.rate, margin: path.dataset.margin ?? null,
                  fill: path.getAttribute('fill'), title: path.getAttribute('aria-label')
                }))""")
                assert len({row["key"] for row in actual}) == count
                assert sum(row["rate"] != "" for row in actual) == rates
                assert all(row["margin"] is None for row in actual)
                if snapshot:
                    expected = {feature["properties"]["key"]: feature["properties"]["participation"]
                                for feature in original_features(snapshot, code)}
                    assert set(expected) == {row["key"] for row in actual}
                    for row in actual:
                        native = expected[row["key"]]
                        assert number(row["ballots"]) == native["ballots"], (code, row["key"], "numerator")
                        assert number(row["registered"]) == native.get("registered", native.get("denominator"))
                        assert number(row["rate"]) == native["reported_pct"], (code, row["key"], "rate")
                elif code == "MI":
                    path = ROOT / "data/participation-map-repairs/20261107-01/MI-2026-qualified-precinct-counts.geojson.gz"
                    expected = {feature["properties"]["key"]: feature["properties"]
                                for feature in json.loads(gzip.decompress(path.read_bytes()))["features"]}
                    assert set(expected) == {row["key"] for row in actual}
                    for row in actual:
                        assert number(row["ballots"]) == expected[row["key"]]["ballots"]
                        assert number(row["registered"]) == expected[row["key"]]["denominator"]
                        assert number(row["rate"]) is None
                elif code == "VT":
                    path = ROOT / "data/participation-map-repairs/20261107-01/vermont-municipal-participation.geojson.gz"
                    expected = {feature["properties"]["name"]: feature["properties"]
                                for feature in json.loads(gzip.decompress(path.read_bytes()))["features"]}
                    for row in actual:
                        municipality_name = row["title"].split(" · 2026")[0]
                        assert number(row["ballots"]) == expected[municipality_name]["ballots"]
                        assert number(row["registered"]) == expected[municipality_name]["registered_voters"]
                        assert number(row["rate"]) == expected[municipality_name]["registered_turnout_pct"]
                    assert "2025" in page.locator("#geography-note").inner_text()
                else:
                    response = page.request.get(args.base_url.rstrip("/") + "/participation-local/RI.json.gz")
                    assert response.ok
                    expected = {row["county_id"]: row for row in json.loads(gzip.decompress(response.body()))["counties"]}
                    assert set(expected) == {row["countyId"] for row in actual}
                    for row in actual:
                        assert number(row["ballots"]) == expected[row["countyId"]]["ballots"]
                        assert number(row["registered"]) == expected[row["countyId"]]["denominator"]
                        assert number(row["rate"]) is None
                    assert "2024 Census" in page.locator("#geography-note").inner_text()
                    assert all("2024 Census" in row["title"] for row in actual)
                assert all(row["fill"] for row in actual)
                table_note = page.locator("#table-note").text_content()
                assert table_note.startswith(f"{count:,} observations"), (code, table_note)
                features.first.focus()
                features.first.press("Enter")
                detail = page.locator("#current-local-navigation" if code in ("RI", "VT") else "#substate-detail")
                expect(detail.locator(".selection-rate")).to_have_count(1)
                assert "candidate" not in detail.locator(".selection-rate").inner_text().lower()
                assert page.locator(".state-selection-outline").count() == 1
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), code
                page.select_option("#map-color", "margin")
                page.wait_for_function(
                    "document.querySelectorAll('.geographic-detail [data-margin]:not([data-margin=\"\"])').length > 0",
                    timeout=60000)
                assert not errors, errors
                results.append({"state": name, "features": count, "rates": rates,
                                "withheld_rates": count - rates, "every_payload_matches": True,
                                "election_results_preserved": True})
            finally:
                page.close()
        context.close()
    finally:
        browser.close()
proof = {
    "status": "PASS_qualified_local_participation_layers",
    "source_overrides": args.source_overrides, "states": results,
    "mobile": args.mobile,
    "script_sha256": hashlib.sha256((ROOT / "public/scripts/participation-explorer.js").read_bytes()).hexdigest(),
}
if args.proof:
    args.proof.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))

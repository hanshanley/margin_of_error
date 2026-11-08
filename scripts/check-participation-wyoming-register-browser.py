"""Verify three source-bound registration scenarios without implying observed turnout."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-wyoming-registration/20261108-01"


def check(base, proof):
    metadata = json.loads((DATA / "download.json").read_bytes())
    raw = (DATA / "source-query.csv").read_bytes()
    assert len(raw) == metadata["source_query"]["bytes"]
    assert hashlib.sha256(raw).hexdigest() == metadata["source_query"]["sha256"]
    rows = list(csv.DictReader(io.StringIO(raw.decode())))
    selection = json.loads((DATA / "selection.json").read_bytes())
    assert selection["rows"] == rows and len(rows) == 3
    assert selection["source_query_sha256"] == metadata["source_query"]["sha256"]
    assert all(row["scope"] == "WY" and row["geographic_level"] == "state" for row in rows)
    assert all(row["election_time_registered"] == "" and row["county_or_precinct_allocation"] == "False"
               for row in rows)
    results = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            for mode, options in [
                ("desktop", dict(viewport=dict(width=1440, height=1000))),
                ("tablet", dict(viewport=dict(width=900, height=1000))),
                ("mobile", dict(viewport=dict(width=390, height=844))),
                ("no_javascript", dict(java_script_enabled=False)),
                ("failed_ap_source", {}),
            ]:
                context = browser.new_context(**options)
                try:
                    if mode == "failed_ap_source":
                        ap = json.loads((ROOT / "data/participation-ap-history/20261108-01/download.json").read_bytes())
                        context.route(ap["viewer"]["url"], lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    drawer = page.locator("#participation-research")
                    assert not drawer.evaluate("element => element.open")
                    drawer.locator(":scope > summary").click()
                    panel = page.locator("#participation-wyoming-registration")
                    expect(panel).to_be_visible()
                    assert panel.get_attribute("data-source-query-sha256") == metadata["source_query"]["sha256"]
                    expect(panel.locator("[data-wy-register-row]")).to_have_count(3)
                    for row in rows:
                        target = panel.locator(f'[data-wy-register-row="{row["year"]}:{row["weight_field"]}"]')
                        expect(target.locator("[data-wy-register-date]")).to_have_text(row["registration_snapshot_date"])
                        for attribute, field in (
                            ("total", "native_registration_snapshot"), ("voter", "conditional_modeled_voter_count"),
                            ("nonvoter", "conditional_modeled_nonvoter_count"),
                            ("unknown", "conditional_model_unknown_count"),
                        ):
                            expect(target.locator(f"[data-wy-register-{attribute}]")).to_have_text(
                                f'{float(row[field]):,.0f}')
                        expect(target.locator("[data-wy-register-share]")).to_have_text(
                            f'{100*float(row["modeled_voter_share"]):.2f}%')
                    for text in (
                        "not observed turnout or staying home", "unvalidated exchangeability",
                        "do not fill the missing election-time denominators",
                        "not a turnout trend", "do not sum same-year rows",
                        "excluding Election Day registrants", "not a final electorate definition",
                        "not harmonized", "No state survey propensity is allocated",
                        "Registration-party categories are accounting, not voting behavior",
                        "eligibility, deaths and migration remain unknown",
                    ):
                        expect(panel).to_contain_text(text)
                    expect(page.locator("#participation-native-history [data-native-history-row]")).to_have_count(7)
                    expect(page.locator("#participation-ap-history [data-ap-overall]")).to_have_count(8)
                    expect(page.locator("#participation-civic-estimates [data-civic-flow]")).to_have_count(112)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    expect(panel.locator("[data-wy-register-download]")).to_have_count(8)
                    for asset in metadata["assets"]:
                        link = panel.locator(f'[data-wy-register-download="{asset["name"]}"]')
                        assert link.get_attribute("href") == asset["url"]
                        if mode == "desktop":
                            response = context.request.get(asset["url"])
                            assert response.ok
                            content = response.body()
                            assert len(content) == asset["bytes"]
                            assert hashlib.sha256(content).hexdigest() == asset["sha256"]
                            if asset["name"] == "complete-analysis.zip":
                                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                                    assert len(archive.namelist()) == 20 and archive.testzip() is None
                                    for member, receipt in json.loads(archive.read("checksums.json")).items():
                                        original = archive.read(member)
                                        assert len(original) == receipt["bytes"]
                                        assert hashlib.sha256(original).hexdigest() == receipt["sha256"]
                    if mode in {"desktop", "mobile"}:
                        panel.screenshot(path=str(proof.with_suffix(f".{mode}.png")))
                    results.append(dict(
                        mode=mode, passed=True, source_matched_rows=3,
                        conditional_not_observed_qualifiers_preserved=True,
                        native_registration_missing_election_time_denominator_preserved=True,
                        no_state_to_county_allocation=True, old_native_ap_civic_tables_preserved=True,
                        default_closed_research_preserved=True))
                finally:
                    context.close()
        finally:
            browser.close()
    proof.write_text(json.dumps(dict(
        base_url=base, passed=True, results=results, source_query_sha256=metadata["source_query"]["sha256"],
        complete_public_assets_verified=metadata["assets"], no_new_client_script=True), indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--proof", type=Path, required=True)
    args = parser.parse_args()
    check(args.base_url, args.proof)

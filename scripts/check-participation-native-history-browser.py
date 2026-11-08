"""Verify source-bound administrative histories, native holds and complete downloads."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-native-history/20261108-01"


def check(base, proof):
    metadata = json.loads((DATA / "download.json").read_bytes())
    raw = (DATA / "source-query.csv").read_bytes()
    assert len(raw) == metadata["source_query"]["bytes"]
    assert hashlib.sha256(raw).hexdigest() == metadata["source_query"]["sha256"]
    rows = list(csv.DictReader(io.StringIO(raw.decode())))
    assert len(rows) == 255
    expected = [r for r in rows if r["state_code"] in {"HI", "WY"} and r["control_id"]]
    assert len(expected) == 7
    selection = json.loads((DATA / "selection.json").read_bytes())
    assert selection["source_query_sha256"] == metadata["source_query"]["sha256"]
    assert len(selection["rows"]) == 7
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
                    panel = page.locator("#participation-native-history")
                    expect(panel).to_be_visible()
                    assert panel.get_attribute("data-source-query-sha256") == metadata["source_query"]["sha256"]
                    expect(panel.locator("[data-native-history-row]")).to_have_count(7)
                    for row in expected:
                        target = panel.locator(
                            f'[data-native-history-row="{row["state_code"]}:{row["year"]}"]')
                        held = row["control_measure"] != "reported_cast_ballots"
                        count = f'{int(row["native_control_numerator"]):,}' + (" (held)" if held else "")
                        expect(target.locator("[data-native-count]")).to_have_text(count)
                        registered = f'{int(row["native_registered"]):,}' if row["native_registered"] else "Not supplied"
                        expect(target.locator("[data-native-registered]")).to_have_text(registered)
                        fraction = (f'{100*int(row["reported_cast_ballots"])/int(row["native_registered"]):.2f}%'
                                    if not held and row["reported_cast_ballots"] and row["native_registered"]
                                    else "Not comparable")
                        expect(target.locator("[data-native-fraction]")).to_have_text(fraction)
                        status = ("Held: conflicting printed total" if held else
                                  "Source-labeled final" if row["source_labeled_final"] == "True"
                                  else "Preliminary snapshot")
                        expect(target.locator("[data-native-status]")).to_have_text(status)
                        assert target.get_attribute("data-native-qualified-cast") == str(not held).lower()
                        assert target.get_attribute("title") == row["source_time_label"]
                    for text in (
                        "not nationwide historical coverage", "Registration definitions are not harmonized",
                        "2026 counts are preliminary", "six ballots below the native unit sum",
                        "printed county total is two ballots higher", "No registration denominator is inferred",
                        "not eligibility rates, original-cohort retention or independent validation",
                        "not final-count turnout declines", "not silently harmonized",
                    ):
                        expect(panel).to_contain_text(text)
                    expect(page.locator("#participation-ap-history [data-ap-overall]")).to_have_count(8)
                    expect(page.locator("#participation-civic-estimates [data-civic-flow]")).to_have_count(112)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    expect(panel.locator("[data-native-history-download]")).to_have_count(6)
                    if mode == "desktop":
                        for asset in metadata["assets"]:
                            link = panel.locator(f'[data-native-history-download="{asset["name"]}"]')
                            assert link.get_attribute("href") == asset["url"]
                            response = context.request.get(asset["url"])
                            assert response.ok
                            body = response.body()
                            assert len(body) == asset["bytes"]
                            assert hashlib.sha256(body).hexdigest() == asset["sha256"]
                            if asset["name"] == "complete-analysis.zip":
                                with zipfile.ZipFile(io.BytesIO(body)) as archive:
                                    assert archive.testzip() is None
                                    for member, receipt in json.loads(archive.read("checksums.json")).items():
                                        content = archive.read(member)
                                        assert len(content) == receipt["bytes"]
                                        assert hashlib.sha256(content).hexdigest() == receipt["sha256"]
                        panel.screenshot(path=str(proof.with_suffix(".desktop.png")))
                    if mode == "mobile":
                        panel.screenshot(path=str(proof.with_suffix(".mobile.png")))
                    results.append(dict(
                        mode=mode, passed=True, rows=7, source_query_rows=255,
                        wyoming_held_and_missing_registration_preserved=True,
                        all_native_values_and_statuses_source_matched=True,
                        default_closed_research_preserved=True))
                finally:
                    context.close()
        finally:
            browser.close()
    proof.write_text(json.dumps(dict(
        base_url=base, passed=True, results=results, source_query_sha256=metadata["source_query"]["sha256"],
        complete_public_assets_verified=metadata["assets"],
        no_new_client_script=True), indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5083")
    parser.add_argument("--proof", type=Path, required=True)
    args = parser.parse_args()
    check(args.base_url, args.proof)

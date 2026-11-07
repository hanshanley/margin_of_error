"""Verify all selected Clark summary counts, honest scope and complete downloads."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "participation-clark-history/20261107-01/"


def check(base, proof):
    expected = json.loads((ROOT / "public" / PREFIX / "summary.json").read_bytes())
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for mode, options in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("mobile", {"viewport": {"width": 390, "height": 844}}),
                ("no_javascript", {"java_script_enabled": False}), ("failed_json", {}),
            ]:
                context = browser.new_context(**options)
                try:
                    if mode == "failed_json":
                        context.route("**/participation-clark-history/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    panel = page.locator("#participation-clark-history")
                    expect(panel.locator("[data-clark-observation]")).to_have_count(4)
                    for observation in expected["observations"]:
                        identity = f'{observation["year"]}-{observation["native_contest"]}'
                        row = panel.locator(f'[data-clark-observation="{identity}"]')
                        for field in ("native_reporting_units", "summed_native_registration_once_per_unit",
                                      "native_turnout", "turnout_exceeds_registration_units"):
                            expect(row.locator(f'[data-clark-count="{field}"]')).to_have_text(
                                format(observation[field], ","))
                        for method in ("Election Day", "Early Vote", "Mail"):
                            expect(row.locator(f'[data-clark-mode="{method}"]')).to_have_text(
                                format(observation["native_footer"][method]["native_turnout"], ","))
                    for text in ("3,894", "not candidate vote totals", "915 shared",
                                 "42 native registrations and 40 mail participants",
                                 "not interchangeable", "No turnout rates",
                                 "not 2026 participation"):
                        expect(panel).to_contain_text(text)
                    panel.locator("summary").click()
                    for text in ("All eight selected PDF/Data originals", "11,682",
                                 "not independent outcome evidence", "preserved but unused",
                                 "does not rerun it", "without network access"):
                        expect(panel).to_contain_text(text)
                    expect(panel.locator(".download-links a")).to_have_count(3)
                    expect(page.locator("#participation-registration-entry")).to_be_attached()
                    expect(page.locator("#participation-nd-history")).to_be_attached()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    if mode == "desktop":
                        for name in ("summary.json", "download.json", "complete-analysis.zip"):
                            response = context.request.get(base.rstrip("/") + "/" + PREFIX + name)
                            assert response.ok
                            assert response.body() == (ROOT / "public" / PREFIX / name).read_bytes()
                        metadata = json.loads((ROOT / "public" / PREFIX / "download.json").read_bytes())
                        raw = (ROOT / "public" / PREFIX / "complete-analysis.zip").read_bytes()
                        assert len(raw) == metadata["bytes"]
                        assert hashlib.sha256(raw).hexdigest() == metadata["sha256"]
                        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                            assert len(archive.namelist()) == metadata["members"]
                            assert archive.testzip() is None
                            inventory = json.loads(archive.read("checksums.json"))
                            assert set(inventory) == set(archive.namelist()) - {"checksums.json"}
                            for name, receipt in inventory.items():
                                member = archive.read(name)
                                assert len(member) == receipt["bytes"]
                                assert hashlib.sha256(member).hexdigest() == receipt["sha256"]
                    results.append({"mode": mode, "passed": True, "statement_rows": 4,
                                    "numeric_cells": 28})
                finally:
                    context.close()
        finally:
            browser.close()
    if proof:
        if proof.exists():
            raise ValueError("Require a new proof path")
        proof.write_text(json.dumps({"base_url": base, "checks": results}, indent=2) + "\n")
    print(json.dumps(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4331")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    check(args.base_url, args.proof)

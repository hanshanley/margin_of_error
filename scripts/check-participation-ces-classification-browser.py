"""Verify all selected classification rows, denominators, fallbacks and complete bytes."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "participation-ces-classification/20261107-01/"


def check(base, proof):
    if proof and proof.exists():
        raise FileExistsError("Refusing to overwrite an existing browser proof")
    expected = json.loads((ROOT / "public" / PREFIX / "classification-evidence.json").read_bytes())
    assert len(expected["rows"]) == 29 and len(expected["jurisdictions"]) == 51
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for mode, options in [
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("mobile", {"viewport": {"width": 390, "height": 844}}),
                ("no_javascript", {"java_script_enabled": False}),
                ("failed_json", {}),
            ]:
                context = browser.new_context(**options)
                try:
                    if mode == "failed_json":
                        context.route("**/participation-ces-classification/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    panel = page.locator("#participation-ces-classification")
                    expect(panel.locator("[data-ces-row]")).to_have_count(29)
                    expect(panel.locator("[data-ces-table]")).to_have_count(7)
                    numeric_cells = 0
                    for table in panel.locator("[data-ces-table]").all():
                        if table.get_attribute("open") is None:
                            table.locator("summary").click()
                        expect(table.locator("table")).to_be_visible()
                    for source in expected["rows"]:
                        row = panel.locator(
                            f'[data-ces-row][data-ces-dimension="{source["dimension"]}"]'
                            f'[data-ces-group="{source["group"]}"]')
                        values = {
                            "respondents": format(source["respondents"], ","),
                            "effective_sample_size_not_design_precision":
                                format(round(source["effective_sample_size_not_design_precision"]), ","),
                            "lower": f'{source["conditional_compatible_fraction"][0] * 100:.1f}%',
                            "upper": f'{source["conditional_compatible_fraction"][1] * 100:.1f}%',
                        }
                        for field in ("record_positive_weight_fraction", "classified_nonvote_weight_fraction",
                                      "unresolved_weight_fraction"):
                            values[field] = f'{source[field] * 100:.1f}%'
                        for field, value in values.items():
                            expect(row.locator(f'[data-ces-value="{field}"]')).to_have_text(value)
                            numeric_cells += 1
                    for count in expected["source_accounting"].values():
                        expect(panel.locator("[data-ces-response-accounting]")).to_contain_text(format(count, ","))
                    for text in (
                            "not population-turnout point estimates", "All unresolved histories stay",
                            "not a confidence interval", "not significance tests", "Nonexhaustive, overlapping",
                            "Income, urban/suburban/rural residence", "All 51 state/D.C. withholding dispositions",
                            "not allocated to states, counties or precincts",
                            "not exact election-day age or a fixed 2026 age cohort",
                            "not administrative sex", "not interchangeable", "not a product of demographic marginals"):
                        expect(panel).to_contain_text(text)
                    panel.locator("[data-ces-methods] summary").click()
                    for text in (
                            "conservative conflict-as-unknown", "W = P + N + U", "[P/W, (P+U)/W]", "P/(P+N)",
                            "commonpostweight", "June-July 2025", "Utah private/withheld",
                            "2020/2022 histories"):
                        expect(panel).to_contain_text(text)
                    expect(panel).to_contain_text("does not recreate private respondent extraction")
                    comparator = expected["record_only_compatible_fraction_same_post_frame_overall_only"]
                    for label, value in zip(("lower", "upper"), comparator):
                        expect(panel.locator(f'[data-ces-comparator="{label}"]')).to_have_text(f"{value * 100:.1f}%")
                        numeric_cells += 1
                    assert numeric_cells == 205
                    links = panel.locator(".download-links a")
                    expect(links).to_have_count(3)
                    assert [item.get_attribute("href") for item in links.all()] == [
                        "/" + PREFIX + name for name in (
                            "complete-analysis.zip", "classification-evidence.json", "download.json")]
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    expect(page.locator("#participation-registration-entry")).to_be_attached()
                    expect(page.locator("#participation-panel-intentions")).to_be_attached()
                    if mode == "desktop":
                        for name in ("classification-evidence.json", "download.json", "complete-analysis.zip"):
                            response = context.request.get(base.rstrip("/") + "/" + PREFIX + name)
                            assert response.ok
                            assert response.body() == (ROOT / "public" / PREFIX / name).read_bytes()
                        metadata = json.loads((ROOT / "public" / PREFIX / "download.json").read_bytes())
                        raw = (ROOT / "public" / PREFIX / "complete-analysis.zip").read_bytes()
                        assert len(raw) == metadata["bytes"]
                        assert hashlib.sha256(raw).hexdigest() == metadata["sha256"]
                        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                            assert archive.testzip() is None
                            inventory = json.loads(archive.read("checksums.json"))
                            assert len(archive.namelist()) == metadata["members"] == 13
                            assert set(inventory) == set(archive.namelist()) - {"checksums.json"}
                            for name, receipt in inventory.items():
                                member = archive.read(name)
                                assert len(member) == receipt["bytes"]
                                assert hashlib.sha256(member).hexdigest() == receipt["sha256"]
                    results.append({"mode": mode, "passed": True, "verified_numeric_cells": numeric_cells})
                finally:
                    context.close()
        finally:
            browser.close()
    if proof:
        with proof.open("x") as target:
            target.write(json.dumps({"base_url": base, "checks": results}, indent=2) + "\n")
    print(json.dumps(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4331")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    check(args.base_url, args.proof)

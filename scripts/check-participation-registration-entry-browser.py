"""Check registration-date counts, qualified denominators, fallbacks and complete bytes."""

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "participation-registration-entry/20261107-01/"


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
                        context.route("**/participation-registration-entry/**/*.json", lambda route: route.abort())
                    page = context.new_page()
                    page.goto(base.rstrip("/") + "/voter-participation/", wait_until="domcontentloaded")
                    panel = page.locator("#participation-registration-entry")
                    expect(panel.locator("[data-registration-county]")).to_have_count(2)
                    for source in expected["rows"]:
                        row = panel.locator(f'[data-registration-county="{source["county"]}"]')
                        for field in ("accepted_cohort", "post_2024_registration",
                                      "positive_2024_nc_history", "no_2024_nc_history_found"):
                            expect(row.locator(f'[data-registration-count="{field}"]')).to_have_text(
                                format(source[field], ","))
                        expect(row.locator("[data-registration-positive-share]")).to_have_text(
                            f'{source["positive_history_share_of_post_registration_pct"]:.1f}% of date group')
                    for text in ("not a first-ever registration date", "not all voters",
                                 "National participation unresolved", "No first-time-voter estimate",
                                 "Not final turnout or counted ballots", "November 2", "November 6",
                                 "No candidate choice, persuasion or staying home"):
                        expect(panel).to_contain_text(text)
                    panel.locator("summary").click()
                    for text in ("statewide NC general-election history",
                                 "Every record for an ambiguous registration or accepted identifier is excluded",
                                 "does not recreate private native linkage",
                                 "not estimates for North Carolina or the country"):
                        expect(panel).to_contain_text(text)
                    links = panel.locator(".download-links a")
                    expect(links).to_have_count(3)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                    expect(page.locator("#participation-panel-intentions")).to_be_attached()
                    if mode == "desktop":
                        for name in ("summary.json", "download.json", "complete-analysis.zip"):
                            response = context.request.get(base.rstrip("/") + "/" + PREFIX + name)
                            assert response.ok
                            assert response.body() == (ROOT / "public" / PREFIX / name).read_bytes()
                        metadata = json.loads((ROOT / "public" / PREFIX / "download.json").read_bytes())
                        raw = (ROOT / "public" / PREFIX / "complete-analysis.zip").read_bytes()
                        assert len(raw) == metadata["bytes"]
                        assert hashlib.sha256(raw).hexdigest() == metadata["sha256"]
                    results.append({"mode": mode, "passed": True})
                finally:
                    context.close()
        finally:
            browser.close()
    if proof:
        proof.write_text(json.dumps({"base_url": base, "checks": results}, indent=2) + "\n")
    print(json.dumps(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4331")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    check(args.base_url, args.proof)

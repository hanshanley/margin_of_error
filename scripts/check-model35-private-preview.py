"""Preview model35 with explicit local SDK fixtures and no SDK network requests."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DISPLAY = ROOT / "data/participation-registered-controls/20261114-35/display-model.json"
CATALOG_URL = (
    "https://raw.githubusercontent.com/hanshanley/margin_of_error/"
    "participation-data/catalog.json"
)
FAKE_COMMIT = "f" * 40
FAKE_BASE = (
    "https://raw.githubusercontent.com/hanshanley/margin_of_error/"
    + FAKE_COMMIT + "/participation-counts-2026/"
)


def pin(path):
    body = path.read_bytes()
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def check(base_url, proof, display_path, counts_root, count_sdk):
    display = json.loads(display_path.read_bytes())
    descriptor = json.loads((counts_root / "dataset.json").read_bytes())
    index = json.loads((counts_root / "index.json").read_bytes())
    current = json.loads(gzip.decompress(
        (counts_root / index["current_snapshot"]["file"]).read_bytes()))
    expected_reporting = {
        row["state_code"]: row for row in current["snapshot"]["reporting"]
        if row["state_code"] in ("NC", "OR")
    }
    catalog = {
        "contract": "participation.dataset_catalog.v1",
        "datasets": {
            "participation-counts-2026": {
                "contract": "participation.dataset.v1",
                "id": "participation-counts-2026",
                "status": "loaded",
                "version": descriptor["version"],
                "base_url": FAKE_BASE,
                "index": descriptor["index"],
                "complete_download": {
                    "url": display["count_download"]["url"],
                    **pin(count_sdk),
                    "immutable": True,
                    "verified_anonymously": True,
                },
            }
        },
    }
    checks = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            for width in (1440, 390):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                requests = []
                context.on("request", lambda request: requests.append(request.url))
                context.route(
                    CATALOG_URL,
                    lambda route: route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(catalog).encode(),
                    ),
                )

                def counts(route):
                    name = route.request.url.removeprefix(FAKE_BASE)
                    target = counts_root / name
                    if not target.is_file():
                        route.fulfill(status=404, body=b"missing fixture")
                        return
                    route.fulfill(
                        status=200,
                        headers={"content-type": (
                            "application/gzip" if name.endswith(".gz")
                            else "application/json")},
                        body=target.read_bytes(),
                    )

                context.route(FAKE_BASE + "**", counts)
                try:
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    for code, state in (("NC", "North%20Carolina"), ("OR", "Oregon")):
                        page.goto(
                            base_url.rstrip("/") + "/voter-participation/"
                            + f"?year=2026&state={state}&mode=official&map-level=state",
                            wait_until="domcontentloaded",
                            timeout=90000,
                        )
                        panel = page.locator("#selection-panel")
                        row = expected_reporting[code]
                        expect(panel).to_contain_text(f'{row["ballots"]:,}', timeout=90000)
                        expect(panel).to_contain_text(row["source_update_label"])
                        expect(panel.locator("a.source-link").first).to_have_attribute(
                            "href", row["source_url"])
                    drawer = page.locator("#participation-research")
                    drawer.locator(":scope > summary").click()
                    drawer.get_by_text(
                        "Additional survey tables and model assumptions", exact=True).click()
                    frame = page.locator("[data-native-registered-controls]")
                    expect(frame).to_have_attribute("data-native-version", "35")
                    frame.locator(":scope > summary").click()
                    expect(frame.locator("[data-native-reference-change]")).to_have_count(2)
                    expect(frame.locator(
                        '[data-native-reference-change="reporting-NC"]')).to_have_attribute(
                        "data-native-reference-current", "4242662")
                    or_change = frame.locator(
                        '[data-native-reference-change="reporting-OR"]')
                    expect(or_change).to_have_attribute(
                        "data-native-registered-difference", "-22")
                    expect(or_change).to_have_attribute(
                        "data-native-modeled-voter-difference",
                        "-14.7416565894603554070505860949628091008651443279001558242930301316261507203",
                    )
                    expect(frame.locator(
                        '[data-native-publication-status="verified_immutable"]')).to_contain_text(
                        "Verified immutable releases")
                    expect(frame.locator(
                        '[data-native-registered-download="model-zip"]')).to_have_attribute(
                            "href", display["complete_download"]["url"])
                    expect(frame.locator(
                        '[data-native-registered-download="count-zip"]')).to_have_attribute(
                            "href", display["count_download"]["url"])
                    nm = frame.locator(
                        '[data-native-registered-scenario="nm-2026-native-general-registered-turnout"]')
                    expect(nm).to_contain_text("11/12/2026 11:07 AM MT")
                    expect(frame.locator("[data-native-registered-scenario]")).to_have_count(34)
                    expect(frame.locator("[data-native-registered-state]")).to_have_count(51)
                    assert not [url for url in requests
                                if "participation-nc-or-native-controls-r35" in url]
                    assert not [url for url in requests
                                if "participation-nc-or-native-counts-20261114-01/"
                                "complete-analysis.zip" in url]
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth")
                    assert not errors, errors
                    frame.scroll_into_view_if_needed()
                    page.screenshot(path=str(proof.with_suffix(f".{width}.png")))
                    checks.append({
                        "width": width,
                        "model_version": 35,
                        "count_version": descriptor["version"],
                        "NC_ballots": expected_reporting["NC"]["ballots"],
                        "OR_ballots": expected_reporting["OR"]["ballots"],
                        "NC_OR_changes_rendered": 2,
                        "NM_current_revision_retained": True,
                        "verified_sdk_links_not_requested": True,
                        "future_catalog_fixture_used": True,
                        "no_overflow": True,
                    })
                finally:
                    context.close()
        finally:
            browser.close()
    result = {
        "status": "PASS_private_full_page_fixture_preview_not_publication_evidence",
        "base_url": base_url,
        "test_fixture_used": True,
        "fixture_simulates_future_catalog_verified_flags": True,
        "actual_sdk_creation_flags_remain_planned_unverified": True,
        "external_publication_receipts_projected_verified": True,
        "checks": checks,
    }
    proof.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4327")
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--display", type=Path, default=DEFAULT_DISPLAY)
    parser.add_argument("--count-sdk-root", type=Path, required=True)
    parser.add_argument("--count-sdk-archive", type=Path, required=True)
    args = parser.parse_args()
    if args.proof.exists():
        raise ValueError("Use a fresh private preview proof")
    check(args.base_url, args.proof, args.display, args.count_sdk_root, args.count_sdk_archive)

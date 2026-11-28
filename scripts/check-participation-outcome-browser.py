"""Verify recorded counts against the page-session congressional snapshot, not models."""

import argparse
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def check(args):
    results = []
    base = args.base.rstrip("/") + "/voter-participation/"
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        for width in [320, 390, 768, 1280]:
            page = browser.new_page(viewport={"width": width, "height": 1000},
                                    is_mobile=width < 700, has_touch=width < 700)
            errors, payloads = [], []
            page.on("pageerror", lambda e: errors.append(str(e)))

            def capture(response):
                if "/congressional/results.json.gz" in response.url and response.ok:
                    body = response.body()
                    payloads.append(json.loads(gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body))

            page.on("response", capture)
            page.goto(base + "?view=national", wait_until="domcontentloaded")
            expect(page.locator("#year")).to_have_value("2024", timeout=60000)
            expect(page.locator(".demographic-card").first).to_be_visible(timeout=60000)
            page.goto(base + "?view=national&year=2026&mode=civic_model&countState=MO&dimension=sex")
            expect(page.locator(".group-validation-warning")).to_be_visible(timeout=60000)
            expect(page.locator(".group-validation-warning")).to_contain_text("Not validated against completed 2026 turnout")
            expect(page.locator(".civic-group-row")).to_have_count(2)
            page.locator(".group-observed-link").click()
            expect(page.locator("#year")).to_have_value("2024", timeout=60000)
            expect(page.locator("#demographic-state")).to_have_value("MO")
            page.goto(base + "?view=effects")
            root = page.locator("#participation-return-drivers")
            expect(root.locator("[data-driver-view]")).to_have_value("house_transition_home", timeout=60000)
            root.locator("[data-driver-view]").select_option("reported_counts")
            expect(root.locator("[data-driver-view]")).to_have_value("reported_counts", timeout=60000)
            summary = root.locator("[data-driver-summary]")
            expect(summary).to_have_attribute("data-recorded-source", "current-congressional-counts", timeout=60000)
            assert payloads
            data = payloads[-1]
            states = data["house_states"]
            assert len(states) == 50
            paths = root.locator("[data-driver-map] path.driver-state")
            expect(paths).to_have_count(51)
            actual = paths.evaluate_all("es=>Object.fromEntries(es.map(e=>[e.dataset.stateCode,e.dataset.modelValue]))")
            for row in states:
                code = row["state_code"]
                if row["qualified_comparison"]:
                    assert abs(float(actual[code]) - row["raw_recorded_D_share_change_pp"]) < 1e-8
                else:
                    assert actual[code] == ""
                root.locator("[data-driver-state]").select_option(code)
                expect(summary).to_have_attribute("data-norc-state", code)
                expect(summary).to_have_attribute("data-recorded-source", "current-congressional-counts")
                assert abs(float(summary.get_attribute("data-recorded-raw-share-change")) - row["raw_recorded_D_share_change_pp"]) < 1e-8
                text = summary.text_content()
                for party in ["D", "R", "O"]:
                    assert f"{row['current'][party]:,}" in text
                assert (summary.get_attribute("data-norc-hold") == "true") == (not row["qualified_comparison"])
            root.locator("[data-driver-state]").select_option("MO")
            expect(summary.locator(":scope > .driver-recorded-endpoints")).to_be_visible()
            root.locator("[data-driver-summary]").scroll_into_view_if_needed()
            if args.images:
                page.screenshot(path=args.images / f"recorded-missouri-{width}.png")
            audit = page.locator("#estimate-outcome-check")
            audit.locator("summary").click()
            expect(audit.locator("[data-outcome-check-state]")).to_have_count(50)
            expect(audit).to_contain_text("2.68 percentage points")
            expect(audit.locator('[data-outcome-check-state="MO"]')).to_contain_text("+9.97")
            expect(audit.locator('[data-outcome-check-state="MO"]')).to_contain_text("+5.32")
            audit.locator("summary").click()
            root.locator(".driver-options > summary").click()
            root.locator("[data-driver-view]").select_option("source_total")
            expect(root.locator("[data-driver-model-warning]")).to_be_visible()
            expect(summary).to_have_attribute("data-source-model-state", "MO", timeout=60000)
            expect(summary.locator(".driver-value")).to_have_text("+5.32 pp")
            assert page.evaluate("document.documentElement.scrollWidth") <= width + 1
            assert not errors, errors
            results.append(dict(width=width, current_state_count_checks=50,
                map_gates_follow_current_congress=True, model_gates_not_substituted=True,
                reported_group_default_2024=True, explicit_2026_classifications_preserved_and_flagged=True))
            args.output.with_suffix(".progress.json").write_text(json.dumps(results, indent=2) + "\n")
            page.close()
        page = browser.new_page(viewport={"width": 390, "height": 1000})
        page.route("**/congressional/results.json.gz", lambda route: route.fulfill(status=503, body="Injected congressional source outage"))
        page.goto(base + "?view=effects")
        expect(page.locator("[data-driver-view]")).to_have_value("house_transition_home", timeout=60000)
        page.locator("[data-driver-view]").select_option("reported_counts")
        expect(page.locator("[data-driver-counts-notice]")).to_be_visible(timeout=60000)
        expect(page.locator("[data-driver-counts-notice]")).to_contain_text("older saved model-endpoint snapshot")
        page.close()
        page = browser.new_page(java_script_enabled=False)
        page.goto(base + "#estimate-outcome-check")
        page.evaluate("document.fonts.ready")
        page.locator("#estimate-outcome-check > summary").focus()
        page.locator("#estimate-outcome-check > summary").press("Enter")
        expect(page.locator("[data-outcome-check-state]")).to_have_count(50)
        expect(page.locator("#estimate-outcome-check tbody")).to_be_visible()
        page.close()
        browser.close()
    proof = dict(status="passed", base=args.base, results=results,
                 unavailable_current_feed_explicitly_flagged=True, nojs_all_state_audit=True)
    args.output.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--images", type=Path)
    args = parser.parse_args()
    if args.images:
        args.images.mkdir(parents=True, exist_ok=True)
    check(args)

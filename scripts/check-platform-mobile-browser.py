"""Exercise the editorial DSA reader with real source values at four widths."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def fits(page, width):
    assert page.evaluate("document.documentElement.scrollWidth") == width
    for control in page.locator(".platform-page select:visible, .chart-mode button:visible").all():
        box = control.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width + 1, box
        assert box["height"] >= 44, box


def snapshot(page, args, name, width):
    if args.screenshots:
        page.evaluate("scrollTo({top:0,behavior:'instant'})")
        page.screenshot(path=args.screenshots / f"{name}-{width}.png")


def check(args):
    parties = json.loads((args.website / "public/party-platforms/analysis.json").read_text())
    caucuses = json.loads((args.website / "public/party-platforms/caucuses/analysis.json").read_text())
    density = json.loads((args.website / "public/party-platforms/density-map.json").read_text())
    issues = {topic["topic_id"]: topic for topic in parties["topics"]}
    results = []
    url = args.base.rstrip("/") + "/party-platforms/"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in args.widths:
            page = browser.new_page(viewport={"width": width, "height": 1000},
                                    is_mobile=width < 700, has_touch=width < 700)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script("""(() => {
              const original = CanvasRenderingContext2D.prototype.fillText;
              CanvasRenderingContext2D.prototype.fillText = function(text,x,y,...rest) {
                if (this.canvas.classList.contains('issue-time-chart')) {
                  const m=this.measureText(text), r=this.canvas.getBoundingClientRect();
                  const left=x-(this.textAlign==='center'?m.width/2:this.textAlign==='right'?m.width:0);
                  (this.canvas.textBoxes ??= []).push({text,left,right:left+m.width,
                    top:y-m.actualBoundingBoxAscent,bottom:y+m.actualBoundingBoxDescent,
                    width:r.width,height:r.height});
                }
                return original.call(this,text,x,y,...rest);
              };
            })();""")
            assert page.goto(url, wait_until="domcontentloaded").ok
            expect(page.locator(".platform-page")).to_have_attribute("data-reader-ready", "true")
            page.evaluate("document.fonts.ready")
            tabs = page.locator(".section-links [role=tab]")
            expect(tabs).to_have_count(3)
            expect(page.locator("[data-platform-panel]:visible")).to_have_count(1)
            expect(page.locator("#overview-mobile-subject")).to_be_visible()
            if width < 700:
                menu = page.locator(".platform-mobile-menu")
                menu.locator("summary").tap()
                expect(menu.locator("nav")).to_be_visible()
                menu.locator("summary").tap()
                last = page.locator(".mobile-topic:visible .mobile-party").last.bounding_box()
                assert last["y"] + last["height"] < 800, last
            fits(page, width)
            snapshot(page, args, "parties", width)
            subject_count = page.locator("#overview-mobile-subject option").count()
            assert subject_count == len(issues)
            for identity, source in issues.items():
                page.locator("#overview-mobile-subject").select_option(identity)
                topic = page.locator(f"#issue-{identity}")
                expect(page.locator(".mobile-topic:visible")).to_have_count(1)
                expect(topic.locator(".attention-bars")).to_be_visible()
                expect(topic.locator(".issue-timeline")).to_be_hidden()
                for group in ("democratic", "republican", "dsa"):
                    value = next(float(row["share"]) for row in source["shares"]
                                 if row["view"] == "expanded" and row["group"] == group)
                    row = topic.locator(f".mobile-value[data-group={group}]")
                    assert float(row.get_attribute("data-value")) == value
                    assert row.locator(".mobile-number").inner_text() == f"{100*value:.1f}%"
                right_edges = topic.locator(".mobile-number").evaluate_all("es=>es.map(e=>e.getBoundingClientRect().right)")
                assert max(right_edges) - min(right_edges) < 1
                tracks = topic.locator(".mobile-track").evaluate_all("es=>es.map(e=>({left:e.getBoundingClientRect().left,width:e.getBoundingClientRect().width}))")
                assert max(row["left"] for row in tracks) - min(row["left"] for row in tracks) < 1
                assert max(row["width"] for row in tracks) - min(row["width"] for row in tracks) < 1
                expect(topic.locator(".position-readout")).to_have_count(3)
                detail = topic.locator(".position-evidence").first
                detail.locator("summary").click()
                expect(detail.locator(".group-position")).to_be_visible()
                detail.locator("summary").click()
                length = page.evaluate("history.length")
                page.locator("[data-party-mode=history]").click()
                assert page.evaluate("history.length") == length
                expect(topic.locator(".attention-bars")).to_be_hidden()
                canvas = topic.locator("canvas")
                expect(canvas).to_be_visible()
                page.wait_for_function("e=>e.width>0 && e.textBoxes?.length>0", arg=canvas.element_handle())
                clipped = canvas.evaluate("""e=>e.textBoxes.filter(b=>
                  b.left < -1 || b.right > b.width+1 || b.top < -1 || b.bottom > b.height+1)""")
                assert not clipped, (width, identity, clipped)
                all_values = topic.locator(".issue-all-values")
                all_values.locator(":scope > summary").click()
                periods = all_values.locator(".timeline-values")
                periods.locator("summary").click()
                assert periods.locator("tbody tr").count() == len(json.loads(canvas.get_attribute("data-timeline")))
                ratios = all_values.locator(".attention-table")
                ratios.locator("summary").click()
                expect(ratios.locator("tbody tr")).to_have_count(4)
                all_values.locator(":scope > summary").click()
                if identity == list(issues)[0]:
                    snapshot(page, args, "history", width)
                page.locator("[data-party-mode=overall]").click()
                fits(page, width)
            party_selection = page.locator("#overview-mobile-subject").input_value()
            page.locator("[data-platform-view=caucuses]").click()
            expect(page.locator("#overview")).to_be_hidden()
            cases = 0
            for source in caucuses["topics"]:
                page.locator("#caucus-topic-select").select_option(source["id"])
                panel = page.locator(f"[data-caucus-topic='{source['id']}']")
                expect(panel).to_be_visible()
                expect(panel.locator(".caucus-row")).to_have_count(13)
                for group in source["groups"]:
                    row = panel.locator(f"[data-caucus='{group['id']}']")
                    assert float(row.get_attribute("data-share")) == group["share"]
                    actual = row.get_attribute("data-ratio")
                    assert (None if actual is None else float(actual)) == group["ratio"]
                    cases += 1
                for index in (0, 6, 12):
                    row = panel.locator(".caucus-row").nth(index)
                    row.scroll_into_view_if_needed()
                    top = row.bounding_box()["y"]
                    row.tap() if width < 700 else row.click()
                    position = row.locator("..")
                    expect(position).to_have_attribute("open", "")
                    expect(position.locator(".caucus-position-body")).to_be_visible()
                    assert abs(row.bounding_box()["y"] - top) < 2, "Inline disclosure unexpectedly moved the reader"
                    assert panel.locator(".caucus-position[open]").count() == 1
                    row.click()
                fits(page, width)
            page.locator("#caucus-topic-select").select_option(index=0)
            snapshot(page, args, "caucuses", width)
            first = page.locator(".caucus-issue:visible .caucus-row").first
            first.click()
            if args.screenshots:
                first.evaluate("e=>e.scrollIntoView({block:'start'})")
                page.screenshot(path=args.screenshots / f"inline-caucus-{width}.png")
            caucus_selection = page.locator("#caucus-topic-select").input_value()
            page.locator("[data-platform-view=language]").click()
            expect(page.locator("#density-explorer")).to_have_attribute("data-ready", "true", timeout=60000)
            pairs = page.locator("#density-pair option").evaluate_all("es=>es.map(e=>e.value)")
            for pair in pairs:
                page.locator("#density-pair").select_option(pair)
                for index in (0, len(density["topics"]) - 1):
                    page.locator("#density-topic").select_option(index=index)
                    expect(page.locator("#density-unpin")).to_be_visible()
                    expect(page.locator(".density-topic:visible")).to_have_attribute("data-topic", density["topics"][index]["topic_id"])
                    page.locator("#density-unpin").click()
                    expect(page.locator("#density-unpin")).to_be_hidden()
            page.locator("#density-pair").select_option("dsa_vs_democratic_republican")
            page.locator("#density-canvas").focus()
            page.keyboard.press("ArrowLeft")
            expect(page.locator("#density-unpin")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator("#density-unpin")).to_be_hidden()
            point = density["points"][0]
            canvas = page.locator("#density-canvas")
            box = canvas.bounding_box()
            x = 16 + (point[1] - density["limits"][0][0]) / (density["limits"][0][1] - density["limits"][0][0]) * (box["width"] - 32)
            y = box["height"] - 16 - (point[2] - density["limits"][1][0]) / (density["limits"][1][1] - density["limits"][1][0]) * (box["height"] - 32)
            if width < 700:
                canvas.tap(position={"x": x, "y": y})
            else:
                canvas.click(position={"x": x, "y": y})
            expect(page.locator("#density-unpin")).to_be_visible()
            expect(page.locator("#density-explorer")).to_have_attribute("data-topic", density["topics"][point[3]]["topic_id"])
            language_selection = page.locator("#density-topic").input_value()
            fits(page, width)
            snapshot(page, args, "language", width)
            for view in ("parties", "caucuses", "language"):
                page.locator(f"[data-platform-view={view}]").click()
            assert page.locator("#density-topic").input_value() == language_selection
            page.locator("[data-platform-view=parties]").click()
            assert page.locator("#overview-mobile-subject").input_value() == party_selection
            page.go_back()
            expect(page.locator("[data-platform-panel=language]")).to_be_visible()
            page.locator("[data-platform-view=caucuses]").click()
            assert page.locator("#caucus-topic-select").input_value() == caucus_selection
            page.locator("[data-platform-view=caucuses]").focus()
            page.keyboard.press("ArrowLeft")
            expect(page.locator("[data-platform-view=parties]")).to_be_focused()
            expect(page.locator("#overview")).to_be_visible()
            if width == 390:
                page.set_viewport_size({"width": 1280, "height": 1000})
                expect(page.locator("#overview-mobile-subject")).to_be_visible()
                assert page.locator("#overview-mobile-subject").input_value() == party_selection
                page.set_viewport_size({"width": width, "height": 1000})
            if width == min(args.widths):
                page.add_style_tag(content="html{font-size:200% !important}")
                for view in ("parties", "caucuses", "language"):
                    page.locator(f"[data-platform-view={view}]").click()
                    fits(page, width)
                snapshot(page, args, "enlarged-language", width)
            assert not errors, errors
            results.append({"width": width, "issue_charts": subject_count, "exact_caucus_values": cases,
                            "density_comparisons": len(pairs), "aligned_values": True,
                            "inline_disclosures": True, "selection_and_back": True, "controls_fit": True})
            page.close()
        page = browser.new_page(viewport={"width": 390, "height": 1000})
        targets = ["#issue-topic-022", "#timeline-topic-003", "#ratios-topic-018", "#organization-dsa",
                   "#caucus-topic-005"]
        example = next((topic, group) for topic in caucuses["topics"] for group in topic["groups"] if group["examples"])
        targets += [f"#caucus-position-{example[0]['id']}-{example[1]['id']}",
                    f"#caucus-evidence-{example[0]['id']}-{example[1]['id']}",
                    "#map-democratic_vs_dsa-topic-003"]
        for target in targets:
            page.goto(url + target)
            expect(page.locator(".platform-page")).to_have_attribute("data-reader-ready", "true")
            expect(page.locator(target)).to_be_visible(timeout=60000)
            if target.startswith("#map-"):
                expect(page.locator("#density-explorer")).to_have_attribute("data-ready", "true")
                expect(page.locator("#density-unpin")).to_be_visible()
            elif target.startswith("#caucus-"):
                expect(page.locator("[data-platform-view=caucuses]")).to_have_attribute("aria-selected", "true")
            else:
                expect(page.locator("[data-platform-view=parties]")).to_have_attribute("aria-selected", "true")
        page.goto(url + "?chart=history#issue-topic-022")
        expect(page.locator("#issue-topic-022 canvas")).to_be_visible()
        for width in args.widths:
            page.set_viewport_size({"width": width, "height": 1000})
            assert page.goto(url + "sources/").ok
            expect(page.locator("#topic-filter")).to_be_visible()
            fits(page, width)
        page.close()
        page = browser.new_page(java_script_enabled=False, viewport={"width": 390, "height": 1000})
        page.goto(url)
        assert page.locator(".caucus-row").count() == len(caucuses["topics"]) * 13
        expect(page.locator(".mobile-topic .group-position")).to_have_count(63)
        detail = page.locator(".position-evidence").first
        detail.locator("summary").click()
        expect(detail.locator(".group-position")).to_be_visible()
        page.locator(".caucus-issue").first.locator(".caucus-row").first.click()
        expect(page.locator(".caucus-position-body").first).to_be_visible()
        expect(page.locator("#density a[href='/party-platforms/sources/']").first).to_be_visible()
        fits(page, 390)
        page.close()
        browser.close()
    proof = {"status": "passed", "base": args.base, "results": results,
             "deep_links": targets, "history_link": True, "source_page_widths": args.widths,
             "nojs_caucus_rows": len(caucuses["topics"]) * 13}
    args.output.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8437")
    parser.add_argument("--website", type=Path, default=Path.cwd())
    parser.add_argument("--widths", nargs="+", type=int, default=[320, 390, 768, 1280])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    check(args)

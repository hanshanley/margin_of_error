"""Check responsive DSA issue charts, language maps and caucus navigation."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def fits(page, width):
    assert page.evaluate("document.documentElement.scrollWidth") == width
    for control in page.locator(".platform-page select:visible, .overview-toolbar button:visible").all():
        box = control.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width + 1, box
        if width <= 880:
            assert box["height"] >= 44, box


def check(args):
    data = json.loads((args.website / "public/party-platforms/caucuses/analysis.json").read_text())
    results = []
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
            response = page.goto(args.base.rstrip("/") + "/party-platforms/", wait_until="domcontentloaded")
            assert response.ok
            if width < 700:
                expect(page.locator("#overview-mobile-subject")).to_be_visible()
                expect(page.locator("#overview-picker")).to_be_hidden()
                menu = page.locator(".platform-mobile-menu")
                menu.locator("summary").tap()
                expect(menu.locator("nav a")).to_have_count(5)
                expect(menu.locator("nav")).to_be_visible()
                menu.locator("summary").tap()
                expect(menu).not_to_have_attribute("open", "")
            else:
                expect(page.locator("#overview-picker")).to_be_visible()
            page.evaluate("document.fonts.ready")
            if width <= 880:
                assert "Avenir Next" in page.locator(".mobile-party:visible").first.evaluate("e=>getComputedStyle(e).fontFamily")
            if width < 700:
                page.wait_for_function("""() => {
                  const rows=[...document.querySelectorAll('.mobile-topic:not([hidden]) .mobile-party')]
                    .filter(e=>e.getBoundingClientRect().height);
                  return rows.length===3 && rows[2].getBoundingClientRect().bottom<800;
                }""")
                last_party = page.locator(".mobile-topic:visible .mobile-party").last.bounding_box()
                assert last_party["y"] + last_party["height"] < 800
                expect(page.locator(".mobile-topic:visible .mobile-party-positions")).not_to_have_attribute("open", "")
                expect(page.locator(".mobile-topic:visible .group-position").first).to_be_hidden()
            fits(page, width)
            if args.screenshots:
                page.screenshot(path=args.screenshots / f"page-{width}.png")
            subjects = page.locator("[data-overview-subject]").count()
            for index in range(subjects):
                topic = page.locator(".mobile-topic:visible")
                expect(topic).to_have_count(1)
                expect(topic.locator(".mobile-value")).to_have_count(3)
                if width < 700:
                    positions = topic.locator(".mobile-party-positions")
                    expect(positions.locator(".group-position")).to_have_count(3)
                    positions.locator("summary").tap()
                    expect(positions.locator(".group-position").last).to_be_visible()
                    positions.locator("summary").tap()
                canvas = topic.locator("canvas")
                page.wait_for_function("e => e.width > 0 && e.textBoxes?.length > 0", arg=canvas.element_handle())
                clipped = canvas.evaluate("""e => e.textBoxes.filter(b =>
                  b.left < -1 || b.right > b.width+1 || b.top < -1 || b.bottom > b.height+1)""")
                assert not clipped, (width, topic.get_attribute("data-topic"), clipped)
                if index + 1 < subjects:
                    if width < 700:
                        page.locator("#overview-mobile-subject").select_option(index=index + 1)
                    else:
                        page.locator("#overview-subject-next").click()
            if width == 390:
                page.set_viewport_size({"width": 1280, "height": 1000})
                expect(page.locator(".mobile-topic:visible .mobile-value > .group-position")).to_have_count(3)
                expect(page.locator(".mobile-topic:visible .mobile-party-positions")).to_be_hidden()
                page.set_viewport_size({"width": width, "height": 1000})
                expect(page.locator(".mobile-topic:visible .mobile-party-positions .group-position")).to_have_count(3)
            page.locator(".section-links a[href='#density']").click()
            expect(page.locator("#density-explorer")).to_have_attribute("data-ready", "true", timeout=60000)
            pairs = page.locator("#density-pair option").evaluate_all("es=>es.map(e=>e.value)")
            for pair in pairs:
                page.locator("#density-pair").select_option(pair)
                page.locator("#density-topic").select_option(index=0)
                expect(page.locator("#density-unpin")).to_be_visible()
                page.locator("#density-unpin").click()
                expect(page.locator("#density-unpin")).to_be_hidden()
            fits(page, width)
            if args.screenshots:
                page.locator("#density").evaluate("e=>scrollTo({top:e.offsetTop,behavior:'instant'})")
                page.screenshot(path=args.screenshots / f"density-{width}.png")
            page.locator(".section-links a[href='#caucuses']").click()
            if width <= 880:
                expect(page.locator(".caucus-issue:visible .caucus-theme-context")).not_to_have_attribute("open", "")
                assert page.locator(".caucus-issue:visible .caucus-row").first.bounding_box()["y"] - page.locator("#caucuses").bounding_box()["y"] < 550
            cases = 0
            for topic in data["topics"]:
                page.locator("#caucus-topic-select").select_option(topic["id"])
                panel = page.locator(f"[data-caucus-topic='{topic['id']}']")
                expect(panel).to_be_visible()
                expect(panel.locator(".caucus-row")).to_have_count(13)
                for group in topic["groups"]:
                    row = panel.locator(f"[data-caucus='{group['id']}']")
                    assert float(row.get_attribute("data-share")) == group["share"]
                    actual = row.get_attribute("data-ratio")
                    assert (None if actual is None else float(actual)) == group["ratio"]
                    cases += 1
                for index in (0, 6, 12):
                    row = panel.locator(".caucus-row").nth(index)
                    if width < 700:
                        row.tap()
                    else:
                        row.click()
                    position = panel.locator(".caucus-position:visible")
                    assert position.get_attribute("data-caucus-position") == row.get_attribute("data-caucus")
                    if width < 700:
                        expect(position.locator(".caucus-position-name")).to_be_in_viewport()
                        position.locator(".caucus-back").click()
                        expect(row).to_be_focused()
            fits(page, width)
            if args.screenshots:
                page.locator("#caucus-topic-select").select_option(index=0)
                page.locator("#caucuses").evaluate("e=>scrollTo({top:e.offsetTop,behavior:'instant'})")
                page.screenshot(path=args.screenshots / f"caucuses-{width}.png")
            assert not errors, errors
            results.append({"width": width, "issue_charts": subjects, "exact_caucus_values": cases,
                            "density_comparisons": len(pairs), "controls_fit": True})
            page.close()
        page = browser.new_page(java_script_enabled=False, viewport={"width": 390, "height": 1000})
        page.goto(args.base.rstrip("/") + "/party-platforms/")
        expect(page.locator(".caucus-issue")).to_have_count(len(data["topics"]))
        assert page.locator(".caucus-row").count() == len(data["topics"]) * 13
        expect(page.locator(".mobile-topic .group-position")).to_have_count(63)
        expect(page.locator(".group-position").first).to_be_visible()
        expect(page.locator("#density a[href='/party-platforms/sources/']").first).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth") == 390
        page.close()
        browser.close()
    proof = {"status": "passed", "base": args.base, "results": results, "nojs_caucus_rows": len(data["topics"]) * 13}
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

"""Check every state's modeled House switching/no-ballot comparison and legacy isolation."""

import argparse
import gzip
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def check(args):
    results = []
    url = args.base.rstrip('/') + '/voter-participation/?view=effects'
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        for width in [320, 390, 768, 1280]:
            page = browser.new_page(viewport=dict(width=width, height=1000),
                                    is_mobile=width < 700, has_touch=width < 700)
            errors, captures = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def capture(response):
                if response.ok and response.url.endswith(('/viewer-data.json.gz', '/statewide-transitions/viewer.json.gz')):
                    body = response.body()
                    value = json.loads(gzip.decompress(body) if body[:2] == b'\x1f\x8b' else body)
                    if value.get('contract') == 'participation.statewide_house_transitions.v1':
                        captures.append(value)

            page.on('response', capture)
            page.goto(url, wait_until='domcontentloaded')
            root = page.locator('#participation-return-drivers')
            view = root.locator('[data-driver-view]')
            expect(view).to_have_value('house_transition_home', timeout=60000)
            paths = root.locator('path[data-house-transition]')
            expect(paths).to_have_count(51, timeout=60000)
            assert captures, 'Actual model response was not captured'
            data = captures[-1]
            rows = {row['state_code']: row for row in data['rows']}
            assert len(rows) == 50 and 'DC' not in rows
            summary = root.locator('[data-driver-summary]')
            state = root.locator('[data-driver-state]')
            assert not root.locator('[data-driver-family]').is_visible()
            assert not root.locator('[data-driver-association]').is_visible()
            for unit, factor in [('democratic_two_party_share', 1), ('margin', 2)]:
                unit_control = root.locator('[data-driver-units]')
                if not unit_control.is_visible():
                    root.locator('.driver-options > summary').click()
                unit_control.select_option(unit)
                for mode, term in [('house_transition_home', 'staying_home'), ('house_transition_switching', 'switching')]:
                    view.select_option(mode)
                    expect(paths).to_have_count(51)
                    values = paths.evaluate_all('es=>Object.fromEntries(es.map(e=>[e.dataset.stateCode,e.dataset.modelValue]))')
                    for code, row in rows.items():
                        assert abs(float(values[code]) - factor * row['point']['contributions_pp'][term]) < 1e-8
                        state.select_option(code)
                        expect(summary).to_have_attribute('data-transition-state', code)
                        for key in ['switching', 'staying_home']:
                            estimate = summary.locator(f'[data-transition-term="{key}"]')
                            assert abs(float(estimate.get_attribute('data-value')) - factor * row['point']['contributions_pp'][key]) < 1e-8
                            expect(estimate.locator('small')).to_contain_text(' to ')
                        assert row['available'] is True
                    assert values['DC'] == ''
            state.select_option('DC')
            expect(summary).to_contain_text('no voting House seat')
            state.select_option('TX')
            root.locator('[data-driver-units]').select_option('democratic_two_party_share')
            view.select_option('house_transition_home')
            expect(summary).to_contain_text('percentages are not the contributions in points')
            expect(summary).to_contain_text('no counted 2026 ballot')
            root.locator('[data-driver-detail-title]').click()
            terms = root.locator('[data-driver-detail] tbody td').all_text_contents()
            assert len(terms) == 6
            assert abs(sum(float(value.replace(' pp', '')) for value in terms) - round(rows['TX']['point']['recorded_change_pp'], 2)) < 1e-8
            root.locator('[data-driver-detail-title]').click()
            target = root.locator('path[data-state-code="MO"]')
            target.scroll_into_view_if_needed()
            target.click()
            expect(state).to_have_value('MO')
            target.focus()
            target.press('Enter')
            expect(summary).to_have_attribute('data-transition-state', 'MO')
            summary.scroll_into_view_if_needed()
            if args.images and width in [390, 1280]:
                page.screenshot(path=args.images / f'house-comparison-{width}.png')
            assert page.evaluate('document.documentElement.scrollWidth') <= width + 1
            view.select_option('reported_counts')
            expect(summary).to_have_attribute('data-norc-state', 'MO', timeout=60000)
            expect(root.locator('#estimate-outcome-check')).to_be_visible()
            expect(root.locator('[data-house-transition-table]')).to_be_hidden()
            expect(root.locator('.driver-no-model')).not_to_contain_text('No voting-House model')
            view.select_option('source_total')
            expect(summary).to_have_attribute('data-source-model-state', 'MO', timeout=60000)
            view.select_option('house_transition_home')
            expect(summary).to_have_attribute('data-transition-state', 'MO', timeout=60000)
            expect(root.locator('[data-house-transition-table] tbody tr')).to_have_count(50)
            assert not errors, errors
            results.append(dict(width=width, state_selections=200, exact_map_values=200,
                                both_contributions_and_ranges=True, legacy_restoration=True,
                                automatic=root.locator('[data-driver-map]').get_attribute('data-transition-automatic'),
                                version=data['version']))
            args.output.with_suffix('.progress.json').write_text(json.dumps(results, indent=2) + '\n')
            page.close()
        page = browser.new_page(java_script_enabled=False)
        page.goto(url)
        table = page.locator('[data-house-transition-table]')
        table.locator('summary').click()
        expect(table.locator('tbody tr')).to_have_count(50)
        expect(table.locator('tbody')).to_be_visible()
        page.close()
        page = browser.new_page()
        page.route('**/house/statewide-transitions/viewer.json.gz', lambda route: route.fulfill(status=503, body='Injected optional automatic-model outage'))
        page.route('**/statewide-house-transitions/**/viewer-data.json.gz', lambda route: route.fulfill(status=503, body='Injected saved-model outage'))
        page.goto(url)
        expect(page.locator('[data-driver-map]')).to_contain_text('All-state model unavailable', timeout=60000)
        expect(page.locator('[data-driver-map] path')).to_have_count(0)
        expect(page.locator('[data-house-transition-table] tbody tr')).to_have_count(50)
        page.close()
        browser.close()
    proof = dict(status='passed', base=args.base, results=results, nojs_all_50_states=True,
                 unavailable_models_not_zero_filled=True)
    args.output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--images', type=Path)
    args = parser.parse_args()
    if args.images:
        args.images.mkdir(parents=True, exist_ok=True)
    check(args)

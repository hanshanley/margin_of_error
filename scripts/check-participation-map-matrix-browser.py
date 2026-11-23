"""Exercise published map frames and selections, including explicit coverage gaps."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright


LOCAL = '.geographic-detail path.map-feature'
BAD = ('could not be loaded', 'Source load failed', 'Data unavailable for this selection')


def inventory(page):
    return page.evaluate("""async () => {
      const read = async url => {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
        return response.json();
      };
      const [{index}, geo, pointer, nc, audits] = await Promise.all([
        (await import('/scripts/participation-native-bindings.js')).loadNativeIndex(),
        read('/voter-participation/data/states.geojson'), read('/precinct-results.json'),
        read('/voter-participation/data/nc/summary.json'), read('/voter-participation/data/geometry-audit.json')]);
      const offered = new Set([...document.querySelector('#state-select').options].map(o => o.value));
      const names = Object.fromEntries(geo.features.filter(f => offered.has(f.properties.NAME))
        .map(f => [f.properties.STUSAB, f.properties.NAME]));
      const results = new Map();
      for (const snapshot of [pointer, ...pointer.additional_snapshots || []]) {
        const data = await read(snapshot.base_url + 'index.json');
        for (const [year, states] of Object.entries(data.coverage))
          for (const [code, row] of Object.entries(states)) results.set(`${year}|${code}`,
            {year:Number(year),code,layer:'results',expected:row.colored,kind:'mapped'});
      }
      const current = Object.keys(names).map(code => {
        const entry = index.layers['matched/' + code] || index.layers['precinct/' + code];
        return {code,year:2026,layer:'participation',expected:entry?.features || 0,
          kind:entry ? 'mapped' : index.reporting_sources[code] ? 'table' : 'unavailable'};
      });
      const history = nc.filter(row => row.status === 'aggregated').map(row => ({code:'NC',
        year:row.year,layer:'participation',kind:audits.some(a => a.year === row.year) ? 'history-map' : 'history-table'}));
      return {names,precincts:[...results.values(),...current,...history],
        years:[...document.querySelector('#year').options].map(o => Number(o.value))};
    }""")


def boot(page, base, query=None):
    response = page.goto(base + '/voter-participation/' + ('?' + urlencode(query) if query else ''),
                         wait_until='domcontentloaded')
    assert response.ok
    page.wait_for_function("""() => document.querySelector('#state-select').options.length >= 51
      && document.querySelector('#year').options.length > 1""", timeout=45000)


def local_selection(page, paths):
    count = paths.count()
    if not count:
        return 0
    for index, key in ((0, 'Enter'), (count - 1, 'Space')):
        more = page.locator('#selection-panel > .selection-more')
        if more.count():
            more.evaluate('e => e.open = false')
        candidate = paths.nth(index)
        attribute = 'data-geography' if candidate.get_attribute('data-geography') else 'data-key'
        identity = candidate.get_attribute(attribute)
        assert identity
        path = paths.and_(page.locator(f'[{attribute}={json.dumps(identity)}]'))
        label = path.get_attribute('aria-label')
        path.press(key)
        expect(path).to_have_class(re.compile(r'\bselected\b'))
        if more.count():
            expect(more).to_have_attribute('open', '')
        panel = page.locator('#selection-panel')
        expect(panel).to_be_visible()
        details = panel.locator('#substate-detail, #current-county-detail, #local-detail, .selection-stats')
        assert any(detail.is_visible() and detail.inner_text().strip() for detail in details.all()), label
        settled(page)
    return 2


def settled(page):
    page.wait_for_timeout(120)  # The map intentionally debounces drill-down by 80 ms.
    page.wait_for_function("""() => !/^Loading /i.test(document.querySelector('#geography-note').textContent)
      && !/^Loading /i.test(document.querySelector('#coverage-note').textContent)""", timeout=45000)
    text = '\n'.join(page.locator(selector).text_content() for selector in
                     ('#geography-note', '#coverage-note', '#visualization'))
    assert not any(term in text for term in BAD), text[:1000]


def check(args):
    rows = []

    def run(page, errors, width, spec, action):
        errors.clear()
        try:
            detail = action() or {}
            assert not errors, errors
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), spec
            row = dict(width=width, **spec, **detail, status='passed')
        except Exception as error:
            row = dict(width=width, **spec, status='failed', error=str(error)[:2000])
        rows.append(row)
        if args.output:
            args.output.write_text(json.dumps(rows, indent=2) + '\n')
        print(json.dumps(row), flush=True)
        if args.fail_fast and row['status'] == 'failed':
            raise AssertionError(row)

    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            probe = browser.new_page()
            boot(probe, args.base)
            expected = inventory(probe)
            probe.close()
            names = expected['names']
            codes = [code for code in names if not args.states or code in args.states]
            for width in args.widths:
                context = browser.new_context(viewport={'width': width, 'height': 950},
                                              has_touch=width < 700, is_mobile=width < 700)
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                if 'counties' in args.families:
                    boot(page, args.base)
                    expect(page.locator('svg.turnout-map')).to_be_visible(timeout=45000)
                    for mode in args.modes:
                        page.locator('#atlas-options').evaluate('e => e.open = true')
                        page.locator('#map-color').select_option('turnout')
                        page.locator('#mode').select_option('available' if mode == 'margin' else mode)
                        page.locator('#map-level').select_option('county')
                        if mode == 'margin':
                            page.locator('#map-color').select_option('margin')
                        page.locator('#atlas-options').evaluate('e => e.open = false')
                        for code in codes:
                            def county(code=code):
                                page.locator('#map-reset').click()
                                page.locator(f'path.map-feature[data-state="{names[code]}"]').press('Enter')
                                settled(page)
                                expect(page.locator('#state-select')).to_have_value(names[code])
                                paths = page.locator(LOCAL)
                                note = page.locator('#geography-note').text_content()
                                assert names[code] in note or names[code] in page.locator('#title').text_content(), note
                                return {'shapes': paths.count(), 'selections': local_selection(page, paths)}
                            run(page, errors, width, {'family':'counties','code':code,'mode':mode}, county)
                if 'historical' in args.families:
                    boot(page, args.base)
                    for year in expected['years']:
                        if year == 2026:
                            continue
                        def historical(year=year):
                            page.locator('#year').select_option(str(year))
                            expect(page.locator('svg.turnout-map path[data-state]')).to_have_count(51)
                            for code in codes:
                                page.locator('#map-reset').click()
                                page.locator(f'path.map-feature[data-state="{names[code]}"]').press('Enter')
                                settled(page)
                                expect(page.locator('#state-select')).to_have_value(names[code])
                                local_selection(page, page.locator(LOCAL))
                            return {'states':len(codes)}
                        run(page, errors, width, {'family':'historical','year':year}, historical)
                if 'precincts' in args.families:
                    for spec in expected['precincts']:
                        if spec['code'] not in codes:
                            continue
                        def precinct(spec=spec):
                            boot(page, args.base, {'view':'precincts','year':spec['year'],
                                 'state':names[spec['code']],'layer':spec['layer']})
                            page.wait_for_function("""() => {
                              const summary=document.querySelector('#precinct-source-summary').textContent;
                              return !/^Loading /i.test(document.querySelector('#coverage-note').textContent)
                                && /mapped|precinct observations|reporting-unit|No qualified/.test(summary);
                            }""", timeout=45000)
                            settled(page)
                            expect(page.locator('#precinct-state-select')).to_have_value(names[spec['code']])
                            expect(page.locator('#year')).to_have_value(str(spec['year']))
                            expect(page.locator('#precinct-layer')).to_have_value(spec['layer'])
                            kind = spec['kind']
                            paths = page.locator(LOCAL).filter(visible=True)
                            paths = paths.locator('xpath=self::*[@data-level="precinct" or @data-level="ward" or @data-level="subprecinct" or @data-level="reporting_reference"]')
                            if kind in ('mapped', 'history-map'):
                                if kind == 'history-map':
                                    paths = page.locator('svg.turnout-map path[data-key]')
                                assert paths.count() > 0, spec
                                if kind == 'mapped':
                                    expect(paths).to_have_count(spec['expected'])
                                    summary = page.locator('#precinct-source-summary').text_content()
                                    assert int(summary.split()[0].replace(',', '')) == spec['expected'], summary
                                    expect(page.locator('#precinct-options option')).to_have_count(spec['expected'])
                                selected = local_selection(page, paths)
                            elif kind == 'table':
                                expect(page.locator('#source-reporting-unit-select')).to_be_visible()
                                control = page.locator('#source-reporting-unit-select')
                                last = control.locator('option').last.get_attribute('value')
                                control.select_option(last)
                                expect(page.locator('#source-reporting-unit-detail')).to_be_visible()
                                selected = 1
                            elif kind == 'history-table':
                                expect(page.locator('#visualization')).to_contain_text('No verified')
                                assert page.locator('#precinct-options option').count() > 0
                                selected = 0
                            else:
                                expect(page.locator('#show-state-county-data')).to_be_visible()
                                expect(paths).to_have_count(0)
                                page.locator('#show-state-county-data').click()
                                expect(page.locator('#state-select')).to_have_value(names[spec['code']])
                                expect(page.locator('#year')).to_have_value(str(spec['year']))
                                settled(page)
                                selected = 1
                            return {'shapes':paths.count() if kind != 'unavailable' else 0,'selections':selected}
                        run(page, errors, width, {'family':'precincts',**spec}, precinct)
                if 'results' in args.families:
                    boot(page, args.base)
                    page.locator('#tab-effects').click()
                    page.locator('.driver-options').evaluate('e => e.open = true')
                    for office in ('house', 'senate', 'governor'):
                        page.locator('[data-driver-office]').select_option(office)
                        views = page.locator('[data-driver-view] option').evaluate_all(
                            'es => es.filter(e => !e.disabled).map(e => e.value)')
                        for view in views:
                            def result_view(view=view):
                                page.locator('[data-driver-view]').select_option(view)
                                shapes = page.locator('[data-driver-map] path.driver-state')
                                expect(shapes).to_have_count(51, timeout=45000)
                                expect(page.locator('[data-driver-map]')).to_have_attribute('data-driver-map', view)
                                for code in codes:
                                    page.locator('[data-driver-state]').select_option(code)
                                    expect(page.locator('[data-driver-summary]')).to_be_visible()
                                    expect(page.locator('[data-driver-state]')).to_have_value(code)
                                return {'states':len(codes)}
                            run(page, errors, width, {'family':'results','office':office,'view':view}, result_view)
                if 'districts' in args.families:
                    boot(page, args.base)
                    page.locator('#tab-effects').click()
                    page.locator('[data-driver-geography]').select_option('district')
                    paths = page.locator('[data-driver-map] path[data-district]')
                    expect(paths).to_have_count(435, timeout=45000)
                    seats = paths.evaluate_all('es => es.map(e => ({id:e.dataset.district,code:e.dataset.stateCode}))')
                    for seat in seats:
                        if seat['code'] not in codes:
                            continue
                        def district(seat=seat):
                            path = page.locator(f'[data-driver-map] path[data-district="{seat["id"]}"]')
                            path.press('Enter')
                            expect(path).to_have_class(re.compile(r'\bselected\b'))
                            expect(page.locator('[data-driver-district]')).to_have_value(seat['id'])
                            expect(page.locator('[data-driver-summary]')).to_contain_text(seat['id'])
                            return {'qualified':path.get_attribute('data-district-qualified')}
                        run(page, errors, width, {'family':'districts','district':seat['id']}, district)
                    for code in codes:
                        def district_scope(code=code):
                            page.locator('[data-driver-state]').select_option(code)
                            expect(paths).to_have_count(sum(seat['code'] == code for seat in seats))
                            return {'seats':paths.count()}
                        run(page, errors, width, {'family':'district-filter','code':code}, district_scope)
                context.close()
        finally:
            browser.close()
    failures = [row for row in rows if row['status'] == 'failed']
    print(json.dumps({'cases':len(rows),'failures':len(failures),
                      'families':dict(Counter(row['family'] for row in rows))}), flush=True)
    assert not failures, json.dumps(failures, indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8436')
    parser.add_argument('--widths', nargs='+', type=int, default=[1280,390])
    parser.add_argument('--families', nargs='+', choices=['counties','historical','precincts','results','districts'],
                        default=['counties','historical','precincts','results','districts'])
    parser.add_argument('--modes', nargs='+', default=['available','official','in_person_early','mail_returned','margin'])
    parser.add_argument('--states', nargs='+')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--fail-fast', action='store_true')
    options = parser.parse_args()
    options.base = options.base.rstrip('/')
    check(options)

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import test from 'node:test';
import { loadMarylandCardCounts, reviewMarylandCardCounts } from './maryland-county-cards.mjs';
import { loadAdditionalParticipation } from './additional-participation.mjs';

test('joins all Maryland card references without changing the frozen frame or inventing turnout', () => {
  const rows = loadMarylandCardCounts();
  assert.equal(rows.length, 24);
  assert.equal(new Set(rows.map(row => row.county_fips)).size, 24);
  assert.equal(rows.reduce((total, row) => total + row.cards_cast, 0), 2079801);
  assert.equal(rows.find(row => row.county_fips === '24510').native_record.native_county_label, 'Baltimore City');
  assert.equal(rows.find(row => row.county_fips === '24005').native_record.native_county_label, 'Baltimore County');
  assert.equal(rows.find(row => row.county_fips === '24037').native_record.native_county_label, "Saint Mary's County");
  assert.equal(loadAdditionalParticipation().counties.filter(row => row.state_code === 'MD').length, 0);
  const live = loadAdditionalParticipation({ nativeCountyParents: true }).counties.filter(row => row.state_code === 'MD');
  assert.equal(live.length, 24);
  for (const row of live) {
    const native = rows.find(item => item.county_fips === row.county_fips);
    assert.deepEqual(row.native_record, native.native_record);
    assert.equal(row.ballots, native.cards_cast);
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    assert.equal(row.cast_ballot_count_qualified, false);
    assert.equal(row.unique_voter_count_qualified, false);
    assert.equal(row.reported_units, null);
    assert.equal(row.total_units, null);
    assert.match(row.participation_measure_label, /Cards Cast.*not unique voters/);
    assert.match(row.source_update_label, /MIB2.*11\/8\/2026 7:44 pm.*timezone not supplied/);
  }
});

test('rejects changed source clocks, ballot promotion, incomplete coverage and swapped Maryland identities', () => {
  const base = 'data/county-source-reviews/20261109-maryland-cards-01';
  const json = name => JSON.parse(readFileSync(`${base}/${name}`));
  const inputs = json('inputs.json');
  const source = { inputs, grid: json('independent-card-grid.json'), scope: json('source-scope.json'),
    crosswalk: json('county-crosswalk.json'), geometry: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))) };
  for (const mutate of [
    value => { value.inputs.cast_ballot_count_qualified = true; },
    value => { value.inputs.rates_approved = true; },
    value => { value.grid.run_date = '11/9/2026'; },
    value => { value.grid.rows[0].native_cards_cast = null; },
    value => { value.grid.rows[0].native_cards_cast = true; },
    value => { value.grid.rows[0].native_cards_cast = '0'; },
    value => { value.grid.rows.pop(); },
    value => { value.crosswalk[0].county_fips = value.crosswalk[1].county_fips; },
    value => {
      const city = value.crosswalk.find(row => row.county_fips === '24510');
      const county = value.crosswalk.find(row => row.county_fips === '24005');
      [city.county_fips, county.county_fips] = [county.county_fips, city.county_fips];
    },
    value => { value.inputs.reference.boundary_year = 2024; },
  ]) {
    const changed = structuredClone(source);
    mutate(changed);
    assert.throws(() => reviewMarylandCardCounts(changed), /Maryland/);
  }
});

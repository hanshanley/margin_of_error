import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { loadHawaiiAdministrations, reviewHawaiiAdministrations } from './hawaii-administrations.mjs';
import { qualifiedHawaiiAdministrationReference } from '../public/scripts/participation-geography.js';

const version = 'data/county-source-reviews/20261109-hawaii-administrations-01';
const fixture = () => {
  const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
  const json = name => JSON.parse(readFileSync(`${version}/${name}`, 'utf8'));
  return { inputs, grid: json('native-administration-grid.json'), scope: json('scope-facts.json'),
    geometry: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))),
    original: JSON.parse(gunzipSync(readFileSync(inputs.original_reference.path))),
    units: JSON.parse(gunzipSync(readFileSync(`${version}/native-unit-participation.json.gz`))),
    audit: json('source-audit.json') };
};
const browserRows = result => result.administrations.map(row => ({ ...row,
  county_id: `additional:HI:${row.source_administration_id}`,
  geography_level: 'election_administration', ballots: row.source_count }));

test('four native reporting areas preserve original counts and withhold two separate Census-county totals', () => {
  const result = loadHawaiiAdministrations();
  assert.deepEqual(result.administrations.map(r => [r.source_administration_id, r.source_count]),
    [['HI-HONOLULU', 228487], ['HI-HAWAII', 62453], ['HI-KAUAI', 24635], ['HI-MAUI', 50324]]);
  const maui = result.administrations.find(r => r.source_administration_id === 'HI-MAUI');
  assert.deepEqual(maui.component_county_fips, ['15009', '15005']);
  assert.equal(maui.native_record.native_values['Mail TURNOUT'], 47362);
  assert.equal(maui.native_record.native_values['In-Person TURNOUT'], 2962);
  assert.equal(result.Census_county_decisions.length, 5);
  for (const fips of ['15009', '15005'])
    assert.equal(result.Census_county_decisions.find(r => r.county_fips === fips).source_count, null);
  for (const row of result.administrations) {
    assert.equal(row.county_fips, null);
    assert.equal(row.source_count, row.native_record.native_values['TOTAL TURNOUT']);
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    assert.equal(row.cast_ballot_count_qualified, false);
    assert.equal(row.unique_voter_count_qualified, false);
  }
  assert.equal(result.diagnostics.administration_snapshot_sum_not_statewide_control, 365899);
  assert.equal(result.diagnostics.administration_sum_minus_state_summary, 2);
  assert.equal(result.diagnostics.original_units_minus_state_summary, 6);
  assert.equal(result.diagnostics.common_cutoff_qualified, false);
});

test('wrong election, count, scope or component inventories cannot become qualified administrations', () => {
  for (const change of [
    x => x.inputs.year = 2024,
    x => x.grid[0].native_values['TOTAL TURNOUT'] = 228485,
    x => x.grid[0].native_values['TOTAL TURNOUT'] = null,
    x => x.grid[3].component_county_fips = ['15009'],
    x => x.scope.membership['HI-MAUI'] = ['15005'],
    x => x.grid.push(structuredClone(x.grid[3])),
    x => x.geometry.features.find(f => f.properties.key === 'HI-MAUI').properties.component_county_fips = ['15009'],
    x => x.geometry.features[0].properties.boundary_year = 2024,
    x => x.inputs.cast_ballot_count_qualified = true,
    x => x.inputs.rates_approved = true,
    x => x.grid[0].source_timezone = 'Pacific/Honolulu',
    x => x.audit.source_summary_ballots = 365903,
    x => x.units[0].ballots++,
  ]) {
    const data = fixture();
    change(data);
    assert.throws(() => reviewHawaiiAdministrations(data));
  }
});

test('browser inventory uses source administration IDs and rejects allocated or mismatched Maui/Kalawao records', () => {
  const data = fixture(), result = reviewHawaiiAdministrations(data), rows = browserRows(result);
  assert.equal(qualifiedHawaiiAdministrationReference(rows, data.inputs.reference, data.geometry), true);
  for (const change of [
    x => x.rows[3].county_fips = '15009',
    x => x.rows[3].component_county_fips = ['15009'],
    x => x.rows[3].ballots = 50314,
    x => x.rows[0].denominator = 550792,
    x => x.rows[0].reported_pct = 41.5,
    x => x.rows.push(structuredClone(x.rows[3])),
    x => x.reference.Census_counties = 4,
    x => x.geometry.features[0].properties.key = '15003',
    x => x.geometry.features[3].properties.component_county_fips = ['15005'],
  ]) {
    const changed = structuredClone({ rows, reference: data.inputs.reference, geometry: data.geometry });
    change(changed);
    assert.equal(qualifiedHawaiiAdministrationReference(changed.rows, changed.reference, changed.geometry), false);
  }
});

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { loadNewHampshireCities } from './new-hampshire-city-counts.mjs';
import { loadNewHampshireCityExtension, reviewNewHampshireCityExtension } from './new-hampshire-city-extension.mjs';

const version = 'data/county-source-reviews/20261110-new-hampshire-cities-02';
const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
const base = loadNewHampshireCities();
const fixture = () => ({ inputs: structuredClone(inputs), base: structuredClone(base),
  nashua: JSON.parse(readFileSync(inputs.readings_paths.nashua, 'utf8')),
  dover: JSON.parse(readFileSync(inputs.readings_paths.dover, 'utf8')) });

test('four-city extension preserves every first-release field and all unknown reference areas', () => {
  const result = loadNewHampshireCityExtension();
  assert.equal(result.source_queries.length, 242);
  assert.deepEqual(result.source_queries.slice(0,107), base.source_queries);
  assert.deepEqual(result.municipalities.slice(0,2), base.municipalities);
  assert.deepEqual(result.ward_rows.slice(0,22), base.ward_rows);
  assert.equal(result.ward_rows.length, 37);
  assert.equal(result.reference_queries.length, 259);
  assert.equal(result.reference_queries.filter(row => row.source_city === null).length, 255);
  assert.deepEqual(result.municipalities.map(row => [row.city, row.source_count]),
    [['Manchester',38562],['Concord',19234],['Nashua',33849],['Dover',15941]]);
  assert.ok(result.ward_rows.every(row => row.maps_approved === false && row.reported_pct === null));
  assert.equal(result.reference_geometry.url, base.reference_geometry.url);
  assert.equal(result.reference_geometry.sha256, base.reference_geometry.sha256);
});

test('literal Nashua totals retain three source disagreements, red amendments and separate federal-only cells', () => {
  const result = reviewNewHampshireCityExtension(fixture());
  const conflicts = result.source_accounting_queries.filter(row =>
    row.city === 'Nashua' && row.component_minus_printed_total !== 0);
  assert.deepEqual(conflicts.map(row => [row.ward, row.component_minus_printed_total]), [[3,1],[4,-2],[8,-1]]);
  assert.equal(result.summary.nashua_federal_only_separate_sum, 92);
  assert.equal(result.summary.nashua_component_minus_printed_sum, -2);
  const ward8 = result.ward_rows.find(row => row.source_unit_id === 'Nashua:Ward:8');
  assert.equal(ward8.source_count, 3575);
  assert.equal(ward8.native_record.absentee, 225);
  assert.equal(ward8.native_record.cancelled_election_day_mark, '3264');
  assert.equal(ward8.native_record.cancelled_total_mark, '3489');
  assert.equal(ward8.native_record.red_source_amendment_selected_not_analyst_repair, true);
  assert.equal(result.municipalities.find(row => row.city === 'Nashua').native_city_parent_printed, false);
});

test('Dover uses the native 2026 header, complete register stocks and explicit source percentage basis', () => {
  const result = reviewNewHampshireCityExtension(fixture());
  assert.equal(result.source_queries.filter(row => row.city === 'Dover').length, 99);
  const city = result.municipalities.find(row => row.city === 'Dover');
  assert.equal(city.native_record.native_file_basename, '2025.11.03_VoterTurnout.pdf');
  assert.equal(city.source_election_date, '2026-11-03');
  assert.equal(city.native_city_parent_printed, true);
  assert.equal(city.native_record.native_register_rows.at(-1).checklist, 20972);
  assert.equal(city.native_record.native_register_rows.at(-1).new, 1484);
  const basis = result.source_printed_rate_basis_queries.filter(row => row.city === 'Dover');
  assert.equal(basis.length, 7);
  assert.ok(basis.every(row => row.matches_explicit_native_registered_basis));
  assert.equal(basis.at(-1).source_defined_registered_fraction, 15941 / 22456);
  assert.equal(basis.at(-1).native_printed, '71.0%');
  assert.ok(basis.every(row => row.analysis_rate === null && row.not_group_or_population_turnout));
});

test('missing native values and wrong election/scope are rejected, but genuine zero is retained', () => {
  const zero = fixture();
  Object.assign(zero.nashua.wards[0], { election_day: 0, absentee: 0, total: 0, federal_only: 0 });
  assert.equal(reviewNewHampshireCityExtension(zero).ward_rows.find(row =>
    row.source_unit_id === 'Nashua:Ward:1').source_count, 0);
  for (const change of [
    input => { input.nashua.wards[0].total = null; },
    input => { input.nashua.wards.pop(); },
    input => { input.dover.native_election_label = 'NOVEMBER 3, 2025 GENERAL ELECTION'; },
    input => { input.dover.native_ballot_rows[0].registered = null; },
    input => { input.dover.native_new_voter_definition = 'First-ever eligible voters'; },
    input => { input.inputs.reference.boundary_year = 2026; },
    input => { input.base.reference_queries.find(row => row.municipality === 'Nashua').contextual_municipality_key = '3318820'; },
  ]) {
    const changed = fixture();
    change(changed);
    assert.throws(() => reviewNewHampshireCityExtension(changed));
  }
});

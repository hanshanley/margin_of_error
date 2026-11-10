import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { loadNewHampshireCities, reviewNewHampshireCities } from './new-hampshire-city-counts.mjs';

const version = 'data/county-source-reviews/20261110-new-hampshire-cities-01';
const fixture = () => {
  const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
  return { inputs, readings: JSON.parse(readFileSync(inputs.readings_path, 'utf8')),
    reference: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))) };
};

test('all107 native queries retain22 wards, two city measures and all259 reference decisions', () => {
  const data = loadNewHampshireCities();
  assert.equal(data.source_queries.length, 107);
  assert.equal(data.ward_rows.length, 22);
  assert.equal(data.reference_queries.length, 259);
  assert.equal(data.reference_queries.filter(r => r.source_city !== null).length, 2);
  assert.equal(data.municipalities.find(r => r.city === 'Manchester').source_count, 38562);
  assert.equal(data.municipalities.find(r => r.city === 'Concord').source_count, 19234);
  assert.ok(data.municipalities.every(r => r.denominator === null && r.reported_pct === null));
  assert.ok(data.ward_rows.every(r => r.maps_approved === false && r.reported_pct === null));
});

test('Ward7 source discrepancy stays85 and separately revised federal-only counts are never added', () => {
  const data = loadNewHampshireCities();
  const ward = data.source_accounting_queries.find(r => r.ward === 7);
  assert.equal(ward.printed_total, 2712);
  assert.equal(ward.component_sum, 2797);
  assert.equal(ward.component_minus_printed_total, 85);
  assert.equal(data.summary.federal_only_separate_sum, 76);
  assert.equal(data.summary.federal_only_added, false);
  const revised = data.ward_rows.find(r => r.city === 'Manchester' && r.native_ward === 4);
  assert.equal(revised.native_record.federal_only, 2);
  assert.equal(revised.native_record.federal_only_native_cancelled_mark, '8 struck through; 2 written beside it');
  assert.ok(data.municipalities.find(r => r.city === 'Manchester').quality_flags.length);
});

test('Concord school splits and printed ward/city parents are not double-counted or mixed with registers', () => {
  const data = loadNewHampshireCities();
  const wards = data.ward_rows.filter(r => r.city === 'Concord');
  assert.equal(wards.length, 10);
  assert.equal(wards.reduce((s, r) => s + r.source_count, 0), 19234);
  assert.equal(wards[0].native_record.total_cast_columns.length, 2);
  assert.equal(wards[0].native_record.printed_ward_subtotal, 1985);
  const city = data.municipalities.find(r => r.city === 'Concord').native_record;
  assert.equal(city.native_totals.opening, 25879);
  assert.equal(city.native_totals.closing, 27340);
  assert.equal(city.native_totals.election_day_registrations, 1461);
  assert.equal(city.native_totals.printed_turnout, '74.32%');
  assert.equal(city.analysis_denominator, null);
  assert.equal(data.source_printed_rate_basis_queries.length, 11);
  assert.ok(data.source_printed_rate_basis_queries.every(r => r.matches_opening_stock_arithmetic
    && !r.matches_closing_stock_arithmetic && r.analysis_rate === null && r.analysis_denominator === null));
});

test('literal native zero survives; missing fields, wrong wards/elections, false geometry and pooled additions reject', () => {
  const f = fixture();
  f.readings.manchester.wards[0].total = 0;
  const zero = reviewNewHampshireCities(f).ward_rows.find(r => r.city === 'Manchester' && r.native_ward === 1);
  assert.equal(zero.source_count, 0);
  assert.equal(zero.reported_pct, null);
  assert.ok(zero.quality_flags.length);
  for (const change of [
    x => x.readings.manchester.wards[0].total = null,
    x => x.readings.manchester.wards[0].ward = 2,
    x => x.readings.manchester.federal_only_added_to_total = true,
    x => x.readings.election_date = '2024-11-05',
    x => x.inputs.reference.boundary_year = 2026,
    x => x.inputs.certified_election_boundaries = true,
    x => x.readings.concord.total_cast_columns[0].school_district = null,
    x => x.readings.concord.separate_printed_ward_subtotals[0].count++,
    x => x.reference.features[0].properties.key = x.reference.features[1].properties.key,
    x => x.reference.features.find(f => f.properties.name !== 'Concord').properties.name = 'Concord',
  ]) {
    const changed = fixture();
    change(changed);
    assert.throws(() => reviewNewHampshireCities(changed));
  }
});

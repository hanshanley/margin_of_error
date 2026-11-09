import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { loadColoradoCountyReturns, reviewColoradoCountyReturns } from './colorado-returned-counties.mjs';

const version = 'data/county-source-reviews/20261109-colorado-returned-01';
const fixture = () => {
  const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
  return { inputs, sheets: JSON.parse(gunzipSync(readFileSync(`${version}/workbook-cells.json.gz`))),
    geometry: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))) };
};

test('all64 native returned county parents retain their three distinct source frames and no rates', () => {
  const result = loadColoradoCountyReturns();
  assert.equal(result.counties.length, 64);
  assert.equal(result.counties.reduce((sum, r) => sum + r.source_count, 0), 2761449);
  const adams = result.counties.find(r => r.county_fips === '08001');
  assert.equal(adams.source_count, 205277);
  assert.equal(adams.native_record.Returned_Mail_Ballots_By_County.native_record['Grand Total'], 194044);
  assert.equal(adams.native_record.In_Person_Ballots_By_County.native_record['Grand Total'], 11233);
  assert.equal(result.original_state_mode_parents.Returned_Mail_Ballots_By_County['Grand Total'], 2618985);
  assert.equal(result.original_state_mode_parents.In_Person_Ballots_By_County['Grand Total'], 142464);
  for (const row of result.counties) {
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    assert.equal(row.cast_ballot_count_qualified, false);
    assert.equal(row.unique_voter_count_qualified, false);
    assert.match(row.participation_measure_label, /Returned and processed/);
    assert.equal(row.reference_geometry.boundary_year, 2026);
  }
});

test('missing county cells, changed source parents and wrong mode labels cannot become zero or replacements', () => {
  const mutate = change => { const data = fixture(); change(data); assert.throws(() => reviewColoradoCountyReturns(data)); };
  mutate(x => x.sheets.find(s => s.name === 'All_Returned_Ballots_By_County')
    .native_cells.find(c => c.address === 'M3').value = null);
  mutate(x => x.sheets.find(s => s.name === 'All_Returned_Ballots_By_County')
    .native_cells.find(c => c.address === 'A3').value = 'Unknown county');
  mutate(x => x.sheets.find(s => s.name === 'All_Returned_Ballots_By_County')
    .native_cells.find(c => c.address === 'M67').value++);
  mutate(x => x.sheets.find(s => s.name === 'In_Person_Ballots_By_County')
    .native_cells.find(c => c.address === 'A1').value = 'EARLY IN PERSON');
});

test('source clocks, county identities and count-only qualifications are required', () => {
  for (const change of [
    x => x.inputs.year = 2024,
    x => x.inputs.cast_ballot_count_qualified = true,
    x => x.inputs.rates_approved = true,
    x => x.inputs.source_timezone = 'America/Denver',
    x => x.geometry.features[0].properties.key = x.geometry.features[1].properties.key,
    x => x.geometry.features[0].properties.boundary_year = 2024,
  ]) {
    const data = fixture();
    change(data);
    assert.throws(() => reviewColoradoCountyReturns(data));
  }
});

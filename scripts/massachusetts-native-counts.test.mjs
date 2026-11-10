import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { gunzipSync } from 'node:zlib';
import { loadMassachusettsNativeCounts, reviewMassachusettsNativeCounts,
  massachusettsVersion } from './massachusetts-native-counts.mjs';

const root = `data/county-source-reviews/${massachusettsVersion}`;
const read = path => JSON.parse(readFileSync(`${root}/${path}`, 'utf8'));
const inputs = read('inputs.json');
const fixture = {
  inputs,
  counts: read(inputs.queries.counts),
  reference: { decisions: read(inputs.queries.reporting_reference).decisions },
  extension: { all_reference_decisions: JSON.parse(gunzipSync(
    readFileSync(`${root}/${inputs.queries.reference_extension}`))).all_reference_decisions },
  receipts: { boston: read('declared-results-01/boston-2026-Unofficial-Statement-Of-Votes-Cast.pdf.receipt.json'),
    somerville: read('declared-results-01/somerville-election-results-preliminary-20261103.pdf.receipt.json') },
};

test('MA preserves printed conflicts, real zeros and lettered subprecincts without rate inference', () => {
  const result = loadMassachusettsNativeCounts();
  const [boston, somerville] = result.cities;
  assert.equal(boston.count, 185569);
  assert.equal(boston.native_record.native_summary_voters_cast, 556369);
  assert.equal(boston.native_record.native_summary_registered, 0);
  assert.equal(boston.native_record.native_summary_pct, 'N/A');
  assert.equal(somerville.count, 64597);
  assert.equal(somerville.native_record.native_registered_voters, 56008);
  assert.equal(result.reporting_rows.find(row => row.source_unit_id === 'Boston:Ward:1:Precinct:15').source_count, 0);
  assert.deepEqual(result.reporting_rows.filter(row => row.precinct.endsWith('A'))
    .map(row => row.source_unit_id),
  ['Somerville:Ward:1:Precinct:4A', 'Somerville:Ward:2:Precinct:1A',
    'Somerville:Ward:4:Precinct:2A', 'Somerville:Ward:6:Precinct:3A']);
  assert.equal(result.reporting_references.filter(row => row.qualified).length, 303);
  assert.equal(result.reporting_references.filter(row => !row.qualified).length, 4);
});

test('MA rejects substitution of summary values, candidate sums or inferred rates', () => {
  for (const change of [
    copy => { copy.counts.boston_all_times_cast_frames['SENATOR IN CONGRESS (Vote for 1)'][0].times_cast_literal = 2405; },
    copy => { copy.counts.boston_summary[0].registered_voters_literal = null; },
    copy => { copy.counts.candidate_votes_summed = true; },
    copy => { copy.inputs.analysis_rates_approved = true; },
    copy => { copy.counts.central_tabulation_added_to_combined = true; },
  ]) {
    const copy = structuredClone(fixture);
    change(copy);
    assert.throws(() => reviewMassachusettsNativeCounts(copy));
  }
});

test('MA does not repair Somerville status/count disagreements or collapse split units', () => {
  for (const change of [
    copy => { copy.counts.somerville_native_counts.find(row => row.native_level === 'city').ballots_cast_literal = 32266; },
    copy => { copy.counts.somerville_native_counts[0].source_document_literal_status = 'Official'; },
    copy => { copy.counts.somerville_native_counts.find(row => row.precinct === '4A').precinct = '4'; },
  ]) {
    const copy = structuredClone(fixture);
    change(copy);
    assert.throws(() => reviewMassachusettsNativeCounts(copy));
  }
});

test('MA never promotes parent remainder joins or repairs the invalid Wayland reference', () => {
  for (const change of [
    copy => { copy.extension.all_reference_decisions.find(row => row.source === 'somerville-parent-precincts'
      && row.ward === '1' && row.precinct === '4').source_count_join_qualified = true; },
    copy => { copy.extension.all_reference_decisions.find(row => row.native_properties.TOWN === 'WAYLAND')
      .geometry_qualified = true; },
  ]) {
    const copy = structuredClone(fixture);
    change(copy);
    assert.throws(() => reviewMassachusettsNativeCounts(copy));
  }
});

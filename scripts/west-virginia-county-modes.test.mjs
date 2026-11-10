import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import test from 'node:test';
import { loadWestVirginiaCountyModes, reviewWestVirginiaModes } from './west-virginia-county-modes.mjs';
import { hasCountySourceMode, selectCountySourceFrame } from '../public/scripts/participation-geography.js';

const VERSION = 'data/county-source-reviews/20261109-west-virginia-modes-01';
const json = name => JSON.parse(readFileSync(`${VERSION}/${name}`));
const inputs = json('inputs.json');
const fixture = {
  modes: JSON.parse(gunzipSync(readFileSync(`${VERSION}/native-mode-queries.json.gz`))),
  parents: json('native-county-parents.json'), definitions: json('publisher-definitions.json'),
  geometry: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))), reference: inputs.reference,
};

test('preserves all 55 WV all-method queries, only three native parents and no invented statewide sum', () => {
  const data = loadWestVirginiaCountyModes();
  assert.equal(data.counties.length, 55);
  assert.equal(data.counties.filter(row => row.source_count !== null).length, 3);
  const values = { '54039': 48729, '54061': 28614, '54107': 22935 };
  for (const row of data.counties) {
    assert.equal(row.source_count, values[row.county_fips] ?? null);
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    assert.equal(row.unique_voter_count_qualified, false);
    if (!values[row.county_fips]) assert.equal(row.native_record, null);
  }
  assert.equal(data.statewide_full_election_count, undefined);
  assert.match(data.counties.find(row => row.county_fips === '54061').source_reporting_label, /0 complete and 43 partially/);
});

test('keeps three full 55-county modes and all seven native party categories separate', () => {
  const before = structuredClone(fixture);
  const data = reviewWestVirginiaModes(fixture);
  assert.deepEqual(fixture, before);
  assert.equal(data.county_frames.in_person_early.length, 55);
  assert.equal(data.county_frames.mail_returned.length, 55);
  assert.equal(data.absentee_requests.length, 55);
  for (const [mode, total, rows] of [
    ['in_person_early', 162349, data.county_frames.in_person_early],
    ['mail_returned', 7001, data.county_frames.mail_returned],
    ['absentee_requested', 9735, data.absentee_requests],
  ]) {
    assert.equal(rows.reduce((sum, row) => sum + row.source_count, 0), total);
    assert.equal(data.original_state_mode_parents[mode].native_record['TOTAL VOTERS'], total);
    for (const row of rows) {
      assert.equal(row.source_count, row.native_record['TOTAL VOTERS']);
      assert.equal(Object.keys(row.native_party_counts).length, 7);
      assert.equal(Object.values(row.native_party_counts).reduce((sum, value) => sum + value, 0), row.source_count);
      assert.equal(row.denominator, null);
      assert.equal(row.reported_pct, null);
      assert.equal(row.cast_ballot_count_qualified, false);
      assert.match(row.source_reporting_label, /not candidate choices/);
    }
  }
  assert.match(data.county_frames.mail_returned[0].participation_measure_label, /not qualified cast ballots/);
  assert.equal(data.summary.no_additive_cast_total, true);
  assert.equal(data.combined_cast_ballots, undefined);
});

test('preserves real zero party cells and the empty second original worksheet without filling missing values', () => {
  const source = fixture.modes.mail_returned.counties.find(row => row.county_fips === '54013');
  assert.equal(source.source_count, 1);
  assert.equal(source.native_record['REPUBLICAN PARTY'], 0);
  assert.equal(source.native_record['TOTAL VOTERS'], 1);
  const empty = fixture.modes.in_person_early.original_worksheets[1];
  assert.equal(empty.name, 'Sheet2');
  assert.ok(empty.native_cells.every(cell => cell.value === null));
  const broken = structuredClone(fixture);
  broken.modes.mail_returned.counties[0].native_record['CONSTITUTION PARTY'] = null;
  assert.throws(() => reviewWestVirginiaModes(broken), /WV/);
});

test('rejects wrong county/election, missing modes, unsafe counts, party conflicts and incompatible references', () => {
  for (const mutate of [
    value => { value.modes.in_person_early.counties.pop(); },
    value => { value.modes.in_person_early.counties[0].source_count++; },
    value => { value.modes.mail_returned.counties[0].mode = 'in_person_early'; },
    value => { value.modes.mail_returned.counties[0].native_party_counts['OTHER PARTY']++; },
    value => { value.parents[0].native_record.election_date = '2024-11-05'; },
    value => { value.parents[0].source_count++; },
    value => { value.definitions.combined_figure_qualified_as_cast = true; },
    value => { value.definitions.source_period_end = '2026-11-03'; },
    value => { value.reference.boundary_year = 2024; },
    value => { value.geometry.features.pop(); },
  ]) {
    const changed = structuredClone(fixture);
    mutate(changed);
    assert.throws(() => reviewWestVirginiaModes(changed), /WV/);
  }
});

test('selects only the requested browser county mode and rejects missing or relabelled data instead of all-method fallback', () => {
  const source = loadWestVirginiaCountyModes();
  const imported = row => ({ ...row, ballots: row.source_count, source_mode: row.mode,
    county_id: `additional:WV:${row.county_fips}` });
  const data = { counties: source.counties, county_frames: Object.fromEntries(
    Object.entries(source.county_frames).map(([mode, rows]) => [mode, rows.map(imported)])) };
  assert.equal(selectCountySourceFrame(data, 'WV', 'official'), data.counties);
  assert.equal(selectCountySourceFrame(data, 'WV', 'in_person_early'), data.county_frames.in_person_early);
  assert.equal(selectCountySourceFrame(data, 'WV', 'mail_returned'), data.county_frames.mail_returned);
  assert.equal(hasCountySourceMode('AK', 'in_person_early'), false);
  assert.equal(hasCountySourceMode('WV', 'absentee_requested'), false);
  for (const mutate of [
    value => { delete value.county_frames; },
    value => { value.county_frames.mail_returned.pop(); },
    value => { value.county_frames.mail_returned[0].source_mode = 'in_person_early'; },
    value => { value.county_frames.mail_returned[0].cast_ballot_count_qualified = true; },
    value => { value.county_frames.mail_returned[0].ballots++; },
    value => { value.county_frames.mail_returned[0].reported_pct = 1; },
  ]) {
    const changed = structuredClone(data);
    mutate(changed);
    assert.throws(() => selectCountySourceFrame(changed, 'WV', 'mail_returned'), /WV county source mode/);
  }
});

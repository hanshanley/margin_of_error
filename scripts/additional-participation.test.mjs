import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { parse } from 'csv-parse/sync';
import test from 'node:test';
import { loadAdditionalParticipation, participationCount } from './additional-participation.mjs';

const data = loadAdditionalParticipation();
const csv = path => parse(readFileSync(path, 'utf8'), { columns: true, skip_empty_lines: true });

test('exposes whole native county and locality counts instead of candidate results', () => {
  const expected = { AL: [67, 1693621], AZ: [15, 2248900], AR: [75, 893026],
    VA: [133, 3593781], IA: [1, 107457], KY: [1, 31918], VT: [247, 311009], RI: [39, 363326] };
  for (const [code, [count, ballots]] of Object.entries(expected)) {
    const rows = data.counties.filter(row => row.state_code === code);
    assert.equal(rows.length, count);
    assert.equal(rows.reduce((sum, row) => sum + row.ballots, 0), ballots);
    assert.ok(rows.every(row => row.maps_approved === false));
  }
  for (const code of ['AL', 'AZ']) {
    const native = csv(`data/precinct-source-reviews/20261105/${code}-2026-native-counts/county-participation.csv`);
    for (const row of data.counties.filter(row => row.state_code === code)) {
      const source = native.find(source => source.county === row.county);
      assert.equal(row.ballots, Number(source.ballots));
      assert.equal(row.denominator, Number(source.registered_voters));
      assert.deepEqual(row.native_record, source);
      assert.equal(row.reported_pct, null);
    }
  }
});

test('preserves actual county totals separately from missing or incomplete precinct totals', () => {
  const directory = 'data/precinct-source-reviews/20261105/AR-2026-native-counts';
  const source = JSON.parse(gunzipSync(readFileSync(
    resolve(directory, 'native-source/originals/official-full-election-json.gz'))));
  for (const row of data.counties.filter(row => row.state_code === 'AR')) {
    const native = source.TurnoutData.Locations[row.native_record.LocationID];
    assert.equal(row.ballots, native.TotalBallotsCast);
    assert.equal(row.denominator, native.RegisteredVoters ?? null);
    assert.equal(row.reported_pct, null);
  }
  const va = JSON.parse(readFileSync(
    'data/precinct-source-reviews/20261105/VA-2026-native-locality-counts/counts-review.json', 'utf8'));
  for (const row of data.counties.filter(row => row.state_code === 'VA')) {
    assert.equal(row.ballots, va.locality_versions.find(native =>
      native.locality_code === row.native_record.locality_code).ballots_cast);
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
  }
  assert.notEqual(va.native_locality_ballots, va.native_precinct_turnout);
  const daviess = data.counties.find(row => row.state_code === 'KY');
  assert.equal(daviess.ballots, 31918);
  assert.equal(daviess.denominator, null);
  assert.equal(daviess.reported_pct, null);
});

test('retains individual source rows without inventing county totals or merging special units', () => {
  for (const [code, countyCount, unitCount] of [['MN', 87, 4105], ['ND', 53, 358], ['ID', 44, 986], ['MI', 2, 63]]) {
    const rows = data.counties.filter(row => row.state_code === code);
    assert.equal(rows.length, countyCount);
    assert.ok(rows.every(row => row.ballots === null && row.denominator === null && row.reported_pct === null));
    assert.ok(rows.every(row => row.native_record === null && row.quality.length === 2));
    const units = data.precincts.filter(row => row.state_code === code);
    assert.equal(units.length, unitCount);
    assert.equal(new Set(units.map(row => `${row.county_id}|${row.unit_key}`)).size, unitCount);
    assert.equal(rows.reduce((sum, row) => sum + row.source_rows, 0), unitCount);
  }
  const nd = data.precincts.filter(row => row.state_code === 'ND');
  assert.ok(nd.every(row => row.denominator === null && row.reported_pct === null));
  assert.ok(nd.every(row => row.denominator_basis === 'electorate_not_supplied'));
  const pooled = data.precincts.filter(row => row.native_record.quality_flags?.includes('pooled_nongeographic_reporting_unit'));
  assert.equal(pooled.length, 8);
  assert.ok(pooled.every(row => row.unit_kind === row.native_record.reporting_unit_kind
    && row.unit_kind === 'pooled_absentee_or_early_unit' && row.maps_approved === false));
});

test('keeps withheld municipal rates and nongeographic federal ballots out of geographic totals', () => {
  const vt = data.counties.filter(row => row.state_code === 'VT');
  assert.equal(vt.filter(row => row.reported_pct === null).length, 6);
  assert.ok(vt.every(row => row.geography_level === 'municipality'));
  assert.ok(data.counties.every(row => row.county !== 'Federal'));
  assert.equal(data.nongeographic.length, 1);
  assert.equal(data.nongeographic[0].ballots, 756);
  assert.equal(data.nongeographic[0].geography_level, 'nongeographic_reporting_unit');
});

test('never converts missing counts to zero or accepts malformed native counts', () => {
  for (const value of ['', undefined, null]) assert.equal(participationCount(value), null);
  assert.equal(participationCount('0'), 0);
  for (const value of [-1, '1.5', '12 people', NaN, Number.MAX_SAFE_INTEGER + 1])
    assert.throws(() => participationCount(value), /Invalid native participation count/);
});

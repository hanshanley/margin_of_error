import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { parse } from 'csv-parse/sync';
import test from 'node:test';
import { loadAdditionalParticipation, participationCount } from './additional-participation.mjs';
import { loadNativeCountyParents, reviewCountyParents } from './native-county-parents.mjs';
import { loadMichiganCountyParents, reviewMichiganCountyParents } from './michigan-county-parents.mjs';

const data = loadAdditionalParticipation({ nativeCountyParents: true });
const csv = path => parse(readFileSync(path, 'utf8'), { columns: true, skip_empty_lines: true });

test('Hawaii live-only administrations do not fabricate separate Maui/Kalawao counts or modify frozen source units', () => {
  const legacy = loadAdditionalParticipation();
  const rows = data.counties.filter(row => row.state_code === 'HI');
  assert.equal(legacy.counties.filter(row => row.state_code === 'HI').length, 0);
  assert.equal(rows.length, 4);
  assert.deepEqual(rows.flatMap(r => r.component_county_fips).sort(),
    ['15001', '15003', '15005', '15007', '15009']);
  for (const row of rows) {
    assert.equal(row.county_fips, null);
    assert.equal(row.ballots, row.native_record.native_values['TOTAL TURNOUT']);
    assert.equal(row.geography_level, 'election_administration');
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
  }
  assert.deepEqual(data.precincts.filter(r => r.state_code === 'HI'), legacy.precincts.filter(r => r.state_code === 'HI'));
  assert.deepEqual(data.nongeographic.filter(r => r.state_code === 'HI'), legacy.nongeographic.filter(r => r.state_code === 'HI'));
});

test('live Colorado counties use all64 native returned totals without changing the frozen source frame', () => {
  const rows = data.counties.filter(row => row.state_code === 'CO');
  assert.equal(rows.length, 64);
  assert.equal(loadAdditionalParticipation().counties.filter(row => row.state_code === 'CO').length, 0);
  const native = csv('data/county-source-reviews/20261109-colorado-returned-01/native-county-query.csv');
  for (const original of native) {
    const row = rows.find(row =>
      row.native_record.All_Returned_Ballots_By_County.county === original.native_county);
    assert.equal(row.ballots, Number(original.returned_ballots));
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    assert.equal(row.cast_ballot_count_qualified, false);
    assert.equal(row.unique_voter_count_qualified, false);
    assert.equal(row.reference_geometry.boundary_year, 2026);
    assert.match(row.source_update_label, /November 5, 2026/);
    assert.match(row.participation_measure_label, /Returned and processed/);
  }
});

test('connects explicit Michigan county parents only in the live frame without changing any native unit', () => {
  const legacy = loadAdditionalParticipation();
  const rows = data.counties.filter(row => row.state_code === 'MI');
  assert.equal(rows.length, 2);
  assert.ok(legacy.counties.filter(row => row.state_code === 'MI').every(row => row.ballots === null));
  assert.deepEqual(data.precincts.filter(row => row.state_code === 'MI'),
    legacy.precincts.filter(row => row.state_code === 'MI'));
  assert.equal(data.precincts.filter(row => row.state_code === 'MI').length, 63);
  for (const [county, fips, ballots, sourceRows] of [
    ['Bay County', '26017', 50246, 35], ['Isabella County', '26073', 26288, 28]]) {
    const row = rows.find(row => row.county === county);
    assert.equal(row.county_fips, fips);
    assert.equal(row.ballots, ballots);
    assert.equal(row.source_rows, sourceRows);
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    assert.equal(row.maps_approved, true);
    assert.equal(row.reference_geometry.counties, 83);
    assert.equal(row.reference_geometry.boundary_year, 2026);
    assert.deepEqual(row.reference_geometry.partial_county_fips, ['26017', '26073']);
  }
  const bay = rows.find(row => row.county === 'Bay County');
  assert.equal(bay.reported_units, 43);
  assert.equal(bay.native_record.native_registered_voters_columns[0], 87721);
  assert.match(bay.source_update_label, /11\/04\/2026 12:26AM/);
  const isabella = rows.find(row => row.county === 'Isabella County');
  assert.equal(isabella.native_record.election.ballotsCast, 26288);
  assert.equal(isabella.native_record.election.totalVoters, 44217);
  assert.match(isabella.source_reporting_label, /26266 is not substituted/);
  assert.equal(loadNativeCountyParents().length, 97);
  assert.equal(loadMichiganCountyParents().length, 2);
});

test('Michigan county-parent qualification rejects changed totals, unit scopes and reference vintages', () => {
  const inputs = JSON.parse(readFileSync('data/county-source-reviews/20261109-michigan-native-parents-01/inputs.json'));
  const source = {
    bay: JSON.parse(readFileSync(inputs.bay_parent)),
    isabella: JSON.parse(gunzipSync(readFileSync(inputs.isabella_parent))),
    units: JSON.parse(gunzipSync(readFileSync(inputs.units))),
    geometry: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))),
    reference: inputs.reference, snapshot: {},
  };
  for (const mutate of [
    value => { value.bay.native_ballots_cast_columns[0] += 1; },
    value => { value.bay.native_ballots_cast_columns[0] = true; },
    value => { value.isabella.election.ballotsCast = 26266; },
    value => { value.units.pop(); },
    value => { value.units.find(row => row.precinct === 'City of Clare, Precinct 1').ballots_cast_total = '0'; },
    value => { value.reference.boundary_year = 2024; },
    value => { value.reference.partial_county_fips.pop(); },
    value => { value.geometry.features.pop(); },
  ]) {
    const changed = structuredClone(source);
    mutate(changed);
    assert.throws(() => reviewMichiganCountyParents(changed), /Michigan|Bay|Isabella/);
  }
});

test('complete counts-only CSV inputs preserve every native row and missing total without enabling rates', () => {
  const directory = 'public/participation-reporting-units/20261109-02';
  const manifest = JSON.parse(readFileSync(`${directory}/manifest.json`));
  const index = JSON.parse(readFileSync('public/participation-reporting-units.json'));
  for (const [code, count, missing] of [['AZ', 1763, 1], ['AR', 2768, 82], ['WY', 432, 0]]) {
    const raw = readFileSync(`${directory}/${code}.json.gz`);
    const rows = JSON.parse(gunzipSync(raw));
    const native = csv(manifest[code].source_file);
    assert.equal(rows.length, count);
    assert.equal(new Set(rows.map(row => row.key)).size, count);
    assert.equal(createHash('sha256').update(raw).digest('hex'), manifest[code].output_sha256);
    assert.equal(index.sources[code].sha256, manifest[code].output_sha256);
    assert.equal(index.sources[code].rows, count);
    assert.equal(index.sources[code].data_url, `/${directory.replace('public/', '')}/${code}.json.gz`);
    assert.equal(rows.filter(row => row.ballots === null).length, missing);
    for (const [i, row] of rows.entries()) {
      assert.deepEqual(row.native_record, native[i]);
      assert.equal(row.ballots, native[i].ballots === '' ? null : Number(native[i].ballots));
      assert.equal(row.registered, native[i].registered_voters === '' ? null : Number(native[i].registered_voters));
      assert.equal(row.reported_pct, null);
      assert.equal(row.source_csv_row, i + 2);
      assert.equal(row.year, 2026);
      assert.equal(row.state_code, code);
    }
  }
});

test('exposes complete Alaska and Hawaii source-unit counts without enabling geometry or rates', () => {
  const index = JSON.parse(readFileSync('public/participation-reporting-units.json'));
  assert.equal(index.year, 2026);
  for (const [code, count, ballots] of [['AK', 523, 215906], ['HI', 496, 365903]]) {
    const source = index.sources[code];
    const directory = `data/precinct-source-reviews/20261105/${code}`;
    const raw = readFileSync(`${directory}/participation.json.gz`);
    const rows = JSON.parse(gunzipSync(raw));
    const audit = JSON.parse(readFileSync(`${directory}/audit.json`));
    assert.equal(source.rows, count);
    assert.equal(rows.length, count);
    assert.equal(new Set(rows.map(row => row.key)).size, count);
    assert.equal(createHash('sha256').update(raw).digest('hex'), source.sha256);
    assert.equal(rows.reduce((sum, row) => sum + row.ballots, 0), ballots);
    assert.ok(rows.every(row => row.year === 2026 && row.state_code === code && row.reported_pct === null));
    assert.equal(source.complete_download_url, audit.complete_download_url);
    assert.match(source.geometry_note, /No (approved|verified)/);
    assert.match(source.data_url, /\/[0-9a-f]{40}\//);
    if (code === 'AK') {
      assert.equal(rows.filter(row => row.reporting_unit_kind === 'geographic_precinct').length, 402);
      assert.equal(rows.filter(row => row.reporting_unit_kind === 'federal_overseas').length, 1);
    } else {
      const vsc = rows.filter(row => row.reporting_unit_kind === 'native_vsc_split');
      assert.equal(vsc.length, 247);
      assert.ok(vsc.every(row => row.registered === 0 && row.source_reporting === 0));
      assert.ok(vsc.some(row => row.ballots > 0));
    }
  }
});

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

test('connects reviewed Florida, Missouri and Wyoming ballots without substituting candidate totals or rates', () => {
  for (const [code, suffix, ballots, registered] of [
    ['FL', 'FL-2026-MON', 32506, 54704],
    ['MO', 'MO-2026-CHRISTIAN', 35258, 70148],
  ]) {
    const audit = JSON.parse(readFileSync(`data/precinct-source-reviews/20261105/${suffix}/audit.json`));
    const rows = data.counties.filter(row => row.state_code === code);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].ballots, ballots);
    assert.equal(rows[0].ballots, audit.county_ballots);
    assert.equal(rows[0].denominator, registered);
    assert.equal(rows[0].denominator, audit.county_registered);
    assert.notEqual(rows[0].ballots, audit.candidate_totals.contest_votes);
    assert.equal(rows[0].reported_pct, null);
    assert.equal(rows[0].maps_approved, false);
  }
  const florida = data.counties.find(row => row.state_code === 'FL');
  const flNative = JSON.parse(gunzipSync(readFileSync(
    'data/precinct-source-reviews/20261105/FL-2026-MON/participation.json.gz')))[0];
  assert.deepEqual(florida.native_record, flNative);
  assert.equal(florida.native_printed_pct, flNative.source_reported_percent);
  const missouri = data.counties.find(row => row.state_code === 'MO');
  assert.equal(missouri.native_printed_pct, '50.26%');
  assert.match(missouri.source_reporting_label, /centralized absentee/i);
  const native = JSON.parse(readFileSync(
    'data/precinct-source-reviews/20261105/WY-2026-native-counts/counts-review.json'));
  const wyoming = data.counties.filter(row => row.state_code === 'WY');
  assert.deepEqual(wyoming.map(row => row.native_record), native.counties);
  assert.equal(wyoming.reduce((sum, row) => sum + row.ballots, 0), native.statewide_ballots);
  assert.equal(native.statewide_ballots, 191688);
  assert.ok(wyoming.every(row => row.denominator === null && row.reported_pct === null
    && row.denominator_basis === 'electorate_not_supplied' && row.maps_approved === false));
});

test('retains legacy county containers and individual source rows without merging special units', () => {
  const legacy = loadAdditionalParticipation();
  for (const [code, countyCount, unitCount] of [['MN', 87, 4105], ['MI', 2, 63]]) {
    const rows = legacy.counties.filter(row => row.state_code === code);
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

test('connects all Idaho and North Dakota native county parents without substituting House votes', () => {
  const legacy = loadAdditionalParticipation();
  assert.ok(legacy.counties.filter(row => ['ID', 'ND'].includes(row.state_code))
    .every(row => row.ballots === null && row.denominator === null && row.reported_pct === null
      && row.maps_approved === false && row.native_record === null));
  assert.deepEqual(legacy.precincts, data.precincts.filter(row => row.state_code !== 'IN'));
  const parents = loadNativeCountyParents();
  const published = JSON.parse(gunzipSync(readFileSync(
    'data/county-source-reviews/20261109-native-county-parents-01/queries.json.gz')));
  assert.deepEqual(parents, published);
  for (const [code, count, ballots, units, rates] of [
    ['ID', 44, 731980, 986, 43], ['ND', 53, 239057, 358, 0],
  ]) {
    const rows = data.counties.filter(row => row.state_code === code);
    assert.equal(rows.length, count);
    assert.equal(rows.reduce((sum, row) => sum + row.ballots, 0), ballots);
    assert.equal(rows.reduce((sum, row) => sum + row.source_rows, 0), units);
    assert.equal(rows.filter(row => row.reported_pct !== null).length, rates);
    assert.equal(data.precincts.filter(row => row.state_code === code).length, units);
    for (const row of rows) {
      const parent = parents.find(parent => parent.code === code && parent.county === row.county);
      assert.deepEqual(row.native_record, parent.native);
      assert.equal(row.ballots, parent.ballots);
      assert.equal(row.maps_approved, true);
      assert.equal(row.county_fips, parent.fips);
      assert.equal(row.reference_geometry.boundary_year, 2026);
      assert.match(row.source_url, /originals\/.*json\.gz$/);
      assert.match(row.quality.join(' '), /not certified election-precinct/);
      if (row.reported_pct !== null) assert.equal(row.reported_pct, 100 * row.ballots / row.denominator);
    }
  }
  const twinFalls = data.counties.find(row => row.state_code === 'ID' && row.county === 'Twin Falls County');
  assert.equal(twinFalls.ballots, 28906);
  assert.equal(twinFalls.denominator, 42990);
  assert.equal(twinFalls.reported_pct, null);
  assert.match(twinFalls.quality.join(' '), /registration_does_not_reconcile/);
  assert.ok(data.precincts.filter(row => row.state_code === 'ID' && row.county === 'Twin Falls County')
    .every(row => row.reported_pct === null));
  assert.ok(data.counties.filter(row => row.state_code === 'ND').every(row =>
    row.denominator === null && row.reported_pct === null
    && row.denominator_basis === 'electorate_not_qualified'
    && row.native_record.RegisteredVoters > 0));
});

test('adds Indiana county and Monroe reporting-unit counts only to the live opt-in frame', () => {
  const legacy = loadAdditionalParticipation();
  assert.equal(legacy.counties.filter(row => row.state_code === 'IN').length, 0);
  assert.equal(legacy.precincts.filter(row => row.state_code === 'IN').length, 0);
  const counties = data.counties.filter(row => row.state_code === 'IN');
  const units = data.precincts.filter(row => row.state_code === 'IN');
  assert.equal(counties.length, 92);
  assert.equal(counties.filter(row => row.ballots !== null).length, 75);
  assert.equal(units.length, 103);
  assert.equal(units.filter(row => row.maps_approved).length, 83);
  assert.equal(counties.find(row => row.county_id === 'additional:IN:18105').source_rows, 103);
  assert.equal(counties.find(row => row.county_id === 'additional:IN:18013').ballots, null);
  assert.equal(counties.find(row => row.county_id === 'additional:IN:18013').native_record.VotersVoting, 0);
  assert.equal(units.find(row => row.unit_key === '51').ballots, 241);
  assert.equal(units.find(row => row.unit_key === '51').maps_approved, false);
  assert.ok([...counties, ...units].every(row => row.denominator === null && row.reported_pct === null));
});

test('keeps WV all-method county holds distinct from every early and returned source-mode row', () => {
  const legacy = loadAdditionalParticipation();
  assert.equal(legacy.counties.filter(row => row.state_code === 'WV').length, 0);
  assert.equal(legacy.county_frames, undefined);
  const counties = data.counties.filter(row => row.state_code === 'WV');
  assert.equal(counties.length, 55);
  assert.equal(counties.filter(row => row.ballots !== null).length, 3);
  for (const [mode, total] of [['in_person_early', 162349], ['mail_returned', 7001]]) {
    const rows = data.county_frames.WV[mode];
    assert.equal(rows.length, 55);
    assert.equal(rows.reduce((sum, row) => sum + row.ballots, 0), total);
    assert.ok(rows.every(row => row.source_mode === mode && row.denominator === null
      && row.reported_pct === null && row.cast_ballot_count_qualified === false));
    assert.equal(rows.find(row => row.county_id === 'additional:WV:54107').native_record.COUNTY, 'WOOD');
  }
  assert.equal(counties.find(row => row.county_id === 'additional:WV:54107').ballots, 22935);
  assert.equal(data.county_frames.WV.in_person_early.find(row => row.county_id === 'additional:WV:54107').ballots, 9828);
  assert.equal(data.county_frames.WV.mail_returned.find(row => row.county_id === 'additional:WV:54107').ballots, 340);
});

test('native county-parent review rejects missing, mismatched and cross-election inputs', () => {
  const directory = 'data/precinct-results/20261105-north-dakota-02';
  const original = name => JSON.parse(gunzipSync(readFileSync(`${directory}/originals/${name}.json.gz`)));
  const source = { full: original('full-results'), election: original('election'), turnout: original('turnout') };
  const units = JSON.parse(gunzipSync(readFileSync(`${directory}/participation.json.gz`)));
  const geometry = JSON.parse(gunzipSync(readFileSync('data/county-results/20261105-house-02/geometry/ND.geojson.gz')));
  const mismatch = structuredClone(source);
  mismatch.full.TurnoutData.Locations['38001'].TotalBallotsCast += 1;
  assert.throws(() => reviewCountyParents('ND', mismatch, units, geometry, {}), /disagrees/);
  const missingZero = structuredClone(source);
  delete missingZero.full.TurnoutData.Locations['38105'].Locations['0140'].BallotsCast;
  assert.throws(() => reviewCountyParents('ND', missingZero, units, geometry, {}), /explicit All/);
  const wrongElection = structuredClone(source);
  wrongElection.turnout.electionID = 'other';
  assert.throws(() => reviewCountyParents('ND', wrongElection, units, geometry, {}), /election/);
  assert.throws(() => reviewCountyParents('ND', source, units.slice(1), geometry, {}), /scope|identity/);
  assert.throws(() => reviewCountyParents('ND', source, [...units, units[0]], geometry, {}), /Duplicate/);
  const wrongGeometry = structuredClone(geometry);
  wrongGeometry.features[0].properties.state_code = 'SD';
  assert.throws(() => reviewCountyParents('ND', source, units, wrongGeometry, {}), /reference/);
});

test('preserves every Washington county record and King ballots without using native statewide or unit zeroes', () => {
  const native = csv('data/county-source-reviews/20261106-washington-participation-01/county-participation.csv');
  const rows = data.counties.filter(row => row.state_code === 'WA');
  assert.deepEqual(rows.map(row => row.native_record), native);
  assert.equal(rows.reduce((sum, row) => sum + row.ballots, 0), 2266746);
  for (const row of rows) {
    assert.equal(row.ballots, Number(row.native_record.ballots_cast));
    assert.equal(row.denominator, Number(row.native_record.registered_voters));
    assert.equal(row.reported_pct, 100 * row.ballots / row.denominator);
    assert.equal(row.native_printed_pct, null);
    assert.equal(row.maps_approved, false);
    for (const field of ['source_as_of', 'source_last_updated', 'source_publish_date',
      'state_locality_source_as_of', 'state_locality_source_last_updated'])
      assert.ok(row.source_update_label.includes(row.native_record[field]));
  }
  const king = rows.find(row => row.native_record.source_short_name === 'king-county-wa');
  assert.equal(king.ballots, 601199);
  assert.equal(king.native_record.source_unit_ballots, '0');
  assert.equal(king.native_record.unallocated_county_ballots, '601199');
  assert.match(king.source_reporting_label, /not zero participation/);
  assert.equal(data.precincts.filter(row => row.state_code === 'WA').length, 0);
});

test('preserves all Oregon counted ballots and active registrations despite separate false reporting flags', () => {
  const native = csv('data/county-source-reviews/20261106-oregon-participation-01/county-participation.csv');
  const rows = data.counties.filter(row => row.state_code === 'OR');
  assert.deepEqual(rows.map(row => row.native_record), native);
  assert.equal(rows.reduce((sum, row) => sum + row.ballots, 0), 1760007);
  assert.equal(rows.reduce((sum, row) => sum + row.denominator, 0), 3109086);
  for (const row of rows) {
    const original = JSON.parse(row.native_record.native_record_json);
    assert.equal(row.ballots, original.calcVoterTurnout);
    assert.equal(row.denominator, original.Voters);
    assert.equal(row.denominator_basis, 'native_active_registered_voters');
    assert.equal(row.county_id, `additional:OR:${original.CountyID}`);
    assert.equal(row.reported_pct, null);
    assert.equal(row.native_printed_pct, row.native_record.native_reported_percent);
    assert.equal(row.source_status_literal, 'Unofficial');
    assert.ok(row.source_update_label.includes(original.CurrentDateTime));
    assert.match(row.source_update_label, /11\/5\/2026 \| 8:30 PM PT/);
    assert.match(row.source_reporting_label, /IsReported false/);
    assert.equal(row.maps_approved, false);
    assert.equal(original.IsReported, false);
    assert.ok(row.ballots > 0);
  }
  assert.equal(data.precincts.filter(row => row.state_code === 'OR').length, 0);
});

test('connects Washoe native ballots without replacing them with House votes or counting groups', () => {
  const native = csv('data/county-source-reviews/20261106-washoe-participation-01/county-participation.csv');
  const rows = data.counties.filter(row => row.state_code === 'NV');
  assert.deepEqual(rows.map(row => row.native_record), native);
  assert.equal(rows[0].ballots, 191830);
  assert.equal(rows[0].denominator, 329777);
  assert.equal(rows[0].native_printed_pct, '58.17%');
  assert.equal(rows[0].reported_pct, null);
  assert.equal(rows[0].source_status_literal, 'REPORT 6 - UNOFFICIAL RESULTS');
  assert.match(rows[0].source_update_label, /11\/4\/2026 6:13:35 PM/);
  assert.match(rows[0].source_reporting_label, /must not be summed/);
  assert.equal(rows[0].maps_approved, false);
  assert.equal(data.precincts.filter(row => row.state_code === 'NV').length, 0);
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

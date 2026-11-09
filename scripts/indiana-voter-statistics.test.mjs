import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import test from 'node:test';
import { loadIndianaVoterStatistics, reviewIndianaVoterStatistics, reviewIndianaMonroe } from './indiana-voter-statistics.mjs';
import { qualifiedIndianaMonroePrecinct } from '../public/scripts/participation-geography.js';

const directory = process.env.INDIANA_REVIEW_FIXTURE
  || 'data/county-source-reviews/20261109-indiana-voter-statistics-01';
const json = name => JSON.parse(readFileSync(`${directory}/${name}`));
const compressed = name => JSON.parse(gunzipSync(readFileSync(`${directory}/${name}`)));
const inputs = json('inputs.json');
const fixture = {
  settings: compressed('original-settings.json.gz'),
  turnout: compressed('original-statewide-turnout.json.gz'),
  roster: compressed('native-county-identity-control.json.gz'),
  geometry: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))),
  reference: inputs.reference, countyParents: [],
};

test('preserves all 93 Indiana rows while withholding 24 contradictory source zeros, not substituting votes', () => {
  const before = structuredClone(fixture);
  const data = reviewIndianaVoterStatistics(fixture);
  assert.deepEqual(fixture, before);
  assert.equal(data.counties.length, 92);
  assert.equal(data.summary.selected_counts, 68);
  assert.equal(data.summary.held_counts, 24);
  assert.equal(data.original_state_subtotal.VotersVoting, 1055902);
  assert.deepEqual(data.original_state_subtotal, fixture.turnout.root.CountyTurnout.at(-1));
  assert.equal(new Set(data.counties.map(row => row.county_fips)).size, 92);
  for (const row of data.counties) {
    assert.deepEqual(row.statewide_statistics_native_record,
      fixture.turnout.root.CountyTurnout.find(native => native.County === row.native_record.County));
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    assert.equal(row.cast_ballot_count_qualified, false);
    assert.equal(row.unique_voter_count_qualified, false);
    assert.match(row.source_update_label, /2026-11-09T15:03:29\.353; timezone not supplied/);
    if (row.native_record.VotersVoting === 0) {
      assert.equal(row.source_count, null);
      assert.equal(row.source_count_qualified, false);
      assert.ok(row.source_candidate_votes_not_participation > 0);
      assert.match(row.source_reporting_label, /not zero turnout/);
    } else {
      assert.equal(row.source_count, row.native_record.VotersVoting);
      assert.match(row.participation_measure_label, /Native Voters Voting/);
    }
  }
  const hamilton = data.counties.find(row => row.county_fips === '18057');
  assert.equal(hamilton.source_count, 150804);
  assert.equal(hamilton.native_record.REGISTERED_VOTERS, 290805);
  assert.equal(hamilton.native_record.InPerson, 70925);
  assert.equal(hamilton.native_record.Absentee, 79879);
  assert.notEqual(hamilton.source_count, hamilton.source_candidate_votes_not_participation);
});

test('accepts a source zero with no contradiction but never labels it certified turnout', () => {
  const source = structuredClone(fixture);
  source.roster.rows.find(row => row.county_fips === '18013').candidate_counts.fill(0);
  const row = reviewIndianaVoterStatistics(source).counties.find(item => item.county_fips === '18013');
  assert.equal(row.source_count, 0);
  assert.equal(row.native_record.VotersVoting, 0);
  assert.equal(row.source_count_qualified, true);
  assert.equal(row.reported_pct, null);
  assert.equal(row.unique_voter_count_qualified, false);
});

test('uses an independently reviewed parent without overwriting the original zero or printed state subtotal', () => {
  const source = structuredClone(fixture);
  const parent = {
    state_code: 'IN', county: 'Brown County', county_fips: '18013', election_date: '2026-11-03',
    whole_county_scope_reviewed: true, unique_voters_certified: false, analysis_rate_approved: false,
    measure_kind: 'native_ballots_cast', measure_literal: 'Ballots Cast - Total', count: 7000,
    source_url: 'https://county.invalid/2026-summary.pdf', original_sha256: 'a'.repeat(64),
    original_bytes: 100, source_clock_literal: 'Native test-fixture clock, timezone unspecified',
    source_status_literal: 'UNOFFICIAL RESULTS',
    native_record: { county: 'Brown County', native_ballots_cast: '7,000' },
  };
  source.countyParents = [parent];
  const data = reviewIndianaVoterStatistics(source);
  const row = data.counties.find(item => item.county_fips === '18013');
  assert.equal(row.source_count, 7000);
  assert.deepEqual(row.native_record, parent.native_record);
  assert.equal(row.statewide_statistics_native_record.VotersVoting, 0);
  assert.equal(data.original_state_subtotal.VotersVoting, 1055902);
  assert.equal(data.summary.selected_counts, 69);
  assert.equal(data.summary.held_counts, 23);
  assert.equal(row.reported_pct, null);
  for (const mutate of [
    value => { value.countyParents[0].measure_literal = 'Total Votes'; },
    value => { value.countyParents[0].whole_county_scope_reviewed = false; },
    value => { value.countyParents[0].count = 0; },
    value => { value.countyParents[0].election_date = '2024-11-05'; },
    value => { value.countyParents[0].county_fips = '18057'; },
  ]) {
    const changed = structuredClone(source);
    mutate(changed);
    assert.throws(() => reviewIndianaVoterStatistics(changed), /Indiana/);
  }
});

test('rejects changed elections, unsafe counts, missing counties, mode conflicts and incompatible references', () => {
  for (const mutate of [
    value => { value.settings.Root.CurrentElection = '11/05/2024'; },
    value => { value.settings.Root.Certified = 'T'; },
    value => { value.turnout.root.CountyTurnout.pop(); },
    value => { value.turnout.root.CountyTurnout[0].VotersVoting = null; },
    value => { value.turnout.root.CountyTurnout[0].VotersVoting = true; },
    value => { value.turnout.root.CountyTurnout[0].InPerson += 1; },
    value => { value.roster.rows[0].county_fips = value.roster.rows[1].county_fips; },
    value => { value.roster.rows[0].candidate_counts[0] = false; },
    value => { value.reference.boundary_year = 2013; },
    value => { value.geometry.features.pop(); },
  ]) {
    const changed = structuredClone(fixture);
    mutate(changed);
    assert.throws(() => reviewIndianaVoterStatistics(changed), /Indiana/);
  }
});

test('selects seven independent snapshots, preserving all original zeros, literal measures and state subtotal', () => {
  const data = loadIndianaVoterStatistics();
  assert.equal(data.summary.selected_counts, 75);
  assert.equal(data.summary.held_counts, 17);
  assert.equal(data.summary.independent_county_parents, 7);
  assert.equal(data.original_state_subtotal.VotersVoting, 1055902);
  const selected = { '18017': 9699, '18043': 28336, '18049': 5350, '18105': 42766,
    '18127': 59917, '18129': 7857, '18177': 16514 };
  for (const row of data.counties) {
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    if (selected[row.county_fips]) {
      assert.equal(row.source_count, selected[row.county_fips]);
      assert.equal(row.statewide_statistics_native_record.VotersVoting, 0);
    }
    if (['18017', '18049'].includes(row.county_fips)) {
      assert.equal(row.selected_source_kind, 'native_turnout_numerator');
      assert.equal(row.cast_ballot_count_qualified, false);
      assert.match(row.participation_measure_label, /not cast ballots/);
    }
  }
  assert.equal(data.counties.find(row => row.county_fips === '18091').source_count, null);
  assert.equal(data.counties.find(row => row.county_fips === '18043').source_status_literal, null);
});

test('keeps all 103 Monroe counts but maps only 83 nonoverlapping references, with no rates or allocations', () => {
  const data = loadIndianaVoterStatistics();
  assert.equal(data.precincts.length, 103);
  assert.equal(data.precincts.reduce((sum, row) => sum + row.ballots, 0), 42766);
  assert.equal(data.precincts.filter(row => row.match_status === 'matched').length, 83);
  assert.equal(data.precincts.filter(row => row.geometry_withheld_reason).length, 20);
  assert.match(data.precincts.find(row => row.native_precinct_id === 51).geometry_withheld_reason, /carrier/);
  const source = JSON.parse(readFileSync(inputs.monroe.source_count_file));
  const units = compressed('monroe-reporting-units.json.gz');
  const geometry = JSON.parse(gunzipSync(readFileSync(inputs.monroe.normalized_reference_file)));
  const audit = json('monroe-reference-review.json');
  assert.equal(reviewIndianaMonroe({ units, source, geometry, audit }).length, 103);
  for (const feature of geometry.features) assert.equal(qualifiedIndianaMonroePrecinct(feature.properties), true);
  for (const mutate of [
    value => { value.units[0].ballots++; },
    value => { value.units[0].reported_pct = 50; },
    value => { value.units[0].year = 2024; },
    value => { value.geometry.features[0].properties.ballots++; },
    value => { value.audit.geometry_repaired = true; },
  ]) {
    const changed = structuredClone({ units, source, geometry, audit });
    mutate(changed);
    assert.throws(() => reviewIndianaMonroe(changed), /Indiana Monroe/);
  }
  for (const mutate of [
    value => { value.state_code = 'MI'; },
    value => { value.year = 2024; },
    value => { value.native_record.Ballots_Cast++; },
    value => { value.denominator = 1000; },
    value => { value.match_status = 'withheld_source_geometry'; },
  ]) {
    const changed = structuredClone(geometry.features[0].properties);
    mutate(changed);
    assert.equal(qualifiedIndianaMonroePrecinct(changed), false);
  }
});

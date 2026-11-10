import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { loadConnecticutTowns, reviewConnecticutTowns } from './connecticut-town-counts.mjs';
import { qualifiedConnecticutTownReference } from '../public/scripts/participation-geography.js';

const version = 'data/county-source-reviews/20261110-connecticut-towns-01';
const fixture = () => {
  const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
  const native = name => JSON.parse(gunzipSync(readFileSync(`${version}/originals/${name}.json.gz`)));
  return { inputs, turnout: native('voterTurnout_Electiondata'), after: native('after-voterTurnout_Electiondata'),
    election: native('election_Electiondata'), elections: native('Elections'), status: native('townStatus_Electiondata'),
    version: native('Version'), afterVersion: native('Version-after-reports'),
    original: JSON.parse(gunzipSync(readFileSync(`${version}/originals/municipality-CT-2024.geojson.gz`))),
    geometry: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))) };
};
const imported = row => ({ ...row, ballots: row.source_count,
  county_id: `additional:CT:${row.source_administration_id}` });

test('all169 native towns reconcile eight columns without double-counting Total or inventing counties/precincts', () => {
  const data = loadConnecticutTowns();
  assert.equal(data.towns.length, 169);
  assert.equal(Object.keys(data.all_native_source_queries).length, 170);
  assert.equal(data.towns.reduce((sum, r) => sum + r.source_count, 0), 1150127);
  assert.ok(data.accounting.every(r => r.agrees));
  assert.equal(data.towns.find(r => r.source_town_id === '1').source_count, 2214);
  assert.equal(data.towns.find(r => r.source_town_id === '20').native_record.PR, '');
  assert.equal(data.summary.blank_town_reporting_counters, 13);
  for (const row of data.towns) {
    assert.equal(row.county_fips, null);
    assert.equal(row.reference_geometry.boundary_year, 2024);
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    assert.equal(row.native_printed_pct, row.native_record.TO);
    assert.equal(row.cast_ballot_count_qualified, false);
    assert.equal(row.unique_voter_count_qualified, false);
  }
});

test('a native town zero survives while missing counts and inconsistent native parents are rejected', () => {
  const f = fixture(), prior = Number(f.turnout['1'].VV);
  f.turnout['1'].VV = f.after['1'].VV = '0';
  f.turnout['170'].VV = f.after['170'].VV = String(1150127 - prior);
  f.election.BC = String(1150127 - prior);
  const result = reviewConnecticutTowns(f);
  assert.equal(result.towns[0].source_count, 0);
  assert.equal(result.towns[0].native_printed_pct, '93.50%');
  for (const change of [
    x => x.turnout['1'].VV = x.after['1'].VV = '',
    x => x.turnout['1'].VV = x.after['1'].VV = null,
    x => x.turnout['1'].VV = x.after['1'].VV = '2215',
    x => x.after['1'].EV = '0',
    x => x.election.BC = '0',
  ]) {
    const changed = fixture();
    change(changed);
    assert.throws(() => reviewConnecticutTowns(changed));
  }
});

test('native election and original contextual geometry cannot be relabeled or altered', () => {
  for (const change of [
    x => x.elections.find(r => r.ID === '108').Name = '2024 election',
    x => x.election.ID = '97',
    x => x.inputs.reference.boundary_year = 2026,
    x => x.inputs.rates_approved = true,
    x => x.version.Version = 52338,
    x => x.geometry.features[0].properties.source_town_id = '170',
    x => x.geometry.features[0].geometry.coordinates = [],
  ]) {
    const changed = fixture();
    change(changed);
    assert.throws(() => reviewConnecticutTowns(changed));
  }
});

test('browser town joins reject missing identities, fake county FIPS, changed counts and false2026 shapes', () => {
  const f = fixture(), rows = loadConnecticutTowns().towns.map(imported);
  assert.equal(qualifiedConnecticutTownReference(rows, f.inputs.reference, f.geometry), true);
  for (const change of [
    x => x.rows.pop(),
    x => x.rows[0].county_fips = '09001',
    x => x.rows[0].ballots++,
    x => x.rows[0].reported_pct = 1,
    x => x.reference.boundary_year = 2026,
    x => x.geometry.features[0].properties.source_administration_id = 'CT-TOWN-170',
  ]) {
    const changed = structuredClone({ rows, reference: f.inputs.reference, geometry: f.geometry });
    change(changed);
    assert.equal(qualifiedConnecticutTownReference(changed.rows, changed.reference, changed.geometry), false);
  }
});

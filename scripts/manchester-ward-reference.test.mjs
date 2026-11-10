import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { qualifiedManchesterWardReference } from '../public/scripts/participation-geography.js';

const root = 'public/participation-precincts/20261110-manchester-ward-reference-01/';
const data = JSON.parse(gunzipSync(readFileSync(root+'NH.geojson.gz')));
const index = JSON.parse(readFileSync(root+'index.json','utf8'));

test('all twelve source ward totals use explicit current municipal context, not certified2026 precincts', () => {
  assert.equal(data.features.length,12);
  assert.ok(data.features.every(f => qualifiedManchesterWardReference(f.properties)));
  assert.equal(data.features.reduce((sum,f) => sum+f.properties.ballots,0),38562);
  assert.equal(index.state_metadata.NH.boundary_reference_year,2022);
  assert.equal(index.state_metadata.NH.current_clerk_effective_date,'2021-12-21');
  assert.equal(index.state_metadata.NH.held_table_only_ward_rows,25);
  const registry = JSON.parse(readFileSync('public/participation-precincts.json','utf8'));
  assert.equal(registry.additional_sources.filter(r => !r.base_url.includes('20261110-massachusetts-native-local-counts-01')).length,4);
  assert.ok(registry.additional_sources.some(row => row.base_url === '/participation-precincts/20261110-alaska-native-display-01/'));
  assert.ok(registry.additional_sources.some(row => row.base_url === '/participation-precincts/20261109-indiana-monroe-01/'));
});

test('corrected raw totals, mislabeled source identities, inferred rates and false2026 shapes reject', () => {
  const source = data.features.find(f => f.properties.native_ward_number === 7).properties;
  assert.equal(source.ballots,2712);
  for (const change of [
    p => {p.ballots=2797;},
    p => {p.native_object_id=7;},
    p => {p.reference_geometry.boundary_vintage=2026;},
    p => {p.reference_geometry.certified_legal_boundaries=true;},
    p => {p.reference_geometry.native_overlaps_preserved=false;},
    p => {p.source_election_date='2024-11-05';},
    p => {p.denominator=1;p.reported_pct=100;},
    p => {p.reporting_unit_kind='precinct';},
    p => {p.cast_ballot_count_qualified=true;},
  ]) {
    const changed = structuredClone(source);change(changed);
    assert.equal(qualifiedManchesterWardReference(changed),false);
  }
});

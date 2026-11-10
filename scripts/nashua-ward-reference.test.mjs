import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { qualifiedNashuaWardReference } from '../public/scripts/participation-geography.js';

const root = 'public/participation-precincts/20261110-new-hampshire-ward-reference-03/';
const data = JSON.parse(gunzipSync(readFileSync(root+'NH.geojson.gz')));
const previous = JSON.parse(gunzipSync(readFileSync('public/participation-precincts/20261110-new-hampshire-ward-reference-02/NH.geojson.gz')));
const index = JSON.parse(readFileSync(root+'index.json','utf8'));

test('preserves all22 earlier features and maps nine adopted Nashua counts without repairing source totals', () => {
  assert.deepEqual(data.features.slice(0,22),previous.features);
  const nashua = data.features.slice(22);
  assert.equal(nashua.length,9);
  assert.ok(nashua.every(f => qualifiedNashuaWardReference(f.properties)));
  assert.equal(nashua.reduce((sum,f) => sum+f.properties.ballots,0),33849);
  assert.equal(nashua.reduce((sum,f) => sum+f.properties.native_record.federal_only,0),92);
  assert.equal(index.state_metadata.NH.held_table_only_ward_rows,6);
  assert.equal(index.state_metadata.NH.boundary_reference_years.Nashua,null);
  const registry = JSON.parse(readFileSync('public/participation-precincts.json','utf8'));
  assert.equal(registry.additional_sources.filter(r => !r.base_url.includes('20261110-massachusetts-')
    && !r.base_url.includes('/20261110-minnesota-')).length,4);
  assert.equal(registry.additional_sources.filter(r =>
    /^\/participation-precincts\/20261110-new-hampshire-ward-reference-0[34]\/$/.test(r.base_url)).length,1);
});

test('rejects object IDs as wards, proposed/point/parcel roles, repaired source conflicts and inferred rates', () => {
  const source = data.features.find(f => f.properties.county === 'Nashua'
    && f.properties.native_ward_number === 8).properties;
  assert.equal(source.ballots,3575);
  for (const change of [
    p => {p.native_object_id=8;},
    p => {p.reference_geometry.rest_layer_id=6;},
    p => {p.reference_geometry.proposed_geometry_used=true;},
    p => {p.reference_geometry.layer_name='Proposed Ward Boundaries';},
    p => {p.reference_geometry.certified_legal_boundaries=true;},
    p => {p.ballots=3574;},
    p => {p.denominator=1;p.reported_pct=100;},
    p => {p.cast_ballot_count_qualified=true;},
  ]) {
    const changed = structuredClone(source);change(changed);
    assert.equal(qualifiedNashuaWardReference(changed),false);
  }
});

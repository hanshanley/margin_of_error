import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { qualifiedConcordWardReference, qualifiedManchesterWardReference } from '../public/scripts/participation-geography.js';

const root = 'public/participation-precincts/20261110-new-hampshire-ward-reference-02/';
const data = JSON.parse(gunzipSync(readFileSync(root+'NH.geojson.gz')));
const previous = JSON.parse(gunzipSync(readFileSync('public/participation-precincts/20261110-manchester-ward-reference-01/NH.geojson.gz')));
const index = JSON.parse(readFileSync(root+'index.json','utf8'));

test('preserves every Manchester feature and adds ten literal Concord counts without reusing a service-name year', () => {
  assert.deepEqual(data.features.slice(0,12),previous.features);
  assert.ok(data.features.slice(0,12).every(f => qualifiedManchesterWardReference(f.properties)));
  const concord = data.features.slice(12);
  assert.equal(concord.length,10);
  assert.ok(concord.every(f => qualifiedConcordWardReference(f.properties)));
  assert.equal(concord.reduce((sum,f) => sum+f.properties.ballots,0),19234);
  assert.equal(index.state_metadata.NH.held_table_only_ward_rows,15);
  assert.equal(index.state_metadata.NH.boundary_reference_years.Concord,null);
  const registry = JSON.parse(readFileSync('public/participation-precincts.json','utf8'));
  assert.equal(registry.additional_sources.filter(r => !r.base_url.includes('20261110-massachusetts-')
    && !r.base_url.includes('/20261110-minnesota-')).length,4);
  assert.equal(registry.additional_sources.filter(r =>
    /^\/participation-precincts\/20261110-new-hampshire-ward-reference-0[234]\/$/.test(r.base_url)).length,1);
});

test('rejects native-ID mistakes, school-split changes, false vintage/datum claims and source printed percentages used as rates', () => {
  const source = data.features.find(f => f.properties.county === 'Concord'
    && f.properties.native_ward_number === 1).properties;
  for (const change of [
    p => {p.native_object_id=1;},
    p => {p.native_record.total_cast_columns.pop();},
    p => {p.native_record.printed_ward_subtotal=0;},
    p => {p.reference_geometry.boundary_vintage=2020;},
    p => {p.reference_geometry.native_datum_operation.forward=true;},
    p => {p.reference_geometry.certified_legal_boundaries=true;},
    p => {p.denominator=p.native_record.opening;p.reported_pct=100;},
    p => {p.cast_ballot_count_qualified=true;},
  ]) {
    const changed = structuredClone(source);change(changed);
    assert.equal(qualifiedConcordWardReference(changed),false);
  }
});

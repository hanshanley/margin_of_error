import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { qualifiedDoverWardReference, qualifiedManchesterWardReference,
  qualifiedConcordWardReference, qualifiedNashuaWardReference } from '../public/scripts/participation-geography.js';

const root = 'public/participation-precincts/20261110-new-hampshire-ward-reference-04/';
const data = JSON.parse(gunzipSync(readFileSync(root+'NH.geojson.gz')));
const previous = JSON.parse(gunzipSync(readFileSync(
  'public/participation-precincts/20261110-new-hampshire-ward-reference-03/NH.geojson.gz')));

test('all37 direct native references retain31 prior features and all six literal Dover counts', () => {
  assert.deepEqual(data.features.slice(0, 31), previous.features);
  const dover = data.features.slice(31);
  assert.equal(dover.length, 6);
  assert.ok(dover.every(feature => qualifiedDoverWardReference(feature.properties)));
  assert.deepEqual(dover.map(feature => feature.properties.ballots), [2577, 2533, 3207, 2872, 2298, 2454]);
  assert.equal(dover.reduce((sum, feature) => sum + feature.properties.ballots, 0), 15941);
  assert.ok(data.features.every(({ properties: p }) => qualifiedManchesterWardReference(p)
    || qualifiedConcordWardReference(p) || qualifiedNashuaWardReference(p) || qualifiedDoverWardReference(p)));
  const index = JSON.parse(readFileSync(root+'index.json'));
  assert.equal(index.state_metadata.NH.held_table_only_ward_rows, 0);
  assert.equal(index.state_metadata.NH.boundary_reference_years.Dover, 2022);
  const registry = JSON.parse(readFileSync('public/participation-precincts.json'));
  assert.equal(registry.additional_sources.filter(row => row.base_url === '/'+root.slice(7)).length, 1);
  assert.ok(registry.additional_sources.some(row =>
    row.base_url === '/participation-precincts/20261110-massachusetts-city-precinct-reference-02/'));
});

test('Dover rejects FID-as-ward, county allocation, old geometry roles, wrong datum and source-rate promotion', () => {
  const source = data.features[31].properties;
  for (const change of [
    p => { p.native_ward_number = 280; },
    p => { p.county_fips = '33017'; },
    p => { p.reference_geometry.rest_layer_id = 5; },
    p => { p.reference_geometry.boundary_vintage = 2020; },
    p => { p.reference_geometry.native_datum_operation.code = 1188; },
    p => { p.reference_geometry.native_projection_epsg = 32110; },
    p => { p.reference_geometry.certified_legal_boundaries = true; },
    p => { p.reference_geometry.source_geometry_clipped = true; },
    p => { p.native_record.ballots.total = 1; },
    p => { p.denominator = p.native_record.registrations.registered; p.reported_pct = 68.2; },
  ]) {
    const changed = structuredClone(source);
    change(changed);
    assert.equal(qualifiedDoverWardReference(changed), false);
  }
});

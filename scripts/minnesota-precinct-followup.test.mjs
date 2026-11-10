import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { qualifiedMinnesotaPrecinctReference } from '../public/scripts/participation-geography.js';

const root = 'data/county-source-reviews/20261110-minnesota-followup-02/';
const data = JSON.parse(gunzipSync(readFileSync(root + 'MN.geojson.gz')));
const review = JSON.parse(gunzipSync(readFileSync(root + 'precinct-reference-queries.json.gz')));

test('all4105 full native references join current IDs;4079 counts and26 unknowns never promote rates or generalized shapes', () => {
  assert.equal(data.features.length, 4105);
  assert.ok(data.features.every(feature => qualifiedMinnesotaPrecinctReference(feature.properties)));
  assert.equal(data.features.filter(feature => feature.properties.ballots === null).length, 26);
  assert.equal(data.features.reduce((sum, feature) => sum + (feature.properties.ballots ?? 0), 0), 2827091);
  assert.equal(review.summary.positive_native_overlap_pairs, 0);
  assert.equal(review.summary.invalid_generalized_legacy_references_not_reused.length, 16);
  assert.equal(review.summary.names_differ_beyond_case, 1723);
  assert.equal(review.all4105_reference_decisions.length, 4105);
  assert.ok(data.features.every(feature => feature.properties.reported_pct === null));
  const registry = JSON.parse(readFileSync('public/participation-precincts.json'));
  assert.equal([...registry.additional_sources, ...(registry.previous_sources || [])].filter(row =>
    row.base_url === '/participation-precincts/20261110-minnesota-followup-02/').length, 1);
  assert.ok(registry.additional_sources.some(row =>
    row.base_url === '/participation-precincts/20261110-new-hampshire-ward-reference-04/'));
});

test('current Minnesota references reject missing-as-zero, wrong native namespaces, rates and repaired/generalized roles', () => {
  const missing = data.features.find(feature => feature.properties.ballots === null).properties;
  assert.equal(qualifiedMinnesotaPrecinctReference({ ...missing, ballots: 0 }), false);
  for (const change of [
    p => { p.reference_geometry.native_vtdid = '270030005'; },
    p => { p.reference_geometry.native_county_fips = p.native_county_id; },
    p => { p.reference_geometry.source_reference_date = '2024-09-18'; },
    p => { p.reference_geometry.generalized_legacy_geometry_used = true; },
    p => { p.reference_geometry.full_native_coordinates_preserved = false; },
    p => { p.reference_geometry.certified_legal_boundaries = true; },
    p => { p.reference_geometry.source_geometry_clipped = true; },
    p => { p.denominator = 1455; p.reported_pct = 1; },
    p => { p.ballots = 2852528; },
  ]) {
    const changed = structuredClone(data.features[0].properties);
    change(changed);
    assert.equal(qualifiedMinnesotaPrecinctReference(changed), false);
  }
});

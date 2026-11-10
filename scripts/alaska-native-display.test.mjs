import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { qualifiedAlaskaNativePrecinct } from '../public/scripts/participation-geography.js';

const load = () => JSON.parse(gunzipSync(readFileSync(
  'public/participation-precincts/20261110-alaska-native-display-01/AK.geojson.gz')));

test('native81 unrepaired shapes preserve geographic ballots, not candidate votes or rates', () => {
  const features = load().features;
  assert.equal(features.length, 81);
  assert.equal(new Set(features.map(f => f.properties.native_precinct_id)).size, 81);
  assert.ok(features.every(f => f.geometry.type === 'MultiPolygon'
    && qualifiedAlaskaNativePrecinct(f.properties)));
  const counts = JSON.parse(gunzipSync(readFileSync(
    'data/precinct-source-reviews/20261110-alaska-native-display-01/qualified-source-count-queries.json.gz')));
  assert.equal(counts.length, 523);
  const byKey = new Map(counts.map(row => [row.key, row]));
  for (const { properties: p } of features) {
    assert.equal(p.ballots, byKey.get(p.key).ballots);
    assert.deepEqual(p.quality_flags, byKey.get(p.key).quality_flags);
    assert.equal(p.reported_pct, null);
    assert.equal(p.denominator, null);
  }
});

test('zero native ballots remain valid; pooled units, changed references and invented rates reject', () => {
  const original = load().features[0].properties;
  const zero = structuredClone(original);
  zero.ballots = zero.native_record.b = 0;
  assert.equal(qualifiedAlaskaNativePrecinct(zero), true);
  for (const change of [
    p => p.ballots = null,
    p => p.ballots++,
    p => p.native_record.contest = 'Governor',
    p => p.native_record.number = '99-999',
    p => p.reporting_unit_kind = 'pooled_district_absentee',
    p => p.count_scope = 'all_ballots',
    p => p.denominator = p.native_record.v,
    p => p.reported_pct = 50,
    p => p.reference_geometry.source_selected_election_app = 2024,
    p => p.reference_geometry.certified_legal_boundaries = true,
    p => p.reference_geometry.topology_valid_without_repairs = false,
    p => p.reference_geometry.single_path_per_polygon = false,
  ]) {
    const row = structuredClone(original);
    change(row);
    assert.equal(qualifiedAlaskaNativePrecinct(row), false);
  }
});

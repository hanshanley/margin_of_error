import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { loadMinnesotaCompleteNative } from './minnesota-complete-native.mjs';
import { qualifiedMinnesotaCountyFrame, qualifiedMinnesotaPrecinctReference,
  selectCountySourceFrame } from '../public/scripts/participation-geography.js';

test('complete native frame closes 26 unknowns without repairing conflicts or inventing precinct rates', () => {
  const { counties, precincts } = loadMinnesotaCompleteNative();
  assert.ok(qualifiedMinnesotaCountyFrame(counties));
  assert.equal(precincts.length, 4105);
  assert.equal(precincts.filter(row => row.ballots === 0 && row.source_count_qualified).length, 32);
  assert.ok(precincts.every(row => row.ballots !== null && row.reported_pct === null));
  assert.equal(counties.filter(row => row.reported_pct !== null).length, 73);
  for (const name of ['Fillmore', 'Hubbard', 'Wright'])
    assert.ok(counties.find(row => row.county === name).source_count_qualified);
  const data = { counties: [], county_frames: { native_county_followup: counties } };
  assert.equal(selectCountySourceFrame(data, 'MN', 'official'), counties);
  for (const mode of ['in_person_early', 'mail_returned'])
    assert.throws(() => selectCountySourceFrame(data, 'MN', mode), /all-method counts are not substituted/);
});

test('new county and precinct guards reject missing flags, source substitutions and invented rates', () => {
  const { counties } = loadMinnesotaCompleteNative();
  for (const replacement of [{ ballots: 0 }, { denominator: 1 }, { reported_units: 0 }]) {
    const changed = structuredClone(counties);
    Object.assign(changed[0], replacement);
    assert.equal(qualifiedMinnesotaCountyFrame(changed), false);
  }
  const geo = JSON.parse(gunzipSync(readFileSync(
    'data/county-source-reviews/20261110-minnesota-complete-native-03/MN.geojson.gz')));
  assert.equal(geo.features.length, 4105);
  assert.ok(geo.features.every(feature => qualifiedMinnesotaPrecinctReference(feature.properties)));
  const original = geo.features[0].properties;
  for (const replacement of [{ ballots: original.ballots + 1 }, { reported_pct: 0.5 },
    { source_snapshot: 'unreviewed' }, { source_count_qualified: false }])
    assert.equal(qualifiedMinnesotaPrecinctReference({ ...original, ...replacement }), false);
  assert.equal(qualifiedMinnesotaPrecinctReference({ ...original, ballots: null, source_count_qualified: false,
    native_record: { ...original.native_record, has_reported_statistics: '0' } }), false);
});

test('explicit complete-source opt-in preserves old readers and other states', async () => {
  const { loadAdditionalParticipation } = await import('./additional-participation.mjs');
  const before = loadAdditionalParticipation({ nativeCountyParents: true });
  const current = loadAdditionalParticipation({ nativeCountyParents: true, minnesotaCompleteNative: true });
  assert.equal(before.counties.filter(row => row.state_code === 'MN' && row.ballots !== null).length, 84);
  assert.equal(current.counties.filter(row => row.state_code === 'MN' && row.ballots !== null).length, 87);
  const registry = JSON.parse(readFileSync('public/participation-precincts.json'));
  assert.equal(registry.additional_sources.filter(row =>
    row.base_url === '/participation-precincts/20261110-minnesota-complete-native-03/').length, 1);
  assert.equal(registry.previous_sources.filter(row =>
    row.base_url === '/participation-precincts/20261110-minnesota-followup-02/').length, 1);
  assert.deepEqual(current.counties.filter(row => row.state_code !== 'MN'),
    before.counties.filter(row => row.state_code !== 'MN'));
  for (const mode of ['in_person_early', 'mail_returned'])
    assert.deepEqual(current.county_frames.MN[mode], before.county_frames.MN[mode]);
  assert.deepEqual(loadAdditionalParticipation({ nativeCountyParents: true }), before);
});

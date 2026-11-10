import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { loadMaineLocalityActivity, reviewMaineLocalityActivity } from './maine-locality-activity.mjs';

const version = 'data/county-source-reviews/20261110-maine-locality-activity-01';
const fixture = () => {
  const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
  return { inputs, original: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))),
    historical: JSON.parse(gunzipSync(readFileSync(inputs.historical_identity_path))),
    sources: Object.fromEntries(Object.entries(inputs.responses).map(([category, row]) =>
      [category, { native: JSON.parse(readFileSync(row.path, 'utf8')), receipt: row.receipt }])) };
};

test('all1168 source and1056 reference decisions retain480 mapped and104/48 held per mode', () => {
  const data = loadMaineLocalityActivity();
  assert.equal(data.complete_source_region_queries.length, 1168);
  assert.equal(data.complete_reference_queries.length, 1056);
  assert.equal(data.complete_frame_queries.length, 2);
  for (const mode of ['in_person_early', 'mail_returned']) {
    const mapped = data.locality_frames[mode];
    assert.equal(mapped.length, 480);
    assert.equal(new Set(mapped.map(r => r.reference_key)).size, 480);
    assert.equal(data.complete_source_region_queries.filter(r => r.mode === mode && r.reference_key === null).length, 104);
    assert.equal(data.complete_reference_queries.filter(r => r.mode === mode && r.source_region === null).length, 48);
    for (const row of mapped) {
      assert.equal(row.source_count, Object.values(row.native_categories).reduce((sum, r) => sum + r.votes, 0));
      assert.equal(row.denominator, null);
      assert.equal(row.reported_pct, null);
      assert.equal(row.native_election_id_qualified, false);
      assert.equal(row.cast_ballot_count_qualified, false);
      assert.equal(row.unique_voter_count_qualified, false);
    }
  }
});

test('ambiguous plantations/townships are not assigned by elimination or aggregated into other shapes', () => {
  const data = loadMaineLocalityActivity(), rows = data.complete_source_region_queries;
  assert.equal(rows.find(r => r.source_region === 'Lincoln').reference_key, '2339475');
  for (const name of ['Lincoln Plt', 'Rangeley Plt', 'Unity Twp', 'Washington Twp'])
    assert.equal(rows.find(r => r.source_region === name).reference_key, null);
  const changed = fixture();
  for (const row of changed.historical) row.geography = null;
  const withoutQualified = reviewMaineLocalityActivity(changed);
  assert.equal(withoutQualified.locality_frames.in_person_early.length, 476);
  assert.equal(withoutQualified.complete_source_region_queries.find(r => r.source_region === 'Lincoln').reference_key, null);
});

test('native zero cells remain zero while missing cells, mismatched parents and false2026 shapes reject', () => {
  const f = fixture(), source = f.sources.returned.native;
  for (const [category, bucket] of Object.entries(source.regions.Abbot)) {
    source.statewide_total[category].votes -= bucket.votes;
    bucket.votes = 0;
  }
  assert.equal(reviewMaineLocalityActivity(f).locality_frames.mail_returned
    .find(r => r.source_region === 'Abbot').source_count, 0);
  for (const change of [
    x => Object.values(x.sources.returned.native.regions.Abbot)[0].votes = null,
    x => Object.values(x.sources.returned.native.statewide_total)[0].votes++,
    x => x.sources.returned.native.snapshot_date = '2024-11-02',
    x => x.inputs.reference.boundary_year = 2026,
    x => x.inputs.native_election_id_qualified = true,
    x => x.inputs.rates_approved = true,
    x => x.original.features[0].properties.key = x.original.features[1].properties.key,
  ]) {
    const changed = fixture();
    change(changed);
    assert.throws(() => reviewMaineLocalityActivity(changed));
  }
});

test('held historical counts and rates are never transferred to2026 provider activity', () => {
  const f = fixture();
  for (const row of f.historical) {
    row.total_participation = 999999999;
    row.registered = 1;
    row.turnout_pct = 100;
    row.methods = {};
  }
  assert.deepEqual(reviewMaineLocalityActivity(f), loadMaineLocalityActivity());
});

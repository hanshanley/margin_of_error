import test from 'node:test';
import assert from 'node:assert/strict';
import { loadAlabamaCountyCounts } from './alabama-county-counts.mjs';
import { qualifiedAlabamaCountyFrame, selectCountySourceFrame } from '../public/scripts/participation-geography.js';

test('all67 native county counts use explicit county references while preserving the original field and clock', () => {
  const { counties } = loadAlabamaCountyCounts();
  assert.ok(qualifiedAlabamaCountyFrame(counties));
  const jefferson = counties.find(row => row.native_record.county_code === '01');
  assert.equal(jefferson.county_fips, '01073');
  assert.equal(jefferson.ballots, 248526);
  assert.equal(jefferson.denominator, 497469);
  assert.equal(jefferson.native_printed_pct, '49.96%');
  assert.equal(jefferson.reported_pct, null);
  assert.equal(jefferson.source_update_literal, '11/04/2026 12:07:22 AM');
});

test('native frame rejects candidate substitutions, inferred rates and ordinal-as-FIPS duplication', () => {
  const original = loadAlabamaCountyCounts().counties;
  for (const replacement of [
    { ballots: 1 }, { reported_pct: 49.96 }, { county_fips: '01001' },
    { source_update_timezone: 'UTC' }, { registration_frame_qualified: true },
  ]) {
    const rows = structuredClone(original);
    Object.assign(rows.find(row => row.native_record.county_code === '01'), replacement);
    assert.equal(qualifiedAlabamaCountyFrame(rows), false);
    assert.throws(() => selectCountySourceFrame(
      { counties: [], county_frames: { native_county_counts: rows } }, 'AL', 'available'), /Unqualified Alabama/);
  }
});

test('only live opt-in changes Alabama map approval; old keys and values survive and Minnesota remains qualified', async () => {
  const { loadAdditionalParticipation } = await import('./additional-participation.mjs');
  const legacy = loadAdditionalParticipation();
  const live = loadAdditionalParticipation({ nativeCountyParents: true });
  const old = legacy.counties.filter(row => row.state_code === 'AL');
  const current = live.counties.filter(row => row.state_code === 'AL');
  assert.equal(old.length, 67);
  assert.ok(old.every(row => !row.maps_approved));
  assert.ok(qualifiedAlabamaCountyFrame(current));
  for (const previous of old) {
    const next = current.find(row => row.county_id === previous.county_id);
    assert.equal(next.county, previous.county);
    assert.equal(next.ballots, previous.ballots);
    assert.equal(next.denominator, previous.denominator);
  }
  assert.deepEqual(loadAdditionalParticipation(), legacy);
  const frames = { counties: old, county_frames: live.county_frames.AL };
  for (const mode of ['available', 'official'])
    assert.equal(selectCountySourceFrame(frames, 'AL', mode), live.county_frames.AL.native_county_counts);
  for (const mode of ['in_person_early', 'mail_returned'])
    if (live.county_frames.AL[mode])
      assert.equal(selectCountySourceFrame(frames, 'AL', mode), live.county_frames.AL[mode]);
    else
      assert.equal(selectCountySourceFrame(frames, 'AL', mode).length, 0,
        'All-method county counts must not fill an unsupported early/returned mode');
  assert.equal(live.counties.filter(row => row.state_code === 'MN' && row.ballots !== null).length, 84);
});

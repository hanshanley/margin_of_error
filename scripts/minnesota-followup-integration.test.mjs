import test from 'node:test';
import assert from 'node:assert/strict';
import { loadAdditionalParticipation } from './additional-participation.mjs';
import { qualifiedMinnesotaCountyFrame, selectCountySourceFrame } from '../public/scripts/participation-geography.js';

test('only the live opt-in replaces Minnesota containers and stale unit statistics with the complete reviewed snapshot', () => {
  const legacy = loadAdditionalParticipation();
  const live = loadAdditionalParticipation({ nativeCountyParents: true });
  const counties = live.counties.filter(row => row.state_code === 'MN');
  assert.ok(legacy.counties.filter(row => row.state_code === 'MN').every(row => row.ballots === null));
  assert.ok(qualifiedMinnesotaCountyFrame(counties));
  assert.equal(live.precincts.filter(row => row.state_code === 'MN').length, 4105);
  assert.ok(live.precincts.filter(row => row.state_code === 'MN')
    .every(row => row.source_snapshot === '20261110-minnesota-followup-02'));
  assert.deepEqual(loadAdditionalParticipation(), legacy);
  const combined = { counties: [{ state_code: 'MN', county: 'Aitkin', ballots: 1 }],
    county_frames: live.county_frames.MN };
  assert.equal(selectCountySourceFrame(combined, 'MN', 'available'), live.county_frames.MN.native_county_followup);
  for (const mode of ['in_person_early', 'mail_returned']) {
    const selected = selectCountySourceFrame(combined, 'MN', mode);
    assert.ok(selected.every(row => row.source_provider === 'civicAPI early activity'));
    assert.ok(selected.every(row => row.source_snapshot !== '20261110-minnesota-followup-02'));
  }
});

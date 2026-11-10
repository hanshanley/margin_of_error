import test from 'node:test';
import assert from 'node:assert/strict';
import { loadNativeModeInputs, reviewNativeModeFrames } from './native-mode-frames.mjs';
import { selectCountySourceFrame } from '../public/scripts/participation-geography.js';

test('all204 actual merged-source decisions remove23 unqualified selections and preserve defaults and qualified frames', async () => {
  const result = await reviewNativeModeFrames();
  assert.equal(result.summary.available_official_decisions_preserved, 102);
  assert.equal(result.summary.changed_unsupported_mode_decisions, 23);
  assert.equal(result.summary.residual_non_mode_specific_selections, 0);
  assert.equal(result.summary.changed_states.length, 16);
  for (const code of ['AK', 'DC'])
    assert.ok(result.complete204_state_mode_decisions.filter(row => row.state_code === code && row.explicit_requested_mode)
      .every(row => !row.separate_local_export_present && row.after_selected_rows === 0));
  assert.ok(result.summary.DC_existing_reviewed_county_observation_preserved);
});

test('unsupported modes cannot borrow zero or positive all-method, town, card or municipal observations', () => {
  for (const code of ['AK', 'DC', 'CT', 'HI', 'MO', 'NH', 'RI', 'VT'])
    for (const ballots of [0, 100]) {
      const counties = [{ state_code: code, county_id: 'native', ballots, source_mode: 'native_other_frame' }];
      const data = { counties, precincts: [{ state_code: code, ballots }] };
      assert.equal(selectCountySourceFrame(data, code, 'available'), counties);
      assert.equal(selectCountySourceFrame(data, code, 'official'), counties);
      for (const mode of ['in_person_early', 'mail_returned'])
        assert.deepEqual(selectCountySourceFrame(data, code, mode), []);
      assert.equal(counties[0].ballots, ballots);
    }
});

test('qualified actual provider frames survive but missing requested frames still fail instead of borrowing native totals', async () => {
  const { byState } = await loadNativeModeInputs();
  const data = byState.TX;
  for (const mode of ['in_person_early', 'mail_returned']) {
    assert.equal(selectCountySourceFrame(data, 'TX', mode), data.county_frames[mode]);
    const broken = structuredClone(data);
    delete broken.county_frames[mode];
    assert.throws(() => selectCountySourceFrame(broken, 'TX', mode), /Unqualified/);
  }
});

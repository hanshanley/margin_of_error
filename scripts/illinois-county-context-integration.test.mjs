import test from 'node:test';
import assert from 'node:assert/strict';
import { loadAdditionalParticipation } from './additional-participation.mjs';
import { qualifiedIllinoisCountyContextFrame, selectCountySourceFrame } from '../public/scripts/participation-geography.js';

test('live-only Illinois context keeps city holds separate and native/official priority intact', () => {
  const frozen = loadAdditionalParticipation();
  assert.equal(frozen.county_frames, undefined);
  const live = loadAdditionalParticipation({ nativeCountyParents: true });
  const data = { counties: live.counties.filter(r => r.state_code === 'IL'),
    county_frames: live.county_frames.IL, county_frame_holds: live.county_frame_holds.IL };
  const frame = selectCountySourceFrame(data, 'IL', 'available');
  assert.equal(frame.length, 102);
  assert.ok(qualifiedIllinoisCountyContextFrame(frame, 'in_person_early'));
  assert.deepEqual(selectCountySourceFrame(data, 'IL', 'official'), data.counties);
  for (const mode of ['in_person_early', 'mail_returned']) {
    assert.equal(data.county_frame_holds[mode].length, 6);
    assert.ok(data.county_frame_holds[mode].every(r => r.contextual_county_fips === null));
  }
  const zero = { state_code: 'IL', ballots: 0 };
  assert.deepEqual(selectCountySourceFrame({ ...data, counties: [zero] }, 'IL', 'available'), [zero]);
  const missingCities = { ...data, county_frame_holds: {} };
  assert.throws(() => selectCountySourceFrame(missingCities, 'IL', 'in_person_early'));
  const wrongCities = structuredClone(data);
  wrongCities.county_frame_holds.in_person_early[0].contextual_county_fips = '17031';
  assert.throws(() => selectCountySourceFrame(wrongCities, 'IL', 'in_person_early'));
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { loadNevadaNativeCounties } from './nevada-native-counties.mjs';
import { qualifiedNevadaCountyFrame, selectCountySourceFrame } from '../public/scripts/participation-geography.js';

test('four native observations preserve different clocks, 13 unknowns and full county context', () => {
  const { counties } = loadNevadaNativeCounties();
  assert.ok(qualifiedNevadaCountyFrame(counties));
  assert.equal(counties.filter(row => row.ballots === null).length, 13);
  assert.equal(new Set(counties.filter(row => row.ballots !== null).map(row => row.source_update_literal)).size, 4);
  assert.ok(counties.every(row => row.reported_pct === null));
  const data = { counties: [], county_frames: { native_county_followup: counties } };
  for (const mode of ['available', 'official'])
    assert.equal(selectCountySourceFrame(data, 'NV', mode), counties);
  for (const mode of ['in_person_early', 'mail_returned'])
    assert.throws(() => selectCountySourceFrame(data, 'NV', mode), /all-method counts are not substituted/);
});

test('Nevada frame rejects candidate counts, missing-as-zero, made-up rates and clock changes', () => {
  const original = loadNevadaNativeCounties().counties;
  for (const [county, replacement] of [
    ['Clark', { ballots: 741970 }], ['Douglas', { ballots: 0 }],
    ['Churchill', { reported_pct: 56.27 }], ['White Pine', { source_update_timezone: 'UTC' }],
    ['Clark', { county_fips: '32005' }], ['Washoe', { source_update_literal: '2026-11-10' }],
  ]) {
    const rows = structuredClone(original);
    Object.assign(rows.find(row => row.county === county), replacement);
    assert.equal(qualifiedNevadaCountyFrame(rows), false);
    assert.throws(() => selectCountySourceFrame({ counties: [], county_frames: {
      native_county_followup: rows } }, 'NV', 'official'), /Unqualified Nevada/);
  }
});

test('Nevada live opt-in retains the frozen Washoe reader and never invents precincts', async () => {
  const { loadAdditionalParticipation } = await import('./additional-participation.mjs');
  const legacy = loadAdditionalParticipation();
  const old = legacy.counties.filter(row => row.state_code === 'NV');
  const live = loadAdditionalParticipation({ nativeCountyParents: true });
  const current = live.counties.filter(row => row.state_code === 'NV');
  assert.equal(old.length, 1);
  assert.equal(current.length, 17);
  const washoe = current.find(row => row.county === 'Washoe');
  assert.equal(washoe.county_id, old[0].county_id);
  assert.equal(washoe.ballots, old[0].ballots);
  assert.equal(washoe.denominator, old[0].denominator);
  assert.equal(washoe.source_status_literal, old[0].source_status_literal);
  assert.equal(washoe.native_printed_pct, old[0].native_printed_pct);
  assert.deepEqual(loadAdditionalParticipation(), legacy);
  assert.deepEqual(live.precincts.filter(row => row.state_code === 'NV'), []);
  for (const mode of ['in_person_early', 'mail_returned'])
    assert.equal(selectCountySourceFrame({ counties: current, county_frames: live.county_frames.NV },
      'NV', mode), live.county_frames.NV[mode]);
});

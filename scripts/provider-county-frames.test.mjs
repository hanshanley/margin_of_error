import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { loadProviderCountyFrames, reviewProviderCountyFrames } from './provider-county-frames.mjs';
import { qualifiedProviderCountyFrame, selectCountySourceFrame } from '../public/scripts/participation-geography.js';

const version = 'data/county-source-reviews/20261109-provider-county-frames-01';
const fixture = () => {
  const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
  const sources = Object.fromEntries(Object.entries(inputs.responses).map(([key, r]) =>
    [key, { native: JSON.parse(readFileSync(r.path, 'utf8')), receipt: r.receipt }]));
  const catalogue = Object.fromEntries(Object.entries(inputs.references).map(([code, r]) =>
    [code, { ...r, identities: JSON.parse(gunzipSync(readFileSync(r.path))).features.map(({ properties: p }) =>
      ({ county: p.name, county_fips: p.key, state_code: p.state_code, boundary_year: p.boundary_year })) }]));
  return { context: JSON.parse(readFileSync(`${version}/source-context.json`, 'utf8')),
    sources, catalogue, completeDownloadUrl: inputs.complete_download_url };
};

test('complete102 frame decisions retain all6371 source regions and approve only63 complete county frames', () => {
  const data = loadProviderCountyFrames();
  assert.equal(data.frame_queries.length, 102);
  assert.equal(data.region_queries.length, 6371);
  assert.equal(data.summary.approved_county_frames, 63);
  assert.equal(data.summary.approved_states, 39);
  assert.equal(data.summary.approved_county_observations, 4731);
  assert.equal(data.county_frames.TX.in_person_early.length, 254);
  assert.equal(data.county_frames.TX.mail_returned.length, 254);
  assert.equal(data.county_frames.DE.mail_returned.length, 3);
  const anderson = data.county_frames.TX.in_person_early.find(r => r.county_fips === '48001');
  assert.equal(anderson.source_count, 9384);
  assert.equal(anderson.source_date, '2026-10-30');
  assert.equal(anderson.native_record.categories.Unspecified.votes, 9384);
  const francis = data.county_frames.AR.mail_returned.find(r => r.county_fips === '05123');
  assert.equal(francis.source_region, 'St Francis');
  for (const row of Object.values(data.county_frames).flatMap(r => Object.values(r)).flat()) {
    assert.equal(row.source_count, Object.values(row.native_record.categories).reduce((s, r) => s + r.votes, 0));
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    assert.equal(row.cast_ballot_count_qualified, false);
    assert.equal(row.unique_voter_count_qualified, false);
    assert.equal(row.native_election_id_qualified, false);
  }
});

test('towns, mixed jurisdictions, partial inventories and absent regions do not become county totals', () => {
  const data = loadProviderCountyFrames();
  for (const code of ['AK', 'CT', 'HI', 'IL', 'ME', 'MO', 'RI', 'VT'])
    assert.equal(data.county_frames[code], undefined);
  assert.ok(data.region_queries.filter(r => !r.county_frame_approved).every(r => r.county_fips === null));
  const absent = data.frame_queries.find(r => r.state_code === 'MA' && r.mode === 'mail_returned');
  assert.equal(absent.source_count, null);
  const zero = data.frame_queries.find(r => r.state_code === 'VT' && r.mode === 'in_person_early');
  assert.equal(zero.source_count, 0);
  assert.equal(zero.disposition, 'state_only_no_region_counts');
  const raw = fixture();
  delete raw.sources['TX-inperson'].native.regions.Anderson;
  const changed = reviewProviderCountyFrames(raw);
  assert.equal(changed.county_frames.TX.in_person_early, undefined);
  assert.equal(changed.frame_queries.find(r => r.state_code === 'TX' && r.mode === 'in_person_early')
    .county_frame_approved, false);
});

test('native zero counts survive, but missing counts or invented election context are rejected', () => {
  const data = fixture(), native = data.sources['DE-returned'].native;
  for (const [category, bucket] of Object.entries(native.regions.Kent)) {
    native.statewide_total[category].votes -= bucket.votes;
    bucket.votes = 0;
  }
  const result = reviewProviderCountyFrames(data);
  assert.equal(result.county_frames.DE.mail_returned.find(r => r.source_region === 'Kent').source_count, 0);
  for (const change of [
    x => x.sources['DE-returned'].native.regions.Kent.Democratic.votes = null,
    x => x.sources['TX-inperson'].native.snapshot_date = '2024-10-30',
    x => x.context.native_election_id_qualified = true,
    x => x.context.rates_approved = true,
    x => x.catalogue.TX.identities[0].state_code = 'CA',
  ]) {
    const raw = fixture();
    change(raw);
    assert.throws(() => reviewProviderCountyFrames(raw));
  }
});

test('browser mode selection preserves native observations and never substitutes full counts for a broken activity frame', () => {
  const provider = loadProviderCountyFrames();
  const imported = row => ({ ...row, ballots: row.source_count, source_mode: row.mode,
    county_id: `additional:${row.state_code}:${row.county_fips}` });
  for (const [code, frames] of Object.entries(provider.county_frames))
    for (const [mode, rows] of Object.entries(frames))
      assert.equal(qualifiedProviderCountyFrame(rows.map(imported), code, mode), true);
  const data = { counties: [], county_frames: Object.fromEntries(
    Object.entries(provider.county_frames.TX).map(([mode, rows]) => [mode, rows.map(imported)])) };
  assert.equal(selectCountySourceFrame(data, 'TX', 'available'), data.county_frames.in_person_early);
  assert.equal(selectCountySourceFrame(data, 'TX', 'mail_returned'), data.county_frames.mail_returned);
  assert.equal(selectCountySourceFrame(data, 'TX', 'official'), data.counties);
  for (const value of [1392280, 0]) {
    const native = [{ state_code: 'TX', ballots: value }];
    assert.equal(selectCountySourceFrame({ ...data, counties: native }, 'TX', 'available'), native);
  }
  for (const change of [
    x => delete x.county_frames.mail_returned,
    x => x.county_frames.mail_returned.pop(),
    x => x.county_frames.mail_returned[0].ballots++,
    x => x.county_frames.mail_returned[0].reported_pct = 1,
    x => x.county_frames.mail_returned[0].native_election_id_qualified = true,
  ]) {
    const changed = structuredClone(data);
    change(changed);
    assert.throws(() => selectCountySourceFrame(changed, 'TX', 'mail_returned'));
  }
});

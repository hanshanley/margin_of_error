import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { loadIllinoisCountyContext, reviewIllinoisCountyContext } from './illinois-county-context.mjs';
import { qualifiedIllinoisCountyContextFrame, qualifiedIllinoisCountyContextReference,
  selectCountySourceFrame } from '../public/scripts/participation-geography.js';

const version = 'data/county-source-reviews/20261110-illinois-county-context-01';
const fixture = () => {
  const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
  return { inputs, reference: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))),
    sources: Object.fromEntries(Object.entries(inputs.responses).map(([category, row]) =>
      [category, { native: JSON.parse(readFileSync(row.path, 'utf8')), receipt: row.receipt }])) };
};

test('all216 source and204 reference decisions retain102 contextual rows and6 unallocated cities per mode', () => {
  const data = loadIllinoisCountyContext();
  assert.equal(data.source_queries.length, 216);
  assert.equal(data.reference_queries.length, 204);
  assert.equal(data.frame_queries.length, 2);
  for (const [mode, mapped] of Object.entries(data.county_context_frames)) {
    assert.equal(mapped.length, 102);
    assert.equal(new Set(mapped.map(r => r.contextual_county_fips)).size, 102);
    const held = data.held_city_regions[mode];
    assert.equal(held.length, 6);
    assert.ok(held.every(r => r.contextual_county_fips === null));
    const frame = data.frame_queries.find(r => r.mode === mode);
    assert.equal(frame.contextual_region_count_sum + frame.held_city_count_sum, frame.native_parent_source_count);
    for (const row of mapped) {
      assert.equal(row.whole_county_count_qualified, false);
      assert.equal(row.source_authority_territory_qualified, false);
      assert.equal(row.native_geography_id_qualified, false);
      assert.equal(row.denominator, null);
      assert.equal(row.reported_pct, null);
      assert.equal(row.ballots, Object.values(row.native_record.categories).reduce((s, r) => s + r.votes, 0));
    }
  }
});

test('Chicago is neither assigned by elimination nor added into the Cook source-region value', () => {
  const data = loadIllinoisCountyContext();
  const f = fixture();
  for (const [category, mode] of [['inperson', 'in_person_early'], ['returned', 'mail_returned']]) {
    const native = f.sources[category].native;
    const cook = data.county_context_frames[mode].find(r => r.county === 'Cook');
    assert.equal(cook.ballots, native.regions.Cook.Unspecified.votes);
    assert.notEqual(cook.ballots, native.regions.Cook.Unspecified.votes
      + native.regions['City of Chicago'].Unspecified.votes);
    assert.equal(data.held_city_regions[mode].find(r => r.source_region === 'City of Chicago').contextual_county_fips, null);
  }
});

test('native zero and raw unknown categories survive without inferring an electorate or full-county count', () => {
  const f = fixture(), native = f.sources.inperson.native;
  native.regions['City of Chicago'].Unspecified.votes += native.regions.Adams.Unspecified.votes;
  native.regions.Adams.Unspecified.votes = 0;
  for (const row of Object.values(native.regions)) row.Unknown = { votes: 0, color: '#999999' };
  native.statewide_total.Unknown = { votes: 0, color: '#999999' };
  const data = reviewIllinoisCountyContext(f);
  const zero = data.county_context_frames.in_person_early.find(r => r.county === 'Adams');
  assert.equal(zero.ballots, 0);
  assert.deepEqual(zero.native_record.categories.Unknown, { votes: 0, color: '#999999' });
  assert.equal(zero.denominator, null);
  assert.equal(zero.whole_county_count_qualified, false);
});

test('missing cells, wrong frames, category-parent failures and authority/full-county promotion reject', () => {
  for (const mutate of [
    f => f.sources.inperson.native.regions.Adams.Unspecified.votes = null,
    f => f.sources.returned.native.statewide_total.Unspecified.votes++,
    f => f.sources.inperson.native.snapshot_date = '2024-11-04',
    f => f.inputs.whole_county_counts_qualified = true,
    f => f.inputs.authority_territories_qualified = true,
    f => f.inputs.native_election_id_qualified = true,
    f => f.inputs.reference.boundary_year = 2024,
    f => f.reference.features[0].properties.key = f.reference.features[1].properties.key,
    f => delete f.sources.inperson.native.regions['City of Chicago'],
    f => f.sources.inperson.receipt.url = 'https://example.invalid/',
  ]) {
    const f = fixture();
    mutate(f);
    assert.throws(() => reviewIllinoisCountyContext(f));
  }
});

test('browser guards reject false whole-county scope, city promotion, bad frames and duplicate references', () => {
  const data = loadIllinoisCountyContext();
  const rows = data.county_context_frames.in_person_early.map(row => ({
    ...row, reference_geometry: data.reference_geometry }));
  const original = fixture().reference, reference = rows[0].reference_geometry;
  assert.ok(qualifiedIllinoisCountyContextReference(rows, reference, original));
  for (const mutate of [
    rows => rows[0].whole_county_count_qualified = true,
    rows => rows[0].source_authority_territory_qualified = true,
    rows => rows[0].native_geography_id_qualified = true,
    rows => rows[0].native_record.source_region = rows[0].county = 'City of Chicago',
    rows => rows[0].ballots = null,
    rows => rows[0].reported_pct = 50,
    rows => rows[0].denominator = 10,
  ]) {
    const changed = structuredClone(rows);
    mutate(changed);
    assert.equal(qualifiedIllinoisCountyContextFrame(changed, 'in_person_early'), false);
  }
  const changed = structuredClone(original);
  changed.features[0].properties.key = changed.features[1].properties.key;
  assert.equal(qualifiedIllinoisCountyContextReference(rows, reference, changed), false);
  assert.throws(() => selectCountySourceFrame({ counties: [], county_frames: {} }, 'IL', 'mail_returned'));
});

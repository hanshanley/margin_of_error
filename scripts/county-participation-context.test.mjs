import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { contextualCountyRows } from '../public/scripts/participation-county-context.js';
import { createCountyContextReview, loadCountyContextReview } from './build-county-participation-context.mjs';
import { loadAdditionalParticipation } from './additional-participation.mjs';
import { loadReviewedCountyParticipation } from './reviewed-county-participation.mjs';

const root = new URL('../public/participation-county-context/20261106-08/', import.meta.url);
const json = file => JSON.parse(readFileSync(new URL(file, root), 'utf8'));
const compressed = file => JSON.parse(gunzipSync(readFileSync(new URL(file, root))));
const review = json('review.json');
const records = compressed('complete-source-records.json.gz');
const inventories = Object.fromEntries(['2024', '2026'].map(year =>
  [year, compressed(`complete-${year}-county-identities.json.gz`)]));
const collections = Object.fromEntries(Object.keys(review.geometry).map(code =>
  [code, json(review.geometry[code].file)]));
const investigation = { geometry_checks: json('geometry-verification.json') };
const copy = value => structuredClone(value);
const match = (rows, candidateReview = review, code = 'AL', collection = collections[code]) =>
  contextualCountyRows(rows, candidateReview, collection, code, review.context_base_url, review.geometry[code].file);

test('complete county review reproduces without changing any source observations or withheld rates', () => {
  const liveRecords = [...loadAdditionalParticipation().counties,
    ...loadReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)];
  assert.deepEqual(records, liveRecords);
  assert.deepEqual(createCountyContextReview(records, inventories, collections, investigation), review);
  assert.deepEqual(review.counts, { complete_source_records: 911, contextual_joins: 439, jurisdictions: 15,
    reviewed_rates: 66, missing_rates: 373, excluded_municipalities: 286, excluded_missing_county_totals: 186 });
  assert.ok(review.observations.every(row => row.source_map_approval_unchanged === false));
});

test('independent joins use each entire unchanged record and exact contextual geometry', async () => {
  let joined = 0, rates = 0;
  for (const code of Object.keys(collections)) {
    const matches = await match(records.filter(row => row.state_code === code), review, code);
    joined += matches.size;
    for (const [geoid, row] of matches) {
      assert.equal(row.maps_approved, false);
      assert.equal(review.observations.find(item => item.contextual_geoid === geoid).reported_pct, row.reported_pct);
      if (row.reported_pct !== null) rates++;
    }
  }
  assert.equal(joined, 439); assert.equal(rates, 66);
  assert.equal((await match(records.filter(row => ['VT', 'RI', 'MN', 'ND', 'ID', 'MI'].includes(row.state_code)))).size, 0);
  const nj = await match(records.filter(row => row.state_code === 'NJ'), review, 'NJ');
  assert.equal(nj.size, 19);
  assert.equal([...nj.values()].filter(row => row.reported_pct === null && row.denominator === null).length, 18);
  assert.equal(nj.get('34009').county, 'Cape May');
});

test('preserves the full previous immutable query while independently joining Jefferson', async () => {
  const previous = new URL('../public/participation-county-context/20261106-01/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => ['pennsylvania-jefferson-20261106-01', 'pennsylvania-clarion-20261106-01',
    'pennsylvania-cameron-20261106-01', 'pennsylvania-carbon-20261106-01',
    'pennsylvania-elk-20261106-01', 'pennsylvania-forest-20261106-01',
    'pennsylvania-potter-20261106-01', 'pennsylvania-mifflin-20261106-01',
    'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(review.geometry, oldReview.geometry);
  const joined = await match(records.filter(row => row.state_code === 'PA'), review, 'PA');
  const jefferson = joined.get('42065');
  assert.equal(jefferson.county, 'Jefferson');
  assert.equal(jefferson.ballots, 15205);
  assert.equal(jefferson.denominator, 28226);
  assert.equal(jefferson.reported_pct, 100 * 15205 / 28226);
  assert.equal(jefferson.maps_approved, false);
  assert.deepEqual(loadCountyContextReview(records).counts, review.counts);
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('preserves every full context02 record and approval while independently joining Clarion', async () => {
  const previous = new URL('../public/participation-county-context/20261106-02/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => ['pennsylvania-clarion-20261106-01', 'pennsylvania-cameron-20261106-01',
    'pennsylvania-carbon-20261106-01', 'pennsylvania-elk-20261106-01',
    'pennsylvania-forest-20261106-01', 'pennsylvania-potter-20261106-01',
    'pennsylvania-mifflin-20261106-01', 'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(review.geometry, oldReview.geometry);
  const joined = await match(records.filter(row => row.state_code === 'PA'), review, 'PA');
  const clarion = joined.get('42031');
  assert.equal(clarion.county, 'Clarion');
  assert.equal(clarion.ballots, 12975);
  assert.equal(clarion.denominator, 23306);
  assert.equal(clarion.reported_pct, 100 * 12975 / 23306);
  assert.equal(clarion.maps_approved, false);
  assert.equal(clarion.native_record.county_fips, undefined);
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('preserves every full context03 record while independently joining Cameron and Carbon', async () => {
  const previous = new URL('../public/participation-county-context/20261106-03/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => ['pennsylvania-cameron-20261106-01', 'pennsylvania-carbon-20261106-01',
    'pennsylvania-elk-20261106-01', 'pennsylvania-forest-20261106-01',
    'pennsylvania-potter-20261106-01', 'pennsylvania-mifflin-20261106-01',
    'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(review.geometry, oldReview.geometry);
  const joined = await match(records.filter(row => row.state_code === 'PA'), review, 'PA');
  for (const [geoid, county, ballots, denominator] of [
    ['42023', 'Cameron', 1624, 2885], ['42025', 'Carbon', 24840, 45896],
  ]) {
    const row = joined.get(geoid);
    assert.equal(row.county, county);
    assert.equal(row.ballots, ballots);
    assert.equal(row.denominator, denominator);
    assert.equal(row.reported_pct, 100 * ballots / denominator);
    assert.equal(row.maps_approved, false);
    assert.equal(row.native_record.county_fips, undefined);
  }
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('preserves every full context04 record while independently joining Elk and Forest', async () => {
  const previous = new URL('../public/participation-county-context/20261106-04/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => ['pennsylvania-elk-20261106-01', 'pennsylvania-forest-20261106-01',
    'pennsylvania-potter-20261106-01', 'pennsylvania-mifflin-20261106-01',
    'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(review.geometry, oldReview.geometry);
  const joined = await match(records.filter(row => row.state_code === 'PA'), review, 'PA');
  for (const [geoid, county, ballots, denominator] of [
    ['42047', 'Elk', 11742, 20533], ['42053', 'Forest', 1877, 3275],
  ]) {
    const row = joined.get(geoid);
    assert.equal(row.county, county);
    assert.equal(row.ballots, ballots);
    assert.equal(row.denominator, denominator);
    assert.equal(row.reported_pct, 100 * ballots / denominator);
    assert.equal(row.maps_approved, false);
    assert.equal(row.native_record.county_fips, undefined);
  }
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('preserves every full context05 record while independently joining Potter', async () => {
  const previous = new URL('../public/participation-county-context/20261106-05/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => ['pennsylvania-potter-20261106-01', 'pennsylvania-mifflin-20261106-01',
    'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(review.geometry, oldReview.geometry);
  const row = (await match(records.filter(item => item.state_code === 'PA'), review, 'PA')).get('42105');
  assert.equal(row.county, 'Potter');
  assert.equal(row.ballots, 6244);
  assert.equal(row.denominator, 11041);
  assert.equal(row.reported_pct, 100 * 6244 / 11041);
  assert.equal(row.maps_approved, false);
  assert.equal(row.native_record.county_fips, undefined);
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('preserves every full context06 record and joins Mifflin without creating a rate from native zero registrations', async () => {
  const previous = new URL('../public/participation-county-context/20261106-06/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => ['pennsylvania-mifflin-20261106-01', 'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(review.geometry, oldReview.geometry);
  const row = (await match(records.filter(item => item.state_code === 'PA'), review, 'PA')).get('42087');
  assert.equal(row.county, 'Mifflin');
  assert.equal(row.ballots, 14439);
  assert.equal(row.denominator, null);
  assert.equal(row.reported_pct, null);
  assert.equal(row.native_record.registered_voters, '0');
  assert.equal(row.native_printed_pct, '0.00%');
  assert.equal(row.maps_approved, false);
  assert.equal(row.native_record.county_fips, undefined);
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('preserves every full context07 record while independently joining Perry without native FIPS or inferred ballot modes', async () => {
  const previous = new URL('../public/participation-county-context/20261106-07/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => row.review_id === 'pennsylvania-perry-20261106-01';
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(review.geometry, oldReview.geometry);
  const row = (await match(records.filter(item => item.state_code === 'PA'), review, 'PA')).get('42099');
  assert.equal(row.county, 'Perry');
  assert.equal(row.ballots, 18064);
  assert.equal(row.denominator, 31391);
  assert.equal(row.reported_pct, 100 * 18064 / 31391);
  assert.equal(row.native_printed_pct, '57.55%');
  assert.equal(row.native_record.native_fips, '');
  assert.equal(row.maps_approved, false);
  assert.equal(row.native_record.provisional_ballots, '');
  assert.equal(row.native_record.source_status_literal, '');
  assert.equal(row.source_status_literal, 'Unofficial');
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('publication refuses changed, missing or duplicated source records rather than reusing old approvals', () => {
  const changed = copy(records); changed[0].ballots++;
  assert.throws(() => loadCountyContextReview(changed), /complete current source records/);
  assert.throws(() => loadCountyContextReview(records.slice(1)), /complete current source records/);
  assert.throws(() => loadCountyContextReview([...records.slice(1), records[1]]), /complete current source records/);
});

test('changed native facts, source identity or counting metadata invalidate only that join', async () => {
  const rows = records.filter(row => row.state_code === 'AL');
  const changes = [
    row => { row.ballots++; },
    row => { row.denominator++; },
    row => { row.source_url += '?different-source'; },
    row => { row.review_id = 'unreviewed'; },
    row => { row.native_record = { ...row.native_record, injected_count: 7 }; },
    row => { row.source_update_label = 'changed'; },
    row => { row.geography_level = 'municipality'; },
    row => { row.maps_approved = true; },
  ];
  for (const change of changes) {
    const changed = copy(rows); change(changed[0]);
    assert.equal((await match(changed)).size, rows.length - 1);
  }
  assert.equal((await match(rows)).size, rows.length);
});

test('ambiguous records, duplicate join targets and changed contextual geometry fail closed', async () => {
  const rows = records.filter(row => row.state_code === 'AL');
  assert.equal((await match([...rows, rows[0]])).size, rows.length - 1);
  const duplicated = copy(review);
  duplicated.observations.push(copy(duplicated.observations[0]));
  assert.equal((await match(rows, duplicated)).size, 0);
  const changed = copy(collections.AL); changed.features[0].properties.key = '01000';
  assert.equal((await match(rows, review, 'AL', changed)).size, 0);
  assert.equal((await contextualCountyRows(rows, review, collections.AL, 'AL',
    '/different-context/', review.geometry.AL.file)).size, 0);
});

test('review creation rejects current identity conflicts, duplicate sources and ambiguous official aliases', () => {
  const changed = copy(inventories); changed['2026'][0].NAME += ' changed';
  assert.throws(() => createCountyContextReview(records, changed, collections, investigation), /identities disagree/);
  assert.throws(() => createCountyContextReview([...records, records[0]], inventories, collections, investigation), /duplicate whole-county/);
  const ambiguous = copy(collections);
  ambiguous.AL.features[1].properties.aliases.push(records[0].county);
  assert.throws(() => createCountyContextReview(records, inventories, ambiguous, investigation), /ambiguous county join/);
});

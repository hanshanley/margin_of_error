import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { contextualCountyRows } from '../public/scripts/participation-county-context.js';
import { createCountyContextReview, loadCountyContextReview } from './build-county-participation-context.mjs';
import { loadAdditionalParticipation } from './additional-participation.mjs';
import { loadReviewedCountyParticipation } from './reviewed-county-participation.mjs';

const root = new URL('../public/participation-county-context/20261106-02/', import.meta.url);
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
  assert.deepEqual(review.counts, { complete_source_records: 903, contextual_joins: 431, jurisdictions: 15,
    reviewed_rates: 59, missing_rates: 372, excluded_municipalities: 286, excluded_missing_county_totals: 186 });
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
  assert.equal(joined, 431); assert.equal(rates, 59);
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
  const isNew = row => row.review_id === 'pennsylvania-jefferson-20261106-01';
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

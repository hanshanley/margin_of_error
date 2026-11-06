import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { contextualCountyRows } from '../public/scripts/participation-county-context.js';
import { createCountyContextReview, loadCountyContextReview } from './build-county-participation-context.mjs';
import { loadAdditionalParticipation } from './additional-participation.mjs';
import { loadReviewedCountyParticipation as loadCompleteReviewedCountyParticipation, loadReviewedMinnesotaParticipation } from './reviewed-county-participation.mjs';

const utahId = 'utah-ballot-statistics-20261106-01';
const loadCurrentReviewedCountyParticipation = reviews =>
  loadCompleteReviewedCountyParticipation(reviews).filter(row => row.review_id !== utahId);
const newCountyIds = ['pennsylvania-bedford-20261106-01', 'pennsylvania-northumberland-20261106-01'];
const loadAllReviewedCountyParticipation = reviews =>
  loadCurrentReviewedCountyParticipation(reviews).filter(row => !newCountyIds.includes(row.review_id));
const additionalId = 'pennsylvania-three-additional-summaries-20261106-01';
const somersetId = 'pennsylvania-somerset-20261106-01';
const susquehannaId = 'pennsylvania-susquehanna-20261106-01';
const sullivanWyomingId = 'pennsylvania-sullivan-wyoming-20261106-01';
const loadReviewedCountyParticipation = reviews =>
  loadAllReviewedCountyParticipation(reviews).filter(row =>
    ![additionalId, somersetId, susquehannaId, sullivanWyomingId].includes(row.review_id));

const root = new URL('../public/participation-county-context/20261106-14/', import.meta.url);
const batchIds = ['pennsylvania-lycoming-20261106-01', 'georgia-bulk-participation-20261106-01', 'pennsylvania-greene-20261106-01', 'pennsylvania-columbia-20261106-01', 'california-bulk-participation-20261106-01', 'pennsylvania-juniata-20261106-01', 'pennsylvania-mercer-20261106-01',
  'pennsylvania-montour-20261106-01'];
const json = file => JSON.parse(readFileSync(new URL(file, root), 'utf8'));
const compressed = file => JSON.parse(gunzipSync(readFileSync(new URL(file, root))));
const review = json('review.json');
const geometryBeforeGeorgia = Object.fromEntries(Object.entries(review.geometry).filter(([code]) => code !== 'GA'));
const previousGeometry = Object.fromEntries(Object.entries(geometryBeforeGeorgia).filter(([code]) => code !== 'CA'));
const records = compressed('complete-source-records.json.gz');
const inventories = Object.fromEntries(['2024', '2026'].map(year =>
  [year, compressed(`complete-${year}-county-identities.json.gz`)]));
const collections = Object.fromEntries(Object.keys(review.geometry).map(code =>
  [code, json(review.geometry[code].file)]));
const investigation = { geometry_checks: json('geometry-verification.json') };
const copy = value => structuredClone(value);
const match = (rows, candidateReview = review, code = 'AL', collection = collections[code]) =>
  contextualCountyRows(rows, candidateReview, collection, code, review.context_base_url, review.geometry[code].file);

function floridaSelectionFixture() {
  const directory = new URL('../public/participation-county-context/20261106-23/', import.meta.url);
  const prior = JSON.parse(readFileSync(new URL('review.json', directory)));
  const previous = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', directory))));
  const qualification = JSON.parse(readFileSync(
    'data/county-source-reviews/20261106-florida-consolidated-explorer-01/county-usability-review.json'));
  return {
    prior, previous, records: [...previous, ...qualification.current_source_records],
    collections: Object.fromEntries(Object.keys(prior.geometry).map(code =>
      [code, JSON.parse(readFileSync(new URL(prior.geometry[code].file, directory)))])),
    investigation: { geometry_checks: JSON.parse(readFileSync(new URL('geometry-verification.json', directory))) },
  };
}

test('Florida selects one reconciled Monroe source without losing any complete historical record', async () => {
  const fixture = floridaSelectionFixture();
  const original = copy(fixture.records);
  const next = createCountyContextReview(fixture.records, inventories, fixture.collections, fixture.investigation);
  assert.deepEqual(fixture.records, original);
  assert.deepEqual(fixture.records.slice(0, fixture.previous.length), fixture.previous);
  assert.deepEqual(next.counts, { complete_source_records: 1328, contextual_joins: 833, jurisdictions: 19,
    reviewed_rates: 446, missing_rates: 387, excluded_municipalities: 286, excluded_missing_county_totals: 208,
    retained_duplicate_source_observations: 1 });
  assert.deepEqual(next.geometry, fixture.prior.geometry);
  assert.deepEqual(next.observations.filter(row => row.state_code !== 'FL'),
    fixture.prior.observations.filter(row => row.state_code !== 'FL'));
  assert.deepEqual(next.excluded.filter(row => row.state_code !== 'FL'), fixture.prior.excluded);
  assert.equal(next.observations.filter(row => row.contextual_geoid === '12087').length, 1);
  assert.equal(next.observations.filter(row => row.state_code === 'FL').length, 67);
  assert.equal(next.source_selections.length, 1);
  assert.equal(next.source_selections[0].retained_source_record_sha256,
    fixture.prior.observations.find(row => row.state_code === 'FL').source_record_sha256);
  const retained = next.excluded.find(row => row.county_id === 'additional:FL:12087');
  assert.match(retained.reason, /Retained duplicate source observation/);
  assert.equal(retained.source_record_sha256, next.source_selections[0].retained_source_record_sha256);
  const mapped = await contextualCountyRows(fixture.records.filter(row => row.state_code === 'FL'),
    next, fixture.collections.FL, 'FL', next.context_base_url, next.geometry.FL.file);
  assert.equal(mapped.size, 67);
  assert.equal(mapped.get('12087').county_id, 'reviewed:FL:Monroe');
  assert.equal(mapped.get('12087').reported_pct, 100 * 32506 / 54704);
});

test('Florida rejects a changed retained source or an unreconciled statewide Monroe observation', () => {
  for (const [id, field, value] of [
    ['additional:FL-2026-MON', 'reported_pct', 59.42],
    ['florida-consolidated-turnout-20261106-01', 'ballots', 32507],
    ['florida-consolidated-turnout-20261106-01', 'denominator', 54705],
    ['florida-consolidated-turnout-20261106-01', 'native_printed_pct', '59.43%'],
    ['florida-consolidated-turnout-20261106-01', 'reported_pct', null],
  ]) {
    const fixture = floridaSelectionFixture();
    fixture.records.find(row => row.review_id === id && row.county === 'Monroe')[field] = value;
    assert.throws(() => createCountyContextReview(fixture.records, inventories,
      fixture.collections, fixture.investigation), /Unreconciled retained Monroe source/);
  }
});

test('context22 preserves every prior record, join, exclusion and geometry while adding only two county fractions', async () => {
  const nextRoot = new URL('../public/participation-county-context/20261106-22/', import.meta.url);
  const priorRoot = new URL('../public/participation-county-context/20261106-21/', import.meta.url);
  const next = JSON.parse(readFileSync(new URL('review.json', nextRoot)));
  const prior = JSON.parse(readFileSync(new URL('review.json', priorRoot)));
  const nextRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', nextRoot))));
  const priorRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', priorRoot))));
  const current = [...loadAdditionalParticipation().counties,
    ...loadCurrentReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)];
  assert.deepEqual(nextRecords, current);
  assert.deepEqual(nextRecords.filter(row => !newCountyIds.includes(row.review_id)), priorRecords);
  assert.deepEqual(next.observations.filter(row => !newCountyIds.includes(row.review_id)), prior.observations);
  assert.deepEqual(next.excluded, prior.excluded);
  assert.deepEqual(next.geometry, prior.geometry);
  for (const entry of Object.values(prior.geometry))
    assert.deepEqual(readFileSync(new URL(entry.file, nextRoot)), readFileSync(new URL(entry.file, priorRoot)));
  assert.deepEqual(next.counts, { complete_source_records: 1232, contextual_joins: 748, jurisdictions: 18,
    reviewed_rates: 361, missing_rates: 387, excluded_municipalities: 286, excluded_missing_county_totals: 198 });
  const collection = JSON.parse(readFileSync(new URL(next.geometry.PA.file, nextRoot)));
  const rows = await contextualCountyRows(current.filter(row => row.state_code === 'PA'), next,
    collection, 'PA', next.context_base_url, next.geometry.PA.file);
  for (const [geoid, county, ballots, denominator] of [
    ['42009', 'Bedford', 19041, 33079], ['42097', 'Northumberland', 28341, 55540],
  ]) {
    const row = rows.get(geoid);
    assert.equal(row.county, county);
    assert.equal(row.ballots, ballots);
    assert.equal(row.denominator, denominator);
    assert.equal(row.reported_pct, 100 * ballots / denominator);
    assert.equal(row.maps_approved, false);
    assert.equal(row.native_record.native_fips, '');
    assert.equal(row.native_record.analysis_rate_approved, 'False');
    assert.equal(next.observations.find(row => row.contextual_geoid === geoid).boundary_year, 2024);
  }
  const publication = JSON.parse(readFileSync(
    'data/county-source-reviews/20261106-bedford-northumberland-explorer-01/context22-published-verification.json'));
  assert.equal(publication.immutable, true);
  assert.equal(publication.all_32_files_reproduce_exactly, true);
  assert.equal(publication.entire_assets.length, 4);
  assert.equal(publication.commit_pinned_files.length, 32);
  assert.throws(() => loadCountyContextReview(priorRecords), /complete current source records/);
});

test('context23 retains all context22 records and joins only the 19 qualified Utah counted snapshots', async () => {
  const directory = new URL('../public/participation-county-context/20261106-23/', import.meta.url);
  const priorDirectory = new URL('../public/participation-county-context/20261106-22/', import.meta.url);
  const next = JSON.parse(readFileSync(new URL('review.json', directory)));
  const prior = JSON.parse(readFileSync(new URL('review.json', priorDirectory)));
  const current = [...loadAdditionalParticipation().counties,
    ...loadCompleteReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)];
  assert.deepEqual(JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', directory)))), current);
  assert.deepEqual(current.filter(row => row.review_id !== utahId),
    JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', priorDirectory)))));
  assert.deepEqual(next.observations.filter(row => row.review_id !== utahId), prior.observations);
  assert.deepEqual(next.excluded.filter(row => row.state_code !== 'UT'), prior.excluded);
  for (const [code, geometry] of Object.entries(prior.geometry)) {
    assert.deepEqual(next.geometry[code], geometry);
    assert.deepEqual(readFileSync(new URL(geometry.file, directory)), readFileSync(new URL(geometry.file, priorDirectory)));
  }
  assert.deepEqual(next.counts, { complete_source_records: 1261, contextual_joins: 767, jurisdictions: 19,
    reviewed_rates: 379, missing_rates: 388, excluded_municipalities: 286, excluded_missing_county_totals: 208 });
  assert.equal(next.excluded.filter(row => row.state_code === 'UT' && /scope withheld/.test(row.reason)).length, 6);
  assert.equal(next.excluded.filter(row => row.state_code === 'UT' && /no declared/.test(row.reason)).length, 4);
  const loaded = loadCountyContextReview(current);
  assert.deepEqual(loaded.coverage.UT, { counties: 19, rates: 18 });
  assert.deepEqual(loaded.coverage.PA, { counties: 43, rates: 40 });
  assert.equal(loaded.base_url, '/participation-county-context/20261106-23/');
  const collection = JSON.parse(readFileSync(new URL(next.geometry.UT.file, directory)));
  const matched = await contextualCountyRows(current.filter(row => row.state_code === 'UT'), next,
    collection, 'UT', next.context_base_url, next.geometry.UT.file);
  assert.equal(matched.size, 19);
  assert.equal(matched.get('49011').ballots, 115308);
  assert.equal(matched.get('49003').reported_pct, null);
  assert.equal(matched.has('49005'), false);
  assert.equal(matched.has('49009'), false);
});

test('Sullivan/Wyoming context21 preserves all context20 records, joins, exclusions and geometry', async () => {
  const nextRoot = new URL('../public/participation-county-context/20261106-21/', import.meta.url);
  const priorRoot = new URL('../public/participation-county-context/20261106-20/', import.meta.url);
  const next = JSON.parse(readFileSync(new URL('review.json', nextRoot)));
  const prior = JSON.parse(readFileSync(new URL('review.json', priorRoot)));
  const nextRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', nextRoot))));
  const priorRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', priorRoot))));
  const live = [...loadAdditionalParticipation().counties,
    ...loadAllReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)];
  assert.deepEqual(nextRecords, live);
  assert.deepEqual(nextRecords.filter(row => row.review_id !== sullivanWyomingId), priorRecords);
  assert.deepEqual(next.observations.filter(row => row.review_id !== sullivanWyomingId), prior.observations);
  assert.deepEqual(next.excluded, prior.excluded);
  assert.deepEqual(next.geometry, prior.geometry);
  for (const entry of Object.values(prior.geometry))
    assert.deepEqual(readFileSync(new URL(entry.file, nextRoot)), readFileSync(new URL(entry.file, priorRoot)));
  assert.throws(() => loadCountyContextReview(live), /complete current source records/);
  assert.deepEqual(next.counts, { complete_source_records: 1230, contextual_joins: 746, jurisdictions: 18,
    reviewed_rates: 359, missing_rates: 387, excluded_municipalities: 286, excluded_missing_county_totals: 198 });
  const collection = JSON.parse(readFileSync(new URL(next.geometry.PA.file, nextRoot)));
  const rows = await contextualCountyRows(live.filter(row => row.state_code === 'PA'), next,
    collection, 'PA', next.context_base_url, next.geometry.PA.file);
  for (const [geoid, county, ballots, denominator] of [
    ['42113', 'Sullivan', 2712, 4501], ['42131', 'Wyoming', 10542, 18565],
  ]) {
    const row = rows.get(geoid);
    assert.equal(row.county, county);
    assert.equal(row.reported_pct, 100 * ballots / denominator);
    assert.equal(row.maps_approved, false);
    assert.equal(row.native_record.source_fips, '');
    assert.equal(row.native_record.analysis_rate_approved, 'False');
    assert.equal(row.native_record.native_timezone, '');
    assert.equal(next.observations.find(row => row.contextual_geoid === geoid).boundary_year, 2024);
  }
  const publication = JSON.parse(readFileSync(
    'data/county-source-reviews/20261106-sullivan-wyoming-explorer-01/context21-published-verification.json'));
  assert.equal(publication.immutable, true);
  assert.equal(publication.all_32_files_reproduce_exactly, true);
  assert.equal(publication.entire_assets.length, 4);
  assert.equal(publication.commit_pinned_files.length, 32);
  assert.throws(() => loadCountyContextReview(priorRecords), /complete current source records/);
});

test('Susquehanna context20 preserves every context19 record, join, exclusion and complete geometry', async () => {
  const nextRoot = new URL('../public/participation-county-context/20261106-20/', import.meta.url);
  const priorRoot = new URL('../public/participation-county-context/20261106-19/', import.meta.url);
  const next = JSON.parse(readFileSync(new URL('review.json', nextRoot)));
  const prior = JSON.parse(readFileSync(new URL('review.json', priorRoot)));
  const nextRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', nextRoot))));
  const priorRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', priorRoot))));
  const live = [...loadAdditionalParticipation().counties,
    ...loadAllReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)
      .filter(row => row.review_id !== sullivanWyomingId)];
  assert.deepEqual(nextRecords, live);
  assert.deepEqual(nextRecords.filter(row => row.review_id !== susquehannaId), priorRecords);
  assert.deepEqual(next.observations.filter(row => row.review_id !== susquehannaId), prior.observations);
  assert.deepEqual(next.excluded, prior.excluded);
  assert.deepEqual(next.geometry, prior.geometry);
  for (const entry of Object.values(prior.geometry))
    assert.deepEqual(readFileSync(new URL(entry.file, nextRoot)), readFileSync(new URL(entry.file, priorRoot)));
  assert.throws(() => loadCountyContextReview(live), /complete current source records/);
  assert.equal(next.observations.filter(row => row.state_code === 'PA').length, 39);
  assert.equal(next.observations.filter(row => row.state_code === 'PA' && row.reported_pct !== null).length, 36);
  assert.deepEqual(next.counts, { complete_source_records: 1228, contextual_joins: 744, jurisdictions: 18,
    reviewed_rates: 357, missing_rates: 387, excluded_municipalities: 286, excluded_missing_county_totals: 198 });
  const collection = JSON.parse(readFileSync(new URL(next.geometry.PA.file, nextRoot)));
  const rows = await contextualCountyRows(live.filter(row => row.state_code === 'PA'), next,
    collection, 'PA', next.context_base_url, next.geometry.PA.file);
  const row = rows.get('42115');
  assert.equal(row.county, 'Susquehanna');
  assert.equal(row.ballots, 15317);
  assert.equal(row.denominator, 27504);
  assert.equal(row.reported_pct, 100 * 15317 / 27504);
  assert.equal(row.maps_approved, false);
  assert.equal(row.native_record.source_fips, '');
  assert.equal(row.native_record.analysis_rate_approved, 'False');
  assert.equal(next.observations.find(row => row.contextual_geoid === '42115').boundary_year, 2024);
  assert.throws(() => loadCountyContextReview(priorRecords), /complete current source records/);
});

test('Somerset context19 preserves all context18 records, joins, exclusions and geometry', async () => {
  const nextRoot = new URL('../public/participation-county-context/20261106-19/', import.meta.url);
  const priorRoot = new URL('../public/participation-county-context/20261106-18/', import.meta.url);
  const next = JSON.parse(readFileSync(new URL('review.json', nextRoot)));
  const prior = JSON.parse(readFileSync(new URL('review.json', priorRoot)));
  const nextRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', nextRoot))));
  const priorRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', priorRoot))));
  const live = [...loadAdditionalParticipation().counties,
    ...loadAllReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)
      .filter(row => ![susquehannaId, sullivanWyomingId].includes(row.review_id))];
  assert.deepEqual(nextRecords, live);
  assert.deepEqual(nextRecords.filter(row => row.review_id !== somersetId), priorRecords);
  assert.deepEqual(next.observations.filter(row => row.review_id !== somersetId), prior.observations);
  assert.deepEqual(next.excluded, prior.excluded);
  assert.deepEqual(next.geometry, prior.geometry);
  for (const entry of Object.values(prior.geometry))
    assert.deepEqual(readFileSync(new URL(entry.file, nextRoot)), readFileSync(new URL(entry.file, priorRoot)));
  assert.throws(() => loadCountyContextReview(live), /complete current source records/);
  assert.equal(next.observations.filter(row => row.state_code === 'PA').length, 38);
  assert.equal(next.observations.filter(row => row.state_code === 'PA' && row.reported_pct !== null).length, 35);
  assert.deepEqual(next.counts, { complete_source_records: 1227, contextual_joins: 743, jurisdictions: 18,
    reviewed_rates: 356, missing_rates: 387, excluded_municipalities: 286, excluded_missing_county_totals: 198 });
  const collection = JSON.parse(readFileSync(new URL(next.geometry.PA.file, nextRoot)));
  const rows = await contextualCountyRows(live.filter(row => row.state_code === 'PA'), next,
    collection, 'PA', next.context_base_url, next.geometry.PA.file);
  const row = rows.get('42111');
  assert.equal(row.county, 'Somerset');
  assert.equal(row.reported_pct, 100 * 27019 / 48578);
  assert.equal(row.maps_approved, false);
  assert.equal(row.native_record.source_fips, '');
  assert.equal(next.observations.find(row => row.contextual_geoid === '42111').boundary_year, 2024);
  assert.throws(() => loadCountyContextReview(priorRecords), /complete current source records/);
});

test('context18 preserves every context17 record and geometry while joining only the three new county fractions', async () => {
  const nextRoot = new URL('../public/participation-county-context/20261106-18/', import.meta.url);
  const priorRoot = new URL('../public/participation-county-context/20261106-17/', import.meta.url);
  const next = JSON.parse(readFileSync(new URL('review.json', nextRoot)));
  const prior = JSON.parse(readFileSync(new URL('review.json', priorRoot)));
  const nextRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', nextRoot))));
  const priorRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', priorRoot))));
  const live = [...loadAdditionalParticipation().counties,
    ...loadAllReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)
      .filter(row => ![somersetId, susquehannaId, sullivanWyomingId].includes(row.review_id))];
  assert.deepEqual(nextRecords, live);
  assert.deepEqual(nextRecords.filter(row => row.review_id !== additionalId), priorRecords);
  assert.deepEqual(next.observations.filter(row => row.review_id !== additionalId), prior.observations);
  assert.deepEqual(next.excluded, prior.excluded);
  assert.deepEqual(next.geometry, prior.geometry);
  for (const entry of Object.values(prior.geometry))
    assert.deepEqual(readFileSync(new URL(entry.file, nextRoot)), readFileSync(new URL(entry.file, priorRoot)));
  assert.throws(() => loadCountyContextReview(live), /complete current source records/);
  assert.deepEqual(next.counts, { complete_source_records: 1226, contextual_joins: 742, jurisdictions: 18,
    reviewed_rates: 355, missing_rates: 387, excluded_municipalities: 286, excluded_missing_county_totals: 198 });
  const collection = JSON.parse(readFileSync(new URL(next.geometry.PA.file, nextRoot)));
  const rows = await contextualCountyRows(live.filter(row => row.state_code === 'PA'), next,
    collection, 'PA', next.context_base_url, next.geometry.PA.file);
  for (const [geoid, county] of [['42063', 'Indiana'], ['42069', 'Lackawanna'], ['42107', 'Schuylkill']]) {
    const row = rows.get(geoid);
    assert.equal(row.county, county);
    assert.equal(row.reported_pct, 100 * row.ballots / row.denominator);
    assert.equal(row.maps_approved, false);
    assert.equal(row.native_record.source_fips, '');
    assert.equal(next.observations.find(row => row.contextual_geoid === geoid).boundary_year, 2024);
  }
  assert.throws(() => loadCountyContextReview(priorRecords), /complete current source records/);
});

test('Huntingdon context17 preserves context16 and joins only the native registered-voter fraction', async () => {
  const nextRoot = new URL('../public/participation-county-context/20261106-17/', import.meta.url);
  const previousRoot = new URL('../public/participation-county-context/20261106-16/', import.meta.url);
  const next = JSON.parse(readFileSync(new URL('review.json', nextRoot)));
  const previous = JSON.parse(readFileSync(new URL('review.json', previousRoot)));
  const nextRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', nextRoot))));
  const previousRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previousRoot))));
  const id = 'pennsylvania-huntingdon-20261106-01';
  const liveRecords = [...loadAdditionalParticipation().counties,
    ...loadReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)];
  assert.deepEqual(nextRecords, liveRecords);
  assert.deepEqual(nextRecords.filter(row => row.review_id !== id), previousRecords);
  assert.deepEqual(next.observations.filter(row => row.review_id !== id), previous.observations);
  assert.deepEqual(next.excluded, previous.excluded);
  assert.deepEqual(next.geometry, previous.geometry);
  assert.throws(() => loadCountyContextReview(liveRecords), /complete current source records/);
  assert.deepEqual(next.counts, { complete_source_records: 1223, contextual_joins: 739, jurisdictions: 18,
    reviewed_rates: 352, missing_rates: 387, excluded_municipalities: 286, excluded_missing_county_totals: 198 });
  const collection = JSON.parse(readFileSync(new URL(next.geometry.PA.file, nextRoot)));
  const rows = await contextualCountyRows(liveRecords.filter(row => row.state_code === 'PA'), next,
    collection, 'PA', next.context_base_url, next.geometry.PA.file);
  const huntingdon = rows.get('42061');
  assert.equal(huntingdon.county, 'Huntingdon');
  assert.equal(huntingdon.ballots, 16024);
  assert.equal(huntingdon.denominator, 27917);
  assert.equal(huntingdon.reported_pct, 100 * 16024 / 27917);
  assert.equal(huntingdon.maps_approved, false);
  assert.equal(huntingdon.native_record.source_fips, '');
  assert.equal(next.observations.find(row => row.review_id === id).boundary_year, 2024);
  assert.throws(() => loadCountyContextReview(previousRecords), /complete current source records/);
});

test('Lawrence context16 preserves context15 and joins only the reviewed county participation fraction', async () => {
  const nextRoot = new URL('../public/participation-county-context/20261106-16/', import.meta.url);
  const previousRoot = new URL('../public/participation-county-context/20261106-15/', import.meta.url);
  const next = JSON.parse(readFileSync(new URL('review.json', nextRoot)));
  const previous = JSON.parse(readFileSync(new URL('review.json', previousRoot)));
  const nextRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', nextRoot))));
  const previousRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previousRoot))));
  const id = 'pennsylvania-lawrence-20261106-01';
  const liveRecords = [...loadAdditionalParticipation().counties,
    ...loadReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)];
  assert.deepEqual(nextRecords, liveRecords.filter(row => row.review_id !== 'pennsylvania-huntingdon-20261106-01'));
  assert.deepEqual(nextRecords.filter(row => row.review_id !== id), previousRecords);
  assert.deepEqual(next.observations.filter(row => row.review_id !== id), previous.observations);
  assert.deepEqual(next.excluded, previous.excluded);
  assert.deepEqual(next.geometry, previous.geometry);
  assert.throws(() => loadCountyContextReview(nextRecords), /complete current source records/);
  assert.deepEqual(next.counts, { complete_source_records: 1222, contextual_joins: 738, jurisdictions: 18,
    reviewed_rates: 351, missing_rates: 387, excluded_municipalities: 286, excluded_missing_county_totals: 198 });
  const collection = JSON.parse(readFileSync(new URL(next.geometry.PA.file, nextRoot)));
  const rows = await contextualCountyRows(liveRecords.filter(row => row.state_code === 'PA'), next,
    collection, 'PA', next.context_base_url, next.geometry.PA.file);
  const lawrence = rows.get('42073');
  assert.equal(lawrence.county, 'Lawrence');
  assert.equal(lawrence.ballots, 31401);
  assert.equal(lawrence.denominator, 57470);
  assert.equal(lawrence.reported_pct, 100 * 31401 / 57470);
  assert.equal(lawrence.maps_approved, false);
  assert.equal(lawrence.native_record.source_fips, undefined);
  assert.equal(next.observations.find(row => row.review_id === id).boundary_year, 2024);
  assert.throws(() => loadCountyContextReview(previousRecords), /complete current source records/);
});

test('Minnesota context15 preserves every old record and joins only complete native statistics', async () => {
  const nextRoot = new URL('../public/participation-county-context/20261106-15/', import.meta.url);
  const next = JSON.parse(readFileSync(new URL('review.json', nextRoot)));
  const nextRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', nextRoot))));
  const native = loadReviewedMinnesotaParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews);
  assert.deepEqual(nextRecords, [...records, ...native]);
  const liveRecords = [...loadAdditionalParticipation().counties,
    ...loadReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)];
  assert.deepEqual(nextRecords, liveRecords.filter(row => ![
    'pennsylvania-lawrence-20261106-01', 'pennsylvania-huntingdon-20261106-01'].includes(row.review_id)));
  assert.throws(() => loadCountyContextReview(nextRecords), /complete current source records/);
  assert.deepEqual(next.observations.filter(row => row.state_code !== 'MN'), review.observations);
  assert.deepEqual(next.excluded.slice(0, review.excluded.length), review.excluded);
  assert.deepEqual(next.counts, { complete_source_records: 1221, contextual_joins: 737, jurisdictions: 18,
    reviewed_rates: 350, missing_rates: 387, excluded_municipalities: 286, excluded_missing_county_totals: 198 });
  const collection = JSON.parse(readFileSync(new URL(next.geometry.MN.file, nextRoot)));
  const matches = await contextualCountyRows(native, next, collection, 'MN',
    next.context_base_url, next.geometry.MN.file);
  assert.equal(collection.features.length, 87);
  assert.equal(matches.size, 75);
  assert.equal([...matches.values()].filter(row => row.reported_pct !== null).length, 64);
  for (const row of native.filter(row => row.ballots === null)) {
    assert.ok(![...matches.values()].some(match => match.county_id === row.county_id));
    assert.match(next.excluded.find(item => item.county_id === row.county_id).reason,
      /whole-county participation total missing: native statistics are incomplete/);
  }
});

test('complete county review reproduces without changing any source observations or withheld rates', () => {
  const liveRecords = [...loadAdditionalParticipation().counties,
    ...loadReviewedCountyParticipation(JSON.parse(readFileSync('public/participation-source-reviews.json')).reviews)];
  assert.deepEqual(records, liveRecords.filter(row =>
    !['minnesota-bulk-participation-20261106-01', 'pennsylvania-lawrence-20261106-01',
      'pennsylvania-huntingdon-20261106-01'].includes(row.review_id)));
  assert.deepEqual(createCountyContextReview(records, inventories, collections, investigation), review);
  assert.deepEqual(review.counts, { complete_source_records: 1134, contextual_joins: 662, jurisdictions: 17,
    reviewed_rates: 286, missing_rates: 376, excluded_municipalities: 286, excluded_missing_county_totals: 186 });
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
  assert.equal(joined, 662); assert.equal(rates, 286);
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
  const isNew = row => [...batchIds, 'pennsylvania-jefferson-20261106-01', 'pennsylvania-clarion-20261106-01',
    'pennsylvania-cameron-20261106-01', 'pennsylvania-carbon-20261106-01',
    'pennsylvania-elk-20261106-01', 'pennsylvania-forest-20261106-01',
    'pennsylvania-potter-20261106-01', 'pennsylvania-mifflin-20261106-01',
    'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(previousGeometry, oldReview.geometry);
  const joined = await match(records.filter(row => row.state_code === 'PA'), review, 'PA');
  const jefferson = joined.get('42065');
  assert.equal(jefferson.county, 'Jefferson');
  assert.equal(jefferson.ballots, 15205);
  assert.equal(jefferson.denominator, 28226);
  assert.equal(jefferson.reported_pct, 100 * 15205 / 28226);
  assert.equal(jefferson.maps_approved, false);
  assert.throws(() => loadCountyContextReview(records), /complete current source records/);
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('preserves every full context02 record and approval while independently joining Clarion', async () => {
  const previous = new URL('../public/participation-county-context/20261106-02/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => [...batchIds, 'pennsylvania-clarion-20261106-01', 'pennsylvania-cameron-20261106-01',
    'pennsylvania-carbon-20261106-01', 'pennsylvania-elk-20261106-01',
    'pennsylvania-forest-20261106-01', 'pennsylvania-potter-20261106-01',
    'pennsylvania-mifflin-20261106-01', 'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(previousGeometry, oldReview.geometry);
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
  const isNew = row => [...batchIds, 'pennsylvania-cameron-20261106-01', 'pennsylvania-carbon-20261106-01',
    'pennsylvania-elk-20261106-01', 'pennsylvania-forest-20261106-01',
    'pennsylvania-potter-20261106-01', 'pennsylvania-mifflin-20261106-01',
    'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(previousGeometry, oldReview.geometry);
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
  const isNew = row => [...batchIds, 'pennsylvania-elk-20261106-01', 'pennsylvania-forest-20261106-01',
    'pennsylvania-potter-20261106-01', 'pennsylvania-mifflin-20261106-01',
    'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(previousGeometry, oldReview.geometry);
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
  const isNew = row => [...batchIds, 'pennsylvania-potter-20261106-01', 'pennsylvania-mifflin-20261106-01',
    'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(previousGeometry, oldReview.geometry);
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
  const isNew = row => [...batchIds, 'pennsylvania-mifflin-20261106-01', 'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(previousGeometry, oldReview.geometry);
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
  const isNew = row => [...batchIds, 'pennsylvania-perry-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(previousGeometry, oldReview.geometry);
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

test('preserves context08 and independently joins all three county identities without inventing native FIPS', async () => {
  const previous = new URL('../public/participation-county-context/20261106-08/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => batchIds.includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(previousGeometry, oldReview.geometry);
  const joined = await match(records.filter(row => row.state_code === 'PA'), review, 'PA');
  for (const [geoid, county, ballots, registrations] of [
    ['42067', 'Juniata', 8258, 14095], ['42085', 'Mercer', 39121, 72238], ['42093', 'Montour', 7008, 12418],
  ]) {
    const row = joined.get(geoid);
    assert.equal(row.county, county);
    assert.equal(row.ballots, ballots);
    assert.equal(row.reported_pct, 100 * ballots / registrations);
    assert.equal(row.native_record.source_fips, '');
    assert.equal(row.maps_approved, false);
  }
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('preserves context09 while joining all 58 California identities with native participation fractions', async () => {
  const previous = new URL('../public/participation-county-context/20261106-09/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => ['CA', 'GA'].includes(row.state_code)
    || ['pennsylvania-columbia-20261106-01', 'pennsylvania-greene-20261106-01',
      'pennsylvania-lycoming-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(previousGeometry, oldReview.geometry);
  const joined = await match(records.filter(row => row.state_code === 'CA'), review, 'CA');
  assert.equal(joined.size, 58);
  assert.equal([...joined.values()].filter(row => row.reported_pct !== null).length, 58);
  const alameda = joined.get('06001');
  assert.equal(alameda.county, 'Alameda');
  assert.equal(alameda.ballots, 314951);
  assert.equal(alameda.denominator, 983846);
  assert.equal(alameda.participation_measure_literal, 'voterTurnout');
  assert.equal(alameda.native_record.county_fips, '');
  assert.equal(alameda.maps_approved, false);
  assert.equal(review.geometry.CA.boundary_year, 2024);
  assert.equal(review.geometry.CA.simplification_overlap_pairs.length, 43);
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('preserves all context10 facts and geometry while independently joining Columbia', async () => {
  const previous = new URL('../public/participation-county-context/20261106-10/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => ['pennsylvania-columbia-20261106-01', 'pennsylvania-greene-20261106-01', 'pennsylvania-lycoming-20261106-01',
    'georgia-bulk-participation-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(geometryBeforeGeorgia, oldReview.geometry);
  const joined = await match(records.filter(row => row.state_code === 'PA'), review, 'PA');
  const row = joined.get('42037');
  assert.equal(row.county, 'Columbia');
  assert.equal(row.ballots, 22583);
  assert.equal(row.reported_pct, 100 * 22583 / 40797);
  assert.equal(row.native_record.source_fips, '');
  assert.equal(row.maps_approved, false);
  assert.equal(row.native_source_updates[0].declared_timezone, 'EST');
  assert.equal(row.native_source_updates[1].native_update_literal, '');
});

test('preserves context11 and joins Greene without promoting missing turnout or native geography', async () => {
  const previous = new URL('../public/participation-county-context/20261106-11/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => ['pennsylvania-greene-20261106-01', 'pennsylvania-lycoming-20261106-01',
    'georgia-bulk-participation-20261106-01'].includes(row.review_id);
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(geometryBeforeGeorgia, oldReview.geometry);
  const joined = await match(records.filter(row => row.state_code === 'PA'), review, 'PA');
  const row = joined.get('42059');
  assert.equal(row.county, 'Greene');
  assert.equal(row.ballots, 11105);
  assert.equal(row.denominator, null);
  assert.equal(row.reported_pct, null);
  assert.equal(row.native_record.source_fips, '');
  assert.equal(row.maps_approved, false);
  assert.equal(row.native_record.counting_complete, 'False');
  const changed = copy(records);
  changed.find(isNew).denominator = 0;
  assert.throws(() => loadCountyContextReview(changed), /complete current source records/);
});

test('preserves all context12 facts and joins 159 Georgia counties without turning two missing rates into zero', async () => {
  const previous = new URL('../public/participation-county-context/20261106-12/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  assert.deepEqual(records.filter(row => row.state_code !== 'GA' && row.county !== 'Lycoming'), oldRecords);
  assert.deepEqual(review.observations.filter(row => row.state_code !== 'GA' && row.county !== 'Lycoming'), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(geometryBeforeGeorgia, oldReview.geometry);
  const joined = await match(records.filter(row => row.state_code === 'GA'), review, 'GA');
  assert.equal(joined.size, 159);
  assert.equal([...joined.values()].filter(row => row.reported_pct !== null).length, 157);
  assert.equal([...joined.values()].reduce((sum, row) => sum + row.ballots, 0), 4210155);
  for (const [geoid, county, ballots] of [['13251', 'Screven County', 5236], ['13161', 'Jeff Davis County', 4180]]) {
    const row = joined.get(geoid);
    assert.equal(row.county, county);
    assert.equal(row.ballots, ballots);
    assert.equal(row.reported_pct, null);
    assert.equal(row.denominator, null);
    assert.equal(Number(row.native_record.native_total_voters), 0);
    assert.equal(row.native_record.source_fips, '');
    assert.equal(row.maps_approved, false);
  }
  assert.equal(review.geometry.GA.boundary_year, 2024);
  assert.throws(() => loadCountyContextReview(oldRecords), /complete current source records/);
});

test('publication refuses changed, missing or duplicated source records rather than reusing old approvals', () => {
  const changed = copy(records); changed[0].ballots++;
  assert.throws(() => loadCountyContextReview(changed), /complete current source records/);
  assert.throws(() => loadCountyContextReview(records.slice(1)), /complete current source records/);
  assert.throws(() => loadCountyContextReview([...records.slice(1), records[1]]), /complete current source records/);
});

test('preserves all context13 facts and geometries while independently joining Lycoming', async () => {
  const previous = new URL('../public/participation-county-context/20261106-13/', import.meta.url);
  const oldRecords = JSON.parse(gunzipSync(readFileSync(new URL('complete-source-records.json.gz', previous))));
  const oldReview = JSON.parse(readFileSync(new URL('review.json', previous), 'utf8'));
  const isNew = row => row.review_id === 'pennsylvania-lycoming-20261106-01';
  assert.deepEqual(records.filter(row => !isNew(row)), oldRecords);
  assert.deepEqual(review.observations.filter(row => !isNew(row)), oldReview.observations);
  assert.deepEqual(review.excluded, oldReview.excluded);
  assert.deepEqual(review.geometry, oldReview.geometry);
  const row = (await match(records.filter(item => item.state_code === 'PA'), review, 'PA')).get('42081');
  assert.equal(row.county, 'Lycoming');
  assert.equal(row.ballots, 40596);
  assert.equal(row.denominator, 73009);
  assert.equal(row.reported_pct, 100 * 40596 / 73009);
  assert.equal(row.native_record.source_fips, '');
  assert.equal(row.native_record.county_ballot_modes, '');
  assert.equal(row.native_record.counting_complete, 'False');
  assert.equal(row.maps_approved, false);
  assert.equal(review.geometry.PA.boundary_year, 2024);
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

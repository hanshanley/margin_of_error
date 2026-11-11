import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { registeredTableCounts, extendCountDataset } from './extend-participation-counts.mjs';
import { encoded, digest } from './compile-participation-counts.mjs';

const root = process.env.PARTICIPATION_EXTENSION_INPUT || 'data/participation-count-extensions/20261111-nj-gap-01';
const body = readFileSync(`${root}/native-facts.json`);
const facts = JSON.parse(body), recipe = JSON.parse(readFileSync(`${root}/extension.json`));
const input = { body, sha256: digest(body), file: 'native-facts.json' };
const baseline = process.env.PARTICIPATION_COUNT_BASELINE || 'data/participation-counts/20261110-02/runtime';
const descriptor = JSON.parse(readFileSync(`${baseline}/dataset.json`));
const files = Object.fromEntries(Object.keys(descriptor.files).map(name => [name, readFileSync(`${baseline}/${name}`)]));
const additions = registeredTableCounts(facts, recipe, input);
const extended = extendCountDataset(files, additions, { id: recipe.id });
const shard = JSON.parse(gunzipSync(extended.files['states/NJ.json.gz']));

test('new native aggregate agreement produces counted-mode subtotals with conflicts and provisionals retained', () => {
  assert.deepEqual(additions.map(row => row.record.count.value), [225368, 213051]);
  const [essex, hudson] = additions.map(row => row.record);
  assert.deepEqual(essex.quality.conflicts[0].values, [11740, 1990]);
  assert.equal(essex.quality.conflicts[0].affects_selected_count, false);
  assert.equal(essex.quality.conflicts[0].repaired, false);
  assert.equal(hudson.view.native_record.provisional_ballots_counted, '1200');
  for (const row of [essex, hudson]) {
    assert.equal(row.denominator, null);
    assert.equal(row.view.reported_pct, null);
    assert.equal(row.reporting_status.complete, null);
    assert.equal(row.geography.join.status, 'unreviewed');
  }
});

test('missing native observations cannot become zero or a partial sum', () => {
  const changed = structuredClone(facts);
  for (const row of changed.reports[1].rows.filter(row => row.label.endsWith('TOTALS')))
    row.count_literals[2] = '';
  const changedBody = encoded(changed), changedRecipe = { ...recipe, input_sha256: digest(changedBody) };
  assert.throws(() => registeredTableCounts(changed, changedRecipe,
    { ...input, body: changedBody, sha256: digest(changedBody) }), /missing/);
});

test('conflicting selected totals and duplicate apparent corroboration are rejected', () => {
  const changed = structuredClone(facts);
  changed.reports[0].rows.find(row => row.label === 'Municipality TOTALS').count_literals[5] = '140184';
  const changedBody = encoded(changed), changedRecipe = { ...recipe, input_sha256: digest(changedBody) };
  assert.throws(() => registeredTableCounts(changed, changedRecipe,
    { ...input, body: changedBody, sha256: digest(changedBody) }), /disagree/);
  const duplicate = structuredClone(recipe);
  duplicate.sources[0].selected_labels = ['Congressional TOTALS', 'Congressional TOTALS'];
  assert.throws(() => registeredTableCounts(facts, duplicate, input), /identity/);
});

test('native total classification retains the source literal and cannot disguise a component sum', () => {
  const native = structuredClone(recipe);
  native.sources[0].participation_measure_kind = 'source_defined_participation_count';
  assert.throws(() => registeredTableCounts(facts, native, input), /native total/);
  native.sources[0].count_columns = [native.sources[0].count_columns[0]];
  const record = registeredTableCounts(facts, native, input)[0].record;
  const report = facts.reports.find(row => row.key === native.sources[0].report_key);
  const selected = report.rows.find(row => row.label === native.sources[0].selected_labels[0]);
  assert.equal(record.count.literal, selected.count_literals[report.columns.indexOf(native.sources[0].count_columns[0])]);
  assert.equal(record.view.participation_measure_kind, 'source_defined_participation_count');
  assert.equal(record.view.native_record.native_reported_total, String(record.count.value));
  assert.equal(record.view.native_record.reported_participation_subtotal, undefined);
});

test('an extension preserves all prior records and every unaffected runtime byte', () => {
  const prior = JSON.parse(gunzipSync(files['states/NJ.json.gz']));
  assert.deepEqual(shard.records.slice(0, prior.records.length), prior.records);
  assert.equal(shard.records.length, prior.records.length + 2);
  for (const [name, body] of Object.entries(files))
    if (!['index.json', 'states/NJ.json.gz'].includes(name)) assert.ok(extended.files[name].equals(body), name);
  for (const mode of ['available', 'official', 'uf_vep', 'uf_vap'])
    assert.equal(shard.views[mode].counties.length, 21);
  for (const mode of ['in_person_early', 'mail_returned'])
    assert.deepEqual(shard.views[mode], prior.views[mode]);
});

test('accepted observations and source-mode qualifications cannot be overwritten', () => {
  assert.throws(() => extendCountDataset(extended.files, additions, { id: 'again' }), /overwrite/);
  const wrongMode = structuredClone(additions);
  wrongMode[0].modes = ['mail_returned'];
  assert.throws(() => extendCountDataset(files, wrongMode, { id: 'wrong' }), /substitute/);
});

function heldFrame(value = null) {
  const holding = structuredClone(additions[0]);
  holding.record.id = digest(encoded(['held', value])).slice(0, 32);
  holding.record.measure.id = 'earlier-missing-observation';
  holding.record.count = { value, literal: value, status: value === null ? 'withheld' : 'reported' };
  holding.record.view.ballots = value;
  const base = extendCountDataset(files, [holding], { id: 'holding-fixture' });
  return { holding, base };
}

test('a pinned missing source can be superseded without losing any accepted source record', () => {
  const { holding, base } = heldFrame();
  const replacement = { ...additions[0],
    supersedes: { id: holding.record.id, sha256: digest(encoded(holding.record)) } };
  const result = extendCountDataset(base.files, [replacement], { id: 'qualified-successor' });
  const before = JSON.parse(gunzipSync(base.files['states/NJ.json.gz']));
  const after = JSON.parse(gunzipSync(result.files['states/NJ.json.gz']));
  assert.deepEqual(after.records.slice(0, before.records.length), before.records);
  for (const mode of ['available', 'official', 'uf_vep', 'uf_vap']) {
    assert.equal(after.views[mode].counties.length, before.views[mode].counties.length);
    assert.ok(after.views[mode].counties.includes(replacement.record.id));
    assert.ok(!after.views[mode].counties.includes(holding.record.id));
  }
  for (const mode of ['in_person_early', 'mail_returned'])
    assert.deepEqual(after.views[mode], before.views[mode]);
});

test('a changed predecessor, reported zero, and cross-mode source substitution cannot be superseded', () => {
  const { holding, base } = heldFrame();
  const replacement = { ...additions[0],
    supersedes: { id: holding.record.id, sha256: '0'.repeat(64) } };
  assert.throws(() => extendCountDataset(base.files, [replacement], {}), /pinned missing/);
  const zero = heldFrame(0);
  replacement.supersedes = { id: zero.holding.record.id, sha256: digest(encoded(zero.holding.record)) };
  assert.throws(() => extendCountDataset(zero.base.files, [replacement], {}), /pinned missing/);
  replacement.supersedes = { id: holding.record.id, sha256: digest(encoded(holding.record)) };
  replacement.modes = ['in_person_early'];
  assert.throws(() => extendCountDataset(base.files, [replacement], {}), /pinned missing/);
});

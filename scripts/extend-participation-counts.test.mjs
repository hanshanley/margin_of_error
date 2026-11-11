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

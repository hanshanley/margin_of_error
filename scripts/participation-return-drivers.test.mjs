import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { driverRows, driverScale, validateModels, mapScale, effectFill, mapTerms, mapValue } from '../public/scripts/participation-return-drivers.js';

const data = JSON.parse(readFileSync('data/participation-return-attribution/20261110-02/viewer-data.json'));

test('all modeled offices retain every computed state/race and complete accounting', () => {
  validateModels(data);
  assert.equal(driverRows(data, 'house').length, 50);
  assert.equal(driverRows(data, 'senate').length, 35);
  assert.equal(driverRows(data, 'governor').length, 28);
  for (const row of data.rows)
    assert.ok(Math.abs(Object.values(row.components_pp).reduce((a, b) => a + b, 0)
      - row.source_frame_change_pp) < 1e-8);
});

test('rankings compare contribution magnitudes, preserve opposing signs and filter states', () => {
  for (const office of ['house', 'senate', 'governor']) {
    const rows = driverRows(data, office, '', 'switching');
    assert.ok(rows.every((row, i) => !i
      || Math.abs(rows[i - 1].components_pp.switching) >= Math.abs(row.components_pp.switching)));
  }
  const rows = driverRows(data, 'house', 'minne', 'name', { MN: 'Minnesota' });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].state_code, 'MN');
  assert.ok(data.rows.some(row => row.components_pp.switching < 0));
});

test('the common scale contains the entire declared assumption ranges', () => {
  for (const office of ['house', 'senate', 'governor']) {
    const rows = driverRows(data, office), scale = driverScale(rows);
    for (const row of rows)
      for (const key of ['switching', 'modeled_nonparticipation']) {
        assert.ok(Math.abs(row.ranges_pp[key].minimum) <= scale);
        assert.ok(Math.abs(row.ranges_pp[key].maximum) <= scale);
      }
  }
});

test('unknowns and tampered reconciliation cannot become apparently valid zero effects', () => {
  const missing = structuredClone(data);
  missing.rows[0].components_pp.switching = null;
  assert.throws(() => validateModels(missing), /Invalid model contribution/);
  const changed = structuredClone(data);
  changed.rows[0].components_pp.return_frame_gap += 1;
  assert.throws(() => validateModels(changed), /do not reconcile/);
  const duplicate = structuredClone(data);
  duplicate.rows.push(duplicate.rows[0]);
  assert.throws(() => validateModels(duplicate), /duplicate model identity/);
});

test('all four selectable views share one signed point scale and missing is not zero', () => {
  for (const office of ['house', 'senate', 'governor']) {
    const rows = driverRows(data, office), scale = mapScale(rows);
    for (const row of rows)
      for (const [key] of mapTerms)
        assert.ok(Math.abs(mapValue(row, key) ?? 0) <= scale);
    assert.notEqual(effectFill(null, scale), effectFill(0, scale));
    assert.notEqual(effectFill(-scale, scale), effectFill(scale, scale));
    assert.equal(effectFill(0, scale), '#f1eee6');
  }
});

test('Texas reported swing reconciles instead of being mislabeled as its switching component', () => {
  const row = data.rows.find(row => row.id === 'TX-house');
  assert.ok(Math.abs(mapValue(row, 'reported_total') - 25.16363563924734) < 1e-10);
  assert.ok(Math.abs(mapValue(row, 'other_and_unallocated') - 22.41207106277195) < 1e-10);
  assert.ok(Math.abs(mapValue(row, 'reported_total') - mapValue(row, 'switching')
    - mapValue(row, 'modeled_nonparticipation') - mapValue(row, 'other_and_unallocated')) < 1e-10);
  assert.equal(row.reported_comparison.baseline_year, 2024);
  const changed = structuredClone(data);
  changed.rows.find(row => row.id === 'TX-house').reported_comparison.reported_change_pp += 1;
  assert.throws(() => validateModels(changed), /Reported swing does not reconcile/);
});

test('unqualified return comparisons stay missing without hiding available modeled components', () => {
  const row = data.rows.find(row => row.id === 'AK-house');
  assert.equal(mapValue(row, 'reported_total'), null);
  assert.equal(mapValue(row, 'other_and_unallocated'), null);
  assert.equal(mapValue(row, 'switching'), row.components_pp.switching);
  assert.equal(mapValue(undefined, 'reported_total'), null);
  const changed = structuredClone(data);
  changed.rows.find(row => row.id === 'AK-house').reported_comparison.reported_change_pp = 0;
  assert.throws(() => validateModels(changed), /must remain unknown/);
});

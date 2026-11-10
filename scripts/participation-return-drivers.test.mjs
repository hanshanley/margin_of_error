import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { driverRows, driverScale, validateModels } from '../public/scripts/participation-return-drivers.js';

const data = JSON.parse(readFileSync('data/participation-return-attribution/20261110-01/viewer-data.json'));

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

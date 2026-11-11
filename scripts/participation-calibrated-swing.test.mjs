import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validateCalibratedSwing, roundedContributions, calibratedTerms } from '../public/scripts/participation-calibrated-swing.js';
import { mapValue, mapScale, driverRows, mapTerms } from '../public/scripts/participation-return-drivers.js';

const original = JSON.parse(readFileSync('data/participation-return-attribution/20261110-02/viewer-data.json'));
const data = JSON.parse(readFileSync('data/participation-return-attribution/20261111-03/return-constrained-viewer.json'));
const rows = validateCalibratedSwing(data, original);

test('every state/office decision uses both actual endpoints or remains explicitly unavailable', () => {
  assert.equal(rows.size, 113);
  assert.equal([...rows.values()].filter(row => row.point).length, 89);
  for (const old of original.rows) {
    const row = rows.get(old.id);
    if (row.point) {
      assert.ok(Math.abs(row.point.previous_margin_pp - old.reported_comparison.previous_margin_pp) < 1e-8);
      assert.ok(Math.abs(row.point.current_margin_pp - old.reported_comparison.current_margin_pp) < 1e-8);
      assert.equal(Math.round(Object.values(roundedContributions(row.point)).reduce((a,b)=>a+b,0)*100),
        Math.round(Number(old.reported_comparison.reported_change_pp.toFixed(2))*100));
    } else for (const key of ['switching','modeled_nonparticipation','entry','other_choice'])
      assert.equal(mapValue(old, key, row), null);
  }
});

test('all displayed contribution maps use calibrated cells, never the old survey-frame terms', () => {
  for (const office of ['house','senate','governor']) {
    const selected = driverRows(original, office), scale = mapScale(selected, rows);
    for (const old of selected) for (const [key] of mapTerms)
      assert.ok(Math.abs(mapValue(old, key, rows.get(old.id)) ?? 0) <= scale);
  }
  const texas = original.rows.find(row=>row.id==='TX-house');
  assert.notEqual(mapValue(texas,'switching',rows.get(texas.id)), texas.components_pp.switching);
  assert.equal(mapValue(texas,'switching'), null);
  assert.equal(mapValue(texas,'other_and_unallocated',rows.get(texas.id)), null);
});

test('a tampered endpoint, negative cell, absent comparison or claimed independent validation fails closed', () => {
  for (const mutate of [
    row=>{row.point.previous_margin_pp+=1;},
    row=>{row.point.synthetic_joint[0][0]=-1;},
    row=>{row.calibration_is_not_independent_validation=false;},
    row=>{row.point.target_rows[0]+=.001;},
    row=>{row.ranges_pp.entry.maximum=-1000;},
  ]) {
    const changed = structuredClone(data); mutate(changed.rows.find(row=>row.id==='TX-house'));
    assert.throws(()=>validateCalibratedSwing(changed, original));
  }
  const changed=structuredClone(data);
  changed.rows.find(row=>row.status==='unavailable').point={};
  assert.throws(()=>validateCalibratedSwing(changed,original),/Missing endpoints/);
});

test('unknown Other in governor frames is declared assumed, never changed to an observed zero', () => {
  for (const row of data.rows.filter(row=>row.office==='governor' && row.point)) {
    assert.deepEqual(row.observed_other_vote_endpoints,[false,false]);
    assert.equal(row.reported_comparison.previous.O,undefined);
    assert.equal(row.reported_comparison.current.O,undefined);
    assert.ok(row.point.target_rows[2]>=0);
  }
});

test('sum-preserving display rounding handles negative halves without altering raw model values', () => {
  const point={reported_change_pp:-.125, components_pp:{switching:-.05, nonparticipation:-.025, entry:-.025, other_choice:-.025}};
  const before=structuredClone(point), rounded=roundedContributions(point);
  assert.ok(Math.abs(Object.values(rounded).reduce((a,b)=>a+b,0)+.13)<1e-12);
  assert.deepEqual(point,before);
  assert.ok(calibratedTerms.every(([key])=>Math.abs(rounded[key]-point.components_pp[key])<=.01+1e-12));
});

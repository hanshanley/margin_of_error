import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validateScenarios, scenarioGroups, scenarioEstimate, scenarioScale,
  groupIdentity } from '../public/scripts/participation-transition-scenarios.js';

const data = JSON.parse(readFileSync('data/participation-transition-simulation/20261111-01/viewer-data.json'));

test('the actual full released query retains overall decisions without duplicating the overall control', () => {
  validateScenarios(data);
  assert.ok(data.complete_demographic_decisions.some(row => row.dimension === 'overall'));
  assert.ok(scenarioGroups(data).length > 0);
  assert.ok(scenarioGroups(data).every(row => !row.key.startsWith('overall|')));
});

test('D.C., withheld groups and absent categories remain unavailable rather than zero', () => {
  assert.equal(scenarioEstimate(data, 'DC', 'scenario_nonparticipation'), null);
  const held = data.complete_demographic_decisions.find(row => row.point === null);
  assert.equal(scenarioEstimate(data, held.state_code, 'scenario_switching', groupIdentity(held)), null);
  assert.equal(scenarioEstimate(data, 'TX', 'scenario_retaining', 'AGE6|not-a-category'), null);
  const actual = scenarioEstimate(data, 'TX', 'scenario_nonparticipation');
  assert.ok(actual.minimum <= actual.value && actual.value <= actual.maximum);
});

test('a held group cannot acquire apparently valid values copied from another state', () => {
  const changed = structuredClone(data);
  const held = changed.complete_demographic_decisions.find(row => row.point === null);
  Object.assign(held, changed.state_scenarios.TX);
  assert.throws(() => validateScenarios(changed), /Held demographic/);
});

test('invalid gross partitions, missing denominator values and false population claims are rejected', () => {
  const changed = structuredClone(data);
  changed.state_scenarios.TX.point.synthetic_retaining_share_of_recalled_major_party += .01;
  assert.throws(() => validateScenarios(changed), /partition|share/);
  const missing = structuredClone(data);
  missing.state_scenarios.TX.point.synthetic_no_prior_contest_vote_entry_share_of_current_major_party = null;
  assert.throws(() => validateScenarios(missing), /denominator/);
  const relabeled = structuredClone(data);
  relabeled.source_nonvoter_is_administrative_staying_home = true;
  assert.throws(() => validateScenarios(relabeled), /unqualified/);
});

test('same-office reconciliation preserves both residuals and unavailable historical baselines', () => {
  const supported = data.unfitted_return_checks.filter(row => row.reported_same_office_change_pp !== null);
  assert.equal(supported.length, 89);
  for (const row of supported)
    assert.ok(Math.abs(row.reported_same_office_change_pp - row.prior_baseline_alignment_pp
      - row.unallocated_return_minus_model_pp
      - Object.values(row.synthetic_components_pp).reduce((a, b) => a + b, 0)) < 1e-8);
  const changed = structuredClone(data);
  changed.unfitted_return_checks.find(row => row.reported_same_office_change_pp === null)
    .reported_same_office_change_pp = 0;
  assert.throws(() => validateScenarios(changed), /reconcile/);
});

test('sequential share scale contains valid shares without conflating missing and zero', () => {
  assert.equal(scenarioScale([null, .53, 0]), .6);
  assert.equal(scenarioScale([null, 0]), .1);
  assert.throws(() => scenarioEstimate(data, 'TX', 'reported_total'), /Unknown scenario/);
});

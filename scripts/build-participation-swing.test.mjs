import assert from 'node:assert/strict';
import test from 'node:test';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { cohortSelection } from '../public/scripts/participation-swing.js';
import { demographicRegistry, observedComparisons, qualifyConditionalScenarios, swingRoot, verifyFrozenSwingInputs } from './build-participation-swing.mjs';
import { qualifyCohort } from './participation-swing.mjs';

const read = file => JSON.parse(readFileSync(file, 'utf8'));
const cohort = read('data/participation-swing/20261106-demographic-cohort-01/aggregate-cohort.json');
const audit = read('data/participation-swing/20261106-demographic-cohort-01/audit.json');
const candidates = read('data/participation-swing/20261106-candidate-scope-01/county-contest-methods.json');

function votes(year, county, contest, democratic, republican, other = 0) {
  return [['DEM', democratic], ['REP', republican], ['UNA', other]].map(([party_literal, count]) => ({
    year, county, contest, method: 'Total Votes', party_literal, votes: count,
  }));
}

test('descriptive swing uses two-party denominators and never becomes persuasion or turnout', () => {
  const rows = observedComparisons([
    ...votes(2024, 'TEST', 'US PRESIDENT', 40, 60, 100),
    ...votes(2026, 'TEST', 'US SENATE', 60, 40, 300),
  ]);
  assert.equal(rows[0].swing_margin_pp, 40);
  assert.equal(rows[0].democratic_share_change_pp, 20);
  assert.equal(rows[0].outcome_other_votes, 300);
  assert.equal(rows[0].persuasion_share_pct, null);
  assert.equal(rows[0].staying_home_share_pct, null);
});

test('split House counties, missing baselines and absent major parties are withheld separately', () => {
  const rows = observedComparisons([
    ...votes(2024, 'TEST', 'US PRESIDENT', 50, 50),
    ...votes(2026, 'TEST', 'US SENATE', 60, 40),
    ...votes(2026, 'TEST', 'US HOUSE DISTRICT 01', 10, 5),
    ...votes(2026, 'TEST', 'US HOUSE DISTRICT 02', 20, 5),
    ...votes(2026, 'MISSING', 'US SENATE', 20, 10),
    ...votes(2024, 'UNCONTESTED', 'US PRESIDENT', 50, 50),
    ...votes(2026, 'UNCONTESTED', 'US SENATE', 50, 0),
  ]);
  assert.equal(rows.filter(row => row.observed_comparison_status === 'provisional_descriptive').length, 1);
  for (const row of rows.filter(row => row.contest !== 'US SENATE' || row.county !== 'TEST')) {
    assert.equal(row.swing_margin_pp, null);
    assert.ok(row.exclusion_reasons.length > 0);
  }
});

test('cohort selector sums only the selected county, method and one demographic partition', () => {
  const selected = cohortSelection(cohort, 'DURHAM', 'All included methods', 'age');
  assert.equal(selected.reduce((sum, row) => sum + row.accepted_records, 0), 116775);
  assert.equal(selected.reduce((sum, row) => sum + row.positive_2024_history_matches, 0), 103614);
  assert.equal(selected.reduce((sum, row) => sum + row.history_unresolved, 0), 13161);
  const early = cohortSelection(cohort, 'DURHAM', 'EARLY VOTING', 'age');
  assert.equal(early.reduce((sum, row) => sum + row.accepted_records, 0), 112802);
  assert.ok(cohortSelection(cohort, 'WAKE', 'MAIL', 'race')
    .every(row => row.positive_2024_history_matches === null && row.history_unresolved === null));
  assert.deepEqual(cohortSelection(cohort, 'DURHAM', 'MAIL', 'education'), []);
});

test('registry preserves overlapping source definitions, unknowns, and truly absent dimensions', () => {
  const registry = demographicRegistry(cohort);
  assert.equal(registry.length, 8);
  assert.match(registry.find(row => row.dimension === 'race').definition, /overlaps/);
  assert.ok(registry.find(row => row.dimension === 'sex_gender').groups.some(row => row.group === 'U'));
  assert.ok(registry.find(row => row.dimension === 'age').groups.some(row => row.group === 'Unknown'));
  for (const name of ['education', 'household_income', 'residence_type']) {
    assert.equal(registry.find(row => row.dimension === name).composition_available, false);
  }
  assert.ok(registry.every(row => !row.candidate_choice_observed && !row.persuasion_estimate_available));
});

test('full frozen review reconciles every single-dimension partition and keeps all 100 counties', () => {
  assert.equal(new Set(cohort.map(row => row.county)).size, 100);
  assert.equal(audit.cohort_audit.duplicate_accepted_identifier_records, 11);
  const allowed = ['state_code', 'county', 'method_literal', 'dimension', 'group', 'accepted_records',
    'positive_2024_history_matches', 'history_unresolved', 'group_turnout_pct',
    'prior_democratic_share_pct', 'swing_margin_pp'].sort();
  for (const row of cohort) {
    assert.deepEqual(Object.keys(row).sort(), allowed);
    assert.equal(row.group_turnout_pct, null);
    assert.equal(row.prior_democratic_share_pct, null);
    assert.equal(row.swing_margin_pp, null);
    if (row.county === 'DURHAM') {
      assert.equal(row.positive_2024_history_matches + row.history_unresolved, row.accepted_records);
    }
  }
  for (const overall of cohort.filter(row => row.dimension === 'overall')) {
    for (const dimension of ['race', 'ethnicity', 'age', 'sex_gender', 'registered_party']) {
      const selected = cohortSelection(cohort, overall.county, overall.method_literal, dimension);
      assert.equal(selected.reduce((sum, row) => sum + row.accepted_records, 0), overall.accepted_records);
    }
  }
});

test('real-data model fails qualification; fitting totals and passing math tests do not release estimates', () => {
  assert.equal(qualifyCohort(audit.evidence, { demographic: true }).qualified, false);
  const comparisons = observedComparisons(candidates);
  assert.equal(comparisons.filter(row => row.contest === 'US SENATE').length, 100);
  assert.ok(comparisons.every(row => row.persuasion_share_pct === null && row.staying_home_share_pct === null));
});

test('public complete-input manifest pins exact bytes and excludes private voter archives', () => {
  const manifest = read(`${swingRoot}/inputs.json`);
  for (const file of ['conditional-transitions.json', 'historical-choice-model.json', 'nationwide-scope.json',
    'NC-results-20241105.zip', 'NC-results-20261103.zip', 'county-district-candidate-totals.csv.gz']) {
    assert.ok(manifest.some(row => row.path.endsWith(`/${file}`)), `Complete input missing: ${file}`);
  }
  for (const row of manifest) {
    assert.doesNotMatch(row.path, /absentee\.zip|history-durham\.zip|session-state|\.copilot/);
  }
  assert.equal(verifyFrozenSwingInputs(manifest), true);
  assert.equal(read(`${swingRoot}/analysis.json`).validation.release_point_estimates, false);
  assert.deepEqual(read(`${swingRoot}/observed-comparisons.json`), observedComparisons(candidates));
});

test('county refreshes retain the exact historical input manifest and its prior pointer', () => {
  const original = {
    data_directory: 'old', previous_snapshots: [], label: 'Old observation',
    party_votes: { data_directory: 'old/party-votes' },
  };
  const bytes = Buffer.from(`${JSON.stringify(original, null, 2)}\n`);
  const manifest = [{
    path: 'public/county-results.json', bytes: bytes.length,
    sha256: createHash('sha256').update(bytes).digest('hex'),
  }];
  const unchanged = structuredClone(manifest);
  const { previous_snapshots, ...snapshot } = original;
  const refreshed = {
    ...original, data_directory: 'new', previous_snapshots: [snapshot],
    label: 'New observation', party_votes: { data_directory: 'new/party-votes' },
  };
  const readPointer = () => Buffer.from(JSON.stringify(refreshed));
  assert.equal(verifyFrozenSwingInputs(manifest, () => bytes), true);
  assert.equal(verifyFrozenSwingInputs(manifest, readPointer), true);
  assert.deepEqual(manifest, unchanged);
  refreshed.previous_snapshots[0].label = 'Changed historical observation';
  assert.throws(() => verifyFrozenSwingInputs(manifest, readPointer), /Changed frozen analysis input/);
  refreshed.previous_snapshots = [];
  assert.throws(() => verifyFrozenSwingInputs(manifest, readPointer), /Changed frozen analysis input/);
});

test('an unchanged historical pointer cannot hide changed frozen candidate inputs', () => {
  const bytes = Buffer.from('original candidate counts');
  const manifest = [{
    path: 'data/county-results/old/candidates.csv.gz', bytes: bytes.length,
    sha256: createHash('sha256').update(bytes).digest('hex'),
  }];
  assert.equal(verifyFrozenSwingInputs(manifest, () => bytes), true);
  assert.throws(() => verifyFrozenSwingInputs(manifest, () => Buffer.from('changed candidate counts')),
    /Changed frozen analysis input/);
});

test('experimental scenarios reconcile but never become independently validated persuasion', () => {
  const model = read('data/participation-swing/20261106-conditional-model-01/conditional-transitions.json');
  const comparison = observedComparisons(candidates).find(row => row.county === 'DURHAM' && row.contest === 'US SENATE');
  assert.equal(qualifyConditionalScenarios(model, comparison.swing_margin_pp), true);
  const invalid = structuredClone(model);
  invalid.scenarios[0].demographics[0].ncid = 'must never be published';
  assert.throws(() => qualifyConditionalScenarios(invalid, comparison.swing_margin_pp));
  const unreconciled = structuredClone(model);
  unreconciled.scenarios[0].margin_pp_contributions.switching += 1;
  assert.throws(() => qualifyConditionalScenarios(unreconciled, comparison.swing_margin_pp));
  assert.equal(read(`${swingRoot}/analysis.json`).validation.individual_transition_accuracy_validated, false);
});

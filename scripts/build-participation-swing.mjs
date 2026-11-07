import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { cohortShift, qualifyCohort, transitionBounds, twoPartyResult } from './participation-swing.mjs';

const read = path => JSON.parse(readFileSync(path, 'utf8'));
const cohortRoot = 'data/participation-swing/20261106-demographic-cohort-01';
const candidateRoot = 'data/participation-swing/20261106-candidate-scope-01';
const modelRoot = 'data/participation-swing/20261106-conditional-model-01';
export const swingVersion = '20261106-02';
export const swingRoot = `public/participation-swing/${swingVersion}`;

export function qualifyConditionalScenarios(model, observedSwing) {
  assert.equal(model.status, 'experimental_conditional_model_not_individually_identified');
  assert.equal(model.validated_individual_attribution, false);
  assert.equal(model.state, 'NC');
  assert.equal(model.county, 'DURHAM');
  assert.equal(model.scenario_count, model.scenarios.length);
  assert.ok(model.scenarios.length > 1);
  const dimensions = ['overall', 'age_2024', 'race', 'ethnicity', 'administrative_gender'];
  for (const scenario of model.scenarios) {
    assert.ok(Math.abs(scenario.swing_margin_pp - observedSwing) < 1e-7);
    const components = Object.entries(scenario.margin_pp_contributions);
    assert.ok(components.every(([, value]) => Number.isFinite(value)));
    assert.ok(Math.abs(components.reduce((sum, [, value]) => sum + value, 0) - observedSwing) < 1e-7);
    assert.deepEqual([...new Set(scenario.demographics.map(row => row.dimension))].sort(), [...dimensions].sort());
    for (const row of scenario.demographics) {
      assert.deepEqual(Object.keys(row).sort(), ['dimension', 'group', 'registered_or_baseline_records',
        'modeled_2026_participants', 'margin_pp_contributions'].sort(), 'No private cell fields in public rows');
    }
    for (const dimension of dimensions) {
      const groups = scenario.demographics.filter(row => row.dimension === dimension);
      assert.equal(new Set(groups.map(row => row.group)).size, groups.length);
      for (const [component, contribution] of components) {
        assert.ok(Math.abs(groups.reduce((sum, row) => sum + row.margin_pp_contributions[component], 0) - contribution) < 1e-7);
      }
    }
  }
  return true;
}

export function observedComparisons(candidates) {
  const grouped = new Map();
  for (const row of candidates) {
    if (row.method !== 'Total Votes') continue;
    const key = JSON.stringify([row.year, row.county, row.contest]);
    if (!grouped.has(key)) grouped.set(key, {
      year: row.year, county: row.county, contest: row.contest, democratic: 0, republican: 0, other: 0,
    });
    const column = row.party_literal === 'DEM' ? 'democratic' : row.party_literal === 'REP' ? 'republican' : 'other';
    const group = grouped.get(key);
    group[column] += row.votes;
  }
  const rows = [...grouped.values()];
  const baseline = new Map(rows.filter(row => row.year === 2024 && row.contest === 'US PRESIDENT')
    .map(row => [row.county, row]));
  const houseCounts = new Map();
  for (const row of rows.filter(row => row.year === 2026 && row.contest.startsWith('US HOUSE'))) {
    houseCounts.set(row.county, (houseCounts.get(row.county) ?? 0) + 1);
  }
  return rows.filter(row => row.year === 2026).map(row => {
    const before = baseline.get(row.county);
    const excluded = [];
    if (!before) excluded.push('Missing county presidential baseline');
    if (row.contest.startsWith('US HOUSE') && houseCounts.get(row.county) !== 1) {
      excluded.push('Split House county requires a matching county/district presidential baseline');
    }
    if (!row.democratic || !row.republican || !before?.democratic || !before?.republican) {
      excluded.push('Missing or zero major-party comparison');
    }
    const start = before ? twoPartyResult(before.democratic, before.republican) : null;
    const end = twoPartyResult(row.democratic, row.republican);
    return {
      county: row.county, contest: row.contest, ballot_scope: 'All native reported ballot methods',
      baseline: start, outcome: end, baseline_other_votes: before?.other ?? null, outcome_other_votes: row.other,
      observed_comparison_status: excluded.length ? 'withheld' : 'provisional_descriptive',
      exclusion_reasons: excluded,
      swing_margin_pp: excluded.length ? null : end.margin_pp - start.margin_pp,
      democratic_share_change_pp: excluded.length ? null : end.democratic_share_pct - start.democratic_share_pct,
      persuasion_share_pct: null, staying_home_share_pct: null,
      interpretation: 'Different elections and electorates. Descriptive county swing, not fixed-cohort persuasion or turnout.',
    };
  });
}

export function demographicRegistry(records) {
  const definitions = [
    ['race', 'Race', 'race', 'Administrative source category; overlaps ethnicity.'],
    ['ethnicity', 'Ethnicity', 'ethnicity', 'Administrative source category; overlaps race.'],
    ['age', 'Age', 'age', 'Derived age bins; the native age reference date is not independently established.'],
    ['sex_gender', 'Source-defined sex / gender', 'gender', 'Native administrative gender field, not a harmonized survey identity.'],
    ['registered_party', 'Registered party (not vote choice)', 'voter_party_code', 'Administrative registration, never a Trump/Harris vote label.'],
    ['education', 'Education', null, 'Absent from this cohort source; neighborhood attainment is not personal education.'],
    ['household_income', 'Household income', null, 'Absent from this cohort source; neighborhood income is not household income.'],
    ['residence_type', 'Urban / suburban / rural', null, 'No documented classification or geographic vintage in this cohort review.'],
  ];
  return definitions.map(([dimension, label, native_field, definition]) => {
    const groups = new Map();
    for (const row of records.filter(row => row.dimension === dimension)) {
      groups.set(row.group, (groups.get(row.group) ?? 0) + row.accepted_records);
    }
    return {
      dimension, label, native_field, definition,
      provenance: dimension === 'age' ? 'derived_from_administrative_age'
        : native_field ? 'administrative_source_field' : 'not_supplied',
      election: '2026-11-03', geography: 'NC counties', scope: 'Literal ACCEPTED early/mail records',
      composition_available: Boolean(native_field), group_turnout_available: false,
      candidate_choice_observed: false, persuasion_estimate_available: false,
      groups: [...groups].sort(([a], [b]) => a.localeCompare(b))
        .map(([group, accepted_records]) => ({ group, accepted_records })),
      intersections_available: false,
    };
  });
}

export function buildSwingAnalysis() {
  const audit = read(`${cohortRoot}/audit.json`);
  const records = read(`${cohortRoot}/aggregate-cohort.json`);
  const candidates = read(`${candidateRoot}/county-contest-methods.json`);
  const candidateAudit = read(`${candidateRoot}/candidate-audit.json`);
  const registry = demographicRegistry(records);
  const observed = observedComparisons(candidates);
  const conditional = read(`${modelRoot}/conditional-transitions.json`);
  const historical = read(`${modelRoot}/historical-choice-model.json`);
  const scope = read(`${modelRoot}/nationwide-scope.json`);
  qualifyConditionalScenarios(conditional, observed.find(row => row.county === 'DURHAM' && row.contest === 'US SENATE').swing_margin_pp);
  assert.equal(scope.jurisdictions.length, 51);
  assert.equal(historical.state_count, 51);
  const participationPath = 'public/voter-participation/data/current/20261104T152627Z/snapshot.json';
  for (const [role, path] of [['fitted_choice_models', `${modelRoot}/historical-choice-model.json`],
    ['complete_candidate_methods', `${candidateRoot}/county-contest-methods.json`],
    ['participation_snapshot', participationPath]]) {
    assert.equal(conditional.inputs.find(row => row.role === role)?.sha256,
      createHash('sha256').update(readFileSync(path)).digest('hex'), `Changed fitted input: ${role}`);
  }
  assert.equal(new Set(records.map(row => row.county)).size, 100);
  assert.equal(observed.filter(row => row.contest === 'US SENATE').length, 100);
  for (const county of new Set(records.map(row => row.county))) {
    for (const method of new Set(records.filter(row => row.county === county).map(row => row.method_literal))) {
      const subset = records.filter(row => row.county === county && row.method_literal === method);
      const total = subset.find(row => row.dimension === 'overall')?.accepted_records;
      assert.ok(Number.isSafeInteger(total));
      for (const dimension of registry.filter(row => row.composition_available)) {
        assert.equal(subset.filter(row => row.dimension === dimension.dimension)
          .reduce((sum, row) => sum + row.accepted_records, 0), total, `Partition does not reconcile: ${dimension.dimension}`);
      }
    }
  }
  const qualification = qualifyCohort(audit.evidence, { demographic: true });
  assert.equal(qualification.qualified, false, 'A qualified cohort requires a new reviewed analysis version');
  const sourceLedger = [
    { source: 'NC native early/mail and Durham history', status: 'complete_aggregate_review',
      source_url: 'https://www.ncsbe.gov/results-data/absentee-and-provisional-data',
      receipts: audit.source_receipts,
      conclusion: 'Positive turnout history only; accepted-record duplicates, unknown historical nonmatches, and candidate-cohort mismatch prevent attribution.' },
    { source: 'NC 2024 President and 2026 Senate / House native returns',
      status: 'complete_county_contest_method_review', receipts: candidateAudit.source_receipts,
      source_url: 'https://www.ncsbe.gov/results-data/election-results/historical-election-results-data',
      conclusion: 'All four methods reconcile per native candidate row. County comparisons remain provisional and descriptive, never voter transitions.' },
    { source: 'CES 2024 common content', status: 'four_historical_models_fitted_internal_county_holdout',
      source_url: 'https://doi.org/10.7910/DVN/X11EP6', dataset_version: '9.0',
      checked_date: '2026-11-06',
      conclusion: 'Four historical-choice models fitted to 32,891 validated-turnout respondents across all 50 states plus DC. County-held-out diagnostics are internal checks, not independent validation of 2026 transitions; survey weights include outcome calibration.' },
    { source: 'CES 2026', status: 'validated_panel_not_yet_available_on_published_schedule',
      source_url: 'https://tischcollege.tufts.edu/research-faculty/research-centers/cooperative-election-study/about-methodology',
      checked_date: '2026-11-06', team_data_schedule: 'March 2027', matched_voter_file_schedule: 'Summer 2027',
      conclusion: 'Published delivery schedule cannot supply current 2024-to-2026 validated transitions; do not treat a repeated cross-section as the same people.' },
    { source: 'ANES 2024 time series', status: 'historical_choice_and_turnout_validation_available',
      source_url: 'https://electionstudies.org/data-center/2024-time-series-study/',
      checked_date: '2026-11-06', current_dataset_version: '2026-05-19', vote_validation_version: '2026-06-23',
      conclusion: 'Historical panel extends through 2024, not a validated 2026 cohort or 2026 demographic vote choices.' },
  ];
  const example = {
    evidence: 'synthetic_explanation_only', before: { D: 50, R: 50, O: 0, B: 0, N: 0, X: 0 },
    after: { D: 50, R: 40, O: 0, B: 0, N: 10, X: 0 },
  };
  const bounds = transitionBounds({ ...example, common_population_verified: true });
  const illustration = cohortShift(Object.fromEntries([
    'membership_verified', 'same_people', 'methods_matched', 'geography_matched', 'cutoff_matched',
    'valid_vote_universe_matched', 'prior_turnout_verified', 'prior_preference_validated',
  ].map(key => [key, true])), -6, 12);
  const output = {
    version: swingVersion, schema_version: 1, baseline_election: '2024-11-05', outcome_election: '2026-11-03',
    status: 'experimental_durham_scenarios_with_nationwide_evidence_ledger', state_code: 'NC',
    demographic_attribution: qualification, cohort_audit: audit, candidate_audit: candidateAudit,
    demographic_registry: registry, source_ledger: sourceLedger,
    validation: { transition_math: 'exhaustive_small_population_tests', real_transition_model_fitted: true,
      historical_preference_model_validated: 'internal_county_holdout_only', demographic_choice_model_validated: false,
      individual_transition_accuracy_validated: false, release_point_estimates: false,
      release_experimental_conditional_scenarios: true,
      reason: 'Numerical correctness is not validation of individual or demographic electoral transitions.' },
    illustrative_identification_bounds: { ...example, ...bounds },
    illustrative_fixed_cohort_shift: { ...illustration, evidence: 'user_supplied_design_illustration_not_texas_data' },
    privacy: 'No personal identifiers, individual joins, individual scores, or native voter records in this package.',
    complete_download: `/participation-swing/${swingVersion}/complete-analysis.zip`,
    files: { cohort: 'aggregate-cohort.json', candidates: 'county-contest-methods.json', observed: 'observed-comparisons.json',
      conditional: 'conditional-transitions.json', historical: 'historical-choice-model.json', coverage: 'nationwide-scope.json' },
  };
  mkdirSync(swingRoot, { recursive: true });
  for (const [name, value] of [
    ['analysis.json', output], ['aggregate-cohort.json', records],
    ['county-contest-methods.json', candidates], ['observed-comparisons.json', observed],
    ['conditional-transitions.json', conditional], ['historical-choice-model.json', historical],
    ['nationwide-scope.json', scope],
  ]) {
    writeFileSync(`${swingRoot}/${name}`, `${JSON.stringify(value)}\n`);
  }
  const inputs = [
    `${cohortRoot}/audit.json`, `${cohortRoot}/aggregate-cohort.json`,
    `${candidateRoot}/candidate-audit.json`, `${candidateRoot}/county-contest-methods.json`,
    `${candidateRoot}/source-receipt.json`, `${candidateRoot}/NC-results-20241105.zip`,
    'data/precinct-results/20261105T015000Z/originals/NC-results-20261103.zip',
    ...['conditional-transitions.json', 'historical-choice-model.json', 'nationwide-scope.json',
      'linked-cohort-audit.json'].map(file => `${modelRoot}/${file}`),
    participationPath, 'public/county-results.json', 'public/participation-results/latest.json',
  ];
  const countyPointer = read('public/county-results.json');
  const districtPointer = read('public/participation-results/latest.json');
  inputs.push(`${countyPointer.party_votes.data_directory}/county-district-candidate-totals.csv.gz`,
    `public/participation-results/${districtPointer.snapshot_id}/margins.json`);
  writeFileSync(`${swingRoot}/inputs.json`, `${JSON.stringify(inputs.map(path => {
    const bytes = readFileSync(path);
    return { path, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') };
  }), null, 2)}\n`);
  return output;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = buildSwingAnalysis();
  console.log(JSON.stringify({ version: result.version, qualification: result.demographic_attribution,
    validation: result.validation }, null, 2));
}

import { loadDataset, checkedDatasetFile } from "./participation-dataset.js";

export const scenarioViews = [
  ["scenario_retaining", "Keep party choice", "synthetic_retaining_share_of_recalled_major_party"],
  ["scenario_switching", "Switch party choice", "synthetic_switching_share_of_recalled_major_party"],
  ["scenario_nonparticipation", "Modeled nonparticipation", "synthetic_nonparticipation_share_of_recalled_major_party"],
];
const partition = ["retaining", "switching", "nonparticipation", "other_choice", "unresolved"]
  .map(name => `synthetic_${name}_share_of_recalled_major_party`);
const dimensions = { overall: "Overall", AGE6: "Age", EDUC: "Education", SEX: "Sex", GENDER3: "Gender",
  RACETH5: "Race / ethnicity", INCOME: "Source income", RUCC: "Source county context" };
const stateCodes = new Set("AK AL AR AZ CA CO CT DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY".split(" "));
export const scenarioDownload = "https://github.com/hanshanley/margin_of_error/releases/download/participation-transition-simulation-20261111-01/complete-analysis.zip";
export const isScenarioView = view => scenarioViews.some(([key]) => key === view);
export const groupIdentity = row => `${row.dimension}|${row.group}`;

function validateEstimate(estimate) {
  const point = estimate?.point, envelope = estimate?.envelope;
  if (!point || !envelope || point.identified_individual_histories !== false
      || point.measured_staying_home !== null)
    throw new Error("Unqualified synthetic estimate");
  for (const key of partition) {
    const value = point[key], range = envelope[key];
    if (!Number.isFinite(value) || value < 0 || value > 1 || !range
        || !Number.isFinite(range.minimum) || !Number.isFinite(range.maximum)
        || range.minimum < 0 || range.maximum > 1 || range.minimum > value + 1e-8
        || range.maximum < value - 1e-8 || range.minimum > range.maximum)
      throw new Error("Invalid synthetic share or assumption envelope");
  }
  if (Math.abs(partition.reduce((sum, key) => sum + point[key], 0) - 1) > 1e-8)
    throw new Error("Gross outcomes do not partition recalled major-party mass");
  if (!Number.isFinite(point.modeled_nonvoter_share) || point.modeled_nonvoter_share < 0
      || point.modeled_nonvoter_share > 1)
    throw new Error("Missing demographic model-class probability");
  for (const field of ["synthetic_no_prior_contest_vote_entry_share_of_current_major_party",
    "synthetic_gross_switching_share_of_modeled_current_voters"])
    if (!Number.isFinite(point[field]) || point[field] < 0 || point[field] > 1)
      throw new Error("Invalid separate current-choice denominator");
}

export function validateScenarios(data) {
  if (data?.schema_version !== 1 || data.status !== "conditional_source_frame_scenarios_not_population_validated"
      || data.source_units_are_people !== false || data.local_allocation !== false
      || data.source_nonvoter_is_administrative_staying_home !== false
      || data.private_joint_cells_reconstructed !== false || data.design_confidence_intervals !== null
      || data.validation?.population_transport_validated !== false
      || data.validation.historical_joint_holdout_passed !== false)
    throw new Error("Unknown or unqualified transition scenario contract");
  const states = Object.keys(data.state_scenarios || {});
  if (states.length !== stateCodes.size || states.some(code => !stateCodes.has(code)))
    throw new Error("Source states differ; D.C. has no sample");
  for (const estimate of Object.values(data.state_scenarios)) validateEstimate(estimate);
  if (!Array.isArray(data.complete_demographic_decisions)
      || data.complete_demographic_decisions.length !== 1530)
    throw new Error("Incomplete demographic decision inventory");
  const identities = new Set();
  for (const row of data.complete_demographic_decisions) {
    const identity = `${row.state_code}|${groupIdentity(row)}`;
    if (identities.has(identity) || (!stateCodes.has(row.state_code) && row.state_code !== "DC")
        || !dimensions[row.dimension] || typeof row.label !== "string")
      throw new Error("Invalid or duplicate demographic identity");
    identities.add(identity);
    if (row.disposition === "selected_broad_source_model") {
      if (row.state_code === "DC") throw new Error("D.C. has no Civic sample");
      validateEstimate(row);
    } else if (row.point !== null || row.envelope !== null)
      throw new Error("Held demographic results must stay unavailable");
  }
  if (!Array.isArray(data.unfitted_return_checks) || data.unfitted_return_checks.length !== 113
      || new Set(data.unfitted_return_checks.map(row => row.id)).size !== 113)
    throw new Error("Incomplete unfitted return checks");
  for (const row of data.unfitted_return_checks) {
    if (row.fitted_to_reported_partisan_counts !== false)
      throw new Error("Reported partisan returns were used for fitting");
    if (row.reported_same_office_change_pp === null) {
      if (row.prior_baseline_alignment_pp !== null || row.reconciliation_residual_pp !== null)
        throw new Error("Unavailable baseline must remain unknown");
    } else if (![row.reported_same_office_change_pp, row.prior_baseline_alignment_pp,
        row.unallocated_return_minus_model_pp, ...Object.values(row.synthetic_components_pp || {})]
      .every(Number.isFinite) || Math.abs(row.reported_same_office_change_pp
        - row.prior_baseline_alignment_pp - row.unallocated_return_minus_model_pp
        - Object.values(row.synthetic_components_pp).reduce((a, b) => a + b, 0)) > 1e-8)
      throw new Error("Synthetic source model does not reconcile the reported swing");
  }
  return data;
}

export function scenarioGroups(data) {
  const groups = new Map();
  for (const row of data.complete_demographic_decisions)
    if (row.point && row.dimension !== "overall") groups.set(groupIdentity(row), {
      key: groupIdentity(row), label: `${dimensions[row.dimension]}: ${row.label}` });
  return [...groups.values()].sort((a, b) => a.label.localeCompare(b.label));
}

export function scenarioEstimate(data, code, view, group = "") {
  const metric = scenarioViews.find(([key]) => key === view);
  if (!metric) throw new Error("Unknown scenario map view");
  const estimate = group ? data.complete_demographic_decisions.find(row =>
    row.state_code === code && groupIdentity(row) === group) : data.state_scenarios[code];
  if (!estimate?.point) return null;
  const field = metric[2];
  return { value: estimate.point[field], ...estimate.envelope[field], point: estimate.point };
}

export function scenarioScale(values) {
  return Math.max(.1, Math.ceil(Math.max(0, ...values.filter(value => value != null)) * 10) / 10);
}

let promise;
export function loadScenarios() {
  promise ||= loadDataset("transition-scenarios-2026").then(async ({ entry, index }) => {
    if (entry.record_contract !== "participation.transition_scenarios.v1"
        || index.contract !== entry.record_contract || index.source_states !== 50
        || index.complete_demographic_decisions !== 1530 || index.local_allocation !== false
        || index.population_transport_validated !== false)
      throw new Error("Scenario index identity or source scope differs");
    return validateScenarios(await checkedDatasetFile(entry.base_url, index.viewer));
  }).catch(error => { promise = null; throw error; });
  return promise;
}

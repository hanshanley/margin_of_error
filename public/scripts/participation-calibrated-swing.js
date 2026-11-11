export const calibratedTerms = [
  ["switching", "Party-choice switching"],
  ["nonparticipation", "No current-contest vote"],
  ["entry", "Entry / return to the contest"],
  ["other_choice", "Other-party choice"],
];
const finite = value => typeof value === "number" && Number.isFinite(value);
const close = (a, b) => finite(a) && finite(b) && Math.abs(a - b) < 1e-8;

export function validateCalibratedSwing(data, legacy) {
  if (data?.contract !== "participation.return_constrained_scenarios.v1"
      || data.fitted_to_both_endpoints !== true || data.identified_histories !== false
      || data.measured_staying_home !== null || data.confidence_intervals !== null
      || data.local_allocation !== false || !Array.isArray(data.rows) || data.rows.length !== 113)
    throw new Error("Unqualified return-constrained scenario dataset");
  const originals = new Map(legacy.rows.map(row => [row.id, row])), result = new Map();
  for (const row of data.rows) {
    const original = originals.get(row.id);
    if (!original || result.has(row.id) || row.office !== original.office || row.state_code !== original.state_code)
      throw new Error("Scenario identity differs from its actual return comparison");
    result.set(row.id, row);
    if (original.reported_comparison.status === "unavailable") {
      if (row.status !== "unavailable" || row.point !== null || row.ranges_pp !== null || !row.reason)
        throw new Error("Missing endpoints must not become fitted zero effects");
      continue;
    }
    if (row.status !== "return_constrained_scenario_not_identified_histories"
        || row.fitted_to_both_reported_candidate_count_endpoints !== true
        || row.calibration_is_not_independent_validation !== true
        || row.population_size_measured !== false || row.measured_staying_home !== null
        || row.confidence_intervals !== null || !row.point)
      throw new Error("An uncalibrated source contrast is not a return attribution");
    const point = row.point, comparison = original.reported_comparison;
    if (!Array.isArray(row.observed_other_vote_endpoints) || row.observed_other_vote_endpoints.length !== 2
        || row.observed_other_vote_endpoints.some((value, i) =>
          value !== (comparison[i ? "current" : "previous"].O !== undefined)))
      throw new Error("Unreported Other votes cannot become observed zeros");
    if (!close(point.previous_margin_pp, comparison.previous_margin_pp)
        || !close(point.current_margin_pp, comparison.current_margin_pp)
        || !close(point.reported_change_pp, comparison.reported_change_pp)
        || !close(calibratedTerms.reduce((sum, [key]) => sum + point.components_pp[key], 0),
          comparison.reported_change_pp))
      throw new Error("Both reported election endpoints must reconcile");
    if (!finite(point.assumed_common_frame_units) || point.assumed_common_frame_units <= 0
        || !Array.isArray(point.synthetic_joint) || point.synthetic_joint.length !== 4
        || point.synthetic_joint.some(values => values.length !== 4 || values.some(value => !finite(value) || value < 0))
        || !close(point.synthetic_joint.flat().reduce((a, b) => a + b, 0), 1))
      throw new Error("Invalid nonnegative common-frame transition table");
    for (let i = 0; i < 4; i++) {
      if (!close(point.synthetic_joint[i].reduce((a, b) => a + b, 0), point.target_rows[i])
          || !close(point.synthetic_joint.reduce((sum, values) => sum + values[i], 0), point.target_columns[i]))
        throw new Error("Transition rows or columns do not match their endpoints");
    }
    for (const [period, target] of [["previous", point.target_rows], ["current", point.target_columns]]) {
      for (const [i, party] of ["D", "R", "O"].entries()) {
        const count = comparison[period][party];
        if (count !== undefined && Math.abs(target[i] * point.assumed_common_frame_units - count) > .0001)
          throw new Error("Scenario substituted different candidate counts");
      }
    }
    for (const [key] of calibratedTerms) {
      const range = row.ranges_pp[key], value = point.components_pp[key];
      if (!finite(value) || !finite(range?.minimum) || !finite(range?.maximum)
          || range.minimum > value + 1e-8 || range.maximum < value - 1e-8)
        throw new Error("Invalid scenario assumption sensitivity");
    }
    const gross = Object.values(point.gross_shares_of_modeled_previous_major_party);
    if (gross.length !== 4 || gross.some(value => !finite(value) || value < 0 || value > 1)
        || !close(gross.reduce((a, b) => a + b, 0), 1))
      throw new Error("Gross outcomes do not partition prior major-party mass");
  }
  return result;
}

export function calibratedMapValue(row, key) {
  if (!row?.point) return null;
  return row.point.components_pp[key === "modeled_nonparticipation" ? "nonparticipation" : key] ?? null;
}

export function roundedContributions(point) {
  const total = Math.round(Number(point.reported_change_pp.toFixed(2)) * 100);
  const values = calibratedTerms.map(([key]) => ({ key, scaled: point.components_pp[key] * 100 }));
  const rounded = Object.fromEntries(values.map(({ key, scaled }) => [key, Math.floor(scaled)]));
  const remaining = total - Object.values(rounded).reduce((a, b) => a + b, 0);
  if (remaining < 0 || remaining > values.length) throw new Error("Invalid sum-preserving rounding");
  values.sort((a, b) => (b.scaled - Math.floor(b.scaled)) - (a.scaled - Math.floor(a.scaled)));
  for (let i = 0; i < remaining; i++) rounded[values[i].key]++;
  return Object.fromEntries(Object.entries(rounded).map(([key, value]) => [key, value / 100]));
}

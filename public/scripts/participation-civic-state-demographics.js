export const civicStateSource = {
  url: "https://raw.githubusercontent.com/hanshanley/voter-participation/83c072e58680e74ce57a34748c813549d99ef5da/data/civic-group-rates/20261127-01/viewer-data.json",
  sha256: "102d580b05c9c048a404df31b667fcd6b38e5196ea4be71ab31523dd47efd335",
  release: "https://raw.githubusercontent.com/hanshanley/voter-participation/83c072e58680e74ce57a34748c813549d99ef5da/data/civic-group-rates/20261127-01/",
};
export const civicDimensions = [
  ["overall", "Overall"], ["age", "Age"], ["sex", "Source sex"], ["gender", "Source gender · held"],
  ["education", "Education"], ["race", "Race / Hispanic origin"],
  ["income", "Income · source bins"], ["county_context", "County type · source context"],
];
const dimensions = { overall: "overall", age: "AGE6", sex: "SEX", gender: "GENDER3",
  education: "EDUC", race: "RACETH5", income: "INCOME", county_context: "RUCC" };

export function validateCivicStates(data) {
  const rounded = data?.schema === "civic-state-demographics-v2";
  if ((!rounded && data?.schema !== "civic-state-demographics-v1") || data.year !== 2026
    || data.status !== "source_weighted_modeled_participation_not_observed_turnout"
    || data.field_period !== null || data.weight_target_and_calibration !== null
    || data.groups?.length !== 1530)
    throw new Error("Incomplete or changed 2026 source model");
  if (rounded && (data.publication?.format !== "rounded_rates_without_new_count_or_weight_primitives"
    || data.publication.resolution_pp !== "0.1" || data.publication.minimum_source_cases !== 100
    || data.publication.minimum_each_model_class !== 30 || data.publication.new_subgroup_counts_or_weights_exported !== false
    || data.publication.standalone_unknown_categories_released !== false || data.publication.gender3_released !== false))
    throw new Error("Changed rate-only publication safeguards");
  const keys = new Set(), states = new Set();
  for (const row of data.groups) {
    const key = [row.state_code, row.dimension, row.group].join("|");
    if (keys.has(key) || row.year !== 2026 || !Object.values(dimensions).includes(row.dimension)
      || row.population_representativeness_qualified !== false || row.administratively_observed_turnout !== false
      || row.local_allocation !== false || row.design_confidence_interval !== null
      || row.eligible_or_registered_group_population !== null || row.estimated_group_participants !== null
      || row.measured_staying_home !== null)
      throw new Error("Changed model frame, privacy or population claim");
    keys.add(key); states.add(row.state_code);
    const selected = row.disposition === "selected_broad_source_model";
    if (selected) {
      if (row.state_code === "DC" || row.dimension === "GENDER3" || row.group === "unknown"
        || (rounded ? row.n !== null || row.source_weight_concentration_effective_n !== null
          || !/^\d{1,3}\.\d$/.test(row.modeled_voter_pct) || !/^\d{1,3}\.\d$/.test(row.modeled_nonvoter_pct)
          : !Number.isInteger(row.n) || row.n < 100) || row.modeled_voter_pct === null || row.modeled_nonvoter_pct === null
        || ![row.modeled_voter_pct, row.modeled_nonvoter_pct].every(value =>
          Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 100)
        || Math.abs(Number(row.modeled_voter_pct) + Number(row.modeled_nonvoter_pct) - 100) > 1e-10)
        throw new Error("Invalid model fraction or source support");
    } else if (row.n !== null || row.modeled_voter_pct !== null || row.modeled_nonvoter_pct !== null
      || !["no_dc_source_sample", "held_source_support_or_complementary_disclosure",
        "held_cross_dimension_disclosure"].includes(row.disposition))
      throw new Error("Held model cell must remain unavailable, not zero");
  }
  if (states.size !== 51 || !states.has("DC")) throw new Error("Missing state query");
  return data;
}

export async function loadCivicStates() {
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(civicStateSource.url, { signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const bytes = await response.arrayBuffer();
    const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
      .map(value => value.toString(16).padStart(2, "0")).join("");
    if (digest !== civicStateSource.sha256) throw new Error("2026 model source checksum mismatch");
    return validateCivicStates(JSON.parse(new TextDecoder().decode(bytes)));
  } finally { clearTimeout(timer); }
}

export function civicStateRows(data, code, dimension) {
  return data.groups.filter(row => row.state_code === code && row.dimension === dimensions[dimension]);
}

export function civicGroupOptions(data, dimension) {
  return data.groups.filter(row => row.state_code === "AL" && row.dimension === dimensions[dimension])
    .map(row => [row.group, row.label]);
}

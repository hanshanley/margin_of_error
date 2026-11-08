export const demographicStates = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(" ");
const groups = {
  overall: ["All"],
  age_group: ["18 to 24 Years", "25 to 44 Years", "45 to 64 Years", "65 Years and Over"],
  sex: ["Female", "Male"],
  education: ["Less than 9th grade", "9th\u201312th grade, no diploma", "High school / GED",
    "Some college / associate's degree", "Bachelor's degree or more"],
  race_ethnicity: ["White, non-Hispanic", "Black, non-Hispanic", "Asian, non-Hispanic",
    "Hispanic, any race", "Other, non-Hispanic"],
};
export const demographicSource = {
  url: "https://raw.githubusercontent.com/hanshanley/voter-participation/8910486e113366ca3d6db884ddebdef21b5ea21b/data/cps-state-demographics/20261108-01/viewer-data.json",
  sha256: "9fde18b387be28cf8f8c35e675db6c451cafa193bbfd654ba479b2b32c2dddbd",
  release: "https://github.com/hanshanley/margin_of_error/releases/download/participation-cps-state-demographics-20261108-01/",
};
const sourceDimension = dimension => ({ age: "age_group", race: "race_ethnicity" }[dimension] || dimension);

export function demographicGroups(dimension) {
  return groups[sourceDimension(dimension)] || [];
}

export function validateDemographics(data) {
  if (data?.schema !== "cps-state-demographics-v1" || data.rows?.length !== 1734)
    throw new Error("Incomplete state demographic source");
  const keys = new Set();
  for (const row of data.rows) {
    const key = [row.year, row.state_code, row.dimension, row.group].join("|");
    if (!["2022", "2024"].includes(row.year) || !demographicStates.includes(row.state_code)
      || !groups[row.dimension]?.includes(row.group) || keys.has(key)
      || row.population_frame !== "civilian_noninstitutionalized_adult_citizens"
      || ["estimated_2026_turnout", "administratively_observed_turnout", "local_allocation",
        "observed_staying_home", "design_based_confidence_interval_available"].some(field => row[field] !== "False")
      || row.registered_voter_population_count !== "" || row.legal_eligibility !== "")
      throw new Error("Changed state demographic frame or duplicate cell");
    keys.add(key);
    const total = Number(row.citizen_weight_units);
    const yes = Number(row.reported_voter_weight_units), no = Number(row.reported_nonvoter_weight_units);
    const unknown = Number(row.unknown_weight_units), n = Number(row.sample_n);
    if (![total, yes, no, unknown, n].every(value => Number.isSafeInteger(value) && value >= 0)
      || total !== yes + no + unknown || row.raw_case_count_under_30_diagnostic !== (n > 0 && n < 30 ? "True" : "False"))
      throw new Error("Changed state demographic denominator or support");
    for (const [field, numerator] of [["reported_voting_pct", yes], ["reported_nonvoting_pct", no], ["unknown_pct", unknown]]) {
      if (total ? row[field] === "" || !Number.isFinite(Number(row[field]))
          || Math.abs(Number(row[field]) - 100 * numerator / total) > 1e-10
        : row[field] !== "")
        throw new Error("Changed state demographic rate or absent cell");
    }
  }
  return data;
}

export async function loadDemographics() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(demographicSource.url, { signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const bytes = await response.arrayBuffer();
    const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
      .map(value => value.toString(16).padStart(2, "0")).join("");
    if (digest !== demographicSource.sha256) throw new Error("State demographic checksum mismatch");
    return validateDemographics(JSON.parse(new TextDecoder().decode(bytes)));
  } finally {
    clearTimeout(timer);
  }
}

export function demographicRows(data, code, dimension, group) {
  return data.rows.filter(row => row.state_code === code && row.dimension === sourceDimension(dimension)
    && (!group || group === "All groups" || row.group === group))
    .map(row => ({ ...row, year: Number(row.year), series: row.group,
      turnout_pct: row.reported_voting_pct === "" ? null : Number(row.reported_voting_pct),
      sample_n: Number(row.sample_n), unknown_response: row.unknown_pct === "" ? "Not available" : Number(row.unknown_pct).toFixed(1) + "%",
      low_n: row.raw_case_count_under_30_diagnostic === "True", denominator: "cvap",
      warnings: [row.raw_case_count_under_30_diagnostic === "True" ? "Small sample: descriptive estimate only; no design confidence interval."
        : "Source-weighted self-report; no design confidence interval.",
      ...(!row.citizen_weight_units || row.citizen_weight_units === "0" ? ["No observed source cell, not zero participation."] : [])] }));
}

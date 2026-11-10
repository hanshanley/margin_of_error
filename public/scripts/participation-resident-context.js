import { loadDataset, checkedDatasetFile } from "./participation-dataset.js";

const nameKey = value => String(value || "").toUpperCase()
  .replace(/\b(COUNTY|PARISH|BOROUGH|CENSUS AREA)\b/g, "").replace(/[^A-Z0-9]/g, "");
const fmt = value => value == null ? "Not available" : value > 0 && value < 1 ? "<1"
  : value.toLocaleString("en-US", { maximumFractionDigits: 0 });
const pct = value => value == null ? "Not available" : value > 0 && value < 0.1 ? "<0.1%" : value.toFixed(1) + "%";
const element = (tag, text = "", className = "") => {
  const node = document.createElement(tag); node.textContent = text; node.className = className; return node;
};

export function countyForSource(counties, row, code) {
  if (row?.state_code !== code || !["county", "county_equivalent", "independent_city"].includes(row.geography_level))
    return null;
  const matches = counties.filter(county => county.state_code === code && county.name_keys.includes(nameKey(row.county)));
  if (matches.length !== 1) return null;
  const match = matches[0];
  if (row.county_fips && row.county_fips !== match.geography.census_geoid) return null;
  return match;
}

export function precinctForReference(data, key, referenceHash) {
  if (!referenceHash || referenceHash !== data.precinct_source?.sha256) return null;
  const matches = data.precincts.filter(row => row.geography.reference_key === key);
  return matches.length === 1 ? matches[0] : null;
}

export function validateResidentShard(data, code, declared) {
  if (data?.contract !== "geographic.resident_context.v1" || data.state_code !== code
      || data.resident_context_not_voter_data !== true || data.counties?.length !== declared.counties
      || !Array.isArray(data.precincts) || data.precincts.length !== declared.precincts)
    throw new Error("Resident context contract or coverage differs");
  const keys = new Set();
  for (const row of data.counties) {
    const key = row.geography?.census_geoid;
    if (row.state_code !== code || !/^\d{5}$/.test(key) || keys.has(key)
        || row.map_join?.feature_key !== key || row.geography.level !== "county"
        || row.map_join.status !== "approved_context_identity"
        || row.map_join.certified_election_boundary !== false
        || row.map_join.reference_year !== row.geography.source_geography_vintage
        || row.resident_composition_is_not_voter_composition !== true)
      throw new Error("Unqualified resident county identity");
    keys.add(key);
  }
  keys.clear();
  for (const row of data.precincts) {
    const key = row.geography?.reference_key;
    if (row.state_code !== code || !key || keys.has(key) || row.geography.level !== "precinct_reference"
        || row.resident_composition_is_not_voter_composition !== true
        || row.source_geometry_repaired !== false || row.voter_participation_rate !== null
        || !data.precinct_source?.sha256)
      throw new Error("Unqualified conditional resident reference");
    keys.add(key);
  }
  return data;
}

export function incomeLabel(row) {
  const band = row.modeled_income_median_band;
  if (row.geography.level === "precinct_reference") {
    if (band?.status !== "modeled_income_bin_interval_not_exact_median") return "Not available";
    if (band.upper_bound == null && band.lower_bound != null) return `$${fmt(band.lower_bound)} or more`;
    if (band.lower_bound == null && band.upper_bound != null) return `Below $${fmt(band.upper_bound)}`;
    if (band.lower_bound != null && band.upper_bound != null)
      return `$${fmt(band.lower_bound)}–$${fmt(band.upper_bound)}`;
    return "Not available";
  }
  const income = row.median_household_income;
  if (income.estimate != null) return "$" + fmt(income.estimate);
  if (income.bounded && income.lower_bound != null) return `$${fmt(income.lower_bound)} or more`;
  if (income.bounded && income.upper_bound != null) return `Below $${fmt(income.upper_bound)}`;
  return "Not available";
}

export function installResidentContext(host = document.getElementById("resident-context")) {
  if (!host) return { hide() {}, setState() {}, selectSource() {}, selectCounty() {}, selectPrecinct() {} };
  const controls = host.querySelector("[data-resident-controls]");
  const detail = host.querySelector("[data-resident-detail]"), select = host.querySelector("select");
  let datasetPromise, activeCode = "", activeName = "", activeScope = "", choice = null, generation = 0;
  const shards = new Map();
  const dataset = () => datasetPromise ||= loadDataset("resident-context").catch(error => {
    datasetPromise = null; throw error;
  });
  async function shard(code) {
    if (!shards.has(code)) shards.set(code, dataset().then(async ({ entry, index }) => {
      if (index.contract !== "geographic.resident_context.v1" || index.resident_context_not_voter_data !== true)
        throw new Error("Unqualified resident index");
      const declaration = index.states[code];
      if (!declaration) throw new Error("No resident context for this state");
      return validateResidentShard(await checkedDatasetFile(entry.base_url, declaration), code, declaration);
    }).catch(error => { shards.delete(code); throw error; }));
    return shards.get(code);
  }
  function clearIdentity() {
    delete detail.dataset.censusGeoid; delete detail.dataset.referenceKey; delete detail.dataset.contextStatus;
  }
  function failure(error) {
    clearIdentity();
    detail.replaceChildren(element("p", `${error.message}. No resident values inferred; participation observations are unchanged.`),
      element("button", "Retry resident context"));
    detail.querySelector("button").addEventListener("click", () => update(activeCode, activeName, choice));
  }
  function definition(label, value, note = "") {
    const group = element("div", "", "resident-stat");
    group.append(element("dt", label), element("dd", value));
    if (note) group.append(element("p", note, "caption"));
    return group;
  }
  function render(row, data, entry) {
    clearIdentity();
    const conditional = row.geography.level === "precinct_reference", income = row.median_household_income;
    const stats = element("dl", "", "resident-stats");
    stats.append(definition(conditional ? "Estimated median income band" : "Median household income", incomeLabel(row),
      conditional ? `${data.income_dollar_year} dollars; income-bin interval, not an exact median or confidence interval.`
        : `${data.income_dollar_year} dollars; published MOE ${income.margin_of_error == null ? "not available" : "$" + fmt(income.margin_of_error)}.`),
      definition(conditional ? "Estimated residents" : "Residents", fmt(row.resident_population.estimate),
        conditional ? "Conditional block-weighted estimate; no derived MOE."
          : `Published population MOE: ${fmt(row.resident_population.margin_of_error)}.`),
      definition("Bachelor's degree or higher", pct(row.education.bachelors_or_higher_pct),
        `${fmt(row.education.source_total ?? row.education.estimated_universe)} residents age 25+; percentage MOE not calculated.`));
    const race = element("details"), table = element("table"), body = element("tbody");
    const head = element("thead"), headings = element("tr");
    for (const text of ["Race / Hispanic origin", conditional ? "Estimated residents" : "Residents", "Share",
      ...(conditional ? [] : ["Count MOE"])])
      headings.append(element("th", text));
    head.append(headings); table.append(head);
    for (const group of row.race_ethnicity.groups) {
      const tr = element("tr");
      tr.append(element("th", group.label), element("td", fmt(group.estimate)),
        element("td", pct(group.percent)));
      if (!conditional) tr.append(element("td", fmt(group.margin_of_error)));
      body.append(tr);
    }
    table.append(body);
    const wrap = element("div", "", "table-wrap"); wrap.append(table);
    race.append(element("summary", "Race / ethnicity"), wrap,
      element("p", "Exclusive non-Hispanic racial groups and Hispanic / Latino of any race. These describe residents, not voters; percentage MOEs are not calculated.", "caption"));
    const age = element("dl", "", "resident-stats resident-ages");
    const ageNames = { under18: "Under 18", "18_64": "Age 18–64", "65plus": "Age 65+" };
    for (const group of row.age.groups) age.append(definition(ageNames[group.id], pct(group.percent)));
    const complete = element("a", "Complete resident inputs, code and queries (ZIP)");
    complete.href = entry.complete_download.url; complete.className = "source-link";
    detail.replaceChildren(element("h3", row.name), element("p",
      `ACS ${data.source_period} resident context; not a ${document.getElementById("year")?.value || "current"} voter profile or group turnout rate.`,
      "caption"), stats, age, race, complete);
    detail.dataset.contextStatus = row.context_status;
    if (conditional) {
      detail.dataset.referenceKey = row.geography.reference_key;
      const assumptions = element("details");
      assumptions.append(element("summary", "How this local estimate is made"),
        element("p", "Conditional local estimate using 2020 block population / housing-unit proxies and 2020–2024 ACS block-group composition. Code equivalence and within-group composition are assumptions; boundary ties stay unallocated. No source geometry is repaired or state survey estimate assigned locally.", "caption"));
      detail.append(assumptions);
    } else {
      detail.dataset.censusGeoid = row.geography.census_geoid;
      detail.append(element("p", `Native ${row.map_join.reference_year} Census county reference; matching the county code does not establish election-year boundary equivalence.`, "caption"));
    }
    if (row.conflicts.length) detail.append(element("p",
      "Source disagreements remain in the full queries; values are not repaired.", "caption"));
  }
  async function update(code, name = code, selection = null) {
    if (!code) return;
    const token = ++generation;
    activeCode = code; activeName = name; choice = selection; host.hidden = false;
    select.disabled = true;
    clearIdentity();
    detail.replaceChildren(element("p", "Loading resident context…", "caption"));
    try {
      const [data, { entry }] = await Promise.all([shard(code), dataset()]);
      if (token !== generation) return;
      host.dataset.datasetVersion = entry.version;
      select.replaceChildren(new Option("Choose a Census county / equivalent…", ""),
        ...data.counties.map(row => new Option(row.name, row.geography.census_geoid)));
      controls.hidden = false;
      select.disabled = false;
      let row;
      if (selection?.kind === "county")
        row = data.counties.find(value => value.geography.census_geoid === selection.key);
      else if (selection?.kind === "source") row = countyForSource(data.counties, selection.row, code);
      else if (selection?.kind === "precinct")
        row = precinctForReference(data, selection.key, selection.referenceHash);
      select.value = row?.geography.census_geoid || "";
      if (row) render(row, data, entry);
      else detail.replaceChildren(element("p", selection
        ? "No qualified resident profile for this selected reference. County values are not assigned to a precinct or municipality; choose a Census county separately for county context."
        : `Choose a county in ${activeName || code}, or select a place on the map. All ${data.counties.length} native Census counties / equivalents are available independently of participation coverage.`, "caption"));
    } catch (error) { if (token === generation) failure(error); }
  }
  select.addEventListener("change", () => update(activeCode, activeName,
    select.value ? { kind: "county", key: select.value } : null));
  return {
    hide() { ++generation; host.hidden = true; },
    setState(code, name = code, scope = "") {
      const previous = code === activeCode && scope === activeScope ? choice : null;
      activeScope = scope;
      return update(code, name, previous);
    },
    selectCounty(key, code) { return update(code, code === activeCode ? activeName : code, { kind: "county", key }); },
    selectSource(row) { return update(row.state_code, row.state_code === activeCode ? activeName : row.state_code,
      { kind: "source", row }); },
    selectPrecinct(row, metadata = {}) { return update(row.state_code, row.state_code === activeCode ? activeName : row.state_code,
      { kind: "precinct", key: row.key || row.unit_key, referenceHash: metadata.sha256 || metadata.geometry_sha256 }); },
  };
}

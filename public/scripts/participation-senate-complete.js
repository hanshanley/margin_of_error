import { calibratedTerms, validateCalibratedSwing } from "./participation-calibrated-swing.js";
import { loadAutomaticSenateComplete } from "./participation-automatic-runtime.js";

const key = "RI-senate-87396";
const scope = "complete_reported_DRO_candidate_universe_not_ballots_or_turnout";
const fresh = row => row.status.startsWith("fresh_");
const statuses = new Set(["fresh_complete_scenario", "fresh_unchanged_complete_scenario",
  "held_retain_last_good_complete_scenario", "held_no_compatible_complete_bridge"]);
const close = (a, b) => Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) < 1e-8;

export function validateSenateComplete(data, legacy, calibration) {
  const originals = new Map(calibration.rows.filter(row => row.office === "senate" && row.point)
    .map(row => [row.id, row]));
  if (data?.contract !== "participation.senate_complete_category_scenarios.v1"
      || data.review_version !== "20261118-01" || data.source_models_refitted !== false
      || data.measured_staying_home !== null || data.confidence_intervals !== null
      || data.local_allocation !== false || originals.size !== 26
      || !Array.isArray(data.rows) || data.rows.length !== originals.size)
    throw new Error("Unreviewed complete Senate scenario contract");
  const result = new Map();
  for (const row of data.rows) {
    const old = originals.get(row.id);
    if (!old || result.has(row.id) || row.office !== old.office || row.state_code !== old.state_code
        || !statuses.has(row.status) || !Array.isArray(row.holds)
        || row.holds.some(reason => typeof reason !== "string" || !reason)
        || row.strict_legacy_model_refreshed !== fresh(row)
        || fresh(row) === Boolean(row.holds.length))
      throw new Error("Complete Senate identity, status or hold differs");
    result.set(row.id, row);
    if (row.model === null) {
      if (row.status !== "held_no_compatible_complete_bridge"
          || row.model_source_clock !== null || row.official_evidence_clock !== null
          || row.official_source !== null)
        throw new Error("Missing complete model must remain held");
      continue;
    }
    const model = row.model, comparison = model?.reported_comparison;
    const frame = row.current_identity;
    if (row.id !== key || row.status === "held_no_compatible_complete_bridge"
        || model.id !== row.id || model.state_code !== row.state_code || model.office !== "senate"
        || model.separately_versioned_complete_extension !== true
        || model.current_unreported_other_unknown !== false
        || model.complete_candidate_universe_qualified !== true || model.senate_respondent_model !== false
        || model.source_models_refitted !== false || !model.limitation || row.conditioning_scope !== scope
        || comparison?.current_source_scope !== scope
        || comparison?.current_native_clock !== row.model_source_clock
        || [row.model_source_clock, row.official_evidence_clock].some(value =>
          typeof value !== "string" || !Number.isFinite(Date.parse(value)) || !/(?:Z|\+00:00)$/.test(value))
        || !Number.isSafeInteger(row.official_source?.bytes) || row.official_source.bytes < 1
        || !/^[a-f0-9]{64}$/.test(row.official_source.sha256)
        || row.official_source.url !== "https://electionresults.ri.gov/results/public/api/elections/rhodeisland/2026StatewideGeneralElection/data"
        || JSON.stringify(model.observed_other_vote_endpoints) !== "[true,true]"
        || ["D", "R", "O"].some(party => !Number.isSafeInteger(comparison.current[party])
          || comparison.current[party] < 0
          || comparison.previous[party] !== old.reported_comparison.previous[party])
        || ["status", "baseline_year", "baseline_office", "baseline_stage", "scope"].some(
          name => comparison[name] !== old.reported_comparison[name])
        || comparison.current_stage !== "general" || comparison.current_round !== null
        || !frame || Object.entries({
          chamber: "senate", state_code: "RI", seat: "2", election_date: "2026-11-03",
          election_kind: "regular", stage: "general", ranked_choice: false, round: "not_ranked",
          id: "npr:senate:RI:2:regular:general:not_ranked",
        }).some(([name, value]) => frame[name] !== value)
        || !Array.isArray(model.complete_scenarios) || model.complete_scenarios.length !== 9)
      throw new Error("Complete Other, same-seat history or transported Senate prior differs");
    const comparisonData = { ...legacy, rows: legacy.rows.map(value =>
      value.id === row.id ? { ...value, reported_comparison: comparison } : value) };
    const validate = point => validateCalibratedSwing({
      ...calibration, rows: calibration.rows.map(value => value.id === row.id ? { ...model, point } : value),
    }, comparisonData);
    validate(model.point);
    const pairs = new Set();
    for (const scenario of model.complete_scenarios) {
      if (![.5, 1, 2].includes(scenario.persistence_scale) || ![.8, 1, 1.25].includes(scenario.frame_scale))
        throw new Error("Unreviewed complete Senate sensitivity assumption");
      pairs.add(`${scenario.persistence_scale}|${scenario.frame_scale}`);
      validate(scenario);
    }
    if (pairs.size !== 9 || !model.complete_scenarios.some(value => JSON.stringify(value) === JSON.stringify(model.point)))
      throw new Error("Incomplete complete Senate sensitivity or point");
    for (const [name] of calibratedTerms) {
      const values = model.complete_scenarios.map(value => value.components_pp[name]);
      if (!close(model.ranges_pp[name].minimum, Math.min(...values))
          || !close(model.ranges_pp[name].maximum, Math.max(...values)))
        throw new Error("Complete Senate sensitivity differs from its scenarios");
    }
  }
  const summary = data.summary, current = data.rows.filter(fresh).length;
  if (!summary || summary.legacy_fitted_decisions !== 26 || summary.fresh_complete_scenarios !== current
      || summary.retained_complete_scenarios !== data.rows.filter(
        row => row.status === "held_retain_last_good_complete_scenario").length
      || summary.fresh_sensitivity_fits !== 9 * current
      || summary.strict_legacy_models_refreshed !== current || summary.empirical_senate_models_added !== 0)
    throw new Error("Complete Senate coverage differs from its decisions");
  return result;
}

const node = (tag, text, className = "") => {
  const value = document.createElement(tag);
  if (text != null) value.textContent = text;
  value.className = className;
  return value;
};
const pp = value => `${value > 0 ? "+" : ""}${value.toFixed(2)} pp`;

export function senateCompleteController(legacy, calibration, load = loadAutomaticSenateComplete) {
  let pending;
  return function render(id, detail) {
    if (id !== key) return;
    const section = node("section");
    section.dataset.senateComplete = id;
    section.setAttribute("aria-live", "polite");
    section.append(node("p", "Checking the complete-candidate Senate extension.", "caption"));
    detail.prepend(section);
    if (!pending) pending = load().then(value => value && ({
      ...value, decisions: validateSenateComplete(value.data, legacy, calibration),
    })).catch(error => { pending = null; throw error; });
    pending.then(value => {
      if (!section.isConnected) return;
      const row = value?.decisions.get(id);
      if (!row?.model) { section.remove(); return; }
      for (const partial of detail.querySelectorAll("[data-senate-partial]"))
        if (partial.dataset.senatePartial === id) partial.remove();
      section.dataset.status = row.status;
      section.replaceChildren(node("h4", "Current complete-category Senate scenario"),
        node("p", `${fresh(row) ? "Compatible current report" : "Held update; last-good scenario retained"}. `
          + `National count clock: ${row.model_source_clock}; official inventory clock: ${row.official_evidence_clock}. `
          + row.holds.join("; "), "caption"),
        node("p", "Full reported D/R/Other candidate universe, including the independent candidate and write-ins; "
          + "reviewed regular Class II seat and 2020 Senate baseline. "
          + "Transported President/House synthetic associations, not a Senate respondent fit, turnout or measured staying home. "
          + "The dated archived map remains unchanged.", "caption"));
      const table = node("table"), body = node("tbody"), head = node("thead"), headings = node("tr");
      table.append(node("caption", "Separate complete extension · D−R margin contributions; nine assumptions, not confidence intervals"));
      for (const label of ["Term", "Contribution", "Assumption sensitivity"]) headings.append(node("th", label));
      head.append(headings); table.append(head);
      for (const [name, label] of calibratedTerms) {
        const tr = node("tr"), th = node("th", label), model = row.model, range = model.ranges_pp[name];
        th.scope = "row"; tr.dataset.term = name; tr.dataset.value = model.point.components_pp[name];
        tr.append(th, node("td", pp(model.point.components_pp[name]), "numeric"),
          node("td", `${pp(range.minimum)} to ${pp(range.maximum)}`, "numeric"));
        body.append(tr);
      }
      table.append(body);
      const wrapper = node("div", null, "table-wrap"); wrapper.append(table); section.append(wrapper);
      const link = node("a", "Complete current analysis: native facts, priors, all decisions, scenarios, cells and code · ZIP");
      link.href = value.manifest.complete_download.url; section.append(link);
    }).catch(() => {
      if (!section.isConnected) return;
      section.replaceChildren(node("p", "Complete-category update unavailable; dated archived and partial results are retained.", "caption"));
      const retry = node("button", "Retry complete Senate scenario"); retry.type = "button";
      retry.addEventListener("click", () => { section.remove(); render(id, detail); });
      section.append(retry);
    });
  };
}

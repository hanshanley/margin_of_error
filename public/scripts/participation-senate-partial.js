import { calibratedTerms, validateCalibratedSwing } from "./participation-calibrated-swing.js";
import { loadAutomaticSenatePartial } from "./participation-automatic-runtime.js";

const contract = "participation.senate_legacy_partial_scenarios.v1";
const reviewedModels = new Map([
  ["20261117-01", new Set(["AL-senate-86907"])],
  ["20261117-02", new Set(["AL-senate-86907", "NM-senate-87288"])],
]);
const fresh = row => row.status.startsWith("fresh_");
const statuses = new Set(["fresh_partial_scenario", "fresh_unchanged_partial_scenario",
  "held_retain_last_good_partial_scenario", "held_no_compatible_partial_bridge"]);
const close = (a, b) => Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) < 1e-8;

export function validateSenatePartial(data, legacy, calibration) {
  const original = new Map(calibration.rows.filter(row => row.office === "senate" && row.point)
    .map(row => [row.id, row]));
  const approved = reviewedModels.get(data?.review_version);
  if (data?.contract !== contract || !approved
      || data.source_models_refitted !== false || data.measured_staying_home !== null
      || data.confidence_intervals !== null || data.local_allocation !== false
      || data.complete_candidate_universe_qualified !== false || !Array.isArray(data.rows)
      || original.size !== 26 || data.rows.length !== original.size)
    throw new Error("Unreviewed partial Senate scenario contract");
  const result = new Map();
  for (const row of data.rows) {
    const old = original.get(row.id);
    if (!old || result.has(row.id) || row.office !== old.office || row.state_code !== old.state_code
        || !statuses.has(row.status) || !Array.isArray(row.holds)
        || row.holds.some(reason => typeof reason !== "string" || !reason)
        || row.strict_legacy_model_refreshed !== false
        || fresh(row) === Boolean(row.holds.length))
      throw new Error("Partial Senate identity, status or hold differs");
    result.set(row.id, row);
    if (row.model === null) {
      if (row.status !== "held_no_compatible_partial_bridge" || row.model_source_clock !== null)
        throw new Error("Missing partial model must remain held");
      continue;
    }
    const model = row.model, comparison = model?.reported_comparison;
    if (row.status === "held_no_compatible_partial_bridge"
        || !approved.has(row.id) || model.id !== row.id || model.state_code !== row.state_code
        || model.office !== "senate" || model.separately_versioned_partial_extension !== true
        || model.current_unreported_other_unknown !== true
        || model.complete_candidate_universe_qualified !== false || model.senate_respondent_model !== false
        || model.source_models_refitted !== false || !model.limitation
        || row.conditioning_scope !== "reported_DR_only_current_O_unknown"
        || comparison?.current_source_scope !== "reported_DR_only_not_complete_candidate_or_ballot_universe"
        || comparison?.current_native_clock !== row.model_source_clock
        || typeof row.model_source_clock !== "string"
        || !Number.isFinite(Date.parse(row.model_source_clock))
        || !Array.isArray(model.observed_other_vote_endpoints)
        || JSON.stringify(model.observed_other_vote_endpoints) !== "[true,false]"
        || Object.hasOwn(comparison.current, "O")
        || ["status", "baseline_year", "baseline_office", "baseline_stage", "scope"].some(
          key => comparison[key] !== old.reported_comparison[key])
        || comparison.current_stage !== "general" || comparison.current_round !== null
        || ["D", "R", "O"].some(party => comparison.previous[party] !== old.reported_comparison.previous[party])
        || !Array.isArray(model.complete_scenarios) || model.complete_scenarios.length !== 9)
      throw new Error("Unknown Other or transported Senate prior was misrepresented");
    const compare = { ...legacy, rows: legacy.rows.map(value => value.id === row.id
      ? { ...value, reported_comparison: comparison } : value) };
    const validate = point => validateCalibratedSwing({ ...calibration, rows: calibration.rows.map(value =>
      value.id === row.id ? { ...model, point } : value) }, compare);
    validate(model.point);
    const pairs = new Set();
    for (const scenario of model.complete_scenarios) {
      if (![.5, 1, 2].includes(scenario.persistence_scale) || ![.8, 1, 1.25].includes(scenario.frame_scale))
        throw new Error("Unreviewed Senate sensitivity assumptions");
      pairs.add(`${scenario.persistence_scale}|${scenario.frame_scale}`);
      validate(scenario);
    }
    if (pairs.size !== 9 || !model.complete_scenarios.some(value => JSON.stringify(value) === JSON.stringify(model.point)))
      throw new Error("Incomplete Senate sensitivity or point scenario");
    for (const [key] of calibratedTerms) {
      const values = model.complete_scenarios.map(value => value.components_pp[key]);
      if (!close(model.ranges_pp[key].minimum, Math.min(...values))
          || !close(model.ranges_pp[key].maximum, Math.max(...values)))
        throw new Error("Senate sensitivity differs from complete scenarios");
    }
  }
  const summary = data.summary;
  if (!summary || summary.legacy_fitted_decisions !== 26
      || summary.fresh_partial_scenarios !== data.rows.filter(fresh).length
      || summary.retained_partial_scenarios !== data.rows.filter(
        row => row.status === "held_retain_last_good_partial_scenario").length
      || summary.fresh_sensitivity_fits !== 9 * data.rows.filter(fresh).length
      || summary.empirical_senate_models_added !== 0 || summary.strict_legacy_models_refreshed !== 0)
    throw new Error("Partial Senate coverage differs from its decisions");
  return result;
}

const node = (tag, text, className = "") => {
  const value = document.createElement(tag);
  if (text != null) value.textContent = text;
  value.className = className;
  return value;
};
const pp = value => `${value > 0 ? "+" : ""}${value.toFixed(2)} pp`;

export function senatePartialController(legacy, calibration, load = loadAutomaticSenatePartial) {
  let pending;
  return function render(id, detail) {
    const old = legacy.rows.find(row => row.id === id);
    if (old?.office !== "senate") return;
    const section = node("section");
    section.dataset.senatePartial = id;
    section.setAttribute("aria-live", "polite");
    section.append(node("h4", "Current partial Senate scenario"),
      node("p", "Checking the separate reported-D/R-only extension. Archived map and scenario remain unchanged.", "caption"));
    detail.prepend(section);
    if (!pending) pending = load().then(value => value && ({
      ...value, decisions: validateSenatePartial(value.data, legacy, calibration),
    })).catch(error => { pending = null; throw error; });
    pending.then(value => {
      if (!section.isConnected) return;
      const row = value?.decisions.get(id);
      section.replaceChildren(node("h4", "Current partial Senate scenario"));
      if (!row?.model) {
        section.append(node("p", row?.holds.join("; ") ||
          "No reviewed current extension is available. The dated archived scenario is retained.", "caption"));
      } else {
        section.dataset.status = row.status;
        const model = row.model;
        section.append(node("p", `${fresh(row) ? "Current compatible report" : "Held update; last-good scenario retained"}. `
          + `Native model source clock: ${row.model_source_clock}. ${row.holds.join("; ")}`, "caption"),
        node("p", "Reported D/R only; current unreported Other/write-ins are unknown and prior-assumed. "
          + "Transported President/House synthetic associations, not a Senate respondent fit, measured turnout or identified behavior. "
          + "The archived map below is not replaced.", "caption"));
        const table = node("table"), body = node("tbody"), head = node("thead"), headings = node("tr");
        table.append(node("caption", "Separate partial extension · D−R margin contributions; nine assumptions, not confidence intervals"));
        for (const label of ["Term", "Contribution", "Assumption sensitivity"]) headings.append(node("th", label));
        head.append(headings); table.append(head);
        for (const [key, label] of calibratedTerms) {
          const tr = node("tr"), th = node("th", label), range = model.ranges_pp[key];
          th.scope = "row"; tr.dataset.term = key;
          tr.dataset.value = model.point.components_pp[key];
          tr.append(th, node("td", pp(model.point.components_pp[key]), "numeric"),
            node("td", `${pp(range.minimum)} to ${pp(range.maximum)}`, "numeric"));
          body.append(tr);
        }
        table.append(body);
        const wrapper = node("div", null, "table-wrap"); wrapper.append(table); section.append(wrapper);
      }
      if (value) {
        const link = node("a", "Complete current analysis: priors, native facts, all decisions, scenarios, cells and code · ZIP");
        link.href = value.manifest.complete_download.url; section.append(link);
      }
    }).catch(() => {
      if (!section.isConnected) return;
      section.replaceChildren(node("p", "Current partial scenario unavailable; archived results and their dates are retained.", "caption"));
      const retry = node("button", "Retry partial Senate scenario"); retry.type = "button";
      retry.addEventListener("click", () => { section.remove(); render(id, detail); });
      section.append(retry);
    });
  };
}

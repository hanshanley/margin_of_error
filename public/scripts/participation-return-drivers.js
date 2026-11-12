import { projectStateContext } from "./participation-map-projection.js";
import { participationDownload } from "./participation-downloads.js";
import { calibratedTerms, validateCalibratedSwing, calibratedMapValue, roundedContributions, switchingConstraintBounds } from "./participation-calibrated-swing.js";
import { isScenarioView, loadScenarios, scenarioViews, scenarioGroups,
  scenarioEstimate, scenarioScale, scenarioDownload } from "./participation-transition-scenarios.js";
import { loadNorcHouse, norcViews, norcGroups, norcMapValue, renderNorcSelection, norcFamilies,
  norcAssociations, norcSharedBound, validateNorcAssociation } from "./participation-norc-house.js";

export const effectTerms = [
  ["switching", "Switching", "#3e7d84"],
  ["modeled_nonparticipation", "Modeled nonparticipation", "#b27a4d"],
  ["no_prior_contest_vote_entry", "No-prior-contest-vote entry", "#7d8793"],
  ["other_choice", "Other choices", "#919688"],
  ["unresolved", "Unresolved choices", "#a49b92"],
  ["denominator", "Denominator change", "#a49b92"],
  ["return_frame_gap", "Return / source-frame gap · unallocated", "#a49b92"],
];
const offices = ["house", "senate", "governor"];
export const mapTerms = [
  ["reported_total", "Reported swing"],
  ["switching", "Party-choice switching · fitted scenario"],
  ["modeled_nonparticipation", "No current-contest vote · fitted scenario"],
  ["entry", "Entry / return · fitted scenario"],
  ["other_choice", "Other-party choice · fitted scenario"],
];
const mapDescriptions = {
  reported_total: "Total same-office change in the known-D/R margin.",
  switching: "Contribution of D↔R cells in the return-constrained scenario; not identified individual switchers.",
  modeled_nonparticipation: "Contribution of modeled exits from counted candidate choices, not administratively confirmed staying home.",
  entry: "Contribution of modeled entry or return to counted candidate choices, not identified first-time voters.",
  other_choice: "Contribution of transitions involving the modeled Other-party category; not a balancing residual.",
};
export function mapValue(row, key, calibrated) {
  if (!row) return null;
  if (key === "reported_total") return row.reported_comparison?.reported_change_pp ?? null;
  return calibratedMapValue(calibrated, key);
}
export const signedPP = value => `${value > 0 ? "+" : ""}${value.toFixed(2)} pp`;
const magnitude = row => Math.max(Math.abs(row.components_pp.switching),
  Math.abs(row.components_pp.modeled_nonparticipation));

export function validateModels(data) {
  if (data?.version !== "20261110-02" || !Array.isArray(data.rows) || !data.rows.length)
    throw new Error("Unrecognized model dataset");
  const ids = new Set();
  for (const row of data.rows) {
    if (!row.id || ids.has(row.id) || !offices.includes(row.office) || !row.state_code)
      throw new Error("Missing or duplicate model identity");
    ids.add(row.id);
    for (const [key] of effectTerms) {
      const value = row.components_pp?.[key], range = row.ranges_pp?.[key];
      if (!Number.isFinite(value) || !Number.isFinite(range?.minimum)
          || !Number.isFinite(range?.maximum) || range.minimum > value + 1e-8
          || range.maximum < value - 1e-8 || range.minimum > range.maximum)
        throw new Error("Invalid model contribution or assumption range");
    }
    if (!Number.isFinite(row.source_frame_change_pp)
        || Math.abs(effectTerms.reduce((sum, [key]) => sum + row.components_pp[key], 0)
          - row.source_frame_change_pp) > 1e-8)
      throw new Error("Model contributions do not reconcile");
    const comparison = row.reported_comparison;
    if (comparison?.status === "unavailable") {
      if (!comparison.reason || ["reported_change_pp", "baseline_alignment_pp", "other_and_unallocated_pp"]
        .some(key => comparison[key] !== null))
        throw new Error("Unavailable comparison must remain unknown");
    } else {
      const margin = counts => {
        if (!counts || !["D", "R"].every(key => Number.isSafeInteger(counts[key]) && counts[key] > 0))
          throw new Error("Invalid reported comparison counts");
        return 100 * (counts.D - counts.R) / (counts.D + counts.R);
      };
      if (comparison?.status !== "reported_source_comparison"
          || !Number.isInteger(comparison.baseline_year) || comparison.baseline_office !== row.office)
        throw new Error("Invalid reported comparison baseline");
      const current = margin(comparison.current), previous = margin(comparison.previous);
      if (![comparison.reported_change_pp, comparison.baseline_alignment_pp,
        comparison.other_and_unallocated_pp].every(Number.isFinite)
        || Math.abs(current - row.current_return_margin_pp) > 1e-8
        || Math.abs(current - previous - comparison.reported_change_pp) > 1e-8
        || Math.abs(row.source_frame_change_pp + comparison.baseline_alignment_pp
          - comparison.reported_change_pp) > 1e-8
        || Math.abs(row.components_pp.switching + row.components_pp.modeled_nonparticipation
          + comparison.other_and_unallocated_pp - comparison.reported_change_pp) > 1e-8)
        throw new Error("Reported swing does not reconcile");
    }
  }
  return data;
}

export function driverRows(data, office, query = "", order = "magnitude", names = {}) {
  const search = query.trim().toLowerCase();
  return data.rows.filter(row => row.office === office
    && `${names[row.state_code] || ""} ${row.state_code}`.toLowerCase().includes(search))
    .sort((a, b) => order === "name"
      ? (names[a.state_code] || a.state_code).localeCompare(names[b.state_code] || b.state_code)
      : order === "switching" ? Math.abs(b.components_pp.switching) - Math.abs(a.components_pp.switching)
        : order === "nonparticipation" ? Math.abs(b.components_pp.modeled_nonparticipation)
          - Math.abs(a.components_pp.modeled_nonparticipation) : magnitude(b) - magnitude(a));
}

export function driverScale(rows) {
  const maximum = Math.max(0, ...rows.flatMap(row => effectTerms.slice(0, 2).flatMap(([key]) =>
    [Math.abs(row.ranges_pp[key].minimum), Math.abs(row.ranges_pp[key].maximum)])));
  return maximum === 0 ? 1 : Math.ceil(maximum / 5) * 5;
}

const element = (tag, text, className = "") => {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  node.className = className;
  return node;
};
const svgElement = (tag, attributes) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  return node;
};

export function mapScale(rows, calibration = new Map()) {
  const maximum = Math.max(0, ...rows.flatMap(row =>
    mapTerms.map(([key]) => Math.abs(mapValue(row, key, calibration.get(row.id)) ?? 0))));
  return maximum === 0 ? 1 : Math.ceil(maximum / 5) * 5;
}

export function effectFill(value, bound) {
  if (value == null) return "#d6d3cb";
  if (!Number.isFinite(value) || !Number.isFinite(bound) || bound <= 0)
    throw new Error("Invalid modeled map scale");
  const neutral = [241, 238, 230], end = value < 0 ? [164, 112, 69] : [44, 108, 117];
  const weight = Math.min(1, Math.abs(value) / bound);
  return "#" + neutral.map((channel, i) => Math.round(channel + weight * (end[i] - channel))
    .toString(16).padStart(2, "0")).join("");
}

export async function initializeReturnDrivers() {
  const root = document.querySelector("#participation-return-drivers");
  if (!root || root.dataset.initialized) return;
  root.dataset.initialized = "true";
  const status = root.querySelector("[data-driver-status]");
  try {
    const payload = JSON.parse(root.querySelector("[data-driver-data]").textContent);
    const data = validateModels(payload.data), names = payload.names;
    const calibration = validateCalibratedSwing(payload.calibration, data);
    const office = root.querySelector("[data-driver-office]");
    const view = root.querySelector("[data-driver-view]");
    const stateSelect = root.querySelector("[data-driver-state]");
    const group = root.querySelector("[data-driver-group]");
    const familySelect = root.querySelector("[data-driver-family]");
    const associationSelect = root.querySelector("[data-driver-association]");
    const associationNote = root.querySelector("[data-driver-association-note]");
    const unitsSelect = root.querySelector("[data-driver-units]");
    const detail = root.querySelector("[data-driver-detail]");
    const summary = root.querySelector("[data-driver-summary]");
    const response = await fetch(participationDownload("/voter-participation/data/states.geojson"));
    if (!response.ok) throw new Error(`State context: HTTP ${response.status}`);
    const collection = await response.json();
    const items = projectStateContext(collection.features);
    if (items.length !== 51 || new Set(items.map(item => item.feature.properties.STUSAB)).size !== 51)
      throw new Error("State context inventory differs");
    for (const item of items) names[item.feature.properties.STUSAB] ||= item.feature.properties.NAME;
    const codes = items.map(item => item.feature.properties.STUSAB).sort((a, b) => names[a].localeCompare(names[b]));
    let selectedCode = "TX";
    let scenarios, norc, norcComparison, norcOriginalComparison, norcFamily, hitObserver, groupKind="", generation = 0;
    const associationKey=()=>associationSelect?.value || "original";
    const norcUnits=()=>unitsSelect?.value || "margin";
    const legacyMapNote = root.querySelector(".driver-map-note").cloneNode(true);
    stateSelect.replaceChildren(new Option("Select a state on the map…", ""),
      ...codes.map(code => new Option(names[code], code)));
    const paintSelection = () => {
      for (const path of root.querySelectorAll(".driver-state")) {
        path.classList.toggle("selected", path.dataset.stateCode === selectedCode);
        path.setAttribute("tabindex",path.dataset.stateCode === selectedCode ? "0" : "-1");
      }
      const selected=root.querySelector(".driver-state.selected");
      if (selected) selected.parentNode.append(selected);
      for (const hit of root.querySelectorAll("[data-driver-hit]"))
        hit.parentNode.append(hit);
    };
    const setGroups = kind => {
      if (groupKind===kind) return;
      const previous=group.value;
      const options=kind==="norc" ? norcGroups(norc).map(g=>new Option(g.label,g.value))
        : scenarioGroups(scenarios).map(g=>new Option(g.label,g.key));
      group.replaceChildren(new Option(kind==="norc"?"All source groups":"Overall source frame",""),...options);
      if ([...group.options].some(o=>o.value===previous)) group.value=previous;
      groupKind=kind;
      root.querySelector("[data-driver-group-control]").childNodes[0].textContent=kind==="norc"?"Demographic group":"Source group";
    };
    const selectScenario = (row, code) => {
      const estimate = row && scenarioEstimate(scenarios, code, view.value, group.value);
      const category = group.selectedOptions[0]?.textContent || "Overall source frame";
      const label = scenarioViews.find(([key]) => key === view.value)[1];
      summary.replaceChildren(element("h3", `${names[code]} · ${category}`));
      detail.replaceChildren(element("h4", `${names[code]} · conditional party-choice scenario`));
      if (!estimate) {
        const reason = code === "DC" ? "D.C. has no Civic sample."
          : !row ? `No supplied ${office.value} model frame for this state.`
            : "This demographic source group is unavailable or withheld. It is not inferred from other categories.";
        summary.append(element("p", `${reason} Gray is unavailable, not zero.`, "caption"));
        detail.append(element("p", reason, "caption"));
      } else {
        const percent = value => `${(100 * value).toFixed(1)}%`;
        summary.append(element("p", `${label}: ${percent(estimate.value)}. `
          + `Half/double-persistence scenarios: ${percent(estimate.minimum)} to ${percent(estimate.maximum)}.`,
        "driver-equation"), element("p",
          "Share within recalled 2024 major-party choices in the source frame, not all voters or a contribution to the electoral swing. Synthetic histories are not identified people.",
          "caption"));
        const body = element("tbody"), table = element("table");
        table.append(element("caption", "Five exhaustive gross outcomes · share of recalled major-party source weight"));
        for (const [name, field] of [
          ["Keep party choice", "retaining"], ["Switch party choice", "switching"],
          ["Modeled nonparticipation", "nonparticipation"], ["Other choice", "other_choice"],
          ["Unresolved current choice", "unresolved"],
        ]) {
          const tr = element("tr"), th = element("th", name); th.scope = "row";
          tr.append(th, element("td", percent(estimate.point[
            `synthetic_${field}_share_of_recalled_major_party`]), "numeric"));
          body.append(tr);
        }
        table.append(body);
        const wrapper = element("div", null, "table-wrap"); wrapper.append(table);
        detail.append(wrapper, element("p",
          `Separate current-major-party denominator: ${percent(estimate.point.synthetic_no_prior_contest_vote_entry_share_of_current_major_party)} `
          + "have no recalled prior-contest vote. This does not identify first-ever voting, new eligibility or no prior ballot.",
          "caption"));
        if (group.value) detail.append(element("p",
          "Only this group's disclosed modeled-nonvoter fraction conditions the state coupling. Demographic prior-party associations are assumed, not learned; groups and dimensions are not additive populations.",
          "caption"));
        const check = scenarios.unfitted_return_checks.find(value => value.id === row.id);
        if (check?.reported_same_office_change_pp != null) {
          const model = Object.values(check.synthetic_components_pp).reduce((a, b) => a + b, 0);
          detail.append(element("p", `Whole-state reconciliation, not a subgroup swing: `
            + `${signedPP(check.reported_same_office_change_pp)} reported same-office swing = `
            + `${signedPP(model)} synthetic signed mechanisms / denominator + `
            + `(${signedPP(check.unallocated_return_minus_model_pp)}) current-frame residual + `
            + `(${signedPP(check.prior_baseline_alignment_pp)}) prior-baseline alignment. `
            + "Both residuals remain unallocated.", "caption"));
        } else detail.append(element("p", "No qualified previous same-office return comparison; no baseline is filled with zero.", "caption"));
        detail.append(element("p", office.value === "house"
          ? "Recalled 2024 presidential party choice versus the current House source model."
          : `House-source coupling transported to the ${office.value} frame; not an office-specific individual-history estimate.`, "caption"),
        element("p", "Current-voter gross-switching state-held-out MAE: 1.39 pp (fixed factor-16: 1.40 pp). "
          + "This is not material evidence of better population prediction. Some governor misses exceed four points. "
          + "There are no House poll targets; survey independence and population transport are unvalidated.", "caption"),
        element("p", "Half/double strength is assumption sensitivity, not a confidence interval. "
          + "Monte Carlo error is separate from unknown source/design uncertainty. Historical CPS marginals supply no joint-transition truth. "
          + "Modeled nonparticipation is not administrative staying home. No state model is allocated to counties or precincts.", "caption"));
      }
      const download = element("a", "Complete simulation inputs, every query/seed/scenario and code · ZIP");
      download.href = scenarioDownload; detail.append(download);
      summary.hidden = false; detail.hidden = false;
    };
    const select = row => {
      const comparison = row.reported_comparison;
      const fitted = calibration.get(row.id);
      const heading = `${names[row.state_code]} · ${row.office === "house"
        ? "House state aggregate" : row.office === "governor" ? "Governor source frame" : "Senate race"}`;
      summary.replaceChildren(element("h3", heading));
      if (comparison.status === "reported_source_comparison") {
        summary.append(element("p", `${comparison.baseline_year} ${row.office}`
          + `${comparison.baseline_stage === "general_runoff" ? " · runoff" : ""} → held 2026 ${row.office} returns. `
          + `${comparison.scope}.`, "caption"));
        const rounded = roundedContributions(fitted.point);
        const equation = element("p", null, "driver-equation");
        equation.append(element("strong", `${signedPP(comparison.reported_change_pp)} reported swing`),
          document.createTextNode(" = " + calibratedTerms.map(([key, label], index) =>
            `${index ? rounded[key] < 0 ? " − " : " + " : rounded[key] < 0 ? "−" : ""}`
            + `${Math.abs(rounded[key]).toFixed(2)} pp ${label.toLowerCase()}`).join("") + "."));
        summary.append(element("p",
          "Fitted scenario; not independently measured switching or confirmed staying home. "
          + (switchingConstraintBounds(fitted).minimumPercent === 0
            ? "The same totals also permit zero switching." : "The split depends on the transition assumptions."),
          "caption"), equation);
        if (fitted.observed_other_vote_endpoints.some(value => !value))
          summary.append(element("p", "Other-party totals are not supplied in this source frame; the split between Other and no counted contest vote is prior-assumed, not observed.", "caption"));
      } else {
        summary.append(element("p", `Reported swing unavailable: ${comparison.reason} `
          + "No return-constrained contributions are filled with zero or borrowed from another frame.", "caption"));
      }
      summary.hidden = false;
      detail.replaceChildren(element("h4", heading),
        element("p", "The model uses a common synthetic candidate-vote accounting frame, not a measured eligible population. The original survey-derived associations are a prior only; they are not the earlier same-office return.", "caption"));
      if (!fitted.point) { detail.append(element("p", fitted.reason, "caption")); detail.hidden = false; return; }
      const table = element("table"), body = element("tbody");
      table.append(element("caption", "Return-constrained scenario · exact Shapley contributions to the normalized D−R margin"));
      const head = element("thead"), headings = element("tr");
      for (const label of ["Term", "Contribution", "Assumption sensitivity"]) headings.append(element("th", label));
      head.append(headings); table.append(head);
      for (const [key, label] of calibratedTerms) {
        const tr = element("tr"), th = element("th", label), range = fitted.ranges_pp[key];
        th.scope = "row";
        tr.append(th, element("td", signedPP(fitted.point.components_pp[key]), "numeric"),
          element("td", `${signedPP(range.minimum)} to ${signedPP(range.maximum)}`, "numeric"));
        body.append(tr);
      }
      {
        const tr = element("tr"), th = element("th", "Reported total · all four transition mechanisms");
        th.scope = "row"; tr.append(th, element("td", signedPP(comparison.reported_change_pp), "numeric"), element("td", "—")); body.append(tr);
      }
      table.append(body);
      const wrapper = element("div", null, "table-wrap"); wrapper.append(table);
      detail.append(wrapper, element("p", "Ranges span nine prior-persistence and common-frame-size assumptions, not confidence or identification intervals. The four mechanisms are computed from a nonnegative transition table, with denominator changes included symmetrically; no return/frame residual is added.", "caption"),
      element("p", `Why the earlier display failed: its survey-recall baseline differed from the same-office return by ${signedPP(comparison.baseline_alignment_pp)}. That difference is not a behavioral contribution. Earlier unfitted estimates remain in the archived table/download, not these scenario maps.`, "caption"),
      element("p", "No counted vote for this office does not establish no ballot, new eligibility, death, migration or first-ever voting. Original synthetic nonvote/unresolved categories are pooled only in the prior; source observations are not recoded. A fitted decomposition is not independent validation.", "caption"),
      element("p", `${fitted.source_prior_transport}. `
        + `Return scope: ${row.evidence.return_scope.replaceAll("_", " ")}.`, "caption"),
      element("p", `Whole-state source n ${row.support.raw_whole_state_n.toLocaleString("en-US")}; `
        + "weights are not people and support is not a precision guarantee. Eligibility, death and migration remain unknown.", "caption"));
      const gross = fitted.point.gross_shares_of_modeled_previous_major_party;
      detail.append(element("p", `Gross modeled outcomes within the previous major-party frame: `
        + `${(100*gross.retaining).toFixed(1)}% keep party choice; `
        + `${(100*gross.switching).toFixed(1)}% switch party choice; `
        + `${(100*gross.nonparticipation).toFixed(1)}% have no counted target-contest vote; `
        + `${(100*gross.other_choice).toFixed(1)}% choose Other. These scenario shares are not swing contributions or measured people.`, "caption"));
      const compatible = switchingConstraintBounds(fitted);
      const identification = element("p",
        `Under the same assumed accounting frame, the recorded totals permit `
        + `${compatible.minimumPercent.toFixed(1)}% to ${compatible.maximumPercent.toFixed(1)}% `
        + "gross D↔R switching within previous D/R votes. "
        + (compatible.minimumPercent === 0 ? "They do not require any switching; " : "")
        + "the fitted amount depends on the transition prior. This is a feasibility range, "
        + "not a confidence interval or a contribution to the electoral margin.", "caption");
      identification.dataset.driverIdentification = row.id;
      detail.append(identification);
      const completeBounds = element("a", "Complete compatible-flow bounds, every witness table, inputs and code · ZIP");
      completeBounds.href = "https://github.com/hanshanley/margin_of_error/releases/download/participation-flow-identification-20261111-01/complete-analysis.zip";
      detail.append(completeBounds);
      if (comparison.status === "reported_source_comparison")
        detail.append(element("p", `${comparison.qualification} `
          + `Current native source clock: ${comparison.current_native_clock || "not supplied"}. `
          + `${comparison.current_percent_reporting == null ? "" : `Source reporting: ${comparison.current_percent_reporting}%. `}`
          + `Reported count margins: ${signedPP(comparison.previous_margin_pp)} → ${signedPP(comparison.current_margin_pp)}.`, "caption"));
      detail.hidden = false;
    };
    const selectState = code => {
      selectedCode = code; stateSelect.value = code;
      const row = data.rows.find(value => value.state_code === code && value.office === office.value);
      if (isScenarioView(view.value) && scenarios && code) selectScenario(row, code);
      else if (isScenarioView(view.value)) { detail.hidden = true; summary.hidden = true; }
      else if (office.value==="house" && payload.norc_source) {
        if (norc && code) renderNorcSelection(norc.rows.find(r=>r.state_code===code),
          view.value==="reported_total"?"":group.value,names[code],summary,detail,
          {units:norcUnits(),family:norcFamily,comparison:norcComparison,
            association:norcComparison?.association_profile,
            associationState:norc?.historical_association_stress?.state_parameters[code],
            originalComparison:norcOriginalComparison});
        else { summary.replaceChildren();detail.replaceChildren();summary.hidden=true;detail.hidden=true; }
      }
      else if (row) select(row);
      else if (code) {
        detail.replaceChildren(element("h3", names[code]),
          element("p", code === "DC" ? "D.C. has no NORC sample. No contribution is estimated."
            : `No supplied ${office.value} model for this state. Gray is missing coverage, not zero change.`));
        detail.hidden = false;
        summary.replaceChildren(...Array.from(detail.childNodes).map(node => node.cloneNode(true)));
        summary.hidden = false;
      } else { detail.hidden = true; summary.hidden = true; }
      paintSelection();
    };
    const render = async () => {
      const current = ++generation, scenario = isScenarioView(view.value);
      const norcMode=office.value==="house" && !scenario && Boolean(payload.norc_source);
      if (associationNote) associationNote.hidden=true;
      if (associationSelect) {
        associationSelect.closest("label").hidden=!norcMode || !payload.norc_association_sources;
        associationSelect.disabled=!norcMode || !payload.norc_association_sources;
      }
      if (familySelect) {
        familySelect.closest("label").hidden=!norcMode || Boolean(norc && !norcComparison);
        familySelect.disabled=!norcComparison;
      }
      if (unitsSelect) {
        unitsSelect.closest("label").hidden=!norcMode;
        unitsSelect.disabled=!norc || view.value==="retaining";
      }
      root.querySelector("[data-driver-group-control]").hidden = !scenario && !norcMode;
      root.querySelector(".driver-controls").dataset.scenarios = String(scenario || norcMode);
      if (norcMode && !norc) {
        status.textContent="Loading the checksum-verified NORC demographic House model.";
        root.querySelector("[data-driver-map]").replaceChildren();summary.hidden=true;detail.hidden=true;
        try {
          const requested=associationKey();
          const receipt=requested==="original"?payload.norc_source:payload.norc_association_sources?.profiles?.[requested];
          if (!receipt) throw new Error("Missing pinned association profile");
          const [loaded,original]=await Promise.all([
            loadNorcHouse(receipt),
            requested==="original"?Promise.resolve(null):loadNorcHouse(payload.norc_source),
          ]);
          if (current!==generation) return;
          if (requested!=="original") validateNorcAssociation(loaded,original);
          if (loaded.contract==="participation.house_model_families.v1") {
            norcComparison=loaded;
            norcOriginalComparison=requested==="original"?loaded:original;
            norcFamily=loaded.families[norcFamily]?norcFamily:loaded.preferred_family;
            if (familySelect) {
              familySelect.replaceChildren(...norcFamilies.map(([key,label])=>new Option(label,key)));
              familySelect.value=norcFamily;familySelect.disabled=false;
            }
            norc=loaded.families[norcFamily];
          } else norc=loaded;
          if (unitsSelect) unitsSelect.disabled=view.value==="retaining";
        } catch (error) {
          if (current!==generation) return;
          status.textContent=`NORC House model unavailable: ${error.message}. No older fitted model is substituted.`;
          const retry=element("button","Retry NORC model");retry.type="button";retry.addEventListener("click",render);
          root.querySelector("[data-driver-map]").replaceChildren(retry);return;
        }
      }
      if (norcMode) {setGroups("norc");group.disabled=view.value==="reported_total";}
      if (norcMode && associationNote) {
        const share=norcUnits()==="democratic_two_party_share";
        associationNote.textContent=`Before conditioning: ${norc.summary.return_anchored}-state `
          +`${share?"Democratic two-party-share":"D−R margin"} mean absolute error `
          +`${(norc.preconditioning_margin_MAE_pp*(share ? .5 : 1)).toFixed(2)} pp. `
          +"Temporal-association profiles were not selected using these return errors.";
        associationNote.hidden=false;
      }
      if (scenario && !scenarios) {
        status.textContent = "Loading verified conditional scenarios; previous values are cleared.";
        root.querySelector("[data-driver-map]").replaceChildren();
        summary.hidden = true; detail.hidden = true;
        try {
          const loaded = await loadScenarios();
          if (current !== generation) return;
          scenarios = loaded;
        } catch (error) {
          if (current !== generation) return;
          status.textContent = `Scenario map unavailable: ${error.message}. Other map views and complete downloads remain available.`;
          const retry = element("button", "Retry scenario data");
          retry.type = "button"; retry.addEventListener("click", render);
          root.querySelector("[data-driver-map]").replaceChildren(retry);
          return;
        }
      }
      if (scenario) {setGroups("legacy");group.disabled=false;}
      const all = driverRows(data, office.value, "", "magnitude", names);
      const byCode = new Map(all.map(row => [row.state_code, row]));
      const norcByCode=norcMode?new Map(norc.rows.map(r=>[r.state_code,r])):null;
      const retention=norcMode && view.value==="retaining";
      const sharedMaximum=payload.norc_association_sources?.shared_max_abs_margin?.[group.value] ?? null;
      const bound = retention ? 100 : norcMode ? norcSharedBound(norcComparison || norc,group.value,norcUnits(),sharedMaximum)
        : scenario ? scenarioScale(Object.keys(scenarios.state_scenarios).map(code =>
        scenarioEstimate(scenarios, code, view.value, group.value)?.value ?? null)) : mapScale(all, calibration);
      if (byCode.size !== all.length) throw new Error("Multiple race frames require separate state selection");
      status.textContent = norcMode ? `${norc.summary.return_anchored} House reconstructions use recorded endpoints; `
        +`${50-norc.summary.return_anchored} are NORC source scenarios with unavailable observed comparisons. `
        +"Gray means unsupported, not zero. Demographic values contribute to the statewide shift. "
        +(norcComparison?`${norcComparison.family_labels[norcFamily]}. `:"")
        +(payload.norc_association_sources?`${norcAssociations.find(([key])=>key===associationKey())?.[1]}. `:"")
        +(retention?"Retained-choice percentages keep their own denominator; change units do not apply."
          :norcUnits()==="democratic_two_party_share"?"Change units: Democratic two-party share points.":"Change units: D−R margin points.")
        : scenario
        ? `${all.filter(row => scenarioEstimate(scenarios, row.state_code, view.value, group.value)).length} supported source scenarios in ${office.value} frames. `
          + "Gross source-weight shares, not swing contributions or measured staying home."
        : `${all.filter(row => calibration.get(row.id)?.point).length}/${all.length} `
        + `${office.value === "house" ? "House states" : office.value === "governor" ? "governor source frames" : "Senate races"} `
        + "have comparable endpoints. Gray is unavailable; views share one signed scale.";
      root.querySelector("[data-driver-scale-min]").textContent = retention?"0%":scenario ? "0%" : `−${bound} pp`;
      root.querySelector("[data-driver-scale-max]").textContent = retention?"100%":scenario ? `${Math.round(bound * 100)}%` : `+${bound} pp`;
      root.querySelector(".driver-map-ticks").children[1].textContent = retention?"50%":scenario ? `${Math.round(bound * 50)}%` : "0";
      root.querySelector(".driver-map-ramp").style.background = scenario || retention
        ? "linear-gradient(to right,#f1eee6,#2c6c75)" : "";
      root.querySelector(".driver-map-key").setAttribute("aria-label", retention
        ? "Sequential modeled party-retention percentage scale" : scenario
          ? "Sequential synthetic source-weight share scale" : norcMode && norcUnits()==="democratic_two_party_share"
            ? "Shared signed Democratic two-party-share-change scale" : "Shared signed margin-point scale");
      const directions = root.querySelector(".driver-map-directions").children;
      directions[0].textContent = scenario || retention ? "Lower share" : "Republican direction";
      directions[1].textContent = scenario || retention ? "Higher share" : "Democratic direction";
      const note = root.querySelector(".driver-map-note");
      if (norcMode) note.textContent=retention
        ? "Modeled share of previous major-party choices assigned the same party. Retention is not a contribution to the change in margin."
        : "NORC-informed, return-constrained model estimates, not observed voter histories. Net participation combines modeled exits and entry/return. "
          +"Each demographic dimension separately partitions its state; dimensions overlap and are not additive causes. "
          +(norcUnits()==="democratic_two_party_share"?"Democratic two-party share changes are half D−R margin changes; Other is outside that denominator. ":"")
          +"Model-family and historical-association stresses are not confidence intervals. Historical transport is not validated for 2026. "
          +"No state model is spread onto precincts.";
      else if (scenario) note.textContent = "Synthetic shares within recalled major-party source choices, not all voters, "
        + "electoral swing contributions or confirmed missing ballots. The five gross outcomes include Other and unresolved choices. "
        + "State models are not allocated to counties or precincts.";
      else note.replaceChildren(...Array.from(legacyMapNote.childNodes).map(node => node.cloneNode(true)));
      {
        const [key, label] = [...(norcMode?norcViews:mapTerms), ...scenarioViews].find(([value]) => value === view.value);
        const host = root.querySelector("[data-driver-map]");
        host.dataset.driverMap = key;
        root.querySelector("[data-driver-map-title]").textContent = label;
        root.querySelector("[data-driver-map-caption]").textContent = norcMode
          ? key==="reported_total" ? `Observed same-office House ${norcUnits()==="democratic_two_party_share"?"Democratic two-party-share":"margin"} change; no demographic vote shares are inferred.`
            : `${group.selectedOptions[0].textContent}. ${retention?"Share retaining party":norcUnits()==="democratic_two_party_share"?"Contribution to statewide Democratic two-party-share change":"Contribution to statewide margin change"}. `
              +(key==="modeled_nonparticipation"?"Entry/return and modeled absence are included together.":"")
          : scenario
          ? `${group.selectedOptions[0].textContent}. Share of recalled major-party source weight; assumption-dependent, not identified histories.`
          : mapDescriptions[key];
        const svg = svgElement("svg", { viewBox: "0 0 1000 640", role: "group",
          "aria-label": `${label}: ${retention ? "modeled percentages" : scenario ? "synthetic source-weight shares" : "signed percentage-point changes"} by state`, "data-scale": bound });
        for (const item of items) {
          const code = item.feature.properties.STUSAB, row = byCode.get(code);
          const value = norcMode ? norcMapValue(norcByCode.get(code),key,group.value,norcUnits())
            : scenario ? row && scenarioEstimate(scenarios, code, key, group.value)?.value : mapValue(row, key, calibration.get(row?.id));
          const normalized = value ?? null;
          const text = `${names[code]} · ${label}: ${normalized === null ? "no qualified comparison, group or model"
            : retention ? `${normalized.toFixed(1)}%` : scenario ? `${(normalized * 100).toFixed(1)}%` : signedPP(normalized)}. `
            + (retention ? "Modeled party-retention share, not a margin contribution."
              : scenario ? "Synthetic source-weight share, not measured staying home."
                : norcMode && norcUnits()==="democratic_two_party_share"
                  ? "Change in Democratic two-party-share points, not population turnout."
                  : "Margin points, not a vote share or turnout rate.");
          const path = svgElement("path", { d: item.d, fill: effectFill(normalized, bound),
            class: "driver-state", "fill-rule": "evenodd", "data-state-code": code,
            "data-model-value": normalized ?? "", ...(row ? { "data-model-id": row.id } : {}),
            role: "button", tabindex: "-1",
            "aria-label": text });
          const title = svgElement("title", {}); title.textContent = text; path.append(title);
          path.addEventListener("click", () => selectState(code));
          path.addEventListener("keydown",event=>{
            if (event.key==="Enter" || event.key===" ") {event.preventDefault();selectState(code);}
          });
          svg.append(path);
        }
        for (const [x, text] of [[60, "Alaska"], [310, "Hawaii · insets not to scale"]]) {
          const caption = svgElement("text", { x, y: 625, class: "driver-inset-label" });
          caption.textContent = text; svg.append(caption);
        }
        host.replaceChildren(svg);
        const updateHitTargets=()=>{
          svg.querySelectorAll("[data-driver-hit]").forEach(node=>node.remove());
          const scale=svg.getBoundingClientRect().width/1000;
          if (scale>0) for (const path of svg.querySelectorAll("path")) {
            const box=path.getBBox();
            if (box.width*scale>=6 || box.height*scale>=6) continue;
            const hit=svgElement("circle",{cx:box.x+box.width/2,cy:box.y+box.height/2,
              r:3/scale,fill:"transparent","data-driver-hit":path.dataset.stateCode,
              "aria-hidden":"true",style:"cursor:pointer"});
            hit.addEventListener("click",()=>selectState(path.dataset.stateCode));
            svg.append(hit);
          }
        };
        hitObserver?.disconnect();
        hitObserver=new ResizeObserver(updateHitTargets);hitObserver.observe(svg);
        updateHitTargets();
      }
      selectState(selectedCode);
    };
    for (const control of [office, view, stateSelect]) {
      control.disabled = false;
    }
    const changeOffice=() => {
      const previous=view.value, options=office.value==="house" && payload.norc_source?norcViews:mapTerms;
      view.replaceChildren(...options.map(([key,label])=>new Option(label,key)));
      const archived=element("optgroup");archived.label="Archived survey-frame scenarios";
      for (const [key,label] of scenarioViews) archived.append(new Option(label,key));
      view.append(archived);
      view.value=[...view.options].some(o=>o.value===previous)?previous:"reported_total";
      render();
    };
    office.addEventListener("change",changeOffice);
    view.addEventListener("change", render);
    stateSelect.addEventListener("change", () => selectState(stateSelect.value));
    group.addEventListener("change", render);
    familySelect?.addEventListener("change",()=>{
      if (!norcComparison?.families[familySelect.value]) return;
      norcFamily=familySelect.value;norc=norcComparison.families[norcFamily];render();
    });
    associationSelect?.addEventListener("change",()=>{
      norc=undefined;norcComparison=undefined;
      render();
    });
    unitsSelect?.addEventListener("change",render);
    window.addEventListener("participation:effects-state", event => {
      selectState(codes.find(code => names[code] === event.detail || code === event.detail) || "");
    });
    changeOffice();
  } catch (error) {
    status.textContent = `Model map unavailable: ${error.message}. Saved numerical tables and complete downloads remain below.`;
  }
}

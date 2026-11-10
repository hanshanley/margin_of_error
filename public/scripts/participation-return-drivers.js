import { projectStateContext } from "./participation-map-projection.js";
import { participationDownload } from "./participation-downloads.js";

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
export const signedPP = value => `${value > 0 ? "+" : ""}${value.toFixed(2)} pp`;
const magnitude = row => Math.max(Math.abs(row.components_pp.switching),
  Math.abs(row.components_pp.modeled_nonparticipation));

export function validateModels(data) {
  if (data?.version !== "20261110-01" || !Array.isArray(data.rows) || !data.rows.length)
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

export function mapScale(rows) {
  const maximum = Math.max(0, ...rows.flatMap(row =>
    [Math.abs(row.components_pp.switching), Math.abs(row.components_pp.modeled_nonparticipation)]));
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
    const office = root.querySelector("[data-driver-office]");
    const stateSelect = root.querySelector("[data-driver-state]");
    const detail = root.querySelector("[data-driver-detail]");
    const response = await fetch(participationDownload("/voter-participation/data/states.geojson"));
    if (!response.ok) throw new Error(`State context: HTTP ${response.status}`);
    const collection = await response.json();
    const items = projectStateContext(collection.features);
    if (items.length !== 51 || new Set(items.map(item => item.feature.properties.STUSAB)).size !== 51)
      throw new Error("State context inventory differs");
    for (const item of items) names[item.feature.properties.STUSAB] ||= item.feature.properties.NAME;
    const codes = items.map(item => item.feature.properties.STUSAB).sort((a, b) => names[a].localeCompare(names[b]));
    let selectedCode = "";
    stateSelect.replaceChildren(new Option("Select a state on either map…", ""),
      ...codes.map(code => new Option(names[code], code)));
    const paintSelection = () => {
      for (const path of root.querySelectorAll(".driver-state"))
        path.classList.toggle("selected", path.dataset.stateCode === selectedCode);
    };
    const select = row => {
      detail.replaceChildren(element("h4", `${names[row.state_code]} · ${row.office === "house"
        ? "House state aggregate" : row.office === "governor" ? "Governor source frame" : "Senate race"}`),
      element("p", "Recalled 2024 President in the current study frame → 2026 selected office. Not automatically the last election for this office.", "caption"));
      const table = element("table"), body = element("tbody");
      table.append(element("caption", "Full accounting · percentage-point contributions to the margin"));
      const head = element("thead"), headings = element("tr");
      for (const label of ["Term", "Contribution", "Strength sensitivity"]) headings.append(element("th", label));
      head.append(headings); table.append(head);
      for (const [key, label] of effectTerms) {
        const tr = element("tr"), th = element("th", label);
        th.scope = "row"; tr.append(th, element("td", signedPP(row.components_pp[key]), "numeric"));
        if (key === "switching" || key === "modeled_nonparticipation") {
          const range = row.ranges_pp[key];
          tr.append(element("td", `${signedPP(range.minimum)} to ${signedPP(range.maximum)}`, "numeric"));
        } else tr.append(element("td", "—"));
        body.append(tr);
      }
      table.append(body);
      const wrapper = element("div", null, "table-wrap"); wrapper.append(table);
      detail.append(wrapper, element("p", "Ranges vary contrast strength from 0.5× to 1.5×; these are not confidence intervals.", "caption"),
      element("p", `Within-source change: ${signedPP(row.source_frame_change_pp)}. `
        + `Current return margin: ${signedPP(row.current_return_margin_pp)}.`, "caption"),
      element("p", `${row.evidence.switching}. `
        + (row.evidence.cross_office_transport
          ? "Participation and remaining House-model terms are explicitly transported across offices. " : "")
        + `Return scope: ${row.evidence.return_scope.replaceAll("_", " ")}.`, "caption"),
      element("p", `Whole-state source n ${row.support.raw_whole_state_n.toLocaleString("en-US")}; `
        + "weights are not people and support is not a precision guarantee. Eligibility, death and migration remain unknown.", "caption"));
      if (row.observed_same_office_change_pp !== null)
        detail.append(element("p", `Separate supplied previous-office comparison: ${signedPP(row.observed_same_office_change_pp)}. `
          + `Prior-office/source-frame gap: ${signedPP(row.previous_office_frame_gap_pp)}.`, "caption"));
      detail.hidden = false;
    };
    const selectState = code => {
      selectedCode = code; stateSelect.value = code;
      const row = data.rows.find(value => value.state_code === code && value.office === office.value);
      if (row) select(row);
      else if (code) {
        detail.replaceChildren(element("h3", names[code]),
          element("p", code === "DC" ? "D.C. has no NORC sample. No contribution is estimated."
            : `No supplied ${office.value} model for this state. Gray is missing coverage, not zero change.`));
        detail.hidden = false;
      } else detail.hidden = true;
      paintSelection();
    };
    const render = () => {
      const all = driverRows(data, office.value, "", "magnitude", names);
      const byCode = new Map(all.map(row => [row.state_code, row])), bound = mapScale(all);
      if (byCode.size !== all.length) throw new Error("Multiple race frames require separate state selection");
      status.textContent = `${all.length} ${office.value === "house" ? "House state aggregates"
        : office.value === "governor" ? "governor source frames" : "Senate races"}. Both maps use the same scale.`;
      root.querySelector("[data-driver-scale-min]").textContent = `−${bound} pp`;
      root.querySelector("[data-driver-scale-max]").textContent = `+${bound} pp`;
      for (const [key, label] of effectTerms.slice(0, 2)) {
        const host = root.querySelector(`[data-driver-map="${key}"]`);
        const svg = svgElement("svg", { viewBox: "0 0 1000 640", role: "group",
          "aria-label": `${label}: modeled margin contribution by state`, "data-scale": bound });
        for (const item of items) {
          const code = item.feature.properties.STUSAB, row = byCode.get(code), value = row?.components_pp[key] ?? null;
          const text = `${names[code]} · ${label}: ${value === null ? "no model" : signedPP(value)}. Model contribution, not a vote share.`;
          const path = svgElement("path", { d: item.d, fill: effectFill(value, bound),
            class: "driver-state", "fill-rule": "evenodd", "data-state-code": code,
            "data-model-value": value ?? "", ...(row ? { "data-model-id": row.id } : {}),
            role: "button", tabindex: "-1",
            "aria-label": text });
          const title = svgElement("title", {}); title.textContent = text; path.append(title);
          path.addEventListener("click", () => selectState(code));
          svg.append(path);
        }
        for (const [x, text] of [[60, "Alaska"], [310, "Hawaii · insets not to scale"]]) {
          const caption = svgElement("text", { x, y: 625, class: "driver-inset-label" });
          caption.textContent = text; svg.append(caption);
        }
        host.replaceChildren(svg);
      }
      selectState(selectedCode);
    };
    for (const control of [office, stateSelect]) {
      control.disabled = false;
    }
    office.addEventListener("change", render);
    stateSelect.addEventListener("change", () => selectState(stateSelect.value));
    window.addEventListener("participation:effects-state", event => {
      selectState(codes.find(code => names[code] === event.detail || code === event.detail) || "");
    });
    render();
  } catch (error) {
    status.textContent = `Model maps unavailable: ${error.message}. Saved numerical tables and complete downloads remain below.`;
  }
}

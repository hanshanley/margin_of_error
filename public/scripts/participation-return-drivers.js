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

function plot(row, bound) {
  const svg = svgElement("svg", { viewBox: "0 0 320 46", role: "img", class: "driver-plot",
    "aria-label": `Switching ${signedPP(row.components_pp.switching)}; modeled nonparticipation ${signedPP(row.components_pp.modeled_nonparticipation)}. Whiskers are assumption strength, not confidence intervals.` });
  svg.append(svgElement("line", { x1: 160, x2: 160, y1: 1, y2: 44, stroke: "#aaa79f", "stroke-width": 1 }));
  for (const [index, [key, label, colour]] of effectTerms.slice(0, 2).entries()) {
    const x = value => 160 + 142 * value / bound;
    const value = row.components_pp[key], range = row.ranges_pp[key], y = 11 + 22 * index;
    svg.append(svgElement("line", { x1: x(range.minimum), x2: x(range.maximum), y1: y, y2: y,
      stroke: colour, "stroke-width": 1.5 }));
    for (const end of [range.minimum, range.maximum])
      svg.append(svgElement("line", { x1: x(end), x2: x(end), y1: y - 5, y2: y + 5,
        stroke: colour, "stroke-width": 1.5 }));
    const bar = svgElement("rect", { x: Math.min(160, x(value)), y: y - 3.5,
      width: Math.max(.7, Math.abs(x(value) - 160)), height: 7, fill: colour });
    const title = svgElement("title", {});
    title.textContent = `${label}: ${signedPP(value)}; strength scenarios ${signedPP(range.minimum)} to ${signedPP(range.maximum)}`;
    bar.append(title); svg.append(bar);
  }
  return svg;
}

export function initializeReturnDrivers() {
  const root = document.querySelector("#participation-return-drivers");
  if (!root || root.dataset.initialized) return;
  root.dataset.initialized = "true";
  const status = root.querySelector("[data-driver-status]");
  try {
    const payload = JSON.parse(root.querySelector("[data-driver-data]").textContent);
    const data = validateModels(payload.data), names = payload.names;
    const office = root.querySelector("[data-driver-office]");
    const search = root.querySelector("[data-driver-search]");
    const order = root.querySelector("[data-driver-order]");
    const host = root.querySelector("[data-driver-rows]");
    const detail = root.querySelector("[data-driver-detail]");
    const select = row => {
      detail.replaceChildren(element("h4", `${names[row.state_code]} · ${row.office === "house"
        ? "House state aggregate" : row.office === "governor" ? "Governor source frame" : "Senate race"}`),
      element("p", "Recalled 2024 President in the current study frame → 2026 selected office. Not automatically the last election for this office.", "caption"));
      const table = element("table"), body = element("tbody");
      table.append(element("caption", "Full accounting · signed known-major-party margin points"));
      for (const [key, label] of effectTerms) {
        const tr = element("tr"), th = element("th", label);
        th.scope = "row"; tr.append(th, element("td", signedPP(row.components_pp[key]), "numeric"));
        body.append(tr);
      }
      table.append(body);
      detail.append(table, element("p", `Within-source change: ${signedPP(row.source_frame_change_pp)}. `
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
    const render = () => {
      const all = driverRows(data, office.value, "", "magnitude", names);
      const rows = driverRows(data, office.value, search.value, order.value, names);
      const bound = driverScale(all);
      root.querySelector("[data-driver-axis]").textContent = `−${bound} pp · 0 · +${bound} pp`;
      status.textContent = `${rows.length} of ${all.length} ${office.value === "house"
        ? "state House aggregates" : office.value === "governor" ? "governor source frames" : "Senate races"} · conditional modeled effects, not observed individual behavior.`;
      host.replaceChildren();
      detail.hidden = true;
      for (const row of rows) {
        const line = element("div", null, "driver-row");
        line.dataset.driverId = row.id;
        const button = element("button", names[row.state_code], "driver-place");
        button.type = "button"; button.addEventListener("click", () => select(row));
        const values = element("p", null, "driver-values");
        const switching = element("span", signedPP(row.components_pp.switching), "driver-switching");
        const nonparticipation = element("span", signedPP(row.components_pp.modeled_nonparticipation), "driver-nonparticipation");
        values.append(switching, nonparticipation);
        line.append(button, plot(row, bound), values);
        const gap = element("p", `Unallocated return/frame gap ${signedPP(row.components_pp.return_frame_gap)}`, "driver-gap");
        line.append(gap); host.append(line);
      }
      if (!rows.length) host.append(element("p", "No matching state in this office's supplied source frame."));
    };
    for (const control of [office, search, order]) {
      control.disabled = false;
      control.addEventListener(control === search ? "input" : "change", render);
    }
    window.addEventListener("participation:effects-state", event => {
      search.value = event.detail;
      render();
    });
    render();
  } catch (error) {
    status.textContent = `Model chart unavailable: ${error.message}. Saved numerical tables and complete downloads remain below.`;
  }
}

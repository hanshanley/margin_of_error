import { loadDataset, checkedDatasetFile } from "./participation-dataset.js";
import { countStates } from "./participation-counts.js";

const contract = "participation.historical_native_counts.v1";
const datasetId = "participation-historical-native-counts";
const years = [2018, 2020];
const identity = /^[a-f0-9]{32}$/;
const labels = new Map([
  ["ballots cast", "ballots_cast"], ["ballots cast - total", "ballots_cast"],
  ["ballots_cast", "ballots_cast"], ["registered voters", "registration_stock"],
  ["registered voters - total", "registration_stock"],
]);
const require = (condition, message) => {
  if (!condition) throw new Error("Unqualified historical native counts: " + message);
};
const https = value => typeof value === "string" && value.startsWith("https://");

export function validateHistoricalNativeIndex(index) {
  require(index?.contract === contract && JSON.stringify(index.years) === JSON.stringify(years), "contract/year");
  require(Array.isArray(index.jurisdictions) && index.jurisdictions.length === 51
    && new Set(index.jurisdictions).size === 51
    && index.jurisdictions.every(code => countStates.includes(code)), "jurisdiction inventory");
  require(index.candidate_votes_used_as_ballots === false
    && index.alternative_sources_or_modes_summed === false
    && index.registration_stocks_are_denominators === false
    && index.outside_projection_years_are_not_classified_as_missing === true, "source-frame promotion");
  require(index.states && typeof index.states === "object" && !Array.isArray(index.states), "state declarations");
  for (const [code, declaration] of Object.entries(index.states))
    require(countStates.includes(code) && declaration.file === `states/${code}.json.gz`
      && Number.isSafeInteger(declaration.records) && declaration.records > 0
      && Array.isArray(declaration.snapshots) && declaration.snapshots.length > 0, "state declaration");
  require(Array.isArray(index.decisions) && index.decisions.length === 102, "all-state decisions");
  const decisions = new Set();
  for (const row of index.decisions) {
    const key = `${row.state_code}|${row.year}`;
    require(countStates.includes(row.state_code) && years.includes(row.year) && !decisions.has(key)
      && [row.source_cells, row.ballot_cells, row.registration_cells].every(value =>
        Number.isSafeInteger(value) && value >= 0)
      && row.source_cells === row.ballot_cells + row.registration_cells
      && row.status === (row.source_cells ? "explicit_administrative_cells"
        : "no_explicit_administrative_cells_in_selected_components")
      && row.turnout_rate_qualified === false && row.geography_join_qualified === false, "decision scope");
    decisions.add(key);
  }
  return index;
}

function nativeOffice(fields) {
  if (typeof fields?.contest === "string") return fields.contest;
  require(Array.isArray(fields?.columns) && Array.isArray(fields.values), "native fields");
  const columns = fields.columns.map((name, index) =>
    ["office", "race"].includes(name.trim().toLowerCase()) ? index : -1).filter(index => index >= 0);
  require(columns.length === 1 && typeof fields.values[columns[0]] === "string", "native office");
  return fields.values[columns[0]];
}

function nativeValue(fields) {
  if ("value" in fields) return fields.value;
  const columns = fields.columns.map((name, index) =>
    ["votes", "total_votes"].includes(name.trim().toLowerCase()) ? index : -1).filter(index => index >= 0);
  require(columns.length === 1 && columns[0] < fields.values.length, "native count field");
  return fields.values[columns[0]];
}

export function validateHistoricalNativeState(data, code, index) {
  const declaration = index.states[code];
  require(data?.contract === contract && data.state_code === code && declaration
    && Array.isArray(data.records) && data.records.length === declaration.records
    && Array.isArray(data.snapshots)
    && JSON.stringify(data.snapshots) === JSON.stringify(declaration.snapshots), "state inventory");
  const snapshots = new Map(), ids = new Set();
  for (const source of data.snapshots) {
    require(identity.test(source.id) && !snapshots.has(source.id) && source.state_code === code
      && years.includes(source.year) && source.election_type === "general"
      && source.additive_with_other_snapshots === false && source.count_clock === null
      && source.timezone === null && https(source.source_url), "snapshot scope");
    snapshots.set(source.id, source);
  }
  for (const row of data.records) {
    const source = snapshots.get(row.snapshot_id), value = row.count?.value;
    require(identity.test(row.id) && !ids.has(row.id) && source
      && row.state_code === code && row.year === source.year
      && ["ballots_cast", "registration_stock"].includes(row.measure)
      && typeof row.measure_literal === "string"
      && labels.get(row.measure_literal.trim().toLowerCase()) === row.measure
      && labels.get(nativeOffice(row.source?.native_fields).trim().toLowerCase()) === row.measure,
    "administrative measure/identity");
    require(row.rate === null && row.denominator === null && row.geography_join === "unreviewed"
      && row.cross_year_identity_approved === false, "rate or boundary promotion");
    require(["county_literal", "unit_literal", "unit_kind", "native_category"].every(key =>
      typeof row[key] === "string") && https(row.source?.url)
      && row.source.url === source.source_url
      && row.source.input_sha256 === source.input_sha256, "source provenance");
    require(["reported", "unknown", "withheld"].includes(row.count.status)
      && typeof row.count.literal === "string"
      && (row.count.status === "reported") === (value !== null)
      && (value === null || Number.isSafeInteger(value) && value >= 0), "count/unknown/zero");
    if (value !== null) {
      const literal = String(nativeValue(row.source.native_fields));
      require(/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.0+)?$/.test(literal)
        && Number(literal.replaceAll(",", "")) === value, "native/canonical count differs");
    }
    ids.add(row.id);
  }
  for (const year of years) {
    const rows = data.records.filter(row => row.year === year);
    const decision = index.decisions.find(row => row.state_code === code && row.year === year);
    require(decision.source_cells === rows.length
      && decision.ballot_cells === rows.filter(row => row.measure === "ballots_cast").length
      && decision.registration_cells === rows.filter(row => row.measure === "registration_stock").length,
    "declared historical source-cell counts");
  }
  return data;
}

export function createHistoricalNativeReader(dependencies = { loadDataset, checkedDatasetFile }) {
  let indexPromise;
  const states = new Map();
  const loadIndex = () => indexPromise ||= dependencies.loadDataset(datasetId)
    .then(({ entry, index }) => {
      require(entry.id === datasetId && https(entry.complete_download?.url), "complete numerical download");
      return { entry, index: validateHistoricalNativeIndex(index) };
    })
    .catch(error => { indexPromise = null; throw error; });
  return { loadIndex, async loadState(code) {
    require(countStates.includes(code), "selected jurisdiction");
    if (states.has(code)) {
      const cached = states.get(code);
      states.delete(code); states.set(code, cached);
      return cached;
    }
    const pending = loadIndex().then(async ({ entry, index }) => {
      const declaration = index.states[code];
      if (!declaration) return { entry, index, state: null };
      require(entry.files[declaration.file], "missing state checksum");
      const data = await dependencies.checkedDatasetFile(entry.base_url,
        { file: declaration.file, ...entry.files[declaration.file] });
      return { entry, index, state: validateHistoricalNativeState(data, code, index) };
    }).catch(error => {
      if (states.get(code) === pending) states.delete(code);
      throw error;
    });
    states.set(code, pending);
    if (states.size > 4) states.delete(states.keys().next().value);
    return pending;
  } };
}

export function historicalNativeRows(data, selection) {
  const query = (selection.query || "").trim().toLocaleLowerCase();
  return (data?.records || []).filter(row => row.year === selection.year
    && row.snapshot_id === selection.snapshot
    && (selection.county === undefined || row.county_literal === selection.county)
    && (!selection.measure || row.measure === selection.measure)
    && (!query || `${row.unit_literal} ${row.native_category}`.toLocaleLowerCase().includes(query)));
}

const reader = createHistoricalNativeReader();
export function installHistoricalNativeCounts(anchor = document.getElementById("participation-coverage"),
  source = reader) {
  if (!anchor) return { setScope() {} };
  const node = (tag, text, className) => {
    const result = document.createElement(tag);
    if (text !== undefined) result.textContent = text;
    if (className) result.className = className;
    return result;
  };
  const panel = node("details", undefined, "source-coverage historical-native-counts");
  panel.id = "historical-native-counts"; panel.hidden = true;
  const summary = node("summary"), content = node("div");
  panel.append(summary, content); anchor.after(panel);
  let generation = 0, scope, loaded = false;
  const load = async () => {
    if (!panel.open || panel.hidden || loaded) return;
    loaded = true;
    const token = generation, selected = { ...scope };
    content.replaceChildren(node("p", "Loading verified historical administrative cells..."));
    let verifiedEntry;
    try {
      verifiedEntry = (await source.loadIndex()).entry;
      const { entry, index, state } = await source.loadState(selected.code);
      if (token !== generation) return;
      content.replaceChildren(node("p",
        "Official workbooks and OpenElections compilations remain separate source snapshots. "
        + "Ballot counts and registration stocks are not population turnout or demographic estimates. "
        + "Alternative files, totals, ballot styles and voting modes are never added. Native labels do not establish matched precincts across years."));
      const downloads = node("ul");
      const complete = entry.complete_download;
      if (https(complete?.url)) {
        const item = node("li"), link = node("a", "Complete numerical inputs, queries, decisions and reproduction", "source-link");
        link.href = complete.url; item.append(link); downloads.append(item);
      }
      if (index.states[selected.code]) {
        const item = node("li"), link = node("a", "Complete state source cells and native fields (JSON.gz)", "source-link");
        link.href = entry.base_url + index.states[selected.code].file;
        item.append(link); downloads.append(item);
      }
      content.append(downloads);
      const snapshots = (state?.snapshots || []).filter(row => row.year === selected.year);
      if (!snapshots.length) {
        content.append(node("p",
          "No explicit ballot or registration cells for this state/year in these selected historical components. "
          + "This is not zero participation or a statement that all other historical sources are missing."));
        return;
      }
      const controls = node("div", undefined, "controls");
      const control = (label, tag = "select") => {
        const wrapper = node("label", label), input = node(tag);
        input.setAttribute("aria-label", label);
        wrapper.append(input); controls.append(wrapper); return input;
      };
      const snapshot = control("Source snapshot"), county = control("County field"),
        measure = control("Native measure"), search = control("Find native unit or category", "input");
      search.type = "search";
      const option = (host, value, label) => {
        const item = node("option", label); item.value = value; host.append(item);
      };
      for (const item of snapshots) option(snapshot, item.id, item.name);
      for (const [value, label] of [["", "Ballot and registration cells"],
        ["ballots_cast", "Native Ballots Cast"], ["registration_stock", "Native registration stock"]])
        option(measure, value, label);
      const note = node("p"), original = node("a", "Pinned source publication", "source-link");
      note.setAttribute("aria-live", "polite");
      const wrap = node("div", undefined, "table-wrap");
      wrap.tabIndex = 0; wrap.setAttribute("role", "region");
      wrap.setAttribute("aria-label", "Historical native source cells, horizontally scrollable");
      const table = node("table"), caption = node("caption"), head = node("thead"), heading = node("tr"),
        body = node("tbody");
      caption.className = "sr-only"; caption.textContent = "Separate historical administrative source cells";
      for (const label of ["Native unit", "Native category", "Measure", "Source count", "Status / literal"])
        heading.append(node("th", label));
      head.append(heading); table.append(caption, head, body); wrap.append(table);
      const paging = node("div", undefined, "controls"), previous = node("button", "Previous 100"),
        next = node("button", "Next 100");
      previous.type = next.type = "button"; paging.append(previous, next);
      content.append(controls, note, original, wrap, paging);
      let offset = 0;
      const draw = () => {
        const rows = historicalNativeRows(state, { year: selected.year, snapshot: snapshot.value,
          county: county.value === "*" ? undefined : county.value.slice("native:".length),
          measure: measure.value, query: search.value });
        const current = snapshots.find(item => item.id === snapshot.value);
        original.href = current.source_url;
        note.textContent = `${rows.length.toLocaleString("en-US")} separate source cells; `
          + `showing ${rows.length ? offset + 1 : 0}-${Math.min(offset + 100, rows.length)}. `
          + "Source count-update clock not supplied/qualified. Counts are not an additive participant total; no rate or geography join is approved.";
        body.replaceChildren();
        for (const row of rows.slice(offset, offset + 100)) {
          const tr = node("tr"); tr.dataset.recordId = row.id;
          const values = [row.unit_literal || "Not supplied", row.native_category || "Not supplied",
            row.measure === "ballots_cast" ? "Native Ballots Cast" : "Registration stock",
            row.count.value === null ? row.count.status === "unknown" ? "Unknown" : "Withheld"
              : row.count.value.toLocaleString("en-US"),
            `${row.count.source_status}: ${row.count.literal || "not supplied"}`];
          for (const value of values) tr.append(node("td", value));
          const fields = node("details"), label = node("summary", "Native fields"),
            raw = node("pre", JSON.stringify(row.source.native_fields, null, 2));
          fields.append(label, raw); tr.children[0].append(fields);
          body.append(tr);
        }
        previous.disabled = offset === 0;
        next.disabled = offset + 100 >= rows.length;
      };
      const selectSnapshot = () => {
        county.replaceChildren(); option(county, "*", "All supplied county fields");
        const names = [...new Set(state.records.filter(row => row.snapshot_id === snapshot.value)
          .map(row => row.county_literal))].sort();
        for (const name of names) option(county, "native:" + name, name || "County field not supplied");
        offset = 0; draw();
      };
      snapshot.addEventListener("change", selectSnapshot);
      for (const input of [county, measure, search]) input.addEventListener(
        input === search ? "input" : "change", () => { offset = 0; draw(); });
      previous.addEventListener("click", () => { offset = Math.max(0, offset - 100); draw(); });
      next.addEventListener("click", () => { offset += 100; draw(); });
      selectSnapshot();
    } catch (error) {
      if (token !== generation) return;
      content.replaceChildren(node("p", `${error.message}. No historical values or rates have been inferred.`));
      if (https(verifiedEntry?.complete_download?.url)) {
        const complete = node("a", "Complete verified numerical package", "source-link");
        complete.href = verifiedEntry.complete_download.url; content.append(complete);
      }
      const retry = node("button", "Retry verified historical source data"); retry.type = "button";
      retry.addEventListener("click", () => { loaded = false; load(); });
      content.append(retry);
    }
  };
  panel.addEventListener("toggle", load);
  return { setScope(value) {
    if (scope && ["year", "code", "enabled", "name"].every(key => scope[key] === value[key])) return;
    generation += 1; scope = { ...value }; loaded = false;
    panel.hidden = !value.enabled || !years.includes(value.year) || !countStates.includes(value.code);
    summary.textContent = `${value.year} source-native ballot and registration cells · ${value.name || value.code || ""}`;
    content.replaceChildren();
    if (!panel.hidden && panel.open) load();
  } };
}

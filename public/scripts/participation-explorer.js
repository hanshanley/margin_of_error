import { installParticipationDownloads, participationDownload } from "./participation-downloads.js";
import { contextualCountyRows } from "./participation-county-context.js";
import { demographicStates, demographicSource, demographicGroups, loadDemographics, demographicRows } from "./participation-state-demographics.js";
import { civicStateSource, civicDimensions, loadCivicStates, civicStateRows, civicGroupOptions } from "./participation-civic-state-demographics.js";
import { countFill, precinctSelectionYears, qualifiedDcPrecinctParticipation, qualifiedVaPrecinctParticipation, qualifiedIndianaMonroePrecinct, hasCountySourceMode, selectCountySourceFrame, qualifiedHawaiiAdministrationReference, qualifiedConnecticutTownReference, qualifiedMaineLocalityReference } from "./participation-geography.js";

installParticipationDownloads(document.querySelector(".participation-page"));
const $ = id => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const MAX_MAP_ZOOM = 16384;
const root = document.querySelector(".participation-page");
const params = new URLSearchParams(location.search);
const colors = ["#284766", "#8c98a6"];
const albers = conicProjection(-96, 29.5, 45.5);
const alaska = conicProjection(-154, 55, 65);
const hawaii = conicProjection(-157, 8, 18);
const labelLocations = {
  AL: [-86.8, 32.8], AK: [-152.5, 64], AZ: [-111.9, 34.2], AR: [-92.4, 34.9],
  CA: [-119.5, 36.8], CO: [-105.55, 39], CT: [-72.7, 41.6], DE: [-75.45, 39],
  DC: [-77.04, 38.9], FL: [-81.7, 27.8], GA: [-83.4, 32.5], HI: [-155.55, 19.65],
  ID: [-114.5, 43.9], IL: [-89, 40], IN: [-86.15, 40], IA: [-93.5, 42],
  KS: [-98.4, 38.5], KY: [-85.2, 37.5], LA: [-92.1, 31], ME: [-69, 45.2],
  MD: [-76.7, 39], MA: [-71.8, 42.2], MI: [-84.7, 43.5], MN: [-94.5, 46],
  MS: [-89.65, 32.8], MO: [-92.5, 38.45], MT: [-110, 47], NE: [-99.8, 41.5],
  NV: [-116.8, 39], NH: [-71.5, 43.8], NJ: [-74.7, 40.1], NM: [-106, 34.4],
  NY: [-75.5, 43], NC: [-79.8, 35.6], ND: [-100.5, 47.5], OH: [-82.8, 40.3],
  OK: [-97.3, 35.5], OR: [-120.6, 44], PA: [-77.8, 40.9], RI: [-71.5, 41.7],
  SC: [-80.8, 33.9], SD: [-100.2, 44.4], TN: [-86.05, 35.8], TX: [-99, 31],
  UT: [-111.7, 39.3], VT: [-72.7, 44], VA: [-79.2, 37.6], WA: [-120.7, 47.3],
  WV: [-80.6, 38.8], WI: [-89.8, 44.7], WY: [-107.5, 43],
};
const views = ["states", "national", "precincts", "updates", "methods"];
const state = {
  view: views.includes(params.get("view")) ? params.get("view") : "states",
  national: [], states: [], ncSummary: [], geometry: null, audits: [],
  nc: new Map(), shapes: new Map(), selectedState: params.get("state") || "North Carolina",
  county: params.get("county") || "", precinct: params.get("precinct") || "",
  table: [], columns: [], generation: 0, viewport: null, map: null, mapPaths: [],
  precinctRows: new Map(), precinctItems: new Map(), searchItems: new Map(), projected: [],
  loadedPrecinctYear: null, loadedCounty: "",
  current: null, currentError: "", ufTurnout: [], reviewedCounties: [], reviewedStates: [], countState: params.get("countState") || "GA",
  currentPath: "", currentLocal: null, currentCounty: "", currentUnit: "",
  countyContext: null, countyContextReview: null,
  currentPrecincts: null, currentPrecinctPath: "", currentPrecinctShapes: new Map(), currentPrecinctError: "",
  currentMunicipalities: {},
  currentPrecinctSelection: "",
  reportingUnitSources: {}, reportingUnitData: new Map(), reportingUnitError: "",
  context: null, contextPath: "", margins: [], contextError: "", subshapes: new Map(),
  results: null, resultsError: "",
  countyResults: null, countyResultsPath: "", countyResultsError: "",
  countyOverview: null,
  precinctResults: null, precinctResultsPath: "", precinctResultShapes: new Map(),
  precinctResultSelection: "", precinctResultsError: "",
  drillKey: "", drillToken: 0, drillTimer: null, subSelection: null,
  methods: null, methodStates: [], methodNational: [], methodsPath: "", methodsError: "",
  viewSelections: {}, precinctControlNote: "", initialized: false,
  precinctHistories: new Map(),
  local: null, localPath: "", localStates: new Map(), localGeometry: new Map(),
  localSelection: null, localError: "",
};
const fmt = value => value == null ? "—" : value.toLocaleString("en-US");
const pct = value => value == null ? "Not available" : value.toFixed(1) + "%";
const typeFor = year => year % 4 === 0 ? "presidential" : "midterm";
const isProvisional = () => $("year").value === "2026";
const stateDemographicView = () => state.view === "national" && !isProvisional()
  && $("demographic-state").value && $("demographic-state").value !== "US";
let demographicsPromise;
let civicStatesPromise, civicStatesData, civicModelInitialized = false;
const civicModelView = () => state.view === "national" && isProvisional() && $("mode").value === "civic_model";
const modeLabels = { available: "Nationwide turnout estimates + official counts",
  uf_vep: "Turnout · eligible population (UF)", uf_vap: "Turnout · voting-age population (UF)",
  official: "Official administrative ballots · partial coverage", in_person_early: "In-person early voting", mail_returned: "Returned mail ballots",
  civic_model: "Civic · modeled participation" };
const currentDimension = () => ({ sex: "gender", age: "age_range" }[$("dimension").value] || $("dimension").value);
const unique = items => [...new Set(items)];
const ufMode = () => isProvisional() && state.view === "states"
  && ["available", "uf_vep", "uf_vap"].includes($("mode").value) && state.ufTurnout.length > 0;
const ufBasis = () => $("mode").value === "uf_vap" ? "vap" : "vep";
const participationRate = row => row?.uf_source && row.turnout_pct != null
  ? row.turnout_pct.toFixed(2) + "%" : pct(row?.turnout_pct);
const titleCase = text => text.toLowerCase().replace(/\b[a-z]/g, c => c.toUpperCase());
const keyFor = row => `${row.county}|${row.precinct}`;
const methodLabels = { election_day: "Election Day · in person", early_in_person: "Early · in person",
  mail: "By mail", domestic_absentee: "Domestic absentee / mail", all_mail: "Vote-by-mail jurisdiction",
  uocava: "Military / overseas absentee", provisional: "Provisional", other: "Other reported",
  unknown: "Unknown / refused" };
const svgNode = (tag, attrs = {}, text = "") => {
  const element = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
  element.textContent = text;
  return element;
};
function html(tag, className = "", text = "") {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}
async function get(path) {
  const response = await fetch(participationDownload("/voter-participation/data/" + path));
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}
async function localGet(path) {
  const response = await fetch(state.localPath + path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  if (!path.endsWith(".gz")) return response.json();
  if (!globalThis.DecompressionStream) throw new Error("This browser cannot read compressed local data; the complete download remains available");
  return new Response(response.body.pipeThrough(new DecompressionStream("gzip"))).json();
}
async function loadLocal() {
  try {
    const response = await fetch("/participation-local.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const pointer = await response.json();
    state.localPath = pointer.base_url;
    state.local = await localGet("index.json");
    const link = html("a", "", "Complete nationwide local participation observations (CSV · gzip)");
    link.href = state.localPath + "observations.csv.gz"; link.download = "";
    if (!$("downloads").querySelector(`a[href="${link.getAttribute("href")}"]`))
      $("downloads").querySelector(".download-links").append(link);
    const coverage = html("a", "", "Every state and election year: local-data coverage (JSON)");
    coverage.href = state.localPath + "coverage.json";
    if (!$("downloads").querySelector(`a[href="${coverage.getAttribute("href")}"]`))
      $("downloads").querySelector(".download-links").append(coverage);
  } catch (error) {
    state.localError = `Nationwide local observations could not be loaded: ${error.message}.`;
  }
}
async function localRows(code) {
  if (!state.localStates.has(code)) {
    const promise = localGet(`states/${code}.json.gz`).catch(error => {
      state.localStates.delete(code); throw error;
    });
    state.localStates.set(code, promise);
  }
  return state.localStates.get(code);
}
const localKey = row => row.history_key;
async function localNavigation(container) {
  const code = stateCode(), year = Number($("year").value);
  container.append(html("h4", "", "Local participation"));
  if (!state.local) {
    container.append(html("p", "selection-note", state.localError || "Local observations are unavailable."));
    return;
  }
  container.append(html("p", "selection-note", "Loading reporting units…"));
  try {
    const rows = await localRows(code);
    if (!container.isConnected) return;
    const current = rows.filter(row => row.year === year);
    const uniqueRows = [...new Map(rows.map(row => [localKey(row), row])).values()]
      .sort((a, b) => a.jurisdiction.localeCompare(b.jurisdiction));
    const label = html("label", "selection-note", "Reporting unit");
    const select = html("select"); select.id = "local-unit-select";
    options(select, [["", "Choose a reporting unit…"], ...uniqueRows.map(row => [localKey(row),
      row.source_details?.missing_jurisdiction_id
        ? `${row.jurisdiction} · ${row.year} source row ${row.source_details.source_row}` : row.jurisdiction])],
      state.localSelection?.code === code ? state.localSelection.key : "");
    label.htmlFor = select.id;
    select.addEventListener("change", () => {
      state.localSelection = select.value ? { code, key: select.value } : null;
      if (state.localSelection) localDetail(rows, state.localSelection.key);
      else $("local-detail")?.replaceChildren(html("p", "selection-note",
        "Select a reporting unit to see its counts and history."));
    });
    container.replaceChildren(html("h4", "", "Local participation"),
      html("p", "selection-note", current.length
        ? `${fmt(current.length)} reported units in ${year}. Choose one for its complete available history, or zoom into the map.`
        : `No verified local observations for ${year}. Other available years remain accessible below; no year is filled or substituted.`),
      label, select, html("p", "selection-note",
        "EAC reporting units are counties, municipalities or state offices—not uniformly precincts. Precinct-specific inputs remain separately identified."));
    if (state.localSelection?.code === code && select.value) localDetail(rows, select.value);
  } catch (error) {
    if (container.isConnected) container.replaceChildren(html("p", "selection-note",
      `Local observations could not be loaded: ${error.message}. No values inferred.`));
  }
}
function localDetail(rows, key) {
  const host = $("local-detail");
  if (!host) return;
  const history = rows.filter(row => localKey(row) === key).sort((a, b) => a.year - b.year);
  if (!history.length) return;
  const year = Number($("year").value), row = history.find(value => value.year === year);
  const name = history[0].jurisdiction;
  host.replaceChildren(html("h4", "", name), html("p", "selection-rate", pct(row?.turnout_pct)),
    html("p", "selection-basis", "Reported participants / source registrations"),
    html("p", "selection-note", `${year}: ${fmt(row?.total_participation)} participants; ${fmt(row?.registered)} registrations. `
      + (row ? row.quality.join(" ") : "No verified observation for this election.")));
  const chart = html("div", "state-chart"); chart.id = "local-history"; host.append(chart);
  const chartRows = history.map(value => ({
    ...value, participants: value.total_participation, series: name, warnings: [],
  }));
  seriesChart(chart, chartRows, { width: 300, height: 210, compact: true, dimension: "local" });
  chart.querySelector("svg")?.setAttribute("aria-label", `${name}: reported participants / total registrations over time`);
  host.append(html("p", "selection-note",
    "Registration definitions and dates vary; these are not citizen or eligible-population turnout rates. 2004/2006 count ballots counted, not the later cast-ballot definition. IDs and names are matched across years, not constant boundaries or the same electorate. Missing rates remain gaps."));
  const details = html("details"), table = html("table", "precinct-history-table"), head = html("thead"), tr = html("tr");
  for (const value of ["Year", "Participants", "Registered", "Rate"]) tr.append(html("th", "", value));
  head.append(tr); table.append(head);
  const body = html("tbody");
  for (const value of [...history].reverse()) {
    const line = html("tr"); line.dataset.year = value.year;
    for (const text of [String(value.year), fmt(value.total_participation), fmt(value.registered), pct(value.turnout_pct)])
      line.append(html("td", "", text));
    body.append(line);
  }
  table.append(body);
  details.append(html("summary", "", "Every observed year and count"), table); host.append(details);
  const source = row || history.at(-1);
  if (row?.methods) {
    const breakdown = html("details"), methodTable = html("table", "precinct-history-table");
    methodTable.append(html("caption", "", "Source-defined ballot-method counts; unavailable modes remain missing."));
    const methodBody = html("tbody");
    for (const [mode, count] of Object.entries(row.methods)) {
      const line = html("tr");
      line.append(html("th", "", methodLabels[mode] || mode.replaceAll("_", " ")),
        html("td", "", count == null ? "Not reported" : fmt(count)));
      methodBody.append(line);
    }
    methodTable.append(methodBody);
    breakdown.append(html("summary", "", "Reported voting-method counts"), methodTable);
    host.append(breakdown);
  }
  host.append(sourceLink(source));
  if (source.registration_comment) host.append(html("p", "selection-note", source.registration_comment));
  if (source.registration_definition) host.append(html("p", "selection-note", source.registration_definition));
  const metadata = html("details");
  metadata.append(html("summary", "", "Original participation reporting notes"),
    html("p", "selection-note", JSON.stringify(source.source_details)));
  host.append(metadata);
}
async function drawLocalGeography(map, selected, code, year, token) {
  const rows = await localRows(code);
  const current = rows.filter(row => row.year === year);
  const municipality = state.local.geometry[String(year)]?.municipality?.[code];
  const level = municipality ? "municipality" : "county";
  const file = state.local.geometry[String(year)]?.[level]?.[code];
  if (!file) {
    $("geography-note").textContent = `No verified ${year} local boundary collection for ${state.selectedState}. Reporting-unit histories remain available in the sidebar.`;
    return;
  }
  if (!state.localGeometry.has(file)) state.localGeometry.set(file, await localGet(file));
  if (token !== state.drillToken || state.map !== map) return;
  const collection = state.localGeometry.get(file);
  const panel = $("selection-panel"), navigation = html("div", "substate-detail"), detail = html("div", "substate-detail");
  navigation.id = "local-navigation"; detail.id = "local-detail";
  detail.append(html("p", "selection-note", "Select a reporting unit on the map or above to see its counts and history."));
  panel.replaceChildren(html("p", "eyebrow", `${year} · administrative reporting`),
    html("h3", "", state.selectedState), navigation, detail);
  localNavigation(navigation);
  const byKey = new Map(current.filter(row => row.geography?.level === level).map(row => [row.geography.key, row]));
  let observed = 0;
  for (const feature of collection.features) {
    const p = feature.properties, row = byKey.get(p.key), item = projectInside(feature, selected.point);
    const rate = row?.turnout_pct;
    if (rate != null) observed++;
    const path = featurePath(item, rate, `${p.name} · ${year}\n${pct(rate)} · ${fmt(row?.total_participation)} participants / ${fmt(row?.registered)} registrations`
      + (row ? "" : "\nNo matched reporting unit; boundary context only"), () => {
      const host = $("local-detail");
      if (row) {
        state.localSelection = { code, key: localKey(row) };
        if ($("local-unit-select")) $("local-unit-select").value = localKey(row);
        localDetail(rows, localKey(row));
      } else if (host) {
        state.localSelection = null;
        if ($("local-unit-select")) $("local-unit-select").value = "";
        host.replaceChildren(html("h4", "", p.name),
          html("p", "selection-note", `No uniquely matched ${year} reporting unit. Missing is not zero turnout.`));
      }
      for (const other of map.detail.querySelectorAll(".selected")) other.classList.remove("selected");
      path.classList.add("selected"); fit(item.bounds);
    }, { class: "map-feature substate-feature", "data-geography": p.key, "data-level": level,
      tabindex: "-1" });
    path.classList.toggle("selected", Boolean(row && state.localSelection?.code === code
      && state.localSelection.key === localKey(row)));
    map.detail.append(path);
  }
  map.localLayer = true;
  map.stateTable ||= { rows: state.table, columns: state.columns };
  setTable(current, [["jurisdiction", "Reporting unit"], ["year", "Year"],
    ["total_participation", "Participants"], ["registered", "Total registrations"],
    ["turnout_pct", "Participation / registrations"], ["quality", "Notes"]]);
  header(`${year} ${typeFor(year)} election · EAC local reporting units`,
    `Local participation in ${state.selectedState}`,
    "Reported participants / total registrations. Select a reporting unit for its available history.",
    "Registration definitions and dates vary by source. These are not CPS population rates or nationwide precinct data. Gray means a missing or unmatched rate.");
  ramp();
  $("coverage-note").textContent = `Local reporting-unit histories: 50 states and D.C., ${Math.min(...state.local.years)}–2024. Reporting geography, registration definitions and source completeness vary; missing years are never filled.`;
  $("geography-note").textContent = `${state.selectedState} · ${year} Census boundaries · ${fmt(collection.features.length)} ${level === "municipality" ? "municipalities / county subdivisions" : "counties / equivalents"} · ${fmt(byKey.size)} matched reporting units · ${fmt(observed)} with participation rates. `
    + ($("map-color").value === "margin" ? "No verified local party margins here; this layer shows participation instead. " : "")
    + "These units are not precincts. Use the sidebar for counts and histories even when a denominator or boundary match is unavailable.";
}
async function loadCurrent() {
  try {
    const audit = $("nationwide-participation");
    if (state.contextPath || audit?.dataset.snapshotDirectory) {
      const path = audit?.dataset.snapshotDirectory
        ? audit.dataset.dataRoot + audit.dataset.snapshotDirectory + "snapshot.json"
        : state.contextPath + "nationwide/snapshot.json";
      const response = await fetch(path);
      if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
      state.current = await response.json();
      state.currentPath = path.replace(/snapshot\.json$/, "");
      return;
    }
    const pointer = await get("nationwide/latest.json");
    state.currentPath = `/voter-participation/data/nationwide/${pointer.snapshot_id}/`;
    state.current = await get(`nationwide/${pointer.snapshot_id}/snapshot.json`);
  } catch (error) {
    state.currentError = `Saved 2026 observations could not be loaded: ${error.message}.`;
  }
}
function loadUfTurnout() {
  const table = document.querySelector('table[data-uf-turnout="2026"]');
  if (!table) return;
  state.ufTurnout = [...table.querySelectorAll("tbody tr")].map(tr => {
    const number = name => {
      const value = tr.getAttribute("data-" + name);
      return value == null || value === "" ? null : Number(value);
    };
    return {
      state: tr.querySelector("th").textContent.trim(), state_code: tr.dataset.stateCode,
      ballots: number("ballots"), vep: number("vep"), vap: number("vap"),
      vep_rate: number("vep-rate"), vap_rate: number("vap-rate"),
      source_status: tr.dataset.sourceStatus, status: tr.dataset.ballotsStatus,
      source_url: table.dataset.sourceUrl,
      source_date: `UF version ${table.dataset.sourceVersion}; captured ${table.dataset.capturedAt}`,
      uf_source: true,
      quality: ["Source-labeled estimates, not final official ballots or Census CPS survey estimates."],
    };
  });
}
function loadReviewedCounties() {
  const table = document.querySelector("table[data-reviewed-county-participation]");
  if (table) state.reviewedCounties = JSON.parse(table.dataset.reviewedCountyParticipation);
  const statewide = document.querySelector("[data-reviewed-state-participation]");
  state.reviewedStates = statewide ? JSON.parse(statewide.dataset.reviewedStateParticipation) : [];
  const additional = document.querySelector("[data-additional-participation]");
  state.additionalCoverage = additional ? JSON.parse(additional.dataset.additionalParticipation) : [];
  const context = document.querySelector("[data-county-context-review]");
  state.countyContext = context ? JSON.parse(context.dataset.countyContextReview) : null;
}
async function currentCountyContextReview() {
  if (!state.countyContext) return null;
  if (!state.countyContextReview) state.countyContextReview = (async () => {
    const pointer = state.countyContext;
    const response = await fetch(pointer.base_url + "review.json");
    if (!response.ok) throw new Error(`Contextual county review: HTTP ${response.status}`);
    const body = await response.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", body);
    const hex = [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
    if (body.byteLength !== pointer.review_bytes || hex !== pointer.review_sha256)
      throw new Error("Contextual county review checksum changed");
    return JSON.parse(new TextDecoder().decode(body));
  })().catch(error => { state.countyContextReview = null; throw error; });
  return state.countyContextReview;
}
function stateParticipationRows() {
  if (!ufMode()) return currentStateRows().map(row => ({
    ...row, turnout_pct: row.validated_pct ?? null,
  }));
  const basis = ufBasis();
  return state.ufTurnout.filter(row => row.state_code !== "US").map(row => ({
    ...row, turnout_pct: row[basis + "_rate"], denominator: row[basis],
    denominator_basis: basis === "vep" ? "voting-eligible population" : "voting-age population",
    observation_type: `UF ${basis.toUpperCase()} turnout · ${row.source_status}`,
  }));
}
    const additionalLocal = new Map();
    async function currentLocal() {
      const code = stateCode();
      const supplement = { counties: state.reviewedCounties, precincts: [] };
      if (state.current?.local_file && !state.currentLocal) state.currentLocal = fetch(state.currentPath + state.current.local_file)
        .then(response => {
          if (!response.ok) throw new Error(`Local 2026 counts: HTTP ${response.status}`);
          return response.json();
        }).then(data => ({
          ...data, counties: [...data.counties, ...state.reviewedCounties.filter(row =>
            !data.counties.some(other => other.state_code === row.state_code
              && (other.county_id === row.county_id || countyName(other.county) === countyName(row.county))))],
        })).catch(error => {
          state.currentLocal = null;
          if (state.reviewedCounties.some(row => row.state_code === code)
            || state.additionalCoverage.some(row => row.state_code === code)) return supplement;
          throw error;
        });
      const data = state.current?.local_file ? await Promise.resolve(state.currentLocal) : supplement;
      if (!state.additionalCoverage.some(row => row.state_code === code)) return data;
      if (!additionalLocal.has(code)) additionalLocal.set(code, fetch(`/participation-local/${code}.json.gz`)
        .then(response => {
          if (!response.ok) throw new Error(`Additional ${code} participation: HTTP ${response.status}`);
          if (!globalThis.DecompressionStream)
            throw new Error("Compressed participation is unsupported by this browser");
          return new Response(response.body.pipeThrough(new DecompressionStream("gzip"))).json();
        }).catch(error => {
          additionalLocal.delete(code);
          return { counties: [], precincts: [], additional_error: error.message };
        }));
      const additional = await additionalLocal.get(code);
      const combined = [...data.counties, ...additional.counties.filter(row =>
        !data.counties.some(other => other.state_code === row.state_code
          && countyName(other.county) === countyName(row.county)))];
      let selectedCounties;
      try {
        selectedCounties = selectCountySourceFrame({ ...additional, counties: combined }, code, $("mode").value);
      } catch (error) {
        additionalLocal.delete(code);
        throw error;
      }
      const scoped = hasCountySourceMode(code, $("mode").value) || selectedCounties !== combined;
      const baseCounties = scoped ? combined.filter(row => row.state_code !== code) : combined;
      return { ...data,
        counties: scoped ? [...baseCounties, ...selectedCounties] : combined,
        precincts: scoped ? [] : [...data.precincts, ...additional.precincts],
        nongeographic: scoped ? [] : additional.nongeographic || [], additional_error: additional.additional_error,
      };
    }
    const countyName = value => value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .toUpperCase().replace(/\s*\(VOTE CENTER\)/g, "").replace(/\b(COUNTY|PARISH)\b/g, "")
      .replace(/[^A-Z0-9]/g, "");
    const electorateLabel = row => row.denominator_basis.replaceAll("_", " ");
    const participationLabel = row => row.participation_measure_label || row.participation_measure_literal;
    function currentCountDetail(host, row, county = false) {
      const approvedGeometry = row.maps_approved || row.state_code === "MI"
        && state.currentPrecinctShapes.get("MI")?.features.some(({ properties: p }) =>
          p.maps_approved && p.unit_key === row.unit_key && p.county_id === row.county_id);
      host.replaceChildren(html("h4", "", county ? row.county : row.unit),
        html("p", "selection-rate", fmt(row.ballots)),
        html("p", "selection-basis", row.ballots === null ? row.native_record?.source_scope_review?.startsWith("withheld_")
          ? "Counted-ballot total withheld · native counting scope unresolved"
          : row.native_record?.source_scope_review === "missing_declared_report"
            ? "County total not supplied · no declared county report"
            : row.native_record?.all_statistics_reported === "false"
              ? "County total not supplied · incomplete native statistics" : "County total not supplied · select a source reporting unit"
          : row.review_id ? `2026 ${participationLabel(row) || "ballots reported"} · not final/certified` : "2026 ballots reported · unofficial"),
        html("p", "selection-note", `${fmt(row.denominator)} ${electorateLabel(row)}; `
          + `${pct(row.reported_pct)} ${participationLabel(row) || "reported-ballot"} fraction. Not final turnout or a CPS estimate.`),
        html("p", "selection-note", `Source update: ${row.source_update_label || "not supplied"}. `
          + row.quality.join(" ")), sourceLink(row));
      if (row.review_id) {
        host.append(html("p", "selection-note", `Native result-status literal: ${row.source_status_literal || "not supplied"}.`),
          html("p", "selection-note", `Native printed fraction: ${row.native_printed_pct ?? "not supplied"}. `
          + (row.reported_pct === null ? "Analysis fraction withheld / not supplied. "
            : `Reviewed fraction from these counts: ${row.reported_pct.toFixed(2)}%. `)
          + "Printed and calculated values are separate; neither establishes finished counting."),
          html("p", "selection-note", row.source_reporting_label));
        const complete = html("a", "source-link", row.geography_level === "municipality"
          ? "Complete locality tables and source package" : "Complete county tables and source package");
        complete.href = row.complete_download_url; host.append(complete);
        if (!county) host.append(html("p", "selection-note",
          `Native reporting-unit type: ${row.unit_kind.replaceAll("_", " ")}. `
          + (approvedGeometry ? "A separate subsequent review qualifies this direct-count precinct identity; the original source review and withheld rate remain unchanged."
            : "This source row is not approved as precinct geography.")));
      } else if (county) host.append(html("p", "selection-note",
        `${fmt(row.reported_units)} / ${fmt(row.total_units)} source precincts reporting. `
        + `${fmt(row.source_rows)} source rows available below; special units and vote centers are identified separately.`));
      else host.append(html("p", "selection-note",
        `${row.unit_kind.replaceAll("_", " ")}. County + snapshot-local row ordinal identifies this 2026 reporting row, not a stable historical precinct. Boundary matches are documented separately on the precinct map.`));
    }
    async function currentNavigation(container) {
      container.append(html("p", "selection-note", "Loading 2026 local counts…"));
      const code = stateCode();
      try {
        const data = await currentLocal();
        if (!container.isConnected || code !== stateCode()) return;
        const counties = data?.counties.filter(row => row.state_code === code) ?? [];
        const administrations = code === "HI" && counties.length === 4
          && counties.every(row => row.geography_level === "election_administration");
        const towns = code === "CT" && counties.length === 169
          && counties.every(row => row.geography_level === "municipality");
        const localityActivity = code === "ME" && counties.length === 480
          && counties.every(row => row.geography_level === "source_locality_activity");
        const providerActivity = counties.length > 0
          && counties.every(row => row.source_provider === "civicAPI early activity");
        if (!counties.length) {
          container.replaceChildren(html("h4", "", "2026 local reporting"),
            html("p", "selection-note", data.additional_error
              ? `${data.additional_error}. Imported source tables and complete downloads remain in Methods & data; no missing observations are replaced with zero.`
              : "No verified full-election county/precinct counts ingested for this state yet. Statewide early/mail observations above are separate, not final turnout."));
          return;
        }
        const label = html("label", "selection-note", localityActivity ? "2026 source local reporting area"
          : administrations ? "2026 election administration" : "2026 county / native locality");
        const select = html("select"); select.id = "current-county-select"; label.htmlFor = select.id;
        options(select, [["", administrations ? "Choose an election administration…" : "Choose a county / locality…"], ...counties.map(row => [row.county_id,
          row.county + (row.geography_level === "municipality" ? " · municipality" : "")])],
          state.currentCounty.startsWith(code + "|") ? state.currentCounty.slice(code.length + 1) : "");
        const detail = html("div", "substate-detail"); detail.id = "current-county-detail";
        const units = html("div", "substate-detail"); units.id = "current-unit-navigation";
        container.replaceChildren(html("h4", "", "2026 local reporting"), label, select, detail, units);
        if (data.additional_error) container.append(html("p", "selection-note",
          `${data.additional_error}. Imported source tables and complete downloads remain in Methods & data.`));
        for (const row of data.nongeographic || []) container.append(html("p", "selection-note",
          `${row.county}: ${fmt(row.ballots)} ballots in a separate nongeographic reporting unit; not assigned to county or municipal geography.`));
        const additional = counties.filter(row => row.review_id);
        if (additional.length) {
          const overview = html("div", "substate-detail"); overview.id = "reviewed-county-overview";
          overview.append(html("p", "selection-note",
            `${additional.length} reviewed ${localityActivity ? "source local-area observations" : towns ? "native towns" : administrations ? "election administrations" : code === "DC" ? "county-equivalent observation" : "county / locality observations"}. `
            + (providerActivity ? "Provider-reported early activity, not official all-method ballots, unique people or UF turnout. "
              : "Native counts and source reporting units, not UF population-based turnout. ")
            + "Missing county totals and withheld rates are not zero. "
            + "Source coverage does not establish finished counting. "
            + (localityActivity ? "480 of 584 source regions match the full 528-area 2024 contextual reference. Each mode retains 104 source regions and 48 reference areas held; full queries are downloadable. Not county totals or certified 2026 precincts."
              : towns ? "Connecticut's 169 town VV counts use held 2024 contextual municipality shapes, not nine county totals or certified 2026 precincts. Native Total is not added again; rates stay withheld."
              : administrations ? "Maui includes Kalawao. Reporting areas group complete 2026 Census components; no separate Maui/Kalawao counts or rates are allocated."
              : code === "RI"
              ? "Rhode Island municipality counts use explicitly dated 2024 Census reference shapes; all rates remain withheld and no town counts are assigned to precincts."
              : "County map joins require the separate contextual identity review; municipalities and reporting-unit containers are not mapped as counties.")));
          const previews = additional.every(row => row.review_id.startsWith("additional:"))
            ? additional.slice(0, 4) : additional;
          for (const row of previews) {
            const button = html("button", "selection-link",
              row.ballots === null ? `${row.county}: ${fmt(row.source_rows)} source reporting-unit observations; county total not supplied`
                : towns || administrations || providerActivity ? `${row.county}: ${fmt(row.ballots)} ${participationLabel(row)} · no rate`
                  : `${row.county}: ${fmt(row.ballots)} ${participationLabel(row) || "ballots"} / ${fmt(row.denominator)} ${electorateLabel(row)} (${pct(row.reported_pct)})`);
            button.type = "button"; button.dataset.countyId = row.county_id;
            button.addEventListener("click", () => { select.value = row.county_id; select.dispatchEvent(new Event("change")); });
            overview.append(button);
          }
          if (previews.length < additional.length) overview.append(html("p", "selection-note",
            `Choose any of the ${additional.length} counties / localities from the selector below.`));
          container.insertBefore(overview, label);
        }
        const choose = () => {
          const county = counties.find(row => row.county_id === select.value);
          const previousUnit = state.currentCounty === code + "|" + select.value ? state.currentUnit : "";
          state.currentCounty = code + "|" + select.value; state.currentUnit = "";
          detail.replaceChildren(); units.replaceChildren();
          if (!county) return;
          currentCountDetail(detail, county, true);
          const rows = data.precincts.filter(row => row.state_code === code && row.county_id === county.county_id);
          setTable(rows.length ? rows : [county], rows.length
            ? [["county", "County"], ["unit", "Source precinct / reporting location"], ["unit_kind", "Unit type"],
              ["ballots", "Ballots reported"], ["denominator", "Source electorate"],
              ["reported_pct", "Reported-ballot fraction"], ["quality", "Notes"]]
            : [["county", administrations ? "Election administration" : "County"], ["ballots", participationLabel(county) || "Ballots reported"], ["denominator", "Source electorate"],
              ["reported_pct", participationLabel(county) ? `${participationLabel(county)} fraction` : "Reported-ballot fraction"],
              ...(county.review_id ? [["native_printed_pct", "Native printed fraction"],
                ["source_status_literal", "Native result-status literal"],
                ["source_update_label", "Source update"], ["source_reporting_label", "Native reporting status"]] : []),
              ["quality", "Notes"]]);
          if (!rows.length) {
            units.append(html("p", "selection-note", "Native locality counts only; no reporting-unit table connected here. Complete source packages remain available."));
            return;
          }
          const unitLabel = html("label", "selection-note", "Precinct / source reporting row");
          const unitSelect = html("select"); unitSelect.id = "current-unit-select"; unitLabel.htmlFor = unitSelect.id;
          options(unitSelect, [["", "Choose a precinct / reporting row…"],
            ...rows.map(row => [row.unit_key, row.unit
              + (rows.filter(other => other.unit === row.unit).length > 1 ? ` · source row ${row.unit_key.split("|").at(-1)}` : "")
              + (row.unit_kind === "precinct" ? "" : ` · ${row.unit_kind.replaceAll("_", " ")}`)])]);
          const unitDetail = html("div", "substate-detail"); unitDetail.id = "current-unit-detail";
          unitSelect.addEventListener("change", () => {
            state.currentUnit = unitSelect.value;
            const row = rows.find(row => row.unit_key === unitSelect.value);
            if (row) currentCountDetail(unitDetail, row);
            else unitDetail.replaceChildren();
          });
          units.append(unitLabel, unitSelect, unitDetail,
            html("p", "selection-note", "Every source row is available in the observations table and complete downloads. No early/mail counts are added to these ballot totals."));
          if (rows.some(row => row.unit_key === previousUnit)) {
            unitSelect.value = previousUnit;
            unitSelect.dispatchEvent(new Event("change"));
          }
        };
        select.addEventListener("change", choose);
        if (select.value) choose();
      } catch (error) {
        if (container.isConnected) container.replaceChildren(html("p", "selection-note",
          `${error.message}. No local counts inferred; complete downloads remain in Methods & data.`));
      }
    }
    async function drawCurrentMunicipalityGeography(map, selected, code, token) {
      const data = await currentLocal();
      const observations = data?.counties.filter(row => row.state_code === code
        && row.geography_level === "municipality") ?? [];
      const metadata = state.currentMunicipalities[code], vermont = code === "VT";
      const file = vermont ? metadata?.url : state.local?.geometry?.["2024"]?.municipality?.[code];
      if (token !== state.drillToken || state.map !== map) return;
      if (!file) {
        $("geography-note").textContent = `${state.selectedState} reference municipality boundaries could not be loaded. Native locality counts remain available in the sidebar.`;
        return;
      }
      if (!state.localGeometry.has(file)) {
        if (vermont) {
          const response = await fetch(file);
          if (!response.ok) throw new Error(`Frozen municipal geometry: HTTP ${response.status}`);
          const compressed = await response.arrayBuffer();
          const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", compressed))]
            .map(byte => byte.toString(16).padStart(2, "0")).join("");
          if (digest !== metadata.geometry_sha256) throw new Error("Frozen municipal geometry checksum differs");
          state.localGeometry.set(file,
            await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream("gzip"))).json());
        } else state.localGeometry.set(file, await localGet(file));
      }
      if (token !== state.drillToken || state.map !== map) return;
      const collection = state.localGeometry.get(file), byName = new Map();
      for (const row of observations) {
        const key = countyName(row.county);
        if (byName.has(key)) throw new Error(`Duplicate ${code} municipality identity`);
        byName.set(key, row);
      }
      const shapeNames = collection.features.map(feature => countyName(feature.properties.name));
      const count = vermont ? metadata.features : 39;
      if (observations.length !== count || collection.features.length !== count
        || new Set(shapeNames).size !== count || shapeNames.some(name => !byName.has(name))
        || (vermont ? observations.filter(row => row.reported_pct !== null).length !== metadata.rates
          : observations.some(row => row.reported_pct !== null)))
        throw new Error(`${code} municipality reference-identity gate failed`);
      if (vermont && collection.features.some(({ properties: p }) => {
        const row = byName.get(countyName(p.name));
        return p.ballots !== row.ballots || p.registered_voters !== row.denominator
          || p.registered_turnout_pct !== row.reported_pct;
      })) throw new Error("Frozen Vermont observations differ from the qualified municipality join");
      const reference = vermont ? metadata.boundary_label : "2024 Census reference boundaries";
      const maximum = Math.max(0, ...observations.map(row => row.ballots ?? 0));
      for (const feature of collection.features) {
        const row = byName.get(countyName(feature.properties.name));
        const item = projectInside(feature, selected.point);
        const path = featurePath(item, row.reported_pct,
          `${feature.properties.name} · 2026 observations on ${reference}\n`
          + `${fmt(row.ballots)} ballots · ${fmt(row.denominator)} source registrations`
          + `\n${row.reported_pct === null ? "Rate withheld" : pct(row.reported_pct)}; municipality counts are not assigned to precincts.`, () => {
            if ($("current-county-select")) {
              $("current-county-select").value = row.county_id;
              $("current-county-select").dispatchEvent(new Event("change"));
            }
            for (const other of map.detail.querySelectorAll(".selected")) other.classList.remove("selected");
            path.classList.add("selected"); fit(item.bounds);
          }, { class: "map-feature substate-feature", "data-geography": feature.properties.key,
            "data-level": "municipality", "data-rate": row.reported_pct ?? "", "data-count": row.ballots,
            "data-registered": row.denominator,
            "data-source-county-id": row.county_id, tabindex: "-1",
            ...(!vermont ? { fill: countFill(row.ballots, maximum), "data-count-measure": "reported_ballots" } : {}) });
        map.detail.append(path);
      }
      map.localLayer = true;
      map.stateTable ||= { rows: state.table, columns: state.columns };
      setTable(observations, [["county", "Municipality"], ["ballots", "Ballots reported"],
        ["denominator", "Source registrations"], ["reported_pct", "Analysis fraction"],
        ["source_update_label", "Source update"], ["quality", "Notes"]]);
      header("2026 midterms · uncertified municipality observations", `Local participation in ${state.selectedState}`,
        vermont ? "Native municipality ballots / source-registered voters; six reviewed rates remain withheld."
          : "Native municipality ballots and registrations; no analysis fraction is calculated or displayed.",
        `${reference}, explicitly not a newly verified 2026 precinct-boundary snapshot. Municipal counts are never assigned to legislative reporting splits or precincts.`);
      if (vermont) {
        ramp();
        const complete = html("a", "source-link", "Complete municipality counts, exact boundary query and verification (ZIP)");
        complete.href = metadata.complete_download_url; $("caption").append(" ", complete);
      } else countLegend(maximum, "Municipality ballots · no rate");
      $("coverage-note").textContent = vermont
        ? "247 municipality observations; 241 reviewed rates and six withheld. Nine unincorporated reference polygons have no source observation and remain excluded."
        : "39 municipality observations; all analysis rates remain withheld. Federal and limited-only units are not assigned to towns or precincts.";
      $("geography-note").textContent = `${state.selectedState} · ${count} municipality observations on ${reference} · `
        + `${vermont ? metadata.rates : 0} approved rates. `
        + (vermont ? "Gray is withheld, not zero. " : "Color shows ballot counts, not a rate. ")
        + "Select a municipality for native ballots and registrations. No municipal count or registration is assigned to a precinct; Federal/limited-only units remain unallocated.";
    }
    async function drawCurrentGeography(map, selected, code, token) {
      if (code === "VT") return drawCurrentMunicipalityGeography(map, selected, code, token);
      const data = await currentLocal();
      if (token !== state.drillToken || state.map !== map) return;
      const observations = data?.counties.filter(row => row.state_code === code) ?? [];
      const reference = observations.find(row => row.reference_geometry)?.reference_geometry;
      const administrations = code === "HI" && reference?.geography_scope === "native_election_administration";
      const towns = code === "CT" && reference?.geography_scope === "native_town_reporting_area";
      const localityActivity = code === "ME" && reference?.geography_scope === "provider_partial_locality_activity";
      const providerActivity = observations.length > 0
        && observations.every(row => row.source_provider === "civicAPI early activity");
      const file = reference?.url || state.context?.geometry.county?.[code];
      if (!observations.length && state.countyResults?.year === 2026 && state.countyResults.coverage[code])
        return drawCountyCountFallback(map, selected, code, 2026, token,
          "County participation is unavailable.");
      if (!observations.length) {
        const message = `No loaded 2026 county participation observations for ${state.selectedState}.`;
        header("2026 · county coverage", `County turnout unavailable in ${state.selectedState}`,
          message, "The statewide estimate remains visible. Missing county observations are not zero turnout.");
        $("coverage-note").textContent = message;
        $("geography-note").textContent = "State context only; no county rates are inferred.";
        $("substate-detail")?.replaceChildren(html("h4", "", message));
        return;
      }
      if (!file) {
        $("geography-note").textContent = "County context boundaries could not be loaded. Verified 2026 county/precinct counts remain accessible in the sidebar.";
        return;
      }
      const cacheKey = reference ? `native-county:${file}|${reference.sha256}` : file;
      if (!state.subshapes.has(cacheKey)) {
        if (reference) {
          const promise = (async () => {
            const response = await fetch(file);
            if (!response.ok) throw new Error(`Native county reference: HTTP ${response.status}`);
            const raw = await response.arrayBuffer();
            const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", raw))]
              .map(value => value.toString(16).padStart(2, "0")).join("");
            if (hash !== reference.sha256) throw new Error("Native county reference checksum disagrees");
            return countyJSON(new Response(raw));
          })().catch(error => { state.subshapes.delete(cacheKey); throw error; });
          state.subshapes.set(cacheKey, promise);
        } else state.subshapes.set(cacheKey, await contextGet(file));
      }
      if (token !== state.drillToken || state.map !== map) return;
      const collection = await state.subshapes.get(cacheKey);
      if (token !== state.drillToken || state.map !== map) return;
      const nativeByFips = new Map();
      if (reference) {
        if (towns && !qualifiedConnecticutTownReference(observations, reference, collection)) {
          additionalLocal.delete(code);
          throw new Error("Unqualified Connecticut town reference; county or precinct totals are not invented");
        }
        if (localityActivity && !qualifiedMaineLocalityReference(observations, reference, collection)) {
          additionalLocal.delete(code);
          throw new Error("Unqualified Maine locality reference; unmatched source regions are not allocated");
        }
        if (reference.identity_field && !towns && !localityActivity && (!administrations
          || !qualifiedHawaiiAdministrationReference(observations, reference, collection))) {
          additionalLocal.delete(code);
          throw new Error("Unqualified election-administration reference; separate Maui/Kalawao counts are not invented");
        }
        for (const row of observations) {
          const identity = localityActivity ? row.reference_municipality_key
            : administrations || towns ? row.source_administration_id : row.county_fips;
          if (row.reference_geometry?.sha256 !== reference.sha256 || nativeByFips.has(identity)) {
            additionalLocal.delete(code);
            throw new Error("Mixed or duplicate native county reference identities");
          }
          nativeByFips.set(identity, row);
        }
        const partial = reference.partial_county_fips;
        if (partial !== undefined && (code !== "MI" || reference.counties !== 83
          || !Array.isArray(partial) || partial.length !== 2 || new Set(partial).size !== 2
          || nativeByFips.size !== 2 || partial.some(fips => !nativeByFips.has(fips)))) {
          additionalLocal.delete(code);
          throw new Error("Unqualified partial native county-parent scope");
        }
        const shapeIds = new Set(collection.features.map(feature => feature.properties.key));
        const boundaryYear = towns || localityActivity ? 2024 : 2026;
        const identities = towns || localityActivity ? reference.localities : reference.counties;
        if (reference.boundary_year !== boundaryYear || (!partial && !localityActivity && observations.length !== identities)
          || collection.features.length !== identities
          || shapeIds.size !== identities
          || [...nativeByFips.keys()].some(fips => !shapeIds.has(fips))
          || collection.features.some(({ properties: p }) => p.state_code !== code || p.boundary_year !== boundaryYear
            || (nativeByFips.has(p.key)
              ? !localityActivity && countyName(p.name) !== countyName(nativeByFips.get(p.key).county)
              : !partial && !localityActivity))) {
          additionalLocal.delete(code);
          throw new Error("Native whole-county inventory disagrees with the verified 2026 reference");
        }
      }
      let contextRows = new Map(), contextError = "";
      try {
        const review = reference ? null : await currentCountyContextReview();
        if (review) contextRows = await contextualCountyRows(observations, review, collection, code, state.contextPath, file);
      } catch (error) {
        contextError = `${error.message}. Independently reviewed county joins are withheld; source observations remain in the sidebar. `;
      }
      if (token !== state.drillToken || state.map !== map) return;
      const contextualIds = new Set([...contextRows.values()].map(row => row.county_id));
      const counties = observations.filter(row => row.maps_approved !== false
        && (!row.reference_geometry || row.reference_geometry.url === file)
        || contextualIds.has(row.county_id));
      if (observations.length && !counties.length) {
        if (state.countyResults?.year === 2026 && state.countyResults.coverage[code])
          return drawCountyCountFallback(map, selected, code, 2026, token,
            "Participation map joins are withheld; native observations remain in the sidebar.");
        $("geography-note").textContent = contextError + `${state.selectedState}: ${observations.length} source county / locality observations `
          + "are available in the sidebar, but no whole-county participation joins are approved. "
          + "Municipalities and source reporting-unit containers are not aggregated into counties. The state estimate remains visible.";
        return;
      }
      const byName = new Map(), duplicates = new Set();
      for (const row of counties.filter(row => row.maps_approved !== false)) {
        const key = countyName(row.county);
        if (byName.has(key)) duplicates.add(key);
        byName.set(key, row);
      }
      for (const key of duplicates) byName.delete(key);
      const features = collection.features;
      const shapeCounts = new Map();
      for (const feature of features) {
        const key = countyName(feature.properties.name);
        shapeCounts.set(key, (shapeCounts.get(key) || 0) + 1);
      }
      let observed = 0;
      const countsOnly = !counties.some(row => row.reported_pct != null);
      const measures = [...new Set(counties.map(participationLabel).filter(Boolean))];
      const countLabel = !providerActivity && code === "MD" && counties.every(row => row.cast_ballot_count_qualified === false)
        ? "Cards Cast (not unique voters)" : measures.length === 1 ? measures[0]
          : measures.length ? "Source participation count" : "Ballots reported";
      const availableCounts = counties.filter(row => row.ballots != null).length;
      const maximum = Math.max(0, ...counties.map(row => row.ballots ?? 0));
      for (const feature of features) {
        const key = countyName(feature.properties.name);
        const contextual = contextRows.get(feature.properties.key);
        const row = contextual || nativeByFips.get(feature.properties.key)
          || (!localityActivity && shapeCounts.get(key) === 1 ? byName.get(key) : null);
        const item = projectInside(feature, selected.point), rate = row?.reported_pct;
        if (rate != null) observed++;
        const path = featurePath(item, rate,
          `${feature.properties.name} · 2026\n${fmt(row?.ballots)} ${row ? participationLabel(row) || "ballots reported" : "ballots reported"} · ${pct(rate)}`
          + (row ? "\nSource-defined electorate; not final turnout. Missing rates are not zero."
            + (contextual ? "\nSeparately reviewed Census county identity join; approximate 2024 contextual shape, not certified 2026 election geography." : "")
            : localityActivity ? "\nNo uniquely matched source activity count; missing is not zero."
              : "\nNo matched county counts"), () => {
            if (row && $("current-county-select")) {
              $("current-county-select").value = row.county_id;
              $("current-county-select").dispatchEvent(new Event("change"));
            } else if (reference?.partial_county_fips || localityActivity) {
              const select = $("current-county-select");
              if (select) { select.value = ""; select.dispatchEvent(new Event("change")); }
              const message = localityActivity
                ? "No uniquely matched source activity count for this reference area. Ambiguous and unmatched regions are held, not allocated or filled with zero."
                : "No matching county ballot parent in this source. Only Bay and Isabella are observed; missing counts are not zero.";
              $("current-county-detail")?.replaceChildren(html("h4", "", feature.properties.name),
                html("p", "selection-note", message));
              setTable([{ county: feature.properties.name, ballots: null, reported_pct: null, quality: [message] }],
                [["county", localityActivity ? "Reference locality" : "County"], ["ballots", localityActivity ? "Source activity count" : "Ballots reported"],
                  ["reported_pct", "Reported-ballot fraction"], ["quality", "Notes"]]);
              syncURL();
            }
            for (const other of map.detail.querySelectorAll(".selected")) other.classList.remove("selected");
            path.classList.add("selected"); fit(item.bounds);
          }, { class: "map-feature substate-feature", "data-geography": feature.properties.key,
            "data-level": towns || localityActivity ? "municipality" : "county", "data-rate": rate ?? "", "data-count": row?.ballots ?? "",
            "data-source-county-id": row?.county_id ?? "", "data-reference-year": reference?.boundary_year ?? 2024,
            "data-context-review": reference ? reference.review_id || "native-county-parents-20261109-01"
              : contextual ? state.countyContext.base_url.split("/").filter(Boolean).at(-1) : "",
            tabindex: "-1",
            ...(countsOnly ? { fill: countFill(row?.ballots, maximum), "data-count-measure": "source_participation_count" } : {}) });
        map.detail.append(path);
      }
      map.localLayer = true;
      map.stateTable ||= { rows: state.table, columns: state.columns };
      setTable(counties, [["county", localityActivity ? "Source locality" : towns ? "Town" : administrations ? "Election administration" : "County"], ["ballots", countLabel],
        ["denominator", "Source electorate"], ["reported_pct", "Reported-ballot fraction"],
        ["reported_units", "Precincts reporting"], ["total_units", "Total precincts"], ["quality", "Notes"]]);
      header(providerActivity ? "2026 project · provider-reported source activity"
        : "2026 midterms · unofficial administrative counts", localityActivity
          ? `Local source activity in ${state.selectedState}` : `${towns ? "Town" : "Local"} participation in ${state.selectedState}`,
        countsOnly ? (providerActivity
          ? `${countLabel}. This is provider-reported source activity, not official full-election turnout, certified ballots or unique people.`
          : towns ? "Native town VV counts, not candidate choices or certified cast ballots/unique people. Source EV, modes and printed percentages remain separate; no analysis rate is qualified."
          : code === "WV"
          ? `${countLabel}. Counts are source-specific snapshots, not full-election turnout rates; early, returned and all-method frames stay separate.`
          : code === "MD"
          ? "Color shows native Cards Cast, not unique voters or qualified cast ballots. No county turnout rates are qualified."
          : "Color shows source participation counts; no county turnout rates are qualified. Select a county for its original counts.")
          : "Reported ballots / source-defined electorate. Select a county, then a precinct or reporting row in the sidebar.",
        (countsOnly ? `Not final turnout. Color shows counts, not a fraction; ${towns || localityActivity ? "localities" : "counties"} have different population sizes. `
          : "Not final turnout. County colors use their own reviewed reported fraction, not the UF state population denominator. Counts with missing or withheld rates remain gray. ")
        + (providerActivity ? "Native source dates are retained below and differ across frames; collector 2026 context is not an independently qualified native election identifier. Early and returned frames are never added. " : "")
        + (localityActivity ? "480 source regions match the full 528-area 2024 contextual municipality reference. Per mode, 104 source regions and 48 reference areas remain held, not allocated or filled with zero. Historical counts are never transferred. Not county totals or certified 2026 precincts. "
          : towns ? "169 native towns use the held full 2024 contextual municipality reference, not 2026 election or precinct boundaries. Native Total is separate, not an extra town. No nine-county totals or precinct observations are inferred. "
          : administrations ? "Four election administrations use grouped full 2026 Census county components; Maui includes Kalawao. No separate Maui/Kalawao count is supplied, allocated or duplicated. These are not certified precinct boundaries. "
          : providerActivity ? "Provider-region identities are separately matched to the full 2026 Census county reference; these are not native FIPS, official county parents or precincts. "
            : reference ? "Whole-county native parents use checksum-verified 2026 Census county references, not precincts. "
          : "Separately reviewed identity joins retain the original source records. Approximate 2024 Census counties are contextual shapes, not certified 2026 election or precinct boundaries.")
        + (code === "WV" ? "Early in-person and returned tables are through October 31, released November 2; native clocks/timezones are absent. "
          + "Full-election county reports are separate November 3 snapshots, not a common statewide cutoff." : ""));
      if (countsOnly) countLegend(maximum, providerActivity || towns ? countLabel + " · no rate"
        : code === "WV" ? countLabel + " · no rate"
        : code === "MD" ? "Native Cards Cast · not unique voters" : "Source participation counts · no rate");
      else ramp();
      $("geography-note").textContent = (localityActivity
        ? "Maine · 480 mapped local source counts · 528 full 2024 contextual areas · 104 source regions / 48 reference areas held per mode · no rates. Missing is not zero; no county or precinct allocation. "
        : towns
        ? "Connecticut · 169 native town observations · 2024 contextual municipality shapes · no analysis rates. Not nine county totals or certified 2026 precincts. "
        : administrations
        ? `${state.selectedState} · 4 election administrations · 5 Census county components · no analysis rates. Maui includes Kalawao; no separate totals are invented. `
        : `${state.selectedState} · ${fmt(counties.length)} county observations · `
          + `${fmt(observed)} reviewed county rates on ${reference?.boundary_year ?? 2024} Census reference boundaries; `
          + `${fmt(reference ? nativeByFips.size : contextRows.size)} reviewed county identity joins. `)
        + (reference?.partial_county_fips
          ? `Only ${fmt(nativeByFips.size)} of ${fmt(reference.counties)} counties have native parents in this source; other counties are missing, not zero. ` : "")
        + (availableCounts < counties.length
          ? `${fmt(availableCounts)} available participation counts; ${fmt(counties.length - availableCounts)} source totals are withheld, not zero turnout. ` : "")
        + "Gray does not mean zero participation; select a county to inspect its actual counts and missingness. "
        + "Precinct mapping uses a separate, source-specific layer; use the sidebar where a qualified 2026 layer is available. "
        + contextError
        + ($("map-color").value === "margin" ? "This local layer shows participation, not party margins." : "");
    }
async function loadCurrentPrecincts() {
  try {
    const pointer = await fetch("/participation-precincts.json");
    if (!pointer.ok) throw new Error(`Precinct pointer: HTTP ${pointer.status}`);
    const config = await pointer.json();
    state.currentPrecinctPath = config.base_url;
    for (const [sourceIndex, source] of [{ base_url: config.base_url }, ...(config.additional_sources || [])].entries()) {
      try {
        const base = new URL(source.base_url, location.href);
        const response = await fetch(new URL("index.json", base));
        if (!response.ok) throw new Error(`Precinct coverage: HTTP ${response.status}`);
        const data = await response.json();
        if (!sourceIndex) state.currentPrecincts = { ...data, states: {}, state_metadata: {} };
        for (const [code, file] of Object.entries(data.states || {})) {
          if (state.currentPrecincts.states[code]) throw new Error(`Duplicate 2026 precinct source: ${code}`);
          state.currentPrecincts.states[code] = new URL(file, base).href;
          state.currentPrecincts.state_metadata[code] = {
            boundary_label: data.boundary_date || "July 2026 reference boundaries",
            ...data.state_metadata?.[code],
            ...(data.complete_download_file
              ? { complete_download_url: new URL(data.complete_download_file, base).href } : {}),
          };
        }
        for (const [code, metadata] of Object.entries(data.municipalities || {})) {
          if (state.currentMunicipalities[code]) throw new Error(`Duplicate municipal source: ${code}`);
          state.currentMunicipalities[code] = { ...metadata, url: new URL(metadata.file, base).href,
            complete_download_url: new URL(metadata.complete_download_file, base).href };
        }
      } catch (error) {
        if (!sourceIndex) throw error;
        state.currentPrecinctError = `Additional precinct source unavailable: ${error.message}.`;
      }
    }
  } catch (error) {
    state.currentPrecinctError = `2026 precinct geography could not be loaded: ${error.message}.`;
  }
}
  async function loadPrecinctResults() {
    try {
      const response = await fetch("/precinct-results.json");
      if (!response.ok) throw new Error(`Result pointer: HTTP ${response.status}`);
      const pointer = await response.json();
      for (const snapshot of [pointer, ...(pointer.additional_snapshots || [])]) {
        const index = await fetch(snapshot.base_url + "index.json");
        if (!index.ok) throw new Error(`Precinct result coverage: HTTP ${index.status}`);
        const data = await index.json();
        state.precinctResults ||= { coverage: {} };
        for (const [year, states] of Object.entries(data.coverage)) {
          state.precinctResults.coverage[year] ||= {};
          for (const [code, coverage] of Object.entries(states)) {
            state.precinctResults.coverage[year][code] = {
              ...coverage, data_url: new URL(coverage.file, snapshot.base_url).href,
              complete_download_url: snapshot.complete_download_url,
              ...(snapshot.participation_count_sha256
                ? { participation_count_sha256: snapshot.participation_count_sha256 } : {}),
            };
          }
        }
      }
    } catch (error) {
      state.precinctResultsError = `Precinct candidate returns could not be loaded: ${error.message}.`;
    }
  }
  async function countyJSON(response) {
    const raw = new Uint8Array(await response.arrayBuffer());
    if (raw[0] !== 31 || raw[1] !== 139) return JSON.parse(new TextDecoder().decode(raw));
    if (!globalThis.DecompressionStream) throw new Error("Compressed county shapes are unsupported");
    return new Response(new Blob([raw]).stream().pipeThrough(new DecompressionStream("gzip"))).json();
  }
  async function loadCountyResults() {
    try {
      const pointer = await fetch("/county-results.json");
      if (!pointer.ok) throw new Error(`County result pointer: HTTP ${pointer.status}`);
      const { base_url, overview_url } = await pointer.json();
      const response = await fetch(base_url + "index.json");
      if (!response.ok) throw new Error(`County result coverage: HTTP ${response.status}`);
      const index = await response.json();
      const result = await fetch(base_url + index.margins_file);
      if (!result.ok) throw new Error(`County results: HTTP ${result.status}`);
      const rows = await result.json();
      if (index.geographic_level !== "county_equivalent" || index.boundary_reference_year !== index.year
        || rows.some(row => row.year !== index.year || row.level !== "county" || !index.coverage[row.state_code]))
        throw new Error("County result scope and boundary reference disagree");
      state.margins = [...state.margins.filter(row => !(row.year === index.year && row.level === "county"
        && index.coverage[row.state_code])), ...rows];
      state.countyResults = index;
      state.countyResultsPath = base_url;
      if (overview_url) {
        const response = await fetch(overview_url);
        if (!response.ok) throw new Error(`County overview: HTTP ${response.status}`);
        const data = await countyJSON(response);
        if (data.year !== index.year || data.features.length !== index.mapped_counties
          || new Set(data.features.map(feature => feature.properties.key)).size !== index.mapped_counties)
          throw new Error("National county overview scope disagrees with reviewed counts");
        state.countyOverview = data;
      }
    } catch (error) {
      state.countyResultsError = `County candidate returns unavailable; state results remain. ${error.message}.`;
    }
  }
  function drawNationalCountyResults(map, year) {
      if (!map.countyOverview) {
        const group = svgNode("g", { class: "county-overview" });
        const returns = new Map(state.margins.filter(row => row.year === year && row.level === "county")
          .map(row => [row.geography, row]));
        for (const feature of state.countyOverview.features) {
          const p = feature.properties, election = returns.get(p.key);
          const selected = map.stateItems.get(p.state_code);
          if (!selected || !election) continue;
          const item = projectInside(feature, selected.point);
          group.append(featurePath(item, null,
            `${p.name} · ${year}\n${marginLabel(election)} · ${fmt(election.contest_votes)} candidate votes\nCounty results, not turnout`,
            () => {
              state.selectedState = selected.feature.properties.NAME;
              $("state-select").value = state.selectedState;
              state.countySelection = { year, code: p.state_code, key: p.key };
              stateDetail(); countyResultDetail(p, election); syncURL(); fit(item.bounds);
            }, { class: "map-feature county-overview-feature", "data-geography": p.key, "data-level": "county",
              "data-color-level": election.margin_pp == null ? "none" : "county",
              "data-margin": election.margin_pp ?? "", "data-total-votes": election.contest_votes,
              "data-year": year, fill: election.margin_pp == null ? "#d6d3cb" : marginFill(election.margin_pp),
              tabindex: "-1" }));
        }
        map.svg.insertBefore(group, map.detail);
        map.countyOverview = group;
      }
      map.countyOverview.style.display = "";
      $("coverage-note").textContent = `${year} county / equivalent results: ${Object.keys(state.countyResults.coverage).length} states; `
        + `${fmt(state.countyResults.colored_counties)} counties colored by their own candidate votes. `
        + "State colors remain only where county returns are missing. Pennsylvania has partial county coverage. Candidate votes are not turnout.";
      $("geography-note").hidden = false;
      $("geography-note").textContent = "County colors are visible at national scale. Select a county to zoom; "
        + "full 2026 Census county shapes load as you zoom. The national overview uses display-simplified copies.";
  }
  function countyResultDetail(p, election, countsOnly = false) {
    const panel = $("substate-detail");
    if (countsOnly) {
      panel.replaceChildren(html("h4", "", p.name),
        html("p", "selection-rate", fmt(election.contest_votes)),
        html("p", "selection-basis", `${election.office} contest votes · not ballots cast or turnout`),
        html("p", "selection-note", "This is the sum of votes recorded in the tracked contest, not a count of all voters. No county participation rate is available. County population sizes differ."),
        sourceLink(election));
      panel.parentElement.prepend(panel);
      return;
    }
    panel.replaceChildren(html("h4", "", p.name), html("p", "selection-rate", marginLabel(election)),
      html("p", "selection-note", `${election.office} · ${fmt(election.contest_votes)} candidate votes. `
        + `${fmt(election.democratic_votes)} Democratic; ${fmt(election.republican_votes)} Republican; `
        + `${fmt(election.other_votes)} other. ${election.district_count} House district fragments reconciled.`),
      html("p", "selection-note", election.source_note || ("County / equivalent candidate results on 2026 Census reference boundaries, "
        + "not precinct results, unique voters or turnout. Explicit overseas returns and zero-only unresolved "
        + "Chicago reporting placeholders remain unallocated in the complete audit; no city votes are merged into Cook.")),
      sourceLink(election));
    panel.parentElement.prepend(panel);
  }
  async function drawCountyResults(map, selected, code, year, token, background = false, countsOnly = false) {
    const coverage = state.countyResults.coverage[code];
    const url = new URL(coverage.file, state.countyResultsPath).href;
    if (!state.subshapes.has(url)) {
      const promise = (async () => {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`County geometry: HTTP ${response.status}`);
        if (!globalThis.DecompressionStream) throw new Error("Compressed county shapes are unsupported; complete downloads remain available");
        return countyJSON(response);
      })().catch(error => { state.subshapes.delete(url); throw error; });
      state.subshapes.set(url, promise);
    }
    const data = await state.subshapes.get(url);
    if (token !== state.drillToken || state.map !== map) return;
    const returns = new Map(state.margins.filter(row => row.year === year
      && row.state_code === code && row.level === "county").map(row => [row.geography, row]));
    const maximum = Math.max(0, ...[...returns.values()].map(row => row.contest_votes ?? 0));
    for (const feature of data.features) {
      const p = feature.properties, election = returns.get(p.key);
      if (!election || (!countsOnly && election.margin_pp == null)) continue;
      const item = projectInside(feature, selected.point);
      const description = `${election.office} · ${countsOnly ? "" : marginLabel(election) + " · "}${fmt(election.contest_votes)} contest votes`;
      const path = featurePath(item, null, `${p.name} · ${year}\n${description}\nCounty result, not precinct results or turnout`, () => {
        state.countySelection = { year, code, key: p.key };
        countyResultDetail(p, election, countsOnly);
        for (const other of map.detail.querySelectorAll(".selected")) other.classList.remove("selected");
        path.classList.add("selected"); fit(item.bounds);
      }, { class: "map-feature substate-feature", "data-geography": p.key, "data-level": "county",
        "data-color-level": countsOnly ? "county-count" : "county",
        ...(countsOnly ? { "data-count-measure": "contest_votes" } : { "data-margin": election.margin_pp ?? "" }),
        "data-total-votes": election.contest_votes, "data-candidate-count-fallback": countsOnly ? "true" : "false",
        "data-year": year, fill: countsOnly ? countFill(election.contest_votes, maximum) : marginFill(election.margin_pp), tabindex: "-1" });
      map.detail.append(path);
    }
    map.countyLayer = true;
    if (background) return;
    if (countsOnly) {
      countLegend(maximum, "Contest votes · not turnout");
      setTable(data.features.filter(feature => returns.has(feature.properties.key)).map(feature => ({
        county: feature.properties.name, contest_votes: returns.get(feature.properties.key).contest_votes,
      })), [["county", "County"], ["contest_votes", "Contest votes (not ballots)"]]);
      return;
    }
    header(`${year} midterm election · county candidate returns`,
      `County election results in ${selected.feature.properties.NAME}`,
      "Red / blue uses each county's own House candidate votes, not participation.",
      "House district fragments are summed only within their actual county. 2026 Census county reference boundaries, not precincts.");
    $("coverage-note").textContent = `${year} county / equivalent results: ${Object.keys(state.countyResults.coverage).length} states; `
      + `${fmt(state.countyResults.colored_counties)} colored counties. Counties are the default detail. `
      + "Pennsylvania has only independently reviewed official county supplements; Maine remains withheld. D.C. is outside this House source. "
      + "Whole-state colors remain where county results are missing. Candidate votes are not turnout.";
    $("geography-note").textContent = `${selected.feature.properties.NAME} · ${fmt(coverage.counties)} 2026 Census counties / equivalents; `
      + `${fmt(coverage.colored_counties)} with county-level House candidate colors. `
      + (coverage.scope_note ? `${coverage.scope_note} ` : "")
      + "County fallback, not precinct coloring. Explicit overseas returns stay unallocated; zero-vote rows have no margin. "
      + "Select a county for its counts.";
    marginLegend("U.S. House aggregate");
    const selection = state.countySelection;
    if (selection?.year === year && selection.code === code) {
      const feature = data.features.find(feature => feature.properties.key === selection.key);
      if (feature && returns.has(selection.key)) countyResultDetail(feature.properties, returns.get(selection.key));
    }
  }
  async function drawCountyCountFallback(map, selected, code, year, token, reason) {
    const rows = state.margins.filter(row => row.year === year && row.state_code === code && row.level === "county");
    map.candidateCountFallback = true;
    map.countyLayer = true;
    map.stateTable ||= { rows: state.table, columns: state.columns };
    setTable(rows, [["geography", "County ID"], ["contest_votes", "Contest votes (not ballots)"]]);
    header(`${year} · county turnout unavailable`,
      `County contest counts in ${selected.feature.properties.NAME}`,
      `${reason} Color shows recorded contest vote counts, not a participation rate.`,
      "No party colors. Contest votes are not ballots cast, unique voters or precinct results. County population sizes differ.");
    $("coverage-note").textContent = `${fmt(rows.length)} county contest-count records; no county turnout rate. The statewide turnout estimate remains separate in the sidebar.`;
    await drawCountyResults(map, selected, code, year, token, false, true);
    if (token !== state.drillToken || state.map !== map) return;
    $("geography-note").hidden = false;
    $("geography-note").textContent = `${selected.feature.properties.NAME} · ${fmt(rows.length)} county contest counts, not turnout. `
      + (state.countyResults.coverage[code].scope_note || "")
      + " Select a county to inspect its total. No state turnout estimate is allocated to counties.";
  }
  async function precinctResultData(code, year) {
    const coverage = state.precinctResults?.coverage[year]?.[code], key = `${year}|${code}`;
    if (!coverage) throw new Error(`No verified ${year} precinct-result layer for ${code}`);
    if (!state.precinctResultShapes.has(key)) {
      const promise = (async () => {
        const response = await fetch(coverage.data_url);
        if (!response.ok) throw new Error(`Precinct results: HTTP ${response.status}`);
        if (!globalThis.DecompressionStream) throw new Error("Compressed precinct data are unsupported by this browser; complete downloads remain available");
        let body = response.body;
        if (coverage.participation_count_sha256) {
          const raw = await response.arrayBuffer();
          const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", raw))]
            .map(value => value.toString(16).padStart(2, "0")).join("");
          if (hash !== coverage.participation_count_sha256)
            throw new Error("Precinct participation source checksum disagrees");
          body = new Response(raw).body;
        }
        return new Response(body.pipeThrough(new DecompressionStream("gzip"))).json();
      })().catch(error => { state.precinctResultShapes.delete(key); throw error; });
      state.precinctResultShapes.set(key, promise);
    }
    return state.precinctResultShapes.get(key);
  }
  function matchedPrecinctParticipationCoverage(code, year = Number($("year").value)) {
    const coverage = year === 2026 && ["ID", "ND", "MN", "DC", "VA"].includes(code)
      ? state.precinctResults?.coverage[year]?.[code] || null : null;
    return code === "VA" && !coverage?.participation_count_sha256 ? null : coverage;
  }
  function matchedPrecinctParticipationMode() {
    return ufMode() || ["available", "official"].includes($("mode").value);
  }
  function matchedParticipationDescription(row, countsOnly = row.measure === "reported_ballots") {
    if (countsOnly)
      return `${fmt(row.ballots)} reported ballots · no precinct electorate denominator or participation rate`;
    return `${row.reported_pct == null ? "Rate withheld" : pct(row.reported_pct)} · `
      + `${fmt(row.ballots)} ${row.measure ? "reported ballots" : "reported voters"} / `
      + `${fmt(row.registered ?? row.denominator)} ${row.denominator_basis || "source-registered voters"}`;
  }
  function matchedPrecinctParticipationDetail(p) {
    const row = p.participation, countsOnly = row.measure === "reported_ballots" || p.state_code === "VA";
    const panel = $("substate-detail");
    panel.replaceChildren(html("h4", "", `${p.county} · ${p.precinct}`),
      html("p", `selection-rate${!countsOnly && row.reported_pct == null ? " selection-unavailable" : ""}`,
        countsOnly ? fmt(row.ballots) : pct(row.reported_pct)),
      html("p", "selection-note", matchedParticipationDescription(row, countsOnly)),
      html("p", "selection-note", p.state_code === "VA"
        ? "Literal native ballotsCast from the locality voterTurnout object. The distinct voterTurnout count is not substituted. Mode allocations and registration denominators remain unqualified; no final or all-mode turnout is inferred."
        : row.basis || row.quality),
      html("p", "selection-note", row.quality_flags?.length
        ? `Rate review: ${row.quality_flags.map(flag => flag.replaceAll("_", " ")).join("; ")}.`
        : p.state_code === "DC" ? "Provisional election-night fraction; not final, population or demographic turnout."
        : countsOnly ? "Color shows reported ballot counts; no precinct denominator or participation rate is available."
          : "Source inputs passed the published rate checks."),
      html("p", "selection-note", "Only this approved reporting-unit join is shown. Unmatched and conflicting units remain excluded; pooled absentee/early units are never allocated. Candidate votes are not ballots cast."),
      sourceLink(row.source_url ? row : p));
    if (p.boundary_provenance) panel.append(html("p", "selection-note", p.boundary_provenance));
    if (p.state_code === "DC") panel.append(html("p", "selection-note",
      `${p.source_reporting_status} · source updated ${p.source_updated_at}.`));
    if (p.state_code === "VA") panel.append(html("p", "selection-note",
      `Native registrations: ${fmt(row.registered)} · not a qualified rate denominator. See complete locality originals for their separate source clocks.`));
    panel.parentElement.prepend(panel);
  }
  async function drawMatchedPrecinctParticipation(map, selected, code, year, token) {
    const coverage = matchedPrecinctParticipationCoverage(code, year);
    const data = await precinctResultData(code, year);
    if (token !== state.drillToken || state.map !== map) return;
    const keys = new Set(), countsOnly = ["ND", "VA"].includes(code);
    for (const { properties: p, geometry } of data.features) {
      const row = p.participation;
      const scope = code === "DC" ? qualifiedDcPrecinctParticipation(p, year)
        : code === "VA" ? qualifiedVaPrecinctParticipation(p, year)
        : countsOnly
        ? p.reporting_unit_kind === "precinct" && row?.measure === "reported_ballots"
          && row.denominator === null && row.reported_pct === null
          && Number.isSafeInteger(row.ballots) && row.ballots >= 0
        : code === "MN"
        ? p.reporting_unit_kind === "precinct" && row && row.measure == null
          && ["county", "precinct", "county_code", "precinct_code"].every(key => row[key] === p[key])
          && typeof row.reported === "boolean" && Number.isSafeInteger(row.ballots) && row.ballots >= 0
          && Number.isSafeInteger(row.denominator)
          && row.denominator === row.registered_at_open + row.election_day_registrations
        : p.reporting_unit_kind === "source_reporting_unit"
          && row?.reporting_unit_kind === "source_reporting_unit"
          && row.measure === "reported_ballots_and_registration";
      if (!geometry || !row || p.match_status !== "matched" || p.state_code !== code || p.year !== year
        || (code !== "VA" && (row?.key !== p.key || row.state_code !== code || row.year !== year))
        || !scope || keys.has(p.key))
        throw new Error(`Unqualified ${code} precinct participation payload`);
      keys.add(p.key);
    }
    if (data.features.length !== coverage.features)
      throw new Error(`Verified ${code} participation payload count disagrees with the approved geometry inventory`);
    const observed = data.features.filter(feature => feature.properties.participation.reported_pct != null).length;
    const maximum = Math.max(0, ...data.features.map(feature => feature.properties.participation.ballots));
    for (const feature of data.features) {
      const p = feature.properties, row = p.participation, item = projectInside(feature, selected.point);
      const path = featurePath(item, row.reported_pct,
        `${p.county} · ${p.precinct} · ${year}\n${matchedParticipationDescription(row, countsOnly)}`, () => {
          state.precinctResultSelection = p.key;
          matchedPrecinctParticipationDetail(p);
          for (const other of map.detail.querySelectorAll(".selected")) other.classList.remove("selected");
          path.classList.add("selected"); fit(item.bounds);
        }, { class: "map-feature substate-feature", "data-geography": p.key, "data-level": "precinct",
          "data-color-level": row.reported_pct == null ? "none" : "precinct",
          "data-rate": row.reported_pct ?? "", "data-count": row.ballots,
          "data-registered": row.registered ?? row.denominator ?? "", "data-year": year, tabindex: "-1",
          ...(countsOnly ? { fill: countFill(row.ballots, maximum),
            "data-count-measure": code === "VA" ? "native_ballotsCast" : "reported_ballots" } : {}) });
      path.classList.toggle("selected", p.key === state.precinctResultSelection);
      map.detail.append(path);
    }
    map.precinctLayer = true;
    map.stateTable ||= { rows: state.table, columns: state.columns };
    setTable(data.features.map(({ properties: p }) => ({
      county: p.county, precinct: p.precinct, ballots: p.participation.ballots,
      registered: p.participation.registered ?? p.participation.denominator ?? null,
      reported_pct: p.participation.reported_pct, notes: p.participation.basis || p.participation.quality,
    })), [["county", "County"], ["precinct", "Reporting unit"],
      ["ballots", code === "MN" ? "Reported voters" : "Ballots reported"],
      ["registered", code === "VA" ? "Native registrations (not a rate denominator)" : "Source registrations"],
      ["reported_pct", code === "DC" ? "Provisional source fraction (%)" : "Participation rate"], ["notes", "Notes"]]);
    header("2026 midterms · unofficial precinct observations · partial coverage",
      `Precinct participation${countsOnly ? " counts" : ""} in ${selected.feature.properties.NAME}`,
      code === "VA" ? "Literal native ballotsCast counts on reviewed current-reference joins, not all Virginia. Participation rates remain withheld; distinct voterTurnout values and missing ballot modes are not substituted."
        : countsOnly ? "Native reported-ballot counts. No precinct electorate denominators or rates are available."
        : code === "DC" ? "Provisional election-night ballots / source-registered voters. Registration reference date is not independently verified; this is not final turnout."
        : code === "MN" ? "Native reported voters / registered at 7 a.m. plus election-day registrations. County detail remains available separately."
        : "Reported ballots / source total registered voters. Every colored shape uses its own approved reporting-unit counts.",
      "Only previously reviewed geometry joins are shown. Gray is a withheld or unavailable rate, not zero participation. Conflicting and unmatched units remain excluded; pooled absentee/early units are not allocated.");
    if (["DC", "VA"].includes(code) && coverage.complete_download_url) {
      const complete = html("a", "source-link", `Complete ${code === "DC" ? "D.C." : "Virginia"} precinct counts and original sources (ZIP)`);
      complete.href = coverage.complete_download_url;
      $("caption").append(" ", complete);
    }
    $("coverage-note").textContent = `${fmt(data.features.length)} approved reporting-unit joins; `
      + `${fmt(observed)} have ${code === "DC" ? "provisional source fractions" : "reviewed rates"} and ${fmt(data.features.length - observed)} retain withheld or unavailable rates. `
      + (code === "DC"
        ? "All source precinct identities have a reference join; ambiguous overlapping strips remain withheld. "
        : "The complete source table has additional unmapped units. ")
      + "Candidate votes are not used as ballots.";
    $("geography-note").textContent = `${selected.feature.properties.NAME} · ${fmt(data.features.length)} `
      + (code === "DC"
        ? "official-app reference joins for the 2026 election. The app selects its 2019-named reference, not newly surveyed or certified 2026 boundaries. Ambiguous overlapping strips remain withheld; counts describe whole precincts, not clipped-area allocations. "
        : code === "VA"
        ? "reviewed 2026 current-reference shapes, not certified election-day boundaries. Unmatched, invalid, overlapping, virtual, split-district and incomplete-mode units remain excluded. "
        : "verified 2026 reporting-unit shapes. ")
      + (countsOnly ? "All shapes carry native ballot counts but no precinct electorate denominator or rate. "
        : `${fmt(observed)} ${code === "DC" ? "provisional source fractions" : "source-defined participation rates"}. `)
      + "Select a shape for its exact counts and review notes. No county/state rate is painted onto a precinct.";
    if (countsOnly) countLegend(maximum, "Reported ballots · no rate");
    else ramp();
    const chosen = data.features.find(feature => feature.properties.key === state.precinctResultSelection);
    if (chosen) matchedPrecinctParticipationDetail(chosen.properties);
  }
  function precinctResultDetail(p) {
    const panel = $("substate-detail");
    panel.replaceChildren(html("h4", "", `${p.county} · ${p.precinct}`),
      html("p", "selection-rate", marginLabel(p)),
      html("p", "selection-note", `${p.office} · ${p.year}. `
        + `${fmt(p.democratic_votes)} Democratic; ${fmt(p.republican_votes)} Republican; `
        + `${fmt(p.other_votes)} other; ${fmt(p.contest_votes)} total contest votes.`),
      html("p", "selection-note", p.ballot_scope),
      html("p", "selection-note", "Candidate-vote margin, not turnout or demographic participation. Matching precinct identifiers does not establish unchanged boundaries across elections."));
    if (p.official_boundary === false) panel.append(html("p", "selection-note", "Approximate boundary reconstructed by The New York Times, not an official precinct shape."));
    if (p.boundary_provenance) panel.append(html("p", "selection-note", p.boundary_provenance));
    if (p.participation) {
      const participation = p.participation;
      panel.append(html("p", "selection-note", participation.measure === "reported_ballots"
        ? `Separate participation statistics: ${fmt(participation.ballots)} ballots reported. `
        + "No precinct electorate denominator; no participation rate. " + participation.quality
        : participation.measure === "reported_ballots_and_registration"
        ? `Separate participation statistics: ${fmt(participation.ballots)} reported ballots / `
        + `${fmt(participation.registered)} source-registered voters. `
        + (participation.reported_pct == null ? "Rate withheld. " : `${pct(participation.reported_pct)}. `)
        + `${participation.basis} ${participation.quality.replaceAll("_", " ")}.`
        : !participation.reported
        ? "Separate participation statistics: not yet reported for this precinct. No participation rate; original source values remain in the downloads."
        : `Separate participation statistics: ${fmt(participation.ballots)} reported voters / `
        + `${fmt(participation.denominator)} registered at opening plus election-day registrations; `
        + `${pct(participation.reported_pct)}. ${participation.quality}. Missing, inconsistent or small denominators have no rate.`));
    }
    panel.append(sourceLink(p));
    panel.parentElement.prepend(panel);
  }
  async function drawPrecinctResults(map, selected, code, year, token) {
    const coverage = state.precinctResults.coverage[year][code];
    const data = await precinctResultData(code, year);
    if (token !== state.drillToken || state.map !== map) return;
    let countyBackground = state.countyResults?.year === year && state.countyResults.coverage[code]
      && map.full[0] / state.viewport[2] >= 2.3;
    if (countyBackground) {
      try {
        await drawCountyResults(map, selected, code, year, token, true);
      } catch (error) {
        countyBackground = false;
        state.countyResultsError = `County backdrop unavailable; verified precinct results remain. ${error.message}.`;
      }
      if (token !== state.drillToken || state.map !== map) return;
    }
    for (const feature of data.features) {
      const p = feature.properties;
      if (!feature.geometry || p.match_status !== "matched" || p.margin_pp == null) continue;
      const item = projectInside(feature, selected.point);
      const path = featurePath(item, null,
        `${p.county} · ${p.precinct} · ${year}\n${p.office} · ${marginLabel(p)} · ${fmt(p.contest_votes)} contest votes\n${p.ballot_scope}`, () => {
          state.precinctResultSelection = p.key;
          precinctResultDetail(p);
          for (const other of map.detail.querySelectorAll(".selected")) other.classList.remove("selected");
          path.classList.add("selected"); fit(item.bounds);
        }, { class: "map-feature substate-feature", "data-geography": p.key, "data-level": "precinct",
          "data-color-level": "precinct", "data-margin": p.margin_pp, "data-total-votes": p.contest_votes,
          "data-match": p.match_status, "data-year": year, fill: marginFill(p.margin_pp), tabindex: "-1" });
      path.classList.toggle("selected", p.key === state.precinctResultSelection);
      map.detail.append(path);
    }
    map.precinctLayer = true;
    map.stateTable ||= { rows: state.table, columns: state.columns };
    setTable(data.features.map(({ properties: p }) => ({
      county: p.county, precinct: p.precinct, office: p.office,
      democratic_votes: p.democratic_votes, republican_votes: p.republican_votes,
      other_votes: p.other_votes, contest_votes: p.contest_votes,
      margin_pp: p.margin_pp, match_status: p.match_status,
    })), [["county", "County"], ["precinct", "Reporting unit"], ["office", "Office"],
      ["democratic_votes", "Democratic votes"], ["republican_votes", "Republican votes"],
      ["other_votes", "Other votes"], ["contest_votes", "Candidate votes"],
      ["margin_pp", "D−R margin"], ["match_status", "Map match"]]);
    header(`${year} ${typeFor(year)} election · precinct candidate returns · partial coverage`,
      `Precinct election results in ${selected.feature.properties.NAME}`,
      "Red / blue uses each mapped reporting area's own candidate votes, not participation.",
      coverage.notes);
    const codes = Object.keys(state.precinctResults.coverage[year]);
    $("coverage-note").textContent = `${year} precinct / municipal result layers: `
      + `${codes.filter(value => value !== "DC").length} states${codes.includes("DC") ? " and D.C." : ""}. `
      + `${fmt(coverage.colored)} colored reporting areas in this state. Partial coverage is not every precinct or all ballot modes. `
      + (countyBackground ? "County result colors remain beneath unmatched precinct areas; whole-state colors remain where county results are missing. "
        : "Whole-state red/blue result colors remain beneath unmatched areas. ")
      + ([2020, 2024].includes(year) ? `${year} source: The New York Times; original state caveats and license are in Methods & data.` : "");
    $("geography-note").textContent = `${selected.feature.properties.NAME} · ${fmt(coverage.colored)} verified candidate-result shapes `
      + `on ${coverage.boundary_date} boundaries. ${coverage.notes}`;
    marginLegend(coverage.office);
    const chosen = data.features.find(feature => feature.properties.key === state.precinctResultSelection);
    if (chosen) precinctResultDetail(chosen.properties);
  }
function currentPrecinctDescription(p) {
  const counts = `${fmt(p.ballots)} ballots / ${fmt(p.denominator)} `
    + (p.state_code === "MI" ? "native registrations (components undefined)" : "source-defined electorate");
  return p.match_status === "county_precinct_set_mismatch"
    ? `No rate mapped: county boundary and reporting precinct sets differ. ${counts}.`
    : p.reported_pct == null ? `${counts}. Rate withheld: ${p.rate_withheld_reason
      || "missing/inconsistent inputs or fewer than 25 source-electorate voters"}.`
      : `${pct(p.reported_pct)} · ${counts}`;
}
function currentPrecinctDetail(p, metadata = {}) {
  const panel = $("substate-detail");
  panel.replaceChildren(html("h4", "", `${p.county} · ${p.unit}`),
    html("p", "selection-rate", p.reported_pct == null ? fmt(p.ballots) : pct(p.reported_pct)),
    html("p", "selection-note", currentPrecinctDescription(p)),
    html("p", "selection-note", `2026 unofficial counts, not final turnout. ${p.boundary_label
      || metadata.boundary_label || "Reviewed reference boundaries"}; no cross-election boundary match is implied.`));
  if (p.source_reporting_label) panel.append(html("p", "selection-note", p.source_reporting_label));
  if (p.source_update_label) panel.append(html("p", "selection-note", p.source_update_label));
  if (p.source_url) panel.append(sourceLink(p));
  panel.parentElement.prepend(panel);
}
async function drawCurrentPrecinctGeography(map, selected, code, token) {
  const file = state.currentPrecincts?.states[code];
  const metadata = state.currentPrecincts?.state_metadata?.[code] || {};
  if (!file || !(ufMode() || ["available", "official"].includes($("mode").value))) {
    if (map.full[0] / state.viewport[2] >= 2.3 && state.countyResults?.year === 2026
      && state.countyResults.coverage[code] && matchedPrecinctParticipationMode())
      return drawCountyCountFallback(map, selected, code, 2026, token,
        "Precinct participation geometry is unavailable.");
    $("geography-note").textContent = state.currentPrecinctError
      || `No matched 2026 precinct participation map for ${state.selectedState} and this ballot mode. `
        + "Other years' boundaries and county rates are not substituted. New Mexico has partial verified coverage. State-level rates, where available, remain a separate layer.";
    if (map.stateRateMap) ramp();
    else legend([["No matched precinct participation", "#d6d3cb"]]);
    return;
  }
  if (!state.currentPrecinctShapes.has(code)) {
    const response = await fetch(new URL(file, state.currentPrecinctPath));
    if (!response.ok) throw new Error(`2026 precinct boundaries: HTTP ${response.status}`);
    if (!globalThis.DecompressionStream) throw new Error("This browser cannot read compressed precinct geography; complete downloads remain available");
    let body = response.body;
    if (metadata.sha256) {
      const raw = await response.arrayBuffer();
      const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", raw))]
        .map(value => value.toString(16).padStart(2, "0")).join("");
      if (hash !== metadata.sha256 || raw.byteLength !== metadata.bytes)
        throw new Error("2026 precinct source checksum disagrees");
      body = new Response(raw).body;
    }
    const data = await new Response(body.pipeThrough(new DecompressionStream("gzip"))).json();
    if (metadata.source_id === "indiana-monroe-native-20261109-01"
      && (code !== "IN" || data.features.length !== metadata.expected_features
        || new Set(data.features.map(feature => feature.properties.key)).size !== data.features.length
        || data.features.some(feature => !feature.geometry || !qualifiedIndianaMonroePrecinct(feature.properties))))
      throw new Error("Unqualified Indiana Monroe precinct count or reference");
    state.currentPrecinctShapes.set(code, data);
  }
  if (token !== state.drillToken || state.map !== map) return;
  const features = state.currentPrecinctShapes.get(code).features;
  const name = selected.feature.properties.NAME;
  const countsOnly = code === "MI" || metadata.counts_only === true;
  const maximum = Math.max(0, ...features.map(feature => feature.properties.ballots ?? 0));
  for (const feature of features) {
    const p = feature.properties, item = projectInside(feature, selected.point);
    const description = currentPrecinctDescription(p);
    const path = featurePath(item, p.reported_pct,
      `${p.county} · ${p.unit} · 2026\n${description}\nUnofficial counts · ${p.boundary_label || metadata.boundary_label}`, () => {
        state.currentPrecinctSelection = p.key;
        if (p.unit_key) {
          state.currentCounty = code + "|" + p.county_id; state.currentUnit = p.unit_key;
        }
        if (state.selectedState !== name) {
          state.selectedState = name; $("state-select").value = name; stateDetail(); syncURL();
        }
        currentPrecinctDetail(p, metadata);
        if (p.unit_key && $("current-county-select")) {
          $("current-county-select").value = p.county_id;
          $("current-county-select").dispatchEvent(new Event("change"));
          if ($("current-unit-select")) {
            $("current-unit-select").value = p.unit_key;
            $("current-unit-select").dispatchEvent(new Event("change"));
          }
        }
        for (const other of map.detail.querySelectorAll(".selected")) other.classList.remove("selected");
        path.classList.add("selected"); fit(item.bounds);
      }, { class: "map-feature substate-feature", "data-geography": p.key, "data-level": "precinct",
        "data-match": p.match_status, "data-rate": p.reported_pct ?? "", "data-count": p.ballots,
        "data-registered": p.denominator ?? "", tabindex: "-1",
        ...(countsOnly ? { fill: countFill(p.ballots, maximum), "data-count-measure": "reported_ballots" } : {}) });
    path.classList.toggle("selected", p.key === state.currentPrecinctSelection);
    map.detail.append(path);
  }
  map.precinctLayer = true;
  const index = state.currentPrecincts, observed = features.filter(feature => feature.properties.reported_pct != null).length;
  map.stateTable ||= { rows: state.table, columns: state.columns };
  setTable(features.map(feature => feature.properties), [["county", "County"], ["unit", "Reporting unit"],
    ["ballots", "Ballots reported"], ["denominator", "Source electorate"],
    ["reported_pct", "Participation rate"], ["rate_withheld_reason", "Rate review"]]);
  header("2026 midterms · unofficial precinct observations · partial coverage",
    map.full[0] / state.viewport[2] < 2.3 ? "Precinct participation · available coverage" : `Precinct participation in ${name}`,
    countsOnly ? "Color shows reported ballot counts, not turnout rates. All precinct rates remain withheld."
      : "Reported ballots / source-defined electorate where qualified. Gray shapes can still carry direct counts.",
    `${metadata.boundary_label || "Reviewed 2026 reference boundaries"}. Rates remain withheld where inputs or electorate definitions are unqualified. State-level colors underneath are separate, never assigned to precincts.`);
  if (metadata.complete_download_url) {
    const complete = html("a", "source-link", "Complete originals, matched/withheld rows and exact geometry (ZIP)");
    complete.href = metadata.complete_download_url; $("caption").append(" ", complete);
  }
  $("coverage-note").textContent = code === "NM"
    ? `${fmt(index.colored_precincts)} colored precincts across ${index.matched_counties} New Mexico counties. `
      + `All precinct shapes in ${index.unmatched_counties.join(", ")} remain neutral because reporting and boundary sets differ. `
      + "This is partial coverage, not a nationwide precinct map."
    : `${fmt(features.length)} approved count-bearing shapes; ${fmt(observed)} rates. ${metadata.notes || "Partial coverage only."}`;
  if (observed) ramp();
  else if (countsOnly) countLegend(maximum, "Reported ballots · no rate");
  else legend([["Direct counts available · rate withheld", fill(null)]]);
  $("geography-note").textContent = `${name} · ${fmt(features.length)} ${metadata.boundary_label || "reviewed 2026 precinct shapes"} · `
    + `${fmt(observed)} with precinct participation rates. No county or state values are painted onto precincts. `
    + "Zoom and select a precinct for its reported counts; complete sources, joins and withheld records are downloadable.";
  const selectedPrecinct = features.find(feature => feature.properties.key === state.currentPrecinctSelection);
  if (selectedPrecinct) currentPrecinctDetail(selectedPrecinct.properties, metadata);
}
async function contextGet(path) {
    const response = await fetch(state.contextPath + path);
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }
  async function loadContext() {
    try {
      const response = await fetch("/participation-context/latest.json");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const pointer = await response.json();
      state.contextPath = `/participation-context/${pointer.snapshot_id}/`;
      [state.context, state.margins] = await Promise.all([contextGet("index.json"), contextGet("margins.json")]);
      const link = html("a", "", "Complete map context + original sources (ZIP)");
      link.href = participationDownload(state.contextPath + "complete-context.zip"); link.download = "";
      if (!$("downloads").querySelector(`a[href="${link.getAttribute("href")}"]`))
        $("downloads").querySelector(".download-links").append(link);
    } catch (error) {
      state.contextError = `Election-map context is unavailable: ${error.message}.`;
      state.contextPath = "";
    }
    try {
      const pointer = await fetch("/participation-results/latest.json");
      if (!pointer.ok) throw new Error(`HTTP ${pointer.status}`);
      const path = `/participation-results/${(await pointer.json()).snapshot_id}/`;
      const responses = await Promise.all(["index.json", "margins.json"].map(file => fetch(path + file)));
      if (responses.some(response => !response.ok)) throw new Error("Result snapshot could not be loaded");
      const [index, rows] = await Promise.all(responses.map(response => response.json()));
      state.results = index;
      state.margins = [...state.margins.filter(row => row.year !== index.year), ...rows];
    } catch (error) {
      state.resultsError = `Latest result refresh unavailable; previously saved result context is retained. ${error.message}.`;
    }
    await loadCountyResults();
}
function options(element, values, preferred = element.value) {
  element.replaceChildren(...values.map(([value, label]) => {
    const option = document.createElement("option");
    option.value = value; option.textContent = label;
    return option;
  }));
  element.value = values.some(([value]) => value === preferred) ? preferred : values[0]?.[0] ?? "";
}
const viewControlIds = {
  states: ["year", "basis", "mode", "map-color", "map-level"],
  national: ["year", "basis", "dimension", "group", "mode", "demographic-state"],
  precincts: ["precinct-state-select", "year", "precinct-layer", "dimension", "group", "minimum"],
};
function viewSelection(view = state.view) {
  return Object.fromEntries((viewControlIds[view] ?? []).map(id => [id, $(id).value]));
}
function rememberView(view = state.view) {
  if (!viewControlIds[view]) return;
  state.viewSelections[view] = { ...state.viewSelections[view], ...viewSelection(view) };
  if (view === "states") state.viewSelections[view].selectedState = state.selectedState;
}
function stateName(code) {
  return state.geometry?.features.find(feature => feature.properties.STUSAB === code)?.properties.NAME || code;
}
function precinctResultCoverage(code, year) {
  return state.precinctResults?.coverage?.[year]?.[code] || null;
}
function ncPrecinctYears() {
  return unique(state.ncSummary.filter(row => row.status === "aggregated").map(row => row.year));
}
function precinctParticipationCoverage(code, year) {
  if (code === "NC" && year !== 2026 && ncPrecinctYears().includes(year)) return "nc_history";
  if (year !== 2026) return "";
  if (matchedPrecinctParticipationCoverage(code, year)) return "matched_results";
  if (state.currentPrecincts?.states?.[code]) return "current_participation";
  if (state.reportingUnitSources[code]) return "reporting_units";
  return "";
}
function precinctCoverageCodes() {
  const codes = new Set(state.geometry.features.filter(feature =>
    state.states.some(row => row.state === feature.properties.NAME)).map(feature => feature.properties.STUSAB));
  for (const states of Object.values(state.precinctResults?.coverage || {}))
    for (const code of Object.keys(states)) codes.add(code);
  return [...codes].filter(code => stateName(code) !== code || code === "DC")
    .sort((a, b) => stateName(a).localeCompare(stateName(b)));
}
function precinctYears(code) {
  const years = new Set(code === "NC" ? ncPrecinctYears() : []);
  for (const [year, states] of Object.entries(state.precinctResults?.coverage || {}))
    if (states[code]) years.add(Number(year));
  if (state.currentPrecincts?.states?.[code] || matchedPrecinctParticipationCoverage(code, 2026))
    years.add(2026);
  return [...years].sort((a, b) => b - a);
}
function precinctLayerOptions(code, year, requestedLayer) {
  const values = [["participation", precinctParticipationCoverage(code, year)
    ? code === "NC" && year !== 2026
      ? "Registered-voter participation · North Carolina"
      : precinctParticipationCoverage(code, year) === "reporting_units"
        ? "Reported participation counts · map held" : "Participation counts / rates · qualified sources"
    : "Participation · no loaded source"]];
  if (precinctResultCoverage(code, year) || requestedLayer === "results")
    values.push(["results", precinctResultCoverage(code, year)
      ? "Candidate results · red / blue" : "Candidate results · no loaded source"]);
  return values;
}
function ncParticipationView() {
  return state.view === "precincts" && stateCode() === "NC"
    && $("precinct-layer").value === "participation" && Number($("year").value) !== 2026;
}
function currentAudit() {
  if (!state.current) return;
  const snapshot = state.current, el = name => $(`national-current-${name}`);
  options(el("state"), snapshot.coverage.map(row => [row.state_code, row.state]), el("state").value || "GA");
  el("state").disabled = false;
  const render = () => {
    const code = el("state").value, mode = el("mode").value;
    const name = snapshot.coverage.find(row => row.state_code === code).state;
    const total = snapshot.early_voting.find(row => row.state_code === code && row.mode === mode && row.geography_level === "state");
    const groups = snapshot.demographics.filter(row => row.state_code === code && row.mode === mode && row.demographic_source_total > 0);
    options(el("dimension"), unique(groups.map(row => row.dimension)).map(value => [value, value.replaceAll("_", " ")]), el("dimension").value);
    const rows = groups.filter(row => row.dimension === el("dimension").value);
    el("selection").textContent = `${name} · ${modeLabels[mode]}`;
    el("total").textContent = `Reported ${modeLabels[mode]}: ${total ? fmt(total.ballots) : "Not reported"}. Source data date: ${total?.source_date ?? "Not reported"}.`;
    el("mode-note").textContent = total ? sourceNote(total) : "No assessed observation. Missing is not zero.";
    const maximum = Math.max(1, ...rows.map(row => row.ballots));
    el("chart").replaceChildren(...rows.map(row => {
      const item = html("li"), bar = html("i"); bar.style.width = `${100 * row.ballots / maximum}%`; bar.setAttribute("aria-hidden", "true");
      item.append(html("span", "", row.group), html("strong", "", fmt(row.ballots)), bar); return item;
    }));
    el("group-note").textContent = rows.length ? `${sourceNote(rows[0])} Counts, not group turnout rates.`
      : "No nonzero, dated demographic breakdown for this selection. Missing is not zero.";
    const official = snapshot.reporting.find(row => row.state_code === code);
    el("official").textContent = official ? `Official administrative ballots reported: ${fmt(official.ballots)}. `
      + `Source update: ${official.source_update_label}. ${sourceNote(official)} Denominator basis: ${official.denominator_basis.replaceAll("_", " ")}.`
      : "Official full-election ballots have not been ingested for this state. Missing is not zero turnout.";
  };
  for (const id of ["state", "mode", "dimension"]) el(id).addEventListener("change", render);
  render();
}
async function loadMethods() {
  try {
    const pointer = await (await fetch("/participation-methods/latest.json")).json();
    const path = `/participation-methods/${pointer.snapshot_id}/`;
    const read = async file => {
      const response = await fetch(path + file);
      if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
      return response.json();
    };
    const [index, states, national] = await Promise.all([read("index.json"), read("states.json"), read("national.json")]);
    Object.assign(state, { methods: index, methodStates: states, methodNational: national, methodsPath: path });
    const link = html("a", "", "Complete historical voting methods + original sources (ZIP)");
    link.href = participationDownload(path + "complete-methods.zip"); link.download = "";
    if (!$("downloads").querySelector(`a[href="${link.getAttribute("href")}"]`))
      $("downloads").querySelector(".download-links").append(link);
  } catch (error) {
    state.methodsError = `Historical voting methods could not be loaded: ${error.message}.`;
  }
}
function methodHistory(rows, mode, national) {
  const values = rows.filter(row => row.share_pct != null).sort((a, b) => a.year - b.year);
  const host = $("method-history");
  if (!values.length) {
    host.replaceChildren(html("p", "empty", "No matched historical percentages for this method."));
    return;
  }
  const maximum = Math.max(...values.map(row => row.share_pct));
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(1, maximum * 1.1)));
  const ceiling = Math.min(100, [1, 2, 5, 10].map(value => value * magnitude)
    .find(value => value >= Math.max(1, maximum * 1.1)));
  const chart = svgNode("svg", { viewBox: "0 0 520 170", role: "img", "data-scale-max": ceiling,
    "aria-label": `${methodLabels[mode]} history. Shares among ${national ? "reported voters" : "matched reporting units"}, not eligible-population turnout.` });
  const first = values[0].year, last = values.at(-1).year;
  const x = year => first === last ? 275 : 45 + (year - first) / (last - first) * 455;
  const y = share => 130 - share / ceiling * 110;
  for (const value of [0, ceiling / 2, ceiling])
    chart.append(svgNode("line", { x1: 45, x2: 500, y1: y(value), y2: y(value), class: "chart-grid" }),
      svgNode("text", { x: 37, y: y(value) + 4, "text-anchor": "end", class: "axis-label" }, value + "%"));
  let segment = [];
  const flush = () => {
    if (segment.length > 1) chart.append(svgNode("path", { class: "chart-line", stroke: colors[0],
      d: segment.map((r, i) => `${i ? "L" : "M"}${x(r.year)},${y(r.share_pct)}`).join(" ") }));
    segment = [];
  };
  for (const row of values) {
    const previous = segment.at(-1);
    if (previous && (row.year - previous.year !== 2 || !national
      || (previous.year < 2004 && row.year >= 2004) || (previous.year < 2018 && row.year >= 2018))) flush();
    segment.push(row);
  }
  flush();
  const ticks = unique([...values.filter((_, i) => i % Math.ceil(values.length / 5) === 0)
    .map(row => row.year), last]);
  for (const year of ticks) chart.append(svgNode("text", { x: x(year), y: 157, class: "axis-label year-tick",
    "text-anchor": "middle" }, String(year)));
  for (const row of values) {
    const point = svgNode("circle", { cx: x(row.year), cy: y(row.share_pct), r: row.year === Number($("year").value) ? 5 : 3.5,
      fill: colors[0], class: "method-point", tabindex: "0", role: "button", "data-year": row.year,
      "data-share": row.share_pct, "aria-label": `${row.year}: ${pct(row.share_pct)} · ${methodLabels[mode]}` });
    bindTooltip(point, `${row.year} · ${methodLabels[mode]}\n${pct(row.share_pct)}`
      + (national ? "" : ` · ${row.matched_units}/${row.total_units} reporting units`));
    const select = () => { $("year").value = row.year; configure(); render(); };
    point.addEventListener("click", select);
    point.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); select(); } });
    chart.append(point);
  }
  host.replaceChildren(chart);
}
function methodsView() {
  const host = $("voting-methods"), national = state.view === "national", year = Number($("year").value);
  host.hidden = !["states", "national"].includes(state.view) || year === 2026 || stateDemographicView();
  if (host.hidden) return;
  const code = stateCode();
  $("voting-methods-title").textContent = `${year} · ${national ? "United States" : state.selectedState}`;
  $("method-group-label").hidden = !national;
  const groups = state.methodNational.filter(row => row.year === year);
  const key = row => row.category + "|" + row.group;
  options($("method-group"), groups.map(row => [key(row), `${row.category} · ${row.group}`]));
  const selected = groups.find(row => key(row) === $("method-group").value);
  const rows = national ? Object.entries(selected?.methods ?? {}).map(([mode, share_pct]) => ({ mode, share_pct }))
    : state.methodStates.filter(row => row.year === year && row.state_code === code);
  const scope = national ? `national|${selected ? key(selected) : "Overall"}` : code;
  const preferred = scope === state.methodScope ? $("method-history-mode").value
    : ["early_in_person", "election_day", "mail", "domestic_absentee", "all_mail"]
      .find(mode => rows.some(row => row.mode === mode && row.share_pct > 0)) || "early_in_person";
  state.methodScope = scope;
  options($("method-history-mode"), (national ? ["election_day", "early_in_person", "mail", "unknown"]
    : ["election_day", "early_in_person", "domestic_absentee", "all_mail", "uocava", "provisional", "other"])
    .map(mode => [mode, methodLabels[mode]]), preferred);
  $("method-definition").textContent = national
    ? "Share of reported voters, not eligible-population turnout. Census CPS survey."
    : "Share of participants in matched reporting units, not eligible-population turnout. EAC administrative reports.";
  if (!rows.length) $("method-observations").replaceChildren(html("p", "empty", state.methodsError
    || (national ? "No verified voting-method estimates for this year. National history begins in 1996."
      : "No verified state voting-method reports for this year. State reporting begins in 2008; national history begins in 1996.")));
  else {
    const table = html("table"), head = html("thead"), tr = html("tr"), body = html("tbody"), missing = html("tbody");
    for (const name of national ? ["Method", "Share of voters"] : ["Method", "Reported count", "Matched share"]) {
      const th = html("th", "", name); th.scope = "col"; tr.append(th);
    }
    head.append(tr);
    for (const row of rows) {
      const tr = html("tr"); tr.dataset.method = row.mode; tr.dataset.share = row.share_pct ?? "";
      const th = html("th", "", methodLabels[row.mode]); th.scope = "row"; tr.append(th);
      if (!national) {
        const count = html("td", "", fmt(row.reported_count));
        count.append(html("small", "method-coverage", `${row.matched_units}/${row.total_units} units`));
        tr.append(count);
      }
      const share = html("td", "method-share", row.share_pct == null ? "Not reported" : pct(row.share_pct));
      if (row.share_pct != null) {
        const track = html("span", "method-share-track"), bar = html("i");
        track.setAttribute("aria-hidden", "true");
        bar.style.width = `${row.share_pct}%`; track.append(bar); share.append(track);
      }
      tr.append(share);
      (row.share_pct != null || row.reported_count != null ? body : missing).append(tr);
    }
    table.append(head, body); $("method-observations").replaceChildren(table);
    if (missing.childElementCount) {
      const details = html("details", "explorer-notes method-missing"), extra = html("table");
      details.append(html("summary", "", `${missing.childElementCount} methods not reported · not zero`));
      extra.append(head.cloneNode(true), missing); details.append(extra); $("method-observations").append(details);
    }
  }
  const mode = $("method-history-mode").value;
  const history = national ? state.methodNational.filter(row => !selected ? row.category === "Overall" : (selected.category === "Overall"
    ? row.category === "Overall" : key(row) === key(selected))).map(row => ({ ...row, share_pct: row.methods[mode] }))
    : state.methodStates.filter(row => row.state_code === code && row.mode === mode);
  methodHistory(history, mode, national);
  $("method-history-note").textContent = national ? "Survey shares. Breaks mark the 2004 and 2018 definition changes."
    : "Each dot is an observed election. Reporting coverage varies; points are not connected.";
  $("method-note").textContent = national && !selected
    ? `No verified method estimate for ${year}. The chart shows observed overall history, not an estimate for the selected election.`
    : national
    ? (selected?.universe === "valid_method_and_timing_responses"
      ? "1996–2016 excludes unknown method/timing responses. The questionnaire changed in 2004; from 2018 the displayed tables include unknown responses."
      : "2018–2024 retains unknown / refused responses. Race/Hispanic groups overlap and must not be added. Published percentages may differ from 100% by rounding.")
    : "Categories can overlap; do not add them. Missing is not zero.";
  $("method-source-notes").textContent = (state.methods?.notes.join(" ") || state.methodsError)
    + (national ? " Demographic method estimates cover 2018–2024."
      : " Each share matches units reporting both the method and total participation. Counts cover reporting units only. Absentee can include in-person or military/overseas ballots. Participation can be based on vote history, poll books or highest-office votes.");
  const links = $("method-downloads"); links.replaceChildren();
  for (const [file, label] of national ? [["national.csv", "Every national estimate (CSV)"]]
    : [["states.csv", "All state methods and reporting coverage (CSV)"], ["jurisdictions.csv", "Every jurisdiction, method, source comment and participation basis (CSV)"]]) {
    if (!state.methodsPath) continue;
    const link = html("a", "", label); link.href = state.methodsPath + file; link.download = ""; links.append(link);
  }
  if (national && selected) links.append(sourceLink(selected));
  else if (rows.length) links.append(sourceLink(rows[0]));
}
function note(text) {
  $("notice").textContent = text;
  $("notice-panel").hidden = !text;
}
function tooltip(event, text) {
  const box = $("tooltip");
  box.textContent = text;
  box.hidden = false;
  box.style.left = Math.max(8, Math.min(event.clientX + 14, innerWidth - 310)) + "px";
  box.style.top = Math.max(8, Math.min(event.clientY + 14, innerHeight - 150)) + "px";
}
function bindTooltip(element, text) {
  element.addEventListener("pointermove", e => tooltip(e, text));
  element.addEventListener("pointerleave", () => { $("tooltip").hidden = true; });
  element.addEventListener("focus", () => {
    const rect = element.getBoundingClientRect();
    tooltip({ clientX: rect.left, clientY: rect.top }, text);
  });
  element.addEventListener("blur", () => { $("tooltip").hidden = true; });
}
function syncURL() {
  rememberView();
  const url = new URL(location.href);
  url.search = "";
  url.searchParams.set("view", state.view);
  if (["states", "national", "precincts"].includes(state.view)) {
    for (const id of ["year", "basis", "dimension", "group", ...(state.view === "states" ? ["map-color", "map-level"] : []),
      ...(isProvisional() ? ["mode"] : [])])
      if ($(id).value) url.searchParams.set(id, $(id).value);
  }
  if (state.view === "national" && isProvisional()) url.searchParams.set("countState", state.countState);
  if (stateDemographicView()) url.searchParams.set("demographic-state", $("demographic-state").value);
  if (state.view === "states") url.searchParams.set("state", state.selectedState);
  if (state.view === "precincts") {
    url.searchParams.set("state", state.selectedState);
    url.searchParams.set("layer", $("precinct-layer").value);
    if (state.county) url.searchParams.set("county", state.county);
    if (state.precinct) url.searchParams.set("precinct", state.precinct);
  }
  history.replaceState(null, "", url);
}
function configure(preferred = viewSelection()) {
  const precincts = state.view === "precincts";
  if (state.view === "national") options($("demographic-state"),
    [["US", "United States"], ...demographicStates.map(code => [code, stateName(code)])],
    preferred["demographic-state"] || (!state.initialized && params.get("demographic-state"))
      || $("demographic-state").value || "US");
  if ([...$("basis").options].some(option => option.value === preferred.basis))
    $("basis").value = preferred.basis;
  if (state.view === "states") for (const [id, fallback] of [["map-color", "turnout"], ["map-level", "county"]]) {
    const value = preferred[id] || fallback;
    if ([...$(id).options].some(option => option.value === value)) $(id).value = value;
  }
  let rows, years;
  if (precincts) {
    const codes = precinctCoverageCodes();
    const requestedState = (params.get("view") === "precincts" && !state.initialized
      ? params.get("state") : "") || preferred["precinct-state-select"]
      || state.viewSelections.precincts?.["precinct-state-select"]
      || state.selectedState || "North Carolina";
    options($("precinct-state-select"), codes.map(code => [stateName(code), stateName(code)]), requestedState);
    state.selectedState = $("precinct-state-select").value;
    state.precinctControlNote = requestedState && requestedState !== state.selectedState
      ? `No loaded precinct map source for ${requestedState}; showing ${state.selectedState}. Other states' shapes are not substituted.`
      : "";
    const code = stateCode();
    years = precinctSelectionYears(precinctYears(code), preferred.year || params.get("year"),
      unique(state.states.map(row => row.year)));
  } else {
    rows = state.view === "states"
      ? state.states.filter(row => row.denominator === $("basis").value && row.turnout_pct != null)
      : state.national.filter(row => row.denominator === $("basis").value && row.turnout_pct != null);
    years = state.view === "national" && $("demographic-state").value !== "US"
      ? [2024, 2022] : unique([...rows.map(row => row.year), 2026]).sort((a, b) => b - a);
  }
  const requestedYear = (precincts && params.get("view") === "precincts" && !state.initialized
    ? params.get("year") : "") || preferred.year
    || String(years[0] ?? "");
  options($("year"), years.map(year => [String(year), year === 2026 ? "2026 · Provisional" : String(year)]), requestedYear);
  if (precincts && requestedYear && requestedYear !== $("year").value)
    state.precinctControlNote += `${state.precinctControlNote ? " " : ""}No loaded ${requestedYear} precinct layer for ${state.selectedState}; showing ${$("year").value}. Other years' boundaries are not substituted.`;
  if (precincts) {
    const requestedLayer = (params.get("view") === "precincts" && !state.initialized ? params.get("layer") : "")
      || preferred["precinct-layer"] || "participation";
    const layers = precinctLayerOptions(stateCode(), Number($("year").value), requestedLayer);
    options($("precinct-layer"), layers, requestedLayer);
    if (requestedLayer && requestedLayer !== $("precinct-layer").value)
      state.precinctControlNote += `${state.precinctControlNote ? " " : ""}The requested ${requestedLayer} layer is unavailable for this state and year; showing ${$("precinct-layer").selectedOptions[0]?.textContent || "the available layer"}.`;
  }
  const ncParticipation = precincts && ncParticipationView();
  options($("dimension"), ncParticipation
    ? [["overall", "All registered voters"], ["race", "Race"], ["ethnicity", "Ethnicity"], ["sex", "Sex"], ["age", "Age"]]
    : precincts ? [["overall", "All available reporting units"]]
      : [["overall", "Overall"], ["race", "Race / ethnicity"], ["age", "Age"], ["sex", "Sex"], ["education", "Education"],
      ...($("year").value === "2026" ? [["ethnicity", "Ethnicity"]] : [])], preferred.dimension);
  const provisional = isProvisional();
  document.querySelector(".explorer-options").hidden = provisional || precincts && !ncParticipation;
  options($("mode"), Object.entries(modeLabels).filter(([mode]) => mode === "civic_model"
    ? state.view === "national" : state.view !== "national"
      || !["official", "available", "uf_vep", "uf_vap"].includes(mode)),
    precincts ? "official" : preferred.mode || (state.view === "national" && provisional ? "civic_model" : undefined));
  if (civicModelView()) options($("dimension"), civicDimensions, preferred.dimension);
  configureGroups(preferred.group);
  for (const [id, visible] of [
    ["state-label", state.view === "states"], ["precinct-state-label", precincts],
    ["precinct-layer-label", precincts],
    ["current-state-label", state.view === "national" && provisional],
    ["demographic-state-label", state.view === "national" && !provisional],
    ["mode-label", provisional && state.view !== "precincts"],
    ["county-label", ncParticipation], ["precinct-search-label", ncParticipation],
    ["basis-label", !precincts && !provisional], ["minimum-label", ncParticipation],
    ["dimension-label", state.view === "national" || ncParticipation],
    ["group-label", state.view === "national" || ncParticipation],
    ["map-color-label", state.view === "states"], ["map-level-label", state.view === "states"],
  ]) $(id).hidden = !visible;
  rememberView();
}
function configureGroups(preferred = $("group").value) {
  const dimension = $("dimension").value;
  let groups;
  if (state.view === "precincts" && ncParticipationView()) {
    groups = unique((state.ncSummary.find(row => row.year === Number($("year").value))?.statewide ?? [])
      .filter(row => row.dimension === dimension).map(row => row.group));
  } else if (state.view === "precincts") {
    groups = ["All available reporting units"];
  } else if (civicModelView()) {
    const choices = civicStatesData ? civicGroupOptions(civicStatesData, dimension) : [];
    options($("group"), [["All groups", "All groups"], ...choices], preferred);
    return;
  } else if (isProvisional()) {
    groups = ["All groups", ...unique(currentGroups().map(row => row.group))];
  } else if (stateDemographicView()) {
    groups = ["All groups", ...demographicGroups(dimension)];
  } else {
    groups = ["All groups", ...unique(state.national.filter(row => row.denominator === $("basis").value
      && (dimension === "age" ? row.dimension === "overall" && row.age_group !== "All ages"
        : row.dimension === dimension && row.age_group === "All ages"))
      .map(row => dimension === "age" ? row.age_group : row.group))];
  }
  options($("group"), groups.map(group => [group, group]), preferred);
}
function showView(view) {
  const updates = view === "updates";
  if (updates) view = "states";
  const enteringPrecincts = view === "precincts" && state.view !== "precincts"
    && !state.viewSelections.precincts;
  const precinctDefaults = enteringPrecincts
    ? { year: $("year").value, "precinct-state-select": state.selectedState } : {};
  rememberView();
  state.view = view;
  if (view === "states" && state.viewSelections.states?.selectedState) {
    state.selectedState = state.viewSelections.states.selectedState;
    $("state-select").value = state.selectedState;
  }
  clearTimeout(state.drillTimer); ++state.drillToken; state.drillKey = "";
  $("geography-note").hidden = true;
  root.dataset.activeView = view;
  for (const button of document.querySelectorAll(".participation-nav button")) {
    button.setAttribute("aria-selected", String(button.dataset.view === view));
    button.tabIndex = button.dataset.view === view ? 0 : -1;
  }
  for (const panel of document.querySelectorAll("[data-section]"))
    panel.classList.toggle("is-visible", panel.dataset.section === view);
  const methodsPanel = $("methods-panel");
  $("methods-archive").classList.toggle("is-visible", view === "methods"
    && Boolean(hashTarget()?.closest("#methods-archive")));
  $("historical-explorer").hidden = view === "methods";
  methodsPanel.hidden = view !== "methods";
  $("historical-explorer").setAttribute("role", "tabpanel");
  $("historical-explorer").setAttribute("aria-labelledby", `tab-${view}`);
  $("historical-explorer").setAttribute("aria-hidden", String(view === "methods"));
  methodsPanel.setAttribute("aria-hidden", String(view !== "methods"));
  $("search").value = "";
  if (!state.geometry) {
    if (view !== "methods")
      $("visualization").replaceChildren(html("p", "empty", "Loading the saved analysis…"));
    return;
  }
  if (view !== "methods") {
    const preferred = { ...precinctDefaults, ...state.viewSelections[view] };
    if (updates) preferred.year = "2026";
    configure(preferred);
  }
  render();
}
function setTable(rows, columns) {
  state.table = rows; state.columns = columns;
  renderTable();
}
function renderTable() {
  const search = $("search").value.toLowerCase();
  const rows = state.table.filter(row => JSON.stringify(row).toLowerCase().includes(search));
  const head = html("tr");
  for (const [, label] of state.columns) {
    const th = html("th", "", label); th.scope = "col"; head.append(th);
  }
  $("table-head").replaceChildren(head);
  $("table-body").replaceChildren(...rows.slice(0, 150).map(row => {
    const tr = html("tr");
    for (const [key] of state.columns) {
      const value = row[key];
      tr.append(html("td", typeof value === "number" ? "numeric" : "",
        key === "turnout_pct" ? pct(value) : Array.isArray(value) ? value.join("; ") || "OK" : value == null ? "—" : String(value)));
    }
    return tr;
  }));
  $("table-note").textContent = `${fmt(rows.length)} observations; showing ${Math.min(rows.length, 150)}. Complete downloads include every observation, including flagged and unmatched records.`;
}
function legend(items) {
  const wrapper = html("div", "legend");
  for (const [label, color] of items) {
    const span = html("span"), swatch = html("i", "swatch");
    swatch.style.setProperty("--color", color);
    span.append(swatch, document.createTextNode(label)); wrapper.append(span);
  }
  $("key").replaceChildren(wrapper);
}
function ramp() {
  const wrapper = html("div", "legend");
  wrapper.append(html("span", "", "20%"), html("i", "ramp"), html("span", "", "85%+"),
    html("span", "", "Gray: no rate"));
  $("key").replaceChildren(wrapper);
}
function fill(value) {
  if (value == null) return "#edf0f3";
  const t = Math.max(0, Math.min(1, (value - 20) / 65));
  return `rgb(${[240, 244, 249].map((c, i) => Math.round(c + t * ([40, 71, 102][i] - c))).join(",")})`;
}
function countLegend(maximum, label) {
  legend([[`${label} · 0`, countFill(0, maximum)],
    [fmt(Math.round(maximum / 4)), countFill(maximum / 4, maximum)],
    [fmt(maximum), countFill(maximum, maximum)]]);
}
function marginFill(value) {
  if (value == null) return "#d6d3cb";
  const t = Math.min(1, Math.abs(value) / 35);
  const destination = value < 0 ? [137, 40, 45] : [37, 75, 120];
  return `rgb(${[237, 232, 220].map((c, i) => Math.round(c + t * (destination[i] - c))).join(",")})`;
}
function marginLabel(row) {
  if (row?.margin_pp == null) return "No election-margin observation";
  return `${row.margin_pp > 0 ? "D" : row.margin_pp < 0 ? "R" : "Even"}${row.margin_pp ? "+" + Math.abs(row.margin_pp).toFixed(1) : ""} pp`;
}
function marginLegend(office) {
  const wrapper = html("div", "legend margin-legend");
  wrapper.append(html("span", "", "R+35"), html("i", "margin-ramp"), html("span", "", "D+35"),
    html("span", "legend-definition", `${office} · D−R / all votes · gray: no return`));
  $("key").replaceChildren(wrapper);
}
function stateCode() {
  return state.geometry.features.find(feature => feature.properties.NAME === state.selectedState)?.properties.STUSAB;
}
function marginRow(level, key) {
  const year = Number($("year").value), office = year % 4 === 0 ? "President" : "U.S. House";
  return state.margins.find(row => row.year === year && row.level === level && row.geography === key && row.office === office);
}
function modeFor(row) {
  return participationLabel(row || {}) || modeLabels[row?.mode] || modeLabels.official;
}
function header(subtitle, title, measure, caption) {
  $("subtitle").textContent = subtitle; $("title").textContent = title;
  $("measure").textContent = measure; $("caption").textContent = caption;
}
function seriesChart(container, rows, { width = 720, height = 390, compact = false, dimension = "overall" } = {}) {
  const chart = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img",
    "aria-label": compact ? `${state.selectedState} turnout history` : "Turnout across elections", class: "turnout-chart" });
  const left = compact ? 35 : 45, right = width - 18, bottom = height - 35, top = 18;
  const observedYears = unique(rows.filter(row => row.turnout_pct != null).map(row => row.year)).sort((a, b) => a - b);
  if (!observedYears.length) {
    container.replaceChildren(html("p", "empty", "No observed turnout rates for this selection."));
    return;
  }
  const minYear = observedYears[0], maxYear = observedYears.at(-1);
  const x = year => minYear === maxYear ? (left + right) / 2
    : left + (year - minYear) / (maxYear - minYear) * (right - left);
  const y = rate => bottom - rate / 100 * (bottom - top);
  for (const value of compact ? [40, 60, 80] : [0, 20, 40, 60, 80, 100]) {
    chart.append(svgNode("line", { x1: left, x2: right, y1: y(value), y2: y(value), class: "chart-grid" }),
      svgNode("text", { x: left - 8, y: y(value) + 4, "text-anchor": "end", class: "axis-label" }, value + "%"));
  }
  const count = compact || width < 500 ? 3 : 6;
  let ticks = compact ? observedYears.filter((year, index) => index === 0 || (year - minYear) % 8 === 0)
    : unique(Array.from({ length: Math.min(count, observedYears.length) }, (_, index) =>
      observedYears[Math.round(index * (observedYears.length - 1) / Math.max(1, Math.min(count, observedYears.length) - 1))]));
  ticks = ticks.filter(year => year === maxYear || Math.abs(x(year) - x(maxYear)) >= 26);
  ticks.push(maxYear);
  const selectedYear = Number($("year").value);
  if (observedYears.includes(selectedYear)) {
    ticks = ticks.filter(year => Math.abs(x(year) - x(selectedYear)) >= 26);
    ticks.push(selectedYear);
  }
  ticks = unique(ticks).sort((a, b) => a - b);
  for (const year of ticks) chart.append(svgNode("text", { x: x(year), y: height - 10,
    "text-anchor": "middle", class: "axis-label year-tick" }, String(year)));
  if (!compact && observedYears.includes(Number($("year").value)))
    chart.append(svgNode("line", { x1: x(Number($("year").value)), x2: x(Number($("year").value)),
      y1: top, y2: bottom, stroke: "#aaa99c", "stroke-dasharray": "3 4" }));
  unique(rows.map(row => row.series)).forEach(name => {
    {
      const color = colors[0];
      const observations = rows.filter(row => row.series === name && row.turnout_pct != null)
        .sort((a, b) => a.year - b.year);
      let segment = [];
      const flush = () => {
        if (segment.length > 1) chart.append(svgNode("path", {
          d: segment.map((r, i) => `${i ? "L" : "M"}${x(r.year)},${y(r.turnout_pct)}`).join(" "),
          class: "chart-line", stroke: color,
        }));
        segment = [];
      };
      for (const row of observations) {
        const previous = segment.at(-1);
        if (previous) {
          const change = dimension === "local"
            && (previous.year >= 2008 && previous.year <= 2018) !== (row.year >= 2008 && row.year <= 2018)
            ? "EAC question changed between ballots counted and ballots cast (whether counted or not)."
            : dimension === "race" && previous.year < 2004 && row.year >= 2004 ? "Race categories changed in 2004."
            : !["precinct", "local"].includes(dimension) && $("basis").value === "cvap" && previous.year < 1994 && row.year >= 1994
              ? "Citizenship measurement changed in 1994."
              : dimension === "education" && previous.year < 1992 && row.year >= 1992 ? "Education categories changed in 1992."
                : previous.year < 1972 && row.year >= 1972 ? "Survey definitions changed in 1972." : "";
          if (row.year - previous.year !== 2) flush();
          else if (change) {
            const label = `${previous.year}–${row.year}: ${change} Estimates are not directly comparable.`;
            const connector = svgNode("path", {
              d: `M${x(previous.year)},${y(previous.turnout_pct)} L${x(row.year)},${y(row.turnout_pct)}`,
              class: "chart-definition-break", stroke: color, tabindex: "0", role: "img", "aria-label": label,
              "data-from-year": previous.year, "data-to-year": row.year,
            });
            bindTooltip(connector, label);
            chart.append(connector);
            flush();
          }
        }
        segment.push(row);
      }
      flush();
      for (const row of observations) {
        const selected = row.year === Number($("year").value), size = selected ? 4.5 : compact ? 2.6 : 3.5;
        const point = svgNode("circle", { cx: x(row.year), cy: y(row.turnout_pct), r: size });
        for (const [key, value] of Object.entries({ fill: color, class: "chart-point", tabindex: "0",
          role: "button", "aria-label": `${name}, ${row.year}, ${pct(row.turnout_pct)}`
            + (dimension === "local" ? " participants / total registrations" : " reported voting"),
          "aria-pressed": String(selected), "data-year": row.year, "data-rate": row.turnout_pct })) point.setAttribute(key, value);
        bindTooltip(point, `${name} · ${row.year}\n${pct(row.turnout_pct)}`
          + (dimension === "local" ? " participants / total registrations" : " reported voting"));
        const selectYear = () => {
          if ([...$("year").options].some(option => option.value === String(row.year))) {
            if (dimension === "precinct" && state.view === "states") {
              $("year").value = String(row.year);
              $("dimension").value = "overall";
              showView("precincts");
              return;
            }
            if (dimension !== "precinct" && $("year").value !== String(row.year)) state.precinct = "";
            $("year").value = String(row.year); configure(); render();
          }
        };
        point.addEventListener("click", selectYear);
        point.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault(); selectYear();
          }
        });
        chart.append(point);
      }
    }
  });
  container.replaceChildren(chart);
}
function nationalRows(dimension, basis, group) {
  const rows = state.national.filter(row => row.denominator === basis
    && (dimension === "age" ? row.dimension === "overall" && row.age_group !== "All ages"
      : row.dimension === dimension && row.age_group === "All ages"))
    .map(row => ({ ...row, series: dimension === "age" ? row.age_group : row.group }));
  return group && group !== "All groups" ? rows.filter(row => row.series === group) : rows;
}
function nationalView() {
  if (civicModelView()) return civicStateModelView(state.generation);
  if (isProvisional()) { provisionalGroupsView(); return; }
  if (stateDemographicView()) return stateDemographicsView(state.generation);
  const dimension = $("dimension").value, basis = $("basis").value, group = $("group").value;
  const rows = nationalRows(dimension, basis, group);
  header(`${$("year").value} selected · National Census survey estimates`,
    dimension === "overall" ? "Participation over time" : `Participation by ${$("dimension").selectedOptions[0].textContent.toLowerCase()}`,
    `Share of ${basis === "cvap" ? "adult citizens" : "all adult residents, including noncitizens"} who reported voting.`,
    "Each point is an observed election year. Dashed connectors mark survey-definition changes; missing elections remain gaps.");
  $("map-tools").hidden = true; $("map-help").hidden = true;
  state.map = null;
  $("key").replaceChildren();
  const issues = unique(rows.flatMap(row => row.warnings));
  if (!rows.some(row => row.year === Number($("year").value)))
    issues.unshift("No estimate for the selected year and population. Other available years remain shown.");
  note(issues.join(" "));
  const names = unique(rows.map(row => row.series));
  const grid = html("div", `demographic-grid${names.length === 1 ? " single-series" : ""}`);
  for (const name of names) {
    const groupRows = rows.filter(row => row.series === name);
    const card = html("section", "demographic-card");
    card.dataset.group = name;
    const heading = html("div", "demographic-card-heading");
    const selected = groupRows.find(row => row.year === Number($("year").value));
    heading.append(html("h3", "", name), html("strong", "demographic-value", pct(selected?.turnout_pct)));
    const chart = html("div");
    const numeric = groupRows.filter(row => row.turnout_pct != null);
    card.append(heading, html("p", "demographic-period", `${$("year").value}`), chart);
    seriesChart(chart, groupRows, { width: names.length === 1 ? 720 : 360,
      height: names.length === 1 ? 330 : 245, dimension });
    if (numeric.length) card.append(html("p", "demographic-period", `Observed ${Math.min(...numeric.map(row => row.year))}–${Math.max(...numeric.map(row => row.year))}`));
    grid.append(card);
  }
  $("visualization").replaceChildren(grid.childElementCount ? grid : html("p", "empty", "No comparable series for this population."));
  if (!rows.some(row => row.year === Number($("year").value))) {
    const gap = html("div", "observation-gap",
      `${$("year").value} is included in the explorer, but this demographic breakdown has no estimate for the selected population. Available years are shown below.`);
    const overall = state.national.some(row => row.year === Number($("year").value)
      && row.dimension === "overall" && row.age_group === "All ages" && row.denominator === basis);
    if (overall && dimension !== "overall") {
      const button = html("button", "", `Show overall participation in ${$("year").value}`);
      button.type = "button";
      button.addEventListener("click", () => { $("dimension").value = "overall"; configure(); render(); });
      gap.append(button);
    }
    $("visualization").prepend(gap);
  }
  const panel = $("selection-panel");
  panel.replaceChildren(html("p", "eyebrow", `${$("year").value} · ${typeFor(Number($("year").value))}`),
    html("h3", "", "The selected election"));
  const snapshot = rows.filter(row => row.year === Number($("year").value));
  const list = html("ul", "group-snapshot");
  for (const row of snapshot) {
    const li = html("li"); li.append(html("span", "", row.series), html("strong", "", pct(row.turnout_pct)));
    list.append(li);
  }
  panel.append(list, html("p", "selection-note", snapshot.length
    ? `Self-reported participation, not candidate preference.${dimension === "race" ? " Race-alone categories overlap Hispanic ethnicity." : ""}`
    : "This series has no estimate for the selected election. Missing is not zero turnout."));
  setTable(rows.sort((a, b) => b.year - a.year), [["year", "Year"], ["election_type", "Election"],
    ["series", "Group"], ["turnout_pct", "Turnout"], ["denominator", "Population"], ["warnings", "Notes"]]);
}
async function stateDemographicsView(generation) {
  const code = $("demographic-state").value, year = Number($("year").value);
  const dimension = $("dimension").value, group = $("group").value;
  header(`${year} ${typeFor(year)} election · ${stateName(code)} · CPS`,
    `Participation in ${stateName(code)}`,
    "Reported voting / all source-weighted civilian noninstitutionalized adult citizens, including unknown responses.",
    "2022 and 2024 are separate survey cross-sections, not the same people. These are descriptive estimates, not administrative turnout or 2026 forecasts.");
  $("map-tools").hidden = true; $("map-help").hidden = true; state.map = null;
  $("key").replaceChildren();
  const panel = $("selection-panel");
  panel.replaceChildren(html("h3", "", `${stateName(code)} · ${year}`),
    html("p", "selection-note", "Unknown responses remain in the denominator. Small samples are flagged; no design confidence interval is supplied."));
  for (const [file, text] of [["complete-analysis.zip", "Complete inputs, code and all queries (ZIP)"],
    ["complete-state-demographic-participation.csv", "Every state and demographic estimate (CSV)"]]) {
    const link = html("a", "source-link", text); link.href = demographicSource.release + file; panel.append(link);
  }
  if ($("basis").value !== "cvap") {
    $("visualization").replaceChildren(html("p", "empty",
      "State demographic estimates here use adult citizens only. Select Adult citizens (CPS) under More options; no all-resident rate is inferred."));
    setTable([], [["year", "Year"], ["series", "Group"], ["turnout_pct", "Participation"]]);
    return;
  }
  $("visualization").replaceChildren(html("p", "empty", "Loading source-verified state demographic estimates…"));
  try {
    demographicsPromise ||= loadDemographics();
    const data = await demographicsPromise;
    if (generation !== state.generation || !stateDemographicView()) return;
    const rows = demographicRows(data, code, dimension, group);
    const grid = html("div", "demographic-grid");
    for (const name of unique(rows.map(row => row.series))) {
      const history = rows.filter(row => row.series === name);
      const row = history.find(row => row.year === year);
      const card = html("section", "demographic-card");
      Object.assign(card.dataset, { group: name, state: code, year: String(year),
        rate: row?.reported_voting_pct || "", sampleN: String(row?.sample_n ?? ""),
        unknown: row?.unknown_pct || "", smallSample: String(Boolean(row?.low_n)) });
      const heading = html("div", "demographic-card-heading");
      heading.append(html("h3", "", name), html("strong", "demographic-value", pct(row?.turnout_pct)));
      const chart = html("div");
      card.append(heading, chart, html("p", "demographic-period",
        `Source cases: ${fmt(row?.sample_n)} · Unknown: ${row?.unknown_response ?? "Not available"}`));
      seriesChart(chart, history, { width: 360, height: 245, dimension });
      if (row?.low_n) card.append(html("p", "selection-note", "Small sample · interpret cautiously; no design confidence interval."));
      if (row?.turnout_pct == null) card.append(html("p", "selection-note", "No observed source cell, not zero participation."));
      grid.append(card);
    }
    $("visualization").replaceChildren(grid);
    setTable(rows.sort((a, b) => b.year - a.year), [["year", "Year"], ["election_type", "Election"],
      ["series", "Group"], ["turnout_pct", "Reported voting"], ["sample_n", "Source cases"],
      ["unknown_response", "Unknown response"], ["warnings", "Notes"]]);
    note(dimension === "race" ? "Exclusive source race/Hispanic-origin groups, not the overlapping national race-alone series. Other non-Hispanic is pooled; AP/Civic definitions are not harmonized." : "");
  } catch (error) {
    if (generation !== state.generation) return;
    $("visualization").replaceChildren(html("p", "empty",
      `State demographic source unavailable: ${error.message}. No values inferred; complete downloads and United States histories remain available.`));
    setTable([], [["year", "Year"], ["series", "Group"], ["turnout_pct", "Participation"]]);
  }
}
function currentOfficialRows() {
  return [...(state.current?.reporting ?? []).filter(row =>
    !state.reviewedStates.some(reviewed => reviewed.state_code === row.state_code)), ...state.reviewedStates];
}
function currentStateRows() {
  const officialRows = currentOfficialRows();
  if ($("mode").value === "available") {
    const jurisdictions = unique([...(state.current?.coverage ?? []).map(row => row.state_code),
      ...state.reviewedStates.map(row => row.state_code)]);
    return jurisdictions.flatMap(code => {
      const official = officialRows.find(row => row.state_code === code);
      const early = (state.current?.early_voting ?? []).filter(row => row.state_code === code && row.geography_level === "state");
      const row = official || early.find(row => row.mode === "in_person_early") || early.find(row => row.mode === "mail_returned");
      return row ? [{ ...row, observation_type: modeFor(row) }] : [];
    });
  }
  return $("mode").value === "official" ? officialRows
    : (state.current?.early_voting ?? []).filter(row => row.mode === $("mode").value && row.geography_level === "state");
}
function currentGroups() {
  if ($("dimension").value === "overall") {
    const total = currentStateRows().find(row => row.state_code === state.countState);
    return total ? [{ ...total, group: "All reported ballots", dimension: "overall", turnout_pct: null }] : [];
  }
  return (state.current?.demographics ?? []).filter(row => row.state_code === state.countState
    && row.mode === $("mode").value && row.dimension === currentDimension() && row.demographic_source_total > 0);
}
function sourceNote(row) {
  if (!row) return "No observation has been ingested for this selection. Missing is not zero.";
  return `Source update: ${row.source_date || row.source_update_label || "not dated"}.`
    + (row.status === "retained_after_failure" ? " Retained from an earlier capture after a source failure." : "")
    + (row.quality?.length ? ` Source caveats: ${row.quality.join("; ").replaceAll("_", " ")}.` : "");
}
function sourceLink(row) {
  const link = html("a", "source-link", row.review_id ? "Complete native participation table (CSV)" : "Original source");
  link.href = row.source_url;
  return link;
}
function provisionalGroupsView() {
  const name = $("current-state-select").selectedOptions[0]?.textContent ?? state.countState;
  const group = $("group").value;
  const rows = currentGroups().filter(row => group === "All groups" || row.group === group)
    .sort((a, b) => b.ballots - a.ballots);
  header("2026 midterm election · reported observations", `Participation in ${name}`,
    `${modeLabels[$("mode").value]}. Ballot counts, not demographic turnout rates.`,
    "Provisional counts cover only the selected voting mode and state. No matched group population denominator is available; these counts are not added to historical turnout-rate lines.");
  $("map-tools").hidden = true; $("map-help").hidden = true;
  state.map = null; state.mapPaths = [];
  $("key").replaceChildren();
  const list = html("ul", "provisional-bars");
  const maximum = Math.max(1, ...rows.map(row => row.ballots));
  for (const row of rows) {
    const item = html("li"); item.dataset.group = row.group; item.dataset.ballots = row.ballots;
    const track = html("div", "count-track"), bar = html("i");
    bar.style.width = `${100 * row.ballots / maximum}%`;
    track.setAttribute("aria-hidden", "true"); track.append(bar);
    item.append(html("span", "", row.group), html("strong", "", fmt(row.ballots)), track);
    list.append(item);
  }
  const visual = $("visualization");
  if (rows.length) {
    visual.replaceChildren(list, html("p", "count-source", sourceNote(rows[0])), sourceLink(rows[0]));
  } else visual.replaceChildren(html("p", "empty",
    `No 2026 ${$("dimension").selectedOptions[0].textContent.toLowerCase()} breakdown is reported for this state and voting mode. Choose another category or year.`));
  note(state.currentError || (rows.length ? "Group definitions differ across states. Counts do not cover the full election and must not be pooled into a national turnout rate." : ""));
  setTable(rows, [["state", "State"], ["mode", "Voting mode"], ["group", "Group"],
    ["ballots", "Ballots reported"], ["source_date", "Source date"], ["status", "Status"], ["quality", "Notes"]]);
}
async function civicStateModelView(generation) {
  const code = state.countState, dimension = $("dimension").value, group = $("group").value;
  header("2026 midterm · Civic source-weighted model", `Modeled participation in ${stateName(code)}`,
    "Source-weighted share classified as likely voters. Not reported ballots or certified demographic turnout.",
    "No 2024 extrapolation, group-population scaling or local allocation. Source field period, calibration and state representativeness remain unqualified; no design confidence interval.");
  $("map-tools").hidden = true; $("map-help").hidden = true; state.map = null; state.mapPaths = [];
  $("key").replaceChildren();
  const panel = $("selection-panel");
  panel.replaceChildren(html("h3", "", `${stateName(code)} · 2026`),
    html("p", "selection-note", "Native LIKELYVOTER model, not administrative voting. All source weight remains in each group's denominator; unknown demographics remain in statewide totals."));
  for (const [file, label] of [["complete-analysis.zip", "Complete 2026 inputs, code and results (ZIP)"],
    ["complete-state-demographic-query.csv", "Every state/group estimate and holding (CSV)"]]) {
    const link = html("a", "source-link", label); link.href = civicStateSource.release + file; panel.append(link);
  }
  $("visualization").replaceChildren(html("p", "empty", "Loading source-verified 2026 model estimates…"));
  try {
    civicStatesPromise ||= loadCivicStates();
    civicStatesData = await civicStatesPromise;
    if (generation !== state.generation || !civicModelView()) return;
    configureGroups(!civicModelInitialized && params.get("mode") === "civic_model"
      ? params.get("group") || group : group);
    civicModelInitialized = true;
    const selectedGroup = $("group").value;
    const rows = civicStateRows(civicStatesData, code, dimension)
      .filter(row => selectedGroup === "All groups" || row.group === selectedGroup);
    const grid = html("div", "demographic-grid");
    for (const row of rows) {
      const card = html("section", "demographic-card");
      Object.assign(card.dataset, { civicState: code, group: row.group,
        rate: row.modeled_voter_pct ?? "", disposition: row.disposition, sampleN: String(row.n ?? "") });
      const value = row.modeled_voter_pct === null ? null : Number(row.modeled_voter_pct);
      const heading = html("div", "demographic-card-heading");
      heading.append(html("h3", "", row.label), html("strong", "demographic-value",
        value === null ? "Not publicly estimated" : pct(value)));
      card.append(heading);
      if (value !== null) {
        const track = html("div", "count-track"), bar = html("i");
        bar.style.width = `${value}%`; track.setAttribute("aria-hidden", "true"); track.append(bar);
        card.append(track, html("p", "demographic-period", `${fmt(row.n)} source cases · modeled voter share`));
      } else card.append(html("p", "selection-note", row.disposition === "no_dc_source_sample"
        ? "No D.C. survey sample; no value is inferred."
        : "Held for source support or disclosure protection, including complementary cells. Missing is not zero."));
      grid.append(card);
    }
    $("visualization").replaceChildren(grid);
    setTable(rows.map(row => ({ ...row, modeled_share: row.modeled_voter_pct === null
      ? "Not publicly estimated" : pct(Number(row.modeled_voter_pct)) })),
    [["state_code", "State"], ["label", "Source group"], ["modeled_share", "Modeled voter share"],
      ["n", "Source cases"], ["disposition", "Evidence / holding"]]);
    note(dimension === "county_context" ? "Native urban/suburban/rural county context, not measured individual residence or local turnout."
      : dimension === "income" ? "Source income bins; household-income definition is not independently qualified."
        : "Native/coarsened study categories are not harmonized to CPS. Sparse and within/across-state complementary groups remain held.");
  } catch (error) {
    if (generation !== state.generation) return;
    $("visualization").replaceChildren(html("p", "empty",
      `2026 model source unavailable: ${error.message}. Complete downloads and separate reported observations remain available; no values inferred.`));
    setTable([], [["label", "Source group"], ["modeled_share", "Modeled voter share"]]);
  }
}
function stateDetail() {
  const basis = $("basis").value, year = Number($("year").value);
  const rows = state.states.filter(row => row.state === state.selectedState && row.denominator === basis)
    .map(row => ({ ...row, series: row.state }));
  const provisional = isProvisional();
  const selected = provisional ? stateParticipationRows().find(row => row.state === state.selectedState) : rows.find(row => row.year === year);
  const national = state.national.find(row => row.year === year && row.denominator === basis
    && row.dimension === "overall" && row.age_group === "All ages");
  const panel = $("selection-panel");
  panel.replaceChildren(html("p", "eyebrow", `${year} · ${provisional ? "provisional" : typeFor(year)}`),
    html("h3", "", state.selectedState),
    html("p", `selection-rate${selected ? "" : " selection-unavailable"}`,
      provisional ? selected?.turnout_pct != null ? participationRate(selected)
        : selected ? fmt(selected.ballots) : "Not reported" : pct(selected?.turnout_pct)),
    html("p", "selection-basis", provisional ? selected?.uf_source
      ? `${ufBasis().toUpperCase()} turnout · UF ${selected.source_status}`
      : `${selected ? modeFor(selected) : modeLabels[$("mode").value]} · not final turnout`
      : `of ${basis === "cvap" ? "adult citizens" : "all adult residents"} reported voting`));
  if (provisional) {
    panel.append(html("p", "selection-note", selected?.uf_source
      ? `${fmt(selected.ballots)} source-estimated ballots / ${fmt(selected.denominator)} ${selected.denominator_basis}. `
        + `${selected.source_date}. Not final official counts, a CPS estimate or a demographic turnout rate.`
      : sourceNote(selected)));
    if ($("mode").value === "official" && state.ufTurnout.length && $("map-color").value !== "margin") {
      const restore = html("button", "selection-link", "Show nationwide turnout estimates");
      restore.id = "show-nationwide-turnout"; restore.type = "button";
      restore.addEventListener("click", () => { $("mode").value = "available"; render(); resetMap(); });
      panel.append(restore);
    }
    if (selected) {
      panel.append(sourceLink(selected));
      if (!selected.uf_source && selected.validated_pct != null) panel.append(html("p", "selection-note",
        `${fmt(selected.ballots)} ${participationLabel(selected) || "reported ballots"} / ${selected.denominator_basis.replaceAll("_", " ")} (${fmt(selected.denominator)}). Not a CPS survey rate.`));
    }
    const official = currentOfficialRows().find(row => row.state === state.selectedState);
    if (selected?.uf_source && official) {
      const observed = html("div", "substate-detail"); observed.id = "official-state-counts";
      observed.append(html("h4", "", "Separate official administrative observation"),
        html("p", "selection-basis", `${fmt(official.ballots)} ${participationLabel(official) || "reported ballots"}`),
        html("p", "selection-note", official.validated_pct == null ? sourceNote(official)
          : `${pct(official.validated_pct)} / ${official.denominator_basis.replaceAll("_", " ")} `
            + `(${fmt(official.denominator)}). ${sourceNote(official)} Not the UF population denominator.`),
        sourceLink(official));
      panel.append(observed);
    }
    const navigation = html("div", "substate-detail");
    navigation.id = "current-local-navigation"; panel.append(navigation);
    currentNavigation(navigation);
    const precinctCoverage = matchedPrecinctParticipationCoverage(stateCode());
    if (precinctCoverage || state.currentPrecincts?.states[stateCode()]) {
      const button = html("button", "selection-link", precinctCoverage
        ? `Show ${fmt(precinctCoverage.features)} matched precincts' participation`
        : "Show loaded 2026 precinct participation");
      button.id = "show-matched-precinct-participation"; button.type = "button";
      button.addEventListener("click", () => {
        $("map-level").value = "precinct"; $("map-color").value = "turnout";
        if (!matchedPrecinctParticipationMode()) $("mode").value = "official";
        render();
        const item = state.map?.stateItems?.get(stateCode());
        if (item) fit(item.bounds);
      });
      panel.append(button);
    }
    const administrations = stateCode() === "HI"
      && state.additionalCoverage.some(row => row.state_code === "HI" && row.localities === 4);
    const towns = stateCode() === "CT"
      && state.additionalCoverage.some(row => row.state_code === "CT" && row.localities === 169);
    const localityActivity = stateCode() === "ME"
      && state.additionalCoverage.some(row => row.state_code === "ME" && row.source_mode_counties === 480);
    const countyAudit = administrations ? { counties: 4 }
      : towns ? { counties: 169 }
        : localityActivity ? { counties: 480, provider_activity: true }
      : state.current?.local_audit?.find(row => row.state_code === stateCode() && row.counties > 0)
        || state.countyContext?.coverage[stateCode()]
        || (() => {
          const activity = state.additionalCoverage.find(row => row.state_code === stateCode())?.source_mode_counties;
          return activity ? { counties: activity, provider_activity: true } : null;
        })();
    if (countyAudit) {
      const button = html("button", "selection-link", administrations
        ? "Show 4 election administrations" : towns ? "Show 169 native town counts"
          : localityActivity ? "Show 480 locality source-activity counts" : countyAudit.provider_activity
          ? `Show ${fmt(countyAudit.counties)} county source-activity counts`
          : `Show ${fmt(countyAudit.counties)} counties' participation`);
      button.id = "show-current-counties"; button.type = "button";
      button.addEventListener("click", () => {
        $("map-level").value = "county"; $("map-color").value = "turnout";
        if (!ufMode() && !hasCountySourceMode(stateCode(), $("mode").value))
          $("mode").value = countyAudit.provider_activity ? "available" : "official";
        render();
        const item = state.map?.stateItems?.get(stateCode());
        if (item) fit(item.bounds);
      });
      panel.append(button);
      if ($("map-level").value === "precinct" && !state.currentPrecincts?.states[stateCode()] && !precinctCoverage)
        panel.append(html("p", "selection-note",
          localityActivity ? "Verified 2026 precinct geography is unavailable. Partial local source activity is available on 2024 contextual shapes; county/precinct totals and missing regions are not allocated."
            : towns ? "Verified 2026 precinct geography is unavailable. Native counts for 169 towns are available on explicitly dated 2024 contextual municipality shapes, not allocated to counties or precincts."
            : administrations ? "Verified 2026 precinct geography is unavailable. Four native election-administration counts are available instead, with no rates or separate Maui/Kalawao allocation."
            : "Verified 2026 precinct geography is unavailable for this state. County counts and their own participation denominators are available instead; no state or county rate is assigned to a precinct."));
    }
  } else if (selected?.turnout_pct != null && national?.turnout_pct != null) {
    const difference = selected.turnout_pct - national.turnout_pct;
    panel.append(html("p", "selection-note", `${Math.abs(difference).toFixed(1)} percentage points `
      + `${difference >= 0 ? "above" : "below"} the national estimate (${pct(national.turnout_pct)}). `
      + "Not a test of statistical significance."));
  }
  if (state.countyResults?.year === year && state.countyResults.coverage[stateCode()]) {
    const button = html("button", "selection-link", "Show county election results");
    button.id = "show-county-candidate-results"; button.type = "button";
    button.addEventListener("click", () => {
      $("map-level").value = "county"; $("map-color").value = "margin";
      render();
      const item = state.map?.stateItems?.get(stateCode());
      if (item) fit(item.bounds);
    });
    panel.append(button);
  }
  panel.append(html("h4", "", provisional ? "Historical CPS turnout · through 2024" : `${state.selectedState} over time`));
  const chart = html("div", "state-chart"); chart.id = "state-history";
  panel.append(chart);
  if (rows.length) {
    seriesChart(chart, rows, { width: 300, height: 210, compact: true });
  } else chart.append(html("p", "selection-note", "No historical series for this population."));
  panel.append(html("p", "selection-note", basis === "cvap"
    ? "CPS survey estimates. The dashed 1992–1994 connector marks a citizenship-measurement change, not missing data."
    : "CPS survey estimates. Dashed connectors mark definition changes; missing elections remain gaps."));
  const election = marginRow("state", stateCode());
  if (election) panel.append(html("h4", "", `${election.office} · map context`),
    html("p", "selection-note", `${marginLabel(election)} · ${fmt(election.contest_votes)} contest votes. `
      + (election.office === "U.S. House" ? "State aggregate of district party votes, not a statewide winner or seat margin. " : "")
      + "Candidate votes are not ballots cast or a participation rate."), sourceLink(election));
  const detail = html("div", "substate-detail"); detail.id = "substate-detail"; panel.append(detail);
  const local = html("div", "substate-detail"); local.id = "local-navigation"; panel.append(local);
  const localSelection = html("div", "substate-detail"); localSelection.id = "local-detail"; panel.append(localSelection);
  if (!provisional) localNavigation(local);
  methodsView();
  if (state.selectedState === "North Carolina") {
    const button = html("button", "selection-link", "Explore North Carolina precincts");
    button.type = "button";
    button.addEventListener("click", () => showView("precincts"));
    panel.append(button);
  }
  for (const path of state.mapPaths) path.classList.toggle("selected", path.dataset.state === state.selectedState);
  const outline = state.map?.stateSelectionOutline;
  if (outline) {
    outline.setAttribute("d", state.map.statePaths.get(stateCode())?.getAttribute("d") || "");
    outline.dataset.selectedState = state.selectedState;
  }
}
function statesView() {
  const year = Number($("year").value), basis = $("basis").value;
  const provisional = isProvisional();
  const rows = provisional ? stateParticipationRows() : state.states.filter(row => row.year === year && row.denominator === basis);
  const byName = new Map(rows.map(row => [row.state, row]));
  const rates = provisional && rows.some(row => row.turnout_pct != null);
  if (ufMode()) {
    const national = state.ufTurnout.find(row => row.state_code === "US");
    const population = ufBasis() === "vep" ? "voting-eligible population" : "all voting-age residents";
    header("2026 midterm election · UF turnout estimates", "Participation across the United States",
      `${participationRate({ uf_source: true, turnout_pct: national?.[ufBasis() + "_rate"] })} nationally. `
        + `Estimated ballots / ${population}. Select a state for turnout and separate official observations.`,
      "UF Election Lab source-labeled estimates, not final official counts or Census CPS survey rates. "
        + "State estimates are never assigned to counties or precincts. County colors, where available, use their own administrative counts and denominator.");
    ramp();
    note(state.currentError);
  } else if (provisional) {
    header("2026 midterm election · reported observations", "Participation across the United States",
      `${modeLabels[$("mode").value]}. ${rates ? "Colors show reported ballots / each state's source-defined electorate; gray means no rate."
        : "Select a state to see its reported count and source date."}`,
      "Provisional observations, not final turnout. Electorate definitions and source dates vary by state; these are not UF population or CPS survey rates. Alaska and Hawaii are separate-scale insets.");
    if (rates) ramp();
    else legend([["Count reported", "#718ba5"], ["Not yet available", "#edf0f3"]]);
    note(state.currentError);
  } else {
    header(`${year} ${typeFor(year)} election · Census survey estimates`, "Participation across the United States",
    `Share of ${basis === "cvap" ? "adult citizens" : "all adult residents"} who reported voting. Select a state to see its history.`,
    "Survey estimates, not precinct results. Sampling uncertainty can be substantial. Gray means no estimate. Alaska and Hawaii are separate-scale insets.");
    note(unique(rows.flatMap(row => row.warnings)).join(" ")
      || (!rows.length ? "No state estimates for this year and population." : ""));
    ramp();
  }
  $("coverage-note").textContent = provisional && state.current
    ? `${state.current.coverage.filter(row => row.status !== "no_data").length} jurisdictions have a saved observation; `
      + `${currentOfficialRows().length} state-office full-election feeds. Available observations show one feed per state, preferring official administrative participation, then in-person early, then returned mail; modes are never added.`
    : "State histories use CPS survey estimates. Zoom for available local administrative participation; reporting units are not uniformly precincts. Precinct-specific coverage remains explicitly identified.";
  if (provisional && state.current) {
    const withData = new Set([...currentOfficialRows(), ...state.current.early_voting].map(row => row.state_code)).size;
    $("coverage-note").textContent = $("coverage-note").textContent.replace(/^\d+ jurisdictions/, `${withData} jurisdictions`);
  }
  if (ufMode()) $("coverage-note").textContent =
    `${rows.filter(row => row.turnout_pct != null).length} state / D.C. turnout rates plus a separate national estimate. `
    + "UF VEP and VAP are distinct population denominators, not registered voters. "
    + "Use the 2026 measure selector for official full-election counts or separate early/mail observations. "
    + "County participation is available through the selected state's county button where verified; demographic turnout rates remain unavailable.";
  if (provisional && $("mode").value === "official") {
    $("coverage-note").textContent = `${rows.length} jurisdictions have official full-election observations; `
      + `${rows.filter(row => row.turnout_pct != null).length} have a source-defined participation rate. `
      + "Gray means no comparable rate in this partial administrative view, not zero participation.";
  }
  if ($("map-color").value === "margin") {
    const office = year % 4 === 0 ? "President" : "U.S. House";
    const count = state.margins.filter(row => row.year === year && row.level === "state" && row.office === office).length;
    header(`${year} ${typeFor(year)} election · ${provisional ? "unofficial reported results" : "election-result context"}`,
      "Election results across the United States",
      `Blue: Democratic advantage. Red: Republican advantage. ${office === "U.S. House" ? "State totals aggregate U.S. House district votes." : "Presidential party-vote margins."}`,
      "Whole-state result colors remain wherever verified local candidate returns are missing. Colors do not represent participation rates or House seat margins. Alaska and Hawaii are separate-scale insets.");
    $("coverage-note").textContent = `${count} states with ${year} ${office} results. `
      + (provisional && state.results ? `All ${state.results.districts} voting House districts; civicAPI source updated ${state.results.source_update_label}. DC has no voting House district in this source. ` : "")
      + "Precinct participation counts remain available separately; they are never substituted for candidate returns.";
    marginLegend(office === "U.S. House" ? "U.S. House aggregate" : office);
    if (state.resultsError && provisional) note(state.resultsError);
  }
  if (state.contextError) note(state.contextError);
  stateMap(byName, provisional);
  stateDetail();
  setTable(rows.sort((a, b) => a.state.localeCompare(b.state)), provisional
    ? [["state", "State"], ["turnout_pct", "Turnout / source denominator"], ["denominator_basis", "Denominator definition"],
      ["denominator", "Denominator"], ["observation_type", "Observation type"], ["ballots", ufMode() ? "Source-estimated ballots" : "Participation reported"], ["source_date", "Source date"],
      ["source_update_label", "Source update"], ["status", "Status"], ["quality", "Notes"]]
    : [["state", "State"], ["year", "Year"], ["turnout_pct", "Turnout"], ["denominator", "Population"], ["warnings", "Notes"]]);
}
function rings(geometry) {
  return geometry.type === "MultiPolygon" ? geometry.coordinates.flat() : geometry.coordinates;
}
function boundsFor(points) {
  return points.reduce(([x0, y0, x1, y1], [x, y]) =>
    [Math.min(x0, x), Math.min(y0, y), Math.max(x1, x), Math.max(y1, y)], [Infinity, Infinity, -Infinity, -Infinity]);
}
function combinedBounds(items) {
  return boundsFor(items.flatMap(item => [[item.bounds[0], item.bounds[1]], [item.bounds[2], item.bounds[3]]]));
}
function conicProjection(meridian, lower, upper) {
  const radians = Math.PI / 180;
  const n = (Math.sin(lower * radians) + Math.sin(upper * radians)) / 2;
  const c = Math.cos(lower * radians) ** 2 + 2 * n * Math.sin(lower * radians);
  return ([lon, lat]) => {
    const theta = n * (((lon - meridian + 540) % 360) - 180) * radians;
    const rho = Math.sqrt(c - 2 * n * Math.sin(lat * radians)) / n;
    return [rho * Math.sin(theta), rho * Math.cos(theta)];
  };
}
function projectFeatures(features, project, [left, top, width, height]) {
  const projected = features.map(feature => ({ feature, rings: rings(feature.geometry).map(ring => ring.map(project)) }));
  const [x0, y0, x1, y1] = boundsFor(projected.flatMap(item => item.rings.flat()));
  const scale = Math.min(width / (x1 - x0), height / (y1 - y0));
  const ox = left + (width - (x1 - x0) * scale) / 2, oy = top + (height - (y1 - y0) * scale) / 2;
  return projected.map(item => {
    const transformed = item.rings.map(ring => ring.map(([x, y]) => [ox + (x - x0) * scale, oy + (y - y0) * scale]));
    const point = coordinate => {
      const [x, y] = project(coordinate);
      return [ox + (x - x0) * scale, oy + (y - y0) * scale];
    };
    return { feature: item.feature, point, bounds: boundsFor(transformed.flat()),
      d: transformed.map(ring => ring.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`).join("") + "Z").join("") };
  });
}
function setViewport(view) {
  if (!state.map) return;
  const [fullWidth, fullHeight] = state.map.full;
  const width = Math.max(fullWidth / MAX_MAP_ZOOM, Math.min(fullWidth, view[2]));
  const height = width * fullHeight / fullWidth;
  const x = Math.max(0, Math.min(fullWidth - width, view[0]));
  const y = Math.max(0, Math.min(fullHeight - height, view[1]));
  state.viewport = [x, y, width, height];
  state.map.svg.setAttribute("viewBox", state.viewport.join(" "));
  state.map.svg.dataset.zoom = String(fullWidth / width);
  $("map-zoom-out").disabled = width >= fullWidth;
  $("map-zoom-in").disabled = width <= fullWidth / MAX_MAP_ZOOM;
  const screenWidth = state.map.svg.getBoundingClientRect().width || fullWidth;
  for (const label of state.map.svg.querySelectorAll(".map-label")) {
    const size = label.classList.contains("precinct-label") ? 12 : Math.min(12, Math.max(8, screenWidth / 70));
    label.style.fontSize = `${size * width / screenWidth}px`;
    label.style.strokeWidth = `${(label.classList.contains("precinct-label") ? 1 : 0) * width / screenWidth}px`;
  }
  state.map.svg.classList.toggle("compact-map", screenWidth < 500 && fullWidth / width < 2);
  if (state.view === "states" && state.map.stateItems) {
    clearTimeout(state.drillTimer);
    state.drillTimer = setTimeout(loadGeography, 80);
  }
}
function zoom(factor, client) {
  if (!state.map) return;
  const [x, y, width, height] = state.viewport;
  const rect = state.map.svg.getBoundingClientRect();
  const fx = client ? (client.clientX - rect.left) / rect.width : .5;
  const fy = client ? (client.clientY - rect.top) / rect.height : .5;
  const newWidth = Math.max(state.map.full[0] / MAX_MAP_ZOOM, Math.min(state.map.full[0], width / factor));
  const newHeight = newWidth * height / width;
  setViewport([x + fx * (width - newWidth), y + fy * (height - newHeight), newWidth, newHeight]);
}
function fit(bounds) {
  if (!state.map || !bounds?.every(Number.isFinite)) return;
  const [x0, y0, x1, y1] = bounds, ratio = state.map.full[0] / state.map.full[1];
  const width = Math.max(x1 - x0, (y1 - y0) * ratio) * 1.18;
  const w = Math.max(state.map.full[0] / MAX_MAP_ZOOM, Math.min(state.map.full[0], width));
  setViewport([(x0 + x1 - w) / 2, (y0 + y1 - w / ratio) / 2, w, w / ratio]);
}
function createMap(width, height, label) {
  const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, class: "turnout-map", role: "group",
    "aria-label": label, tabindex: "0" });
  state.map = { svg, full: [width, height], dragged: false, view: state.view };
  state.mapPaths = [];
  $("visualization").replaceChildren(svg);
  $("map-tools").hidden = false; $("map-help").hidden = false;
  let drag = null, pinch = null, clickViewport = null;
  const pointers = new Map(), map = state.map;
  const gesture = () => {
    const [a, b] = [...pointers.values()];
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2,
      distance: Math.hypot(a.x - b.x, a.y - b.y) };
  };
  svg.addEventListener("pointerdown", event => {
    if (event.button !== 0 || state.map !== map) return;
    if (!pointers.size) map.dragged = false;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    drag = { id: event.pointerId, x: event.clientX, y: event.clientY, view: [...state.viewport] };
    event.target.setPointerCapture(event.pointerId);
    if (pointers.size === 2) {
      const current = gesture(), rect = svg.getBoundingClientRect();
      const [x, y, w, h] = state.viewport;
      pinch = { distance: Math.max(1, current.distance), width: w,
        x: x + (current.x - rect.left) / rect.width * w,
        y: y + (current.y - rect.top) / rect.height * h };
      drag = null; map.dragged = true;
    }
    $("tooltip").hidden = true;
  });
  svg.addEventListener("pointermove", event => {
    if (state.map !== map || !pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pinch && pointers.size === 2) {
      const current = gesture(), rect = svg.getBoundingClientRect();
      const width = Math.max(map.full[0] / MAX_MAP_ZOOM,
        Math.min(map.full[0], pinch.width * pinch.distance / Math.max(1, current.distance)));
      const height = width * map.full[1] / map.full[0];
      setViewport([pinch.x - (current.x - rect.left) / rect.width * width,
        pinch.y - (current.y - rect.top) / rect.height * height, width, height]);
      $("tooltip").hidden = true;
      return;
    }
    if (!drag || drag.id !== event.pointerId) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (Math.hypot(dx, dy) > 4) state.map.dragged = true;
    if (!state.map.dragged) return;
    $("tooltip").hidden = true;
    const rect = svg.getBoundingClientRect();
    setViewport([drag.view[0] - dx / rect.width * drag.view[2],
      drag.view[1] - dy / rect.height * drag.view[3], drag.view[2], drag.view[3]]);
  });
  const stop = event => {
    if (!pointers.delete(event.pointerId)) return;
    pinch = null; drag = null;
    if (pointers.size === 1) {
      const [id, point] = [...pointers.entries()][0];
      drag = { id, ...point, view: [...state.viewport] };
    }
  };
  svg.addEventListener("pointerup", stop);
  svg.addEventListener("pointercancel", stop);
  svg.addEventListener("lostpointercapture", stop);
  svg.addEventListener("click", event => {
    if (event.detail === 1) clickViewport = [...state.viewport];
  }, true);
  svg.addEventListener("dblclick", event => {
    event.preventDefault();
    const fitted = clickViewport?.some((value, i) => value !== state.viewport[i]);
    zoom(2, fitted ? null : event);
  });
  svg.addEventListener("wheel", event => {
    event.preventDefault();
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? svg.getBoundingClientRect().height : 1;
    zoom(Math.exp(Math.max(-.7, Math.min(.7, -event.deltaY * unit * .002))), event);
  }, { passive: false });
  svg.addEventListener("keydown", event => {
    if (["+", "=", "-", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home"].includes(event.key)) {
      event.preventDefault();
      if (event.key === "+" || event.key === "=") zoom(2);
      else if (event.key === "-") zoom(.5);
      else if (event.key === "Home") resetMap();
      else {
        const [x, y, w, h] = state.viewport;
        setViewport([x + (event.key === "ArrowRight" ? .15 : event.key === "ArrowLeft" ? -.15 : 0) * w,
          y + (event.key === "ArrowDown" ? .15 : event.key === "ArrowUp" ? -.15 : 0) * h, w, h]);
      }
    }
  });
  setViewport([0, 0, width, height]);
  return svg;
}
function featurePath(item, value, label, action, attrs = {}) {
  const path = svgNode("path", { d: item.d, fill: fill(value), class: "map-feature", "fill-rule": "evenodd",
    role: "button", "aria-label": label, ...attrs });
  bindTooltip(path, label);
  path.addEventListener("click", event => {
    event.stopPropagation();
    if (!state.map.dragged && event.detail < 2) action();
  });
  path.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); action(); }
  });
  if (!attrs["data-level"]) state.mapPaths.push(path);
  return path;
}
function stateMap(byName, provisional = false) {
  const previousViewport = state.map?.view === "states" ? state.viewport : null;
  const svg = createMap(1000, 610, `United States ${$("map-color").value === "margin" ? "red and blue election-result" : "participation"} map. Select a state for its results and participation history.`);
  state.map.stateHeading = ["subtitle", "title", "measure", "caption"].map(id => $(id).textContent);
  state.map.stateCoverage = $("coverage-note").textContent;
  state.map.stateRateMap = provisional && [...byName.values()].some(row => row.turnout_pct != null);
  state.drillKey = ""; ++state.drillToken;
  const items = new Map(), paths = new Map();
  const labels = [], callouts = [];
  const external = ["VT", "NH", "MA", "RI", "CT", "NJ", "DE", "MD", "DC"];
  for (const [codes, projection, region] of [
    [null, albers, [40, 20, 840, 480]],
    [["AK"], alaska, [60, 440, 175, 125]],
    [["HI"], hawaii, [275, 495, 105, 65]],
  ]) {
    const features = state.geometry.features.filter(feature => codes
      ? codes.includes(feature.properties.STUSAB) : !["AK", "HI", "PR", "GU", "VI", "MP", "AS"].includes(feature.properties.STUSAB));
    for (const item of projectFeatures(features, projection, region)) {
      const { NAME: name, STUSAB: abbreviation } = item.feature.properties;
      const row = byName.get(name);
      const select = () => {
        if (state.view === "precincts") {
          if (![...$("precinct-state-select").options].some(option => option.value === name)) {
            note(`No loaded precinct map source for ${name}. Other years' or county boundaries are not substituted.`);
            return;
          }
          state.selectedState = name;
          $("precinct-state-select").value = name;
          state.county = ""; state.precinct = "";
          configure({ ...viewSelection(), "precinct-state-select": name });
          render();
          return;
        }
        state.selectedState = name; $("state-select").value = name; stateDetail(); syncURL(); fit(item.bounds);
      };
      const election = marginRow("state", abbreviation);
      const partisan = $("map-color").value === "margin";
      const precinctColors = $("map-level").value === "precinct" && !partisan && !provisional;
      const path = featurePath(item, row?.turnout_pct,
        `${name} · ${$("year").value}\n${partisan ? `${election?.office || "Election"} · ${marginLabel(election)} · ${fmt(election?.contest_votes)} contest votes\nWhole-state result color; not a precinct result or participation rate`
          : provisional ? `${participationRate(row)}${row?.uf_source ? ` ${ufBasis().toUpperCase()} turnout · UF ${row.source_status}`
            : row?.turnout_pct != null ? " / source-defined electorate" : ""}\n${fmt(row?.ballots)} ballots · ${row?.uf_source ? "source estimate" : row ? modeFor(row) : "not reported"} · provisional`
            : `${pct(row?.turnout_pct)} reported voting`}`,
        select, { "data-state": name, "data-color-level": partisan ? "state" : precinctColors ? "none" : "state",
          "data-rate": row?.turnout_pct ?? "", "data-rate-source": row?.uf_source ? "uf_estimate"
            : provisional ? "administrative" : "cps_survey",
          tabindex: "0",
          ...(partisan ? { fill: marginFill(election?.margin_pp) }
            : provisional ? { fill: row?.turnout_pct != null ? fill(row.turnout_pct)
              : !state.map.stateRateMap && row ? "#718ba5" : "#edf0f3" } : {}),
          ...(precinctColors ? { fill: "#d6d3cb" } : {}) });
      items.set(abbreviation, item); paths.set(abbreviation, path);
      svg.append(path);
      const [x, y] = item.point(labelLocations[abbreviation]);
      if (external.includes(abbreviation)) callouts.push({ x, y, abbreviation, name, select });
      else labels.push(svgNode("text", { x, y, dy: ".35em", "text-anchor": "middle",
        class: "map-label state-label", "data-label-state": name,
        style: `fill:${precinctColors ? "#17212d" : partisan ? Math.abs(election?.margin_pp ?? 0) >= 20 ? "#fff" : "#17212d"
          : row?.turnout_pct >= 62 ? "#fff" : "#17212d"}` }, abbreviation));
    }
    const detail = svgNode("g", { class: "geographic-detail" });
    svg.append(detail);
    Object.assign(state.map, { stateItems: items, statePaths: paths, detail });
  }
  for (const label of labels) svg.append(label);
  callouts.sort((a, b) => a.y - b.y);
  let previousY = 120;
  for (const item of callouts) {
    const y = Math.max(previousY + 23, item.y);
    previousY = y;
    svg.append(svgNode("path", { d: `M${item.x},${item.y}L900,${y}H918`, class: "map-callout-line map-callout" }));
    const label = svgNode("text", { x: 926, y, dy: ".35em", class: "map-label map-callout external-label",
      "data-label-state": item.name, role: "button", tabindex: "0", "aria-label": `Select ${item.name}` }, item.abbreviation);
    label.addEventListener("click", () => { if (!state.map.dragged) item.select(); });
    label.addEventListener("keydown", event => {
      if (["Enter", " "].includes(event.key)) { event.preventDefault(); item.select(); }
    });
    svg.append(label);
  }
  svg.append(svgNode("text", { x: 60, y: 590, class: "map-label inset-caption" }, "Alaska"),
    svgNode("text", { x: 275, y: 590, class: "map-label inset-caption" }, "Hawaii · insets not to scale"));
  state.map.stateSelectionOutline = svgNode("path", {
    class: "state-selection-outline", fill: "none", stroke: "#172e48", "stroke-width": 2,
    "stroke-linejoin": "round", "vector-effect": "non-scaling-stroke",
    "pointer-events": "none", "aria-hidden": "true",
  });
  svg.append(state.map.stateSelectionOutline);
  setViewport(previousViewport || state.viewport);
}
function projectInside(feature, point) {
    const projected = rings(feature.geometry).map(ring => ring.map(point));
    return { feature, bounds: boundsFor(projected.flat()),
      d: projected.map(ring => ring.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(3)},${y.toFixed(3)}`).join("") + "Z").join("") };
  }
  async function loadGeography() {
    const map = state.map, pending = updateGeography(), token = state.drillToken;
    try {
      await pending;
    } catch (error) {
      if (state.map !== map || state.drillToken !== token) return;
      state.drillKey = "";
      $("geography-note").hidden = false;
      $("geography-note").textContent = `Geographic detail could not be loaded: ${error.message}. State context is retained; no results have been inferred.`;
      const panel = $("substate-detail");
      if (panel) {
        const retry = html("button", "selection-link", "Retry geographic detail");
        retry.type = "button"; retry.addEventListener("click", loadGeography);
        panel.replaceChildren(html("p", "selection-note", $("geography-note").textContent), retry);
      }
    }
  }
  async function updateGeography() {
    const map = state.map;
    if (state.view !== "states" || !map?.stateItems || (!state.context && !state.local && !state.precinctResults)) return;
    const zoomLevel = map.full[0] / state.viewport[2], year = Number($("year").value);
    const nationalCounties = $("map-color").value === "margin" && $("map-level").value === "county"
      && state.countyResults?.year === year && state.countyOverview;
    if (map.countyOverview) map.countyOverview.style.display = nationalCounties ? "" : "none";
    if (nationalCounties) drawNationalCountyResults(map, year);
    const center = new DOMPoint(state.viewport[0] + state.viewport[2] / 2, state.viewport[1] + state.viewport[3] / 2);
    const currentBounds = map.stateItems.get(stateCode())?.bounds;
    const [vx, vy, vw, vh] = state.viewport;
    const selectedVisible = currentBounds && Math.max(0, Math.min(vx + vw, currentBounds[2]) - Math.max(vx, currentBounds[0]))
      * Math.max(0, Math.min(vy + vh, currentBounds[3]) - Math.max(vy, currentBounds[1])) > .05 * vw * vh;
    if (zoomLevel >= 2.3 && !selectedVisible) {
      const hit = [...map.statePaths.entries()].find(([, path]) => path.isPointInFill(center));
      if (hit && map.stateItems.get(hit[0]).feature.properties.NAME !== state.selectedState) {
        state.selectedState = map.stateItems.get(hit[0]).feature.properties.NAME;
        $("state-select").value = state.selectedState; stateDetail(); syncURL();
      }
    }
    let code = stateCode();
    let level = $("map-level").value;
    const countyCoverage = state.countyResults?.year === year && state.countyResults.coverage[code];
    if (level === "precinct" && $("map-color").value === "margin"
      && !state.precinctResults?.coverage[year]?.[code] && countyCoverage) level = "county";
    if (level === "auto" && $("map-color").value === "margin"
      && zoomLevel >= 2.3 && state.precinctResults?.coverage[year]?.[code]) level = "precinct";
    if (level === "auto" && $("map-color").value !== "margin" && zoomLevel >= (code === "MN" ? 8 : 2.3)
      && matchedPrecinctParticipationMode() && matchedPrecinctParticipationCoverage(code, year)) level = "precinct";
    if (level === "auto" && year === 2026 && code === "MI" && zoomLevel >= 2.3
      && $("map-color").value !== "margin" && matchedPrecinctParticipationMode()
      && state.currentPrecincts?.states[code]) level = "precinct";
    if (level === "auto") level = zoomLevel >= 8 && (code === "NC" && state.audits.some(row => row.year === year)
      || year === 2026 && $("map-color").value !== "margin" && state.currentPrecincts?.states[code]
        && (ufMode() || ["available", "official"].includes($("mode").value)))
      ? "precinct" : state.local?.years.includes(year) ? "county"
        : state.margins.some(row => row.year === year && row.state_code === code && row.level === "county")
        ? "county" : state.context?.district_result_years.includes(year) ? "district" : "county";
    if (level === "precinct" && zoomLevel < 2.3 && $("map-color").value !== "margin") {
      if (year !== 2026 && state.audits.some(row => row.year === year)) code = "NC";
    }
    const selected = map.stateItems.get(code);
    const key = `${year}|${code}|${level}|${$("map-color").value}|${$("mode").value}|${zoomLevel >= 2.3}`;
    if (key === state.drillKey) return;
    state.drillKey = key;
    const token = ++state.drillToken;
    if (map.precinctLayer || map.localLayer || map.countyLayer) {
      if ((map.precinctLayer || map.localLayer || map.candidateCountFallback) && map.stateTable)
        setTable(map.stateTable.rows, map.stateTable.columns);
      map.precinctLayer = false;
      map.localLayer = false;
      map.countyLayer = false;
      map.candidateCountFallback = false;
      header(...map.stateHeading);
      $("coverage-note").textContent = map.stateCoverage;
      stateDetail();
    }
    map.detail.replaceChildren(); $("substate-detail")?.replaceChildren();
    $("geography-note").hidden = !nationalCounties && zoomLevel < 2.3 && level !== "precinct";
    for (const label of map.svg.querySelectorAll(".map-label, .map-callout-line")) label.style.display = zoomLevel >= 2.3 ? "none" : "";
    if (zoomLevel < 2.3 && level !== "precinct") {
      if (nationalCounties) {
        header(`${year} midterm election · county candidate returns`,
          "County election results across the United States",
          "Red / blue uses each county's own House candidate votes, not participation.",
          "County colors are visible without zooming. State fallback only where county results are missing; zero-vote counties have no margin.");
        marginLegend("U.S. House aggregate");
        return;
      }
      if ($("map-color").value === "margin") marginLegend(year % 4 === 0 ? "President" : "U.S. House aggregate");
      else if (isProvisional() && !map.stateRateMap) legend([["Count reported", "#718ba5"], ["Not yet available", "#edf0f3"]]);
      else ramp();
      return;
    }
    if (!selected) return;
    $("geography-note").hidden = false;
    $("geography-note").textContent = `Loading ${year} ${level} detail for ${state.selectedState}…`;
    const unavailable = text => {
      $("geography-note").textContent = text;
      if ($("map-color").value === "margin") marginLegend(year % 4 === 0 ? "President" : "U.S. House aggregate");
      else if (isProvisional() && map.stateRateMap) ramp();
      else if (level === "precinct") legend([["No verified precinct participation", "#d6d3cb"]]);
    };
    if (level === "precinct" && $("map-color").value === "margin"
      && state.precinctResults?.coverage[year]?.[code])
      return drawPrecinctResults(map, selected, code, year, token);
    if (level === "precinct" && $("map-color").value !== "margin"
      && matchedPrecinctParticipationMode() && matchedPrecinctParticipationCoverage(code, year))
      return drawMatchedPrecinctParticipation(map, selected, code, year, token);
    if (level === "county" && $("map-color").value === "margin" && countyCoverage)
      return drawCountyResults(map, selected, code, year, token);
    if ($("map-color").value === "margin"
      && !state.margins.some(row => row.year === year && row.state_code === code && row.level === level))
      return unavailable(`No verified ${year} ${level} candidate-return join for ${state.selectedState}. `
        + "Whole-state red/blue election-result colors remain; participation rates are not used as election results.");
    if (year === 2026 && level === "precinct"
      && !state.currentPrecincts?.states[code]
      && state.current?.local_audit?.some(row => row.state_code === code && row.counties > 0)
      && (ufMode() || ["available", "official"].includes($("mode").value))) {
      if (zoomLevel < 2.3) {
        $("geography-note").textContent = `No verified 2026 precinct participation geography for ${state.selectedState}. `
          + "State-level turnout remains visible; use the county participation button or select the state to see verified county observations.";
        if (map.stateRateMap) ramp();
        return;
      }
      return drawCurrentGeography(map, selected, code, token);
    }
    if (year === 2026 && level === "precinct")
      return drawCurrentPrecinctGeography(map, selected, code, token);
    if (year === 2026 && level === "county" && code === "RI" && $("map-color").value !== "margin"
      && state.additionalCoverage.some(row => row.state_code === code) && matchedPrecinctParticipationMode())
      return drawCurrentMunicipalityGeography(map, selected, code, token);
    if (year === 2026 && level === "county" && $("map-color").value !== "margin"
      && (state.current?.local_file || state.reviewedCounties.some(row => row.state_code === code)
        || state.additionalCoverage.some(row => row.state_code === code))
      && (ufMode() || ["available", "official"].includes($("mode").value)
        || hasCountySourceMode(code, $("mode").value)))
      return drawCurrentGeography(map, selected, code, token);
    if (level === "county" && state.local?.years.includes(year) && $("map-color").value !== "margin")
      return drawLocalGeography(map, selected, code, year, token);
    if (!state.context) return unavailable("Election-context boundaries could not be loaded. Local reporting-unit histories remain available in the sidebar.");
    if (level === "precinct" && (code !== "NC" || !state.audits.some(row => row.year === year)))
      return unavailable(`No verified ${year} precinct boundaries and participation inputs for ${state.selectedState}. Other years' shapes are not substituted.`);
    if (level === "district" && !state.context.district_result_years.includes(year))
      return unavailable(`No verified ${year} congressional-district boundary/result pair. 119th-Congress boundaries are used only for the 2024 election, not substituted for 2026 redistricting.`);
    if (level === "county" && ![2024, 2026].includes(year))
      return unavailable(`No verified ${year} county boundary/result snapshot. The ${year} state participation estimate remains available; newer county shapes are not presented as historical results.`);
    let features;
    if (level === "precinct") {
      state.selectedState = "North Carolina"; $("state-select").value = state.selectedState; syncURL();
      if (!state.shapes.has(year)) state.shapes.set(year, await get(`nc/geometry-${year}.geojson`));
      if (!state.nc.has(year)) state.nc.set(year, await get(`nc/${year}.json`));
      features = state.shapes.get(year).features;
    } else {
      const path = state.context.geometry[level]?.[code];
      if (!path) return unavailable(`No verified ${level} geometry for ${state.selectedState}.`);
      if (!state.subshapes.has(path)) state.subshapes.set(path, await contextGet(path));
      features = state.subshapes.get(path).features;
    }
    if (token !== state.drillToken || state.map !== map) return;
    const returns = new Map(state.margins.filter(row => row.year === year && row.level === level && row.state_code === code)
      .map(row => [row.geography, row]));
    const participation = level === "precinct" ? new Map(state.nc.get(year).records.filter(row => row.dimension === "overall")
      .map(row => [keyFor(row), row])) : new Map();
    const partisan = $("map-color").value === "margin" && level !== "precinct";
    let observed = 0;
    for (const feature of features) {
      const p = feature.properties, id = level === "precinct" ? keyFor(p) : p.key;
      const election = returns.get(id), row = participation.get(id);
      if (partisan && election?.margin_pp == null) continue;
      const rate = row && row.registered >= 25 ? row.turnout_pct : null;
      const item = projectInside(feature, selected.point);
      const name = level === "precinct" ? `${titleCase(p.county)} · precinct ${p.precinct}` : p.name;
      if (partisan ? election?.margin_pp != null : rate != null) observed++;
      const description = level === "precinct" ? `${pct(rate)} · ${fmt(row?.participants)} participants / ${fmt(row?.registered)} registered`
        : election ? `${election.office} · ${marginLabel(election)} · ${fmt(election.contest_votes)} contest votes`
          : "No matched election return; boundary context only";
      const path = featurePath(item, rate, `${name} · ${year}\n${description}`, () => {
        if (level === "precinct") {
          state.precinct = id;
          state.county = p.county;
          state.subSelection = { item: p, row };
          precinctDetail(state.subSelection);
          const button = html("button", "selection-link", "Open precinct participation");
          button.type = "button";
          button.addEventListener("click", () => {
            state.county = p.county; state.precinct = id; $("dimension").value = "overall"; showView("precincts");
          });
          $("selection-panel").append(button);
        } else {
          const panel = $("substate-detail");
          panel.replaceChildren(html("h4", "", name), html("p", "selection-note", description));
          if (election) panel.append(sourceLink(election),
            html("p", "selection-note", "Party-vote margin, not turnout or necessarily the winner's margin; ranked-choice and independent candidacies can differ."));
        }
        for (const other of map.detail.querySelectorAll(".selected")) other.classList.remove("selected");
        path.classList.add("selected");
        fit(item.bounds);
      }, { class: "map-feature substate-feature", "data-geography": id, "data-level": level,
        tabindex: "-1", fill: partisan ? marginFill(election?.margin_pp) : fill(rate) });
      map.detail.append(path);
    }
    if (level === "precinct") {
      map.precinctLayer = true;
      header(`${year} ${typeFor(year)} election · North Carolina precinct records`,
        "Precinct participation in North Carolina",
        "Participants recorded in voter history / election-time registered voters. Select a precinct for its history.",
        "Registered-voter participation, not CPS citizen/resident turnout. Gray: missing or inconsistent rates, or fewer than 25 registrations.");
      $("coverage-note").textContent = "Verified precinct histories cover North Carolina, 2002–2024. County + precinct IDs are matched, not fixed boundaries or the same electorate.";
      const selectedItem = features.find(feature => keyFor(feature.properties) === state.precinct)?.properties;
      state.subSelection = selectedItem ? { item: selectedItem, row: participation.get(state.precinct) } : null;
      precinctDetail(state.subSelection);
    }
    if (level === "precinct") ramp();
    else if (partisan) marginLegend(level === "district" ? "U.S. House" : year % 4 === 0 ? "President" : "U.S. House aggregate");
    else legend([["Gray: no matched local participation rate", "#d6d3cb"]]);
    $("geography-note").textContent = `${selected.feature.properties.NAME} · ${fmt(features.length)} ${level === "district" ? "congressional districts" : level === "precinct" ? "precinct shapes" : "counties / equivalents"}`
      + ` · ${fmt(observed)} with ${partisan ? "party-margin returns" : "participation rates"}. `
      + (level === "precinct" ? "Colors now show participants / registered voters; fewer than 25 registrations are withheld. "
        : level === "district" ? "2024 election · 119th Congress. "
          : "2024 Census boundaries" + (year === 2026 ? " shown as geographic context, not certified 2026 election boundaries. " : ". "))
      + (partisan ? "Party returns are separate from participation. " : "")
      + (level === "precinct" ? "Select a precinct for its participation history."
        : code === "NC" && state.audits.some(row => row.year === year)
          ? "Keep zooming for precinct participation and histories."
          : "Click a shape for counts. Verified precinct participation is currently North Carolina only.");
  }
function resetMap() {
  if (!state.map) return;
  if (state.view === "precincts" && state.projected?.length) fit(combinedBounds(state.projected));
  else setViewport([0, 0, ...state.map.full]);
}
async function precinctHistory(container, item, dimension, group, minimum) {
  container.textContent = "Loading this precinct's participation history…";
  try {
    if (!state.precinctHistories.has(item.county)) {
      const response = await fetch(`/participation-precinct-history/nc/${encodeURIComponent(item.county)}.json`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.precinctHistories.set(item.county, await response.json());
    }
    if (!container.isConnected) return;
    const history = state.precinctHistories.get(item.county);
    const groupIndex = history.groups.findIndex(([d, g]) => d === dimension && g === group);
    const rows = (history.precincts[item.precinct] ?? []).filter(row => row[1] === groupIndex)
      .map(([year, , participants, registered, turnout, quality]) => ({
        year, participants, registered, turnout_pct: registered >= minimum ? turnout : null, quality,
        series: `${titleCase(item.county)} · precinct ${item.precinct}`,
      }));
    seriesChart(container, rows, { width: 300, height: 210, compact: true, dimension: "precinct" });
    container.querySelector("svg")?.setAttribute("aria-label", `${item.county} precinct ${item.precinct}: ${group} participation history`);
    const table = html("table", "precinct-history-table");
    const head = html("thead"), heading = html("tr");
    for (const label of ["Year", "Participants", "Registered", "Rate"]) heading.append(html("th", "", label));
    head.append(heading); table.append(head);
    const body = html("tbody");
    for (const row of [...rows].reverse()) {
      const tr = html("tr");
      for (const value of [String(row.year), fmt(row.participants), fmt(row.registered), pct(row.turnout_pct)])
        tr.append(html("td", "", value));
      tr.dataset.year = String(row.year);
      if (row.quality.length) tr.title = row.quality.join(" ");
      body.append(tr);
    }
    table.append(body);
    const detail = html("details");
    detail.append(html("summary", "", "Every observed year and count"), table);
    container.append(detail);
  } catch (error) {
    if (container.isConnected) container.replaceChildren(html("p", "selection-note",
      `Precinct history could not be loaded: ${error.message}. No values have been inferred.`));
  }
}
function precinctDetail(selection = null) {
  const panel = $("selection-panel"), year = Number($("year").value);
  const inStates = state.view === "states";
  const item = inStates ? selection?.item : state.precinct ? state.precinctItems.get(state.precinct) : null;
  panel.replaceChildren(html("p", "eyebrow", `${year} · ${typeFor(year)}`));
  if (!item) {
    panel.append(html("h3", "", state.county ? `${titleCase(state.county)} County` : "Inside North Carolina"),
      html("p", "selection-note", "Choose a county, search a precinct ID or name, or click a shape on the map."),
      html("h4", "", `${fmt(inStates ? state.map.detail.childElementCount : state.projected?.length ?? 0)} mapped shapes`),
      html("p", "selection-note", "Zoom with the controls, double-click, or use + / − with the map focused. Drag or use arrow keys to pan."),
      html("p", "selection-note", "This registered-voter participation history is North Carolina only. Use the state and layer controls for other loaded precinct result or participation sources."));
    return;
  }
  const row = inStates ? selection.row : state.precinctRows.get(state.precinct);
  const minimum = inStates ? 25 : Number($("minimum").value);
  const dimension = inStates ? "overall" : $("dimension").value, group = inStates ? "All" : $("group").value;
  const value = row && row.registered >= minimum ? row.turnout_pct : null;
  panel.append(html("h3", "", item.label || `Precinct ${item.precinct}`),
    html("p", "selection-note", `${titleCase(item.county)} County · precinct ${item.precinct || "unassigned"}`),
    html("p", `selection-rate${value == null ? " selection-unavailable" : ""}`, pct(value)),
    html("p", "selection-basis", `${group} · participants / registered voters`));
  const stats = html("dl", "selection-stats");
  for (const [name, number] of [["Participants", row?.participants], ["Registered voters", row?.registered]]) {
    const div = html("div"); div.append(html("dt", "", name), html("dd", "", fmt(number))); stats.append(div);
  }
  panel.append(stats);
  const reasons = row ? [...row.quality] : ["No matching observation for this group."];
  if (row && row.registered < minimum) reasons.push(`Fewer than ${minimum} registrations: rate withheld.`);
  if (!inStates && !state.projected.some(shape => keyFor(shape.feature.properties) === state.precinct))
    reasons.push("No matching election-year shape: this observation cannot be located on the map.");
  panel.append(html("p", "selection-note", reasons.length ? reasons.join(" ")
    : "A voter-history participation rate, not a share of all eligible residents."));
  panel.append(html("h4", "", `Precinct ${item.precinct} over time`));
  const history = html("div", "precinct-history"); history.id = "precinct-history";
  panel.append(history);
  panel.append(html("p", "selection-note",
    "Matched by official county + precinct ID, not a boundary crosswalk or the same electorate. Boundaries and IDs can change. Missing years remain gaps; small or inconsistent rates are withheld."));
  precinctHistory(history, item, dimension, group, minimum);
  const link = html("a", "selection-link", `Download all ${year} precinct observations`);
  link.href = `/voter-participation/data/nc/${year}.csv`; link.download = "";
  panel.append(link);
}
function selectPrecinct(key, zoomTo = true) {
  if (!state.precinctItems.has(key)) return;
  $("tooltip").hidden = true;
  state.precinct = key;
  const item = state.precinctItems.get(key);
  $("precinct-search").value = `${item.county} · ${item.precinct} · ${item.label || "Precinct"}`;
  for (const path of state.mapPaths) {
    const selected = path.dataset.key === key;
    path.classList.toggle("selected", selected);
    path.tabIndex = selected ? 0 : -1;
    path.setAttribute("aria-pressed", String(selected));
    if (selected) state.map.svg.append(path);
  }
  const shapes = state.projected.filter(item => keyFor(item.feature.properties) === key);
  state.map?.svg.querySelector(".precinct-label")?.remove();
  if (zoomTo && shapes.length) fit(combinedBounds(shapes));
  if (shapes.length && state.map) {
    const [x0, y0, x1, y1] = combinedBounds(shapes);
    const label = svgNode("text", { x: (x0 + x1) / 2, y: (y0 + y1) / 2,
      "text-anchor": "middle", class: "map-label precinct-label" }, item.precinct);
    state.map.svg.append(label);
    setViewport(state.viewport);
  }
  precinctDetail(); syncURL();
}
function precinctSourcePanel(year, layer) {
  const panel = $("selection-panel");
  panel.replaceChildren(html("p", "eyebrow", `${year} · ${typeFor(year)}`),
    html("h3", "", state.selectedState),
    html("p", "selection-note", layer === "results"
      ? "Mapped candidate returns. Red / blue is the reporting area's own candidate-vote margin, not turnout."
      : "Only source-qualified precinct or reporting-unit participation is shown. Gray can carry a direct count with no qualified rate."));
  const detail = html("div", "substate-detail"); detail.id = "substate-detail"; panel.append(detail);
}
async function loadReportingUnitSources() {
  try {
    const response = await fetch("/participation-reporting-units.json");
    if (!response.ok) throw new Error(`Source reporting units: HTTP ${response.status}`);
    const index = await response.json();
    if (index.year !== 2026 || Object.entries(index.sources).some(([code, source]) =>
      !["AK", "HI", "AZ", "AR", "WY"].includes(code) || !Number.isSafeInteger(source.rows) || source.rows <= 0
      || !/^[0-9a-f]{64}$/.test(source.sha256)))
      throw new Error("Unqualified reporting-unit coverage index");
    state.reportingUnitSources = index.sources;
  } catch (error) {
    state.reportingUnitError = error.message;
  }
}
async function drawReportingUnitCounts(map, code, year, token) {
  const source = state.reportingUnitSources[code];
  if (!state.reportingUnitData.has(code)) {
    const promise = (async () => {
      const response = await fetch(source.data_url);
      if (!response.ok) throw new Error(`Reporting-unit counts: HTTP ${response.status}`);
      const raw = await response.arrayBuffer();
      const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", raw))]
        .map(value => value.toString(16).padStart(2, "0")).join("");
      if (hash !== source.sha256) throw new Error("Reporting-unit source checksum disagrees");
      const rows = await countyJSON(new Response(raw));
      if (rows.length !== source.rows || new Set(rows.map(row => row.key)).size !== source.rows
        || rows.some(row => row.year !== year || row.state_code !== code
          || !row.precinct || !row.reporting_unit_kind || row.reported_pct !== null
          || (row.ballots !== null && (!Number.isSafeInteger(row.ballots) || row.ballots < 0))))
        throw new Error("Reporting-unit identities or native counts disagree with reviewed scope");
      return rows;
    })().catch(error => { state.reportingUnitData.delete(code); throw error; });
    state.reportingUnitData.set(code, promise);
  }
  const rows = await state.reportingUnitData.get(code);
  if (state.map !== map || state.drillToken !== token) return;
  setTable(rows, [["precinct", "Native reporting label"], ["reporting_unit_kind", "Source unit type"],
    ["source_split_label", "Native split"], ["ballots", "Reported ballots"],
    ["registered", "Native registrations (not a rate denominator)"], ["quality_flags", "Source qualifications"]]);
  header(`${year} midterms · source reporting units · geometry withheld`,
    `Reported participation counts in ${state.selectedState}`,
    "Source-unit ballot counts are available below. No precinct map or participation rate is inferred.",
    source.scope);
  legend([["State outline only · reporting-unit counts in table", "#edf0f3"]]);
  $("coverage-note").textContent = `${fmt(rows.length)} source reporting-unit observations. ${source.geometry_note}`;
  $("geography-note").hidden = false;
  $("geography-note").textContent = "No geographic overlays: the count table is available, but boundary joins remain withheld.";
  const panel = $("substate-detail");
  panel.replaceChildren(html("h4", "", "Choose a source reporting unit"),
    html("p", "selection-note", source.geometry_note));
  const label = html("label", "", "Reporting unit"), select = html("select");
  select.id = "source-reporting-unit-select";
  options(select, rows.map(row => [row.key,
    `${row.precinct} · ${row.reporting_unit_kind.replaceAll("_", " ")}${row.source_split_label ? " · " + row.source_split_label : ""}`]),
    state.precinct);
  label.append(select);
  const detail = html("div", "substate-detail"); detail.id = "source-reporting-unit-detail";
  const choose = () => {
    const row = rows.find(row => row.key === select.value);
    state.precinct = row.key;
    detail.replaceChildren(html("h4", "", row.precinct),
      html("p", "selection-rate", row.ballots === null ? "Not supplied" : fmt(row.ballots)),
      html("p", "selection-basis", row.ballots === null
        ? "Native ballot total is missing, not zero · no participation rate"
        : "Native reported ballots · no participation rate"),
      html("p", "selection-note", `Native registrations: ${fmt(row.registered)} · not a qualified rate denominator.`),
      html("p", "selection-note", row.basis),
      html("p", "selection-note", (row.quality_flags || []).join("; ")),
      html("p", "selection-note", `Source label: ${source.source_update_label}.`));
    syncURL();
  };
  select.addEventListener("change", choose);
  panel.append(label, detail);
  const table = html("button", "selection-link", `View all ${fmt(rows.length)} source observations`);
  table.type = "button";
  table.addEventListener("click", () => {
    $("table-panel").open = true;
    $("table-panel").scrollIntoView({ block: "start" });
    $("search").focus();
  });
  panel.append(table);
  const complete = html("a", "source-link", "Complete original sources and every reporting-unit query (ZIP)");
  complete.href = source.complete_download_url;
  const counts = html("a", "source-link", "All native reporting-unit observations (JSON · gzip)");
  counts.href = source.data_url;
  panel.append(complete, counts);
  choose();
}
function precinctCoverageNavigation(panel, year) {
  const codes = precinctCoverageCodes().filter(code => precinctParticipationCoverage(code, year));
  const details = html("details");
  details.append(html("summary", "", `Loaded ${year} precinct participation sources (${codes.length})`));
  if (!codes.length) details.append(html("p", "selection-note", "No qualified precinct participation map is loaded for this year."));
  for (const code of codes) {
    const button = html("button", "selection-link", stateName(code)
      + (precinctParticipationCoverage(code, year) === "reporting_units" ? " · counts only" : ""));
    button.type = "button"; button.dataset.precinctCoverageState = code;
    button.addEventListener("click", () => {
      state.selectedState = stateName(code); state.county = ""; state.precinct = "";
      configure({ year: String(year), "precinct-state-select": state.selectedState, "precinct-layer": "participation" });
      render();
    });
    details.append(button);
  }
  panel.append(details);
}
function unavailablePrecincts(year, code, layer) {
  const message = `No loaded ${year} precinct ${layer === "results" ? "candidate-result" : "participation"} map for ${state.selectedState}.`;
  header(`${year} · precinct coverage`, `Precinct data unavailable in ${state.selectedState}`,
    message, "The selected state and year are retained. Other years' precincts and county shapes are not substituted.");
  $("coverage-note").textContent = message + " This is a data gap, not zero participation.";
  $("geography-note").hidden = false;
  $("geography-note").textContent = "State outline only; no precinct values are drawn.";
  legend([["State outline · no precinct data", "#edf0f3"]]);
  const panel = $("substate-detail");
  panel.append(html("h4", "", message),
    html("p", "selection-note", "County data and statewide estimates are separate from precinct participation."));
  const estimate = year === 2026 && state.ufTurnout.find(row => row.state_code === code);
  if (estimate?.vep_rate != null) panel.append(html("p", "selection-basis",
    `${estimate.vep_rate.toFixed(2)}% statewide VEP turnout · UF estimate, not precinct turnout.`));
  const counties = html("button", "selection-link", `View ${state.selectedState} state / county data`);
  counties.type = "button"; counties.id = "show-state-county-data";
  counties.addEventListener("click", () => {
    state.viewSelections.states = { ...state.viewSelections.states, year: String(year),
      selectedState: state.selectedState, "map-color": "turnout", "map-level": "county", mode: "available" };
    showView("states");
    const selected = state.map?.stateItems?.get(code);
    if (selected) fit(selected.bounds);
  });
  panel.append(counties);
  precinctCoverageNavigation(panel, year);
  $("table-note").textContent = message + " Missing observations are not zero.";
}
async function sourcedPrecinctsView(generation) {
  const year = Number($("year").value), code = stateCode(), layer = $("precinct-layer").value;
  const sourceKey = `${year}|${code}|${layer}`;
  const previous = state.map?.view === "precincts-sourced" && state.map.sourceKey === sourceKey
    ? [...state.viewport] : null;
  $("map-color").value = layer === "results" ? "margin" : "turnout";
  $("map-level").value = "precinct";
  $("mode").value = "official";
  header(`${year} ${typeFor(year)} election · loaded precinct sources`,
    `${layer === "results" ? "Precinct election results" : "Precinct participation"} in ${state.selectedState}`,
    layer === "results"
      ? "Candidate votes by matched reporting area. These are not ballots cast or participation rates."
      : "Direct participation counts and source-defined rates where qualified. No state or county rate is assigned to a precinct.",
    "Coverage is source-specific and partial. Other years' boundaries are never substituted.");
  legend([[layer === "results" ? "Loading candidate-result layer" : "Loading participation layer", "#d6d3cb"]]);
  $("coverage-note").textContent = "Loading the selected source-qualified precinct layer…";
  stateMap(new Map(), year === 2026);
  if (generation !== state.generation) return;
  state.map.view = "precincts-sourced";
  state.map.sourceKey = sourceKey;
  const selected = state.map.stateItems.get(code);
  if (!selected) throw new Error(`No state reference geometry for ${state.selectedState}`);
  const outline = state.map.stateSelectionOutline;
  outline.setAttribute("d", state.map.statePaths.get(code)?.getAttribute("d") || "");
  outline.dataset.selectedState = state.selectedState;
  if (previous) setViewport(previous);
  else fit(selected.bounds);
  state.map.detail.replaceChildren();
  precinctSourcePanel(year, layer);
  state.precinctItems = new Map(); state.precinctRows = new Map(); state.searchItems = new Map();
  $("precinct-options").replaceChildren();
  setTable([], [["county", "County"], ["precinct", "Reporting unit"]]);
  if (layer === "results" ? !precinctResultCoverage(code, year) : !precinctParticipationCoverage(code, year)) {
    unavailablePrecincts(year, code, layer);
    return;
  }
  const token = ++state.drillToken;
  try {
    if (layer === "results") {
      await drawPrecinctResults(state.map, selected, code, year, token);
    } else {
      const coverage = precinctParticipationCoverage(code, year);
      if (coverage === "matched_results")
        await drawMatchedPrecinctParticipation(state.map, selected, code, year, token);
      else if (coverage === "reporting_units")
        await drawReportingUnitCounts(state.map, code, year, token);
      else await drawCurrentPrecinctGeography(state.map, selected, code, token);
    }
  } catch (error) {
    if (generation !== state.generation || token !== state.drillToken) return;
    $("coverage-note").textContent = `The ${year} precinct source could not be loaded: ${error.message}. State context is retained.`;
    $("geography-note").textContent = "Source load failed, not zero participation.";
    const retry = html("button", "selection-link", "Retry precinct source");
    retry.type = "button"; retry.addEventListener("click", render);
    $("substate-detail").replaceChildren(html("p", "selection-note", $("coverage-note").textContent), retry);
  }
  if (generation !== state.generation) return;
  $("geography-note").hidden = false;
  precinctCoverageNavigation($("selection-panel"), year);
  note(state.precinctControlNote);
}
async function ncPrecinctsView(generation) {
  const year = Number($("year").value), county = state.county;
  header(`${year} ${typeFor(year)} election · North Carolina`, "A closer look at precinct participation",
    "Participants recorded in voter history / election-time registered voters. Select a precinct for its counts.",
    "Gray: no validated rate, no matched observation, or registrations below the selected minimum. Unmatched records remain in the full downloads.");
  ramp();
  const previous = state.loadedPrecinctYear === year && state.loadedCounty === county && state.map?.view === "precincts"
    ? [...state.viewport] : null;
  if (!state.nc.has(year)) {
    $("visualization").replaceChildren(html("p", "empty", `Loading ${year} precinct observations…`));
    state.nc.set(year, await get(`nc/${year}.json`));
  }
  if (generation !== state.generation) return;
  const data = state.nc.get(year), dimension = $("dimension").value, group = $("group").value;
  const rows = data.records.filter(row => row.dimension === dimension && row.group === group);
  const counties = unique(data.records.map(row => row.county)).sort();
  if (!counties.includes(state.county)) state.county = "";
  options($("precinct-county"), [["", "All counties"], ...counties.map(name => [name, titleCase(name)])], state.county);
  const filtered = rows.filter(row => !state.county || row.county === state.county);
  state.precinctRows = new Map(rows.map(row => [keyFor(row), row]));
  $("nc-download").href = `/voter-participation/data/nc/${year}.csv`;
  $("nc-download").textContent = `NC ${year} precinct observations`;
  setTable(filtered, [["county", "County"], ["precinct", "Precinct"], ["group", "Group"],
    ["participants", "Participants"], ["registered", "Registered"], ["turnout_pct", "Participation"], ["quality", "Quality flags"]]);
  const audit = state.audits.find(row => row.year === year);
  state.precinctItems = new Map(filtered.map(row => [keyFor(row), { county: row.county, precinct: row.precinct, label: "" }]));
  if (!audit) {
    state.map = null; state.mapPaths = []; state.projected = [];
    $("map-tools").hidden = true; $("map-help").hidden = true;
    $("visualization").replaceChildren(html("p", "empty", `No verified ${year} precinct boundary snapshot.\nCounts remain available in the table and full download.`));
    note("We do not substitute a different year's map. Precinct IDs are not a boundary crosswalk.");
  } else {
    if (!state.shapes.has(year)) state.shapes.set(year, await get(`nc/geometry-${year}.geojson`));
    if (generation !== state.generation) return;
    const features = state.shapes.get(year).features;
    const allProjected = projectFeatures(features, albers, [25, 30, 950, 490]);
    state.projected = allProjected.filter(item => !state.county || item.feature.properties.county === state.county);
    for (const item of state.projected) state.precinctItems.set(keyFor(item.feature.properties), item.feature.properties);
    const chart = createMap(1000, 550, `${year} North Carolina precinct map. Use the county selector and precinct search for accessible selection.`);
    const minimum = Number($("minimum").value);
    for (const item of state.projected) {
      const p = item.feature.properties, key = keyFor(p), row = state.precinctRows.get(key);
      const value = row && row.registered >= minimum ? row.turnout_pct : null;
      chart.append(featurePath(item, value,
        `${titleCase(p.county)} · ${p.precinct}\n${pct(value)} · ${fmt(row?.participants)} participants / ${fmt(row?.registered)} registered`,
        () => selectPrecinct(key), { "data-key": key, "data-county": p.county, "data-precinct": p.precinct, tabindex: "-1" }));
    }
    if (previous) setViewport(previous);
    else resetMap();
    note(`${state.precinctControlNote ? state.precinctControlNote + " " : ""}`
      + `${audit.participant_match_pct.toFixed(1)}% of recorded participants match this boundary snapshot by county + precinct ID. `
      + `${audit.vintage}. ID matching is not independent certification of election-day boundaries. Rates with inconsistent counts are withheld.`);
  }
  state.loadedPrecinctYear = year; state.loadedCounty = state.county;
  state.searchItems = new Map();
  const items = [...state.precinctItems.entries()].sort((a, b) =>
    a[1].county.localeCompare(b[1].county) || a[1].precinct.localeCompare(b[1].precinct));
  $("precinct-options").replaceChildren(...items.filter(([, item]) => item.precinct).map(([key, item]) => {
    const value = `${item.county} · ${item.precinct} · ${item.label || "Precinct"}`;
    state.searchItems.set(value, key);
    const option = document.createElement("option"); option.value = value; return option;
  }));
  if (state.precinct && !state.precinct.includes("|")) state.precinct = `${state.county}|${state.precinct}`;
  if (state.precinctItems.has(state.precinct)) selectPrecinct(state.precinct, !previous);
  else {
    state.precinct = ""; $("precinct-search").value = ""; precinctDetail();
  }
}
async function precinctsView(generation) {
  if (ncParticipationView()) return ncPrecinctsView(generation);
  return sourcedPrecinctsView(generation);
}
async function render() {
  const generation = ++state.generation;
  $("tooltip").hidden = true; note("");
  $("provisional-status").hidden = !isProvisional();
  try {
    if (state.view === "states") statesView();
    else if (state.view === "national") await nationalView();
    else if (state.view === "precincts") await precinctsView(generation);
    methodsView();
    if (generation === state.generation) syncURL();
  } catch (error) {
    if (generation !== state.generation) return;
    note(`The saved data could not be loaded: ${error.message}. No values have been inferred.`);
    $("notice-panel").open = true;
    state.map = null; state.mapPaths = [];
    $("map-tools").hidden = true; $("map-help").hidden = true;
    $("selection-panel").replaceChildren(html("p", "selection-note", "No selection data available for this view."));
    $("visualization").replaceChildren(html("p", "empty", "Data unavailable. Complete downloads remain under Methods & data."));
  }
}
function hashTarget() {
  if (!location.hash) return null;
  try {
    return document.getElementById(decodeURIComponent(location.hash.slice(1)));
  } catch {
    return null;
  }
}
function revealHashTarget(target = hashTarget()) {
  if (!target) return;
  if (target.closest("#methods-panel") && state.view !== "methods") showView("methods");
  if (target.closest("#methods-archive")) $("methods-archive").classList.add("is-visible");
  if (target.closest("#participation-research") && state.view === "methods") showView("states");
  for (let element = target; element && element !== root; element = element.parentElement)
    if (element instanceof HTMLDetailsElement) element.open = true;
}
async function main() {
  loadUfTurnout();
  loadReviewedCounties();
  for (const button of document.querySelectorAll(".participation-nav button"))
    button.addEventListener("click", () => {
      if (button.dataset.view === "methods" && hashTarget()?.closest("#methods-archive")) {
        const url = new URL(location.href);
        url.hash = "";
        history.replaceState(null, "", url);
      }
      showView(button.dataset.view);
    });
  $("basis").addEventListener("change", () => { configure(); render(); });
  $("dimension").addEventListener("change", () => { configure(); render(); });
  $("year").addEventListener("change", () => { configure(); render(); });
  $("group").addEventListener("change", () => { configure(); render(); });
  $("demographic-state").addEventListener("change", () => { configure(); render(); });
  $("mode").addEventListener("change", () => { configure(); render(); });
  $("current-state-select").addEventListener("change", () => {
    state.countState = $("current-state-select").value; configureGroups(); render();
  });
  $("minimum").addEventListener("change", render);
  $("method-group").addEventListener("change", methodsView);
  $("method-history-mode").addEventListener("change", methodsView);
  $("search").addEventListener("input", renderTable);
  $("state-select").addEventListener("change", () => {
    state.selectedState = $("state-select").value; stateDetail(); syncURL();
    const item = state.map?.stateItems?.get(stateCode());
    if (item) fit(item.bounds);
  });
  $("precinct-state-select").addEventListener("change", () => {
    state.selectedState = $("precinct-state-select").value;
    state.county = ""; state.precinct = "";
    configure({ ...viewSelection(), "precinct-state-select": state.selectedState });
    render();
  });
  $("precinct-layer").addEventListener("change", () => {
    state.county = ""; state.precinct = "";
    configure(viewSelection());
    render();
  });
  $("map-color").addEventListener("change", render);
  $("map-level").addEventListener("change", () => {
    const item = state.map?.stateItems?.get(stateCode());
    const needsFit = item && state.map.full[0] / state.viewport[2] < 2.3
      && !["precinct", "county"].includes($("map-level").value);
    render();
    if (needsFit) fit(item.bounds);
  });
  $("precinct-county").addEventListener("change", () => {
    state.county = $("precinct-county").value; state.precinct = ""; render();
  });
  $("precinct-search").addEventListener("change", () => {
    const value = $("precinct-search").value, key = state.searchItems?.get(value);
    if (key) {
      if (key !== state.precinct) selectPrecinct(key);
    }
    else if (value) {
      const matches = [...(state.precinctItems?.entries() ?? [])].filter(([, item]) =>
        item.precinct.toLowerCase() === value.trim().toLowerCase());
      if (matches.length === 1) {
        if (matches[0][0] !== state.precinct) selectPrecinct(matches[0][0]);
      }
      else note("Choose a county and a precinct suggestion; this search does not uniquely identify a mapped precinct.");
    }
  });
  $("map-zoom-in").addEventListener("click", () => zoom(2));
  $("map-zoom-out").addEventListener("click", () => zoom(.5));
  $("map-reset").addEventListener("click", resetMap);
  const tabs = [...document.querySelectorAll(".participation-nav button")];
  for (const tab of tabs) tab.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1
      : (tabs.indexOf(tab) + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    tabs[index].focus(); showView(tabs[index].dataset.view);
  });
  await Promise.all([loadContext(), loadMethods(), loadLocal(), loadCurrentPrecincts(), loadPrecinctResults(),
    loadReportingUnitSources()]);
  const [national, states, geometry, ncSummary, audits] = await Promise.all([
    get("national.json"), get("states.json"), get("states.geojson"), get("nc/summary.json"), get("geometry-audit.json"),
    loadCurrent(),
  ]);
  Object.assign(state, { national, states, geometry, ncSummary, audits });
  for (const row of [...national, ...states]) row.warnings = row.warnings.flatMap(warning =>
    warning === "Citizenship measurement before 1996 is not directly comparable with later years."
      ? row.year < 1994 ? ["Citizenship measurement before 1994 is not directly comparable with later years."] : []
      : [warning]);
  currentAudit();
  const names = unique(geometry.features.map(f => f.properties.NAME)).filter(name => states.some(row => row.state === name)).sort();
  options($("state-select"), names.map(name => [name, name]), state.selectedState);
  state.selectedState = $("state-select").value;
  options($("demographic-state"), [["US", "United States"],
    ...demographicStates.map(code => [code, stateName(code)])], params.get("demographic-state") || "US");
  options($("current-state-select"), (state.current?.coverage ?? []).map(row => [row.state_code, row.state]), state.countState);
  state.countState = $("current-state-select").value || "GA";
  for (const id of ["basis", "map-color", "map-level"])
    if ([...$(id).options].some(o => o.value === params.get(id))) $(id).value = params.get(id);
  configure();
  if ([...$("year").options].some(o => o.value === params.get("year"))) $("year").value = params.get("year");
  configure();
  for (const id of ["mode"])
    if ([...$(id).options].some(o => o.value === params.get(id))) $(id).value = params.get(id);
  configure();
  if ([...$("dimension").options].some(o => o.value === params.get("dimension"))) $("dimension").value = params.get("dimension");
  configureGroups();
  if ([...$("group").options].some(o => o.value === params.get("group"))) $("group").value = params.get("group");
  if (hashTarget()?.closest("#methods-panel")) state.view = "methods";
  showView(state.view);
  state.initialized = true;
  revealHashTarget();
  window.addEventListener("hashchange", () => revealHashTarget());
  let lastWidth = $("visualization").clientWidth;
  new ResizeObserver(() => {
    const width = $("visualization").clientWidth;
    if (width !== lastWidth && state.view === "national") nationalView();
    else if (width !== lastWidth && state.map) setViewport(state.viewport);
    lastWidth = width;
  }).observe($("visualization"));
}
main().catch(error => {
  $("historical-explorer").hidden = false;
  note(`Cannot load the historical explorer: ${error.message}. Methods and complete downloads remain available.`);
  $("notice-panel").open = true;
  $("visualization").replaceChildren(html("p", "empty", "Historical inputs could not be loaded."));
});

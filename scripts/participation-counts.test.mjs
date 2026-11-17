import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { rings } from "../public/scripts/participation-map-projection.js";
import { canonicalObservation, encoded, digest, pin, selectedFrame } from "./compile-participation-counts.mjs";
import { countModes, countStates, validateCountObservation, validateCountShard,
  validateCurrentCountSnapshot, countFrame, validateUfTurnout,
  ufTurnoutRows } from "../public/scripts/participation-counts.js";

const view = () => ({ year: 2026, state_code: "MN", county_id: "native:1", county: "Example",
  ballots: 0, denominator: 100, denominator_basis: "native_registered_voters",
  reported_pct: 0, source_update_label: "November 3; timezone not supplied",
  source_url: "https://example.org/counts", quality: ["Native conflict remains in original fields."] });
const input = { file: "original.json", sha256: "a".repeat(64), url: "https://example.org/export.json" };
const observation = () => canonicalObservation(view(), input, "counties", 0);

function ufSnapshot() {
  const version = "0.3", sha256 = "b".repeat(64);
  return {
    contract: "participation.uf_statewide_turnout.v1", election_date: "2026-11-03",
    version, status: "reported", first_observed_at: "2026-11-17T12:00:00+00:00",
    source: { url: `https://election.lab.ufl.edu/data-downloads/turnoutdata/Turnout_2026G_v${version}.csv`,
      bytes: 8000, sha256 },
    csv_edition: { body_sha256: sha256, http_last_modified: null },
    documentation: { version, license: "CC-BY-4.0", attribution: "Michael McDonald / UF",
      anomalies: ["documentation_date_predates_election_not_a_count_clock"] },
    limitations: ["Statewide only; not independently certified."],
    rows: [...countStates, "US"].map(code => ({
      state_code: code, state: code, year: 2026,
      geographic_level: code === "US" ? "national" : "state",
      ballots: 500, vep: 1000, vap: 2000, vep_rate: 50, vap_rate: 25,
      source_status_literal: "", ballots_status: "estimate",
      source_update_label: null, source_update_timezone: null,
      independently_certified: false, local_allocation_qualified: false,
      native: { STATE_ABV: code, STATE: code, STATUS: "",
        SOURCE: "https://official.test/returns", TOTAL_BALLOTS_COUNTED: "500",
        VEP: "1000", VAP: "2000", VEP_TURNOUT_RATE: "50.00%", VAP_TURNOUT_RATE: "25.00%" },
    })),
  };
}

test("UF consumer preserves source statuses, estimated denominators, zeroes and unknowns", () => {
  const data = ufSnapshot(), before = structuredClone(data);
  assert.equal(validateUfTurnout(data), data);
  assert.equal(ufTurnoutRows(data).length, 52);
  assert.equal(ufTurnoutRows(data)[0].source_status, "estimated");
  assert.deepEqual(data, before);
  for (const literal of ["Official", "Final", "Offiical"]) {
    const row = data.rows[0];
    row.native.STATUS = row.source_status_literal = literal;
    row.ballots_status = literal === "Offiical" ? "unrecognized_source_status"
      : "source_reported_not_independently_certified";
    const result = ufTurnoutRows(data)[0];
    assert.match(result.source_status, literal === "Offiical" ? /unrecognized/ : /not independently verified/);
    assert.equal(result.independently_certified, false);
    assert.equal(result.source_update_label, null);
    assert.equal(result.native.STATUS, literal);
  }
  const row = data.rows[1];
  row.ballots = row.vep_rate = row.vap_rate = 0;
  Object.assign(row.native, { TOTAL_BALLOTS_COUNTED: "0", VEP_TURNOUT_RATE: "0.00%", VAP_TURNOUT_RATE: "0.00%" });
  assert.equal(ufTurnoutRows(data)[1].ballots, 0);
  row.ballots = row.vep_rate = row.vap_rate = null;
  Object.assign(row.native, { TOTAL_BALLOTS_COUNTED: "", VEP_TURNOUT_RATE: "", VAP_TURNOUT_RATE: "" });
  assert.equal(ufTurnoutRows(data)[1].ballots, null);
  data.status = "retained_after_failure";
  assert.equal(ufTurnoutRows(data)[0].status, "retained_after_failure");
  assert.equal(ufTurnoutRows(data)[0].first_observed_at, before.first_observed_at);
});

test("UF consumer refuses inconsistent status, identity, counts, rates and unsupported promotions", () => {
  for (const mutate of [
    data => data.rows.pop(),
    data => { data.rows[0] = structuredClone(data.rows[1]); },
    data => { data.rows[0].year = 2024; },
    data => { data.rows[0].geographic_level = "county"; },
    data => { data.rows[0].native.STATUS = "Official"; },
    data => { data.rows[0].source_status_literal = "Final"; },
    data => { data.rows[0].ballots++; },
    data => { data.rows[0].native.VEP = "-1"; },
    data => { data.rows[0].vep_rate++; },
    data => { data.rows[0].local_allocation_qualified = true; },
    data => { data.rows[0].independently_certified = true; },
    data => { data.rows[0].source_update_label = data.first_observed_at; },
    data => { data.csv_edition.body_sha256 = "c".repeat(64); },
    data => { data.source.url = "https://wrong.test/turnout.csv"; },
    data => { data.documentation.license = null; },
  ]) {
    const data = ufSnapshot(); mutate(data);
    assert.throws(() => validateUfTurnout(data), /UF/);
  }
});

test("actual explorer loading replaces dated UF rows without altering local or model frames", async () => {
  const source = readFileSync(new URL("../public/scripts/participation-explorer.js", import.meta.url), "utf8");
  const start = source.indexOf("async function loadCurrent()");
  const end = source.indexOf("\nfunction loadUfTurnout()", start);
  assert(start >= 0 && end > start);
  const data = ufSnapshot();
  data.complete_download = { url: "https://github.com/hanshanley/margin_of_error/releases/download/current/complete-analysis.zip" };
  const current = { snapshot: { reporting: [{ ballots: 9 }] },
    reviewed_states: [{ ballots: 10 }], original_base: "retained-originals", uf_turnout: data };
  const state = { ufTurnout: [{ ballots: 1 }], models: ["unchanged"] };
  const load = runInNewContext(`(${source.slice(start, end)})`, {
    state, loadCurrentCountSnapshot: async () => current, ufTurnoutRows,
    loadUfTurnout: () => { state.ufTurnout = [{ ballots: 1, source_date: "dated saved edition" }]; },
  });
  await load();
  assert.equal(state.ufTurnout.length, 52);
  assert.equal(state.ufTurnout[0].ballots, 500);
  assert.equal(state.ufTurnout[0].complete_download_url, data.complete_download.url);
  assert.equal(state.current, current.snapshot);
  assert.equal(state.reviewedStates, current.reviewed_states);
  assert.deepEqual(state.models, ["unchanged"]);
  delete current.uf_turnout;
  await load();
  assert.equal(state.ufTurnout[0].ballots, 1);
  assert.equal(state.ufTurnout[0].source_date, "dated saved edition");
});

test("actual asynchronous current loader rejects corrupt UF as one runtime and restores accepted fallback", async () => {
  const source = readFileSync(new URL("../public/scripts/participation-counts.js", import.meta.url), "utf8");
  const start = source.indexOf("export async function loadCurrentCountSnapshot()");
  const current = () => ({
    contract: "participation.current_snapshot.v1", reviewed_states: [],
    snapshot: { reporting: [], early_voting: [],
      coverage: countStates.map(state_code => ({ state_code })) },
  });
  const download = { url: "https://github.com/hanshanley/margin_of_error/releases/download/current/complete-analysis.zip" };
  for (const corrupt of [false, true]) {
    const active = { ...current(), uf_turnout: ufSnapshot() }, fallback = current(), events = [];
    if (corrupt) active.uf_turnout.rows[0].ballots++;
    const automatic = { entry: { base_url: "active/" },
      index: { current_snapshot: "active-current", original_current_base: "active-originals" },
      automatic_runtime: { complete_download: download } };
    const accepted = { entry: { base_url: "accepted/" },
      index: { current_snapshot: "accepted-current", original_current_base: "accepted-originals" } };
    const load = runInNewContext(`(${source.slice(start).replace(/^export /, "")})`, {
      loadCountIndex: async () => automatic,
      checkedDatasetFile: async (base, file) => {
        events.push([base, file]);
        return base === "active/" ? active : fallback;
      },
      validateCurrentCountSnapshot,
      setAutomaticRuntimeStatus: (...args) => events.push(["active", ...args]),
      rejectCountRuntime: error => events.push(["rejected", error.message]),
      validateCountIndex: value => value,
      loadDataset: async (id, options) => {
        assert.equal(id, "participation-counts-2026");
        assert.equal(options.automatic, false);
        return accepted;
      },
    });
    const loaded = await load();
    assert.equal(loaded.original_base, corrupt ? "accepted-originals" : "active-originals");
    if (corrupt) {
      assert.equal(loaded.uf_turnout, undefined);
      assert.equal(events.filter(row => row[0] === "rejected").length, 1);
      assert.equal(events.some(row => row[0] === "active"), false);
    } else {
      assert.equal(loaded.uf_turnout.complete_download, download);
      assert.equal(events.filter(row => row[0] === "active/").length, 1);
      assert.equal(events.some(row => row[0] === "rejected"), false);
    }
  }
});

test("unavailable precincts retain UF native status without claiming local turnout", () => {
  const source = readFileSync(new URL("../public/scripts/participation-explorer.js", import.meta.url), "utf8");
  const start = source.indexOf("function unavailablePrecincts(");
  const end = source.indexOf("\nasync function sourcedPrecinctsView(", start);
  assert(start >= 0 && end > start);
  for (const literal of ["", "Official", "Final", "Offiical"]) {
    const data = ufSnapshot(), native = data.rows[0];
    native.native.STATUS = native.source_status_literal = literal;
    native.ballots_status = !literal ? "estimate" : literal === "Offiical" ? "unrecognized_source_status"
      : "source_reported_not_independently_certified";
    const row = ufTurnoutRows(data)[0], elements = new Map();
    const $ = id => {
      if (!elements.has(id)) elements.set(id, { children: [], append(...items) { this.children.push(...items); } });
      return elements.get(id);
    };
    const render = runInNewContext(`(${source.slice(start, end)})`, {
      $, state: { selectedState: row.state, ufTurnout: [row] },
      options() {}, header() {}, legend() {}, precinctCoverageNavigation() {},
      html: (tag, className, text) => ({ tag, className, text, addEventListener() {} }),
    });
    render(2026, row.state_code, "participation");
    const note = $("substate-detail").children.find(item => item.className === "selection-basis");
    assert(note.text.includes(`UF ${row.source_status}, not precinct turnout.`));
    assert.equal(note.text.includes("UF estimate,"), false);
  }
});

function heldCountyHarness(contextGet) {
  const source = readFileSync(new URL("../public/scripts/participation-explorer.js", import.meta.url), "utf8");
  const start = source.indexOf("  function countyResultHold(");
  const end = source.indexOf("  function countyResultDetail(", start);
  assert(start >= 0 && end > start, "The explorer must handle explicitly held county results");
  const node = () => ({
    children: [], style: {}, classList: { add() {}, remove() {} },
    replaceChildren(...children) { this.children = children; },
    append(...children) { this.children.push(...children); },
    querySelectorAll() { return []; },
  });
  const elements = new Map();
  for (const [id, value] of Object.entries({
    year: "2026", "map-level": "county", "map-color": "margin", mode: "available",
  })) elements.set(id, { ...node(), value });
  const $ = id => {
    if (!elements.has(id)) elements.set(id, node());
    return elements.get(id);
  };
  const selected = { bounds: [0, 0, 1000, 610],
    feature: { properties: { NAME: "Maine", STUSAB: "ME", STATE: "23" } } };
  const state = {
    code: "ME", view: "states", selectedState: "Maine", viewport: [0, 0, 1000, 610],
    drillKey: "", drillToken: 1, subshapes: new Map(), margins: [],
    contextPath: "/participation-context/reviewed/",
    context: { boundary_year: 2024, geometry: { county: { ME: "geometry/county-ME.geojson" } } },
    countyResults: { year: 2026, coverage: { FL: {} },
      withheld_states: { ME: { status: "withheld", error: "District / county vectors do not reconcile" } } },
    countyResultsPath: "https://example.org/county/",
    countyResultsDownload: "https://example.org/complete-county-results.zip",
    countyOverview: {},
    table: [{ state: "Original statewide row" }], columns: [["state", "State"]],
  };
  const map = {
    full: [1000, 610], detail: node(), svg: node(), statePaths: new Map(),
    stateItems: new Map([["ME", selected], ["FL", {
      bounds: selected.bounds, feature: { properties: { NAME: "Florida" } },
    }]]),
    stateHeading: ["state subtitle", "State results", "State measure", "State caption"],
    stateCoverage: "State coverage",
  };
  state.map = map;
  const geometry = { type: "FeatureCollection", features: [{
    type: "Feature", properties: { key: "23031", name: "York County", state_code: "ME", boundary_year: 2024 },
    geometry: { type: "Polygon", coordinates: [[[-70, 43], [-69, 43], [-69, 44], [-70, 43]]] },
  }] };
  const effects = { legends: [], headings: [], outlines: 0, sourceCalls: 0 };
  const dispatchStart = source.indexOf("  async function updateGeography()");
  const dispatchEnd = source.indexOf("\nfunction resetMap()", dispatchStart);
  const helpers = runInNewContext(`(() => { ${source.slice(start, end)}
    ${source.slice(dispatchStart, dispatchEnd)}
    return { hold: countyResultHold, draw: drawHeldCountyResults, update: updateGeography }; })()`, {
    state, $, rings, URL, DOMPoint: class {},
    contextGet: async path => {
      effects.sourceCalls++;
      return contextGet ? contextGet(path, geometry) : geometry;
    },
    html: (tag, className, textContent) => ({ ...node(), tag, className, textContent }),
    projectInside: feature => ({ feature, bounds: selected.bounds }),
    featurePath: (item, value, label, action, attrs) => ({ ...node(), label, action, attrs, value }),
    referenceOutline: () => { effects.outlines++; },
    header: (...args) => { effects.headings.push(args); },
    legend: items => { effects.legends = items; },
    fmt: String, fit() {}, stateCode: () => state.code, stateDetail() {},
    setTable: (rows, columns) => { state.table = rows; state.columns = columns; },
    drawNationalCountyResults: () => { $("geography-note").textContent = "Generic national overview"; },
    drawCountyResults: () => { map.countyLayer = true; effects.qualified = true; },
    marginLegend() {}, isProvisional: () => true,
  });
  return { ...helpers, state, map, selected, geometry, effects, $ };
}

test("held county boundaries remain neutral and export missing counts rather than zero", async () => {
  const h = heldCountyHarness();
  await h.draw(h.map, h.selected, "ME", 2026, 1, h.hold("ME", 2026));
  assert.equal(h.map.detail.children.length, 1);
  const path = h.map.detail.children[0];
  assert.equal(path.attrs["data-color-level"], "none");
  assert.equal(path.attrs["data-boundary-year"], 2024);
  assert.equal(path.attrs["data-results-status"], "withheld");
  assert.equal(path.attrs["data-margin"], undefined);
  assert.equal(path.attrs["data-total-votes"], undefined);
  assert.equal(h.state.table[0].contest_votes, null);
  assert.equal(h.state.table[0].margin_pp, null);
  assert.match(h.$("geography-note").textContent, /2024 Census/);
  assert.match(h.$("geography-note").textContent, /do not reconcile/);
  path.action();
  assert.equal(h.$("substate-detail").children[0].textContent, "York County");
  assert.match(h.$("substate-detail").children[1].textContent, /unavailable/i);
  assert(h.$("substate-detail").children.some(child =>
    child.href === h.state.countyResultsDownload));
});

test("a county hold cannot override a supported state, other year or unreviewed omission", () => {
  const h = heldCountyHarness();
  assert.equal(h.hold("FL", 2026), null);
  assert.equal(h.hold("ME", 2024), null);
  assert.equal(h.hold("DC", 2026), null);
  h.state.countyResults.coverage.ME = {};
  assert.equal(h.hold("ME", 2026), null);
});

test("held county references reject changed identity, vintage, missing and malformed geometry", async () => {
  for (const mutate of [
    data => { data.features = []; },
    data => { data.features[0].properties.state_code = "NH"; },
    data => { data.features[0].properties.key = "33031"; },
    data => { data.features[0].properties.boundary_year = 2026; },
    data => { data.features.push(structuredClone(data.features[0])); },
    data => { data.features[0].geometry.type = "Point"; },
    data => { data.features[0].geometry.coordinates[0][0][0] = NaN; },
  ]) {
    const h = heldCountyHarness((path, geometry) => {
      const data = structuredClone(geometry); mutate(data); return data;
    });
    await assert.rejects(h.draw(h.map, h.selected, "ME", 2026, 1, h.hold("ME", 2026)),
      /county reference/i);
    assert.equal(h.map.detail.children.length, 0);
    assert.equal(h.effects.outlines, 0);
    assert.equal(h.state.table[0].state, "Original statewide row");
  }
});

test("failed held-reference fetches retry and stale responses cannot paint another selection", async () => {
  let release;
  const h = heldCountyHarness((path, geometry) => new Promise(resolve => {
    release = () => resolve(geometry);
  }));
  const pending = h.draw(h.map, h.selected, "ME", 2026, 1, h.hold("ME", 2026));
  h.state.drillToken++;
  release(); await pending;
  assert.equal(h.map.detail.children.length, 0);
  assert.equal(h.effects.headings.length, 0);
  let attempts = 0;
  const retry = heldCountyHarness((path, geometry) => {
    if (!attempts++) throw new Error("HTTP 503");
    return geometry;
  });
  await assert.rejects(retry.draw(retry.map, retry.selected, "ME", 2026, 1, retry.hold("ME", 2026)), /503/);
  await retry.draw(retry.map, retry.selected, "ME", 2026, 1, retry.hold("ME", 2026));
  assert.equal(retry.effects.sourceCalls, 2);
  assert.equal(retry.map.detail.children.length, 1);
});

test("initial county deep links and repeated viewport updates retain the held explanation", async () => {
  const h = heldCountyHarness();
  await h.update();
  assert.equal(h.map.detail.children.length, 1);
  const explanation = h.$("geography-note").textContent;
  await h.update();
  assert.equal(h.$("geography-note").textContent, explanation);
  assert.match(explanation, /do not reconcile/);
  h.state.code = "FL"; h.state.selectedState = "Florida";
  h.state.viewport = [0, 0, 300, 180];
  await h.update();
  assert.equal(h.effects.qualified, true);
  assert.equal(h.state.table[0].state, "Original statewide row");
  assert.equal(h.map.detail.children.length, 0);
});

test("canonical migration preserves zero, unknown, withheld fraction and literal source fields", () => {
  const row = observation();
  validateCountObservation(row, "MN");
  assert.equal(row.count.value, 0);
  assert.equal(row.count.status, "reported");
  assert.equal(row.source_clock.timezone, null);
  assert.equal(row.reporting_status.complete, null);
  assert.equal(row.geography.join.status, "unreviewed");
  assert.deepEqual(row.view, row.source.fields);
  const unknown = view();
  unknown.ballots = null; unknown.reported_pct = null;
  const absent = canonicalObservation(unknown, input, "counties", 0);
  validateCountObservation(absent, "MN");
  assert.equal(absent.count.status, "unknown");
  assert.equal(absent.denominator.qualified, false);
  const held = canonicalObservation({ ...unknown,
    native_record: { source_scope_review: "withheld_processed_not_defined_as_counted" } }, input, "counties", 0);
  validateCountObservation(held, "MN");
  assert.equal(held.count.status, "withheld");
  assert.equal(held.count.value, null);
  assert.notEqual(row.id, canonicalObservation({ ...view(), source_mode: "mail_returned" }, input, "counties", 0).id);
});

test("common contract rejects state/count changes, candidate substitution, false zeros and rate promotion", () => {
  for (const mutate of [
    row => { row.geography.state_code = "NM"; },
    row => { row.count.value = null; },
    row => { row.count.value = false; row.view.ballots = false; },
    row => { row.count.value = Number.MAX_SAFE_INTEGER + 1; },
    row => { row.measure.kind = "candidate_votes"; },
    row => { row.denominator.qualified = false; },
    row => { row.source_clock.literal = null; row.source_clock.timezone = "UTC"; },
    row => { row.geography.join.status = "approved"; },
    row => { row.reporting_status.reported_units = 2; row.reporting_status.total_units = 1; },
    row => { row.quality.conflicts = [{ code: "native_disagreement", repaired: true }]; },
  ]) {
    const row = observation(); mutate(row);
    assert.throws(() => validateCountObservation(row, "MN"), /Unqualified/);
  }
});

function shard() {
  const row = observation();
  return { contract: "participation.count_snapshot.v1", year: 2026, state_code: "MN",
    records: [row], views: Object.fromEntries(countModes
      .map(mode => [mode, { qualified: mode === "available" || mode === "official",
        counties: mode === "available" || mode === "official" ? [row.id] : [],
        precincts: [], nongeographic: [], holds: [] }])) };
}

test("canonical mode bindings reject missing references, duplicate identities and all-method substitution", () => {
  validateCountShard(shard(), "MN", { records: 1 });
  assert.equal(countFrame(shard(), "available").counties[0].ballots, 0);
  for (const mutate of [
    data => { data.records.push(data.records[0]); },
    data => { data.views.available.counties.push(data.records[0].id); },
    data => { data.views.available.counties = ["b".repeat(32)]; },
    data => { data.views.mail_returned.qualified = true; data.views.mail_returned.counties = [data.records[0].id]; },
    data => { data.views.official.qualified = false; },
  ]) {
    const data = shard(); mutate(data);
    assert.throws(() => validateCountShard(data, "MN", { records: data.records.length }), /Duplicate|Unqualified/);
  }
});

function registryShard() {
  const data = shard(), context = observation();
  context.id = "c".repeat(32);
  context.measure = { id: "registry-date-token", literal: "Current registration records",
    kind: "source_activity", mode: "source_defined", unit: "current_registration_records" };
  context.election.type = "date_coded_history_context";
  context.election.qualification = "collector_context";
  context.denominator = null;
  context.view = { ...context.view, denominator: null, reported_pct: null, maps_approved: false,
    administrative_history_context_only: true, source_frame_kind: "current_registry_date_token",
    source_input_kind: "person_record_file_retained_privately", derived_aggregate: true };
  context.source.fields = context.view;
  data.records.push(context);
  data.views.available.administrative_contexts = [context.id];
  return data;
}

test("registry context is a separate optional channel and preserves the original county inventory", () => {
  const data = registryShard();
  validateCountShard(data, "MN", { records: 2 });
  assert.equal(countFrame(data, "available").counties.length, 1);
  assert.equal(countFrame(data, "available").administrative_contexts.length, 1);
  assert.equal(countFrame(data, "available").administrative_contexts[0].ballots, 0);
  assert.deepEqual(countFrame(shard(), "available").administrative_contexts, []);
  assert.deepEqual(countFrame(data, "official").administrative_contexts, []);
});

test("registry context rejects ballot, electorate, map and ordinary-frame promotions", () => {
  for (const mutate of [
    data => { data.records[1].measure.kind = "ballots_cast"; },
    data => { data.records[1].measure.mode = "all_methods"; },
    data => { data.records[1].measure.unit = "voters"; },
    data => { data.records[1].election.type = "general"; },
    data => { data.records[1].view.maps_approved = true; },
    data => { data.records[1].view.derived_aggregate = false; },
    data => { data.views.available.administrative_contexts.push(data.records[1].id); },
    data => { data.views.official.administrative_contexts = [data.records[1].id]; },
    data => { data.views.available.counties.push(data.records[1].id); },
    data => { data.views.official.counties.push(data.records[1].id); },
  ]) {
    const data = registryShard();
    mutate(data);
    assert.throws(() => validateCountShard(data, "MN", { records: 2 }));
  }
});

test("old frame migration keeps unmatched source regions separate and never enables an unsupported mode", () => {
  const unavailable = selectedFrame({ counties: [view()], precincts: [], nongeographic: [] }, null, "NH", "mail_returned");
  assert.equal(unavailable.qualified, false);
  assert.deepEqual(unavailable.counties, []);
  const accepted = selectedFrame({ counties: [view()], precincts: [], nongeographic: [] }, null, "MN", "available");
  assert.equal(accepted.counties[0].ballots, 0);
  assert.deepEqual(accepted.holds, []);
});

test("content identity uses the same canonical ASCII/sorted JSON as the intake backend", () => {
  assert.equal(encoded({ z: "é", a: [true, null, 0] }).toString(), '{"a":[true,null,0],"z":"\\u00e9"}\n');
  assert.equal(pin(Buffer.from("a")).sha256, digest(Buffer.from("a")));
});

test("the current statewide/provider snapshot requires all distinct jurisdictions and exact counts", () => {
  const current = () => ({ contract: "participation.current_snapshot.v1", reviewed_states: [],
    snapshot: { coverage: countStates.map(state_code => ({ state_code })),
      reporting: [{ state_code: "AL", ballots: 0 }], early_voting: [{ state_code: "AK", ballots: null }] } });
  validateCurrentCountSnapshot(current());
  for (const mutate of [
    data => { data.snapshot.coverage[0].state_code = "AK"; },
    data => { data.snapshot.reporting[0].ballots = undefined; },
    data => { data.snapshot.early_voting[0].ballots = 1.5; },
  ]) {
    const data = current(); mutate(data);
    assert.throws(() => validateCurrentCountSnapshot(data), /Unqualified/);
  }
});

function detailHarness() {
  const source = readFileSync(new URL("../public/scripts/participation-explorer.js", import.meta.url), "utf8");
  const start = source.indexOf("const electorateLabel =");
  const end = source.indexOf("\n    async function currentNavigation(", start);
  assert(start >= 0 && end > start);
  const html = (tag, className, textContent) => ({ tag, className, textContent });
  const { detail, countLabel } = runInNewContext(`(() => { ${source.slice(start, end)};
    return { detail: currentCountDetail, countLabel: typeof sourceUnitCountLabel === "function"
      ? sourceUnitCountLabel : undefined }; })()`, {
    residentSource() {}, html, state: { currentPrecinctShapes: new Map() },
    fmt: value => value == null ? "\u2014" : String(value),
    pct: () => "Unavailable",
    sourceLink: row => ({ ...html("a", "source-link", "Original source"), href: row.source_url }),
  });
  const host = { children: [], replaceChildren(...children) { this.children = children; },
    append(...children) { this.children.push(...children); } };
  return { detail, host, countLabel };
}

test("source-unit count headings preserve native measures without treating mixed counts as ballots", () => {
  const { countLabel } = detailHarness();
  for (const [rows, expected] of [
    [[{ ballots: 0, participation_measure_literal: "# VOTING" }], "# VOTING"],
    [[{ ballots: null, participation_measure_label: "Native voters participating" },
      { ballots: 12, participation_measure_label: "Native voters participating" }], "Native voters participating"],
    [[{ participation_measure_literal: "Cards Cast" }], "Cards Cast"],
    [[{ participation_measure_label: "Voters Cast", participation_measure_literal: "# VOTING" },
      { participation_measure_literal: "Ballots Cast" }], "Source participation count"],
    [[{ participation_measure_literal: "Voters Cast" }, {}], "Source participation count"],
    [[{ ballots: 0 }, { ballots: null }], "Ballots reported"],
    [[], "Ballots reported"],
  ]) {
    const before = structuredClone(rows);
    assert.equal(countLabel(rows), expected);
    assert.deepEqual(rows, before);
  }
});

test("legacy reporting details expose supplied complete packages without claiming a native review", () => {
  const { detail, host } = detailHarness();
  const row = { ...view(), unit: "Native reporting row", unit_kind: "precinct",
    denominator: null, reported_pct: null, source_update_label: null,
    complete_download_url: "https://example.org/complete-source.zip" };
  const before = structuredClone(row);
  detail(host, row);
  const links = host.children.filter(node => node.tag === "a");
  assert.deepEqual(links.map(node => node.href), [row.source_url, row.complete_download_url]);
  assert.equal(links[1].textContent, "Complete source tables and source package");
  assert(!host.children.some(node => node.textContent?.startsWith("Native result-status literal:")));
  assert.deepEqual(row, before);
  for (const complete_download_url of [null, undefined]) {
    detail(host, { ...row, complete_download_url });
    assert.deepEqual(host.children.filter(node => node.tag === "a").map(node => node.href),
      [row.source_url]);
  }
});

test("non-review details honor the source measure label and literal while preserving the ballot fallback", () => {
  const { detail, host } = detailHarness();
  for (const [fields, label] of [
    [{ participation_measure_label: "Current-registration records",
      participation_measure_literal: "Native history tokens" }, "Current-registration records"],
    [{ participation_measure_literal: "Absentee In-person" }, "Absentee In-person"],
    [{}, "ballots reported"],
  ]) {
    detail(host, { ...view(), ...fields }, true);
    assert.equal(host.children.find(node => node.className === "selection-basis").textContent,
      `2026 ${label} · unofficial`);
  }
});

test("registry-history details disclose their record frame without ballot fractions or precinct reporting", () => {
  const { detail, host } = detailHarness();
  const row = { ...view(), ballots: 12, denominator: null, reported_pct: null,
    administrative_history_context_only: true, source_frame_kind: "current_registry_date_token",
    participation_measure_label: "Current-registration records with a date-coded history token",
    source_update_label: "Native file-update literal; timezone unknown" };
  const before = structuredClone(row);
  detail(host, row, true);
  const text = host.children.map(node => node.textContent).filter(Boolean).join("\n");
  assert.match(text, /current registry, not an election ballot total/);
  assert.match(text, /Registry file update: Native file-update literal/);
  assert.match(text, /Missing history is not observed nonparticipation/);
  assert.doesNotMatch(text, /source precincts reporting|fraction\. Not final turnout|2026 ballots reported/);
  assert.deepEqual(row, before);
});

test("non-review county details retain literal source status and only supplied reporting metadata", () => {
  const { detail, host } = detailHarness();
  const row = { ...view(), source_status_literal: "Official results following county canvass" };
  detail(host, row, true);
  assert.equal(host.children.find(node => node.className === "selection-basis").textContent,
    "2026 ballots reported · Official results following county canvass");
  assert(!host.children.some(node => node.textContent?.includes("source precincts reporting")));
  detail(host, { ...row, reported_units: null, total_units: null, source_rows: null }, true);
  assert(!host.children.some(node => node.textContent?.includes("source precincts reporting")));
  detail(host, { ...row, reported_units: 0, total_units: 10, source_rows: 0 }, true);
  assert(host.children.some(node => node.textContent?.startsWith("0 / 10 source precincts reporting.")));
});

test("an explicitly missing automatic native result status is not relabeled unofficial", () => {
  const { detail, host } = detailHarness();
  const row = { ...view(), automatic_source_refresh: true, source_status_literal: null,
    participation_measure_label: "Source-reported turnout total",
    native_record: { native_report_status_literal: null,
      query: { native_report_status_literal: null } } };
  const before = structuredClone(row);
  detail(host, row, true);
  assert.equal(host.children.find(node => node.className === "selection-basis").textContent,
    "2026 Source-reported turnout total · result status not supplied");
  assert.deepEqual(row, before);
  for (const status of ["OFFICIAL", "UNOFFICIAL"]) {
    detail(host, { ...row, source_status_literal: status }, true);
    assert.equal(host.children.find(node => node.className === "selection-basis").textContent,
      `2026 Source-reported turnout total · ${status}`);
  }
});

function ncCounty(status = "OFFICIAL") {
  return { ...view(), state_code: "NC", county_id: "1", county: "ALAMANCE",
    native_record: { query: { county_id: "1", county: "ALAMANCE",
      election_literal: `11/03/2026 ${status} GENERAL ELECTION RESULTS - ALAMANCE` } },
    native_state_reference: {
      election_literal: "11/03/2026 UNOFFICIAL GENERAL ELECTION RESULTS - STATEWIDE" } };
}

test("NC county cards use their own literal official or unofficial title without changing facts", () => {
  const { detail, host } = detailHarness();
  for (const status of ["OFFICIAL", "UNOFFICIAL"]) {
    const row = ncCounty(status), before = structuredClone(row);
    detail(host, row, true);
    assert.equal(host.children.find(node => node.className === "selection-basis").textContent,
      `2026 ballots reported · ${status}`);
    assert.deepEqual(row, before);
  }
  const row = { ...ncCounty(), source_status_literal: "Publisher's explicit provisional status" };
  detail(host, row, true);
  assert.equal(host.children.find(node => node.className === "selection-basis").textContent,
    "2026 ballots reported · Publisher's explicit provisional status");
});

test("NC county status cannot come from a different identity, election or statewide parent", () => {
  const { detail, host } = detailHarness();
  for (const mutate of [
    row => { row.native_record.query.county = "HALIFAX"; },
    row => { row.native_record.query.county_id = "42"; },
    row => { row.native_record.query.election_literal =
      "11/03/2026 OFFICIAL GENERAL ELECTION RESULTS - HALIFAX"; },
    row => { row.native_record.query.election_literal =
      "11/03/2026 OFFICIAL PRIMARY ELECTION RESULTS - ALAMANCE"; },
    row => { row.native_record.query.election_literal =
      "11/05/2024 OFFICIAL GENERAL ELECTION RESULTS - ALAMANCE"; },
    row => { row.state_code = "NE"; },
    row => { row.year = 2024; },
    row => { row.county_id = 0; row.native_record.query.county_id = 0; },
    row => { delete row.county_id; delete row.native_record.query.county_id; },
    row => { row.native_record = {}; },
  ]) {
    const row = ncCounty();
    mutate(row);
    detail(host, row, true);
    assert.equal(host.children.find(node => node.className === "selection-basis").textContent,
      "2026 ballots reported · unofficial");
  }
});

test("unknown source electorate metadata renders as unknown without inventing a denominator", () => {
  const { detail, host } = detailHarness();
  for (const denominator_basis of [null, undefined]) {
    const row = { ...view(), denominator: null, denominator_basis, reported_pct: null };
    const before = structuredClone(row);
    detail(host, row, true);
    assert(host.children.some(node => node.textContent?.includes("source electorate not supplied")));
    assert.equal(host.children.find(node => node.className === "selection-rate").textContent, "0");
    assert.deepEqual(row, before);
  }
});

test("native reporting identifiers are not called ordinals and adjacent source downloads stay distinct", () => {
  const { detail, host } = detailHarness();
  const row = { ...view(), unit: "5-3", unit_kind: "source_native_precinct_code",
    complete_download_url: "https://example.org/complete-source.zip" };
  detail(host, row);
  const text = host.children.map(node => node.textContent).filter(Boolean).join("\n");
  assert.match(text, /source native precinct code/);
  assert.doesNotMatch(text, /row ordinal/);
  detail(host, row, true);
  const source = host.children.findIndex(node => node.tag === "a");
  assert.equal(host.children[source + 1].textContent, " · ");
  assert.equal(host.children[source + 2].href, row.complete_download_url);
});

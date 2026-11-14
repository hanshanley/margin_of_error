import test from "node:test";
import assert from "node:assert/strict";
import { countStates } from "../public/scripts/participation-counts.js";
import { validateHistoricalNativeIndex, validateHistoricalNativeState, createHistoricalNativeReader,
  historicalNativeRows } from "../public/scripts/participation-historical-native.js";

function fixture() {
  const snapshot = { id: "a".repeat(32), state_code: "AL", year: 2018,
    election_type: "general", additive_with_other_snapshots: false, count_clock: null, timezone: null,
    source_url: "https://example.org/2018-general.zip", input_sha256: "c".repeat(64) };
  const row = { id: "b".repeat(32), snapshot_id: snapshot.id, state_code: "AL", year: 2018,
    measure: "ballots_cast", measure_literal: "BALLOTS CAST - TOTAL",
    county_literal: "Autauga", unit_literal: "Native source unit", unit_kind: "source_defined_unit",
    native_category: "STYLE 00001", count: { value: 0, status: "reported", literal: "0", source_status: "reported" },
    denominator: null, rate: null, geography_join: "unreviewed", cross_year_identity_approved: false,
    source: { url: snapshot.source_url, input_sha256: snapshot.input_sha256,
      native_fields: { contest: "BALLOTS CAST - TOTAL", value: 0 } } };
  const index = { contract: "participation.historical_native_counts.v1", years: [2018, 2020],
    jurisdictions: [...countStates], candidate_votes_used_as_ballots: false,
    alternative_sources_or_modes_summed: false, registration_stocks_are_denominators: false,
    outside_projection_years_are_not_classified_as_missing: true,
    states: { AL: { file: "states/AL.json.gz", records: 1, snapshots: [snapshot] } },
    decisions: countStates.flatMap(state_code => [2018, 2020].map(year => {
      const selected = state_code === "AL" && year === 2018;
      return { state_code, year, source_cells: Number(selected), ballot_cells: Number(selected),
        registration_cells: 0, status: selected ? "explicit_administrative_cells"
          : "no_explicit_administrative_cells_in_selected_components",
        turnout_rate_qualified: false, geography_join_qualified: false };
    })) };
  const state = { contract: index.contract, state_code: "AL", snapshots: [snapshot], records: [row] };
  const entry = { id: "participation-historical-native-counts",
    complete_download: { url: "https://example.org/complete.zip" },
    base_url: "https://example.org/immutable/", files: { "states/AL.json.gz": { bytes: 1, sha256: "d".repeat(64) } } };
  return { index, state, entry };
}

test("native zero is retained without promoting a rate, person count or historical boundary", () => {
  const { index, state } = fixture();
  validateHistoricalNativeIndex(index);
  validateHistoricalNativeState(state, "AL", index);
  assert.equal(state.records[0].count.value, 0);
  for (const [status, literal] of [["unknown", ""], ["withheld", "12.5"]]) {
    const data = structuredClone(state);
    data.records[0].count = { value: null, status, literal, source_status: status };
    validateHistoricalNativeState(data, "AL", index);
    assert.equal(data.records[0].count.value, null);
  }
});

test("reader rejects candidate substitution, numeric changes, rate promotion and wrong source frames", () => {
  for (const mutate of [
    row => { row.measure = "candidate_votes"; },
    row => { row.source.native_fields.contest = "President"; },
    row => { row.count.value = 1; },
    row => { row.count.value = false; },
    row => { row.rate = 0; },
    row => { row.denominator = 100; },
    row => { row.geography_join = "approved"; },
    row => { row.year = 2020; },
    row => { row.state_code = "TX"; },
  ]) {
    const { state, index } = fixture(); mutate(state.records[0]);
    assert.throws(() => validateHistoricalNativeState(state, "AL", index), /Unqualified/);
  }
  const { state, index } = fixture();
  state.records.push(state.records[0]); index.states.AL.records = 2;
  assert.throws(() => validateHistoricalNativeState(state, "AL", index), /Unqualified/);
});

test("all-state decisions cannot hide a missing jurisdiction or treat unevaluated years as missing", () => {
  for (const mutate of [
    index => { index.jurisdictions.pop(); },
    index => { index.years.push(2024); },
    index => { index.decisions[0].source_cells = 2; },
    index => { index.decisions[1] = index.decisions[0]; },
    index => { index.registration_stocks_are_denominators = true; },
    index => { index.outside_projection_years_are_not_classified_as_missing = false; },
  ]) {
    const { index } = fixture(); mutate(index);
    assert.throws(() => validateHistoricalNativeIndex(index), /Unqualified/);
  }
});

test("selection preserves snapshot, year, native category, county and measure instead of merging modes", () => {
  const { state } = fixture(), first = state.records[0];
  state.records.push({ ...first, snapshot_id: "e".repeat(32), count: { ...first.count, value: 10 } },
    { ...first, year: 2020 }, { ...first, county_literal: "" },
    { ...first, measure: "registration_stock", measure_literal: "REGISTERED VOTERS - TOTAL" });
  const scope = { snapshot: first.snapshot_id, year: 2018, county: "Autauga",
    measure: "ballots_cast", query: "style 00001" };
  assert.deepEqual(historicalNativeRows(state, scope), [first]);
  assert.equal(historicalNativeRows(state, { ...scope, county: "" }).length, 1);
  assert.equal(historicalNativeRows(state, { ...scope, query: "not supplied" }).length, 0);
});

test("cached reader retries failed state bodies and never fetches invented missing-state data", async () => {
  const { index, state, entry } = fixture();
  let catalogs = 0, bodies = 0;
  const reader = createHistoricalNativeReader({
    loadDataset: async () => { catalogs += 1; return { index, entry }; },
    checkedDatasetFile: async () => {
      bodies += 1;
      if (bodies === 1) throw new Error("checksum differs");
      return state;
    },
  });
  await assert.rejects(reader.loadState("AL"), /checksum/);
  assert.equal((await reader.loadState("AL")).state, state);
  assert.equal((await reader.loadState("AL")).state, state);
  assert.equal((await reader.loadState("NY")).state, null);
  assert.equal(catalogs, 1); assert.equal(bodies, 2);
});

test("a rejected index or non-HTTPS complete pointer cannot become loaded historical data", async () => {
  const { index, entry } = fixture();
  let calls = 0;
  const reader = createHistoricalNativeReader({
    loadDataset: async () => {
      calls += 1;
      return { entry, index: calls === 1 ? { ...index, years: [2026] } : index };
    },
  });
  await assert.rejects(reader.loadIndex(), /Unqualified/);
  assert.equal((await reader.loadIndex()).index, index);
  entry.complete_download.url = "javascript:alert(1)";
  const rejected = createHistoricalNativeReader({ loadDataset: async () => ({ index, entry }) });
  await assert.rejects(rejected.loadIndex(), /complete numerical download/);
});

test("historical navigation keeps at most four state bodies instead of retaining the entire corpus", async () => {
  const { index, state, entry } = fixture();
  const codes = ["AL", "AK", "AZ", "AR", "CA"], states = new Map();
  for (const code of codes) {
    const data = structuredClone(state);
    data.state_code = data.snapshots[0].state_code = data.records[0].state_code = code;
    states.set(code, data);
    index.states[code] = { file: `states/${code}.json.gz`, records: 1, snapshots: data.snapshots };
    entry.files[`states/${code}.json.gz`] = { bytes: 1, sha256: "d".repeat(64) };
    const decision = index.decisions.find(row => row.state_code === code && row.year === 2018);
    decision.source_cells = decision.ballot_cells = 1;
    decision.status = "explicit_administrative_cells";
  }
  let bodies = 0;
  const reader = createHistoricalNativeReader({
    loadDataset: async () => ({ index, entry }),
    checkedDatasetFile: async (_, declaration) => {
      bodies += 1;
      return states.get(declaration.file.slice(7, 9));
    },
  });
  for (const code of codes) await reader.loadState(code);
  assert.equal(bodies, 5);
  await reader.loadState("CA");
  assert.equal(bodies, 5);
  await reader.loadState("AL");
  assert.equal(bodies, 6);
});

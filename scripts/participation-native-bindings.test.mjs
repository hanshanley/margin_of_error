import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { canonicalObservation } from "./compile-participation-counts.mjs";
import { countModes } from "../public/scripts/participation-counts.js";
import { validateReferenceBindings } from "../public/scripts/participation-reference-bindings.js";
import { validateNativeShard, bindNativeGeometry, bindCountyReference,
  countyQualifier, countyCoverageMessage, rebindNativeCounts, validatedNativeSnapshot
} from "../public/scripts/participation-native-bindings.js";

const hash = "a".repeat(64);
test("missing county detail describes the selected source inventory after additions", () => {
  const rows = ["Bay County", "Isabella County", "Wayne County"].map(county => ({ county }));
  const message = countyCoverageMessage(rows);
  for (const row of rows) assert.ok(message.includes(row.county));
  assert.ok(message.includes("Missing counts are not zero"));
  assert.ok(!countyCoverageMessage(rows.slice(0, 2)).includes("Wayne County"));
  assert.ok(!countyCoverageMessage([{ county: "Other County" }]).includes("Bay County"));
});
function fixture() {
  const properties = { key: "MN|1", year: 2026, state_code: "MN", county: "Example",
    county_id: "native:1", unit_key: "1", unit: "Unit 1", ballots: 0,
    denominator: null, denominator_basis: "not_supplied", reported_pct: null, quality: [] };
  const observation = canonicalObservation(properties,
    { file: "original.json", sha256: hash, url: "https://example.org/input" }, "precinct/MN", 0);
  observation.geography.join = { status: "approved", reference_id: hash,
    feature_key: properties.key, evidence: "Existing accepted reference review" };
  const data = { contract: "participation.native_bindings.v1", id: "precinct/MN", state_code: "MN",
    geometry: { sha256: hash }, approval: {
      source_revision: "c4ccdf4d677974ea9068724367263dc59d9d0d88", existing_qualification_retained: true },
    rows: [{ key: properties.key, geometry_type: "Polygon", properties,
      observation, paths: { count: ["ballots"], denominator: ["denominator"], rate: ["reported_pct"] } }] };
  const geometry = { type: "FeatureCollection", features: [{
    type: "Feature", properties: { ...properties }, geometry: {
      type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] } }] };
  return { data, geometry };
}
test("count-only updates change returned counts without changing or rebuilding the approved geometry", () => {
  const { data, geometry } = fixture();
  validateNativeShard(data, "precinct/MN");
  assert.deepEqual(bindNativeGeometry(data, geometry, hash), geometry);
  data.rows[0].properties.ballots = 15;
  data.rows[0].observation.count.value = 15;
  data.rows[0].observation.view.ballots = 15;
  validateNativeShard(data, "precinct/MN");
  const result = bindNativeGeometry(data, geometry, hash);
  assert.equal(result.features[0].properties.ballots, 15);
  assert.equal(geometry.features[0].properties.ballots, 0);
  assert.equal(result.features[0].geometry, geometry.features[0].geometry);
  assert.equal(result.features[0].properties.reported_pct, null);
});
test("runtime canonical counts replace native map properties only under the existing identity and join", () => {
  const { data, geometry } = fixture();
  const changed = structuredClone(data.rows[0].observation);
  changed.count.value = 25;
  changed.view.ballots = 25;
  changed.source_clock.literal = "November 14; timezone not supplied";
  changed.view.source_update_label = changed.source_clock.literal;
  changed.source.input_sha256 = "b".repeat(64);
  changed.source.fields = changed.view;
  const rebound = rebindNativeCounts(data, { records: [changed] });
  const mapped = bindNativeGeometry(rebound, geometry, hash);
  assert.equal(mapped.features[0].properties.ballots, 25);
  assert.equal(rebound.rows[0].observation.view.source_update_label, changed.source_clock.literal);
  assert.equal(geometry.features[0].properties.ballots, 0);
  for (const mutate of [
    row => { row.id = "b".repeat(32); },
    row => { row.geography.join.feature_key = "MN|2"; },
    row => { row.view.unit = "Different unit"; row.source.fields = row.view; },
    row => { row.election.qualification = "collector_context"; },
  ]) {
    const invalid = structuredClone(changed);
    mutate(invalid);
    assert.throws(() => rebindNativeCounts(data, { records: [invalid] }),
      /identity|geography|qualification|label/);
  }
});
test("atomic native projections retain their reviewed IDs instead of joining independently keyed table rows", () => {
  const { data, geometry } = fixture();
  data.rows[0].properties.ballots = 25;
  data.rows[0].observation.count.value = 25;
  data.rows[0].observation.view.ballots = 25;
  const runtime = { version: "b".repeat(64), runtime_commit: "c".repeat(40),
    native: { version: "d".repeat(64) }, counts: { version: "e".repeat(64) } };
  const native = { automatic_runtime: runtime, entry: runtime.native };
  const counts = { automatic_runtime: structuredClone(runtime), entry: runtime.counts };
  const result = validatedNativeSnapshot(data, "precinct/MN", native, counts);
  assert.equal(result.rows[0].observation.id, data.rows[0].observation.id);
  assert.equal(bindNativeGeometry(result, geometry, hash).features[0].properties.ballots, 25);
  for (const mutate of [
    source => { source.automatic_runtime = null; },
    source => { source.automatic_runtime.version = "f".repeat(64); },
    source => { source.automatic_runtime.runtime_commit = "f".repeat(40); },
    source => { source.entry = { version: "f".repeat(64) }; },
  ]) {
    const invalid = structuredClone(counts); mutate(invalid);
    assert.throws(() => validatedNativeSnapshot(data, "precinct/MN", native, invalid),
      /verified runtime snapshot/);
  }
  const invalid = structuredClone(data);
  invalid.rows[0].observation.geography.join.reference_id = "f".repeat(64);
  assert.throws(() => validatedNativeSnapshot(invalid, "precinct/MN", native, counts),
    /binding differs/);
});
test("accepted native fallback retains independently sourced counts and rejects mixed automatic data", () => {
  const { data, geometry } = fixture();
  const accepted = { automatic_runtime: null };
  assert.equal(bindNativeGeometry(
    validatedNativeSnapshot(data, "precinct/MN", accepted, accepted), geometry, hash)
    .features[0].properties.ballots, 0);
  assert.throws(() => validatedNativeSnapshot(data, "precinct/MN",
    { automatic_runtime: { version: "b".repeat(64) } }, accepted),
  /verified runtime snapshot/);
});
let loaderFixtureId = 0;
function referenceFixture(ballots) {
  const observation = canonicalObservation({
    year: 2026, state_code: "MN", county: "Example", county_id: "native:1",
    geography_level: "reporting_unit", unit: "Unit 1", unit_key: "native:unit-1",
    ballots, denominator: null, denominator_basis: "not_supplied", reported_pct: null,
    maps_approved: false, unique_voter_count_qualified: false, quality: [],
    automatic_source_refresh: true, complete_download_url: "https://example.org/original.zip",
  }, { file: "original.json", sha256: hash, url: "https://example.org/input" }, "native-MN", 0);
  const declaration = { file: "states/MN.json.gz", bytes: 100, sha256: hash, records: 1 };
  const counts = { contract: "participation.count_snapshot.v1", year: 2026, state_code: "MN",
    records: [observation], views: Object.fromEntries(countModes.map(mode => [mode, {
      qualified: true, holds: [], counties: [], nongeographic: [],
      precincts: ["available", "official"].includes(mode) ? [observation.id] : [],
    }])) };
  const review = { reviewed: true, review_id: "reference-review", rates_approved: false,
    scope: "public_authoritative_reference_context", matching: "exact_literal_only",
    legal_election_boundaries_certified: false, source_observations_preserved: true,
    reference_label: "Public reference; not certified election-day boundaries",
    geometry_retrieved_at_utc: "2026-11-14T07:29:17Z",
    omitted_units_note: "Omitted units are held, not zero." };
  const properties = { ...observation.view, key: "Unit 1", maps_approved: true,
    reference_context_only: true, legal_election_boundaries_certified: false,
    boundary_label: review.reference_label, registered: null,
    source_count_observation_id: observation.id, source_update_label: observation.source_clock.literal,
    source_update_timezone: observation.source_clock.timezone };
  const data = { contract: "participation.reference_bindings.v1", id: "precinct/MN", state_code: "MN",
    source_counts: { ...declaration, source_id: observation.source.id, source_rows: 1 },
    geometry: { file: "geometry.json", sha256: hash }, review, held_rows: [],
    rows: [{ key: "Unit 1", geometry_type: "Polygon",
      observation: structuredClone(observation), properties }] };
  const geometry = fixture().geometry;
  geometry.features[0].properties = { ...properties };
  return { data, geometry, counts, declaration };
}
async function loaderFixture(options = {}) {
  const key = `participation-native-loader-test-${loaderFixtureId++}`;
  const accepted = options.reference ? referenceFixture(0) : fixture();
  const current = options.reference ? referenceFixture(25) : fixture();
  current.data.rows[0].properties.ballots = 25;
  current.data.rows[0].observation.count.value = 25;
  current.data.rows[0].observation.view.ballots = 25;
  const runtime = { version: "b".repeat(64), runtime_commit: "c".repeat(40),
    native: { version: "d".repeat(64) }, counts: { version: "e".repeat(64) } };
  const state = { rejected: false, geometryBases: [], countStateLoads: 0, canonicalBases: [] };
  state.loadDataset = async () => {
    const automatic = !state.rejected;
    return { entry: { version: automatic ? runtime.native.version : "f".repeat(64),
      base_url: automatic ? "https://example.org/current/" : "https://example.org/accepted/" },
    index: { contract: "participation.native_index.v1", layers: {
      "precinct/MN": { file: "native.json", features: 1 } } },
    automatic_runtime: automatic ? runtime : null };
  };
  state.loadCountIndex = async () => ({
    entry: { version: runtime.counts.version,
      base_url: state.rejected ? "https://example.org/accepted/" : "https://example.org/current/" },
    index: { states: { MN: current.declaration } },
    automatic_runtime: state.rejected || options.mixedRuntime ? null : runtime,
  });
  state.checkedDatasetFile = async (base, declaration) => {
    if (declaration.file === "native.json")
      return structuredClone(base.includes("/accepted/") ? accepted.data : current.data);
    if (declaration.file === "states/MN.json.gz") {
      state.canonicalBases.push(base);
      const counts = structuredClone(base.includes("/accepted/") ? accepted.counts : current.counts);
      if (base.includes("/current/")) {
        if (options.corruptReference) counts.records[0].source.input_sha256 = "f".repeat(64);
        if (options.corruptCountShard) counts.records[0].count.status = "unknown";
      }
      return counts;
    }
    state.geometryBases.push(base);
    if (options.corruptGeometry && base.includes("/current/"))
      throw new Error("Native geometry checksum differs");
    if (options.corruptAccepted && base.includes("/accepted/"))
      throw new Error("Accepted geometry checksum differs");
    return structuredClone(accepted.geometry);
  };
  state.loadCountState = async () => {
    state.countStateLoads++;
    if (!options.reference) throw new Error("Unexpected ID join");
    const counts = structuredClone(state.rejected ? accepted.counts : current.counts);
    for (const row of counts.records) {
      row.view.accepted_complete_download_url = row.view.complete_download_url;
      row.view.complete_download_url = "https://example.org/current-runtime.zip";
    }
    return counts;
  };
  state.rejectCountRuntime = () => { state.rejected = true; };
  globalThis[Symbol.for(key)] = state;
  const toURL = source => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
  const dependencies = toURL(`
    const state = globalThis[Symbol.for(${JSON.stringify(key)})];
    export { validateCountObservation, validateCountShard } from ${JSON.stringify(
      new URL("../public/scripts/participation-counts.js", import.meta.url).href)};
    export const loadDataset = (...args) => state.loadDataset(...args);
    export const checkedDatasetFile = (...args) => state.checkedDatasetFile(...args);
    export const loadCountIndex = (...args) => state.loadCountIndex(...args);
    export const loadCountState = (...args) => state.loadCountState(...args);
    export const loadAcceptedCountState = loadCountState;
    export const rejectCountRuntime = (...args) => state.rejectCountRuntime(...args);
    export { validateReferenceBindings, bindReferenceGeometry } from ${JSON.stringify(
      new URL("../public/scripts/participation-reference-bindings.js", import.meta.url).href)};
  `);
  const source = readFileSync(new URL(
    "../public/scripts/participation-native-bindings.js", import.meta.url), "utf8")
    .replaceAll(/from "\.\/participation-(?:dataset|counts|reference-bindings)\.js"/g,
      `from ${JSON.stringify(dependencies)}`);
  const loader = await import(toURL(source));
  delete globalThis[Symbol.for(key)];
  return { loader, state, accepted, current };
}
test("reference loader validates canonical facts before current-download presentation decoration", async () => {
  const { loader, state, current } = await loaderFixture({ reference: true });
  validateReferenceBindings(current.data, "precinct/MN", current.counts, current.declaration);
  const displayed = await state.loadCountState();
  assert.equal(displayed.records[0].view.complete_download_url, "https://example.org/current-runtime.zip");
  assert.throws(() => validateReferenceBindings(
    current.data, "precinct/MN", displayed, current.declaration), /changed a source observation/);
  state.countStateLoads = 0;
  const result = await loader.loadBoundNative("precinct/MN");
  assert.equal(result.data.features[0].properties.ballots, 25);
  assert.equal(result.binding.rows[0].observation.view.complete_download_url,
    "https://example.org/original.zip");
  assert.deepEqual(result.binding, current.data);
  assert.equal(state.rejected, false);
  assert.equal(state.countStateLoads, 0);
  assert.deepEqual(state.canonicalBases, ["https://example.org/current/"]);
});
test("reference loader refuses mixed snapshots and corrupted canonical facts before accepted fallback", async () => {
  for (const options of [{ mixedRuntime: true }, { corruptReference: true },
    { corruptCountShard: true }, { corruptGeometry: true }]) {
    const { loader, state, accepted } = await loaderFixture({ reference: true, ...options });
    const result = await loader.loadBoundNative("precinct/MN");
    assert.equal(result.data.features[0].properties.ballots, 0);
    assert.deepEqual(result.binding, accepted.data);
    assert.equal(state.rejected, true);
    assert.equal(state.countStateLoads, 0);
    assert.equal(state.canonicalBases.at(-1), "https://example.org/accepted/");
    assert.equal(state.geometryBases.at(-1), "https://example.org/accepted/");
  }
  const { loader } = await loaderFixture({
    reference: true, corruptGeometry: true, corruptAccepted: true,
  });
  await assert.rejects(loader.loadBoundNative("precinct/MN"), /Accepted geometry checksum differs/);
});
test("native loader consumes the atomic projection without a canonical table-ID join", async () => {
  const { loader, state } = await loaderFixture();
  const result = await loader.loadBoundNative("precinct/MN");
  assert.equal(result.data.features[0].properties.ballots, 25);
  assert.equal(result.verified_geometry_sha256, hash);
  assert.equal(state.countStateLoads, 0);
  assert.equal(state.rejected, false);
  assert.deepEqual(state.geometryBases, ["https://example.org/current/"]);
});
test("native loader restarts with the accepted snapshot and its own geometry after rejection", async () => {
  for (const options of [{ mixedRuntime: true }, { corruptGeometry: true }]) {
    const { loader, state, accepted } = await loaderFixture(options);
    const result = await loader.loadBoundNative("precinct/MN");
    assert.deepEqual(result.data, accepted.geometry);
    assert.equal(result.binding.rows[0].observation.count.value, 0);
    assert.equal(state.rejected, true);
    assert.equal(state.countStateLoads, 0);
    assert.equal(state.geometryBases.at(-1), "https://example.org/accepted/");
  }
  const { loader } = await loaderFixture({ mixedRuntime: true, corruptAccepted: true });
  await assert.rejects(loader.loadBoundNative("precinct/MN"), /Accepted geometry checksum differs/);
});
test("hash, inventory, state, duplicate keys and denominator promotion cannot qualify a native binding", () => {
  for (const mutate of [
    ({ data }) => { data.state_code = "NM"; },
    ({ data }) => { data.rows.push(data.rows[0]); },
    ({ data }) => { data.rows[0].paths.count = ["__proto__", "x"]; },
    ({ data }) => { data.rows[0].observation.geography.join.reference_id = "b".repeat(64); },
    ({ data }) => { data.rows[0].properties.ballots = null; },
    ({ data }) => { data.rows[0].properties.reported_pct = 1; },
  ]) {
    const current = fixture(); mutate(current);
    assert.throws(() => validateNativeShard(current.data, "precinct/MN"), /Unqualified|differs/);
  }
  const { data, geometry } = fixture();
  assert.throws(() => bindNativeGeometry(data, geometry, "b".repeat(64)), /differs/);
  geometry.features[0].properties.key = "MN|2";
  assert.throws(() => bindNativeGeometry(data, geometry, hash), /differs/);
});
test("county bindings preserve identity and scope but do not hardcode old numerical totals", () => {
  const row = { state_code: "MN", county_id: "native:1", county: "Example", ballots: 10,
    geography_level: "county", county_fips: "27001", reference_geometry: { sha256: hash } };
  const collection = { features: [{ properties: {
    key: "27001", state_code: "MN", name: "Example County", boundary_year: 2026 } }] };
  const binding = { sha256: hash, features: 1, feature_keys: ["27001"],
    feature_scopes: { "27001": { state_code: "MN", name: "Example County", boundary_year: 2026 } },
    rows: [{ feature_key: "27001", county_id: row.county_id, qualifier: countyQualifier(row) }] };
  row.ballots = 20;
  assert.equal(bindCountyReference([row], collection, row.reference_geometry, binding).get("27001").ballots, 20);
  assert.throws(() => bindCountyReference([{ ...row, geography_level: "municipality" }],
    collection, row.reference_geometry, binding), /differs/);
  collection.features[0].properties.boundary_year = 2024;
  assert.throws(() => bindCountyReference([row], collection, row.reference_geometry, binding), /differ/);
});
test("an unmatched reference remains unknown rather than copying an old geometry zero", () => {
  const { data, geometry } = fixture(), row = data.rows[0];
  row.properties.ballots = null;
  row.observation.count.value = null;
  row.observation.count.status = "unknown";
  row.observation.geography.join.status = "unmatched";
  validateNativeShard(data, "precinct/MN");
  assert.equal(bindNativeGeometry(data, geometry, hash).features[0].properties.ballots, null);
  row.properties.ballots = 0;
  row.observation.count.value = 0;
  row.observation.count.status = "reported";
  assert.throws(() => validateNativeShard(data, "precinct/MN"), /binding differs/);
});

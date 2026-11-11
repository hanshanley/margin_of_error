import test from "node:test";
import assert from "node:assert/strict";
import { canonicalObservation } from "./compile-participation-counts.mjs";
import { validateNativeShard, bindNativeGeometry, bindCountyReference,
  countyQualifier } from "../public/scripts/participation-native-bindings.js";

const hash = "a".repeat(64);
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

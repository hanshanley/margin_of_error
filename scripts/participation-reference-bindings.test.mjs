import test from "node:test";
import assert from "node:assert/strict";
import { canonicalObservation } from "./compile-participation-counts.mjs";
import { validateReferenceBindings, bindReferenceGeometry } from "../public/scripts/participation-reference-bindings.js";

const hash = "a".repeat(64), referenceHash = "b".repeat(64);
function fixture() {
  const native = (unit, ordinal, ballots) => canonicalObservation({
    year: 2026, state_code: "KY", county: "Jefferson", county_id: "additional:KY:21111",
    geography_level: "reporting_unit", unit, unit_key: "jefferson-native:" + unit,
    ballots, denominator: null, denominator_basis: "not_supplied", reported_pct: null,
    maps_approved: false, unique_voter_count_qualified: false, quality: [],
  }, { file: "original.json", sha256: hash, url: "https://example.org/input" }, "native-KY", ordinal);
  const original = native("A107", 0, 0), held = native("V120 MID", 1, 23);
  const declaration = { file: "states/KY.json.gz", bytes: 100, sha256: hash };
  const source = { contract: "participation.count_snapshot.v1", state_code: "KY",
    records: [original, held] };
  const review = { reviewed: true, review_id: "independent-reference-review", rates_approved: false,
    scope: "public_authoritative_reference_context", matching: "exact_literal_only",
    legal_election_boundaries_certified: false, source_observations_preserved: true,
    reference_label: "Official reference retrieved November 14; not certified election-day boundaries",
    geometry_retrieved_at_utc: "2026-11-14T07:29:17Z",
    omitted_units_note: "Omitted units are held/unmapped, not zero; every source count remains available." };
  const properties = { ...original.view, key: "A107", maps_approved: true,
    reference_context_only: true, legal_election_boundaries_certified: false,
    boundary_label: review.reference_label, registered: null,
    source_count_observation_id: original.id,
    source_update_label: original.source_clock.literal,
    source_update_timezone: original.source_clock.timezone };
  const data = { contract: "participation.reference_bindings.v1", id: "precinct/KY", state_code: "KY",
    source_counts: { ...declaration, source_id: original.source.id, source_rows: 2 },
    geometry: { sha256: referenceHash }, review,
    rows: [{ key: "A107", geometry_type: "Polygon", observation: structuredClone(original), properties }],
    held_rows: [{ observation_id: held.id, native_label: "V120 MID", reason: "no exact literal match" }] };
  const geometry = { type: "FeatureCollection", features: [{ type: "Feature", properties: { key: "A107", ballots: 999 },
    geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] } }] };
  return { data, geometry, source, declaration };
}

test("separate reference qualification preserves the complete native observation and true zero", () => {
  const { data, geometry, source, declaration } = fixture();
  const nativeBefore = structuredClone(source);
  validateReferenceBindings(data, "precinct/KY", source, declaration);
  const result = bindReferenceGeometry(data, geometry, referenceHash);
  assert.equal(result.features[0].properties.ballots, 0);
  assert.equal(result.features[0].properties.reported_pct, null);
  assert.equal(result.features[0].geometry, geometry.features[0].geometry);
  assert.equal(geometry.features[0].properties.ballots, 999);
  assert.deepEqual(source, nativeBefore);
  assert.equal(source.records[0].view.maps_approved, false);
});

test("source checksum, count mirrors, clock and literal identity cannot be changed together", () => {
  for (const mutate of [
    ({ data }) => { data.source_counts.sha256 = "c".repeat(64); },
    ({ data }) => {
      data.rows[0].observation.count.value = 6;
      data.rows[0].observation.view.ballots = 6;
      data.rows[0].properties.ballots = 6;
    },
    ({ data }) => { data.rows[0].properties.source_update_label = "fabricated"; },
    ({ data }) => { data.rows[0].key = data.rows[0].properties.key = "A108"; },
  ]) {
    const f = fixture(); mutate(f);
    assert.throws(() => validateReferenceBindings(f.data, "precinct/KY", f.source, f.declaration));
  }
});

test("source suffixes cannot be normalized into reference keys", () => {
  const f = fixture(), original = f.source.records[1];
  f.data.rows[0].observation = structuredClone(original);
  f.data.rows[0].key = "V120";
  f.data.rows[0].properties.unit = "V120";
  assert.throws(() => validateReferenceBindings(f.data, "precinct/KY", f.source, f.declaration));
});

test("rate, legal-boundary and unique-person promotions remain disallowed", () => {
  for (const mutate of [
    ({ data }) => { data.review.legal_election_boundaries_certified = true; },
    ({ data }) => { data.rows[0].properties.reported_pct = 1; },
    ({ data }) => { data.rows[0].properties.unique_voter_count_qualified = true; },
    ({ data }) => { data.rows[0].properties.registered = 100; },
    ({ data }) => { data.rows[0].properties.reference_context_only = false; },
    ({ data }) => { data.rows[0].properties.participation_measure_label = "Certified unique voters"; },
    ({ data }) => { data.rows[0].properties.quality = ["Fabricated source qualification"]; },
  ]) {
    const f = fixture(); mutate(f);
    assert.throws(() => validateReferenceBindings(f.data, "precinct/KY", f.source, f.declaration));
  }
});

test("held coverage, duplicate keys and mismatched reference bodies are rejected", () => {
  for (const mutate of [
    ({ data }) => { data.held_rows = []; },
    ({ data }) => { data.held_rows.push(data.held_rows[0]); },
    ({ data }) => { data.held_rows[0].native_label = "V120"; },
    ({ data }) => { data.rows.push(data.rows[0]); },
  ]) {
    const f = fixture(); mutate(f);
    assert.throws(() => validateReferenceBindings(f.data, "precinct/KY", f.source, f.declaration));
  }
  const { data, geometry } = fixture();
  assert.throws(() => bindReferenceGeometry(data, geometry, hash));
  geometry.features[0].properties.key = "unknown";
  assert.throws(() => bindReferenceGeometry(data, geometry, referenceHash));
});

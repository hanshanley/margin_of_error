import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gzipSync, gunzipSync } from "node:zlib";
import { qualifyCountyBindings, readDataset } from "./extend-participation-county-bindings.mjs";
import { encoded, digest } from "./compile-participation-counts.mjs";

const root = process.env.COUNTY_BINDING_INPUT || "data/participation-county-bindings/20261111-nj-01";
const recipe = JSON.parse(readFileSync(`${root}/recipe.json`));
const inputs = Object.fromEntries(["reference.json", "previous-review.json", "native-facts.json"]
  .map(name => [name, readFileSync(`${root}/${name}`)]));
const counts = readDataset(process.env.COUNTY_BINDING_COUNTS || "../new-jersey-gap-count-dataset-20261111-01");
const native = readDataset(process.env.COUNTY_BINDING_NATIVE || "../new-jersey-binding-native-baseline-01");
const qualify = (c = counts, n = native, i = inputs, r = recipe) => qualifyCountyBindings(c, n, i, r, "a".repeat(40));

test("two new whole-county identities reuse all unchanged reference features and nineteen exact accepted source rows", () => {
  const result = qualify(), queries = result.queries;
  assert.equal(queries.filter(row => row.disposition.startsWith("retained")).length, 19);
  assert.deepEqual(queries.filter(row => row.disposition.startsWith("qualified")).map(row => row.count).sort(),
    [213051, 225368]);
  const before = JSON.parse(gunzipSync(counts["states/NJ.json.gz"]));
  const after = JSON.parse(gunzipSync(result.counts.files["states/NJ.json.gz"]));
  assert.deepEqual(after.views, before.views);
  for (const [i, row] of after.records.entries()) {
    const old = before.records[i], comparable = structuredClone(row);
    comparable.geography.join = old.geography.join;
    for (const key of ["maps_approved", "reference_geometry"])
      if (Object.hasOwn(old.view, key)) comparable.view[key] = old.view[key];
      else delete comparable.view[key];
    assert.deepEqual(comparable, old);
    assert.equal(row.count.value, old.count.value);
    assert.deepEqual(row.denominator, old.denominator);
  }
  for (const [name, body] of Object.entries(counts))
    if (!["index.json", "states/NJ.json.gz"].includes(name)) assert.ok(result.counts.files[name].equals(body));
  for (const [name, body] of Object.entries(native))
    if (name !== "index.json") assert.ok(result.native.files[name].equals(body));
});

test("a stale exact-record-hash oracle cannot approve an old county row", () => {
  const changed = JSON.parse(inputs["previous-review.json"]);
  changed.observations.find(row => row.state_code === "NJ").source_record_sha256 = "b".repeat(64);
  const body = encoded(changed);
  assert.throws(() => qualify(counts, native, { ...inputs, "previous-review.json": body },
    { ...recipe, previous_review_sha256: digest(body) }), /exact-record-hash/);
});

test("missing county scope, undeclared source identities and changed reference bytes remain held", () => {
  const changed = JSON.parse(gunzipSync(counts["states/NJ.json.gz"]));
  changed.records.find(row => row.source.id === recipe.new_source_ids[0]).geography.level = "municipality";
  assert.throws(() => qualify({ ...counts, "states/NJ.json.gz": gzipSync(encoded(changed)) }), /county/);
  assert.throws(() => qualify(counts, native, inputs, { ...recipe, new_source_ids: [] }), /Unregistered/);
  const bad = Buffer.from(inputs["reference.json"]); bad[bad.length - 1] = 32;
  assert.throws(() => qualify(counts, native, { ...inputs, "reference.json": bad }), /Pinned/);
  assert.throws(() => qualify(counts, native, inputs, { ...recipe, modes: ["mail_returned"] }), /early\/returned/);
});

test("qualified bindings cannot overwrite any prior native mode or promote missing rates", () => {
  const first = qualify();
  assert.throws(() => qualify(first.counts.files, first.native.files), /overwrite/);
  const after = JSON.parse(gunzipSync(first.counts.files["states/NJ.json.gz"]));
  for (const row of after.records.filter(row => recipe.new_source_ids.includes(row.source.id))) {
    assert.equal(row.view.reported_pct, null);
    assert.equal(row.denominator, null);
    assert.equal(row.reporting_status.complete, null);
    assert.equal(row.geography.join.status, "approved");
  }
});

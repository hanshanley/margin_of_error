import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gunzipSync, gzipSync } from "node:zlib";
import { encoded } from "./compile-participation-counts.mjs";
import { readDataset, qualifyPartialCountyBindings } from "./extend-participation-county-bindings.mjs";
import { bindCountyReference, countyQualifier } from "../public/scripts/participation-native-bindings.js";

const root = process.env.UTAH_EXTENSION_INPUTS;
const counts = readDataset(process.env.UTAH_EXTENSION_COUNTS);
const native = readDataset(process.env.UTAH_EXTENSION_NATIVE);
const recipe = JSON.parse(readFileSync(`${root}/recipe.json`));
const inputs = Object.fromEntries(["reference.json", "previous-review.json", "native-facts.json"]
  .map(name => [name, readFileSync(`${root}/${name}`)]));
const qualify = (files = counts) => qualifyPartialCountyBindings(files, native, inputs, recipe, "f".repeat(40));
const before = JSON.parse(gunzipSync(counts["states/UT.json.gz"]));
const scientific = value => {
  const row = structuredClone(value);
  delete row.geography.join;
  delete row.view.maps_approved;
  delete row.view.reference_geometry;
  return row;
};

test("partial county qualification retains 19 accepted observations, adds four and leaves six holds gray", () => {
  const result = qualify(), after = JSON.parse(gunzipSync(result.counts.files["states/UT.json.gz"]));
  assert.deepEqual(after.records.map(scientific), before.records.map(scientific));
  assert.equal(result.queries.filter(row => row.disposition.startsWith("retained")).length, 19);
  assert.equal(result.queries.filter(row => row.disposition.startsWith("qualified_new")).length, 4);
  const held = result.queries.filter(row => row.disposition.startsWith("held_"));
  assert.equal(held.length, 6);
  assert.ok(held.every(row => row.count === null && row.rate === null));
  const records = new Map(after.records.map(row => [row.id, row]));
  assert.ok(held.every(row => records.get(row.id).view.maps_approved === false
    && records.get(row.id).geography.join.status !== "approved"));
  const index = JSON.parse(result.native.files["index.json"]);
  const geometry = JSON.parse(inputs["reference.json"]);
  for (const mode of recipe.modes) {
    const rows = after.views[mode].counties.map(id => records.get(id).view);
    assert.equal(rows.length, 29);
    assert.equal(rows.filter(row => row.ballots !== null).length, 23);
    assert.equal(bindCountyReference(rows, geometry, result.reference, index.county_bindings.UT[mode]).size, 29);
  }
  for (const mode of ["in_person_early", "mail_returned"]) {
    assert.deepEqual(after.views[mode], before.views[mode]);
    assert.deepEqual(index.county_bindings.UT[mode], JSON.parse(native["index.json"]).county_bindings.UT[mode]);
  }
  for (const [name, body] of Object.entries(native))
    if (name !== "index.json") assert.ok(result.native.files[name].equals(body));
});

test("an old accepted value cannot change under contextual qualification", () => {
  const changed = structuredClone(before);
  const row = changed.records.find(row => row.view.county === "Beaver County");
  row.count.value += 1;
  row.view.ballots += 1;
  assert.throws(() => qualify({ ...counts, "states/UT.json.gz": gzipSync(encoded(changed)) }), /oracle differs/);
});

test("unregistered held counts and new-source fractions cannot be promoted by a partial binding", () => {
  const changed = structuredClone(before);
  const row = changed.records.find(row => row.view.county === "Daggett County");
  row.count.value = row.view.ballots = 1;
  row.count.status = "reported";
  assert.throws(() => qualify({ ...counts, "states/UT.json.gz": gzipSync(encoded(changed)) }), /unreviewed count/);
  const promoted = structuredClone(before);
  promoted.records.find(row => row.source.id === recipe.new_source_ids[0]).view.reported_pct = 0;
  assert.throws(() => qualify({ ...counts, "states/UT.json.gz": gzipSync(encoded(promoted)) }));
});

test("missing fractions and altered scope remain rejected by the unchanged public binder", () => {
  const result = qualify(), after = JSON.parse(gunzipSync(result.counts.files["states/UT.json.gz"]));
  const index = JSON.parse(result.native.files["index.json"]), binding = index.county_bindings.UT.official;
  const records = new Map(after.records.map(row => [row.id, row]));
  const rows = after.views.official.counties.map(id => records.get(id).view);
  const changed = structuredClone(rows);
  changed[0].denominator_basis = "different_population";
  assert.notDeepEqual(countyQualifier(changed[0]), countyQualifier(rows[0]));
  assert.throws(() => bindCountyReference(changed, JSON.parse(inputs["reference.json"]), result.reference, binding),
    /source scope/);
});

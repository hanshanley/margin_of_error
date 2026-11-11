import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { pointFor2002, pointOnlyGroups, validatePointSource } from "../public/scripts/participation-cps-2002.js";

const source = JSON.parse(readFileSync(new URL("../data/participation-cps-2002/20261111-01/points.json", import.meta.url)));

test("adult and citizen overall points keep their own denominator", () => {
  const data = validatePointSource(source);
  assert.equal(pointFor2002(data, "California", "Total").rate, 34.2);
  assert.equal(pointFor2002(data, "California", "Total", true).rate, 42.5);
  assert.equal(pointFor2002(data, "California", "Male", true).rate, null);
});

test("old race labels cannot be aliased to race-alone or combined categories", () => {
  assert.equal(pointFor2002(source, "California", "White alone").sourceKey, "");
  assert.equal(pointFor2002(source, "California", "White alone or in combination").sourceKey, "");
  assert.ok(pointFor2002(source, "California", pointOnlyGroups[0]).sourceKey);
  assert.ok(pointFor2002(source, "California", pointOnlyGroups[3]).sourceKey);
});

test("conflicting Pennsylvania totals and defective national population remain withheld", () => {
  assert.equal(pointFor2002(source, "Pennsylvania", "Total").rate, null);
  assert.equal(pointFor2002(source, "Pennsylvania", "Total", true).rate, null);
  assert.match(pointFor2002(source, "Pennsylvania", "Total").text, /conflicting/);
  assert.equal(pointFor2002(source, "United States (including D.C.)", pointOnlyGroups[1]).rate, null);
});

test("suppression remains unavailable and no source margin is inferred", () => {
  const native = source.records.find(row => row.decision === "withheld_native_missing_or_suppressed_rate");
  const group = native.native.role === "age" ? native.native.native_label.slice(1)
    : pointOnlyGroups.find(label => label.startsWith(native.native.native_label.slice(1) + " ("))
      || native.native.native_label.slice(1);
  assert.equal(pointFor2002(source, native.native.geography, group).rate, null);
  const point = pointFor2002(source, "California", "Total");
  assert.match(point.text, /margin not qualified/);
  assert.equal("moe" in point, false);
});

test("changed precision, selected defects and frame substitutions are rejected", () => {
  for (const change of [
    row => { row.standard_error = 1; },
    row => { row.native.native_flags = ["unsupported"]; },
    row => { row.population_frame = "cvap"; },
  ]) {
    const changed = structuredClone(source);
    change(changed.records.find(row => row.decision === "selected_reported_point_only"));
    assert.throws(() => validatePointSource(changed), /differs/);
  }
});

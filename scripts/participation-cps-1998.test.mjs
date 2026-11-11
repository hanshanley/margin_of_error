import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { load1998Points, pointFor1998, pointOnly1998Groups, validate1998Points } from "../public/scripts/participation-cps-1998.js";
import { pointFor2002, pointOnlyGroups } from "../public/scripts/participation-cps-2002.js";

const body = readFileSync(new URL("../data/participation-cps-1998/20261111-01/points.json", import.meta.url));
const source = JSON.parse(body);
const source2002 = JSON.parse(readFileSync(new URL("../data/participation-cps-2002/20261111-01/points.json", import.meta.url)));

test("1998 voting and printed SE use source adults, not citizen turnout or a margin", () => {
  const point = pointFor1998(validate1998Points(source), "United States (including D.C.)", "Total");
  assert.equal(point.rate, 41.9);
  assert.equal(point.standardError, 0.2);
  assert.match(point.text, /source SE 0.20 pp \(not a margin\)/);
  assert.equal("moe" in point, false);
});

test("small-base suppression stays unavailable rather than becoming zero from dot counts", () => {
  const point = pointFor1998(source, "Virginia", "Hispanic (any race)");
  assert.equal(point.rate, null);
  assert.equal(point.standardError, null);
  assert.ok(point.sourceKey);
  assert.match(point.text, /base too small/);
});

test("non-Hispanic API is distinct from 2002 all-API and modern race-alone groups", () => {
  assert.ok(pointFor1998(source, "California", pointOnly1998Groups[0]).sourceKey);
  assert.equal(pointFor2002(source2002, "California", pointOnly1998Groups[0]).sourceKey, "");
  assert.equal(pointFor1998(source, "California", pointOnlyGroups[4]).sourceKey, "");
  assert.equal(pointFor1998(source, "California", "White alone").sourceKey, "");
  assert.equal(pointFor1998(source, "California", "18 to 24").sourceKey, "");
});

test("shared legacy labels preserve old 2002 choices without creating modern aliases", () => {
  const shared = pointOnlyGroups[0];
  assert.ok(pointFor1998(source, "California", shared).sourceKey);
  assert.deepEqual(pointFor2002(source2002, "California", shared),
    pointFor2002(source2002, "California", "White (2002 native category)"));
});

test("native defects and point-versus-precision holds are not repaired", () => {
  const nj = source.records.find(row => row.geography === "NEW JERSEY" && row.native_group === "Male");
  const nm = source.records.find(row => row.geography === "NEW MEXICO" && row.native_group === "Total");
  assert.equal(nj.measures.citizen_adults.raw_percentage, "900.");
  assert.equal(nm.measures.citizen_adults.raw_standard_error, "0.8.");
  for (const change of [
    row => { row.measures.citizen_adults.selected_percentage = "90.0"; },
    row => { row.population_frame = "cvap"; },
    row => { row.measures.voted.derived_interval = [0, 100]; },
  ]) {
    const changed = structuredClone(source);
    change(changed.records.find(row => row.source_key === nj.source_key));
    assert.throws(() => validate1998Points(changed), /differs/);
  }
});

test("loader verifies every source byte and rejects unavailable or corrupt responses", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(body);
    assert.equal((await load1998Points()).records.length, 468);
    globalThis.fetch = async () => new Response("unavailable", { status: 503 });
    await assert.rejects(load1998Points, /unavailable/);
    globalThis.fetch = async () => new Response("{}");
    await assert.rejects(load1998Points, /checksum differs/);
  } finally {
    globalThis.fetch = original;
  }
});

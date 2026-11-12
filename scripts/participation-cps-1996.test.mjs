import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { load1996Points, pointFor1996, validate1996Points } from "../public/scripts/participation-cps-1996.js";

const body = readFileSync(new URL("../data/participation-cps-1996/20261112-01/points.json", import.meta.url));
const source = JSON.parse(body);

test("adult/citizen points and explicit voting nonresponse use their own native frames", () => {
  const data = validate1996Points(source);
  const adult = pointFor1996(data, "United States (including D.C.)", "Total");
  const citizen = pointFor1996(data, "United States (including D.C.)", "Total", true);
  assert.equal(adult.rate, 54.2);
  assert.equal(adult.votingNonresponse, null);
  assert.equal(citizen.rate, 58.4);
  assert.equal(citizen.votingNonresponse, 7.4);
  assert.match(citizen.text, /uncertainty not supplied/);
  assert.equal("standardError" in citizen, false);
});

test("state citizen totals and national citizen genders are not manufactured", () => {
  assert.equal(pointFor1996(source, "California", "Total", true).sourceKey, "");
  assert.equal(pointFor1996(source, "United States (including D.C.)", "Female", true).rate, null);
  assert.ok(pointFor1996(source, "District of Columbia", "Female", true).sourceKey);
  assert.equal(pointFor1996(source, "California", "Hispanic (any race)", true).rate, null);
});

test("native age/race bins never alias modern race or split age categories", () => {
  for (const group of ["18 to 24", "25 to 44", "45 to 64", "65+", "White (1998/2002 native category)"])
    assert.ok(pointFor1996(source, "California", group).sourceKey);
  for (const group of ["25 to 34", "35 to 44", "White alone", "Non-Hispanic White (1998/2002 native category)",
    "Asian and Pacific Islander (2002 native category)"])
    assert.equal(pointFor1996(source, "California", group).sourceKey, "");
});

test("suppressed and zero-base rates cannot be repaired while rounded count zeros survive", () => {
  for (const key of ["tab4a.txt:91",
    source.records.find(row => row.reference_state_code === "ND" && row.native_group === "BLACK"
      && row.age === "18_24").source_key]) {
    const changed = structuredClone(source);
    changed.records.find(row => row.source_key === key).measures.voted.selected_percentage = "0.0";
    assert.throws(() => validate1996Points(changed), /differs/);
  }
  const row = source.records.find(row => row.reference_state_code === "SD"
    && row.native_group === "HISPANIC ORIGIN" && row.age === "25_44");
  assert.equal(row.raw_values.voted_thousands, "0");
  assert.equal(row.measures.voted.selected_percentage, "21.9");
});

test("a changed frame or invented sampling uncertainty fails validation", () => {
  for (const modify of [
    row => { row.population_frame = "cvap"; },
    row => { row.measures.voted.sample_n = 193651; },
    row => { row.measures.voted.confidence_interval = [0, 100]; },
  ]) {
    const changed = structuredClone(source);
    modify(changed.records[0]);
    assert.throws(() => validate1996Points(changed), /differs/);
  }
});

test("loader verifies all bytes and rejects unavailable or corrupt data", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(body);
    assert.equal((await load1996Points()).records.length, 1923);
    globalThis.fetch = async () => new Response("unavailable", { status: 503 });
    await assert.rejects(load1996Points, /unavailable/);
    globalThis.fetch = async () => new Response("{}");
    await assert.rejects(load1996Points, /checksum differs/);
  } finally {
    globalThis.fetch = original;
  }
});

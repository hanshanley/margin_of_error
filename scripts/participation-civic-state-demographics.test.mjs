import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { validateCivicStates, civicStateRows } from "../public/scripts/participation-civic-state-demographics.js";

const data = JSON.parse(fs.readFileSync(new URL("../data/participation-civic-state-demographics/20261108-01/viewer-data.json", import.meta.url)));

test("every source state has a 2026 model; D.C. remains missing", () => {
  validateCivicStates(data);
  const states = new Set(data.groups.map(row => row.state_code));
  assert.equal(states.size, 51);
  for (const state of states) {
    const overall = civicStateRows(data, state, "overall")[0];
    assert.equal(overall.modeled_voter_pct === null, state === "DC");
  }
});

test("coarse age bins and held gender groups are not fabricated", () => {
  assert.deepEqual(civicStateRows(data, "TX", "age").map(row => row.group),
    ["18_29", "30_49", "50_64", "65_plus", "unknown"]);
  assert.ok(civicStateRows(data, "TX", "gender").every(row => row.modeled_voter_pct === null));
  assert.equal(civicStateRows(data, "DC", "income").length, 6);
});

test("held counts, promoted turnout or invalid fractions fail closed", () => {
  for (const mutate of [
    changed => { changed.groups.find(row => row.modeled_voter_pct === null).n = 1; },
    changed => { changed.groups[0].administratively_observed_turnout = true; },
    changed => { changed.groups[0].modeled_nonvoter_pct = "0"; },
    changed => { changed.groups[0].design_confidence_interval = [0, 100]; },
    changed => { changed.groups[1] = changed.groups[0]; },
    changed => { changed.groups.pop(); },
  ]) {
    const changed = structuredClone(data);
    mutate(changed);
    assert.throws(() => validateCivicStates(changed));
  }
});

test("the percentage-only successor recovers broad groups without releasing new counts", () => {
  const rates = JSON.parse(fs.readFileSync(new URL('../data/participation-civic-group-rates/20261127-01/viewer-data.json', import.meta.url)));
  validateCivicStates(rates);
  assert.equal(rates.groups.filter(row => row.modeled_voter_pct !== null).length, 864);
  const oldKeys = new Set(data.groups.filter(row => row.modeled_voter_pct !== null)
    .map(row => `${row.state_code}|${row.dimension}|${row.group}`));
  assert.equal(rates.groups.filter(row => row.modeled_voter_pct !== null
    && !oldKeys.has(`${row.state_code}|${row.dimension}|${row.group}`)).length, 193);
  assert.notEqual(civicStateRows(rates, 'MO', 'sex').find(row => row.group === 'male').modeled_voter_pct, null);
  assert.ok(rates.groups.every(row => row.n === null && row.source_weight_concentration_effective_n === null));
  for (const mutate of [
    copy => { copy.publication.minimum_source_cases = 1; },
    copy => { copy.groups.find(row => row.modeled_voter_pct !== null).n = 100; },
    copy => { copy.groups.find(row => row.modeled_voter_pct !== null).modeled_voter_pct = '50.123'; },
  ]) {
    const changed = structuredClone(rates); mutate(changed);
    assert.throws(() => validateCivicStates(changed));
  }
});

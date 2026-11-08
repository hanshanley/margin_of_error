import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { validateDemographics, demographicRows } from "../public/scripts/participation-state-demographics.js";

const data = JSON.parse(fs.readFileSync(new URL("../data/participation-state-demographics/20261108-01/viewer-data.json", import.meta.url)));

test("complete state frames preserve every jurisdiction and source group", () => {
  validateDemographics(data);
  for (const code of new Set(data.rows.map(row => row.state_code))) {
    const age = demographicRows(data, code, "age", "All groups");
    assert.equal(age.length, 8);
    assert.deepEqual([...new Set(age.map(row => row.year))], [2022, 2024]);
    assert.ok(age.every(row => row.turnout_pct >= 0 && row.turnout_pct <= 100));
  }
});

test("absent group stays null while an observed zero stays zero", () => {
  const missing = demographicRows(data, "ID", "race", "Black, non-Hispanic").find(row => row.year === 2022);
  assert.equal(missing.turnout_pct, null);
  assert.equal(missing.sample_n, 0);
  const zeroSource = data.rows.find(row => row.reported_voting_pct === "0");
  assert.ok(zeroSource);
  assert.equal(demographicRows(data, zeroSource.state_code, zeroSource.dimension, zeroSource.group)
    .find(row => row.year === Number(zeroSource.year)).turnout_pct, 0);
});

test("duplicate, incomplete, wrong-frame and changed-rate data fail closed", () => {
  for (const mutate of [
    value => value.rows.pop(),
    value => { value.rows[1] = value.rows[0]; },
    value => { value.rows[0].population_frame = "registered_voters"; },
    value => { value.rows[0].local_allocation = "True"; },
    value => { value.rows[0].reported_voting_pct = "99"; },
    value => { value.rows[0].unknown_weight_units = "0"; },
  ]) {
    const changed = structuredClone(data);
    mutate(changed);
    assert.throws(() => validateDemographics(changed));
  }
});

test("unknown response is retained and sparse cases stay visibly diagnostic", () => {
  const rows = demographicRows(data, "ID", "race", "All groups");
  assert.ok(rows.some(row => row.low_n && row.warnings.some(note => note.includes("Small sample"))));
  const source = data.rows.find(row => row.state_code === "ID" && row.year === "2024"
    && row.dimension === "race_ethnicity" && row.group === "White, non-Hispanic");
  const white = rows.find(row => row.year === 2024 && row.series === source.group);
  assert.equal(white.turnout_pct, Number(source.reported_voting_pct));
  assert.equal(white.unknown_response, Number(source.unknown_pct).toFixed(1) + "%");
});

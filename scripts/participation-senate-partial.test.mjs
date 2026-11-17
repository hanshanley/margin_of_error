import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { validateSenatePartial } from "../public/scripts/participation-senate-partial.js";

const fixture = JSON.parse(readFileSync(new URL("./fixtures/senate-partial.json", import.meta.url)));
const validate = value => validateSenatePartial(value, fixture.legacy, fixture.calibration);

test("validates a separate current D/R-only extension and every scenario without mutating archived models", () => {
  const before = JSON.stringify(fixture);
  const rows = validate(fixture.data);
  assert.equal(rows.size, 26);
  assert.equal([...rows.values()].filter(row => row.model).length, 1);
  assert.deepEqual(rows.get("AL-senate-86907").model.observed_other_vote_endpoints, [true, false]);
  assert.equal(JSON.stringify(fixture), before);
});

test("refuses false Other, identity, status, numerical, range and empirical-model promotions", () => {
  const mutations = [
    value => value.rows.pop(),
    value => value.rows[0].id = "unreviewed",
    value => value.rows[0].model.reported_comparison.current.O = 0,
    value => value.rows[0].model.observed_other_vote_endpoints[1] = true,
    value => value.rows[0].model.senate_respondent_model = true,
    value => value.rows[0].model_source_clock = "2026-11-17T00:00:00Z",
    value => value.rows[0].model.complete_scenarios[8].synthetic_joint[0][0] += .01,
    value => value.rows[0].model.complete_scenarios[8].components_pp.switching += 1,
    value => value.rows[0].model.complete_scenarios.pop(),
    value => value.rows[0].model.ranges_pp.entry.maximum += 1,
    value => value.summary.strict_legacy_models_refreshed = 1,
    value => value.rows[0].holds.push("incompatible candidate"),
    value => value.rows[0].model.point.target_columns[0] += .01,
    value => {
      value.rows[0].status = "held_no_compatible_partial_bridge";
      value.rows[0].holds = ["Missing bridge"];
      value.summary.fresh_partial_scenarios = value.summary.fresh_sensitivity_fits = 0;
    },
    value => value.rows[0].model.reported_comparison.baseline_year = 2024,
    value => value.rows[0].model.reported_comparison.baseline_stage = "runoff",
    value => value.rows[0].model.reported_comparison.current_stage = "runoff",
    value => value.rows[0].model.reported_comparison.current_round = 1,
  ];
  for (const mutate of mutations) {
    const changed = structuredClone(fixture.data);
    mutate(changed);
    assert.throws(() => validate(changed));
  }
});

test("retained scenarios retain their own source date and show an explicit update hold", () => {
  const value = structuredClone(fixture.data), row = value.rows.find(row => row.model);
  row.status = "held_retain_last_good_partial_scenario";
  row.holds = ["Source unavailable"];
  value.summary.fresh_partial_scenarios = value.summary.fresh_sensitivity_fits = 0;
  value.summary.retained_partial_scenarios = 1;
  assert.equal(validate(value).get(row.id).model_source_clock, row.model_source_clock);
});

test("accepts the explicit FEC-identity successor without weakening the original version", () => {
  const successor = JSON.parse(readFileSync(new URL("./fixtures/senate-partial-new-mexico.json", import.meta.url)));
  const before = JSON.stringify(successor);
  const check = value => validateSenatePartial(value, successor.legacy, successor.calibration);
  const rows = check(successor.data);
  assert.equal([...rows.values()].filter(row => row.model).length, 2);
  const nm = rows.get("NM-senate-87288");
  assert.equal(nm.model.reported_comparison.previous.O, 24271);
  assert.equal(Object.hasOwn(nm.model.reported_comparison.current, "O"), false);
  assert.equal(nm.model.complete_scenarios.length, 9);
  assert.equal(JSON.stringify(successor), before);
  for (const mutate of [
    value => value.review_version = "20261117-01",
    value => value.review_version = "20261117-03",
    value => value.rows.find(row => row.id === nm.id).model.reported_comparison.current.O = 0,
    value => value.rows.find(row => row.id === nm.id).model.reported_comparison.previous.O = 0,
    value => value.rows.find(row => row.id === nm.id).model.senate_respondent_model = true,
    value => value.rows.find(row => row.id === nm.id).model.reported_comparison.current_stage = "runoff",
  ]) {
    const changed = structuredClone(successor.data);
    mutate(changed);
    assert.throws(() => check(changed));
  }
  const held = structuredClone(successor.data);
  const row = held.rows.find(value => value.id === nm.id);
  row.status = "held_retain_last_good_partial_scenario";
  row.holds = ["Source unavailable"];
  held.summary.fresh_partial_scenarios -= 1;
  held.summary.fresh_sensitivity_fits -= 9;
  held.summary.retained_partial_scenarios += 1;
  assert.equal(check(held).get(row.id).model_source_clock, nm.model_source_clock);
});

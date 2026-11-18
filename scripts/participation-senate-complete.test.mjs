import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validateSenateComplete } from "../public/scripts/participation-senate-complete.js";

const original = JSON.parse(readFileSync(new URL("./fixtures/senate-complete.json", import.meta.url)));
const key = "RI-senate-87396";
const row = data => data.rows.find(value => value.id === key);
const validate = data => validateSenateComplete(data, original.legacy, original.calibration);

test("the complete RI extension validates every original decision, point, range and all nine assumptions", () => {
  const decisions = validate(original.data), value = decisions.get(key);
  assert.equal(decisions.size, 26);
  assert.equal(value.model.complete_scenarios.length, 9);
  assert.equal(value.model.reported_comparison.current.O, 14258);
  assert.deepEqual(value.model.observed_other_vote_endpoints, [true, true]);
  assert.equal(original.data.summary.empirical_senate_models_added, 0);
});

test("last-good complete scenarios retain their own clocks and never claim a fresh model refresh", () => {
  const data = structuredClone(original.data), value = row(data);
  value.status = "held_retain_last_good_complete_scenario";
  value.holds = ["Complete official source unavailable."];
  value.strict_legacy_model_refreshed = false;
  Object.assign(data.summary, { fresh_complete_scenarios: 0, retained_complete_scenarios: 1,
    fresh_sensitivity_fits: 0, strict_legacy_models_refreshed: 0 });
  assert.equal(validate(data).get(key).model_source_clock, row(original.data).model_source_clock);
});

test("wrong seats, stages, source pins, Other mass, clocks, history, scenarios and arithmetic refuse", () => {
  for (const mutate of [
    data => { row(data).current_identity.seat = "1"; },
    data => { row(data).current_identity.stage = "runoff"; },
    data => { row(data).current_identity.ranked_choice = true; },
    data => { row(data).official_source.url += "?unreviewed"; },
    data => { row(data).official_source.sha256 = "wrong"; },
    data => { row(data).official_evidence_clock = "2026-11-12 18:11"; },
    data => { row(data).model.observed_other_vote_endpoints[1] = false; },
    data => { row(data).model.reported_comparison.current.O++; },
    data => { row(data).model.reported_comparison.previous.D++; },
    data => { row(data).model.reported_comparison.baseline_year = 2022; },
    data => { row(data).model.point.components_pp.switching++; },
    data => { row(data).model.ranges_pp.switching.maximum++; },
    data => { row(data).model.complete_scenarios[0].persistence_scale = 3; },
    data => { row(data).model.complete_scenarios.pop(); },
    data => { row(data).model.senate_respondent_model = true; },
    data => { data.rows.push(data.rows[0]); },
    data => { data.summary.strict_legacy_models_refreshed = 2; },
  ]) {
    const changed = structuredClone(original.data); mutate(changed);
    assert.throws(() => validate(changed));
  }
});

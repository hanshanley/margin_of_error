import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validateSenateComplete } from "../public/scripts/participation-senate-complete.js";

const original = JSON.parse(readFileSync(new URL("./fixtures/senate-complete.json", import.meta.url)));
const official = JSON.parse(readFileSync(new URL("./fixtures/senate-complete-official.json", import.meta.url)));
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

test("newer complete official reports retain both provider vectors and all nine numerical scenarios", () => {
  const value = validate(official).get(key);
  assert.equal(value.model_review_version, "20261118-02");
  assert.deepEqual(value.model.reported_comparison.current, { D: 240707, O: 14258, R: 105459 });
  assert.deepEqual(value.model.reported_comparison.source_reconciliation.official_minus_national,
    { D: 13, O: 0, R: 5 });
  assert.equal(value.model.complete_scenarios.length, 9);
});

test("native clock comparison preserves submicrosecond ordering and rejects normalized invalid dates", () => {
  const data = structuredClone(official), value = row(data);
  const audit = value.model.reported_comparison.source_reconciliation;
  value.national_source_clock = audit.national_native_clock = "2026-11-18T01:05:46.0614198Z";
  assert.equal(validate(data).get(key).model_source_clock, "2026-11-18T01:05:46.0614199Z");
  for (const clock of ["2026-11-18T01:05:46.0614199Z", "2026-11-18T01:05:46.0614200Z",
    "2026-02-30T01:05:46Z", "2026-11-17T24:00:00Z", "0000-11-18T01:05:46Z"]) {
    const changed = structuredClone(data), selected = row(changed);
    selected.national_source_clock = selected.model.reported_comparison.source_reconciliation.national_native_clock = clock;
    assert.throws(() => validate(changed), clock);
  }
});

test("a saved first-version scenario remains dated and valid during upgrade outages", () => {
  const data = structuredClone(original.data);
  data.review_version = "20261118-02";
  for (const value of data.rows) {
    value.model_review_version = value.model ? "20261118-01" : null;
    value.national_source_clock = value.model_source_clock;
  }
  const value = row(data);
  value.status = "held_retain_last_good_complete_scenario";
  value.holds = ["Complete official source unavailable."];
  value.strict_legacy_model_refreshed = false;
  Object.assign(data.summary, { fresh_complete_scenarios: 0, retained_complete_scenarios: 1,
    fresh_sensitivity_fits: 0, strict_legacy_models_refreshed: 0 });
  assert.deepEqual(validate(data).get(key).model, row(original.data).model);
  value.model_review_version = "unreviewed";
  assert.throws(() => validate(data), /Unreviewed retained/);
});

test("new official/provider contracts reject changed discrepancies, pins, clocks and allocation claims", () => {
  const reconciliation = data => row(data).model.reported_comparison.source_reconciliation;
  for (const mutate of [
    data => { reconciliation(data).official_minus_national.D++; },
    data => { reconciliation(data).national_counts.O--; },
    data => { reconciliation(data).official_source.sha256 = "a".repeat(64); },
    data => { reconciliation(data).national_source.url += "?unreviewed"; },
    data => { reconciliation(data).official_native_clock = row(data).national_source_clock; },
    data => { reconciliation(data).national_native_clock = row(data).model_source_clock; },
    data => { reconciliation(data).counts_agree = true; },
    data => { reconciliation(data).individual_votes_allocated_from_Other = true; },
    data => { reconciliation(data).provider_and_official_counts_added = true; },
    data => { row(data).model_review_version = "20261118-01"; },
    data => { data.review_version = "unreviewed"; },
    data => { data.rows.find(value => value.model === null).national_source_clock = row(data).national_source_clock; },
  ]) {
    const changed = structuredClone(official); mutate(changed);
    assert.throws(() => validate(changed));
  }
});

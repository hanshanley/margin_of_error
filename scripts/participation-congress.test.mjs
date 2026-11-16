import test from "node:test";
import assert from "node:assert/strict";
import { validateCongressionalResults } from "../public/scripts/participation-congress.js";

function fixture() {
  const races = ["house", "senate"].map(chamber => ({
    id: `npr:${chamber}:AL:${chamber === "house" ? 1 : 2}:regular:general:not_ranked`,
    chamber, state_code: "AL", seat: chamber === "house" ? "1" : "2",
    seat_label: chamber === "house" ? "District 1" : "Class II",
    election_kind: "regular", stage: "general", round: "not_ranked",
    election_date: "2026-11-03", ranked_choice: false, advertised: true,
    freshness: "source_verified", status: "reported",
    source_updated_at: "2026-11-15T00:00:00.000+00:00",
    source_updated_epoch_ms: Date.parse("2026-11-15T00:00:00.000Z"),
    D: 60, R: 40, O: 0, U: 0,
    D_two_party_share_pct: 60, R_two_party_share_pct: 40, D_minus_R_margin_pp: 20,
    candidate_votes_are_not_ballots_or_turnout: true, behavioral_estimate_updated: false,
    count_coverage_complete: true, comparison_holds: [], qualified_comparison: true,
    candidate_ids: ["d", "r", "other"],
    previous: { D: 50, R: 50, O: 0, D_minus_R_margin_pp: 0 },
    baseline: { year: chamber === "house" ? 2024 : 2020, stage: "general", seat: "2" },
    raw_recorded_margin_change_pp: 20, raw_recorded_D_share_change_pp: 10,
    qualified_margin_change_pp: 20,
  }));
  const candidates = races.flatMap(row => [
    { ...row, candidate_id: "d", name: "D Candidate", literal_party: "Dem", party_group: "D", votes: 60 },
    { ...row, candidate_id: "r", name: "R Candidate", literal_party: "GOP", party_group: "R", votes: 40 },
    { ...row, candidate_id: "other", name: "Other", literal_party: "Other", party_group: "O", votes: 0 },
  ]);
  return { contract: "participation.congressional_results.v1", election_date: "2026-11-03",
    source_models_refitted: false, observed_individual_behavior: false,
    races, candidates, coverage: races.map(row => ({ ...row })), house_states: [],
    summary: Object.fromEntries(["house", "senate"].map(chamber =>
      [chamber, { discovered: 1, refreshed: 1, retained: 0, held: 0 }])) };
}

test("complete both-chamber results preserve zeros, separate seat identities and both change scales", () => {
  const data = validateCongressionalResults(fixture());
  assert.equal(data.candidates[2].votes, 0);
  assert.equal(data.races[1].seat, "2");
  assert.equal(data.races[0].raw_recorded_margin_change_pp, 2 * data.races[0].raw_recorded_D_share_change_pp);
});

test("source, candidate, arithmetic, frame and freshness corruptions are rejected", () => {
  for (const mutate of [
    value => { value.candidates.pop(); },
    value => { value.candidates[0].votes = -1; },
    value => { value.candidates[0].literal_party = "Ind"; },
    value => { value.candidates[0].round = "round-2"; },
    value => { value.races[0].D_minus_R_margin_pp = -20; },
    value => { value.races[0].source_updated_at = "2024-11-05T00:00:00Z"; },
    value => { value.races[1].baseline.seat = "3"; },
    value => { value.races[1].ranked_choice = true; },
    value => { value.races[0].freshness = "retained_last_good"; },
    value => { value.races[0].raw_recorded_D_share_change_pp = 20; },
    value => { value.observed_individual_behavior = true; },
    value => { value.summary.house.refreshed = 435; },
    value => { value.coverage[0].source_updated_at = "2024-11-05T00:00:00Z"; },
    value => { value.coverage[0].state_code = "CA"; },
  ]) {
    const data = fixture(); mutate(data);
    assert.throws(() => validateCongressionalResults(data), /Congressional|House-state/);
  }
});

test("a held RCV comparison keeps its raw recorded change without becoming a qualified swing", () => {
  const data = fixture(), row = data.races[1];
  row.ranked_choice = true;
  row.qualified_comparison = false;
  row.qualified_margin_change_pp = null;
  row.comparison_holds = ["Previous/current RCV rounds not matched"];
  assert.equal(validateCongressionalResults(data).races[1].raw_recorded_margin_change_pp, 20);
});

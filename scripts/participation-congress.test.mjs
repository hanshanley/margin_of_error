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
    value => { value.candidates[0].seat = "3"; },
    value => { value.candidates[0].chamber = "senate"; },
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

const readerLimit = "Reviewed same-seat comparison is qualified in congress-comparisons.csv; "
  + "the deployed v1 reader can badge only regular Class II, same-stage comparisons. "
  + "Raw counts and changes remain available here.";

function reviewedFixture() {
  const data = fixture(), senate = data.races[1];
  data.races = [data.races[0], ...["FL", "OH", "GA"].map(state => {
    const row = structuredClone(senate), runoff = state === "GA";
    Object.assign(row, { state_code: state, seat: runoff ? "2" : "3",
      seat_label: runoff ? "Class II" : "Class III",
      election_kind: runoff ? "regular" : "special", native_runoff: false });
    row.id = `npr:senate:${state}:${row.seat}:${row.election_kind}:general:not_ranked`;
    const year = runoff ? 2021 : 2022, cycle = runoff ? 2020 : 2022;
    const url = `https://www.fec.gov/resources/cms-content/documents/federalelections${cycle}.xlsx`;
    row.baseline = { year, cycle_year: cycle, seat: row.seat,
      stage: runoff ? "general_runoff" : "general", election_kind: "regular",
      source_urls: [url],
      comparison_policy: "latest_completed_same_seat_final_election_to_final_election",
      previous_stage_differs: runoff, previous_regular_special_differs: !runoff };
    row.previous_candidates = ["D", "R", "O"].map(party => ({
      candidate: `${party} historical candidate`, party_group: party,
      literal_party: party === "D" ? "DEM" : party === "R" ? "R" : "LIB",
      votes: party === "O" ? 0 : 50, state_code: state, seat: row.seat,
      year, cycle_year: cycle, stage: row.baseline.stage, election_kind: "regular",
      ranked_choice: false, round: "not_ranked", source_url: url,
    }));
    return row;
  })];
  data.candidates = data.races.flatMap(row => [
    { ...row, candidate_id: "d", name: "D Candidate", literal_party: "Dem",
      party_group: "D", role: "named_candidate", votes: 60 },
    { ...row, candidate_id: "r", name: "R Candidate", literal_party: "GOP",
      party_group: "R", role: "named_candidate", votes: 40 },
    { ...row, candidate_id: "other", name: "Other", literal_party: "Other",
      party_group: "O", role: "provider_aggregate_other", votes: 0 },
  ]);
  data.coverage = structuredClone(data.races);
  data.summary.senate.discovered = data.summary.senate.refreshed = 3;
  data.reviewed_races = structuredClone(data.races);
  for (const row of data.races.filter(row => row.chamber === "senate"))
    Object.assign(row, { reviewed_qualified_comparison: true,
      reviewed_qualified_margin_change_pp: 20, qualified_comparison: false,
      qualified_margin_change_pp: null, comparison_holds: [readerLimit],
      legacy_reader_display_limit: true });
  data.analytical_handoff = { review_version: "20261116-01" };
  data.scientific_comparison_coverage = { reviewed_qualified_senate: 3,
    legacy_reader_qualified_senate: 0, reviewed_qualified_house_states: 0 };
  return data;
}

test("reviewed same-seat specials and decisive prior runoffs reach the reader without changing native data", () => {
  const input = reviewedFixture(), before = structuredClone(input);
  const result = validateCongressionalResults(input);
  assert.equal(result.races.filter(row => row.chamber === "senate" && row.qualified_comparison).length, 3);
  assert.equal(result.races[3].baseline.stage, "general_runoff");
  assert.deepEqual(result.candidates, input.candidates);
  assert.deepEqual(input, before);
});

test("reviewed inventory cannot change counts, drop holds, substitute seats or grant model eligibility", () => {
  for (const mutate of [
    value => { value.reviewed_races.pop(); },
    value => { value.reviewed_races[2] = structuredClone(value.reviewed_races[1]); },
    value => { value.reviewed_races[1].D++; },
    value => { value.reviewed_races[1].baseline.seat = "2"; },
    value => { value.reviewed_races[1].source_updated_at = "2026-11-16T00:00:00Z"; },
    value => { value.races[1].comparison_holds.push("Source frame incompatible"); },
    value => { value.races[1].reviewed_qualified_comparison = false; },
    value => { value.reviewed_races[1].behavioral_estimate_updated = true; },
    value => { value.analytical_handoff.review_version = "unreviewed"; },
    value => { value.scientific_comparison_coverage.reviewed_qualified_senate++; },
  ]) {
    const data = reviewedFixture(); mutate(data);
    assert.throws(() => validateCongressionalResults(data), /Congressional|Senate/);
  }
});

for (const version of ["20261117-identity-01", "20261117-declarations-01",
  "20261117-categories-01", "20261117-declarations-02"]) {
test(`the reviewed ${version} successor preserves the same seat-aware recorded contract`, () => {
  const input = reviewedFixture();
  input.analytical_handoff.review_version = version;
  const before = structuredClone(input);
  const result = validateCongressionalResults(input);
  assert.equal(result.races.filter(row => row.chamber === "senate" && row.qualified_comparison).length, 3);
  assert.deepEqual(result.candidates, before.candidates);
  assert.deepEqual(input, before);
  for (const mutate of [
    value => { value.analytical_handoff.review_version = "20261118-identity-01"; },
    value => { value.analytical_handoff.review_version = "20261118-declarations-01"; },
    value => { value.analytical_handoff.review_version = "20261118-categories-01"; },
    value => { value.reviewed_races[1].baseline.seat = "2"; },
    value => { value.reviewed_races[3].baseline.stage = "general"; },
    value => { value.reviewed_races[1].behavioral_estimate_updated = true; },
    value => { value.reviewed_races[1].D++; },
  ]) {
    const changed = structuredClone(input);
    mutate(changed);
    assert.throws(() => validateCongressionalResults(changed), /Congressional|Senate/);
  }
});
}

test("same-seat review checks the complete historical frame, not just major-party totals or names", () => {
  for (const mutate of [
    row => { row.baseline.comparison_policy = "same_names"; },
    row => { row.baseline.stage = "primary"; },
    row => { row.baseline.previous_regular_special_differs = false; },
    row => { row.previous_candidates[0].seat = "2"; },
    row => { row.previous_candidates[0].state_code = "OH"; },
    row => { row.previous_candidates[0].votes--; },
    row => { row.previous_candidates[2].votes = null; },
    row => { row.previous_candidates[2].round = "round-1"; },
    row => { row.previous_candidates[0].source_url = "https://example.com/unreviewed"; },
    row => {
      row.baseline.source_urls[0] = "https://www.fec.gov/resources/cms-content/documents/federalelections2020.xlsx";
      for (const fact of row.previous_candidates) fact.source_url = row.baseline.source_urls[0];
    },
    row => { row.previous_candidates[0].literal_party = "IND"; },
    row => { row.native_runoff = true; },
  ]) {
    const data = reviewedFixture();
    for (const rows of [data.races, data.reviewed_races]) mutate(rows[1]);
    assert.throws(() => validateCongressionalResults(data), /Congressional|Senate/);
  }
});

function boundaryFixture(split = false) {
  const data = fixture(), version = "20261117-01";
  for (const rows of [data.races, data.candidates, data.coverage])
    for (const row of rows.filter(row => row.chamber === "house"))
      Object.assign(row, { id: "npr:house:AL:3:regular:general:not_ranked", seat: "3" });
  const row = data.races[0];
  row.baseline = { year: 2024, stage: "general", seat: "3", district: "AL-03",
    boundary_eligibility: { district: "AL-03", state_code: "AL", state_fips: "01",
      district_code: "03", previous_year: 2024, current_year: 2026,
      previous_congress: 119, current_congress: 120,
      previous_membership: { blocks: 2, sha256: "a".repeat(64) },
      current_membership: { blocks: 2, sha256: "a".repeat(64) },
      affected_split_blocks: split ? ["010010201001000"] : [],
      whole_block_membership_equal: true, boundary_compatible: !split,
      holds: split ? ["split_block_geometry_unresolved"] : [],
      review_version: version,
      method: "identical_2020_census_block_union_without_affected_split_blocks",
      legal_boundary_certification: false, historical_votes_allocated: false,
      behavioral_model_qualified: false } };
  if (split) Object.assign(row, { qualified_comparison: false, qualified_margin_change_pp: null,
    comparison_holds: ["House boundary hold: split_block_geometry_unresolved"] });
  data.house_boundary_review = { contract: "participation.congressional_boundary_review.v1",
    version, districts: 435, boundary_compatible: 288, qualified_recorded_comparisons: split ? 0 : 1,
    evidence: Object.fromEntries(["cd119.zip", "cd120.zip", "CD119_BlockSplits.pdf", "CD120_BlockSplits.pdf"]
      .map(name => {
        const congress = name.includes("119") ? 119 : 120;
        return [name, { bytes: 10, sha256: "b".repeat(64),
          url: "https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/"
            + `${congress === 119 ? 2025 : 2027}/${congress}-congressional-district-befs/${name}` }];
      })) };
  data.scientific_comparison_coverage = { reviewed_qualified_house_districts: split ? 0 : 1 };
  return data;
}

test("district boundary qualification preserves split holds and inspectable raw changes", () => {
  assert.equal(validateCongressionalResults(boundaryFixture()).races[0].qualified_comparison, true);
  const held = validateCongressionalResults(boundaryFixture(true)).races[0];
  assert.equal(held.raw_recorded_margin_change_pp, 20);
  assert.equal(held.qualified_margin_change_pp, null);
});

test("district numbering, equal assigned blocks or boundary compatibility alone cannot grant a swing", () => {
  for (const mutate of [
    value => { delete value.races[0].baseline.boundary_eligibility; },
    value => { value.house_boundary_review.version = "unreviewed"; },
    value => { delete value.house_boundary_review.evidence["CD120_BlockSplits.pdf"]; },
    value => { value.house_boundary_review.evidence["cd120.zip"].url += "?superseded"; },
    value => { value.house_boundary_review.qualified_recorded_comparisons++; },
    value => { value.races[0].baseline.boundary_eligibility.district_code = "01"; },
    value => { value.races[0].baseline.boundary_eligibility.previous_year = 2022; },
    value => { value.races[0].baseline.boundary_eligibility.current_membership.sha256 = "c".repeat(64); },
    value => { value.races[0].baseline.boundary_eligibility.affected_split_blocks = ["010010201001000"]; },
    value => { value.races[0].baseline.boundary_eligibility.historical_votes_allocated = true; },
    value => { value.races[0].freshness = "retained_last_good"; },
    value => { value.races[0].comparison_holds = ["Current nominee absent"]; },
  ]) {
    const data = boundaryFixture(); mutate(data);
    assert.throws(() => validateCongressionalResults(data), /Congressional/);
  }
});

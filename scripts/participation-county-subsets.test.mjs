import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";
import { loadCountySubsets, subsetMarginLabel, subsetColorValue, validateCountySubsets }
  from "../public/scripts/participation-county-subsets.js";

const scope = { year: 2026, state_code: "ME", state_fips: "23", counties: 1, county_ids: ["23001"] };
function fixture() {
  const candidates = [
    { name: "D Candidate", party: "Democratic", candidate_id: 1, role: "D", district_votes: 12, located_county_votes: 12, unlocated_votes: 0 },
    { name: "R Candidate", party: "Republican", candidate_id: 2, role: "R", district_votes: 8, located_county_votes: 8, unlocated_votes: 0 },
    { name: "Write-in", party: "Nonpartisan", candidate_id: 3, role: "unallocated_other", district_votes: 4, located_county_votes: 0, unlocated_votes: 4 },
  ];
  const source = { district: "ME-01", source_url: "https://civicapi.org/api/v2/race/1",
    source_sha256: "a".repeat(64), source_updated_at: "2026-11-07T05:36:43.607Z", source_round: 1 };
  return {
    contract: "participation.county_candidate_subsets.v1", ...scope, office: "U.S. House", stage: "General",
    source_round: 1, boundary_reference_year: 2026, freshness: "retained_historical_observation",
    complete_state_vector_qualified: false, participation_qualified: false, swing_qualified: false,
    model_update_qualified: false, unlocated_other_votes: 4,
    district_decisions: [{ ...source, candidate_decisions: candidates, complete_vector_qualified: false }],
    rows: [{ geography: "23001", geography_name: "Example County", state_code: "ME", year: 2026, level: "county",
      office: "U.S. House", stage: "General", source_round: 1, freshness: "retained_historical_observation",
      democratic_votes: 12, republican_votes: 8, located_other_votes: 0, other_votes: null,
      contest_votes: null, known_candidate_votes: 20, unlocated_other_upper_bound: 4,
      margin_bounds_pp: [100 / 6, 20], margin_pp: null, complete_vector_qualified: false,
      district_fragments: [{ ...source, geography: "23001", unlocated_other_upper_bound: 4,
        candidates: candidates.map(c => ({ name: c.name, party: c.party, votes: c.located_county_votes })) }] }],
    geometry: { type: "FeatureCollection", features: [{ type: "Feature",
      properties: { key: "23001", name: "Example County", state_code: "ME", boundary_year: 2026 },
      geometry: { type: "Polygon", coordinates: [[[-70, 43], [-69, 43], [-69, 44], [-70, 43]]] } }] },
  };
}
const pin = body => ({ url: "https://example.org/county.json.gz", bytes: body.length,
  sha256: createHash("sha256").update(body).digest("hex"),
  complete_download_url: "https://example.org/complete.zip", csv_url: "https://example.org/results.csv" });

test("known counts are available without inventing Other or an exact margin", () => {
  const data = validateCountySubsets(fixture(), scope), row = data.rows[0];
  assert.equal(row.democratic_votes, 12);
  assert.equal(row.other_votes, null);
  assert.equal(row.contest_votes, null);
  assert.equal(subsetColorValue(row), 100 / 6);
  assert.equal(subsetMarginLabel(row), "D+16.66–20.00 pp");
});

test("mutated counts, coverage, clocks, source frames and geometry fail closed", () => {
  const mutations = [
    d => { d.rows[0].democratic_votes++; },
    d => { d.rows[0].other_votes = 0; },
    d => { d.rows[0].contest_votes = 20; },
    d => { d.rows[0].margin_pp = 20; },
    d => { d.rows[0].margin_bounds_pp[0] = 18; },
    d => { d.rows[0].district_fragments[0].candidates.pop(); },
    d => { d.rows[0].district_fragments[0].candidates[0].votes = null; },
    d => { d.rows[0].district_fragments[0].source_updated_at = "2026-11-08T00:00:00Z"; },
    d => { d.district_decisions[0].candidate_decisions[0].unlocated_votes = 1; },
    d => { d.source_round = 2; },
    d => { d.stage = "Runoff"; },
    d => { d.freshness = "fresh"; },
    d => { d.participation_qualified = true; },
    d => { d.model_update_qualified = true; },
    d => { d.geometry.features[0].properties.boundary_year = 2024; },
    d => { d.geometry.features[0].geometry.coordinates[0][0][0] = 999; },
  ];
  for (const mutate of mutations) {
    const data = fixture(); mutate(data);
    assert.throws(() => validateCountySubsets(data, scope), /Unqualified/);
  }
});

test("hash-checked loads support retry after an outage but never accept corrupt bodies", async () => {
  const body = gzipSync(JSON.stringify(fixture())), descriptor = pin(body);
  let requests = 0;
  const request = async () => ++requests === 1 ? new Response("", { status: 503 }) : new Response(body);
  await assert.rejects(loadCountySubsets(descriptor, scope, request), /503/);
  assert.equal((await loadCountySubsets(descriptor, scope, request)).rows[0].republican_votes, 8);
  const corrupt = new Uint8Array(body); corrupt[15] ^= 1;
  await assert.rejects(loadCountySubsets(descriptor, scope, async () => new Response(corrupt)), /Unqualified/);
  assert.equal(requests, 2);
});

test("negative margins use the endpoint nearest zero and outward display rounding", () => {
  const row = { margin_bounds_pp: [-20, -100 / 6], complete_vector_qualified: false };
  assert.equal(subsetColorValue(row), -100 / 6);
  assert.equal(subsetMarginLabel(row), "R+16.66–20.00 pp");
  assert.equal(subsetColorValue({ margin_bounds_pp: null }), null);
});

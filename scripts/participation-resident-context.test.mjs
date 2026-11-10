import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";
import { checkedDatasetFile, validateCatalog } from "../public/scripts/participation-dataset.js";
import { countyForSource, precinctForReference, validateResidentShard, incomeLabel } from "../public/scripts/participation-resident-context.js";

const referenceHash = "c".repeat(64);
const county = () => ({
  state_code: "MN", name: "Aitkin County", name_keys: ["AITKIN"],
  geography: { level: "county", census_geoid: "27001", source_geography_vintage: 2024 },
  map_join: { feature_key: "27001", reference_year: 2024, status: "approved_context_identity",
    certified_election_boundary: false }, resident_composition_is_not_voter_composition: true,
  median_household_income: { estimate: 0, margin_of_error: null, bounded: false },
});
const precinct = () => ({
  state_code: "MN", geography: { level: "precinct_reference", reference_key: "MN|01|0005" },
  resident_composition_is_not_voter_composition: true, source_geometry_repaired: false,
  voter_participation_rate: null, modeled_income_median_band: {
    status: "modeled_income_bin_interval_not_exact_median", lower_bound: 50000, upper_bound: 60000,
  },
});
const shard = () => ({
  contract: "geographic.resident_context.v1", state_code: "MN",
  resident_context_not_voter_data: true, counties: [county()], precincts: [precinct()],
  precinct_source: { sha256: referenceHash },
});

test("source county context requires unique county identity, not a town or partial reporting region", () => {
  const rows = [county()];
  const source = { state_code: "MN", county: "Aitkin", geography_level: "county", county_fips: "27001" };
  assert.equal(countyForSource(rows, source, "MN"), rows[0]);
  assert.equal(countyForSource(rows, { ...source, geography_level: "municipality" }, "MN"), null);
  assert.equal(countyForSource(rows, { ...source, geography_level: "source_region" }, "MN"), null);
  assert.equal(countyForSource(rows, { ...source, county_fips: "27003" }, "MN"), null);
  assert.equal(countyForSource(rows, source, "NM"), null);
  assert.equal(countyForSource([...rows, county()], source, "MN"), null);
});

test("precinct estimates require the exact loaded reference hash and a unique native key", () => {
  const data = shard();
  assert.equal(precinctForReference(data, "MN|01|0005", referenceHash), data.precincts[0]);
  assert.equal(precinctForReference(data, "MN|01|0005", "a".repeat(64)), null);
  assert.equal(precinctForReference(data, "MN|01|0005"), null);
  assert.equal(precinctForReference(data, "MN|01|0006", referenceHash), null);
  data.precincts.push(precinct());
  assert.equal(precinctForReference(data, "MN|01|0005", referenceHash), null);
});

test("resident contract rejects foreign states, duplicate keys, repairs and participation-rate substitution", () => {
  const declaration = { counties: 1, precincts: 1 };
  validateResidentShard(shard(), "MN", declaration);
  for (const change of [
    data => { data.counties[0].geography.census_geoid = "NM"; },
    data => { data.counties[0].state_code = "NM"; },
    data => { data.counties[0].map_join.reference_year = 2026; },
    data => { data.precincts[0].source_geometry_repaired = true; },
    data => { data.precincts[0].voter_participation_rate = 0.6; },
  ]) {
    const data = shard(); change(data);
    assert.throws(() => validateResidentShard(data, "MN", declaration), /Unqualified/);
  }
  assert.throws(() => validateResidentShard(shard(), "MN", { counties: 1, precincts: 2 }), /coverage differs/);
});

test("county zero income is not missing, and conditional income is a band rather than an averaged median", () => {
  const row = county();
  assert.equal(incomeLabel(row), "$0");
  row.median_household_income.estimate = null;
  assert.equal(incomeLabel(row), "Not available");
  const local = precinct();
  assert.equal(incomeLabel(local), "$50,000–$60,000");
  local.modeled_income_median_band.upper_bound = null;
  assert.equal(incomeLabel(local), "$50,000 or more");
  local.modeled_income_median_band.status = "withheld";
  assert.equal(incomeLabel(local), "Not available");
});

function catalog() {
  return {
    contract: "participation.dataset_catalog.v1", datasets: {
      "resident-context": {
        contract: "participation.dataset.v1", id: "resident-context", status: "loaded",
        version: "a".repeat(64), index: { file: "index.json", bytes: 2, sha256: "b".repeat(64) },
        base_url: "https://raw.githubusercontent.com/hanshanley/margin_of_error/" + "d".repeat(40) + "/datasets/",
        complete_download: { verified_anonymously: true, immutable: true, sha256: "e".repeat(64) },
      },
    },
  };
}

test("a pending unrelated dataset does not hide a loaded dataset; unverified or mutable loaded entries fail", () => {
  const data = catalog();
  data.datasets.other = { contract: "participation.dataset.v1", id: "other", status: "awaiting_publication" };
  validateCatalog(data);
  for (const change of [
    value => { value.datasets["resident-context"].complete_download.immutable = false; },
    value => { value.datasets["resident-context"].base_url = "https://raw.githubusercontent.com/hanshanley/margin_of_error/main/"; },
    value => { value.datasets["resident-context"].complete_download.verified_anonymously = false; },
  ]) {
    const value = catalog(); change(value);
    assert.throws(() => validateCatalog(value), /unverified/);
  }
});

test("downloaded compressed bytes are checked before decoding and corruption cannot become a zero", async t => {
  const body = gzipSync(JSON.stringify({ known_zero: 0, unknown: null }));
  const declaration = { file: "states/MN.json.gz", bytes: body.length,
    sha256: createHash("sha256").update(body).digest("hex") };
  t.mock.method(globalThis, "fetch", async () => new Response(body));
  const base = catalog().datasets["resident-context"].base_url;
  assert.deepEqual(await checkedDatasetFile(base, declaration), { known_zero: 0, unknown: null });
  await assert.rejects(checkedDatasetFile(base, { ...declaration, bytes: body.length + 1 }), /checksum differs/);
  await assert.rejects(checkedDatasetFile(base, { ...declaration, sha256: "0".repeat(64) }), /checksum differs/);
  await assert.rejects(checkedDatasetFile(base, { ...declaration, file: "../states/MN.json.gz" }), /Unqualified/);
  await assert.rejects(checkedDatasetFile("https://example.test/", declaration), /Unqualified/);
});

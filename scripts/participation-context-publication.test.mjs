import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { countyContextSuccessor, loadCountPublication } from "./participation-count-publication.mjs";
import { createCountyContextReview } from "./build-county-participation-context.mjs";
import { canonicalJson, contextualCountyRows } from "../public/scripts/participation-county-context.js";

const json = path => JSON.parse(readFileSync(path));
const digest = body => createHash("sha256").update(body).digest("hex");
const directory = "public/participation-county-context/20261106-25/";
const prior = json(directory + "review.json");
const baseline = json("data/participation-counts/20261110-02/inputs/reviewed.json").county_context;
const successor = json("data/participation-counts/context-review.json");

function fixture() {
  const records = JSON.parse(gunzipSync(readFileSync(directory + "complete-source-records.json.gz")));
  const selected = successor.reviewed_source_record;
  const index = records.findIndex(row => row.state_code === selected.state_code && row.county_id === selected.county_id);
  assert.ok(index >= 0);
  assert.equal(digest(canonicalJson(records[index])), prior.observations.find(row =>
    row.county_id === selected.county_id).source_record_sha256);
  records[index] = structuredClone(selected);
  const inventories = Object.fromEntries(["2024", "2026"].map(year => [year,
    JSON.parse(gunzipSync(readFileSync(directory + `complete-${year}-county-identities.json.gz`)))]));
  const collections = Object.fromEntries(Object.entries(prior.geometry).map(([code, entry]) =>
    [code, json(directory + entry.file)]));
  const review = createCountyContextReview(records, inventories, collections, {
    geometry_checks: json(directory + "geometry-verification.json"),
  });
  return { records, collections, review, selected };
}

test("the pinned successor reproduces every numerical join without changing any geography or other source", async () => {
  const { records, collections, review, selected } = fixture();
  const body = JSON.stringify(review, null, 2) + "\n";
  assert.equal(Buffer.byteLength(body), successor.pointer.review_bytes);
  assert.equal(digest(body), successor.pointer.review_sha256);
  assert.deepEqual(review.geometry, prior.geometry);
  assert.deepEqual(review.excluded, prior.excluded);
  assert.deepEqual(review.source_selections, prior.source_selections);
  assert.deepEqual(review.observations.filter(row => row.county_id !== selected.county_id),
    prior.observations.filter(row => row.county_id !== selected.county_id));
  const mapped = await contextualCountyRows(records.filter(row => row.state_code === "WA"), review,
    collections.WA, "WA", review.context_base_url, review.geometry.WA.file);
  assert.equal(mapped.size, 39);
  assert.equal(mapped.get("53033").ballots, 935956);
  assert.equal(mapped.get("53033").reported_pct, null);
  assert.equal(mapped.get("53033").maps_approved, false);
  const loaded = loadCountPublication().countyContext;
  assert.equal(loaded.coverage.WA.counties, 39);
  assert.equal(loaded.coverage.WA.rates, 38);
  assert.deepEqual(loaded.downloads.slice(successor.pointer.downloads.length), baseline.downloads);
});

test("a successor never bypasses full-record or geometry checksum qualification", async () => {
  const { records, collections, review, selected } = fixture();
  const rows = records.filter(row => row.state_code === "WA");
  const match = rows.find(row => row.county_id === selected.county_id);
  match.ballots++;
  const mapped = await contextualCountyRows(rows, review, collections.WA, "WA",
    review.context_base_url, review.geometry.WA.file);
  assert.equal(mapped.size, 38);
  assert.equal(mapped.has("53033"), false);
  const changed = structuredClone(collections.WA);
  changed.features[0].properties.name += " changed";
  assert.equal((await contextualCountyRows(rows, review, changed, "WA",
    review.context_base_url, review.geometry.WA.file)).size, 0);
});

test("successors reject changed preimages, mutable source URLs and invalid full-download pins", () => {
  for (const change of [
    value => { value.predecessor_review_sha256 = "0".repeat(64); },
    value => { value.pointer.base_url = value.pointer.base_url.replace(/[a-f0-9]{40}/, "main"); },
    value => { value.pointer.review_bytes = 0; },
    value => { value.pointer.review_sha256 = "not-a-pin"; },
    value => { value.pointer.complete_download_sha256 = ""; },
  ]) {
    const changed = structuredClone(successor);
    change(changed);
    assert.throws(() => countyContextSuccessor(baseline, changed), /Invalid pinned/);
  }
});

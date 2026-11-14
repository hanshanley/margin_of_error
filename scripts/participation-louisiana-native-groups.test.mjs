import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { gunzipSync } from "node:zlib";
import { validateLouisianaGroupIndex, validateLouisianaGroupState,
  validateLouisianaGeometry, createLouisianaGroupReader, canonicalOwnVotesShare } from
  "../public/scripts/participation-louisiana-native-groups.js";
import { checkedDatasetFile } from "../public/scripts/participation-dataset.js";

const dataset = new URL("./fixtures/louisiana-native-groups/", import.meta.url);
const json = async path => JSON.parse(await readFile(new URL(path, dataset)));
const gz = async path => JSON.parse(gunzipSync(await readFile(new URL(path, dataset))));

test("accepted Louisiana candidate validates all controls, residuals, zeros and context geometry", async () => {
  const index = validateLouisianaGroupIndex(await json("index.json"));
  const state = validateLouisianaGroupState(await gz("states/LA.json.gz"));
  const geometry = validateLouisianaGeometry(await gz("references/LA-context.json.gz"), state);
  assert.equal(index.state.group_bindings, 448);
  assert.equal(state.parishes.length, 64);
  assert.equal(state.state_parent.votes, 536190);
  assert.equal(state.state_parent.margin_residuals.sex, 278);
  assert.equal(state.parishes.filter(row => row.margin_residuals.sex !== 0).length, 37);
  assert.equal(geometry.features.length, 64);
  assert.equal([...state.parishes, state.state_parent]
    .flatMap(row => Object.values(row.native_fields)).filter(value => value === 0).length, 21);
});

test("validator rejects promotions and every group/native/share/key/reference inconsistency", async () => {
  for (const mutate of [
    state => { state.semantics.native_abs_is_mail_returned = true; },
    state => { state.state_parent.margin_residuals.sex = 0; },
    state => { state.parishes[0].reference.native_code_is_fips = true; },
    state => { state.parishes[0].reference.context_not_2026_voting_precinct = false; },
    state => { state.parishes[0].groups[0].turnout_rate = 0; },
    state => {
      const row = state.parishes[0], white = row.groups[0], black = row.groups[1];
      white.count += 1; black.count -= 1;
      white.share_of_own_native_votes = canonicalOwnVotesShare(white.count, row.votes);
      black.share_of_own_native_votes = canonicalOwnVotesShare(black.count, row.votes);
    },
    state => { state.parishes[0].groups[0].share_of_own_native_votes = "99.000000000000000000"; },
    state => { delete state.parishes[0].native_fields.WHITE; },
    state => { state.parishes[1].source_key = state.parishes[0].source_key; },
    state => { state.parishes[1].native_code = state.parishes[0].native_code; },
    state => { state.parishes[1].native_label = state.parishes[0].native_label; },
    state => { state.parishes[0].reference.reference_sha256 = "a".repeat(64); },
    state => { state.parishes[1].reference = structuredClone(state.parishes[0].reference); },
    state => { state.parishes[0].groups[0].dimension = "sex"; },
  ]) {
    const state = await gz("states/LA.json.gz");
    mutate(state);
    assert.throws(() => validateLouisianaGroupState(state), /Unqualified Louisiana/);
  }
});

test("geometry rejects duplicate keys and any key/name mismatch", async () => {
  const state = await gz("states/LA.json.gz");
  for (const mutate of [
    geometry => { geometry.features[1] = structuredClone(geometry.features[0]); },
    geometry => { geometry.features[0].properties.name = "Changed Parish"; },
  ]) {
    const geometry = await gz("references/LA-context.json.gz");
    mutate(geometry);
    assert.throws(() => validateLouisianaGeometry(geometry, state), /Unqualified Louisiana/);
  }
});

test("unchanged shared checkedDatasetFile rejects old alias before fetch and accepts new alias", async () => {
  const body = await readFile(new URL("references/LA-context.json.gz", dataset));
  const declaration = { file: "references/LA-context.json.gz", bytes: body.length,
    sha256: createHash("sha256").update(body).digest("hex") };
  const base = `https://raw.githubusercontent.com/hanshanley/margin_of_error/${"a".repeat(40)}/dataset/`;
  const originalFetch = globalThis.fetch;
  let requests = 0;
  globalThis.fetch = async url => {
    requests += 1;
    assert.equal(String(url), base + declaration.file);
    return new Response(body, { status: 200 });
  };
  try {
    await assert.rejects(checkedDatasetFile(base,
      { ...declaration, file: "references/LA-context.geojson.gz" }),
    /Unqualified immutable dataset declaration/);
    assert.equal(requests, 0);
    const geometry = await checkedDatasetFile(base, declaration);
    assert.equal(requests, 1);
    assert.equal(geometry.features.length, 64);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("reader retries a failed body and never requests Louisiana data for another scope itself", async () => {
  const index = await json("index.json"), state = await gz("states/LA.json.gz");
  const geometry = await gz("references/LA-context.json.gz");
  const descriptor = await json("dataset.json");
  const entry = { id: "source-native-la-early-group-data", base_url: "https://example.test/immutable/",
    files: descriptor.files };
  let catalogs = 0, bodies = 0;
  const reader = createLouisianaGroupReader({
    loadDataset: async id => { catalogs += 1; assert.equal(id, entry.id); return { entry, index }; },
    checkedDatasetFile: async (_, declaration) => {
      bodies += 1;
      if (bodies === 1) throw new Error("Dataset: HTTP 503");
      return declaration.file.startsWith("states/") ? state : geometry;
    },
  });
  await assert.rejects(reader.load(), /HTTP 503/);
  const result = await reader.load();
  assert.equal(result.state, state);
  assert.equal(catalogs, 1);
  assert.equal(bodies, 4);
  const changed = structuredClone(entry);
  changed.files[index.reference.file].sha256 = "a".repeat(64);
  const rejected = createLouisianaGroupReader({
    loadDataset: async () => ({ entry: changed, index }),
    checkedDatasetFile: async () => { throw new Error("must not fetch"); },
  });
  await assert.rejects(rejected.loadIndex(), /dataset declaration/);
});

test("explorer uses one common selected-state/year scope hook without a second async state path", async () => {
  const source = await readFile(new URL("../public/scripts/participation-explorer.js", import.meta.url), "utf8");
  const module = await readFile(new URL("../public/scripts/participation-louisiana-native-groups.js", import.meta.url), "utf8");
  assert.match(source, /historicalNativeCounts\.setScope\(scope\);\s+louisianaNativeGroups\.setScope\(scope\);/);
  assert.equal((source.match(/syncHistoricalNativeScope\(\)/g) || []).length, 3);
  assert.doesNotMatch(source, /fetch\([^)]*Louisiana/);
  assert.doesNotMatch(source, /source-native-la-early-group-data/);
  assert.match(module, /panel\.hidden = !value\.enabled \|\| value\.year !== 2026 \|\| value\.code !== "LA"/);
  assert.match(module, /const token = generation;/);
  assert.ok((module.match(/token !== generation/g) || []).length >= 2);
  assert.match(module, /if \(!panel\.open \|\| panel\.hidden \|\| loaded\) return;/);
  assert.match(module, /reviewed 2026 parish context/);
  assert.doesNotMatch(module, /Context shapes are 2026 Census parishes/);
  assert.match(module, /svg\.style\.width = "100%";\s+svg\.style\.height = "auto";/);
});

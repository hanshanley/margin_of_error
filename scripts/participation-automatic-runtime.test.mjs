import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";
import { readFileSync } from "node:fs";
import {
  automaticRuntimeURL, loadAutomaticRuntime, resetAutomaticRuntimeForTests,
  validateAutomaticRuntime,
  loadAutomaticSenatePartial,
  loadAutomaticSenateComplete,
  loadAutomaticTurnoutHistory,
  loadPennsylvaniaVoteHistory,
} from "../public/scripts/participation-automatic-runtime.js";

const hash = body => createHash("sha256").update(body).digest("hex");
const bodyPin = path => {
  const body = Buffer.from(`fixture:${path}`);
  return { path, compression: "gzip", media_type: "application/json",
    bytes: body.length, sha256: hash(body), decoded_bytes: body.length + 10,
    decoded_sha256: hash(Buffer.concat([body, Buffer.from("0123456789")])) };
};
const states = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(" ");
const profiles = ["original", "attenuated", "full"];
const families = ["accepted_ridge_multinomial", "histogram_gradient_boosting",
  "extra_randomized_trees"];
const runtimeVersion = "1".repeat(64);
const runtimeCommit = "2".repeat(40);
const inputVersion = "3".repeat(64);
const download = { url: "https://github.com/hanshanley/margin_of_error/releases/download/runtime-fixture/complete-analysis.zip",
  bytes: 100, sha256: "4".repeat(64), immutable: true, verified_anonymously: true };

function houseSources() {
  const base_url =
    `https://raw.githubusercontent.com/hanshanley/margin_of_error/${runtimeCommit}/automatic/versions/${runtimeVersion}/`;
  const publishedPin = path => ({ ...bodyPin(path), url: new URL(path, base_url).href });
  const qualified = states.slice(0, 33), held = states.slice(33);
  const controls = Object.fromEntries(profiles.map(profile => [profile,
    Object.fromEntries(families.map(family => [family, `${profile}/${family}`]))]));
  const descriptors = {};
  for (const profile of profiles) for (const family of families) {
    const key = `${profile}/${family}`;
    descriptors[key] = {
      contract: "participation.automatic_house_source_descriptor.v1",
      control_key: key, profile, family, election_date: "2026-11-03",
      version: hash(Buffer.from(key)), estimate_contract: "participation.norc_house_demographic_model.v1",
      qualified_state_codes: qualified, held_state_codes: held,
      qualification_mask_sha256: "5".repeat(64), hold_identity_sha256: "6".repeat(64),
      gate_identity_sha256: "7".repeat(64), official_source_guard_sha256: "8".repeat(64),
      official_source_states: ["HI", "WY"], changed_states: ["AR"],
      source_model_refitted: false, source_weights_changed: false,
      existing_17_behavioral_holds_preserved: true,
      official_HI_WY_scope_guarded: true,
      unchanged_state_numerics_and_complete_queries_reused: true,
      complete_result: publishedPin(`house/results/${profile}-${family}.json.gz`),
      viewer_data: publishedPin(`house/viewers/${profile}-${family}.json.gz`),
    };
  }
  return {
    contract: "participation.automatic_house_sources.v1",
    version: "a".repeat(64), base_url, publication_bound: true,
    election_date: "2026-11-03", profiles, families, controls, descriptors,
    atomic_rejection_required_if_any_selected_body_pin_or_identity_fails: true,
    profile_viewers: Object.fromEntries(profiles.map(profile => [profile, {
      contract: "participation.automatic_house_profile_viewer.v1", profile, families,
      control_keys: families.map(family => `${profile}/${family}`),
      viewer_data: publishedPin(`house/profiles/${profile}.json.gz`),
    }])),
    recorded_states: { contract: "participation.automatic_recorded_house_states.v1",
      ...publishedPin("house/recorded-states.json.gz") },
    sensitivity: { contract: "participation.house_model_sensitivity.v1",
      ...publishedPin("house/sensitivity.json.gz") },
    shared_max_abs_margin: { "": 80, "AGE6|65_plus": 80 },
    participation_state_projections: { contract: "participation.registered_control_display.v2",
      ...publishedPin("participation/state-projections.json.gz") },
    qualification: { districts: 435, candidate_inventory_rows: 1401,
      mask_sha256: "5".repeat(64), hold_identity_sha256: "6".repeat(64),
      gate_identity_sha256: "7".repeat(64), official_source_guard_sha256: "8".repeat(64),
      qualified_state_codes: qualified, held_state_codes: held },
    complete_download: { required: true, path: "complete-results.zip",
      url: download.url, bytes: download.bytes, sha256: download.sha256,
      media_type: "application/zip" },
  };
}

function countEntry(commit=runtimeCommit) {
  const index = Buffer.from('{"contract":"participation.count_index.v1","year":2026}\n');
  const declaration = { file: "index.json", bytes: index.length, sha256: hash(index) };
  return {
    contract: "participation.dataset.v1", id: "participation-counts-2026", status: "loaded",
    record_contract: "participation.count_snapshot.v1", version: "9".repeat(64),
    staged_commit: commit,
    base_url: `https://raw.githubusercontent.com/hanshanley/margin_of_error/${commit}/datasets/participation-counts-2026/${"9".repeat(64)}/`,
    index: declaration, files: { "index.json": { bytes: declaration.bytes, sha256: declaration.sha256 } },
    complete_download: download,
  };
}
function countFixture(marker, commit, version) {
  const index = Buffer.from(JSON.stringify(
    { contract: "participation.count_index.v1", year: 2026, marker }) + "\n");
  const declaration = { file: "index.json", bytes: index.length, sha256: hash(index) };
  return { index, entry: {
    contract: "participation.dataset.v1", id: "participation-counts-2026", status: "loaded",
    record_contract: "participation.count_snapshot.v1", version, staged_commit: commit,
    base_url: `https://raw.githubusercontent.com/hanshanley/margin_of_error/${commit}/datasets/participation-counts-2026/${version}/`,
    index: declaration, files: { "index.json": { bytes: declaration.bytes, sha256: declaration.sha256 } },
    complete_download: download,
  } };
}

function manifest() {
  return {
    contract: "participation.automatic_runtime.v1", version: runtimeVersion,
    election_date: "2026-11-03", processing_version: "website-test-v1",
    input_results_version: inputVersion, checked_at: "2026-11-14T14:00:00+00:00",
    counts: countEntry(), house_sources: houseSources(),
    source_models_refitted: false, geographic_joins_changed: false,
    all_states_certified_or_precinct_complete: false,
    complete_download: download,
  };
}

test("the latest runtime accepts one committed count/model snapshot and all nine guarded controls", () => {
  const result = validateAutomaticRuntime(manifest());
  assert.equal(result.runtime_commit, runtimeCommit);
  assert.equal(Object.keys(result.house_sources.descriptors).length, 9);
  assert.equal(result.house_sources.qualification.qualified_state_codes.length, 33);
  assert.equal(result.house_sources.qualification.held_state_codes.length, 17);
});

function congressDescriptor() {
  const result = {
    ...bodyPin("congressional/results.json.gz"),
    contract: "participation.congressional_results.v1",
    base_url: houseSources().base_url, complete_download: download,
    downloads: Object.fromEntries(["results.json.gz", "queries.json.gz", "congress-races.csv",
      "congress-candidates.csv", "congress-coverage.csv", "congress-comparisons.csv",
      "congress-house-states.csv"]
      .map(file => [`congressional/${file}`, bodyPin(`congressional/${file}`)])),
  };
  return result;
}

test("both chambers require complete queries and one coherent runtime commit", () => {
  const value = manifest();
  value.congressional = congressDescriptor();
  assert.equal(validateAutomaticRuntime(value).runtime_commit, runtimeCommit);
  for (const mutate of [
    row => { row.base_url = row.base_url.replace(runtimeCommit, "f".repeat(40)); },
    row => { delete row.downloads["congressional/queries.json.gz"]; },
    row => { row.downloads[row.path].sha256 = "f".repeat(64); },
    row => { row.complete_download = { ...row.complete_download, bytes: 42 }; },
  ]) {
    const invalid = manifest();
    invalid.congressional = congressDescriptor();
    mutate(invalid.congressional);
    assert.throws(() => validateAutomaticRuntime(invalid), /Congressional|committed snapshot/);
  }
});

test("mixed commits, corruption metadata and changed hold identities reject the whole runtime", () => {
  for (const mutate of [
    value => { value.counts = countEntry("a".repeat(40)); },
    value => { value.counts.index.sha256 = "b".repeat(64); },
    value => { value.house_sources.descriptors["full/extra_randomized_trees"].held_state_codes.pop(); },
    value => { value.house_sources.descriptors["attenuated/accepted_ridge_multinomial"].official_source_states = ["HI"]; },
    value => { value.source_models_refitted = true; },
  ]) {
    const value = manifest(); mutate(value);
    assert.throws(() => validateAutomaticRuntime(value), /runtime|count|House|gate|scope|inventory/i);
  }
});

test("House snapshots require the producer's versioned namespace, not an unversioned lookalike", () => {
  const value = manifest();
  value.house_sources = JSON.parse(JSON.stringify(value.house_sources)
    .replaceAll(`/automatic/versions/${runtimeVersion}/`, `/automatic/${runtimeVersion}/`));
  assert.throws(() => validateAutomaticRuntime(value), /House source contract/);
});

test("concurrent consumers select the same no-cache latest pointer without a late second fetch", async () => {
  resetAutomaticRuntimeForTests();
  const original = globalThis.fetch;
  let requests = 0;
  try {
    globalThis.fetch = async (url, options) => {
      requests++;
      assert.equal(url, automaticRuntimeURL);
      assert.equal(options.cache, "no-cache");
      await new Promise(resolve => setTimeout(resolve, 10));
      return Response.json(manifest());
    };
    const [first, second] = await Promise.all([loadAutomaticRuntime(), loadAutomaticRuntime()]);
    assert.equal(first.version, runtimeVersion);
    assert.equal(second, first);
    assert.equal(requests, 1);
  } finally {
    globalThis.fetch = original;
    resetAutomaticRuntimeForTests();
  }
});

test("Astro-bundled and standalone readers share one page-session snapshot", async () => {
  resetAutomaticRuntimeForTests();
  const standalone = await import(
    "../public/scripts/participation-automatic-runtime.js?standalone-reader-copy");
  const original = globalThis.fetch;
  let requests = 0;
  try {
    globalThis.fetch = async () => {
      requests++;
      await new Promise(resolve => setTimeout(resolve, 10));
      return Response.json(manifest());
    };
    const [bundled, external] = await Promise.all([
      loadAutomaticRuntime(), standalone.loadAutomaticRuntime(),
    ]);
    assert.equal(requests, 1);
    assert.equal(bundled, external);
  } finally {
    globalThis.fetch = original;
    resetAutomaticRuntimeForTests();
    standalone.resetAutomaticRuntimeForTests();
  }
});

for (const [load, field, contract, path] of [
  [loadAutomaticSenatePartial, "senate_partial_scenarios",
    "participation.senate_legacy_partial_scenarios.v1", "senate/legacy-partial-results.json.gz"],
  [loadAutomaticSenateComplete, "senate_complete_scenarios",
    "participation.senate_complete_category_scenarios.v1", "senate/legacy-complete-results.json.gz"],
]) test(`the ${field} loader shares one pinned body, rejects corruption and retries without a new snapshot`, async () => {
  const original = globalThis.fetch;
  const data = { contract, rows: [] };
  const decoded = Buffer.from(JSON.stringify(data)), body = gzipSync(decoded);
  const declaration = {
    contract: data.contract, path,
    compression: "gzip", media_type: "application/json",
    bytes: body.length, sha256: hash(body), decoded_bytes: decoded.length, decoded_sha256: hash(decoded),
  };
  const value = manifest();
  declaration.url = new URL(declaration.path, value.house_sources.base_url).href;
  value.house_sources[field] = declaration;
  let manifests = 0, bodies = 0, corrupt = true;
  resetAutomaticRuntimeForTests();
  try {
    globalThis.fetch = async url => {
      if (url === automaticRuntimeURL) { manifests++; return Response.json(value); }
      assert.equal(url, declaration.url); bodies++;
      return new Response(corrupt ? Buffer.from("corrupt") : body);
    };
    await assert.rejects(load(), /checksum/);
    corrupt = false;
    const [first, second] = await Promise.all([load(), load()]);
    assert.deepEqual(first.data, data);
    assert.equal(first.data, second.data);
    assert.equal(manifests, 1);
    assert.equal(bodies, 2);
    resetAutomaticRuntimeForTests();
    delete value.house_sources[field];
    assert.equal(await load(), null);
    assert.equal(bodies, 2);
    for (const mutate of [
      item => { item.url = item.url.replace(runtimeCommit, "f".repeat(40)); },
      item => { item.contract = "unreviewed"; },
      item => { item.path = "../senate/legacy-partial-results.json.gz"; },
      item => { item.decoded_sha256 = "f".repeat(64); },
      item => { item.decoded_bytes++; },
    ]) {
      resetAutomaticRuntimeForTests();
      const changed = structuredClone(declaration); mutate(changed);
      value.house_sources[field] = changed;
      await assert.rejects(load());
    }
  } finally {
    globalThis.fetch = original;
    resetAutomaticRuntimeForTests();
  }
});

test("Pennsylvania history binds all age and county data and downloads to the active release", async () => {
  const pointer = manifest(), root = pointer.house_sources.base_url;
  const path = "participation/pennsylvania-general-election-vote-history";
  const dataPath = path + ".json.gz", csvPath = path + ".csv";
  const ages = ["18 to 24", "25 to 34", "35 to 44", "45 to 54", "55 to 64", "65 to 74", "75+"];
  const rows = [...Array.from({ length: 67 }, (_, i) => `County ${i}`), "TOTAL"].map(county => ({
    county, vote_history: 8, registered: 16, rate_pct: 50, age_not_tabulated: { vote_history: 1, registered: 2 },
    ages: ages.map(age => ({ age, vote_history: 1, registered: 2, rate_pct: 50 })),
  }));
  const decoded = Buffer.from(JSON.stringify({
    contract: "participation.pa_sure_general_vote_history.v1", state_code: "PA",
    certified_ballots_cast: false, geographic_allocation: false,
    editions: [{ year: 2024, election_date: "2024-11-05", status: "reported", rows }],
  }));
  const compressed = gzipSync(decoded), dataURL = new URL(dataPath, root).href;
  const csvURL = new URL(csvPath, root).href;
  const files = pointer.house_sources.pennsylvania_general_vote_history = {
    data: { ...bodyPin(dataPath), url: dataURL, bytes: compressed.length, sha256: hash(compressed),
      decoded_bytes: decoded.length, decoded_sha256: hash(decoded) },
    csv: { path: csvPath, url: csvURL, bytes: 8, sha256: hash(Buffer.from("csv-data")) },
  };
  pointer.house_sources.base_url = root.replace(/\/$/, "");
  const original = globalThis.fetch;
  try {
    resetAutomaticRuntimeForTests();
    globalThis.fetch = async url => {
      if (String(url) === automaticRuntimeURL) return Response.json(pointer);
      if (String(url) === dataURL) return new Response(compressed);
      throw new Error("Unpinned request: " + url);
    };
    const history = await loadPennsylvaniaVoteHistory();
    assert.equal(history.data.editions[0].rows.length, 68);
    assert.equal(history.csv, csvURL);
    assert.equal(history.complete, pointer.complete_download.url);
    resetAutomaticRuntimeForTests();
    files.csv.url = "https://example.test/other.csv";
    await assert.rejects(loadPennsylvaniaVoteHistory(), /not bound/);
  } finally {
    globalThis.fetch = original;
    resetAutomaticRuntimeForTests();
  }
});

test("North Carolina history uses source-defined eligible voters, not registration", async () => {
  const pointer = manifest(), root = pointer.house_sources.base_url.replace(/\/$/, "");
  pointer.house_sources.base_url = root;
  const path = "participation/north-carolina-general-election-turnout-history";
  const dataPath = path + ".json.gz", csvPath = path + ".csv", url = `${root}/${dataPath}`;
  const data = {
    contract: "participation.statewide_general_election_history.v1", state_code: "NC", status: "reported",
    current_election_status: "not_yet_published", native_denominator: "Eligible Voters", native_measure: "Ballots Cast",
    source: { url: "https://www.ncsbe.gov/results-data/voter-turnout" },
    complete_native_query: Array.from({ length: 27 }, (_, i) => ({
      year: 2024 - 2 * i, ballots_cast: 3, eligible_voters: 10, rate_qualified: true, published_turnout: "30%",
    })),
  };
  let zipped;
  const setBody = () => {
    const body = Buffer.from(JSON.stringify(data));
    zipped = gzipSync(body);
    pointer.house_sources.general_election_turnout_history = { NC: {
      data: { ...bodyPin(dataPath), url, bytes: zipped.length, sha256: hash(zipped),
        decoded_bytes: body.length, decoded_sha256: hash(body) },
      csv: { path: csvPath, url: `${root}/${csvPath}`, bytes: 8, sha256: hash("csv-data") },
    } };
  };
  const original = globalThis.fetch;
  try {
    resetAutomaticRuntimeForTests();
    setBody();
    globalThis.fetch = async path => {
      if (String(path) === automaticRuntimeURL) return Response.json(pointer);
      if (String(path) === url) return new Response(zipped);
      throw new Error("Unpinned request: " + path);
    };
    const history = await loadAutomaticTurnoutHistory("NC");
    assert.equal(history.denominator, "eligible_voters");
    assert.equal(history.data.complete_native_query.length, 27);
    assert.equal(history.csv, `${root}/${csvPath}`);
    resetAutomaticRuntimeForTests();
    data.native_denominator = "Registered Voters";
    setBody();
    await assert.rejects(loadAutomaticTurnoutHistory("NC"), /scope or rows differ/);
  } finally {
    globalThis.fetch = original;
    resetAutomaticRuntimeForTests();
  }
});

test("the existing dataset reader selects changed latest counts and falls back atomically on corruption", async () => {
  const old = countFixture("accepted-build", "b".repeat(40), "c".repeat(64));
  const latest = countFixture("automatic-latest", runtimeCommit, "d".repeat(64));
  const original = globalThis.fetch;
  for (const corrupt of [false, true]) {
    resetAutomaticRuntimeForTests();
    const pointer = manifest();
    delete pointer.house_sources;
    pointer.counts = latest.entry;
    try {
      globalThis.fetch = async url => {
        url = String(url);
        if (url === automaticRuntimeURL) return Response.json(pointer);
        if (url.endsWith("/catalog.json"))
          return Response.json({ contract: "participation.dataset_catalog.v1",
            datasets: { "participation-counts-2026": old.entry } });
        if (url === latest.entry.base_url + "index.json")
          return new Response(corrupt ? Buffer.concat([latest.index, Buffer.from("x")]) : latest.index);
        if (url === old.entry.base_url + "index.json") return new Response(old.index);
        throw new Error(`Unexpected fixture request: ${url}`);
      };
      const { loadDataset } = await import(
        `../public/scripts/participation-dataset.js?latest-selection=${corrupt}`);
      const selected = await loadDataset("participation-counts-2026");
      assert.equal(selected.index.marker, corrupt ? "accepted-build" : "automatic-latest");
      assert.equal(Boolean(selected.automatic_runtime), !corrupt);
    } finally {
      globalThis.fetch = original;
      resetAutomaticRuntimeForTests();
    }
  }
});

test("the website workflow is data-only and the overlapping legacy refresh is manual", () => {
  const workflow = readFileSync(new URL("../.github/workflows/automatic-runtime.yml", import.meta.url), "utf8");
  assert.match(workflow, /cron: "31 \* \* \* \*"/);
  assert.match(workflow, /contents: write/);
  assert.doesNotMatch(workflow, /pull-requests: write|actions: write|\bPAT\b|PERSONAL_ACCESS/);
  assert.match(workflow, /ref: [a-f0-9]{40}/);
  assert.match(workflow, /data\/results-intake\/model-seed/);
  assert.match(workflow, /GH_TOKEN: \$\{\{ github\.token \}\}/);
  assert.match(workflow, /python -m scripts\.automatic_runtime/);
  assert.match(workflow, /pointer="\$RESULTS_POINTER"\s+if \[ -z "\$pointer" \]; then/);
  assert.match(workflow, /git ls-remote --exit-code[\\\s]+https:\/\/github\.com\/hanshanley\/voter-participation\.git refs\/tags\/results-data/);
  assert.match(workflow, /pointer="https:\/\/raw\.githubusercontent\.com\/hanshanley\/voter-participation\/\$source_commit\/latest\.json"/);
  assert.match(workflow, /--results-pointer "\$pointer"/);
  assert.match(workflow, /--repository "\$GITHUB_WORKSPACE"/);
  const legacy = readFileSync(new URL("../.github/workflows/refresh-2026-data.yml", import.meta.url), "utf8");
  assert.match(legacy, /workflow_dispatch:/);
  assert.doesNotMatch(legacy, /\bschedule:/);
});

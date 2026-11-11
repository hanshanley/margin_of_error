import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { pathToFileURL } from "node:url";
import { gzipSync, gunzipSync } from "node:zlib";
import { encoded, digest, pin } from "./compile-participation-counts.mjs";
import { declarationFor } from "./extend-participation-counts.mjs";
import { canonicalJson } from "../public/scripts/participation-county-context.js";
import { validateCountShard, countFrame } from "../public/scripts/participation-counts.js";
import { countyQualifier, bindCountyReference } from "../public/scripts/participation-native-bindings.js";

const nameKey = value => value.normalize("NFKC").trim().toUpperCase().replace(/ COUNTY$/, "");
function dataset(id, contract, files) {
  const declarations = Object.fromEntries(Object.entries(files).sort().map(([name, body]) => [name, pin(body)]));
  return { files, descriptor: { contract: "participation.dataset.v1", id,
    version: digest(encoded({ files: declarations, contract })), record_contract: contract,
    files: declarations, index: { file: "index.json", ...declarations["index.json"] }, complete_download: null } };
}

export function qualifyCountyBindings(countFiles, nativeFiles, inputs, recipe, sourceCommit) {
  assert.equal(recipe.contract, "participation.county_binding_extension.v1");
  assert.match(sourceCommit, /^[a-f0-9]{40}$/);
  for (const [file, expected] of [["reference.json", recipe.geometry_sha256],
    ["previous-review.json", recipe.previous_review_sha256], ["native-facts.json", recipe.native_facts_sha256]])
    assert.equal(digest(inputs[file]), expected, "Pinned full qualification input differs");
  assert.ok(recipe.modes.length && new Set(recipe.modes).size === recipe.modes.length);
  assert.ok(recipe.modes.every(mode => ["available", "official", "uf_vep", "uf_vap"].includes(mode)),
    "Reference qualification cannot change early/returned source frames");
  assert.equal(new Set(recipe.new_source_ids).size, recipe.new_source_ids.length);
  const geometry = JSON.parse(inputs["reference.json"]), review = JSON.parse(inputs["previous-review.json"]);
  const facts = JSON.parse(inputs["native-facts.json"]), code = recipe.state_code;
  assert.equal(digest(Buffer.from(canonicalJson(geometry))), recipe.geometry_canonical_sha256);
  assert.equal(review.geometry[code].canonical_sha256, recipe.geometry_canonical_sha256);
  assert.equal(review.geometry[code].sha256, recipe.geometry_sha256);
  assert.equal(review.geometry[code].boundary_year, recipe.boundary_year);
  assert.equal(geometry.features.length, recipe.expected_counties);
  const features = new Map(), keys = new Set();
  for (const feature of geometry.features) {
    const p = feature.properties, normalized = nameKey(p.name);
    assert.equal(p.state_code, code, "Reference state differs");
    assert.equal(p.boundary_year, recipe.boundary_year, "Reference vintage differs");
    assert.ok(["Polygon", "MultiPolygon"].includes(feature.geometry.type));
    assert.ok(!features.has(normalized) && !keys.has(p.key), "Ambiguous county reference identity");
    features.set(normalized, feature); keys.add(p.key);
  }
  const counts = { ...countFiles }, native = { ...nativeFiles };
  const countIndex = JSON.parse(counts["index.json"]), nativeIndex = JSON.parse(native["index.json"]);
  const declaration = countIndex.states[code];
  assert.ok(declaration);
  const shard = JSON.parse(gunzipSync(counts[declaration.file]));
  const byId = new Map(shard.records.map(row => [row.id, row]));
  const frame = shard.views[recipe.modes[0]];
  assert.ok(frame.qualified && frame.counties.length === recipe.expected_counties);
  for (const mode of recipe.modes) {
    assert.ok(shard.views[mode].qualified);
    assert.deepEqual(shard.views[mode].counties, frame.counties, "Selected county frames differ");
    assert.ok(!nativeIndex.county_bindings[code]?.[mode], "Cannot overwrite an accepted native binding");
  }
  const reference = { url: `https://raw.githubusercontent.com/hanshanley/margin_of_error/${sourceCommit}/${recipe.reference_repository_path}`,
    sha256: recipe.geometry_sha256, uncompressed_sha256: recipe.geometry_sha256,
    boundary_year: recipe.boundary_year, counties: recipe.expected_counties,
    geography_scope: "qualified_whole_county_context",
    review_id: recipe.id, complete_download_url: recipe.complete_download_url };
  const queries = [], seen = new Set(), newSources = new Set();
  for (const id of frame.counties) {
    const row = byId.get(id), view = row.view;
    assert.equal(row.geography.level, "county");
    assert.equal(view.geography_level, "county");
    assert.equal(view.state_code, code); assert.equal(view.year, 2026);
    assert.equal(row.count.status, "reported"); assert.ok(Number.isSafeInteger(row.count.value));
    const feature = features.get(nameKey(view.county));
    assert.ok(feature && !seen.has(feature.properties.key), "Missing or duplicate whole-county identity");
    seen.add(feature.properties.key);
    const prior = review.observations.filter(item => item.state_code === code && item.county_id === view.county_id);
    const beforeHash = digest(Buffer.from(canonicalJson(view)));
    let disposition;
    if (prior.length) {
      assert.equal(prior.length, 1);
      assert.equal(prior[0].source_record_sha256, beforeHash, "Old exact-record-hash oracle differs");
      assert.equal(prior[0].contextual_geoid, feature.properties.key);
      assert.equal(prior[0].contextual_map_approved, true);
      disposition = "retained_accepted_contextual_identity";
    } else {
      assert.ok(recipe.new_source_ids.includes(row.source.id), "Unregistered new geographic qualification");
      const reports = facts.reports.filter(report => report.geography.state_code === code
        && nameKey(report.geography.name) === nameKey(view.county));
      assert.equal(reports.length, 1);
      const report = reports[0];
      assert.equal(report.geography.level, "county");
      assert.equal(report.election.id, row.election.id);
      assert.ok(report.rows.some(item => nameKey(item.label) === nameKey(view.county)
        && item.label.endsWith(" County")), "Native county heading is missing");
      assert.deepEqual(row.source.fields, report, "Full native county sufficient facts differ");
      assert.equal(row.source.input_sha256, recipe.native_facts_sha256);
      assert.equal(row.denominator, null); assert.equal(view.reported_pct, null);
      assert.ok(!newSources.has(row.source.id));
      newSources.add(row.source.id);
      disposition = "qualified_new_source_to_existing_contextual_county";
    }
    queries.push({ id: row.id, county_id: view.county_id, county: view.county,
      source_record_sha256: beforeHash, feature_key: feature.properties.key, disposition,
      geometry_sha256: reference.sha256, boundary_year: recipe.boundary_year,
      count: row.count.value, rate: view.reported_pct, source_id: row.source.id });
    row.geography.join = { status: "approved", reference_id: reference.sha256,
      feature_key: feature.properties.key,
      evidence: "Qualified whole-county identity on unchanged held contextual geometry; not certified 2026 election or precinct boundaries." };
    view.maps_approved = true;
    view.reference_geometry = reference;
  }
  assert.equal(newSources.size, recipe.expected_new);
  assert.equal(queries.filter(row => row.disposition.startsWith("retained")).length, recipe.expected_retained);
  assert.equal(seen.size, geometry.features.length);
  const rows = frame.counties.map(id => byId.get(id).view);
  const binding = { sha256: reference.sha256, features: geometry.features.length,
    feature_keys: geometry.features.map(feature => feature.properties.key),
    feature_scopes: Object.fromEntries(geometry.features.map(({ properties: p }) => [p.key,
      { state_code: p.state_code, name: p.name, boundary_year: p.boundary_year }])),
    rows: queries.map(query => ({ feature_key: query.feature_key, county_id: query.county_id,
      qualifier: countyQualifier(byId.get(query.id).view) })),
    approval: { id: recipe.id, geometry_unchanged: true, source_counts_unchanged: true,
      retained_contextual_identities: recipe.expected_retained, newly_qualified_identities: recipe.expected_new,
      certified_election_boundaries: false, precinct_allocation: false } };
  for (const mode of recipe.modes) {
    assert.equal(bindCountyReference(countFrame(shard, mode).counties, geometry, reference, binding).size,
      recipe.expected_counties);
    (nativeIndex.county_bindings[code] ||= {})[mode] = binding;
  }
  const extension = { id: recipe.id, state_code: code, retained: recipe.expected_retained,
    newly_qualified: recipe.expected_new, unchanged_geometry_sha256: reference.sha256,
    counts_or_rates_changed: false, new_geometry: false };
  nativeIndex.extensions = [...(nativeIndex.extensions || []), extension];
  nativeIndex.county_frame_checks += recipe.modes.length;
  countIndex.extensions = [...(countIndex.extensions || []), extension];
  const body = gzipSync(encoded(shard), { level: 9 });
  counts[declaration.file] = body;
  countIndex.states[code] = declarationFor(shard, declaration, body);
  validateCountShard(shard, code, countIndex.states[code]);
  counts["index.json"] = encoded(countIndex);
  native["index.json"] = encoded(nativeIndex);
  return { counts: dataset("participation-counts-2026", "participation.count_snapshot.v1", counts),
    native: dataset("participation-native-bindings-2026", "participation.native_bindings.v1", native),
    queries, reference };
}

export function readDataset(root) {
  const descriptor = JSON.parse(readFileSync(resolve(root, "dataset.json")));
  return Object.fromEntries(Object.entries(descriptor.files).map(([name, expected]) => {
    const body = readFileSync(resolve(root, name));
    assert.deepEqual(pin(body), expected, "Baseline runtime checksum differs");
    return [name, body];
  }));
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const args = Object.fromEntries(process.argv.slice(2).reduce((rows, value, i, all) =>
    i % 2 ? rows : [...rows, [value.replace(/^--/, ""), all[i + 1]]], []));
  assert.ok(args.counts && args.native && args.inputs && args.output && !existsSync(args.output));
  const recipe = JSON.parse(readFileSync(resolve(args.inputs, "recipe.json")));
  const inputs = Object.fromEntries(["reference.json", "previous-review.json", "native-facts.json"]
    .map(name => [name, readFileSync(resolve(args.inputs, name))]));
  const result = qualifyCountyBindings(readDataset(args.counts), readDataset(args.native), inputs, recipe, args.commit);
  for (const [family, value] of [["counts", result.counts], ["native", result.native]]) {
    for (const [name, body] of Object.entries(value.files)) {
      const path = resolve(args.output, family, name); mkdirSync(dirname(path), { recursive: true }); writeFileSync(path, body);
    }
    writeFileSync(resolve(args.output, family, "dataset.json"), encoded(value.descriptor));
  }
  writeFileSync(resolve(args.output, "county-binding-queries.json"), encoded(result.queries));
  writeFileSync(resolve(args.output, "reference.json"), encoded(result.reference));
  console.log(JSON.stringify({ counts: result.counts.descriptor.version, native: result.native.descriptor.version,
    qualified_counties: result.queries.length, new_identities: recipe.expected_new, geometry_changed: false }));
}

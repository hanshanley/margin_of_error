import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { gzipSync, gunzipSync } from "node:zlib";
import { encoded, pin, digest } from "./compile-participation-counts.mjs";
import { validateReferenceBindings, bindReferenceGeometry } from "../public/scripts/participation-reference-bindings.js";

const sourceId = "ky-jefferson-2026-native-statistics-precinct";
const reviewId = "ky-jefferson-lojic-reference-20261114-01";
const modes = ["available", "official", "uf_vep", "uf_vap"];
const sdkUrl = "https://github.com/hanshanley/margin_of_error/releases/download/"
  + "participation-ky-jefferson-precinct-reference-20261114-01/complete-analysis.zip";
const read = file => JSON.parse(readFileSync(file));

export function appendReferenceDataset(baseline, countDescription, countIndex, countBody, factsBody, candidateBody, approval) {
  assert.deepEqual(pin(factsBody), approval.dispositions_pin);
  assert.deepEqual(pin(candidateBody), approval.reference_candidate_pin);
  const facts = JSON.parse(factsBody), candidate = JSON.parse(candidateBody);
  const { description, files: originalFiles } = baseline, index = JSON.parse(originalFiles["index.json"]);
  assert.equal(description.id, "participation-native-bindings-2026");
  assert.equal(approval.status, "GO_source_data_partial_reference_only");
  assert.equal(approval.literal_reference_joins, facts.summary.candidate_eligible_literal_joins);
  assert.equal(approval.held_reporting_units, facts.summary.candidate_held_source_labels);
  assert.equal(facts.summary.source_counts_changed, false);
  assert.equal(facts.summary.geometries_repaired_or_clipped, false);
  assert.equal(facts.summary.suffixes_stripped_or_inferred, false);
  assert.equal(index.layers["precinct/KY"], undefined);
  assert.equal(index.reporting_tables.KY, undefined);
  assert.equal(index.config.states.KY, undefined);
  const declaration = countIndex.states.KY;
  assert.deepEqual(pin(countBody), { bytes: declaration.bytes, sha256: declaration.sha256 });
  assert.deepEqual(countDescription.files[declaration.file], pin(countBody));
  const source = JSON.parse(gunzipSync(countBody));
  const observations = source.records.filter(row => row.source.id === sourceId);
  const byId = new Map(observations.map(row => [row.id, row]));
  assert.equal(byId.size, facts.summary.native_labels);
  assert.equal(facts.source_rows.length, observations.length);
  const eligible = facts.source_rows.filter(row => row.candidate_reference_join_eligible);
  const held = facts.source_rows.filter(row => !row.candidate_reference_join_eligible);
  assert.equal(candidate.features.length, eligible.length);
  assert.deepEqual(new Set(candidate.features.map(f => f.properties.observation_id)),
    new Set(eligible.map(row => row.observation_id)));
  const byLabel = new Map(eligible.map(row => [row.native_label, row]));
  const geometry = { type: "FeatureCollection", features: candidate.features.map(feature => {
    const row = byLabel.get(feature.properties.native_label);
    assert.ok(row);
    assert.equal(feature.properties.reference_code, row.native_label);
    assert.equal(feature.properties.observation_id, row.observation_id);
    return { type: "Feature", properties: { key: row.native_label }, geometry: feature.geometry };
  }), reference_scope: facts.reference_scope, legend: facts.legend, coverage: facts.summary };
  const body = gzipSync(encoded(geometry), { level: 9 });
  const geometryFile = "geometry/" + digest(body) + ".json.gz";
  const geometryDeclaration = { file: geometryFile, ...pin(body) };
  const referenceLabel = "Public-authoritative LOJIC reference geometry retrieved November 14, 2026; "
    + "companion map printed November 7, 2026. Not certified as November 3 legal boundaries.";
  const metadata = {
    source_id: reviewId, reference_context_only: true, counts_only: true,
    reference_title: "Jefferson County, Kentucky · native counts on partial LOJIC reference",
    boundary_label: referenceLabel, ...pin(body), expected_features: eligible.length,
    native_source_reporting_rows: observations.length, held_table_only_reporting_rows: held.length,
    reference_coverage_label: `${eligible.length} exact-literal reference joins; ${held.length} reporting labels `
      + "remain held/unmapped, not zero. All 646 native counts remain in the source controls and complete downloads.",
    notes: "Sixty suffixed labels are not normalized. Invalid K161, six potential invalid-geometry neighbors "
      + "and fifty other literal overlap labels remain table-only. The service description refers to 2013/623; "
      + "the authoritative item cites 2020, while all current queries contain 646. Dates and source stages remain separate. "
      + "No geometry repairs, registered denominator, analysis rate, unique-person count or demographic allocation.",
    complete_download_url: sdkUrl, certified_legal_precinct_boundaries: false,
    rates_approved: false, geometry_retrieved_at_utc: facts.reference_scope.geometry_retrieved_at_utc,
    companion_map_printed_date: facts.reference_scope.companion_map_printed_date,
  };
  const data = {
    contract: "participation.reference_bindings.v1", id: "precinct/KY", state_code: "KY",
    geometry: geometryDeclaration, metadata,
    source_counts: { file: declaration.file, bytes: declaration.bytes, sha256: declaration.sha256,
      source_id: sourceId, source_rows: observations.length },
    review: { reviewed: true, review_id: reviewId, scope: "public_authoritative_reference_context",
      matching: "exact_literal_only", legal_election_boundaries_certified: false,
      rates_approved: false, source_observations_preserved: true,
      geometry_retrieved_at_utc: facts.reference_scope.geometry_retrieved_at_utc,
      reference_label: referenceLabel, omitted_units_note: facts.legend },
    rows: candidate.features.map(feature => {
      const observation = byId.get(feature.properties.observation_id), unit = observation.geography.name;
      assert.equal(unit, feature.properties.reference_code);
      assert.equal(observation.count.value, feature.properties.native_ballots);
      return { key: unit, geometry_type: feature.geometry.type, observation,
        properties: { ...structuredClone(observation.view), key: unit, maps_approved: true,
          registered: null, denominator: null, reported_pct: null,
          reference_context_only: true, legal_election_boundaries_certified: false,
          boundary_label: referenceLabel, source_count_observation_id: observation.id,
          reference_geometry: { ...geometryDeclaration, source_id: reviewId,
            boundary_vintage: null, source_metadata_revision: "retrieved 2026-11-14" },
          source_snapshot: reviewId, match_status: "qualified_literal_reference_context",
          rate_withheld_reason: "Native count only; no qualified source electorate or analysis fraction." } };
    }),
    held_rows: held.map(row => ({ observation_id: row.observation_id,
      native_label: row.native_label, reason: row.hold_reasons })),
  };
  validateReferenceBindings(data, "precinct/KY", source, declaration);
  const bound = bindReferenceGeometry(data, geometry, geometryDeclaration.sha256);
  assert.deepEqual(bound.features.map(f => f.properties.ballots), data.rows.map(row => row.observation.count.value));
  const files = { ...originalFiles, [geometryFile]: body };
  const layerFile = "counts/precinct-KY.json.gz";
  files[layerFile] = gzipSync(encoded(data), { level: 9 });
  index.layers["precinct/KY"] = {
    file: layerFile, ...pin(files[layerFile]), features: eligible.length,
    geometry_sha256: geometryDeclaration.sha256, eligible_modes: modes,
    coverage: { source_rows: eligible.length, reported: eligible.length, unknown: 0, withheld: 0, fractions: 0 },
    separate_reference_coverage: { all_source_rows: observations.length, mapped: eligible.length, held: held.length },
  };
  index.config.states.KY = geometryFile;
  index.config.state_metadata.KY = metadata;
  const tableFile = "tables/KY.json.gz";
  const table = { contract: "participation.reporting_units.v1", state_code: "KY",
    records: observations.map(observation => ({ observation,
      properties: { ...structuredClone(observation.view), key: observation.view.unit_key,
        precinct: observation.geography.name } })) };
  files[tableFile] = gzipSync(encoded(table), { level: 9 });
  index.reporting_tables.KY = { file: tableFile, ...pin(files[tableFile]), rows: observations.length,
    eligible_modes: modes, coverage: { source_rows: observations.length,
      reported: observations.length, unknown: 0, withheld: 0, fractions: 0 } };
  index.reporting_sources.KY = { data_url: tableFile, rows: observations.length,
    complete_download_url: sdkUrl, source_update_label: observations[0].source_clock.literal };
  index.separate_reference_reviews ||= {};
  index.separate_reference_reviews[reviewId] = {
    source_count_shard: data.source_counts, mapped: eligible.length, held: held.length,
    original_observations_unchanged: true, record_contract: data.contract,
    certified_election_day_geography: false,
  };
  files["index.json"] = encoded(index);
  for (const [file, original] of Object.entries(originalFiles))
    if (file !== "index.json") assert.deepEqual(files[file], original);
  const declarations = Object.fromEntries(Object.entries(files).sort().map(([file, value]) => [file, pin(value)]));
  const result = { ...description, version: digest(encoded({ files: declarations, contract: description.record_contract })),
    files: declarations, index: { file: "index.json", ...declarations["index.json"] }, complete_download: null };
  return { files, descriptor: result, index, binding: data };
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const [baselineRoot, countsRoot, factsRoot, approvalPath, output] = process.argv.slice(2).map(value => resolve(value));
  assert.ok(output && !existsSync(output));
  const description = read(`${baselineRoot}/dataset.json`);
  const files = Object.fromEntries(Object.entries(description.files).map(([file, expected]) => {
    const body = readFileSync(`${baselineRoot}/${file}`);
    assert.deepEqual(pin(body), expected); return [file, body];
  }));
  const counts = read(`${countsRoot}/dataset.json`), countIndex = read(`${countsRoot}/index.json`);
  const compiled = appendReferenceDataset({ description, files }, counts, countIndex,
    readFileSync(`${countsRoot}/${countIndex.states.KY.file}`),
    readFileSync(`${factsRoot}/complete-reference-dispositions.json`),
    readFileSync(`${factsRoot}/candidate-literal-only-reference.geojson`), read(approvalPath));
  for (const [file, body] of Object.entries(compiled.files)) {
    mkdirSync(dirname(`${output}/${file}`), { recursive: true });
    writeFileSync(`${output}/${file}`, body, { flag: "wx" });
  }
  writeFileSync(`${output}/dataset.json`, encoded(compiled.descriptor), { flag: "wx" });
  console.log(JSON.stringify({ version: compiled.descriptor.version, mapped: compiled.binding.rows.length,
    held: compiled.binding.held_rows.length, baseline_files_exact_except_index: Object.keys(files).length - 1 }));
}

import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { gzipSync, gunzipSync } from "node:zlib";
import vm from "node:vm";
import { execFileSync } from "node:child_process";
import * as legacy from "../public/scripts/participation-geography.js";
import { canonicalObservation, encoded, pin, digest } from "./compile-participation-counts.mjs";
import { countFrame, validateCountObservation } from "../public/scripts/participation-counts.js";
import { countyQualifier, validateNativeShard, bindNativeGeometry, bindCountyReference } from "../public/scripts/participation-native-bindings.js";

const revision = "c4ccdf4d677974ea9068724367263dc59d9d0d88";
export function heldPath(url, root) {
  const u = new URL(url, "https://www.themarginoferror.com");
  const path = u.hostname === "www.themarginoferror.com" ? "public" + u.pathname
    : u.hostname === "raw.githubusercontent.com" && u.pathname.startsWith("/hanshanley/margin_of_error/")
      ? u.pathname.split("/").slice(4).join("/") : null;
  if (!path || path.split("/").includes("..")) throw new Error("Not a held owned reference: " + url);
  const file = resolve(root, path);
  assert.ok(existsSync(file), "Missing held original: " + file);
  return file;
}
function nativeOracle(source, code, metadata, data) {
  const a = source.indexOf('  const minnesotaCompleteNative =', source.indexOf("async function drawCurrentPrecinctGeography"));
  const b = source.indexOf('  if (!file ||', a);
  const c = source.indexOf('    if (minnesotaNative &&', b);
  const d = source.indexOf('    state.currentPrecinctShapes.set(code, data);', c);
  assert.ok(a > 0 && b > a && c > b && d > c);
  vm.runInNewContext(source.slice(a, b) + "\n" + source.slice(c, d),
    { ...legacy, code, metadata, data });
}
function countyOracle(source, code, observations, reference, collection) {
  const begin = source.indexOf("    async function drawCurrentGeography");
  const a = source.indexOf("      const administrations =", begin);
  const b = source.indexOf("      const file =", a);
  const c = source.indexOf("      const nativeByFips =", b);
  const d = source.indexOf("      let contextRows =", c);
  assert.ok(a > begin && d > c);
  return vm.runInNewContext(`(()=>{${source.slice(a, b)}\n${source.slice(c, d)}
    return [...nativeByFips];})()`, { ...legacy, code, observations, reference, collection,
    clearCountState: () => {}, countyName: value => value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .toUpperCase().replace(/\s*\(VOTE CENTER\)/g, "").replace(/\b(COUNTY|PARISH)\b/g, "").replace(/[^A-Z0-9]/g, "") });
}

export function compileNativeBindings(root, source, supplied) {
  const inputs = {}, files = {}, layers = {}, reporting_tables = {}, county_bindings = {}, municipal_bindings = {}, original = file => {
    const relative = file.replace(resolve(root) + "/", "");
    const body = supplied ? supplied[relative] : readFileSync(file);
    assert.ok(body, "Missing full input: " + relative);
    inputs[relative] = body;
    return body;
  };
  const read = file => JSON.parse(original(file));
  const pointer = read(resolve(root, "public/participation-precincts.json"));
  const config = { states: {}, state_metadata: {}, municipalities: {} };
  const specs = [];
  for (const [ordinal, description] of [{ base_url: pointer.base_url }, ...pointer.additional_sources].entries()) {
    const indexPath = heldPath(new URL("index.json", new URL(description.base_url, "https://www.themarginoferror.com")).href, root);
    const index = read(indexPath);
    if (!ordinal) Object.assign(config, index, { states: {}, state_metadata: {}, municipalities: {} });
    for (const [code, file] of Object.entries(index.states || {})) {
      const url = new URL(file, new URL(description.base_url, "https://www.themarginoferror.com")).href;
      assert.ok(!config.states[code]);
      config.states[code] = url;
      const metadata = { boundary_label: index.boundary_date || "July 2026 reference boundaries",
        ...index.state_metadata?.[code],
        ...(index.complete_download_file ? { complete_download_url: new URL(index.complete_download_file,
          new URL(description.base_url, "https://www.themarginoferror.com")).href } : {}) };
      config.state_metadata[code] = metadata;
      specs.push({ id: "precinct/" + code, code, metadata, url, kind: "precinct" });
    }
    for (const [code, metadata] of Object.entries(index.municipalities || {})) {
      const url = new URL(metadata.file, new URL(description.base_url, "https://www.themarginoferror.com")).href;
      config.municipalities[code] = { ...metadata, url,
        complete_download_url: new URL(metadata.complete_download_file, new URL(description.base_url, "https://www.themarginoferror.com")).href };
    }
  }
  const resultsPointer = read(resolve(root, "public/precinct-results.json"));
  const matched = {};
  for (const snapshot of [resultsPointer, ...resultsPointer.additional_snapshots]) {
    const dir = snapshot.data_directory || new URL(snapshot.base_url).pathname.split("/").slice(4).join("/");
    const index = read(resolve(root, dir, "index.json"));
    for (const code of ["ID", "ND", "MN", "DC", "VA"]) {
      const coverage = index.coverage?.["2026"]?.[code];
      if (!coverage || config.states[code]) continue;
      matched[code] = { ...coverage, data_url: new URL(coverage.file, snapshot.base_url).href,
        complete_download_url: snapshot.complete_download_url,
        ...(snapshot.participation_count_sha256 ? { participation_count_sha256: snapshot.participation_count_sha256 } : {}) };
      specs.push({ id: "matched/" + code, code, metadata: matched[code], url: matched[code].data_url, kind: "matched" });
    }
  }
  for (const spec of specs) {
    const inputPath = heldPath(spec.url, root), body = original(inputPath);
    const collection = JSON.parse(gunzipSync(body));
    if (spec.metadata.sha256) assert.equal(digest(body), spec.metadata.sha256);
    if (spec.metadata.participation_count_sha256) assert.equal(digest(body), spec.metadata.participation_count_sha256);
    if (spec.kind === "precinct") nativeOracle(source, spec.code, spec.metadata, collection);
    if (spec.kind === "matched") {
      const a = source.indexOf("    const keys = new Set(), countsOnly =", source.indexOf("async function drawMatchedPrecinctParticipation"));
      const b = source.indexOf("    const observed =", a);
      vm.runInNewContext(source.slice(a, b), { ...legacy, code: spec.code, year: 2026,
        data: collection, coverage: spec.metadata });
    }
    const geometryFile = "geometry/" + digest(body) + ".json.gz";
    files[geometryFile] = body;
    const geometry = { file: geometryFile, ...pin(body) };
    const rows = collection.features.map((feature, ordinal) => {
      const properties = feature.properties, nested = spec.kind === "matched";
      const native = nested ? properties.participation : properties;
      const paths = { count: nested ? ["participation", "ballots"] : ["ballots"],
        denominator: nested ? (Object.hasOwn(native, "registered") ? ["participation", "registered"]
          : Object.hasOwn(native, "denominator") ? ["participation", "denominator"] : null)
          : spec.kind === "municipality" ? ["registered_voters"] : Object.hasOwn(native, "denominator") ? ["denominator"] : null,
        rate: nested ? ["participation", "reported_pct"] : spec.kind === "municipality"
          ? ["registered_turnout_pct"] : ["reported_pct"] };
      const value = paths.denominator?.reduce((v, k) => v?.[k], properties) ?? null;
      const rate = paths.rate.reduce((v, k) => v?.[k], properties) ?? null;
      const projection = { ...properties, year: 2026, state_code: spec.code,
        county: properties.county || properties.name || spec.code,
        county_id: properties.county_id || properties.county_code || "reference",
        unit: properties.unit || properties.precinct || properties.name || properties.key,
        unit_key: properties.key, geography_level: spec.kind === "municipality" ? "municipality" : "reporting_unit",
        ballots: native.ballots, denominator: value, reported_pct: rate,
        denominator_basis: native.denominator_basis || native.basis || "previously_reviewed_native_denominator",
        source_update_label: properties.source_update_label || properties.source_updated_at || null,
        quality: Array.isArray(native.quality) ? native.quality : [native.quality || "Previously reviewed native count/reference"],
      };
      const observation = canonicalObservation(projection, { file: inputPath.replace(resolve(root) + "/", ""),
        ...pin(body), url: spec.url }, spec.id, ordinal);
      observation.geography.join = { status: ["matched", "rate_withheld"].includes(properties.match_status)
        || properties.maps_approved === true || /^(matched|qualified)_/.test(properties.match_status || "")
        ? "approved" : "unmatched",
        reference_id: geometry.sha256, feature_key: properties.key,
        evidence: "Existing source-specific qualification retained from accepted c4ccdf4; no new geographic approval." };
      return { key: properties.key, geometry_type: feature.geometry.type, properties, paths, observation };
    });
    const data = validateNativeShard({ contract: "participation.native_bindings.v1", id: spec.id,
      state_code: spec.code, metadata: spec.metadata, geometry, rows,
      approval: { source_revision: revision, existing_qualification_retained: true } }, spec.id);
    assert.deepEqual(bindNativeGeometry(data, collection, geometry.sha256), collection);
    const file = "counts/" + spec.id.replace("/", "-") + ".json.gz";
    files[file] = gzipSync(encoded(data), { level: 9 });
    layers[spec.id] = { file, ...pin(files[file]), features: rows.length, geometry_sha256: geometry.sha256,
      eligible_modes: ["available", "official", "uf_vep", "uf_vap"],
      coverage: { source_rows: rows.filter(row => row.observation.geography.join.status === "approved").length,
        reported: rows.filter(row => row.observation.count.status === "reported").length,
        unknown: rows.filter(row => row.observation.count.status === "unknown").length,
        withheld: rows.filter(row => row.observation.count.status === "withheld").length,
        fractions: rows.filter(row => row.observation.denominator?.qualified).length } };
  }
  const countRoot = resolve(root, "data/participation-counts/20261110-02/runtime");
  const countIndex = read(resolve(countRoot, "index.json"));
  const localPointer = read(resolve(root, "public/participation-local.json"));
  const localIndex = read(heldPath(new URL("index.json", localPointer.base_url).href, root));
  let countyCases = 0;
  for (const [code, declaration] of Object.entries(countIndex.states)) {
    const data = JSON.parse(gunzipSync(original(resolve(countRoot, declaration.file))));
    for (const mode of Object.keys(data.views)) {
      const observations = countFrame(data, mode).counties;
      if (["VT", "RI"].includes(code) && observations.length) {
        const url = code === "VT" ? config.municipalities.VT.url
          : new URL(localIndex.geometry["2024"].municipality.RI, localPointer.base_url).href;
        const body = original(heldPath(url, root)), collection = JSON.parse(gunzipSync(body));
        const normalize = value => value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
          .toUpperCase().replace(/\s*\(VOTE CENTER\)/g, "").replace(/\b(COUNTY|PARISH)\b/g, "").replace(/[^A-Z0-9]/g, "");
        const byName = new Map(observations.map(row => [normalize(row.county), row]));
        assert.equal(byName.size, observations.length);
        const a = source.indexOf("      const shapeNames =", source.indexOf("async function drawCurrentMunicipalityGeography"));
        const b = source.indexOf("      const reference = vermont", a);
        vm.runInNewContext(source.slice(a, b), { code, observations, collection, byName,
          countyName: normalize, vermont: code === "VT", metadata: config.municipalities[code] });
        const geometryFile = "geometry/" + digest(body) + ".json.gz";
        files[geometryFile] = body;
        const binding = { sha256: digest(body), geometry: { file: geometryFile, ...pin(body) },
          features: collection.features.length, embedded_reference_required: false,
          feature_keys: collection.features.map(feature => feature.properties.key),
          feature_scopes: Object.fromEntries(collection.features.map(({ properties: p }) => [p.key,
            { state_code: p.state_code ?? null, name: p.name ?? null, boundary_year: p.boundary_year ?? null }])),
          rows: collection.features.map(({ properties: p }) => {
            const row = byName.get(normalize(p.name));
            assert.ok(row);
            return { feature_key: p.key, county_id: row.county_id, qualifier: countyQualifier(row) };
          }) };
        assert.equal(bindCountyReference(observations, collection, { sha256: binding.sha256 }, binding).size, observations.length);
        (municipal_bindings[code] ||= {})[mode] = binding;
      }
      const reference = observations.find(row => row.reference_geometry)?.reference_geometry;
      if (!reference) continue;
      const body = original(heldPath(reference.url, root));
      assert.equal(digest(body), reference.sha256);
      const collection = JSON.parse(gunzipSync(body));
      const joins = countyOracle(source, code, observations, reference, collection);
      const binding = { sha256: reference.sha256, features: collection.features.length,
        feature_keys: collection.features.map(feature => feature.properties.key),
        feature_scopes: Object.fromEntries(collection.features.map(({ properties: p }) => [p.key,
          { state_code: p.state_code ?? null, name: p.name ?? null, boundary_year: p.boundary_year ?? null }])),
        rows: joins.map(([feature_key, row]) => ({ feature_key, county_id: row.county_id, qualifier: countyQualifier(row) })) };
      const bound = bindCountyReference(observations, collection, reference, binding);
      assert.equal(bound.size, observations.length);
      (county_bindings[code] ||= {})[mode] = binding;
      countyCases++;
    }
  }
  const index = { contract: "participation.native_index.v1", year: 2026, config, matched,
    layers, county_bindings, municipal_bindings, source_revision: revision, county_frame_checks: countyCases };
  const reporting = read(resolve(root, "public/participation-reporting-units.json"));
  assert.equal(reporting.year, 2026);
  for (const [code, source] of Object.entries(reporting.sources)) {
    const url = new URL(source.data_url, "https://www.themarginoferror.com").href;
    const path = heldPath(url, root), body = original(path);
    assert.equal(digest(body), source.sha256);
    const rows = JSON.parse(gunzipSync(body));
    assert.equal(rows.length, source.rows);
    assert.equal(new Set(rows.map(row => row.key)).size, rows.length);
    const records = rows.map((properties, ordinal) => {
      assert.equal(properties.year, 2026); assert.equal(properties.state_code, code);
      assert.equal(properties.reported_pct, null);
      assert.ok(properties.precinct && properties.reporting_unit_kind);
      const projection = { ...properties, county: properties.county || code,
        county_id: properties.county_id || properties.county || "reporting",
        unit: properties.precinct, unit_key: properties.key, geography_level: "reporting_unit",
        denominator: properties.registered ?? null, denominator_basis: properties.basis || "not_qualified",
        source_update_label: source.source_update_label, quality: properties.quality_flags || [] };
      const observation = canonicalObservation(projection,
        { file: path.replace(resolve(root) + "/", ""), ...pin(body), url }, "reporting/" + code, ordinal);
      validateCountObservation(observation, code);
      return { properties, observation };
    });
    const file = "tables/" + code + ".json.gz";
    files[file] = gzipSync(encoded({ contract: "participation.reporting_units.v1", state_code: code, records }), { level: 9 });
    reporting_tables[code] = { file, ...pin(files[file]), rows: rows.length,
      eligible_modes: ["available", "official", "uf_vep", "uf_vap"],
      coverage: { source_rows: rows.length, fractions: 0,
        reported: rows.filter(row => row.ballots !== null).length,
        unknown: rows.filter(row => row.ballots === null).length, withheld: 0 } };
  }
  index.reporting_sources = reporting.sources;
  index.reporting_tables = reporting_tables;
  files["index.json"] = encoded(index);
  const declarations = Object.fromEntries(Object.entries(files).sort().map(([file, body]) => [file, pin(body)]));
  const record_contract = "participation.native_bindings.v1";
  const descriptor = { contract: "participation.dataset.v1", id: "participation-native-bindings-2026",
    version: digest(encoded({ files: declarations, contract: record_contract })), record_contract,
    files: declarations, index: { file: "index.json", ...declarations["index.json"] }, complete_download: null };
  return { files, inputs, descriptor, index };
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const root = resolve(process.argv[2]), output = resolve(process.argv[3]);
  assert.ok(!existsSync(output));
  const source = process.argv[4] ? readFileSync(resolve(process.argv[4]), "utf8")
    : execFileSync("git", ["-C", root, "show", revision + ":public/scripts/participation-explorer.js"], { encoding: "utf8" });
  const compiled = compileNativeBindings(root, source);
  for (const [file, body] of Object.entries(compiled.files)) {
    mkdirSync(dirname(resolve(output, "runtime", file)), { recursive: true });
    writeFileSync(resolve(output, "runtime", file), body);
  }
  writeFileSync(resolve(output, "runtime/dataset.json"), encoded(compiled.descriptor));
  writeFileSync(resolve(output, "legacy-reader.js"), source);
  writeFileSync(resolve(output, "inputs.json"), encoded({ source_revision: revision,
    files: Object.fromEntries(Object.entries(compiled.inputs).map(([file, body]) => [file, pin(body)])) }));
  console.log(JSON.stringify({ version: compiled.descriptor.version, layers: Object.keys(compiled.index.layers).length,
    county_frames: compiled.index.county_frame_checks, files: Object.keys(compiled.files).length }));
}

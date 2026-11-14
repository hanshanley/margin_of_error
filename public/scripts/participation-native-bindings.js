import { loadDataset, checkedDatasetFile } from "./participation-dataset.js";
import { validateCountObservation, loadCountState, loadCountIndex } from "./participation-counts.js";
import { validateReferenceBindings, bindReferenceGeometry } from "./participation-reference-bindings.js";

const qualifierKeys = ["state_code", "county_id", "county", "geography_level", "county_fips",
  "reference_municipality_key", "source_administration_id", "source_mode", "denominator_basis",
  "participation_measure_kind", "participation_measure_literal", "participation_measure_label",
  "cast_ballot_count_qualified", "unique_voter_count_qualified"];
export const countyQualifier = row => Object.fromEntries(qualifierKeys.map(key => [key, row[key] ?? null]));
export const countyCoverageMessage = rows => "No matching county participation observation in this source. "
  + `Observed: ${rows.map(row => row.county).join(", ")}. Missing counts are not zero.`;
const ordered = value => JSON.stringify(Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b))));
const valueAt = (object, path) => path.reduce((value, key) => value?.[key], object);
const paths = new Set(["ballots", "denominator", "registered_voters", "reported_pct",
  "registered_turnout_pct", "participation.ballots", "participation.registered",
  "participation.denominator", "participation.reported_pct"]);
function put(object, path, value) {
  let target = object;
  for (const key of path.slice(0, -1)) target = target[key];
  target[path.at(-1)] = value;
}

export function validateNativeShard(data, identity) {
  if (data?.contract !== "participation.native_bindings.v1" || data.id !== identity
      || identity.split("/")[1] !== data.state_code
      || !Array.isArray(data.rows) || !data.geometry || !/^[a-f0-9]{64}$/.test(data.geometry.sha256)
      || data.approval?.source_revision !== "c4ccdf4d677974ea9068724367263dc59d9d0d88"
      || data.approval.existing_qualification_retained !== true)
    throw new Error("Unqualified native count/reference contract");
  const keys = new Set(), ids = new Set();
  for (const row of data.rows) {
    validateCountObservation(row.observation, data.state_code);
    if (typeof row.key !== "string" || !row.key || keys.has(row.key)
        || ids.has(row.observation.id) || !["Polygon", "MultiPolygon"].includes(row.geometry_type)
        || !row.properties || !row.paths || !Array.isArray(row.paths.count)
        || Object.values(row.paths).some(path => path !== null && (!Array.isArray(path) || !paths.has(path.join("."))))
        || !row.paths.count.length || valueAt(row.properties, row.paths.count) !== row.observation.count.value
        || row.paths.denominator && valueAt(row.properties, row.paths.denominator) !== (row.observation.denominator?.value ?? null)
        || row.paths.rate && valueAt(row.properties, row.paths.rate) !== row.observation.view.reported_pct
        || row.observation.geography.join.reference_id !== data.geometry.sha256
        || row.observation.geography.join.feature_key !== row.key
        || row.observation.geography.join.status !== "approved"
          && (row.observation.count.value !== null || row.observation.denominator?.qualified))
      throw new Error("Native count/key/denominator binding differs");
    keys.add(row.key); ids.add(row.observation.id);
  }
  return data;
}

export function bindNativeGeometry(data, collection, verifiedHash) {
  if (verifiedHash !== data.geometry.sha256 || collection?.type !== "FeatureCollection"
      || collection.features?.length !== data.rows.length)
    throw new Error("Native geometry hash or complete inventory differs");
  const rows = new Map(data.rows.map(row => [row.key, row])), seen = new Set();
  const features = collection.features.map(feature => {
    const key = feature.properties?.key, row = rows.get(key);
    if (!row || seen.has(key) || feature.geometry?.type !== row.geometry_type)
      throw new Error("Native geometry/key scope differs");
    seen.add(key);
    const properties = structuredClone(row.properties);
    put(properties, row.paths.count, row.observation.count.value);
    if (row.paths.denominator) put(properties, row.paths.denominator, row.observation.denominator?.value ?? null);
    if (row.paths.rate) put(properties, row.paths.rate, row.observation.view.reported_pct);
    return { ...feature, properties };
  });
  return { ...collection, features };
}

export function bindCountyReference(rows, collection, reference, binding) {
  if (!binding || reference.sha256 !== binding.sha256
      || collection.features?.length !== binding.features
      || rows.length !== binding.rows.length)
    throw new Error("Unqualified county/local reference inventory");
  const expected = new Map(binding.rows.map(row => [row.county_id, row]));
  if (expected.size !== binding.rows.length) throw new Error("Duplicate county/local source identity");
  const shapeKeys = collection.features.map(feature => feature.properties?.key);
  if (new Set(shapeKeys).size !== shapeKeys.length
      || shapeKeys.some(key => !binding.feature_keys.includes(key)))
    throw new Error("County/local reference feature identity differs");
  if (binding.feature_scopes && collection.features.some(({ properties: p }) =>
    ordered({ state_code: p.state_code ?? null, name: p.name ?? null, boundary_year: p.boundary_year ?? null })
      !== ordered(binding.feature_scopes[p.key] || {})))
    throw new Error("County/local reference names, state or vintage differ");
  const joined = new Map();
  for (const row of rows) {
    const match = expected.get(row.county_id);
    if (!match || ordered(countyQualifier(row)) !== ordered(match.qualifier)
        || binding.embedded_reference_required !== false && row.reference_geometry?.sha256 !== binding.sha256
        || joined.has(match.feature_key)
        || !shapeKeys.includes(match.feature_key))
      throw new Error("County/local native identity or source scope differs");
    joined.set(match.feature_key, row);
  }
  return joined;
}

let dataset;
const shards = new Map(), geometries = new Map();
export function loadNativeIndex() {
  dataset ||= loadDataset("participation-native-bindings-2026").then(result => {
    if (result.index.contract !== "participation.native_index.v1")
      throw new Error("Unknown native reference catalog");
    return result;
  }).catch(error => { dataset = null; throw error; });
  return dataset;
}
export async function loadBoundNative(identity) {
  const { entry, index } = await loadNativeIndex(), declaration = index.layers[identity];
  if (!declaration) throw new Error("No approved native count/reference binding");
  if (!shards.has(identity)) shards.set(identity, checkedDatasetFile(entry.base_url, declaration)
    .then(async data => {
      if (data.contract !== "participation.reference_bindings.v1") return validateNativeShard(data, identity);
      const source = await loadCountState(data.state_code), { index: sourceIndex } = await loadCountIndex();
      if (data.rows.length !== declaration.features) throw new Error("Separate reference coverage differs");
      return validateReferenceBindings(data, identity, source, sourceIndex.states[data.state_code]);
    }).catch(error => { shards.delete(identity); throw error; }));
  const data = await shards.get(identity);
  if (!geometries.has(data.geometry.sha256)) geometries.set(data.geometry.sha256,
    checkedDatasetFile(entry.base_url, data.geometry).catch(error => {
      geometries.delete(data.geometry.sha256); throw error;
    }));
  const geometry = await geometries.get(data.geometry.sha256);
  const bind = data.contract === "participation.reference_bindings.v1" ? bindReferenceGeometry : bindNativeGeometry;
  return { data: bind(data, geometry, data.geometry.sha256),
    verified_geometry_sha256: data.geometry.sha256, binding: data };
}
export async function loadCountyBinding(code, mode) {
  const { index } = await loadNativeIndex();
  return index.county_bindings[code]?.[mode] || null;
}
export async function loadMunicipalReference(code, mode) {
  const { entry, index } = await loadNativeIndex();
  const binding = index.municipal_bindings?.[code]?.[mode];
  if (!binding) throw new Error("No qualified municipality reference for this source mode");
  return { data: await checkedDatasetFile(entry.base_url, binding.geometry), binding,
    reference: { sha256: binding.sha256 } };
}
export async function loadReportingRows(code) {
  const { entry, index } = await loadNativeIndex(), declaration = index.reporting_tables?.[code];
  if (!declaration) throw new Error("No qualified reporting-unit count table");
  const data = await checkedDatasetFile(entry.base_url, declaration);
  if (data.contract !== "participation.reporting_units.v1" || data.state_code !== code
      || data.records?.length !== declaration.rows)
    throw new Error("Reporting-unit source inventory differs");
  const keys = new Set();
  for (const { properties, observation } of data.records) {
    validateCountObservation(observation, code);
    if (!properties.key || !properties.precinct || !properties.reporting_unit_kind
        || keys.has(properties.key) || properties.year !== 2026
        || properties.state_code !== code || properties.ballots !== observation.count.value
        || properties.reported_pct !== null || observation.denominator?.qualified)
      throw new Error("Unqualified reporting-unit count or rate substitution");
    keys.add(properties.key);
  }
  return data.records.map(row => row.properties);
}

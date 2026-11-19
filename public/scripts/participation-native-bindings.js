import { loadDataset, checkedDatasetFile } from "./participation-dataset.js";
import { validateCountObservation, validateCountShard, loadCountState, loadCountIndex, loadAcceptedCountState,
  rejectCountRuntime } from "./participation-counts.js";
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

const nativePropertyIdentity = [
  "key", "year", "state_code", "county", "county_id", "county_fips", "geography_level",
  "reference_municipality_key", "source_administration_id", "source_mode", "unit", "unit_key",
  "unit_kind", "denominator_basis", "participation_measure_kind", "participation_measure_literal",
  "participation_measure_label", "cast_ballot_count_qualified", "unique_voter_count_qualified",
  "maps_approved",
];
function countBindingIdentity(observation) {
  const denominator = observation.denominator;
  return ordered({
    id: observation.id,
    election: observation.election,
    geography: observation.geography,
    measure: observation.measure,
    denominator: denominator && {
      literal: denominator.literal, basis: denominator.basis, qualified: denominator.qualified,
    },
    view: Object.fromEntries(nativePropertyIdentity
      .map(key=>[key,observation.view?.[key]??null])),
  });
}
function propertyIdentity(properties) {
  return ordered(Object.fromEntries(nativePropertyIdentity.map(key => [key, properties?.[key] ?? null])));
}
function updatedProperties(properties, view) {
  const updated=structuredClone(properties);
  for (const key of Object.keys(updated))
    if (!nativePropertyIdentity.includes(key) && Object.hasOwn(view,key))
      updated[key]=structuredClone(view[key]);
  return updated;
}

export function rebindNativeCounts(data, counts) {
  const current = new Map(counts.records.map(row => [row.id, row]));
  const rebound = structuredClone(data);
  for (const row of rebound.rows) {
    const observation = current.get(row.observation.id);
    if (!observation || countBindingIdentity(observation) !== countBindingIdentity(row.observation))
      throw new Error("Automatic count identity or approved native join differs");
    const properties = updatedProperties(row.properties,observation.view);
    if (propertyIdentity(properties) !== propertyIdentity(row.properties))
      throw new Error("Automatic count geography, unit label or map qualification differs");
    row.observation = structuredClone(observation);
    row.properties = properties;
  }
  return validateNativeShard(rebound, data.id);
}

function validateRuntimeSnapshot(nativeSource, countSource) {
  const native = nativeSource.automatic_runtime, counts = countSource.automatic_runtime;
  if (Boolean(native) !== Boolean(counts)
      || native && (native.version !== counts.version
        || native.runtime_commit !== counts.runtime_commit
        || nativeSource.entry.version !== native.native?.version
        || countSource.entry.version !== counts.counts?.version))
    throw new Error("Native and canonical counts do not share one verified runtime snapshot");
}

export function validatedNativeSnapshot(data, identity, nativeSource, countSource) {
  validateRuntimeSnapshot(nativeSource, countSource);
  // Native observations have their own reviewed IDs; the producer refreshes their
  // approved projections before publishing the count/native snapshot atomically.
  return validateNativeShard(data, identity);
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
  if (binding?.embedded_reference_required === false) {
    const mappedIds = new Set(binding.rows.map(row => row.county_id));
    rows = rows.filter(row => row.maps_approved !== false || mappedIds.has(row.county_id));
  }
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
globalThis.addEventListener?.("participation:automatic-runtime-rejected", event => {
  if (event.detail?.component === "counts") shards.clear();
});
export function loadNativeIndex() {
  dataset ||= (async()=>{
    const result=await loadDataset("participation-native-bindings-2026");
    try {
      if (result.index.contract!=="participation.native_index.v1")
        throw new Error("Unknown native reference catalog");
      return result;
    } catch (error) {
      if (!result.automatic_runtime) throw error;
      rejectCountRuntime(error);
      const fallback=await loadDataset("participation-native-bindings-2026",{automatic:false});
      if (fallback.index.contract!=="participation.native_index.v1") throw error;
      return fallback;
    }
  })().catch(error=>{dataset=null;throw error;});
  return dataset;
}
export async function loadBoundNative(identity) {
  const nativeSource=await loadNativeIndex(), {entry,index}=nativeSource, declaration = index.layers[identity];
  if (!declaration) throw new Error("No approved native count/reference binding");
  try {
    if (!shards.has(identity)) shards.set(identity, checkedDatasetFile(entry.base_url, declaration)
      .then(async data => {
        if (data.rows.length !== declaration.features) throw new Error("Separate reference coverage differs");
        const countIndex = await loadCountIndex();
        if (data.contract !== "participation.reference_bindings.v1")
          return validatedNativeSnapshot(data, identity, nativeSource, countIndex);
        validateRuntimeSnapshot(nativeSource, countIndex);
        const sourceDeclaration = countIndex.index.states[data.state_code];
        // Full observation equality requires canonical bytes, not decorated download links.
        const source = validateCountShard(
          await checkedDatasetFile(countIndex.entry.base_url, sourceDeclaration),
          data.state_code, sourceDeclaration);
        return validateReferenceBindings(data, identity, source, sourceDeclaration);
      }));
    const data = await shards.get(identity);
    if (!geometries.has(data.geometry.sha256)) geometries.set(data.geometry.sha256,
      checkedDatasetFile(entry.base_url, data.geometry).catch(error => {
        geometries.delete(data.geometry.sha256); throw error;
      }));
    const geometry = await geometries.get(data.geometry.sha256);
    const bind = data.contract === "participation.reference_bindings.v1" ? bindReferenceGeometry : bindNativeGeometry;
    return { data: bind(data, geometry, data.geometry.sha256),
      verified_geometry_sha256: data.geometry.sha256, binding: data };
  } catch (error) {
    shards.delete(identity);
    if (!nativeSource.automatic_runtime) throw error;
    rejectCountRuntime(error);dataset=null;geometries.clear();
    return loadBoundNative(identity);
  }
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
const reviewedReportingSources = {
  AR: "accepted-export:b128dc3cef02ae063e840495611b3747dc9454692d2788a8cb94e3b160f4908a:reporting/AR",
  AZ: "accepted-export:bc9f1e93785e4a83148b96afa6855701f511be995f7469b8e9e4dfcb7e6cb51f:reporting/AZ",
  WY: "accepted-export:cea7eba88d5ae521db73653ce33992dbe2d253a2854cd81d27655890e74be161:reporting/WY",
};
const frozenReportingSources = {
  AK: { sha256: "5eb889e4ebb1dbcf6687b19f6bb3d27a790b1d498b6c3ad854f7ae59d6a1d138", rows: 523 },
  HI: { sha256: "96b670b42e2156d563bb6dde943817a222ad90e26bcb74727f1d360db68b6052", rows: 496 },
};
const frozenReportingRoot = "https://raw.githubusercontent.com/hanshanley/margin_of_error/"
  + "269406570805a8f9a030f4f01d1ff49f608cc9d5/data/precinct-source-reviews/20261105/";
function heldReportingObservation(observation) {
  return observation.view.reported_pct === null && !observation.denominator?.qualified
    && ["maps_approved", "cast_ballot_count_qualified", "unique_voter_count_qualified"]
      .every(key => observation.view[key] == null || observation.view[key] === false);
}
function frozenReportingObservation(observation, code, index) {
  const profile = frozenReportingSources[code], source = index.reporting_sources?.[code];
  if (!profile || !source) return false;
  const url = frozenReportingRoot + code + "/participation.json.gz";
  return source.sha256 === profile.sha256 && source.rows === profile.rows
    && index.reporting_tables[code].rows === profile.rows && source.data_url === url
    && observation.source.id === `accepted-export:${profile.sha256}:reporting/${code}`
    && observation.source.input_sha256 === profile.sha256 && observation.source.url === url
    && observation.view.source_url === source.source_url
    && observation.geography.level === "reporting_unit"
    && observation.geography.join.status === "unreviewed"
    && observation.source_clock.literal === source.source_update_label
    && observation.source_clock.timezone === null
    && ordered(observation.source.fields) === ordered(observation.view)
    && heldReportingObservation(observation);
}
function reviewedReportingIdentity(native, current, code) {
  return native.source.id === reviewedReportingSources[code]
    && native.id === current.id && heldReportingObservation(native)
    && heldReportingObservation(current)
    && native.geography.level === "reporting_unit"
    && ["election", "measure", "count", "denominator"]
      .every(key => ordered(native[key] || {}) === ordered(current[key] || {}))
    && ["id", "name", "state_code", "level", "join"]
      .every(key => JSON.stringify(native.geography[key]) === JSON.stringify(current.geography[key]))
    && ["id", "input_sha256", "url", "selector", "classification"]
      .every(key => JSON.stringify(native.source[key]) === JSON.stringify(current.source[key]))
    && ordered(native.source.fields) === ordered(native.view)
    && ["state_code", "key", "unit", "year", "native_record"]
      .every(key => JSON.stringify(native.view[key]) === JSON.stringify(current.view[key]))
    && ["literal", "timezone"]
      .every(key => native.source_clock[key] === current.source_clock[key]);
}
export function bindReportingRows(data, code, nativeSource, countSource, counts) {
  validateRuntimeSnapshot(nativeSource, countSource);
  const declaration = nativeSource.index.reporting_tables?.[code];
  if (data.contract !== "participation.reporting_units.v1" || data.state_code !== code
      || !declaration || data.records?.length !== declaration.rows)
    throw new Error("Reporting-unit source inventory differs");
  const current = new Map(counts.records.map(row => [row.id, row]));
  const records = data.records.map(row => {
    validateCountObservation(row.observation, code);
    let observation = current.get(row.observation.id);
    const saved = !observation && frozenReportingObservation(row.observation, code, nativeSource.index);
    if (saved) observation = row.observation;
    if (observation) validateCountObservation(observation, code);
    const reviewed = reviewedReportingSources[code];
    const compatible = saved || observation && (
      reviewed && [row.observation.source.id, observation.source.id].includes(reviewed)
        ? reviewedReportingIdentity(row.observation, observation, code)
        : countBindingIdentity(observation) === countBindingIdentity(row.observation));
    if (!compatible)
      throw new Error("Automatic reporting-unit identity differs");
    const properties = updatedProperties(row.properties,observation.view);
    properties.source_update_label = observation.view.source_update_label
      ?? observation.source_clock.literal;
    properties.source_update_timezone = observation.source_clock.timezone;
    if (saved) properties.source_frame = "saved_reviewed_native_export";
    if (propertyIdentity(properties) !== propertyIdentity(row.properties))
      throw new Error("Automatic reporting-unit labels or qualification differ");
    return { properties, observation };
  });
  const keys = new Set();
  for (const { properties, observation } of records) {
    validateCountObservation(observation, code);
    if (!properties.key || !properties.precinct || !properties.reporting_unit_kind
        || keys.has(properties.key) || properties.year !== 2026
        || properties.state_code !== code || properties.ballots !== observation.count.value
        || properties.reported_pct !== null || observation.denominator?.qualified)
      throw new Error("Unqualified reporting-unit count or rate substitution");
    keys.add(properties.key);
  }
  return records.map(row => row.properties);
}
export function reportingUnitDownloads(code, nativeSource, countSource) {
  validateRuntimeSnapshot(nativeSource, countSource);
  if (!nativeSource.automatic_runtime) return null;
  const complete = nativeSource.automatic_runtime.complete_download?.url;
  const declaration = nativeSource.index.reporting_tables?.[code];
  if (!complete || complete !== countSource.automatic_runtime.complete_download?.url || !declaration?.file)
    throw new Error("Missing complete automatic reporting-unit downloads");
  return { complete, rows: nativeSource.entry.base_url + declaration.file };
}
export async function loadReportingRows(code) {
  const nativeSource=await loadNativeIndex(), {entry,index}=nativeSource;
  const declaration = index.reporting_tables?.[code];
  if (!declaration) throw new Error("No qualified reporting-unit count table");
  try {
    const data = await checkedDatasetFile(entry.base_url,declaration);
    const countSource = await loadCountIndex();
    return bindReportingRows(data, code, nativeSource, countSource, await loadCountState(code));
  } catch (error) {
    if (!nativeSource.automatic_runtime) throw error;
    rejectCountRuntime(error);dataset=null;
    return loadReportingRows(code);
  }
}

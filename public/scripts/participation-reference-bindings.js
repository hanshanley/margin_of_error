import { validateCountObservation } from "./participation-counts.js";

const hash = /^[a-f0-9]{64}$/;
const text = value => typeof value === "string" && value.length > 0;
const sourceQualifiers = ["source_mode", "source_status_literal", "source_reporting_label",
  "participation_measure_label", "participation_measure_literal", "participation_measure_kind",
  "unit_kind", "denominator_basis", "source_url", "cast_ballot_count_qualified",
  "unique_voter_count_qualified"];
const same = (left, right) => JSON.stringify(ordered(left)) === JSON.stringify(ordered(right));
function ordered(value) {
  if (Array.isArray(value)) return value.map(ordered);
  if (value && typeof value === "object")
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])]));
  return value;
}

export function validateReferenceBindings(data, identity, source, declaration) {
  const review = data?.review, origin = data?.source_counts;
  if (data?.contract !== "participation.reference_bindings.v1" || data.id !== identity
      || identity !== "precinct/" + data.state_code || source?.state_code !== data.state_code
      || source.contract !== "participation.count_snapshot.v1" || !Array.isArray(source.records)
      || !origin || !["file", "bytes", "sha256"].every(key => origin[key] === declaration?.[key])
      || !hash.test(origin.sha256) || !text(origin.source_id)
      || !data.geometry || !hash.test(data.geometry.sha256)
      || !Array.isArray(data.rows) || !Array.isArray(data.held_rows)
      || !review || review.reviewed !== true || !text(review.review_id)
      || review.scope !== "public_authoritative_reference_context"
      || review.matching !== "exact_literal_only"
      || review.legal_election_boundaries_certified !== false
      || review.rates_approved !== false || review.source_observations_preserved !== true
      || !text(review.reference_label) || !Number.isFinite(Date.parse(review.geometry_retrieved_at_utc))
      || !text(review.omitted_units_note))
    throw new Error("Unqualified separate reference/count contract");
  const observations = new Map(source.records.filter(row => row.source.id === origin.source_id)
    .map(row => [row.id, row]));
  if (observations.size !== origin.source_rows || data.rows.length + data.held_rows.length !== observations.size)
    throw new Error("Reference and held source inventory differ");
  const ids = new Set(), keys = new Set();
  for (const row of data.rows) {
    const actual = observations.get(row.observation?.id), p = row.properties;
    if (!actual || !same(actual, row.observation) || ids.has(actual.id)
        || !text(row.key) || keys.has(row.key) || row.key !== actual.geography.name
        || !["Polygon", "MultiPolygon"].includes(row.geometry_type)
        || actual.count.status !== "reported" || actual.denominator !== null
        || !p || p.key !== row.key || p.unit !== actual.view.unit
        || p.unit_key !== actual.view.unit_key || p.county_id !== actual.view.county_id
        || p.county !== actual.view.county || p.state_code !== actual.geography.state_code
        || p.year !== actual.election.year || p.ballots !== actual.count.value
        || p.source_update_label !== actual.source_clock.literal
        || p.source_update_timezone !== actual.source_clock.timezone
        || p.source_count_observation_id !== actual.id
        || p.denominator !== null || p.reported_pct !== null
        || p.registered !== null || p.unique_voter_count_qualified !== false
        || p.reference_context_only !== true || p.maps_approved !== true
        || p.legal_election_boundaries_certified !== false
        || p.boundary_label !== review.reference_label)
      throw new Error("Reference changed a source observation, literal identity, count or qualification");
    if (Object.entries(actual.view).some(([key, value]) => key !== "maps_approved" && !same(p[key], value))
        || sourceQualifiers.some(key => !same(p[key] ?? null, actual.view[key] ?? null)))
      throw new Error("Reference display changed native source metadata or qualifications");
    validateCountObservation(actual, data.state_code);
    ids.add(actual.id); keys.add(row.key);
  }
  for (const held of data.held_rows) {
    const actual = observations.get(held.observation_id);
    if (!actual || ids.has(actual.id) || held.native_label !== actual.geography.name || !text(held.reason))
      throw new Error("Held source identity or reason differs");
    validateCountObservation(actual, data.state_code);
    ids.add(actual.id);
  }
  if (ids.size !== observations.size) throw new Error("A source observation has no reference disposition");
  return data;
}

export function bindReferenceGeometry(data, collection, verifiedHash) {
  if (verifiedHash !== data.geometry.sha256 || collection?.type !== "FeatureCollection"
      || collection.features?.length !== data.rows.length)
    throw new Error("Separate reference geometry checksum or inventory differs");
  const rows = new Map(data.rows.map(row => [row.key, row])), seen = new Set();
  const features = collection.features.map(feature => {
    const key = feature.properties?.key, row = rows.get(key);
    if (!row || seen.has(key) || feature.geometry?.type !== row.geometry_type)
      throw new Error("Separate reference geometry identity differs");
    seen.add(key);
    return { ...feature, properties: structuredClone(row.properties) };
  });
  return { ...collection, features };
}

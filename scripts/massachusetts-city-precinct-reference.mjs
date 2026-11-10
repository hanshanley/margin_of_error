import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { loadMassachusettsNativeCounts, massachusettsVersion as priorVersion } from './massachusetts-native-counts.mjs';

export const massachusettsCityReferenceVersion = '20261110-massachusetts-city-precinct-reference-02';
const directory = `data/county-source-reviews/${massachusettsCityReferenceVersion}`;
const sha256 = body => createHash('sha256').update(body).digest('hex');
const key = (ward, precinct) => `Somerville:Ward:${ward}:Precinct:${precinct}`;
const labels = new Set(Array.from({ length: 7 }, (_, index) =>
  Array.from({ length: 4 }, (_, precinct) => `${index + 1}-${precinct + 1}`)).flat()
  .concat(['1-4A', '2-1A', '4-2A', '6-3A']));

export function reviewMassachusettsCityReference({ prior, inputs, native, geographic, geometry, declaration, request }) {
  if (inputs.version !== massachusettsCityReferenceVersion || inputs.prior_source_version !== priorVersion
    || Object.keys(inputs.files).length !== 17
    || inputs.state_code !== 'MA' || inputs.year !== 2026 || inputs.native_election_date !== '2026-11-03'
    || inputs.native_reporting_rows !== 307 || inputs.qualified_reporting_references !== 307
    || inputs.split_parent_holds !== 0 || inputs.city_native_shapes !== 32
    || inputs.city_native_vertices !== 2697 || inputs.city_native_pair_decisions !== 496
    || inputs.duplicate_native_ids_preserved !== true || inputs.exact_native_wkt_required !== true
    || inputs.native_projection_epsg !== null || inputs.source_metadata_revision !== '2023-09-22'
    || inputs.source_census_basis !== 2020 || inputs.current_display_reference_year !== null
    || [inputs.certified_2026_election_boundaries, inputs.source_geometries_clipped,
      inputs.source_geometries_repaired, inputs.source_counts_repaired, inputs.analysis_rates_approved,
      inputs.candidate_votes_used_as_ballots, inputs.modes_added].some(value => value !== false)
    || prior.summary.native_reporting_rows !== 307 || prior.summary.mapped_reporting_references !== 303
    || prior.summary.split_parent_holds !== 4 || prior.summary.displayed_municipalities !== 350)
    throw new Error('Unqualified city reference extension; preserve the complete prior count frame');
  if (declaration.identifier !== 'https://data.somervillema.gov/api/views/da4y-vuae'
    || declaration.selected_metadata.provenance !== 'official'
    || !declaration.description.includes('September 22, 2023')
    || !declaration.description.includes('2020 Census')
    || declaration.distribution[0].downloadURL !==
      'https://data.somervillema.gov/download/da4y-vuae/application/x-zip-compressed')
    throw new Error('Changed city declaration or reference clock');
  const wkt = JSON.parse(request.inSR).wkt;
  if (typeof wkt !== 'string' || !wkt.includes('PARAMETER["False_Easting",656166.6666666665]')
    || !wkt.includes('UNIT["Foot_US",0.3048006096012192]'))
    throw new Error('The exact original city WKT cannot be replaced by rounded EPSG2249');
  const n = native.summary, g = geographic.summary;
  if (!n.status.startsWith('PASS_') || !g.status.startsWith('PASS_')
    || native.all_native_shape_decisions.length !== 32 || geographic.all_decisions.length !== 32
    || geometry.type !== 'FeatureCollection' || geometry.features.length !== 32
    || n.native_shapes !== 32 || n.native_valid_shapes !== 32 || n.native_count_identity_matches !== 32
    || n.native_vertices !== 2697 || n.ballots_sum !== 64597 || n.pair_decisions !== 496
    || n.positive_native_overlap_pairs !== 0 || n.duplicate_native_ids_retained !== true
    || n.rejected_exact_epsg2249_assignment !== true
    || n.no_clipping_repair_allocation_or_rates !== true
    || g.source_shapes !== 32 || g.checked_vertices !== 2697 || g.strict_tolerance_degrees !== 1e-9
    || !Number.isFinite(g.maximum_error_degrees) || g.maximum_error_degrees < 0
    || g.maximum_error_degrees > 1e-9
    || g.exact_original_wkt_preserved !== true
    || g.default_null_offset_and_inexact_EPSG_alias_rejected !== true
    || g.no_clipping_allocation_source_repair_or_rates !== true
    || g.declared_datum_operation?.authority !== 'ESRI'
    || g.declared_datum_operation.code !== 108190 || g.declared_datum_operation.direction !== 'inverse'
    || n.maps_approved !== false || g.maps_approved !== false)
    throw new Error('Unqualified native topology or independent datum/vertex verification');
  const geoDecisions = new Map(geographic.all_decisions.map(row => [row.native_label, row]));
  const features = new Map(geometry.features.map(feature => [feature.properties.native_label, feature]));
  const priorUnits = new Map(prior.reporting_rows.filter(row => row.city === 'Somerville')
    .map(row => [`${row.ward}-${row.precinct}`, row]));
  const references = [];
  let vertices = 0;
  for (const row of native.all_native_shape_decisions) {
    const label = row.native_label, unit = priorUnits.get(label), check = geoDecisions.get(label);
    const feature = features.get(label), ring = feature?.geometry?.coordinates?.[0];
    if (!labels.has(label) || !unit || !check || references.some(ref => ref.native_label === label)
      || row.native_valid !== true || row.source_count_identity_qualified !== true
      || row.native_parts !== 1 || !Number.isInteger(row.native_id)
      || row.native_ballots_literal !== unit.source_count
      || check.geographic_valid !== true || check.cyclic_vertex_adjacency_preserved !== true
      || !Number.isFinite(check.maximum_error_degrees) || check.maximum_error_degrees > 1e-9
      || check.checked_vertices !== row.native_vertices || feature.geometry.type !== 'Polygon'
      || feature.geometry.coordinates.length !== 1 || ring?.length !== row.native_vertices
      || JSON.stringify(ring[0]) !== JSON.stringify(ring.at(-1))
      || ring.some(point => point.length !== 2 || !point.every(Number.isFinite)
        || point[0] < -71.2 || point[0] > -71 || point[1] < 42.3 || point[1] > 42.5))
      throw new Error('Changed literal native city identity, count, ring or independent coordinate check');
    vertices += row.native_vertices;
    references.push({
      city: 'Somerville', ward: unit.ward, precinct: unit.precinct, native_label: label,
      native_object_id: row.native_id, source: 'somerville-city-precincts',
      native_level: unit.precinct.endsWith('A') ? 'subprecinct' : 'precinct',
      native_properties: { ID: row.native_id, WARD: Number(unit.ward), Precinct: label },
      source_count: unit.source_count, qualified: true,
      disposition: 'qualified_direct_native_city_reference_no_clipping',
      source_unit_id: key(unit.ward, unit.precinct),
    });
  }
  if (references.length !== 32 || features.size !== 32 || geoDecisions.size !== 32
    || priorUnits.size !== 32 || vertices !== 2697
    || new Set(references.map(row => row.native_object_id)).size !== 28
    || references.reduce((sum, row) => sum + row.source_count, 0) !== 64597)
    throw new Error('Incomplete32-unit source; duplicate native IDs must not erase the split rows');
  const pairs = new Set();
  for (const row of native.all_native_pair_decisions) {
    const identity = [row.left_label, row.right_label].sort().join('|');
    if (!labels.has(row.left_label) || !labels.has(row.right_label) || row.left_label === row.right_label
      || pairs.has(identity) || row.overlap_area_us_survey_feet_squared !== 0
      || row.positive_overlap !== false)
      throw new Error('Changed complete native pair decisions; no overlap repair');
    pairs.add(identity);
  }
  if (pairs.size !== 496) throw new Error('Incomplete native topology decisions');
  return {
    ...prior, inputs, complete_download_url: inputs.complete_download_url,
    reporting_references: prior.reporting_references.filter(row => row.city === 'Boston').concat(references),
    city_reference_geometries: features, native_projection_wkt: wkt,
    native_projection_wkt_sha256: sha256(wkt),
    summary: { ...prior.summary, mapped_reporting_references: 307, split_parent_holds: 0,
      native_city_reference_shapes: 32, native_city_reference_vertices: 2697,
      native_city_reference_pair_decisions: 496 },
  };
}

export function loadMassachusettsCityReference() {
  const read = path => JSON.parse(readFileSync(`${directory}/${path}`, 'utf8'));
  const inputs = read('inputs.json');
  const prior = loadMassachusettsNativeCounts();
  if (sha256(readFileSync(`data/county-source-reviews/${priorVersion}/inputs.json`))
    !== inputs.prior_inputs_sha256) throw new Error('Changed complete prior native inputs');
  for (const [path, receipt] of Object.entries(inputs.files)) {
    const body = readFileSync(`${directory}/${path}`);
    if (body.length !== receipt.bytes || sha256(body) !== receipt.sha256)
      throw new Error(`Changed sufficient native city reference input: ${path}`);
  }
  return reviewMassachusettsCityReference({ prior, inputs,
    native: read(inputs.queries.native_reference), geographic: read(inputs.queries.geographic_reference),
    geometry: read(inputs.queries.display_reference),
    declaration: read('public-city-precinct-declarations.json'),
    request: read('exact-wkt-transformations-request.json') });
}

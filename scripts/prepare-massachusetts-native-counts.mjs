import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { loadMassachusettsNativeCounts, massachusettsVersion as version } from './massachusetts-native-counts.mjs';

const root = `data/county-source-reviews/${version}`;
const cityDirectory = `public/participation-city-counts/${version}`;
const precinctDirectory = `public/participation-precincts/${version}`;
if ([cityDirectory, precinctDirectory, `${root}/publication.json`].some(existsSync))
  throw new Error('An existing Massachusetts public source cannot be overwritten');
const read = path => JSON.parse(readFileSync(`${root}/${path}`, 'utf8'));
const reviewed = loadMassachusettsNativeCounts();
const pointer = JSON.parse(readFileSync('public/participation-precincts.json', 'utf8'));
if (pointer.additional_sources.length !== 4
  || !pointer.additional_sources[3].base_url.includes('20261110-new-hampshire-ward-reference-03'))
  throw new Error('Changed accepted additional-source registry; preserve it before extending');
for (const source of [pointer, ...pointer.additional_sources]) {
  let path;
  if (source.base_url.startsWith('/')) path = `public${source.base_url}index.json`;
  else {
    const url = new URL(source.base_url);
    if (url.hostname !== 'raw.githubusercontent.com'
      || !url.pathname.startsWith('/hanshanley/margin_of_error/'))
      throw new Error('Unrecognized existing source; preserve and review it before extension');
    path = url.pathname.split('/').filter(Boolean).slice(3).join('/') + '/index.json';
  }
  const index = JSON.parse(readFileSync(path, 'utf8'));
  if (index.states?.MA) throw new Error('An existing Massachusetts source must not be replaced or duplicated');
}
const digest = body => createHash('sha256').update(body).digest('hex');
const referenceByTown = new Map(reviewed.municipality_references
  .map(row => [row.native_properties.TOWN_ID, row]));
const originalTowns = read('selected-native-geometry-02/massachusetts-municipalities-full-geographic-original.geojson');
const towns = originalTowns.features.filter(feature =>
  referenceByTown.get(feature.properties.TOWN_ID)?.geometry_qualified).map(feature => ({
  type: 'Feature',
  properties: { key: `MA:TOWN:${String(feature.properties.TOWN_ID).padStart(3, '0')}`,
    name: feature.properties.TOWN, state_code: 'MA', level: 'municipality', boundary_year: null,
    native_town_id: feature.properties.TOWN_ID, native_object_id: feature.properties.OBJECTID,
    source_id: 'massgis-current-generalized-coast-municipal-reference',
    topology_valid_without_repairs: true, certified_legal_boundaries: false },
  geometry: feature.geometry,
}));
if (towns.length !== 350 || towns.some(feature => feature.properties.native_town_id === 315))
  throw new Error('Invalid original Wayland geometry must stay held');
const townBody = gzipSync(JSON.stringify({ type: 'FeatureCollection', features: towns }), { level: 9 });
const reference = {
  review_id: version, geography_scope: 'native_partial_city_reporting_context',
  identity_field: 'TOWN_ID', boundary_year: null, localities: 350,
  native_source_localities: 351, mapped_localities: 2,
  geometry_holds: [{ native_town_id: 315, name: 'WAYLAND',
    reason: 'Invalid original native and geographic ring; not repaired' }],
  certified_election_boundaries: false, source_geometries_repaired: false,
  url: `/participation-city-counts/${version}/MA.geojson.gz`,
  bytes: townBody.length, sha256: digest(townBody),
};
const featureSources = {
  boston: { folder: 'selected-native-geometry-01', name: 'boston', oid: 'FID',
    source_item_id: 'a8ae7fca286d4441901a97d116d6c9fa', native_epsg: 3857,
    layer_name: 'Boston Precinct Boundaries',
    boundary_label: 'Boston municipal precinct reference adopted 2022; planning/visualization context, not certified 2026 legal precincts' },
  'somerville-subprecincts': { folder: 'selected-native-geometry-01', name: 'somerville-subprecincts',
    oid: 'OBJECTID', source_item_id: 'c96fa785cc694bcdbc07032be7d9365a', native_epsg: 26986,
    layer_name: 'Subprecincts (2022)',
    boundary_label: 'Native MassGIS Somerville subprecinct reference, not certified 2026 legal precincts' },
  'somerville-parent-precincts': { folder: 'selected-native-geometry-02', name: 'somerville-parent-precincts',
    oid: 'OBJECTID', source_item_id: '6d4ae7efad4f4c77907db7cbfb012e64', native_epsg: 26986,
    layer_name: 'Wards and Precincts 2022',
    boundary_label: 'Native MassGIS Somerville precinct reference; four split-parent count joins stay held without clipping' },
};
const originals = new Map(Object.entries(featureSources).map(([name, source]) => [
  name, new Map(read(`${source.folder}/${source.name}-full-geographic-original.geojson`)
    .features.map(feature => [feature.properties[source.oid], feature])),
]));
const units = new Map(reviewed.reporting_rows.map(row => [row.source_unit_id, row]));
const features = reviewed.reporting_references.filter(row => row.qualified).map(row => {
  const source = featureSources[row.source];
  const unitKey = `${row.city}:Ward:${row.ward}:Precinct:${row.precinct}`;
  const native = units.get(unitKey);
  const original = originals.get(row.source)?.get(row.native_object_id);
  const city = reviewed.cities.find(city => city.city === row.city);
  if (!native || !original || !city || original.geometry.type !== 'Polygon')
    throw new Error('Missing exact native reporting-unit geometry or count');
  return { type: 'Feature', properties: {
    key: `MA|${unitKey}`, year: 2026, state_code: 'MA', county: row.city, county_fips: null,
    county_id: `additional:MA:city:${city.reference_key}`,
    unit: `Ward ${row.ward}, ${row.native_level === 'subprecinct' ? 'Subprecinct' : 'Precinct'} ${row.precinct}`,
    unit_key: unitKey, unit_kind: `municipal_${row.native_level}`, reporting_unit_kind: `municipal_${row.native_level}`,
    native_ward_number: Number(row.ward), native_precinct_label: row.precinct,
    native_object_id: row.native_object_id, source_snapshot: version,
    match_status: 'matched_unchanged_native_reporting_reference',
    ballots: native.source_count, denominator: null, reported_pct: null,
    native_record: native.native_record, source_url: native.source_url,
    participation_measure_label: native.participation_measure_label,
    source_count_qualified: true, cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
    maps_approved: true, source_election_date: '2026-11-03', boundary_label: source.boundary_label,
    reference_geometry: { source_item_id: source.source_item_id, rest_layer_id: 0,
      layer_name: source.layer_name, native_reference_source: row.source,
      native_projection_epsg: source.native_epsg, boundary_vintage: 2022,
      topology_valid_without_repairs: true, single_path_per_polygon: true,
      certified_legal_boundaries: false, native_overlaps_preserved: true,
      source_geometry_clipped: false },
    quality_flags: native.quality_flags, geometry_withheld_reason: null,
    rate_withheld_reason: 'Literal native counts only; no qualified unique-person count or analysis denominator/rate.',
    source_update_label: row.city === 'Boston'
      ? 'Native election November 3, 2026; PDF November 4, 11:39:02 AM; timezone not supplied.'
      : 'Native election November 3, 2026; common update clock/timezone not supplied.',
    source_reporting_label: row.city === 'Boston'
      ? 'Native Times Cast, corroborated by six complete statewide context fields and declaring-page Ballots Cast. Separate summary Voters Cast556369/registered0/N_A are not substituted or repaired.'
      : 'Native BALLOTS CAST - TOTAL, not qualified unique people. Source registers and conflicting Official/UnOfficial labels remain separate; no split-parent remainder is constructed.',
  }, geometry: original.geometry };
});
if (features.length !== 303 || new Set(features.map(feature => feature.properties.key)).size !== 303
  || features.filter(feature => feature.properties.county === 'Boston').length !== 275
  || features.filter(feature => feature.properties.county === 'Somerville').length !== 28)
  throw new Error('Incomplete approved reporting-reference inventory');
const precinctBody = gzipSync(JSON.stringify({ type: 'FeatureCollection', features }), { level: 9 });
const metadata = {
  source_id: version, expected_features: 303, native_source_reporting_rows: 307,
  mapped_cities: { Boston: 275, Somerville: 28 }, held_table_only_reporting_rows: 4,
  held_split_parent_units: ['Somerville:Ward:1:Precinct:4', 'Somerville:Ward:2:Precinct:1',
    'Somerville:Ward:4:Precinct:2', 'Somerville:Ward:6:Precinct:3'],
  boundary_reference_year: 2022, certified_legal_precinct_boundaries: false,
  counts_only: true, rates_approved: false, source_geometry_repaired: false,
  source_geometry_clipped: false, source_native_overlaps_preserved: true,
  native_overlap_pairs: 2,
  native_vertices_verified: features.reduce((sum, feature) => sum + feature.geometry.coordinates[0].length, 0),
  source_city_counts: { Boston: 185569, Somerville: 64597 },
  mapped_count_checks_by_city: Object.fromEntries(['Boston', 'Somerville'].map(city => [
    city, features.filter(feature => feature.properties.county === city)
      .reduce((sum, feature) => sum + feature.properties.ballots, 0),
  ])),
  bytes: precinctBody.length, sha256: digest(precinctBody),
  complete_download_url: reviewed.complete_download_url,
  area_column_label: 'City', ballot_column_label: 'Native reporting-unit count',
  boundary_label: 'Official native municipal precinct/subprecinct display references, not certified 2026 legal precincts',
  notes: 'Boston275 / Somerville28 native reference joins. Four Somerville split-parent counts remain table-only; parent polygons are not clipped to invent remainders. All307 raw reporting rows and all351 municipal reference decisions remain in the full download. No rates, source repairs, county allocations or unique-person claims.',
};
const cityIndex = { year: 2026, state_code: 'MA', source_id: version,
  reference_geometry: reference, complete_download_url: reviewed.complete_download_url };
const precinctIndex = { year: 2026, boundary_date: metadata.boundary_label,
  states: { MA: 'MA.geojson.gz' }, state_metadata: { MA: metadata } };
for (const [directory, body, index] of [
  [cityDirectory, townBody, cityIndex], [precinctDirectory, precinctBody, precinctIndex],
]) {
  mkdirSync(directory, { recursive: true });
  writeFileSync(`${directory}/MA.geojson.gz`, body);
  writeFileSync(`${directory}/index.json`, JSON.stringify(index, null, 2) + '\n');
}
pointer.additional_sources.push({ base_url: `/participation-precincts/${version}/` });
writeFileSync('public/participation-precincts.json', JSON.stringify(pointer, null, 2) + '\n');
const publication = { status: 'prepared_local_NOT_native_website_acceptance',
  source_id: version, city_reference: reference, reporting_reference: metadata };
writeFileSync(`${root}/publication.json`, JSON.stringify(publication, null, 2) + '\n');
console.log(JSON.stringify({ status: publication.status, cities: 2, municipality_shapes: 350,
  reporting_shapes: 303, held_source_rows: 4, city_bytes: townBody.length,
  reporting_bytes: precinctBody.length, previous_additional_sources_preserved: 4 }));

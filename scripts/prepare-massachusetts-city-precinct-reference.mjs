import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { gunzipSync, gzipSync } from 'node:zlib';
import { massachusettsVersion as priorVersion } from './massachusetts-native-counts.mjs';
import { loadMassachusettsCityReference,
  massachusettsCityReferenceVersion as version } from './massachusetts-city-precinct-reference.mjs';

const root = `data/county-source-reviews/${version}`;
const directory = `public/participation-precincts/${version}`;
if (existsSync(directory) || existsSync(`${root}/publication.json`))
  throw new Error('An existing city-reference publication cannot be overwritten');
const read = path => JSON.parse(readFileSync(path, 'utf8'));
const reviewed = loadMassachusettsCityReference();
const pointer = read('public/participation-precincts.json');
const oldPointer = structuredClone(pointer);
if (pointer.additional_sources.length !== 5
  || pointer.additional_sources[4].base_url !== `/participation-precincts/${priorVersion}/`)
  throw new Error('Preserve the accepted source registry before extending city references');
const old = JSON.parse(gunzipSync(readFileSync(`public/participation-precincts/${priorVersion}/MA.geojson.gz`)));
const boston = old.features.filter(feature => feature.properties.county === 'Boston');
if (boston.length !== 275) throw new Error('Missing complete prior Boston reference');
const nativeUnits = new Map(reviewed.reporting_rows.map(row => [row.source_unit_id, row]));
const features = boston.map(feature => ({
  ...feature, properties: { ...feature.properties, source_snapshot: version },
}));
for (const reference of reviewed.reporting_references.filter(row => row.city === 'Somerville')) {
  const unitKey = reference.source_unit_id;
  const native = nativeUnits.get(unitKey);
  const original = reviewed.city_reference_geometries.get(reference.native_label);
  if (!native || !original || !reference.qualified || original.geometry.type !== 'Polygon')
    throw new Error('Missing direct native city shape/count; do not clip a parent');
  features.push({ type: 'Feature', properties: {
    key: `MA|${unitKey}`, year: 2026, state_code: 'MA', county: 'Somerville', county_fips: null,
    county_id: 'additional:MA:city:MA:TOWN:274',
    unit: `Ward ${reference.ward}, ${reference.native_level === 'subprecinct' ? 'Subprecinct' : 'Precinct'} ${reference.precinct}`,
    unit_key: unitKey, unit_kind: `municipal_${reference.native_level}`,
    reporting_unit_kind: `municipal_${reference.native_level}`,
    native_ward_number: Number(reference.ward), native_precinct_label: reference.precinct,
    native_object_id: reference.native_object_id, native_source_label: reference.native_label,
    source_snapshot: version, match_status: 'matched_direct_native_city_reporting_reference',
    ballots: native.source_count, denominator: null, reported_pct: null,
    native_record: native.native_record, source_url: native.source_url,
    participation_measure_label: native.participation_measure_label,
    source_count_qualified: true, cast_ballot_count_qualified: false,
    unique_voter_count_qualified: false, maps_approved: true, source_election_date: '2026-11-03',
    boundary_label: 'City-declared Somerville display reference: 2020 Census basis, metadata updated September 22, 2023; not certified 2026 legal precincts',
    reference_geometry: {
      source_item_id: null, source_dataset_id: 'da4y-vuae', rest_layer_id: null,
      layer_name: 'City of Somerville Precincts',
      native_reference_source: 'somerville-city-precincts', native_projection_epsg: null,
      native_projection_wkt_sha256: reviewed.native_projection_wkt_sha256,
      boundary_vintage: null, source_metadata_revision: '2023-09-22', source_census_basis: 2020,
      topology_valid_without_repairs: true, single_path_per_polygon: true,
      certified_legal_boundaries: false, native_overlaps_preserved: true,
      cyclic_vertex_adjacency_verified: true, duplicate_native_ids_preserved: true,
      source_geometry_clipped: false,
    },
    quality_flags: native.quality_flags, geometry_withheld_reason: null,
    rate_withheld_reason: 'Literal native counts only; no qualified unique-person count or analysis denominator/rate.',
    source_update_label: 'Native election November 3, 2026; common source update clock/timezone not supplied.',
    source_reporting_label: 'Native BALLOTS CAST - TOTAL, not qualified unique people. Source registers and conflicting Official/UnOfficial labels remain separate. Every city precinct/subprecinct joins its own original city shape; no parent remainder is constructed.',
  }, geometry: original.geometry });
}
if (features.length !== 307 || new Set(features.map(feature => feature.properties.key)).size !== 307
  || features.filter(feature => feature.properties.county === 'Somerville')
    .reduce((sum, feature) => sum + feature.properties.ballots, 0) !== 64597)
  throw new Error('Incomplete direct city-reference coverage');
const body = gzipSync(JSON.stringify({ type: 'FeatureCollection', features }), { level: 9 });
const sha256 = value => createHash('sha256').update(value).digest('hex');
const metadata = {
  source_id: version, expected_features: 307, native_source_reporting_rows: 307,
  mapped_cities: { Boston: 275, Somerville: 32 }, held_table_only_reporting_rows: 0,
  held_split_parent_units: [], boundary_reference_year: null,
  city_reference_source_years: { Boston: 2022, Somerville: null },
  city_reference_source_metadata_revisions: { Somerville: '2023-09-22' },
  city_reference_dataset_id: 'da4y-vuae',
  city_reference_native_wkt_sha256: reviewed.native_projection_wkt_sha256,
  certified_legal_precinct_boundaries: false, counts_only: true, rates_approved: false,
  source_geometry_repaired: false, source_geometry_clipped: false,
  source_native_overlaps_preserved: true, native_overlap_pairs: 2,
  native_vertices_verified: features.reduce((sum, feature) => sum + feature.geometry.coordinates[0].length, 0),
  source_city_counts: { Boston: 185569, Somerville: 64597 },
  mapped_count_checks_by_city: { Boston: 185569, Somerville: 64597 },
  bytes: body.length, sha256: sha256(body), complete_download_url: reviewed.complete_download_url,
  area_column_label: 'City', ballot_column_label: 'Native reporting-unit count',
  boundary_label: 'Boston2022 and city-declared Somerville references (metadata2023); not certified2026 legal precincts',
  notes: 'Boston275 / Somerville32 direct native reference joins. Four former split-parent holds now use actual city polygons, never clipped remainders. All307 raw reporting rows, earlier303-reference release and351 municipal decisions remain in complete downloads. Invalid Wayland municipal geometry remains held. No rates, county allocations, source repairs or unique-person claims.',
};
mkdirSync(directory, { recursive: true });
writeFileSync(`${directory}/MA.geojson.gz`, body);
writeFileSync(`${directory}/index.json`, JSON.stringify({
  year: 2026, boundary_date: metadata.boundary_label,
  states: { MA: 'MA.geojson.gz' }, state_metadata: { MA: metadata },
}, null, 2) + '\n');
pointer.additional_sources[4] = { base_url: `/participation-precincts/${version}/` };
if (JSON.stringify(pointer.additional_sources.slice(0, 4))
  !== JSON.stringify(oldPointer.additional_sources.slice(0, 4)))
  throw new Error('Earlier four additional sources changed');
writeFileSync('public/participation-precincts.json', JSON.stringify(pointer, null, 2) + '\n');
const cityIndex = `public/participation-city-counts/${priorVersion}/index.json`;
writeFileSync(`${root}/publication.json`, JSON.stringify({
  version, prior_version: priorVersion, source_reporting_rows: 307, reporting_references: 307,
  city_reference_shapes: 32, prior_municipality_reference_reused_unchanged: true,
  reused_city_index: cityIndex, reused_city_index_sha256: sha256(readFileSync(cityIndex)),
  reporting_bytes: body.length, reporting_sha256: sha256(body),
  earlier_source_registry_entries_preserved: 4, prior_full_release_preserved: true,
  full_analysis_url: reviewed.complete_download_url, rates_approved: false,
}, null, 2) + '\n');
console.log(JSON.stringify({ status: 'PASS_prepared307_native_references_NOT_live_acceptance',
  reporting_bytes: body.length, city_wkt_sha256: reviewed.native_projection_wkt_sha256,
  municipal_context_reused_without_duplicate_asset: true }));

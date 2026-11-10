import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { gunzipSync } from 'node:zlib';
import { loadAdditionalParticipation } from './additional-participation.mjs';
import { massachusettsCityReferenceVersion as version } from './massachusetts-city-precinct-reference.mjs';
import { massachusettsVersion as priorVersion } from './massachusetts-native-counts.mjs';
import { qualifiedMassachusettsReportingReference } from '../public/scripts/participation-geography.js';

const read = path => JSON.parse(readFileSync(path, 'utf8'));
const compressed = path => JSON.parse(gunzipSync(readFileSync(path)));
const path = `public/participation-precincts/${version}/MA.geojson.gz`;
const current = compressed(path);

test('307 current references preserve Boston originals and use complete32 direct city shapes with explicit source clocks', () => {
  const index = read(`public/participation-precincts/${version}/index.json`).state_metadata.MA;
  assert.equal(createHash('sha256').update(readFileSync(path)).digest('hex'), index.sha256);
  assert.equal(index.held_table_only_reporting_rows, 0);
  assert.equal(index.boundary_reference_year, null);
  assert.equal(current.features.length, 307);
  assert.ok(current.features.every(feature => qualifiedMassachusettsReportingReference(feature.properties)));
  const original = compressed(`public/participation-precincts/${priorVersion}/MA.geojson.gz`);
  assert.deepEqual(current.features.slice(0, 275).map(feature => feature.geometry),
    original.features.slice(0, 275).map(feature => feature.geometry));
  assert.deepEqual(current.features.slice(0, 275).map(feature => feature.properties.native_record),
    original.features.slice(0, 275).map(feature => feature.properties.native_record));
  const city = current.features.filter(feature => feature.properties.county === 'Somerville');
  assert.equal(city.length, 32);
  assert.equal(new Set(city.map(feature => feature.properties.native_object_id)).size, 28);
  assert.equal(city.reduce((sum, feature) => sum + feature.properties.ballots, 0), 64597);
  assert.ok(city.every(feature => feature.properties.reference_geometry.boundary_vintage === null
    && feature.properties.reference_geometry.source_metadata_revision === '2023-09-22'));
  const data = loadAdditionalParticipation({ nativeCountyParents: true });
  assert.equal(data.precincts.filter(row => row.state_code === 'MA' && row.geometry_withheld_reason).length, 0);
  assert.ok(data.counties.filter(row => row.state_code === 'MA')
    .every(row => row.native_reporting_reference_snapshot === version && row.held_reporting_reference_rows === 0));
});

test('new direct city references cannot be relabeled as clipped MassGIS parents, rounded CRS aliases or turnout rates', () => {
  const properties = current.features.find(feature =>
    feature.properties.unit_key === 'Somerville:Ward:1:Precinct:4').properties;
  assert.equal(qualifiedMassachusettsReportingReference(properties), true);
  for (const change of [
    p => { p.reference_geometry.source_item_id = '6d4ae7efad4f4c77907db7cbfb012e64'; },
    p => { p.reference_geometry.native_reference_source = 'somerville-parent-precincts'; },
    p => { p.reference_geometry.rest_layer_id = 0; },
    p => { p.reference_geometry.native_projection_epsg = 2249; },
    p => { p.reference_geometry.native_projection_wkt_sha256 = '0'.repeat(64); },
    p => { p.reference_geometry.boundary_vintage = 2022; },
    p => { p.reference_geometry.cyclic_vertex_adjacency_verified = false; },
    p => { p.reference_geometry.source_geometry_clipped = true; },
    p => { p.denominator = 56008; p.reported_pct = p.ballots / 56008 * 100; },
  ]) {
    const changed = structuredClone(properties);
    change(changed);
    assert.equal(qualifiedMassachusettsReportingReference(changed), false);
  }
});

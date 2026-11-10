import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { gunzipSync } from 'node:zlib';
import { loadAdditionalParticipation } from './additional-participation.mjs';
import { massachusettsVersion as version } from './massachusetts-native-counts.mjs';
import { qualifiedMassachusettsCityReference, qualifiedMassachusettsReportingReference,
  selectCountySourceFrame } from '../public/scripts/participation-geography.js';

const root = `data/county-source-reviews/${version}`;
const read = path => JSON.parse(readFileSync(path, 'utf8'));
const compressed = path => JSON.parse(gunzipSync(readFileSync(path)));

test('MA city and reporting rows are live-only and never become county totals or denominators', () => {
  const legacy = loadAdditionalParticipation();
  assert.equal(legacy.counties.some(row => row.state_code === 'MA' && row.source_city_name), false);
  const live = loadAdditionalParticipation({ nativeCountyParents: true });
  const cities = live.counties.filter(row => row.state_code === 'MA');
  const units = live.precincts.filter(row => row.state_code === 'MA');
  assert.deepEqual(cities.map(row => [row.county, row.ballots]), [['Boston', 185569], ['Somerville', 64597]]);
  assert.equal(units.length, 307);
  assert.equal(units.filter(row => row.geometry_withheld_reason).length, 4);
  assert.ok(cities.every(row => 'county_fips' in row && row.county_fips === null && row.denominator === null
    && row.reported_pct === null && row.cast_ballot_count_qualified === false));
  assert.ok(units.every(row => row.denominator === null && row.reported_pct === null && row.maps_approved === false));
  assert.equal(selectCountySourceFrame({ counties: cities }, 'MA', 'available'), cities);
  assert.deepEqual(selectCountySourceFrame({ counties: cities }, 'MA', 'in_person_early'), []);
  assert.deepEqual(selectCountySourceFrame({ counties: cities }, 'MA', 'mail_returned'), []);
});

test('MA publishes unchanged valid originals, excludes Wayland without repair and checks raw checksums', () => {
  const index = read(`public/participation-city-counts/${version}/index.json`);
  const path = `public${index.reference_geometry.url}`;
  assert.equal(createHash('sha256').update(readFileSync(path)).digest('hex'), index.reference_geometry.sha256);
  const collection = compressed(path);
  const original = read(`${root}/selected-native-geometry-02/massachusetts-municipalities-full-geographic-original.geojson`);
  const byTown = new Map(original.features.map(feature => [feature.properties.TOWN_ID, feature]));
  assert.equal(collection.features.length, 350);
  for (const feature of collection.features)
    assert.deepEqual(feature.geometry, byTown.get(feature.properties.native_town_id).geometry);
  assert.equal(collection.features.some(feature => feature.properties.native_town_id === 315), false);
  const rows = loadAdditionalParticipation({ nativeCountyParents: true }).counties.filter(row => row.state_code === 'MA');
  assert.equal(qualifiedMassachusettsCityReference(rows, index.reference_geometry, collection), true);
  const changed = structuredClone(rows);
  changed[0].ballots = 556369;
  assert.equal(qualifiedMassachusettsCityReference(changed, index.reference_geometry, collection), false);
});

test('MA strict reporting guards accept303 originals, reject split-parent promotion and preserve source roles', () => {
  const collection = compressed(`public/participation-precincts/${version}/MA.geojson.gz`);
  assert.equal(collection.features.length, 303);
  assert.ok(collection.features.every(feature => feature.geometry.type === 'Polygon'
    && qualifiedMassachusettsReportingReference(feature.properties)));
  assert.equal(collection.features.filter(feature => feature.properties.unit_kind === 'municipal_subprecinct').length, 4);
  const feature = collection.features.find(feature => feature.properties.unit_key === 'Somerville:Ward:1:Precinct:4A');
  const changed = structuredClone(feature.properties);
  changed.native_precinct_label = '4'; changed.native_record.precinct = '4';
  changed.unit_key = 'Somerville:Ward:1:Precinct:4'; changed.key = `MA|${changed.unit_key}`;
  changed.unit_kind = changed.reporting_unit_kind = 'municipal_precinct';
  changed.reference_geometry.source_item_id = '6d4ae7efad4f4c77907db7cbfb012e64';
  changed.reference_geometry.native_reference_source = 'somerville-parent-precincts';
  assert.equal(qualifiedMassachusettsReportingReference(changed), false);
  const wrongRole = structuredClone(feature.properties);
  wrongRole.reference_geometry.rest_layer_id = 1;
  assert.equal(qualifiedMassachusettsReportingReference(wrongRole), false);
});

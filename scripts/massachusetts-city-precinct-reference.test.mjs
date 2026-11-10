import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { loadMassachusettsNativeCounts } from './massachusetts-native-counts.mjs';
import { loadMassachusettsCityReference, reviewMassachusettsCityReference,
  massachusettsCityReferenceVersion as version } from './massachusetts-city-precinct-reference.mjs';

const root = `data/county-source-reviews/${version}`;
const read = path => JSON.parse(readFileSync(`${root}/${path}`, 'utf8'));
const fixture = {
  prior: loadMassachusettsNativeCounts(), inputs: read('inputs.json'),
  native: read('native-only-review.json'), geographic: read('geographic-review.json'),
  geometry: read('verified32-city-display-reference.geojson'),
  declaration: read('public-city-precinct-declarations.json'),
  request: read('exact-wkt-transformations-request.json'),
};

test('direct city shapes close all four count joins without changing native counts or municipal holds', () => {
  const reviewed = loadMassachusettsCityReference();
  assert.deepEqual(reviewed.reporting_rows, fixture.prior.reporting_rows);
  assert.deepEqual(reviewed.cities, fixture.prior.cities);
  assert.deepEqual(reviewed.municipality_references, fixture.prior.municipality_references);
  assert.deepEqual(reviewed.reporting_references.filter(row => row.city === 'Boston'),
    fixture.prior.reporting_references.filter(row => row.city === 'Boston'));
  const city = reviewed.reporting_references.filter(row => row.city === 'Somerville');
  assert.equal(city.length, 32);
  assert.equal(new Set(city.map(row => row.native_object_id)).size, 28);
  assert.equal(city.reduce((sum, row) => sum + row.source_count, 0), 64597);
  const oldHolds = fixture.prior.reporting_references.filter(row => !row.qualified);
  assert.equal(oldHolds.length, 4);
  for (const old of oldHolds) {
    const row = city.find(row => row.ward === old.ward && row.precinct === old.precinct);
    assert.equal(row.qualified, true);
    assert.equal(row.source, 'somerville-city-precincts');
    assert.equal(row.source_count, old.source_count);
    assert.ok(reviewed.city_reference_geometries.has(row.native_label));
  }
});

test('city reference review rejects identity substitution, count changes and missing topology pairs', () => {
  for (const change of [
    input => { input.native.all_native_shape_decisions[3].native_label = '1-4A'; },
    input => { input.native.all_native_shape_decisions[3].native_ballots_literal += 1; },
    input => { input.native.all_native_pair_decisions.pop(); },
    input => { input.native.all_native_pair_decisions[0].positive_overlap = true; },
  ]) {
    const input = structuredClone(fixture);
    change(input);
    assert.throws(() => reviewMassachusettsCityReference(input));
  }
});

test('city reference review requires exact WKT and independently verified datum and cyclic edges', () => {
  for (const change of [
    input => { input.request.inSR = JSON.stringify({ wkid: 2249 }); },
    input => { input.geographic.summary.maximum_error_degrees = 2e-9; },
    input => { input.geographic.summary.declared_datum_operation.direction = 'forward'; },
    input => { input.geographic.all_decisions[0].cyclic_vertex_adjacency_preserved = false; },
    input => { input.geometry.features[0].geometry.coordinates[0].pop(); },
  ]) {
    const input = structuredClone(fixture);
    change(input);
    assert.throws(() => reviewMassachusettsCityReference(input));
  }
});

test('city reference extension never promotes source registers, geography dates or repaired source counts', () => {
  for (const change of [
    input => { input.inputs.analysis_rates_approved = true; },
    input => { input.inputs.certified_2026_election_boundaries = true; },
    input => { input.inputs.current_display_reference_year = 2022; },
    input => { input.inputs.source_geometries_clipped = true; },
    input => { input.inputs.source_counts_repaired = true; },
  ]) {
    const input = structuredClone(fixture);
    change(input);
    assert.throws(() => reviewMassachusettsCityReference(input));
  }
  const reviewed = reviewMassachusettsCityReference(fixture);
  assert.equal(reviewed.cities.find(row => row.city === 'Somerville').native_record.native_registered_voters, 56008);
  assert.equal(reviewed.cities.find(row => row.city === 'Boston').native_record.native_summary_registered, 0);
});

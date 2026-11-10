import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { loadAdditionalParticipation } from './additional-participation.mjs';
import { qualifiedNewHampshireCityReference } from '../public/scripts/participation-geography.js';

test('NH city/ward counts are live-only and never replace source components, registers or source conflicts', () => {
  const frozen = loadAdditionalParticipation();
  assert.equal(frozen.counties.filter(r => r.state_code === 'NH').length, 0);
  assert.equal(frozen.precincts.filter(r => r.state_code === 'NH').length, 0);
  const live = loadAdditionalParticipation({ nativeCountyParents: true });
  const cities = live.counties.filter(r => r.state_code === 'NH');
  const wards = live.precincts.filter(r => r.state_code === 'NH');
  assert.equal(cities.length, 4);
  assert.equal(wards.length, 37);
  const manchester = cities.find(r => r.county === 'Manchester');
  assert.equal(manchester.ballots, 38562);
  assert.equal(manchester.native_city_parent_printed, false);
  assert.equal(manchester.native_record.wards.find(r => r.ward === 7).total, 2712);
  assert.equal(manchester.native_record.federal_only_added_to_total, false);
  const concord = cities.find(r => r.county === 'Concord');
  assert.equal(concord.ballots, 19234);
  assert.equal(concord.native_record.native_totals.opening, 25879);
  assert.equal(concord.native_record.native_totals.closing, 27340);
  assert.equal(concord.native_printed_pct, '74.32%');
  const nashua = cities.find(r => r.county === 'Nashua');
  assert.equal(nashua.ballots, 33849);
  assert.equal(nashua.native_record.wards.find(r => r.ward === 8).absentee, 225);
  const dover = cities.find(r => r.county === 'Dover');
  assert.equal(dover.ballots, 15941);
  assert.equal(dover.native_printed_pct, '71.0%');
  assert.equal(dover.native_record.native_register_rows.at(-1).registered, 22456);
  assert.ok([...cities, ...wards].every(r => r.denominator === null && r.reported_pct === null));
  assert.ok(wards.every(r => r.maps_approved === false && r.unit_kind === 'municipal_ward'));
});

test('partial city reference rejects wrong city identity, corrected sums, false rates and false2026 shapes', () => {
  const live = loadAdditionalParticipation({ nativeCountyParents: true });
  const rows = live.counties.filter(r => r.state_code === 'NH'), ref = rows[0].reference_geometry;
  const collection = JSON.parse(gunzipSync(readFileSync(
    'public/participation-city-counts/20261110-new-hampshire-01/NH.geojson.gz')));
  assert.ok(qualifiedNewHampshireCityReference(rows, ref, collection));
  for (const change of [
    x => x[0].ballots = 38647,
    x => x[0].native_city_parent_printed = true,
    x => x[0].native_record.federal_only_added_to_total = true,
    x => x[0].denominator = 1,
    x => x[0].reported_pct = 100,
    x => x[0].source_election_date = '2024-11-05',
    x => x[0].reference_municipality_key = '3314200',
    x => x[0].cast_ballot_count_qualified = true,
  ]) {
    const changed = structuredClone(rows);
    change(changed);
    assert.equal(qualifiedNewHampshireCityReference(changed, ref, collection), false);
  }
  assert.equal(qualifiedNewHampshireCityReference(rows, { ...ref, boundary_year: 2026 }, collection), false);
  for (const change of [
    x => x.find(r => r.county === 'Dover').native_record.native_election_label = '2025 GENERAL ELECTION',
    x => x.find(r => r.county === 'Dover').ballots = 14632,
    x => x.find(r => r.county === 'Nashua').ballots = 33847,
  ]) {
    const changed = structuredClone(rows);
    change(changed);
    assert.equal(qualifiedNewHampshireCityReference(changed, ref, collection), false);
  }
  const duplicate = structuredClone(collection);
  duplicate.features[0].properties.key = duplicate.features[1].properties.key;
  assert.equal(qualifiedNewHampshireCityReference(rows, ref, duplicate), false);
});

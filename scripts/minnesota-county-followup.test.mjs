import test from 'node:test';
import assert from 'node:assert/strict';
import { loadMinnesotaFollowup } from './minnesota-county-followup.mjs';
import { qualifiedMinnesotaCountyFrame, selectCountySourceFrame } from '../public/scripts/participation-geography.js';

const data = loadMinnesotaFollowup();

test('all84 complete county counts and4105 same-snapshot units preserve true unknowns and native identities', () => {
  assert.ok(qualifiedMinnesotaCountyFrame(data.counties));
  assert.equal(data.counties.filter(row => row.ballots !== null).length, 84);
  assert.equal(data.counties.filter(row => row.reported_pct !== null).length, 71);
  assert.deepEqual(data.counties.filter(row => row.ballots === null).map(row => row.county),
    ['Fillmore', 'Hubbard', 'Wright']);
  const becker = data.counties.find(row => row.county === 'Becker');
  assert.equal(becker.native_record.native_county_id, '03');
  assert.equal(becker.county_fips, '27005');
  assert.equal(data.precincts.length, 4105);
  assert.equal(data.precincts.filter(row => row.ballots === null).length, 26);
  assert.ok(data.precincts.every(row => row.maps_approved === false && row.reference_geometry === null
    && row.denominator === null && row.reported_pct === null));
  assert.equal(data.precincts.reduce((sum, row) => sum + (row.ballots ?? 0), 0), 2827091);
});

test('available source frame explicitly selects the new whole snapshot over retained legacy records', () => {
  const legacy = [{ state_code: 'MN', county: 'Aitkin', ballots: 1 }];
  const input = { counties: legacy, county_frames: { native_county_followup: data.counties } };
  assert.equal(selectCountySourceFrame(input, 'MN', 'available'), data.counties);
  assert.deepEqual(input.counties, legacy);
  assert.throws(() => selectCountySourceFrame(input, 'MN', 'in_person_early'),
    /all-method counts are not substituted/);
});

test('the browser rejects estimated totals, partial-as-complete, replaced registers and source-conflict rates', () => {
  for (const change of [
    rows => { rows.find(row => row.county === 'Wright').ballots = 0; },
    rows => { rows.find(row => row.county === 'Becker').county_fips = '27003'; },
    rows => { rows[0].denominator = 3927036; },
    rows => { rows[0].ballots = 2852528; },
    rows => { rows[0].reference_geometry.boundary_year = 2024; },
    rows => { rows[0].source_snapshot = '20261106-minnesota-facts-01'; },
    rows => { rows.find(row => row.county === 'Benton').reported_pct = 1; },
  ]) {
    const rows = structuredClone(data.counties);
    change(rows);
    assert.equal(qualifiedMinnesotaCountyFrame(rows), false);
    assert.throws(() => selectCountySourceFrame({
      counties: [], county_frames: { native_county_followup: rows },
    }, 'MN', 'available'), /Unqualified Minnesota/);
  }
});

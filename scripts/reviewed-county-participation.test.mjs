import assert from 'node:assert/strict';
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { parse } from 'csv-parse/sync';
import { gunzipSync } from 'node:zlib';
import { loadReviewedCountyParticipation, loadReviewedStatewideParticipation,
  loadReviewedMinnesotaParticipation } from './reviewed-county-participation.mjs';

const reviews = JSON.parse(readFileSync('public/participation-source-reviews.json', 'utf8')).reviews;
const batchCounties = ['Juniata', 'Mercer', 'Montour', 'Columbia', 'Greene', 'Lycoming'];
const isBatch = row => ['CA', 'GA'].includes(row.state_code) || row.state_code === 'PA' && batchCounties.includes(row.county);

test('Minnesota preserves all 87 native inventories without treating partial subtotals as county participation', () => {
  const rows = loadReviewedMinnesotaParticipation(reviews);
  const source = reviews.find(row => row.id === 'minnesota-bulk-participation-20261106-01');
  const native = parse(readFileSync(join(source.data_directory, 'county-participation.csv')), { columns: true });
  assert.deepEqual(rows.map(row => row.native_record), native);
  assert.equal(rows.filter(row => row.ballots !== null).length, 75);
  assert.equal(rows.filter(row => row.reported_pct !== null).length, 64);
  assert.equal(rows.filter(row => row.ballots === null).length, 12);
  for (const row of rows) {
    assert.equal(row.maps_approved, false);
    assert.equal(row.native_record.native_fips, '');
    assert.equal(row.native_printed_pct, null);
    assert.deepEqual(row.native_source_updates, []);
    assert.match(row.source_update_label, /fetch receipts are not report updates/);
    assert.match(row.source_reporting_label, /not inferred ballot modes/);
    if (row.ballots === null) {
      assert.equal(row.denominator, null);
      assert.equal(row.reported_pct, null);
      assert.match(row.source_reporting_label, /partial subtotal is not the county total/);
    } else {
      assert.equal(row.ballots, Number(row.native_record.complete_total_number_voted));
      assert.equal(row.denominator, Number(row.native_record.complete_registered_7am)
        + Number(row.native_record.complete_registered_election_day));
      if (row.reported_pct !== null)
        assert.equal(row.reported_pct, 100 * row.ballots / row.denominator);
    }
  }
});

test('Minnesota keeps supplied counts and electorates but withholds fractions for native conflicts', () => {
  const rows = loadReviewedMinnesotaParticipation(reviews);
  const held = rows.filter(row => row.ballots !== null && row.reported_pct === null);
  assert.equal(held.length, 11);
  for (const row of held) {
    assert.ok(row.denominator > 0);
    assert.ok(Number(row.native_record.reported_precinct_component_conflicts) > 0
      || Number(row.native_record.reported_precinct_electorate_excesses) > 0);
    assert.match(row.source_reporting_label, /not completed ballot counting or certification/);
  }
  assert.deepEqual(rows.filter(row => row.ballots === null).map(row => row.county), [
    'Anoka', 'Carver', 'Fillmore', 'Hubbard', 'Kittson', 'Lac Qui Parle', 'Otter Tail',
    'St. Louis', 'Sherburne', 'Wadena', 'Washington', 'Wright',
  ]);
});

test('Minnesota rejects changed whole inputs and missing or duplicate registrations while exposing every published asset', () => {
  const original = reviews.find(row => row.id === 'minnesota-bulk-participation-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'minnesota-participation-'));
  try {
    const files = ['county-participation.csv', 'audit.json', 'sources.json'];
    const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
    for (const changed of files) {
      for (const file of files) copyFileSync(join(original.data_directory, file), join(directory, file));
      writeFileSync(join(directory, changed), readFileSync(join(directory, changed), 'utf8') + '\n');
      assert.throws(() => loadReviewedMinnesotaParticipation(altered), /Invalid reviewed county participation/);
    }
    assert.throws(() => loadReviewedMinnesotaParticipation(reviews.filter(row => row !== original)),
      /Missing or duplicated reviewed county source/);
    assert.throws(() => loadReviewedMinnesotaParticipation([...reviews, original]),
      /Missing or duplicated reviewed county source/);
    const release = JSON.parse(readFileSync(
      'data/county-source-reviews/20261106-minnesota-publication-01/release-verification.json'));
    assert.deepEqual(new Set([...original.downloads.map(row => row.file), original.complete_download_url.split('/').at(-1)]),
      new Set(release.files.map(row => row.file)));
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('adds all 159 Georgia native county observations without changing the prior 974-record query', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-12/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => row.state_code !== 'GA' && row.county !== 'Lycoming'), oldReviewed);
  const counties = rows.filter(row => row.state_code === 'GA');
  const source = reviews.find(row => row.id === 'georgia-bulk-participation-20261106-01');
  const native = parse(readFileSync(join(source.data_directory, 'county-participation.csv')), { columns: true });
  assert.equal(counties.length, 159);
  assert.deepEqual(counties.map(row => row.native_record), native);
  assert.equal(counties.reduce((sum, row) => sum + row.ballots, 0), 4210155);
  assert.equal(counties.reduce((sum, row) => sum + (row.denominator ?? 0), 0), 7516484);
  assert.equal(counties.filter(row => row.reported_pct !== null).length, 157);
  for (const row of counties) {
    assert.equal(row.ballots, Number(row.native_record.native_ballots_cast));
    assert.equal(row.native_record.source_fips, '');
    assert.equal(row.maps_approved, false);
    assert.equal(row.native_record.counting_complete, 'False');
    assert.equal(row.participation_measure_literal, 'ballotsCast');
    assert.match(row.source_reporting_label, /not completed counting or certification/);
    assert.equal(row.native_source_updates.length, 3);
    for (const update of row.native_source_updates)
      assert.equal(update.declared_timezone, update.native_update_literal.endsWith('Z') ? 'UTC' : '');
    if (row.denominator !== null) assert.equal(row.reported_pct, 100 * row.ballots / row.denominator);
  }
  for (const [county, ballots] of [['Screven County', 5236], ['Jeff Davis County', 4180]]) {
    const row = counties.find(row => row.county === county);
    assert.equal(row.ballots, ballots);
    assert.equal(Number(row.native_record.native_total_voters), 0);
    assert.equal(row.denominator, null);
    assert.equal(row.reported_pct, null);
    assert.equal(row.native_printed_pct, null);
  }
  assert.deepEqual(counties.filter(row => row.native_record.native_is_official_results === 'True')
    .map(row => row.county), ['Wilkinson County']);
});

test('retains the independent Georgia statewide Voters header and conflicting API root zero without approving its rate', () => {
  const state = loadReviewedStatewideParticipation(reviews).find(row => row.state_code === 'GA');
  assert.equal(state.state, 'Georgia');
  assert.equal(state.ballots, 4210155);
  assert.equal(state.denominator, 7516484);
  assert.equal(state.native_printed_pct, '56.01%');
  assert.equal(state.native_record.original_conflicting_api_root_ballots, '0');
  assert.equal(state.native_record.missing_county_registration_denominators, '2');
  assert.equal(state.validated_pct, null);
  assert.equal(state.reported_pct, null);
  assert.equal(state.native_record.printed_timezone, '');
  assert.match(state.source_update_label, /Thursday, November 5, 2026 at 12:29:04 PM.*timezone not declared/);
  assert.equal(state.source_status_literal, 'Native isOfficialResults=false (unofficial)');
  assert.match(state.quality.join(' '), /372 missing candidate-mode cells are not zero/);
  assert.match(state.quality.join(' '), /not an approved analysis rate/);
});

test('both Georgia loaders reject changed complete inputs and missing or duplicate source registrations', () => {
  const original = reviews.find(row => row.id === 'georgia-bulk-participation-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'georgia-participation-'));
  try {
    const files = ['county-participation.csv', 'statewide-participation.csv', 'audit.json'];
    const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
    for (const changed of files) {
      for (const file of files) copyFileSync(join(original.data_directory, file), join(directory, file));
      writeFileSync(join(directory, changed), readFileSync(join(directory, changed), 'utf8') + '\n');
      for (const load of [loadReviewedCountyParticipation, loadReviewedStatewideParticipation])
        assert.throws(() => load(altered), /Invalid reviewed county participation/);
    }
    for (const load of [loadReviewedCountyParticipation, loadReviewedStatewideParticipation]) {
      assert.throws(() => load(reviews.filter(row => row !== original)), /Missing or duplicated reviewed county source/);
      assert.throws(() => load([...reviews, original]), /Missing or duplicated reviewed county source/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('preserves all context10 observations and separates Columbia participation from filtered mail processing', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-10/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !['pennsylvania-columbia-20261106-01',
    'pennsylvania-greene-20261106-01', 'pennsylvania-lycoming-20261106-01',
    'georgia-bulk-participation-20261106-01'].includes(row.review_id)), oldReviewed);
  const row = rows.find(row => row.review_id === 'pennsylvania-columbia-20261106-01');
  assert.equal(row.ballots, 22583);
  assert.equal(row.denominator, 40797);
  assert.equal(row.reported_pct, 100 * 22583 / 40797);
  assert.equal(row.native_printed_pct, '55.35%');
  assert.equal(row.participation_measure_literal, 'Total Ballots');
  assert.equal(row.source_status_literal, 'UNOFFICIAL ELECTION RESULTS');
  assert.equal(row.reported_units, 42);
  assert.equal(row.total_units, 42);
  assert.equal(row.maps_approved, false);
  assert.equal(row.native_record.source_fips, '');
  assert.equal(row.native_record.counting_complete, 'False');
  assert.deepEqual(row.native_source_updates, [
    { source: 'results', native_update_literal: '11/3/2026 10:37:16 PM EST', declared_timezone: 'EST' },
    { source: 'mail-summary', native_update_literal: '', declared_timezone: '' },
  ]);
  assert.match(row.source_reporting_label, /mail returned 3,785 and votes recorded 3,772/);
  assert.match(row.source_reporting_label, /no Election Day remainder is inferred/);
  assert.match(row.source_reporting_label, /registration parties are not candidate parties/);
  assert.match(row.source_reporting_label, /PDF creation metadata supplies neither a report update nor certification/);
});

test('adds all California native participation records while preserving every previous observation', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-09/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !['CA', 'GA'].includes(row.state_code)
    && !['pennsylvania-columbia-20261106-01', 'pennsylvania-greene-20261106-01',
      'pennsylvania-lycoming-20261106-01'].includes(row.review_id)), oldReviewed);
  const source = reviews.find(row => row.id === 'california-bulk-participation-20261106-01');
  const native = parse(readFileSync(join(source.data_directory, 'county-participation.csv'), 'utf8'),
    { columns: true });
  const counties = rows.filter(row => row.state_code === 'CA');
  assert.equal(counties.length, 58);
  assert.deepEqual(counties.map(row => row.native_record), native);
  for (const row of counties) {
    assert.equal(row.ballots, Number(row.native_record.reported_participation));
    assert.equal(row.denominator, Number(row.native_record.registered_voters));
    assert.equal(row.reported_pct, 100 * row.ballots / row.denominator);
    assert.equal(row.participation_measure_literal, 'voterTurnout');
    assert.equal(row.denominator_basis, 'native_registered_voters');
    assert.equal(row.native_record.county_fips, '');
    assert.equal(row.maps_approved, false);
    assert.equal(row.native_record.counting_complete, 'false');
    assert.equal(row.native_record.declared_timezone, '');
    assert.match(row.source_reporting_label, /does not establish completed counting or certification/);
    assert.match(row.quality.join(' '), /not CVAP, VAP, VEP, CPS or demographic turnout/);
    assert.equal(row.native_source_updates.length, 3);
  }
});

test('loads the separate native California statewide observation without treating it as a county', () => {
  const counties = loadReviewedCountyParticipation(reviews).filter(row => row.state_code === 'CA');
  const [state] = loadReviewedStatewideParticipation(reviews);
  assert.equal(state.state, 'California');
  assert.equal(state.geography_level, 'statewide');
  assert.equal(state.native_record.native_county_code, '59');
  assert.equal(state.ballots, 8928966);
  assert.equal(state.denominator, 23273590);
  assert.equal(state.validated_pct, 100 * 8928966 / 23273590);
  assert.equal(state.native_printed_pct, '38.4%');
  assert.equal(counties.reduce((total, row) => total + row.ballots, 0), state.ballots);
  assert.equal(counties.reduce((total, row) => total + row.denominator, 0), state.denominator);
  assert.ok(counties.every(row => row.county_id !== state.county_id));
  assert.equal(state.source_status_literal, 'reportType: SF; reportTypeCode: F');
  assert.match(state.source_update_label, /202611051858 \(timezone not declared\)/);
  assert.ok(state.source_url.endsWith('/statewide-participation.csv'));
});

test('both California loaders reject altered county, statewide and audit bytes or duplicated registration', () => {
  const original = reviews.find(row => row.id === 'california-bulk-participation-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'california-participation-'));
  try {
    const files = ['county-participation.csv', 'statewide-participation.csv', 'audit.json'];
    const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
    for (const changed of files) {
      for (const file of files) copyFileSync(join(original.data_directory, file), join(directory, file));
      writeFileSync(join(directory, changed), readFileSync(join(directory, changed), 'utf8') + '\n');
      for (const load of [loadReviewedCountyParticipation, loadReviewedStatewideParticipation])
        assert.throws(() => load(altered), /Invalid reviewed county participation/);
    }
    for (const load of [loadReviewedCountyParticipation, loadReviewedStatewideParticipation]) {
      assert.throws(() => load(reviews.filter(row => row !== original)), /Missing or duplicated reviewed county source/);
      assert.throws(() => load([...reviews, original]), /Missing or duplicated reviewed county source/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('preserves every context08 record and literal three-county participation qualifications', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-08/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !isBatch(row)), oldReviewed);
  for (const [county, ballots, registrations, printed, provisional] of [
    ['Juniata', 8258, 14095, '58.59%', '0'],
    ['Mercer', 39121, 72238, '54.16%', '0'],
    ['Montour', 7008, 12418, '56.43%', '25'],
  ]) {
    const row = rows.find(row => row.county === county);
    assert.equal(row.ballots, ballots);
    assert.equal(row.denominator, registrations);
    assert.equal(row.reported_pct, 100 * ballots / registrations);
    assert.equal(row.native_printed_pct, printed);
    assert.equal(row.participation_measure_literal, 'Ballots Cast - Total');
    assert.equal(row.native_record.provisional_ballots, provisional);
    assert.equal(row.native_record.source_fips, '');
    assert.equal(row.native_record.complete_counting, 'False');
    assert.equal(row.maps_approved, false);
    assert.equal(row.source_status_literal, 'UNOFFICIAL RESULTS');
    assert.deepEqual(row.native_source_updates.map(update => update.source), ['summary', 'statement']);
    assert.ok(row.native_source_updates.every(update => update.declared_timezone === ''));
    assert.match(row.source_reporting_label, /do not establish completed ballot counting/);
  }
  const mercer = rows.find(row => row.county === 'Mercer');
  assert.equal(mercer.native_record.native_mail_mode_literal, 'Absentee');
  assert.equal(mercer.native_record.native_provisional_mode_literal, 'Provision\nal');
  assert.match(mercer.source_reporting_label, /overvotes and undervotes are absent/);
  assert.match(mercer.source_reporting_label, /16,437\/22,684 ballots/);
  assert.match(mercer.source_reporting_label, /each Sandy Lake Borough question has 226 ballots/);
  assert.match(rows.find(row => row.county === 'Montour').source_reporting_label, /No counter is repaired/);
});

test('rejects altered participation, source clocks or audit metadata in each new county and Perry', () => {
  for (const county of [...batchCounties, 'Perry']) {
    const original = reviews.find(row => row.id === `pennsylvania-${county.toLowerCase()}-20261106-01`);
    const directory = mkdtempSync(join(tmpdir(), 'pinned-county-participation-'));
    try {
      const files = ['county-participation.csv',
        county === 'Greene' ? 'native-reporting-statistics.csv' : 'native-source-pages.csv', 'audit.json'];
      const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
      for (const changed of files) {
        for (const file of files) copyFileSync(join(original.data_directory, file), join(directory, file));
        writeFileSync(join(directory, changed), readFileSync(join(directory, changed), 'utf8') + '\n');
        assert.throws(() => loadReviewedCountyParticipation(altered),
          /Invalid reviewed county participation/);
      }
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  }
});

test('preserves every context07 native record and Perry ballots, registrations and absent ballot modes', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-07/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !isBatch(row) && row.county !== 'Perry'), oldReviewed);
  const row = rows.find(row => row.county === 'Perry');
  assert.equal(row.ballots, 18064);
  assert.notEqual(row.ballots, 17965);
  assert.equal(row.denominator, 31391);
  assert.equal(row.reported_pct, 100 * 18064 / 31391);
  assert.equal(row.native_printed_pct, '57.55%');
  assert.equal(row.participation_measure_literal, 'Total Ballots Cast');
  assert.equal(row.source_status_literal, 'Unofficial');
  assert.equal(row.native_record.source_status_literal, '');
  for (const field of ['election_day_ballots', 'mail_ballots', 'provisional_ballots'])
    assert.equal(row.native_record[field], '');
  assert.equal(row.native_record.native_fips, '');
  assert.equal(row.native_record.counting_complete, 'False');
  assert.equal(row.maps_approved, false);
  assert.deepEqual(row.native_source_updates.map(update => update.source), ['summary', 'statement']);
  assert.match(row.source_update_label, /summary: 2026-11-03 22:49:06 \(timezone not declared\)/);
  assert.match(row.source_update_label, /statement: 2026-11-03 22:30:24 \(timezone not declared\)/);
  assert.match(row.source_reporting_label, /four All Precincts aggregate headers are separate/);
  assert.match(row.source_reporting_label, /zero PR votes do not establish zero provisional ballots/);
  assert.match(row.source_reporting_label, /unresolved unit candidate cells are explicitly outside this query/);
});

test('rejects Perry candidate substitution, inferred ballot modes, completed counting and PDF status', () => {
  const original = reviews.find(row => row.id === 'pennsylvania-perry-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'perry-participation-'));
  try {
    for (const file of ['audit.json', 'native-source-pages.csv'])
      copyFileSync(join(original.data_directory, file), join(directory, file));
    const body = readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8');
    const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
    for (const input of [
      body.replace(',18064,', ',17965,'),
      body.replace(',31391,', ',31392,'),
      body.replace(',31,31,,,,', ',31,31,15276,2689,0,'),
      body.replace(',False,False,', ',False,True,'),
      body.replace('Unofficial', 'Official'),
    ]) {
      assert.notEqual(input, body);
      writeFileSync(join(directory, 'county-participation.csv'), input);
      assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('preserves every context06 record and Mifflin ballots without interpreting native zero registrations as turnout', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-06/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !isBatch(row) && !['Mifflin', 'Perry'].includes(row.county)), oldReviewed);
  const row = rows.find(row => row.county === 'Mifflin');
  assert.equal(row.ballots, 14439);
  assert.equal(row.denominator, null);
  assert.equal(row.reported_pct, null);
  assert.equal(row.native_record.registered_voters, '0');
  assert.equal(row.native_printed_pct, '0.00%');
  assert.equal(row.participation_measure_literal, 'Ballots Cast - Total');
  assert.equal(row.source_status_literal, 'UNOFFICIAL RESULTS');
  assert.equal(row.native_record.election_day_ballots, '12017');
  assert.equal(row.native_record.mail_ballots, '2422');
  assert.equal(row.native_record.provisional_ballots, '0');
  assert.equal(row.native_record.blank_ballots, '6');
  assert.equal(row.native_record.complete_precincts, '0');
  assert.equal(row.native_record.partially_reported_precincts, '26');
  assert.equal(row.native_record.county_fips, undefined);
  assert.equal(row.maps_approved, false);
  assert.deepEqual(row.native_source_updates.map(update => update.source), ['summary', 'statement']);
  assert.match(row.source_update_label, /summary: 11\/03\/2026 09:28PM \(timezone not declared\)/);
  assert.match(row.source_update_label, /statement: 11\/03\/2026 09:26PM \(timezone not declared\)/);
  assert.match(row.source_reporting_label, /rate is unavailable/);
  assert.match(row.source_reporting_label, /4,409\/10,030-ballot subsets/);
  assert.match(row.source_reporting_label, /Primary Election Day, November 3, 2026/);
  assert.match(row.source_reporting_label, /2,435 receipts.*counted mail 2,422.*difference 13 remains unexplained/);
});

test('rejects Mifflin receipt substitution, doubled blanks, invented denominator and completion', () => {
  const original = reviews.find(row => row.id === 'pennsylvania-mifflin-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'mifflin-participation-'));
  try {
    for (const file of ['audit.json', 'native-source-pages.csv'])
      copyFileSync(join(original.data_directory, file), join(directory, file));
    const body = readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8');
    const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
    for (const input of [body.replace(',14439,', ',14445,'), body.replace(',14439,0,', ',14439,25000,'),
      body.replace(',2422,0,', ',2435,0,'), body.replace(',2422,0,', ',2422,,'),
      body.replace(',26,26,0,26,', ',26,26,26,0,'), body.replace('UNOFFICIAL RESULTS', 'Official Results')]) {
      assert.notEqual(input, body);
      writeFileSync(join(directory, 'county-participation.csv'), input);
      assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('preserves every context05 native record and Potter ballot, receipt and accounting distinctions', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-05/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !isBatch(row) && !['Potter', 'Mifflin', 'Perry'].includes(row.county)), oldReviewed);
  const row = rows.find(row => row.county === 'Potter');
  assert.equal(row.ballots, 6244);
  assert.notEqual(row.ballots, 6221);
  assert.equal(row.denominator, 11041);
  assert.equal(row.reported_pct, 100 * 6244 / 11041);
  assert.equal(row.native_printed_pct, '56.55%');
  assert.equal(row.participation_measure_literal, 'Ballots Cast - Total');
  assert.equal(row.source_status_literal, 'UNOFFICIAL RESULTS');
  assert.equal(row.native_record.election_day_ballots, '5389');
  assert.equal(row.native_record.mail_ballots, '855');
  assert.equal(row.native_record.provisional_ballots, '0');
  assert.equal(row.native_record.blank_ballots, '2');
  assert.equal(row.native_record.complete_precincts, '0');
  assert.equal(row.native_record.partially_reported_precincts, '32');
  assert.equal(row.native_record.county_fips, undefined);
  assert.equal(row.maps_approved, false);
  assert.deepEqual(row.native_source_updates.map(update => update.source), ['summary', 'statement']);
  assert.match(row.source_update_label, /summary: 11\/04\/2026 2:44 PM \(timezone not declared\)/);
  assert.match(row.source_update_label, /statement: 11\/04\/2026 2:45 PM \(timezone not declared\)/);
  assert.match(row.source_reporting_label, /Election Day complete column nevertheless says 32/);
  assert.match(row.source_reporting_label, /871.*not counted mail 855.*difference 16 remains unexplained/);
  assert.match(row.source_reporting_label, /unit named breakdowns are absent, not zero/);
  assert.match(row.source_reporting_label, /Total Votes Cast and Contest Totals rows are absent/);
});

test('rejects Potter candidate/receipt substitutions, double-counted blanks, invented status or missing zero', () => {
  const original = reviews.find(row => row.id === 'pennsylvania-potter-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'potter-participation-'));
  try {
    for (const file of ['audit.json', 'native-source-pages.csv'])
      copyFileSync(join(original.data_directory, file), join(directory, file));
    const body = readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8');
    const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
    for (const input of [body.replace(',6244,', ',6221,'), body.replace(',6244,', ',6246,'),
      body.replace(',855,0,', ',871,0,'), body.replace(',855,0,', ',855,,'),
      body.replace(',32,32,0,32,', ',32,32,32,0,'), body.replace('UNOFFICIAL RESULTS', 'Official Results')]) {
      assert.notEqual(input, body);
      writeFileSync(join(directory, 'county-participation.csv'), input);
      assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('preserves every context04 native record and distinct Elk/Forest counts, missingness and scan scope', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-04/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !isBatch(row) && !['Elk', 'Forest', 'Potter', 'Mifflin', 'Perry'].includes(row.county)), oldReviewed);
  const elk = rows.find(row => row.county === 'Elk');
  assert.equal(elk.ballots, 11742);
  assert.notEqual(elk.ballots, 11679);
  assert.equal(elk.denominator, 20533);
  assert.equal(elk.reported_pct, 100 * 11742 / 20533);
  assert.equal(elk.native_printed_pct, '57.19%');
  assert.equal(elk.native_record.mail_ballots, '2017');
  assert.equal(elk.native_record.provisional_ballots, '0');
  assert.equal(elk.native_record.partially_reported_precincts, '29');
  assert.deepEqual(elk.native_source_updates.map(row => row.source), ['summary', 'statement', 'act88']);
  assert.equal(elk.native_source_updates[2].native_update_literal, '');
  assert.match(elk.source_update_label, /11\/03\/2026 22:08 PM/);
  assert.match(elk.source_reporting_label, /55.10%.*319\/579.*55.09%/);
  assert.match(elk.source_reporting_label, /2,035 \/ recorded 2,018.*counted mail 2,017/);
  assert.match(elk.source_reporting_label, /Federal|filtered Act88/);
  const forest = rows.find(row => row.county === 'Forest');
  assert.equal(forest.ballots, 1877);
  assert.notEqual(forest.ballots, 1870);
  assert.equal(forest.denominator, 3275);
  assert.equal(forest.reported_pct, 100 * 1877 / 3275);
  assert.equal(forest.native_printed_pct, '57.31%');
  for (const field of ['election_day_ballots', 'mail_ballots', 'provisional_ballots'])
    assert.equal(forest.native_record[field], '');
  assert.equal(forest.native_record.source_page, '2');
  assert.equal(forest.native_record.native_printed_page, 'Page 1 of 2');
  assert.equal(forest.native_record.partially_reported_precincts, '9');
  assert.deepEqual(forest.native_source_updates.map(row => row.source), ['summary', 'statement']);
  assert.match(forest.source_update_label, /11\/03\/2026 20:56 PM/);
  assert.match(forest.source_reporting_label, /311.*not counted mail/);
  assert.match(forest.source_reporting_label, /both full text engines are empty/);
  assert.match(forest.source_reporting_label, /derived residuals remain unclassified/);
  for (const row of [elk, forest]) {
    assert.equal(row.participation_measure_literal, 'Ballots Cast - Total');
    assert.equal(row.source_status_literal, 'UNOFFICIAL RESULTS');
    assert.equal(row.native_record.complete_precincts, '0');
    assert.equal(row.native_record.county_fips, undefined);
    assert.equal(row.maps_approved, false);
    assert.match(row.source_update_label, /timezone not declared/);
  }
});

test('rejects Elk/Forest candidate or receipt substitution, invented modes, completion and page identity', () => {
  for (const county of ['elk', 'forest']) {
    const original = reviews.find(row => row.id === `pennsylvania-${county}-20261106-01`);
    const directory = mkdtempSync(join(tmpdir(), `${county}-participation-`));
    try {
      for (const file of ['audit.json', 'native-source-pages.csv'])
        copyFileSync(join(original.data_directory, file), join(directory, file));
      const body = readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8');
      const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
      const inputs = county === 'elk'
        ? [body.replace(',11742,', ',11679,'), body.replace(',2017,0,', ',2035,0,'),
          body.replace(',2017,0,', ',2017,,'), body.replace(',29,29,0,29,', ',29,29,29,0,')]
        : [body.replace(',1877,', ',1870,'), body.replace('57.31%,,,,', '57.31%,0,311,0,'),
          body.replace(',9,9,0,9,', ',9,9,9,0,'), body.replace(',summary,2,', ',summary,1,')];
      for (const input of inputs) {
        assert.notEqual(input, body);
        writeFileSync(join(directory, 'county-participation.csv'), input);
        assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
      }
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  }
});

test('preserves every context03 native record and distinct Cameron/Carbon participation scopes', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-03/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !isBatch(row) && !['Cameron', 'Carbon', 'Elk', 'Forest', 'Potter', 'Mifflin', 'Perry'].includes(row.county)), oldReviewed);
  const cameron = rows.find(row => row.county === 'Cameron');
  assert.equal(cameron.ballots, 1624);
  assert.notEqual(cameron.ballots, 1617);
  assert.equal(cameron.denominator, 2885);
  assert.equal(cameron.reported_pct, 100 * 1624 / 2885);
  assert.equal(cameron.native_printed_pct, '56.29%');
  assert.equal(cameron.participation_measure_literal, 'Ballots Cast - Total');
  assert.equal(cameron.source_status_literal, 'UNOFFICIAL RESULTS');
  assert.equal(cameron.native_record.mail_ballots, '319');
  assert.equal(cameron.native_record.provisional_ballots, '');
  assert.equal(cameron.native_record.complete_precincts, '0');
  assert.equal(cameron.native_record.partially_reported_precincts, '10');
  assert.deepEqual(cameron.native_source_updates.map(row => row.source), ['summary', 'act88']);
  assert.equal(cameron.native_source_updates[1].native_update_literal, '');
  assert.match(cameron.source_reporting_label, /zero complete and ten partially reported/);
  assert.match(cameron.source_reporting_label, /returned 324 \/ recorded 320 are not counted Mail 319/);
  assert.match(cameron.source_reporting_label, /12:01 link label does not supply one/);
  const carbon = rows.find(row => row.county === 'Carbon');
  assert.equal(carbon.ballots, 24840);
  assert.notEqual(carbon.ballots, 24490);
  assert.equal(carbon.denominator, 45896);
  assert.equal(carbon.reported_pct, 100 * 24840 / 45896);
  assert.equal(carbon.native_printed_pct, '54.12%');
  assert.equal(carbon.participation_measure_literal, 'Voters Cast');
  assert.equal(carbon.source_status_literal, 'Unofficial Results');
  assert.equal(carbon.native_record.provisional_count, '0');
  assert.deepEqual(carbon.native_source_updates.map(row => row.source), ['summary', 'zero', 'statement']);
  for (const clock of ['summary: 11/3/2026 10:36:36 PM', 'zero: 11/3/2026 7:05:24 PM',
    'statement: 11/3/2026 10:19:13 PM']) assert.ok(carbon.source_update_label.includes(clock));
  assert.match(carbon.source_reporting_label, /earlier Official Zero Report is a separate observation/);
  assert.match(carbon.source_reporting_label, /Kidder.*807\/1,457.*not additional county participation/);
  assert.match(carbon.source_reporting_label, /350\/381\/288\/30.*remain unclassified/);
  for (const row of [cameron, carbon]) {
    assert.equal(row.maps_approved, false);
    assert.equal(row.native_record.county_fips, undefined);
    assert.match(row.source_update_label, /timezone not declared/);
  }
});

test('rejects both new counties on candidate/zero substitution, changed modes or native status', () => {
  for (const county of ['cameron', 'carbon']) {
    const original = reviews.find(row => row.id === `pennsylvania-${county}-20261106-01`);
    const directory = mkdtempSync(join(tmpdir(), `${county}-participation-`));
    try {
      for (const file of ['audit.json', 'native-source-pages.csv'])
        copyFileSync(join(original.data_directory, file), join(directory, file));
      const body = readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8');
      const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
      const inputs = county === 'cameron'
        ? [body.replace(',1624,', ',1617,'), body.replace(',319,,', ',320,0,'),
          body.replace('Ballots Cast - Total,', 'Candidate Votes,'), body.replace('UNOFFICIAL RESULTS', 'Official Results')]
        : [body.replace(',24840,', ',0,'), body.replace(',4465,0,', ',4465,,'),
          body.replace('Voters Cast,', 'Candidate Votes,'), body.replace('Unofficial Results', 'Official Zero Report')];
      for (const input of inputs) {
        assert.notEqual(input, body);
        writeFileSync(join(directory, 'county-participation.csv'), input);
        assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
      }
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  }
});

test('preserves every previous entire record and Clarion native participation scope', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-02/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !isBatch(row) && !['Clarion', 'Cameron', 'Carbon', 'Elk', 'Forest', 'Potter', 'Mifflin', 'Perry'].includes(row.county)), oldReviewed);
  const row = rows.find(row => row.county === 'Clarion');
  assert.equal(row.ballots, 12975);
  assert.notEqual(row.ballots, 12893);
  assert.equal(row.denominator, 23306);
  assert.equal(row.reported_pct, 100 * 12975 / 23306);
  assert.equal(row.native_printed_pct, '55.67%');
  assert.equal(row.participation_measure_literal, 'Voters Cast');
  assert.equal(row.native_record.provisional_count, '');
  assert.equal(row.source_status_literal, 'UNOFFICIAL ELECTION RESULTS');
  assert.equal(row.maps_approved, false);
  assert.equal(row.native_record.county_fips, undefined);
  assert.match(row.source_update_label, /county_report: 11\/3\/2026 9:49:20 PM \(timezone not declared\)/);
  assert.match(row.source_reporting_label, /40 of 40.*does not establish completed ballot counting/);
  assert.match(row.source_reporting_label, /missing mode counts are not zero/);
  assert.match(row.source_reporting_label, /Foxburg.*82\/116.*not additional county participation/);
});

test('rejects Clarion candidate substitution, invented modes and changed source qualifications', () => {
  const original = reviews.find(row => row.id === 'pennsylvania-clarion-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'clarion-participation-'));
  try {
    for (const file of ['audit.json', 'native-source-pages.csv'])
      copyFileSync(join(original.data_directory, file), join(directory, file));
    const body = readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8');
    const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
    for (const input of [body.replace(',12975,', ',12893,'), body.replace(',23306,', ',116,'),
      body.replace('Voters Cast,', 'Ballots Cast,'), body.replace(',40,40,,,', ',40,40,,0,')]) {
      assert.notEqual(input, body);
      writeFileSync(join(directory, 'county-participation.csv'), input);
      assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('preserves every previous entire record while adding reviewed Jefferson Voters Cast', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-01/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !isBatch(row) && !['Jefferson', 'Clarion', 'Cameron', 'Carbon', 'Elk', 'Forest', 'Potter', 'Mifflin', 'Perry'].includes(row.county)), oldReviewed);
  const row = rows.find(row => row.county === 'Jefferson');
  assert.equal(row.ballots, 15205);
  assert.equal(row.denominator, 28226);
  assert.equal(row.reported_pct, 100 * 15205 / 28226);
  assert.equal(row.native_printed_pct, '53.87%');
  assert.equal(row.participation_measure_literal, 'Voters Cast');
  assert.equal(row.native_record.provisional_voters_cast, '39');
  assert.equal(row.source_status_literal, 'Unofficial Results');
  assert.equal(row.native_record.county_fips, undefined);
  assert.equal(row.maps_approved, false);
  assert.deepEqual(row.native_source_updates.map(update => update.source), ['summary', 'statement']);
  assert.match(row.source_update_label, /summary: 11\/4\/2026 3:47:13 PM \(timezone not declared\)/);
  assert.match(row.source_update_label, /statement: 11\/4\/2026 3:47:52 PM \(timezone not declared\)/);
  assert.match(row.source_reporting_label, /Suppressed cells are not recovered by subtraction/);
  assert.match(row.source_reporting_label, /received absentee\/mail ballots are a separate receipt measure/);
});

test('rejects Jefferson vote substitution, changed privacy scope or repaired native values', () => {
  const original = reviews.find(row => row.id === 'pennsylvania-jefferson-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'jefferson-participation-'));
  try {
    for (const file of ['audit.json', 'native-source-pages.csv'])
      copyFileSync(join(original.data_directory, file), join(directory, file));
    const body = readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8');
    const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
    for (const input of [body.replace(',15205,', ',15132,'), body.replace(',28226,', ',0,'),
      body.replace('Voters Cast,', 'Ballots Cast,'), body.replace('Suppressed cells are not recovered', 'Suppressed cells are recovered')]) {
      assert.notEqual(input, body);
      writeFileSync(join(directory, 'county-participation.csv'), input);
      assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('preserves context11 and loads Greene ballots without inventing its missing denominator or clock', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-11/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => !['pennsylvania-greene-20261106-01', 'pennsylvania-lycoming-20261106-01',
    'georgia-bulk-participation-20261106-01'].includes(row.review_id)), oldReviewed);
  const row = rows.find(row => row.review_id === 'pennsylvania-greene-20261106-01');
  const source = reviews.find(source => source.id === row.review_id);
  assert.deepEqual(row.native_record, parse(readFileSync(join(source.data_directory,
    'county-participation.csv')), { columns: true })[0]);
  assert.equal(row.ballots, 11105);
  assert.equal(row.denominator, null);
  assert.equal(row.reported_pct, null);
  assert.equal(row.native_printed_pct, null);
  assert.equal(row.native_record.blank_ballots, '5');
  assert.equal(row.native_record.registered_voters, '');
  assert.equal(row.native_record.source_fips, '');
  assert.equal(row.native_record.counting_complete, 'False');
  assert.equal(row.participation_measure_literal, 'Ballots Cast - Total');
  assert.equal(row.source_status_literal, 'Unofficial Results with MI and Absentee');
  assert.deepEqual(row.native_source_updates, []);
  assert.equal(row.source_update_label, 'Not supplied');
  assert.equal(row.reported_units, 42);
  assert.equal(row.total_units, 42);
  assert.equal(row.maps_approved, false);
  assert.match(row.source_reporting_label, /blank ballots.*not added/);
  assert.match(row.source_reporting_label, /Registrations and the turnout rate are not supplied, not zero/);
  assert.match(row.source_reporting_label, /42 of 42.*does not establish completed counting/);
});

test('loads all reviewed county participation without promoting map coverage', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  assert.equal(rows.length, 269);
  assert.equal(rows.filter(row => row.state_code === 'PA').length, 32);
  assert.equal(rows.filter(row => row.state_code === 'DC').length, 1);
  assert.equal(rows.filter(row => row.state_code === 'NJ').length, 19);
  assert.equal(rows.filter(row => row.state_code === 'CA').length, 58);
  assert.equal(rows.filter(row => row.state_code === 'GA').length, 159);
  assert.ok(rows.every(row => row.maps_approved === false));
  assert.ok(rows.filter(row => row.state_code !== 'CA'
    && !['pennsylvania-columbia-20261106-01', 'pennsylvania-greene-20261106-01', 'pennsylvania-lycoming-20261106-01']
      .includes(row.review_id)).every(row => row.reported_units === null));
  const monroe = rows.find(row => row.county === 'Monroe');
  assert.equal(monroe.county_id, 'reviewed:PA:Monroe');
  assert.equal(monroe.native_record.county_fips, undefined);
  assert.equal(monroe.ballots, 61025);
  assert.notEqual(monroe.ballots, 60481);
  const fulton = rows.find(row => row.county === 'Fulton');
  assert.equal(fulton.ballots, 5085);
  assert.notEqual(fulton.ballots, 5050);
  assert.equal(fulton.denominator, 10155);
  assert.equal(fulton.native_printed_pct, '50.07%');
});

test('preserves all context13 county records and keeps Lycoming ballots separate from candidate counters and mail receipts', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-13/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => row.review_id !== 'pennsylvania-lycoming-20261106-01'), oldReviewed);
  const row = rows.find(row => row.review_id === 'pennsylvania-lycoming-20261106-01');
  const source = reviews.find(source => source.id === row.review_id);
  assert.deepEqual(row.native_record, parse(readFileSync(join(source.data_directory,
    'county-participation.csv')), { columns: true })[0]);
  assert.equal(row.ballots, 40596);
  assert.equal(row.denominator, 73009);
  assert.equal(row.reported_pct, 100 * 40596 / 73009);
  assert.equal(row.native_printed_pct, '55.60%');
  assert.equal(row.participation_measure_literal, 'Total Ballots Cast');
  assert.equal(row.source_status_literal, 'Unofficial Results');
  assert.equal(row.reported_units, 80);
  assert.equal(row.total_units, 80);
  assert.equal(row.maps_approved, false);
  for (const field of ['blank_ballots', 'county_ballot_modes', 'source_fips', 'declared_timezone'])
    assert.equal(row.native_record[field], '');
  assert.equal(row.native_record.counting_complete, 'False');
  assert.deepEqual(row.native_source_updates, [
    { source: 'results', native_update_literal: '2026-11-05 10:37:43', declared_timezone: '' },
  ]);
  assert.match(row.source_update_label, /2026-11-05 10:37:43.*timezone not declared/);
  assert.match(row.source_reporting_label, /ED\/MI\/PR are candidate-vote columns/);
  assert.match(row.source_reporting_label, /5,770 Act88 mail receipts are not added/);
  assert.match(row.source_reporting_label, /weekday\/date conflict is retained/);
  for (const registrations of [reviews.filter(item => item !== source), [...reviews, source]])
    assert.throws(() => loadReviewedCountyParticipation(registrations), /Missing or duplicated reviewed county source/);
});

test('preserves complete Cumberland participation separately from selections and both report times', () => {
  const row = loadReviewedCountyParticipation(reviews).find(row => row.county === 'Cumberland');
  const review = reviews.find(review => review.id === row.review_id);
  const native = parse(readFileSync(join(review.data_directory, 'county-participation.csv'), 'utf8'),
    { columns: true })[0];
  assert.deepEqual(row.native_record, native);
  assert.equal(row.ballots, 117334);
  assert.notEqual(row.ballots, 114712);
  assert.equal(row.denominator, 185538);
  assert.equal(row.native_printed_pct, '63.24%');
  assert.equal(row.source_status_literal, 'UNOFFICIAL RESULTS');
  assert.equal(row.native_source_updates.length, 2);
  assert.match(row.source_update_label, /summary: 11\/04\/2026 12:37PM \(timezone not declared\)/);
  assert.match(row.source_update_label, /precinct: 11\/04\/2026 12:31PM \(timezone not declared\)/);
  assert.match(row.source_reporting_label, /Under\/overvotes and a separate provisional count are absent, not zero/);
  assert.match(row.source_reporting_label, /UPPER ALLEN 6 prints 65.36%/);
});

test('preserves partial counting, absent status, separate timestamps and D.C. accounting', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const chester = rows.find(row => row.county === 'Chester');
  assert.equal(chester.source_status_literal, '');
  assert.match(chester.quality.join(' '), /No native result-status literal/);
  assert.match(chester.quality.join(' '), /contest-ballot zeroes conflict/);
  const lancaster = rows.find(row => row.county === 'Lancaster');
  assert.match(lancaster.source_reporting_label, /Partially Reported: reporting-status-partially-reported; value 241/);
  assert.match(lancaster.source_reporting_label, /Provisional Voting: reporting-status-not-reported; value not supplied/);
  assert.match(lancaster.source_update_label, /as_of_utc: .*; publish_date_utc:/);
  const montgomery = rows.find(row => row.county === 'Montgomery');
  assert.match(montgomery.quality.join(' '), /428\/428 reporting applies only to Election Day/);
  assert.match(montgomery.source_update_label, /source_pdf_update_literal: .*source_json_exported_utc: .*source_json_generated_utc:/);
  const dc = rows.find(row => row.state_code === 'DC');
  assert.equal(dc.ballots, 185086);
  assert.equal(dc.denominator, 457371);
  assert.equal(dc.native_record.native_early_votes, '0');
  assert.equal(dc.native_record.native_show_early_votes, 'False');
  assert.equal(dc.native_record.early_ballot_total_established, 'False');
  assert.match(dc.quality.join(' '), /324 ballots remain unresolved/);
  assert.match(dc.quality.join(' '), /does not establish zero early ballots/);
  assert.equal(rows.find(row => row.county === 'Centre').native_source_updates.length, 6);
  const fulton = rows.find(row => row.county === 'Fulton');
  assert.equal(fulton.source_status_literal, 'Official Results');
  assert.match(fulton.source_reporting_label, /13 of 13.*0 of 1/);
  assert.match(fulton.source_reporting_label, /not independently established certification/);
  assert.match(fulton.source_update_label, /11:30 PM.*timezone not declared/);
});

test('preserves complete Adams ballots, native blank/provisional zeroes and partial-counting qualifications', () => {
  const row = loadReviewedCountyParticipation(reviews).find(row => row.county === 'Adams');
  const review = reviews.find(review => review.id === row.review_id);
  const native = parse(readFileSync(join(review.data_directory, 'county-participation.csv'), 'utf8'),
    { columns: true })[0];
  assert.deepEqual(row.native_record, native);
  assert.equal(row.ballots, 42660);
  assert.notEqual(row.ballots, 42477);
  assert.equal(row.denominator, 77163);
  assert.equal(row.native_printed_pct, '55.29%');
  assert.equal(row.reported_pct, 100 * 42660 / 77163);
  assert.equal(row.source_status_literal, 'UNOFFICIAL RESULTS');
  assert.equal(row.native_record.provisional_ballots, '0');
  assert.equal(row.native_record.blank_ballots, '5');
  assert.equal(row.native_record.mail_ballots, '10320');
  assert.equal(row.native_source_updates.length, 2);
  assert.ok(row.native_source_updates.every(update => update.native_update_literal === '11/03/2026 10:23PM'
    && update.declared_timezone === ''));
  assert.match(row.source_reporting_label, /0 of 53 complete and all 53 partially reported/);
  assert.match(row.source_reporting_label, /10,320, not the index's separately scoped 10,348/);
});

test('preserves Lebanon ballots while withholding its unusable native denominator zero', () => {
  const row = loadReviewedCountyParticipation(reviews).find(row => row.county === 'Lebanon');
  const review = reviews.find(review => review.id === row.review_id);
  const native = parse(readFileSync(join(review.data_directory, 'county-participation.csv'), 'utf8'),
    { columns: true })[0];
  assert.deepEqual(row.native_record, native);
  assert.equal(row.ballots, 51268);
  assert.notEqual(row.ballots, 51061);
  assert.equal(row.county_id, 'reviewed:PA:Lebanon');
  assert.equal(row.denominator, null);
  assert.equal(row.reported_pct, null);
  assert.equal(row.native_record.native_registered_voters, '0');
  assert.equal(row.native_record.registered_voters, '');
  assert.equal(row.native_printed_pct, '0.00%');
  assert.equal(row.source_status_literal, 'UNOFFICIAL RESULTS');
  assert.equal(row.native_source_updates.length, 2);
  assert.match(row.source_update_label, /county: 11\/05\/2026 12:16 PM \(timezone not declared\)/);
  assert.match(row.source_update_label, /unit: 11\/05\/2026 1:02 PM \(timezone not declared\)/);
  assert.match(row.source_reporting_label, /268 provisionals still to process/);
  assert.match(row.source_reporting_label, /0\/60 complete and 60\/60 partially reported/);
  assert.equal(row.maps_approved, false);
});

test('preserves Blair current ballots without substituting its pre-election zero report or House selections', () => {
  const row = loadReviewedCountyParticipation(reviews).find(row => row.county === 'Blair');
  const review = reviews.find(review => review.id === row.review_id);
  const native = parse(readFileSync(join(review.data_directory, 'county-participation.csv'), 'utf8'),
    { columns: true })[0];
  assert.deepEqual(row.native_record, native);
  assert.equal(row.ballots, 43898);
  assert.notEqual(row.ballots, 43749);
  assert.equal(row.denominator, 81846);
  assert.equal(row.reported_pct, 100 * 43898 / 81846);
  assert.equal(row.native_printed_pct, '53.63%');
  assert.equal(row.native_record.source_report, 'current');
  assert.equal(row.native_record.provisional_ballots, '0');
  assert.equal(row.source_status_literal, 'UNOFFICIAL RESULTS');
  assert.equal(row.native_source_updates.length, 2);
  assert.match(row.source_update_label, /current: 11\/03\/2026 10:45 PM \(timezone not declared\)/);
  assert.match(row.source_update_label, /pre_election_zero: 11\/03\/2026 6:00 AM \(timezone not declared\)/);
  assert.match(row.source_reporting_label, /Zero Report is a 6:00 AM pre-election snapshot, not current zero participation/);
  assert.match(row.source_reporting_label, /Blank ballots and pending ballots are not supplied, not zero/);
  assert.equal(row.maps_approved, false);
});

test('requires Lebanon native zero flags and withheld fields instead of accepting a repaired denominator', () => {
  const original = reviews.find(row => row.id === 'pennsylvania-lebanon-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'lebanon-participation-'));
  try {
    copyFileSync(join(original.data_directory, 'audit.json'), join(directory, 'audit.json'));
    const native = parse(readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8'),
      { columns: true })[0];
    const altered = reviews.map(row => row.id === original.id ? { ...row, data_directory: directory } : row);
    for (const change of [{ registered_voters: '100000' }, { native_registered_voters: '' },
      { registered_turnout_percent: '0' }, { native_printed_turnout: '' }, { ballots_cast: '0' }]) {
      const row = { ...native, ...change }, fields = Object.keys(row);
      writeFileSync(join(directory, 'county-participation.csv'), fields.join(',') + '\n'
        + fields.map(field => `"${row[field].replaceAll('"', '""')}"`).join(',') + '\n');
      assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('preserves Armstrong native Voters Cast without substituting party zeroes, selections or provisional participation', () => {
  const row = loadReviewedCountyParticipation(reviews).find(row => row.county === 'Armstrong');
  const review = reviews.find(review => review.id === row.review_id);
  const native = parse(readFileSync(join(review.data_directory, 'county-participation.csv'), 'utf8'),
    { columns: true })[0];
  assert.deepEqual(row.native_record, native);
  assert.equal(row.ballots, 24039);
  assert.notEqual(row.ballots, 23935);
  assert.equal(row.participation_measure_literal, 'Voters Cast');
  assert.equal(row.denominator, 43750);
  assert.equal(row.reported_pct, 100 * 24039 / 43750);
  assert.equal(row.native_printed_pct, '54.95%');
  assert.equal(row.native_record.provisional_voters_cast, '');
  assert.equal(row.source_status_literal, '2026 General Election Unofficial Results w/o PROV');
  assert.match(row.source_update_label, /county_report: 11\/3\/2026 10:26:30 PM \(timezone not declared\)/);
  assert.equal(row.native_source_updates.length, 1);
  assert.match(row.source_reporting_label, /Provisional participation is absent, not zero/);
  assert.match(row.source_reporting_label, /not measured party turnout or zero participation/);
  assert.equal(row.maps_approved, false);
});

test('rejects Armstrong relabeling or an invented provisional participation zero', () => {
  const original = reviews.find(row => row.id === 'pennsylvania-armstrong-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'armstrong-participation-'));
  try {
    copyFileSync(join(original.data_directory, 'audit.json'), join(directory, 'audit.json'));
    const native = parse(readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8'),
      { columns: true })[0];
    const altered = reviews.map(row => row.id === original.id ? { ...row, data_directory: directory } : row);
    for (const change of [{ native_participation_measure_literal: 'Ballots Cast' },
      { provisional_voters_cast: '0' }, { native_status_literal: 'Official Results' }]) {
      const row = { ...native, ...change }, fields = Object.keys(row);
      writeFileSync(join(directory, 'county-participation.csv'), fields.join(',') + '\n'
        + fields.map(field => `"${row[field].replaceAll('"', '""')}"`).join(',') + '\n');
      assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('preserves Wayne header participation, missing modes and explicitly attributed parent status', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const baseline = JSON.parse(readFileSync(
    'data/county-source-reviews/20261106-wayne-publication-01/baseline.json', 'utf8'));
  assert.deepEqual(rows.filter(row => !isBatch(row) && !['Wayne', 'Jefferson', 'Clarion', 'Cameron', 'Carbon', 'Elk', 'Forest', 'Potter', 'Mifflin', 'Perry'].includes(row.county) && row.state_code !== 'NJ'),
    baseline.previous_reviewed_county_records);
  const row = rows.find(row => row.county === 'Wayne');
  const review = reviews.find(review => review.id === row.review_id);
  const native = parse(readFileSync(join(review.data_directory, 'county-participation.csv'), 'utf8'),
    { columns: true })[0];
  assert.deepEqual(row.native_record, native);
  assert.equal(row.ballots, 21707);
  assert.notEqual(row.ballots, 21689);
  assert.notEqual(row.ballots, 21612);
  assert.equal(row.denominator, 36885);
  assert.equal(row.reported_pct, 100 * 21707 / 36885);
  assert.equal(row.native_printed_pct, '58.85%');
  assert.equal(row.source_status_literal, '2026 General Election Unofficial Results');
  assert.equal(row.native_record.native_status_literal, '');
  assert.match(row.quality.join(' '), /Result status comes from the declaring county page/);
  assert.match(row.source_update_label, /county_report: 2026-11-05 15:08:51 \(timezone not declared\)/);
  for (const field of ['election_day_ballots', 'mail_ballots', 'provisional_ballots'])
    assert.equal(row.native_record[field], '');
  assert.match(row.source_reporting_label, /18-ballot scope difference/);
  assert.match(row.source_reporting_label, /Party affiliations|Candidate parties are not supplied/);
  assert.equal(row.maps_approved, false);
});

test('rejects Wayne contest-count substitution, invented mode participation and status relabeling', () => {
  const original = reviews.find(row => row.id === 'pennsylvania-wayne-20261106-01');
  const directory = mkdtempSync(join(tmpdir(), 'wayne-participation-'));
  try {
    copyFileSync(join(original.data_directory, 'audit.json'), join(directory, 'audit.json'));
    const native = parse(readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8'),
      { columns: true })[0];
    const altered = reviews.map(row => row.id === original.id ? { ...row, data_directory: directory } : row);
    for (const change of [{ ballots_cast: '21689' }, { ballots_cast: '21612' },
      { provisional_ballots: '85' }, { election_day_ballots: '16242' }, { mail_ballots: '0' },
      { native_status_literal: 'Official Results' }, { native_parent_status_literal: 'Official Results' },
      { registered_voters: '36886' }]) {
      const row = { ...native, ...change }, fields = Object.keys(row);
      writeFileSync(join(directory, 'county-participation.csv'), fields.join(',') + '\n'
        + fields.map(field => `"${row[field].replaceAll('"', '""')}"`).join(',') + '\n');
      assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('rejects missing or duplicated reviewed sources instead of silently shrinking coverage', () => {
  assert.throws(() => loadReviewedCountyParticipation(reviews.filter(row => row.id !== 'pennsylvania-berks-20261105-01')),
    /Missing or duplicated reviewed county source/);
  assert.throws(() => loadReviewedCountyParticipation([...reviews,
    reviews.find(row => row.id === 'pennsylvania-berks-20261105-01')]),
    /Missing or duplicated reviewed county source/);
});

test('preserves New Jersey partial modes, native Cape May denominator and all previous entire records', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const baseline = JSON.parse(readFileSync(
    'data/county-source-reviews/20261106-nj-participation-publication-02/baseline.json', 'utf8'));
  assert.deepEqual(rows.filter(row => row.state_code !== 'NJ' && !isBatch(row) && !['Jefferson', 'Clarion', 'Cameron', 'Carbon', 'Elk', 'Forest', 'Potter', 'Mifflin', 'Perry'].includes(row.county)), baseline.previous_reviewed_county_records);
  const nj = rows.filter(row => row.state_code === 'NJ');
  assert.equal(nj.length, 19);
  assert.ok(nj.every(row => row.county_id === `reviewed:NJ:${row.county}` && !row.maps_approved));
  assert.ok(!nj.some(row => ['Essex', 'Hudson'].includes(row.county)));
  const derived = nj.filter(row => row.county !== 'Cape May');
  assert.equal(derived.length, 18);
  assert.ok(derived.every(row => row.denominator === null && row.reported_pct === null
    && row.native_printed_pct === null && row.participation_measure_literal === undefined
    && row.participation_measure_kind === 'derived_reported_mode_subtotal'
    && row.participation_measure_label.startsWith('Derived ')));
  for (const row of nj) {
    assert.equal(row.ballots, Number(row.native_record.early_voting_votes_cast)
      + Number(row.native_record.election_day_votes_cast) + Number(row.native_record.mail_ballots_tallied));
    assert.match(row.quality.join(' '), /Issued, received and pending ballots are separate/);
    assert.ok(row.native_source_updates.every(update => update.declared_timezone === ''));
  }
  const cape = nj.find(row => row.county === 'Cape May');
  assert.equal(cape.ballots, 41278);
  assert.equal(cape.denominator, 76899);
  assert.equal(cape.reported_pct, 100 * 41278 / 76899);
  assert.equal(cape.native_printed_pct, '53.68%');
  assert.equal(cape.participation_measure_literal, 'Ballots Cast - Total');
  assert.equal(cape.native_record.source_page, '2');
  assert.match(cape.source_reporting_label, /attached summary, PDF page 2/);
  assert.match(cape.source_update_label, /attached_participation_summary page 2: not supplied/);
  assert.equal(nj.find(row => row.county === 'Bergen').ballots, 319503);
  const union = nj.find(row => row.county === 'Union');
  assert.equal(union.ballots, 176356);
  assert.match(union.source_reporting_label, /405 overseas ballots tallied/);
  assert.equal(nj.find(row => row.county === 'Hunterdon').ballots, 63031);
});

test('rejects New Jersey count substitution, invented denominators and missing/duplicate complete sources', () => {
  const original = reviews.find(row => row.id === 'new-jersey-periodic-participation-20261106-02');
  assert.throws(() => loadReviewedCountyParticipation(reviews.filter(row => row !== original)),
    /Missing or duplicated reviewed county source/);
  assert.throws(() => loadReviewedCountyParticipation([...reviews, original]),
    /Missing or duplicated reviewed county source/);
  const directory = mkdtempSync(join(tmpdir(), 'nj-participation-'));
  try {
    for (const file of ['audit.json', 'native-source-pages.csv', 'native-counting-qualifications.csv'])
      copyFileSync(join(original.data_directory, file), join(directory, file));
    const body = readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8');
    const altered = reviews.map(row => row === original ? { ...row, data_directory: directory } : row);
    for (const input of [body.replace(',319503,', ',319504,'),
      body.replace(',76899,', ',0,'), body.replace('Derived Early Voting', 'Native all-mode total Early Voting')]) {
      assert.notEqual(input, body);
      writeFileSync(join(directory, 'county-participation.csv'), input);
      assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('rejects missing, invalid or mismatched native counts without coercing blanks to zero', () => {
  const original = reviews.find(row => row.id === 'pennsylvania-berks-20261105-01');
  const directory = mkdtempSync(join(tmpdir(), 'reviewed-county-participation-'));
  try {
    copyFileSync(join(original.data_directory, 'audit.json'), join(directory, 'audit.json'));
    const csv = readFileSync(join(original.data_directory, 'county-participation.csv'), 'utf8');
    const inputs = [
      csv.replace(',275941,', ',,'),
      csv.replace(',275941,', ',0,'),
      csv.replace(',143855,', ',,'),
      csv.replace(',143855,', ',-1,'),
      csv.replace(',143855,', ',275942,'),
      csv.replace(',PA,', ',DC,'),
    ];
    const altered = reviews.map(row => row.id === original.id ? { ...row, data_directory: directory } : row);
    for (const input of inputs) {
      assert.notEqual(input, csv);
      writeFileSync(join(directory, 'county-participation.csv'), input);
      assert.throws(() => loadReviewedCountyParticipation(altered), /Invalid reviewed county participation/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

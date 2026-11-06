import assert from 'node:assert/strict';
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { parse } from 'csv-parse/sync';
import { gunzipSync } from 'node:zlib';
import { loadReviewedCountyParticipation } from './reviewed-county-participation.mjs';

const reviews = JSON.parse(readFileSync('public/participation-source-reviews.json', 'utf8')).reviews;

test('preserves every previous entire record and Clarion native participation scope', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  const previous = JSON.parse(gunzipSync(readFileSync(
    'public/participation-county-context/20261106-02/complete-source-records.json.gz')));
  const oldReviewed = previous.filter(row => rows.some(current => current.county_id === row.county_id
    && current.state_code === row.state_code));
  assert.deepEqual(rows.filter(row => row.county !== 'Clarion'), oldReviewed);
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
  assert.deepEqual(rows.filter(row => !['Jefferson', 'Clarion'].includes(row.county)), oldReviewed);
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

test('loads all reviewed county participation without promoting map coverage', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  assert.equal(rows.length, 39);
  assert.equal(rows.filter(row => row.state_code === 'PA').length, 19);
  assert.equal(rows.filter(row => row.state_code === 'DC').length, 1);
  assert.equal(rows.filter(row => row.state_code === 'NJ').length, 19);
  assert.ok(rows.every(row => row.maps_approved === false && row.reported_units === null));
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
  assert.deepEqual(rows.filter(row => !['Wayne', 'Jefferson', 'Clarion'].includes(row.county) && row.state_code !== 'NJ'),
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
  assert.deepEqual(rows.filter(row => row.state_code !== 'NJ' && !['Jefferson', 'Clarion'].includes(row.county)), baseline.previous_reviewed_county_records);
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

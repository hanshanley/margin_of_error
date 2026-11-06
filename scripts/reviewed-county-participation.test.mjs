import assert from 'node:assert/strict';
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { parse } from 'csv-parse/sync';
import { loadReviewedCountyParticipation } from './reviewed-county-participation.mjs';

const reviews = JSON.parse(readFileSync('public/participation-source-reviews.json', 'utf8')).reviews;

test('loads all reviewed county participation without promoting map coverage', () => {
  const rows = loadReviewedCountyParticipation(reviews);
  assert.equal(rows.length, 14);
  assert.equal(rows.filter(row => row.state_code === 'PA').length, 13);
  assert.equal(rows.filter(row => row.state_code === 'DC').length, 1);
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

test('rejects missing or duplicated reviewed sources instead of silently shrinking coverage', () => {
  assert.throws(() => loadReviewedCountyParticipation(reviews.filter(row => row.id !== 'pennsylvania-berks-20261105-01')),
    /Missing or duplicated reviewed county source/);
  assert.throws(() => loadReviewedCountyParticipation([...reviews, reviews[0]]),
    /Missing or duplicated reviewed county source/);
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

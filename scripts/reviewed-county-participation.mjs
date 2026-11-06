import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parse } from 'csv-parse/sync';

const profiles = [
  ['pennsylvania-centre-20261106-01', 'ballots', 'registered_voters', 'registered_voter_rate_literal', 'PA', ['Centre']],
  ['pennsylvania-berks-20261105-01', 'ballots_cast', 'registered_voters', null, 'PA', ['Berks']],
  ['pennsylvania-northampton-20261105-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Northampton']],
  ['pennsylvania-lancaster-20261105-01', 'ballots', 'registrations', 'native_pdf_turnout_percent', 'PA', ['Lancaster']],
  ['pennsylvania-three-county-20261105-01', 'ballots_counted', 'registered_voters', 'native_printed_turnout', 'PA', ['Chester', 'Franklin', 'Lehigh']],
  ['pennsylvania-montgomery-20261105-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout_pct', 'PA', ['Montgomery']],
  ['pennsylvania-bucks-20261105-01', 'ballots_counted', 'registered_voters', 'native_printed_turnout', 'PA', ['Bucks']],
  ['pennsylvania-monroe-20261105-01', 'total_ballots_tabulated', 'eligible_registered_voters', 'native_printed_turnout_pct', 'PA', ['Monroe']],
  ['pennsylvania-fulton-20261106-01', 'accounted_ballots', 'registered_voters', 'native_printed_turnout', 'PA', ['Fulton']],
  ['pennsylvania-cumberland-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Cumberland']],
  ['pennsylvania-adams-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Adams']],
  ['pennsylvania-lebanon-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Lebanon']],
  ['pennsylvania-blair-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Blair']],
  ['pennsylvania-armstrong-20261106-01', 'reported_voters_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Armstrong']],
  ['pennsylvania-wayne-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Wayne']],
  ['dc-delegate-county-20261105-01', 'ballots_cast', 'registered_voters', null, 'DC', ['District of Columbia']],
];
const csv = path => parse(readFileSync(path, 'utf8'), { columns: true, bom: true, skip_empty_lines: true });

export function loadReviewedCountyParticipation(reviews) {
  const observations = [], seen = new Set();
  for (const [id, ballotField, denominatorField, printedField, code, names] of profiles) {
    const matches = reviews.filter(review => review.id === id);
    if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
    const review = matches[0], directory = resolve(review.data_directory);
    const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
    const rows = csv(resolve(directory, 'county-participation.csv'));
    if (rows.length !== names.length) throw new Error(`Incomplete reviewed county source: ${id}`);
    for (const native of rows) {
      const county = native.county ?? native.geography, identity = `${code}|${county}`;
      const unusableNativeZero = id === 'pennsylvania-lebanon-20261106-01';
      const nativeVotersCast = id === 'pennsylvania-armstrong-20261106-01';
      const nativeCountyHeader = id === 'pennsylvania-wayne-20261106-01';
      const ballots = Number(native[ballotField]);
      const denominator = unusableNativeZero ? null : Number(native[denominatorField]);
      const invalidDenominator = unusableNativeZero
        ? native[denominatorField] !== '' || native.native_registered_voters !== '0'
          || native.registered_turnout_percent !== '' || native.native_printed_turnout !== '0.00%'
        : !/^\d+$/.test(native[denominatorField]) || !Number.isSafeInteger(denominator)
          || denominator <= 0 || ballots > denominator;
      if (native.year !== '2026' || native.state_code !== code || !names.includes(county) || seen.has(identity)
        || !/^\d+$/.test(native[ballotField]) || !Number.isSafeInteger(ballots)
        || (unusableNativeZero && ballots <= 0) || invalidDenominator
        || (nativeVotersCast && (native.native_participation_measure_literal !== 'Voters Cast'
          || native.provisional_voters_cast !== ''
          || native.native_status_literal !== '2026 General Election Unofficial Results w/o PROV'))
        || (nativeCountyHeader && (native.native_participation_measure_literal !== 'Total Ballots Cast'
          || native.native_status_literal !== ''
          || native.native_parent_status_literal !== '2026 General Election Unofficial Results'
          || native.election_day_ballots !== '' || native.mail_ballots !== '' || native.provisional_ballots !== ''
          || ballots !== audit.county_participation.ballots_cast
          || denominator !== audit.county_participation.registered_voters)))
        throw new Error(`Invalid reviewed county participation: ${id} / ${county}`);
      seen.add(identity);
      const sourceAudit = audit.counties?.find(row => row.county === county) ?? audit;
      const printed = printedField ? native[printedField] : null;
      const printedPct = printed ? printed.endsWith('%') ? printed : `${printed}%` : null;
      const reporting = [
        ...(sourceAudit.native_reporting_qualifications ?? []),
        ...JSON.parse(native.counting_qualifications_json || '[]'),
        ...[native.mail_counting_status, native.in_person_counting_status,
          native.reporting_basis && `Native reporting basis: ${native.reporting_basis}`].filter(Boolean),
      ];
      for (const field of ['native_group_reporting_status_json', 'native_precinct_reporting_status_json']) {
        for (const row of JSON.parse(native[field] || '[]'))
          reporting.push(`${row.groupName.map(label => label.text).join(' / ')}: `
            + `${row.reportingStatusClientTextKey}; value ${row.value === null ? 'not supplied' : row.value}`);
      }
      const updates = ['source_update_literal', 'source_pdf_update_literal', 'source_json_exported_utc',
        'source_json_generated_utc', 'as_of_utc', 'publish_date_utc']
        .filter(field => native[field]).map(field => `${field}: ${native[field]}`);
      if (audit.native_status_and_update) updates.push(audit.native_status_and_update);
      if (audit.participation_record_edit_ms)
        updates.push(`Native participation edit (UTC milliseconds): ${audit.participation_record_edit_ms.join(', ')}`);
      let nativeSourceUpdates = [];
      if (id === 'pennsylvania-centre-20261106-01') {
        nativeSourceUpdates = csv(resolve(directory, 'native-source-updates.csv'));
      } else if (['pennsylvania-cumberland-20261106-01', 'pennsylvania-adams-20261106-01',
        'pennsylvania-lebanon-20261106-01', 'pennsylvania-blair-20261106-01',
        'pennsylvania-armstrong-20261106-01', 'pennsylvania-wayne-20261106-01'].includes(id)) {
        nativeSourceUpdates = [...new Map(csv(resolve(directory, 'native-source-pages.csv')).map(row =>
          [row.source_report ?? 'county_report', { source: row.source_report ?? 'county_report', native_update_literal: row.source_update_literal,
            declared_timezone: row.declared_timezone }])).values()];
      }
      updates.push(...nativeSourceUpdates.map(row =>
        `${row.source}: ${row.native_update_literal} (${row.declared_timezone || 'timezone not declared'})`));
      const quality = [
        'Reviewed local snapshot, not final certification, statewide coverage, eligible-population or demographic turnout.',
        'Source timestamps retain their native labels; unprovided timezones are not inferred. County mapping is not approved.',
      ];
      if (id === 'pennsylvania-berks-20261105-01') quality.push(...audit.qualifications.slice(2, 4));
      if (native.ballot_receipt_notice_literal || native.act88_mail_ballots_received_by_election_day_deadline)
        quality.push('Received mail ballots are a separate processing count, not the reported ballot total.');
      if (sourceAudit.native_csv_ballot_count_conflicts?.length)
        quality.push('Native contest-ballot zeroes conflict with positive unit ballots; those zeroes are not used as county ballots.');
      if (native.native_status_literal === '' && !native.native_parent_status_literal)
        quality.push('No native result-status literal was supplied; no native status is inferred.');
      if (nativeCountyHeader)
        quality.push('Result status comes from the declaring county page; the PDF supplies no separate status literal.');
      if (id === 'pennsylvania-montgomery-20261105-01') quality.push(audit.limitations[0], audit.limitations[2]);
      if (id === 'dc-delegate-county-20261105-01') quality.push(
        'Citywide county-equivalent participation, separate from the 435 voting House districts.',
        `${native.unresolved_ballot_accounting_difference} ballots remain unresolved in the separate delegate accounting; not filled or allocated.`,
        audit.limitations[1], audit.limitations[4]);
      observations.push({
        year: 2026, state_code: code, county_id: native.county_fips || `reviewed:${code}:${county}`,
        county, geography_level: native.geography_level || 'county', ballots, denominator,
        ...(nativeVotersCast ? { participation_measure_literal: native.native_participation_measure_literal } : {}),
        denominator_basis: 'native_registered_voters', reported_pct: denominator === null ? null : 100 * ballots / denominator,
        native_printed_pct: printedPct, source_status_literal: nativeCountyHeader
          ? native.native_parent_status_literal : native.native_status_literal ?? native.result_status ?? null,
        reported_units: null, total_units: null, source_rows: 0, maps_approved: false,
        review_id: id, native_record: native, native_source_updates: nativeSourceUpdates,
        source_update_label: updates.join('; ') || 'Not supplied',
        source_reporting_label: reporting.join('; ') || 'Counting completion not established by this participation table.',
        source_url: `${review.base_url}county-participation.csv`, complete_download_url: review.complete_download_url, quality,
      });
    }
  }
  return observations;
}

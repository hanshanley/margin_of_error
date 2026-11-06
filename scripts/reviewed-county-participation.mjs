import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
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
  ['pennsylvania-jefferson-20261106-01', 'reported_voters_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Jefferson']],
  ['dc-delegate-county-20261105-01', 'ballots_cast', 'registered_voters', null, 'DC', ['District of Columbia']],
];
/** @returns {Record<string, string>[]} */
const csv = path => parse(readFileSync(path, 'utf8'), { columns: true, bom: true, skip_empty_lines: true });

function loadNewJerseyParticipation(reviews) {
  const id = 'new-jersey-periodic-participation-20261106-02';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  const required = {
    'county-participation.csv': 'a9e1e664ee56675219dbe69355947121b9b6e08fc81b355e899278fbddce172d',
    'native-source-pages.csv': '36699e8025c42379ad5e7d1297777609a75dd593d88b8a63cb0bda534e22a7fe',
    'native-counting-qualifications.csv': '342cb5983e5fbf52f3f6f9aa3d5bc2018a2ade518d8ca230bc42eb7ce849e2ce',
    'audit.json': 'bf47bfe6b959e57123eec0ab0342b235354ac56e91d63e7b4c4dc0897ae48bd0',
  };
  for (const [file, digest] of Object.entries(required)) {
    if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv'));
  const pages = csv(resolve(directory, 'native-source-pages.csv'));
  const notes = csv(resolve(directory, 'native-counting-qualifications.csv'));
  const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
  if (rows.length !== 21 || audit.usable_counties.length !== 19
    || audit.withheld_counties.map(row => row.county).join('|') !== 'Essex|Hudson')
    throw new Error(`Incomplete reviewed county source: ${id}`);
  return rows.filter(native => audit.usable_counties.includes(native.county)).map(native => {
    const ballots = Number(native.reported_participation_subtotal);
    const denominator = native.registered_voters === '' ? null : Number(native.registered_voters);
    const nativeSummary = native.county === 'Cape May';
    const modes = ['early_voting_votes_cast', 'election_day_votes_cast', 'mail_ballots_tallied'];
    if (native.year !== '2026' || native.state_code !== 'NJ' || native.withheld_reason !== ''
      || !Number.isSafeInteger(ballots) || ballots <= 0
      || modes.some(field => !/^\d+$/.test(native[field]))
      || modes.reduce((total, field) => total + Number(native[field]), 0) !== ballots
      || (nativeSummary ? denominator !== 76899 || native.source_page !== '2'
        || native.registration_source_page !== '2' || native.periodic_source_page !== '1'
        || native.native_participation_measure_literal !== 'Ballots Cast - Total'
        : denominator !== null || native.native_participation_measure_literal !== ''))
      throw new Error(`Invalid reviewed county participation: ${id} / ${native.county}`);
    const nativeSourceUpdates = pages.filter(row => row.county === native.county).map(row => ({
      source: `${row.source_role} page ${row.source_page}`, native_update_literal: row.source_update_literal,
      other_update_literals: JSON.parse(row.other_update_literals_json), declared_timezone: row.declared_timezone,
    }));
    return {
      year: 2026, state_code: 'NJ', county_id: `reviewed:NJ:${native.county}`, county: native.county,
      geography_level: 'county', ballots, denominator, denominator_basis: 'native_registered_voters',
      participation_measure_kind: nativeSummary ? 'native_ballot_total' : 'derived_reported_mode_subtotal',
      ...(nativeSummary ? { participation_measure_literal: native.native_participation_measure_literal } : {
        participation_measure_label: 'Derived EV + ED + mail-tallied subtotal; no provisional-issued counts added',
      }),
      reported_pct: denominator === null ? null : 100 * ballots / denominator,
      native_printed_pct: native.native_printed_turnout || null, source_status_literal: native.native_status_literal,
      reported_units: null, total_units: null, source_rows: 0, maps_approved: false,
      review_id: id, native_record: native, native_source_updates: nativeSourceUpdates,
      source_update_label: nativeSourceUpdates.map(row =>
        `${row.source}: ${row.native_update_literal || 'not supplied'}`
        + `${row.other_update_literals.length ? `; other native timestamps: ${row.other_update_literals.join('; ')}` : ''}`
        + ` (${row.declared_timezone || 'timezone not declared'})`).join('; '),
      source_reporting_label: [
        `Periodic participation modes: PDF page ${native.periodic_source_page}.`,
        ...(nativeSummary ? ['Native ballot total and registrations: attached summary, PDF page 2.'] : []),
        ...notes.filter(row => row.county === native.county).map(row => `Native note (page ${row.source_page}): ${row.literal}`),
        ...JSON.parse(native.counting_qualifications_json),
      ].join('; '),
      source_url: `${review.base_url}county-participation.csv`,
      complete_download_url: review.complete_download_url,
      quality: [
        'Reviewed unofficial participation snapshot, not certification, completed statewide counting or demographic turnout.',
        'Issued, received and pending ballots are separate processing measures, not additions to the counted modes.',
        nativeSummary ? 'Native Ballots Cast - Total and registrations are separately verified on PDF page 2.'
          : 'Derived reported mode subtotal, not a native all-mode ballot total or a unique-voter estimate. Registrations and turnout rate are not supplied.',
        'Essex and Hudson remain withheld in the complete 21-county query. County mapping is not approved; undeclared timezones are not inferred.',
      ],
    };
  });
}

export function loadReviewedCountyParticipation(reviews) {
  const observations = [], seen = new Set();
  for (const [id, ballotField, denominatorField, printedField, code, names] of profiles) {
    const matches = reviews.filter(review => review.id === id);
    if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
    const review = matches[0], directory = resolve(review.data_directory);
    if (id === 'pennsylvania-jefferson-20261106-01') {
      for (const [file, digest] of Object.entries({
        'county-participation.csv': 'd9674bfaa0beaf1e2e0b1174a444e6f408dc4e95eb9e1544119f825f8b7cbb2e',
        'native-source-pages.csv': 'd010adc9bcf8508d761dbda77d99ce89431f07714e9d9d02032756a4a2dfe44f',
        'audit.json': '9eedaeba9c068df9e3258ca6bb3e5b2f553f3b956c531f2aa51eaf045d66d375',
      })) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
    const rows = csv(resolve(directory, 'county-participation.csv'));
    if (rows.length !== names.length) throw new Error(`Incomplete reviewed county source: ${id}`);
    for (const native of rows) {
      const county = native.county ?? native.geography, identity = `${code}|${county}`;
      const unusableNativeZero = id === 'pennsylvania-lebanon-20261106-01';
      const excludesProvisionals = id === 'pennsylvania-armstrong-20261106-01';
      const nativeVotersCast = excludesProvisionals || id === 'pennsylvania-jefferson-20261106-01';
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
        || (excludesProvisionals && (native.native_participation_measure_literal !== 'Voters Cast'
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
        'pennsylvania-armstrong-20261106-01', 'pennsylvania-wayne-20261106-01',
        'pennsylvania-jefferson-20261106-01'].includes(id)) {
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
  return [...observations, ...loadNewJerseyParticipation(reviews)];
}

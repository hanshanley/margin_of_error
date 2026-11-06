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
  ['pennsylvania-clarion-20261106-01', 'reported_voters_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Clarion']],
  ['pennsylvania-cameron-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Cameron']],
  ['pennsylvania-carbon-20261106-01', 'reported_voters_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Carbon']],
  ['pennsylvania-elk-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Elk']],
  ['pennsylvania-forest-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Forest']],
  ['pennsylvania-potter-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Potter']],
  ['pennsylvania-mifflin-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Mifflin']],
  ['pennsylvania-perry-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Perry']],
  ['pennsylvania-juniata-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Juniata']],
  ['pennsylvania-mercer-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Mercer']],
  ['pennsylvania-montour-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Montour']],
  ['pennsylvania-columbia-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Columbia']],
  ['pennsylvania-greene-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Greene']],
  ['pennsylvania-lycoming-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout_pct', 'PA', ['Lycoming']],
  ['dc-delegate-county-20261105-01', 'ballots_cast', 'registered_voters', null, 'DC', ['District of Columbia']],
];
/** @returns {Record<string, string>[]} */
const csv = path => parse(readFileSync(path, 'utf8'), { columns: true, bom: true, skip_empty_lines: true });

export function loadReviewedMinnesotaParticipation(reviews) {
  const id = 'minnesota-bulk-participation-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  for (const [file, digest] of Object.entries({
    'county-participation.csv': '0815bde66ec0127b48d7d6b299ca4c0a7ea55773782088269cb82d699e848426',
    'audit.json': '969bb0d143856387675266608644d614aae036c6018d0ce75a81ba3e0d975f6c',
    'sources.json': '88280d24ab113f82c9de81622c26fdbf6ad6b209c2f1d1d6f51a75ddcc773308',
  })) {
    if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
  }
  const nativeRows = csv(resolve(directory, 'county-participation.csv'));
  const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
  if (nativeRows.length !== 87 || audit.complete_native_rows.pctstats !== 4105
    || audit.complete_native_rows.counties !== 87 || audit.reported_statistics !== 3671
    || audit.unreported_statistics !== 434 || audit.maps_approved !== false || audit.rates_approved !== false
    || new Set(nativeRows.map(row => row.native_county_id)).size !== 87
    || new Set(nativeRows.map(row => row.county_name)).size !== 87
    || nativeRows.filter(row => row.all_statistics_reported === 'true').length !== 75
    || nativeRows.filter(row => row.eligible_for_registration_fraction_review === 'true').length !== 64
    || nativeRows.reduce((total, row) => total + Number(row.reported_total_number_voted_subtotal), 0) !== 2354606)
    throw new Error(`Incomplete reviewed county source: ${id}`);
  return nativeRows.map(native => {
    const complete = native.all_statistics_reported === 'true';
    const eligible = native.eligible_for_registration_fraction_review === 'true';
    const ballots = complete ? Number(native.complete_total_number_voted) : null;
    const denominator = complete ? Number(native.derived_complete_7am_plus_election_day_registrations) : null;
    if (native.native_numerator_label !== 'Total Number Voted' || native.native_status !== 'Unofficial Results'
      || native.native_fips !== '' || native.native_update_clock !== '' || native.native_timezone !== ''
      || native.maps_approved !== 'false' || native.rates_approved !== 'false'
      || !['true', 'false'].includes(native.all_statistics_reported)
      || !['true', 'false'].includes(native.eligible_for_registration_fraction_review)
      || Number(native.reported_statistics) + Number(native.missing_statistics) !== Number(native.reference_precincts)
      || complete !== (Number(native.missing_statistics) === 0)
      || (complete ? !Number.isSafeInteger(ballots) || ballots < 0
        || !Number.isSafeInteger(denominator) || denominator < 0
        || denominator !== Number(native.complete_registered_7am) + Number(native.complete_registered_election_day)
        : native.complete_total_number_voted !== '' || native.complete_registered_7am !== ''
          || native.complete_registered_election_day !== ''
          || native.derived_complete_7am_plus_election_day_registrations !== '' || eligible)
      || (eligible && (denominator <= 0 || ballots > denominator
        || Number(native.reported_precinct_electorate_excesses) !== 0
        || Number(native.reported_precinct_component_conflicts) !== 0)))
      throw new Error(`Invalid reviewed county participation: ${id} / ${native.county_name}`);
    return {
      year: 2026, state_code: 'MN', county_id: `reviewed:MN:${native.native_county_id}`,
      county: native.county_name, geography_level: 'county', ballots, denominator,
      participation_measure_kind: 'native_voting_statistics_total',
      participation_measure_literal: 'Total Number Voted',
      participation_measure_label: 'Native Total Number Voted (reported participation)',
      denominator_basis: 'native_registered_voters',
      reported_pct: eligible ? 100 * ballots / denominator : null,
      native_printed_pct: null, source_status_literal: native.native_status,
      reported_units: Number(native.reported_statistics), total_units: Number(native.reference_precincts),
      source_rows: Number(native.reference_precincts), maps_approved: false, review_id: id,
      native_record: native, native_source_updates: [],
      source_update_label: 'Native update clock and timezone not supplied; fetch receipts are not report updates.',
      source_reporting_label: `${native.reported_statistics}/${native.reference_precincts} precincts have native statistics; `
        + `${native.missing_statistics} missing. Native reported Total Number Voted subtotal `
        + `${Number(native.reported_total_number_voted_subtotal).toLocaleString('en-US')}. `
        + (complete ? 'Complete native statistics, not completed ballot counting or certification. '
          : 'County participation and complete registration totals are not supplied; the partial subtotal is not the county total. ')
        + `${native.reported_precinct_component_conflicts} native component conflicts; `
        + `${native.reported_precinct_electorate_excesses} precinct electorate excesses. `
        + 'Roster signatures and three native absentee fields are not inferred ballot modes. '
        + 'Candidate and question votes, parties and estimated question blanks remain separate.',
      source_url: `${review.base_url}county-participation.csv`,
      complete_download_url: review.complete_download_url,
      quality: [
        'Only reporting-flag1 statistics supply actual participation, including true zero. Missing statistics are not zero and governor votes are never a proxy.',
        'The complete electorate is the explicitly derived sum of native 7AM registrations and Election Day registrations, not CVAP, VAP, VEP, CPS or demographic turnout.',
        'Native component conflicts and electorate excesses preserve the complete participation count and supplied electorate but withhold the registration fraction.',
        'Twelve counties remain partial; the 2,354,606 reported-voter subtotal is not a complete statewide participation count.',
        'Native county IDs are not FIPS. No update clock, timezone, counting completion, certification or ballot-mode decomposition is inferred.',
      ],
    };
  });
}

function loadCaliforniaParticipation(reviews) {
  const id = 'california-bulk-participation-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  const required = {
    'county-participation.csv': '0ddaf2f0c122096d0f9eb369aee7fff653c2b32f8019d5048974ad1d6a80c0e1',
    'statewide-participation.csv': '82301cbd7e6ef4e3670403539c728f57a62c2b3173776b4007c024ed4d3edd97',
    'audit.json': 'e1f005b3a3e0871ce8eced5e9f3c0ef1f4ea8b7e79a1042cef3565b7a25de9ec',
  };
  for (const [file, digest] of Object.entries(required)) {
    if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
  }
  const counties = csv(resolve(directory, 'county-participation.csv'));
  const statewide = csv(resolve(directory, 'statewide-participation.csv'));
  const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
  if (counties.length !== 58 || statewide.length !== 1 || audit.county_records !== 58
    || audit.separate_statewide_records !== 1 || new Set(counties.map(row => row.county)).size !== 58
    || new Set(counties.map(row => row.native_county_code)).size !== 58
    || counties.some(row => !Array.from({ length: 58 }, (_, index) => String(index + 1)).includes(row.native_county_code))
    || statewide[0].native_county_code !== '59' || statewide[0].geography_level !== 'statewide'
    || ['reported_participation', 'registered_voters', 'precincts_reporting', 'precincts_total'].some(field =>
      counties.reduce((total, row) => total + Number(row[field]), 0) !== Number(statewide[0][field])))
    throw new Error(`Incomplete reviewed county source: ${id}`);
  return [...counties, ...statewide].map(native => {
    const ballots = Number(native.reported_participation), denominator = Number(native.registered_voters);
    if (native.year !== '2026' || native.election_date !== '2026-11-03' || native.state_code !== 'CA'
      || !Number.isSafeInteger(ballots) || ballots <= 0
      || !Number.isSafeInteger(denominator) || denominator < ballots
      || native.native_participation_measure_literal !== 'voterTurnout'
      || native.native_denominator_measure_literal !== 'totalRegisteredVoters'
      || native.county_fips !== '' || native.maps_approved !== 'false' || native.counting_complete !== 'false'
      || native.declared_timezone !== ''
      || Math.abs(100 * ballots / denominator - Number(native.native_printed_turnout)) > 0.050000000001
      || !['U|U', 'SF|F'].includes(`${native.native_report_type}|${native.native_report_type_code}`))
      throw new Error(`Invalid reviewed county participation: ${id} / ${native.county}`);
    return {
      year: 2026, state_code: 'CA', county_id: `reviewed:CA:${native.native_county_code}`,
      county: native.county, geography_level: native.geography_level, ballots, denominator,
      participation_measure_kind: 'native_voter_turnout',
      participation_measure_literal: native.native_participation_measure_literal,
      participation_measure_label: 'Native voterTurnout (reported participation)',
      denominator_basis: 'native_registered_voters', reported_pct: 100 * ballots / denominator,
      native_printed_pct: `${native.native_printed_turnout}%`,
      source_status_literal: `reportType: ${native.native_report_type}; reportTypeCode: ${native.native_report_type_code}`,
      reported_units: Number(native.precincts_reporting), total_units: Number(native.precincts_total),
      source_rows: 1, maps_approved: false, review_id: id, native_record: native,
      native_source_updates: [
        { source: 'firstReportTimestamp', native_update_literal: native.native_first_report_timestamp, declared_timezone: '' },
        { source: 'lastReportTimestamp', native_update_literal: native.native_last_report_timestamp, declared_timezone: '' },
        { source: 'timestamp', native_update_literal: native.native_timestamp_literal, declared_timezone: '' },
      ],
      source_update_label: `${native.native_timestamp_literal}; firstReportTimestamp: ${native.native_first_report_timestamp}; `
        + `lastReportTimestamp: ${native.native_last_report_timestamp} (timezone not declared)`,
      source_reporting_label: `${native.precincts_reporting}/${native.precincts_total} precincts reporting; `
        + `${native.native_reporting_percent}% native reporting. This does not establish completed counting or certification. `
        + 'Voting-mode, demographic, blank, overvote, undervote and provisional totals are not supplied.',
      source_url: `${review.base_url}${native.geography_level === 'statewide' ? 'statewide' : 'county'}-participation.csv`,
      complete_download_url: review.complete_download_url,
      quality: [
        'Native voterTurnout / totalRegisteredVoters, not candidate sums, a proved all-mode ballot count or independently deduplicated unique voters.',
        'Registered-voter fraction, not CVAP, VAP, VEP, CPS or demographic turnout. No counting completion or certification inferred from U, F, SF or reporting completeness.',
        'Native county codes are not FIPS; source mapping remains unapproved. Native clocks retain their missing timezone.',
      ],
    };
  });
}

export function loadReviewedStatewideParticipation(reviews) {
  const california = loadCaliforniaParticipation(reviews).filter(row => row.geography_level === 'statewide').map(row => ({
    ...row, state: 'California', mode: 'official', validated_pct: row.reported_pct,
    source_date: row.source_update_label, status: 'reviewed_unofficial_snapshot',
    observation_type: row.participation_measure_label,
  }));
  return [...california, loadGeorgiaParticipation(reviews).statewide];
}

function loadGeorgiaParticipation(reviews) {
  const id = 'georgia-bulk-participation-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  for (const [file, digest] of Object.entries({
    'county-participation.csv': '31176798e6ed604c1f84de6f00212e83539bf0643adc33f4843b77590e15dbb1',
    'statewide-participation.csv': 'b882f7f97f0df02fc9b94cbbb18c60416cf3331fa9eb3f34c6b484514a368067',
    'audit.json': 'fa75a75d5751cf5f697df0da3f1e7c29446e69b9e7910e63e9ebb54220db91fa',
  })) {
    if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
  }
  const nativeRows = csv(resolve(directory, 'county-participation.csv'));
  const states = csv(resolve(directory, 'statewide-participation.csv'));
  const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
  if (nativeRows.length !== 159 || states.length !== 1 || audit.native_counties !== 159
    || audit.usable_native_county_fractions !== 157 || audit.missing_county_fractions !== 2
    || new Set(nativeRows.map(row => row.county)).size !== 159
    || new Set(nativeRows.map(row => row.native_uuid.toLowerCase())).size !== 159
    || new Set(nativeRows.map(row => row.native_media_county_id)).size !== 159
    || nativeRows.reduce((total, row) => total + Number(row.native_ballots_cast), 0) !== Number(states[0].ballots)
    || nativeRows.reduce((total, row) => total + Number(row.native_total_voters), 0) !== Number(states[0].voters)
    || states[0].ballots !== '4210155' || states[0].voters !== '7516484'
    || states[0].original_conflicting_api_root_ballots !== '0'
    || states[0].missing_county_registration_denominators !== '2'
    || states[0].rate_comparable_to_cvap !== 'False')
    throw new Error(`Incomplete reviewed county source: ${id}`);
  const quality = [
    'Native ballotsCast separately agrees with the rendered Voters page, not a candidate sum or mail receipt count.',
    'Native Voters/totalVoters is a registration denominator of unspecified active/inactive scope, not CVAP, VAP, VEP, CPS or demographic turnout.',
    'Screven and Jeff Davis have native zero denominators and blank rates, not zero turnout. No active/inactive decomposition is inferred.',
    'Native media county IDs are not FIPS. Reporting statuses and official flags do not independently establish completed counting or certification.',
    'Candidate, party and voting-mode queries remain separate; 372 missing candidate-mode cells are not zero or inferred participation modes.',
  ];
  const counties = nativeRows.map(native => {
    const ballots = Number(native.native_ballots_cast), voters = Number(native.native_total_voters);
    const denominator = voters > 0 ? voters : null;
    if (native.year !== '2026' || native.state_code !== 'GA' || !Number.isSafeInteger(ballots) || ballots <= 0
      || !Number.isSafeInteger(voters) || voters < 0 || Number(native.native_registration_total) !== voters
      || native.source_fips !== '' || native.maps_approved !== 'False' || native.counting_complete !== 'False'
      || !['True', 'False'].includes(native.native_is_official_results)
      || (denominator === null ? native.native_fraction !== '' || native.native_printed_turnout !== ''
        || native.usable_native_fraction !== 'False'
        : ballots > denominator || native.usable_native_fraction !== 'True'
          || native.native_printed_turnout !== `${(100 * ballots / denominator).toFixed(2)}%`
          || Math.abs(100 * Number(native.native_fraction) - 100 * ballots / denominator) > 0.005000001))
      throw new Error(`Invalid reviewed county participation: ${id} / ${native.county}`);
    const updates = ['native_as_of', 'native_last_updated', 'native_publish_date'].map(field => ({
      source: field, native_update_literal: native[field], declared_timezone: native[field].endsWith('Z') ? 'UTC' : '',
    }));
    return {
      year: 2026, state_code: 'GA', county_id: `reviewed:GA:${native.native_uuid.toLowerCase()}`,
      county: native.county, geography_level: 'county', ballots, denominator,
      participation_measure_kind: 'native_ballot_total', participation_measure_literal: 'ballotsCast',
      participation_measure_label: 'Native ballotsCast (reported ballots)',
      denominator_basis: 'native_registered_voters', reported_pct: denominator === null ? null : 100 * ballots / denominator,
      native_printed_pct: native.native_printed_turnout || null,
      source_status_literal: `Native isOfficialResults=${native.native_is_official_results === 'True'}`,
      reported_units: null, total_units: null, source_rows: 1, maps_approved: false,
      review_id: id, native_record: native, native_source_updates: updates,
      source_update_label: updates.map(row => `${row.source}: ${row.native_update_literal || 'not supplied'}`).join('; '),
      source_reporting_label: `Native county reporting statuses: ${native.native_reporting_json}. `
        + 'Reporting completeness is not completed counting or certification. Native ballots include reported returns, '
        + 'not inferred future ballot modes or a unique-voter estimate. Candidate votes and missing mode cells remain separate.',
      source_url: `${review.base_url}county-participation.csv`, complete_download_url: review.complete_download_url, quality,
    };
  });
  const native = states[0];
  return { counties, statewide: {
    year: 2026, state_code: 'GA', state: 'Georgia', geography_level: 'statewide', mode: 'official', review_id: id,
    ballots: Number(native.ballots), denominator: Number(native.voters), denominator_basis: 'native_registered_voters',
    reported_pct: null, validated_pct: null, native_printed_pct: `${native.printed_turnout}%`,
    participation_measure_kind: 'native_ballot_total', participation_measure_literal: 'Ballots Cast',
    participation_measure_label: 'Native Ballots Cast (reported ballots)', observation_type: 'Native Ballots Cast',
    source_status_literal: 'Native isOfficialResults=false (unofficial)',
    source_date: native.source_update_literal, source_update_label: `${native.source_update_literal} (timezone not declared)`,
    status: 'reviewed_unofficial_snapshot', native_record: native,
    source_url: `${review.base_url}statewide-participation.csv`, complete_download_url: review.complete_download_url,
    quality: [...quality, 'Printed statewide 56.01% is retained, not an approved analysis rate: two county registration denominators are missing.',
      'Original API root ballotsCast=0 remains a conflicting field; the rendered Voters header separately reports 4,210,155.'],
  } };
}

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

function loadLawrenceParticipation(reviews) {
  const id = 'pennsylvania-lawrence-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  for (const [file, digest] of Object.entries({
    'county-participation.csv': 'df9fea970547572e67e96351e77d256318346d310b7b4c92f8c9c0a148a562bd',
    'native-source-pages.csv': 'a75f157fb0c1151be5d47807f070fb1c95845eb8941bc179ff162027731e2b86',
    'native-reporting-statements.csv': '2c3f8cb21ef71dde845ec8c27a5b952cec656270193bc100253544e4d923198d',
    'audit.json': '13aa2d243300c869fcb09b2ab35c91c10796f03e16d3b4d6004c1a90afeb0016',
  })) {
    if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv'));
  const pages = csv(resolve(directory, 'native-source-pages.csv'));
  const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
  if (rows.length !== 1 || pages.length !== 214 || audit.maps_approved !== false
    || audit.table_rows['native-unit-participation.csv'] !== 74)
    throw new Error(`Incomplete reviewed county source: ${id}`);
  const native = rows[0], ballots = Number(native.ballots_cast), denominator = Number(native.registered_voters);
  if (native.year !== '2026' || native.state_code !== 'PA' || native.county !== 'Lawrence'
    || native.source_report !== 'county' || native.native_status_literal !== 'UNOFFICIAL RESULTS'
    || native.source_update_literal !== '11/03/2026 9:27 PM' || native.declared_timezone !== ''
    || ballots !== 31401 || denominator !== 57470 || native.blank_ballots !== '2'
    || native.election_day_ballots !== '25293' || native.mail_ballots !== '6108'
    || native.provisional_ballots !== '0' || native.native_printed_turnout !== '54.64%'
    || Number(native.registered_turnout_percent) !== 100 * ballots / denominator)
    throw new Error(`Invalid reviewed county participation: ${id}`);
  const updates = [...new Map(pages.map(row => [row.source_report, {
    source: row.source_report, native_update_literal: row.source_update_literal,
    declared_timezone: row.declared_timezone,
  }])).values()];
  return [{
    year: 2026, state_code: 'PA', county_id: 'reviewed:PA:Lawrence', county: 'Lawrence',
    geography_level: 'county', ballots, denominator, denominator_basis: 'native_registered_voters',
    participation_measure_literal: 'Ballots Cast - Total', reported_pct: 100 * ballots / denominator,
    native_printed_pct: native.native_printed_turnout, source_status_literal: native.native_status_literal,
    reported_units: 74, total_units: 74, source_rows: 1, maps_approved: false, review_id: id,
    native_record: native, native_source_updates: updates,
    source_update_label: updates.map(row =>
      `${row.source}: ${row.native_update_literal} (timezone not declared)`).join('; '),
    source_reporting_label: audit.qualifications.join('; '), quality: audit.qualifications,
    source_url: `${review.base_url}county-participation.csv`, complete_download_url: review.complete_download_url,
  }];
}

function loadHuntingdonParticipation(reviews) {
  const id = 'pennsylvania-huntingdon-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  for (const [file, digest] of Object.entries({
    'county-participation.csv': '08f15f3fbde5886c9a74c4ce5a7c06e38531449fe7e4fad42f2825c824ee00d0',
    'native-source-pages.csv': '82df1da987de8a3316208d9ce0d68c2a1b37ec1667f3bcd188e2ca7053c583e4',
    'native-reporting-statements.csv': '31c5449c825652438725e538bd3bddca0a4a43649350463dbc5a6b15388f6f42',
    'audit.json': 'bcc126c0182b210e7b6b16d234001dae781bcda8b77c15bb9c5660764b0ecfec',
  })) {
    if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv'));
  const pages = csv(resolve(directory, 'native-source-pages.csv'));
  const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
  if (rows.length !== 1 || pages.length !== 2 || audit.maps_approved !== false
    || audit.table_rows['native-candidate-results.csv'] !== 16)
    throw new Error(`Incomplete reviewed county source: ${id}`);
  const native = rows[0], ballots = Number(native.ballots_cast), denominator = Number(native.registered_voters);
  if (native.election_date !== '2026-11-03' || native.state !== 'Pennsylvania' || native.county !== 'Huntingdon'
    || native.source_fips !== '' || native.native_status_literal !== 'UNOFFICIAL RESULTS'
    || native.source_update_literal !== '11/03/2026 9:56 PM' || native.declared_timezone !== ''
    || ballots !== 16024 || denominator !== 27917 || native.blank_ballots !== '0'
    || native.election_day_ballots !== '13855' || native.mail_ballots !== '2169'
    || native.provisional_ballots !== '0' || native.native_printed_turnout !== '57.40%'
    || Number(native.registered_turnout_percent) !== 100 * ballots / denominator)
    throw new Error(`Invalid reviewed county participation: ${id}`);
  return [{
    year: 2026, state_code: 'PA', county_id: 'reviewed:PA:Huntingdon', county: 'Huntingdon',
    geography_level: 'county', ballots, denominator, denominator_basis: 'native_registered_voters',
    participation_measure_literal: native.native_participation_measure_literal,
    reported_pct: 100 * ballots / denominator, native_printed_pct: native.native_printed_turnout,
    source_status_literal: native.native_status_literal, reported_units: 58, total_units: 58,
    source_rows: 1, maps_approved: false, review_id: id, native_record: native,
    native_source_updates: [{ source: 'county', native_update_literal: native.source_update_literal,
      declared_timezone: native.declared_timezone }],
    source_update_label: `${native.source_update_literal} (timezone not declared)`,
    source_reporting_label: audit.qualifications.join('; '), quality: audit.qualifications,
    source_url: `${review.base_url}county-participation.csv`, complete_download_url: review.complete_download_url,
  }];
}

export function loadReviewedAdditionalPennsylvaniaParticipation(reviews) {
  const id = 'pennsylvania-three-additional-summaries-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  const manifestBody = readFileSync(resolve(directory, 'manifest.json'));
  if (createHash('sha256').update(manifestBody).digest('hex')
    !== 'b2359e837f7322b93f4faf86fef021d4b36a25b44a14d65663fccf655f2143c6')
    throw new Error(`Invalid reviewed county participation: ${id} / manifest.json`);
  for (const file of JSON.parse(manifestBody.toString())) {
    const body = readFileSync(resolve(directory, file.file));
    if (body.length !== file.bytes || createHash('sha256').update(body).digest('hex') !== file.sha256)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file.file}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv'));
  const reporting = csv(resolve(directory, 'native-reporting-statistics.csv'));
  const facts = JSON.parse(readFileSync(resolve(directory, 'native-facts.json'), 'utf8'));
  const expected = { Indiana: [28095, 49255], Lackawanna: [87067, 151015], Schuylkill: [48402, 92875] };
  if (rows.length !== 3 || new Set(rows.map(row => row.county)).size !== 3)
    throw new Error(`Incomplete reviewed county source: ${id}`);
  return rows.map(native => {
    const ballots = Number(native.ballots_cast), denominator = Number(native.registered_voters);
    if (native.election_date !== '2026-11-03' || native.state_code !== 'PA'
      || native.native_measure_literal !== 'Ballots Cast - Total' || native.source_fips !== ''
      || native.native_status_literal !== 'UNOFFICIAL RESULTS' || native.declared_timezone !== ''
      || native.maps_approved !== 'False' || native.complete_counting !== 'False'
      || ballots !== expected[native.county]?.[0] || denominator !== expected[native.county]?.[1]
      || Math.abs(100 * ballots / denominator - Number(native.native_printed_turnout.slice(0, -1))) > .005001)
      throw new Error(`Invalid reviewed county participation: ${id} / ${native.county}`);
    const county = facts.counties[native.county];
    const updates = ['summary', 'statement'].map(role => ({
      source: role,
      native_update_literal: role === 'summary' ? native.source_update_literal
        : county.unit_participation[0].source_update_literal,
      declared_timezone: '',
    }));
    const nativeReporting = reporting.filter(row => row.county === native.county);
    const reported = nativeReporting.find(row => row.label_literal === 'Election Day Precincts Reporting');
    const quality = [
      'Native Ballots Cast - Total and the same county report registrations; candidate selections and blank ballots are not added to the ballot total.',
      'Native registered-voter fraction, not CVAP, VAP, VEP, CPS, demographic turnout or a district/mode electorate.',
      'UNOFFICIAL RESULTS and reporting completeness do not establish completed counting or certification. Native clocks have no declared timezone; native FIPS is missing.',
      'The complete download contains every county-summary numerical row plus all 357 local participation headers, not all statement candidate rows or new precinct geography.',
      ...(native.county === 'Indiana' ? [
        'Election Day, mail and provisional breakdowns and native overvotes/undervotes are absent, not zero. Congressional reporting denominators sum to 70, not the county 69; no disjoint geographic partition is inferred.',
      ] : native.county === 'Lackawanna' ? [
        'Contradictory native reporting-mode counters are retained, not repaired or summed. Carbondale and Scott question electorates are restricted; county registrations are not their denominators.',
      ] : [
        'Native contest totals, overvotes and undervotes are absent, not zero; candidate sums are not ballots. Native 0/125 complete and 125/125 partial remain unchanged.',
        'Unit 137 Pine Grove Township 1st prints 55.42% against 802 ballots / 1447 registrations; the complete query flags rather than corrects this rounding conflict.',
      ]),
    ];
    return {
      year: 2026, state_code: 'PA', county_id: `reviewed:PA:${native.county}`, county: native.county,
      geography_level: 'county', ballots, denominator, denominator_basis: 'native_registered_voters',
      participation_measure_literal: native.native_measure_literal, reported_pct: 100 * ballots / denominator,
      native_printed_pct: native.native_printed_turnout, source_status_literal: native.native_status_literal,
      reported_units: Number(reported.reported), total_units: Number(reported.total), source_rows: 1,
      maps_approved: false, review_id: id, native_record: native, native_source_updates: updates,
      source_update_label: updates.map(row =>
        `${row.source}: ${row.native_update_literal} (timezone not declared)`).join('; '),
      source_reporting_label: nativeReporting.map(row =>
        `${row.label_literal}: ${row.reported}/${row.total}`).join('; ') + '; ' + quality.join(' '),
      quality, source_url: `${review.base_url}county-participation.csv`,
      complete_download_url: review.complete_download_url,
    };
  });
}

export function loadReviewedSomersetParticipation(reviews) {
  const id = 'pennsylvania-somerset-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  const manifestBody = readFileSync(resolve(directory, 'manifest.json'));
  if (createHash('sha256').update(manifestBody).digest('hex')
    !== 'f46ccaaaab2ea178ab8031c64cb1e8d88de21caa945f15bfceffb33ad3b5f08a')
    throw new Error(`Invalid reviewed county participation: ${id} / manifest.json`);
  for (const file of JSON.parse(manifestBody.toString())) {
    const body = readFileSync(resolve(directory, file.file));
    if (body.length !== file.bytes || createHash('sha256').update(body).digest('hex') !== file.sha256)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file.file}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv'));
  const reporting = csv(resolve(directory, 'native-reporting-statistics.csv'));
  const facts = JSON.parse(readFileSync(resolve(directory, 'native-facts.json'), 'utf8'));
  const native = rows[0], ballots = Number(native?.ballots_cast), denominator = Number(native?.registered_voters);
  if (rows.length !== 1 || native.county !== 'Somerset' || native.state_code !== 'PA'
    || native.election_date !== '2026-11-03' || native.native_measure_literal !== 'Ballots Cast - Total'
    || native.source_fips !== '' || native.native_status_literal !== 'UNOFFICIAL RESULTS'
    || native.declared_timezone !== '' || native.maps_approved !== 'False' || native.complete_counting !== 'False'
    || ballots !== 27019 || denominator !== 48578 || native.blank_ballots_already_included !== '3'
    || native.native_printed_turnout !== '55.62%'
    || Number(native.calculated_registered_fraction) !== ballots / denominator)
    throw new Error(`Invalid reviewed county participation: ${id}`);
  const updates = ['summary', 'statement', 'statistics'].map(role => ({
    source: role, native_update_literal: facts.reports[role][0].source_update_literal, declared_timezone: '',
  }));
  const quality = [
    'Native Ballots Cast - Total and the same county report registrations; candidate selections and blank ballots are not added to the ballot total.',
    'Native registered-voter fraction, not CVAP, VAP, VEP, CPS, demographic turnout or a district/mode electorate.',
    'UNOFFICIAL RESULTS and reporting completeness do not establish completed counting or certification. Native clocks have no declared timezone; native FIPS is missing.',
    'All 73 numerical report pages, 67 native units and six county contests reconcile in every supplied mode; complete candidate and literal-party results remain separate from participation.',
    '27,019 ballots include 23,233 Election Day, 3,786 Absentee/Mail-In and explicit zero Provisional; three blank ballots are already included.',
    'Native 0/67 complete and 67/67 partial remain unchanged; absentee reporting prints 65/67 with 67 in its mail column. These counters are not repaired or summed.',
    'Eight statistics percentages omit trailing zeros; both native strings are retained and their decimal values agree exactly.',
    'Native contest totals, total votes cast, overvotes and undervotes are absent, not zero; restricted districts and ballot modes have no borrowed registration denominator.',
  ];
  return [{
    year: 2026, state_code: 'PA', county_id: 'reviewed:PA:Somerset', county: 'Somerset',
    geography_level: 'county', ballots, denominator, denominator_basis: 'native_registered_voters',
    participation_measure_literal: native.native_measure_literal, reported_pct: 100 * ballots / denominator,
    native_printed_pct: native.native_printed_turnout, source_status_literal: native.native_status_literal,
    reported_units: 67, total_units: 67, source_rows: 1, maps_approved: false, review_id: id,
    native_record: native, native_source_updates: updates,
    source_update_label: updates.map(row =>
      `${row.source}: ${row.native_update_literal} (timezone not declared)`).join('; '),
    source_reporting_label: reporting.map(row =>
      `${row.label_literal}: ${row.reported}/${row.total}`).join('; ') + '; ' + quality.join(' '),
    quality, source_url: `${review.base_url}county-participation.csv`,
    complete_download_url: review.complete_download_url,
  }];
}

export function loadReviewedSusquehannaParticipation(reviews) {
  const id = 'pennsylvania-susquehanna-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  const manifest = readFileSync(resolve(directory, 'checksums.json'));
  if (createHash('sha256').update(manifest).digest('hex')
    !== 'ad0619a516d2047a384091af1506ad7c0ee5168cfadf5fdaaa52484284dd5a4a')
    throw new Error(`Invalid reviewed county participation: ${id} / checksums.json`);
  const files = { ...JSON.parse(manifest), 'complete-query.zip': {
    bytes: 92737, sha256: '278746dd8f1f6f8ab08d47ecd1486376319272976e7f824034783d752e03d069',
  } };
  for (const [file, expected] of Object.entries(files)) {
    const body = readFileSync(resolve(directory, file));
    if (body.length !== expected.bytes || createHash('sha256').update(body).digest('hex') !== expected.sha256)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv')), native = rows[0];
  const ballots = Number(native?.total_ballots), denominator = Number(native?.registered_voters);
  if (rows.length !== 1 || native.state !== 'Pennsylvania' || native.county !== 'Susquehanna'
    || native.election_date !== '2026-11-03' || native.scope !== 'county'
    || native.native_ballot_label !== 'Total Ballots' || native.native_registration_label !== 'Registered Voters'
    || native.native_status !== 'UNOFFICIAL RESULTS' || native.native_title !== 'Unofficial Election Day Results'
    || native.native_date !== '11/3/2026' || native.native_clock !== '10:25:47 PM EST'
    || native.native_printed_percentage !== '55.69%' || ballots !== 15317 || denominator !== 27504
    || ['source_fips', 'native_mode', 'blank_ballots', 'overvotes', 'undervotes'].some(key => native[key] !== '')
    || ['analysis_ballots_approved', 'analysis_rate_approved', 'map_approved'].some(key => native[key] !== 'False'))
    throw new Error(`Invalid reviewed county participation: ${id}`);
  const pages = csv(resolve(directory, 'source-pages.csv')), reporting = csv(resolve(directory, 'reporting.csv'));
  const updates = [...new Map(pages.map(row => {
    const literal = `${row.native_date} ${row.native_clock}`;
    return [`${row.source_role}:${literal}`, {
      source: row.source_role, native_update_literal: literal, declared_timezone: 'EST',
    }];
  })).values()];
  const quality = [
    'Separately reviewed native whole-county Total Ballots and Registered Voters; all 41 precinct ballot and registration totals reconcile. Candidate selections and mail-process counts are not added.',
    'Native registered-voter fraction only, not CVAP, VAP, VEP, CPS, demographic turnout or a mode electorate. Original frozen analysis/rate/map flags remain unchanged; county usability and contextual identity are separate reviews.',
    'UNOFFICIAL RESULTS, native title Unofficial Election Day Results and 41/41 reporting do not establish completed counting or certification. The canvass explicitly includes Normal and Absentee / Mail-In candidate vectors despite the title.',
    'All 58 complete numerical pages, four contest matrices and 340 canvass mode vectors reconcile; candidate and literal-party results remain separate from participation.',
    'Summary, all three precinct clocks and canvass clock retain native EST. Native precinct Page 1/1 is not substituted for physical page inventory.',
    'Ballot-mode counts, blank ballots, overvotes and undervotes are absent, not zero; ballot-minus-contest differences are unclassified, not native undervotes.',
    'Five exact printed half-even percentage ties are retained. Governor canvass labels lack native parties; separately matched full summary identities are not relabeled as native canvass affiliations.',
    'Native FIPS is missing; a separately reviewed Census contextual county join is not a certified 2026 election reporting boundary.',
  ];
  return [{
    year: 2026, state_code: 'PA', county_id: 'reviewed:PA:Susquehanna', county: 'Susquehanna',
    geography_level: 'county', ballots, denominator, denominator_basis: 'native_registered_voters',
    participation_measure_literal: native.native_ballot_label, reported_pct: 100 * ballots / denominator,
    native_printed_pct: native.native_printed_percentage, source_status_literal: native.native_status,
    reported_units: 41, total_units: 41, source_rows: 1, maps_approved: false, review_id: id,
    native_record: native, native_source_updates: updates,
    source_update_label: updates.map(row => `${row.source}: ${row.native_update_literal}`).join('; '),
    source_reporting_label: reporting.map(row =>
      `${row.native_contest || 'County reporting'}: ${row.reporting}/${row.number_of_precincts}`).join('; ')
      + '; ' + quality.join(' '),
    quality, source_url: `${review.base_url}county-participation.csv`,
    complete_download_url: review.complete_download_url,
  }];
}

export function loadReviewedSullivanWyomingParticipation(reviews) {
  const id = 'pennsylvania-sullivan-wyoming-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  const manifest = readFileSync(resolve(directory, 'checksums.json'));
  if (createHash('sha256').update(manifest).digest('hex')
    !== 'd44ed20e278f8628e159701b709098f3c45389165a462742be67839dd00210c2')
    throw new Error(`Invalid reviewed county participation: ${id} / checksums.json`);
  const files = { ...JSON.parse(manifest), 'complete-query.zip': {
    bytes: 19963, sha256: 'cba0b37aa4ecfd38ce02d0832a67a1f26a8240c15190fab78dca7c51e4519c47',
  } };
  for (const [file, expected] of Object.entries(files)) {
    const body = readFileSync(resolve(directory, file));
    if (body.length !== expected.bytes || createHash('sha256').update(body).digest('hex') !== expected.sha256)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv'));
  if (rows.length !== 2) throw new Error(`Invalid reviewed county participation: ${id}`);
  return rows.map((native, index) => {
    const [county, ballots, denominator, percentage, clock, units] = [
      ['Sullivan', 2712, 4501, '60.25%', '10:36:27', null],
      ['Wyoming', 10542, 18565, '56.78%', '09:15:07', 28],
    ][index];
    if (native.county !== county || native.state !== 'Pennsylvania' || native.scope !== 'county'
      || native.election_date !== '2026-11-03' || native.native_date !== '2026-11-06'
      || native.native_clock !== clock || native.native_printed_percentage !== percentage
      || native.native_ballot_label !== 'Total Ballots Cast' || native.native_registration_label !== 'Registered Voters'
      || Number(native.total_ballots) !== ballots || Number(native.registered_voters) !== denominator
      || ['source_fips', 'native_timezone', 'native_mode', 'blank_ballots', 'overvotes', 'undervotes']
        .some(key => native[key] !== '')
      || ['analysis_ballots_approved', 'analysis_rate_approved', 'map_approved'].some(key => native[key] !== 'False'))
      throw new Error(`Invalid reviewed county participation: ${id} / ${county}`);
    const updates = [{
      source: 'county summary', native_update_literal: `${native.native_date} ${clock}`,
      declared_timezone: null,
    }];
    const quality = [
      'Separately reviewed native whole-county Total Ballots Cast / Registered Voters only; not candidate selections, a mode denominator, CVAP/VAP/VEP or demographic participation.',
      'All four physical pages, 22 candidate-mode vectors, seven contest totals and the entire 944-cell write-in matrix are retained in the complete numerical query.',
      'Native candidate affiliations and summary office districts are missing, not inferred from familiar names; ED / MI / PR remain literal candidate columns, not ballot-mode counts.',
      'Both November 6 summary clocks lack native timezones. The listing prints an election date, not an update clock; its physical pages 2/3 are not the summary native Page 1 of 1.',
      'Sullivan summary status comes from physical page 2; Wyoming unofficial status comes from the declared file name, not a printed PDF status. Neither establishes certification or completed counting.',
      'Sullivan ballot-minus-selection differences 41/32/396 are unclassified, not undervotes; listed write-ins 1/1/48 differ from summary 1/5/73, leaving separately scoped 0/4/25 unallocated.',
      'Wyoming over-voted ballots plus undervotes reconcile each contest; overvotes are not added twice. Ballot-mode counts and blank ballots remain missing, not zero.',
      'All 841 blank matrix cells remain missing; all 16 printed zeros remain zero. Named listings are not added to summary write-ins or participation.',
      'Native FIPS and native approval flags remain unchanged; separate county usability and Census context do not certify 2026 election reporting boundaries or precinct coverage.',
    ];
    return {
      year: 2026, state_code: 'PA', county_id: `reviewed:PA:${county}`, county,
      geography_level: 'county', ballots, denominator, denominator_basis: 'native_registered_voters',
      participation_measure_literal: native.native_ballot_label, reported_pct: 100 * ballots / denominator,
      native_printed_pct: percentage,
      source_status_literal: native.native_status || 'Unofficial (source file name; not printed PDF status)',
      reported_units: units, total_units: units, source_rows: 1, maps_approved: false, review_id: id,
      native_record: native, native_source_updates: updates,
      source_update_label: updates.map(row => `${row.source}: ${row.native_update_literal}`).join('; '),
      source_reporting_label: (units === null ? 'Precinct reporting not printed; '
        : '28/28 precincts reported, not completed counting; ') + quality.join(' '),
      quality, source_url: `${review.base_url}county-participation.csv`,
      complete_download_url: review.complete_download_url,
    };
  });
}

export function loadReviewedBedfordNorthumberlandParticipation(reviews) {
  return [
    ['bedford', 'Bedford', '0b5d7f46f4cc3dd4a44805be5b441e8d6132c466481be04066b26ca3f14d2c43',
      15912, '238a3290697769bc0921d6f20d561961be4ded1d832d6eaa90bc355fab918752',
      19041, 33079, '57.56', '11/3/2026 9:53:30 PM', 40],
    ['northumberland', 'Northumberland', '93111db0c6b298d2aff7bb0b8b8a0cddbb58817f81a997c9673161bee4ea8341',
      16064, '8c4c76b3bc19dd8baa6d188cd25b7c72c8520d68c6da6259d1ac47f989799bc2',
      28341, 55540, '51.03', '11/03/2026 22:18 PM', 74],
  ].map(([slug, county, manifestHash, bytes, sha256, ballots, denominator, percentage, clock, units]) => {
    const id = `pennsylvania-${slug}-20261106-01`;
    const matches = reviews.filter(review => review.id === id);
    if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
    const review = matches[0], directory = resolve(review.data_directory);
    const manifest = readFileSync(resolve(directory, 'checksums.json'));
    if (createHash('sha256').update(manifest).digest('hex') !== manifestHash)
      throw new Error(`Invalid reviewed county participation: ${id} / checksums.json`);
    const bedford = slug === 'bedford', parsed = JSON.parse(manifest);
    const files = { ...(bedford ? Object.fromEntries(parsed.files.map(file => [file.path, file])) : parsed),
      'complete-query.zip': { bytes, sha256 } };
    for (const [file, expected] of Object.entries(files)) {
      const body = readFileSync(resolve(directory, file));
      if (body.length !== expected.bytes || createHash('sha256').update(body).digest('hex') !== expected.sha256)
        throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
    }
    const rows = csv(resolve(directory, 'county-participation.csv')), native = rows[0];
    if (rows.length !== 1 || native.native_county !== `${county} County`
      || Number(bedford ? native.voters_cast : native.ballots_cast) !== ballots
      || bedford && Number(native.cards_cast) !== ballots
      || !bedford && native.election_date !== '2026-11-03'
      || Number(native.registered_voters) !== denominator || native.native_turnout_pct !== percentage
      || native.native_report_clock !== clock || native.native_status !== (bedford ? 'Unofficial' : 'UNOFFICIAL RESULTS')
      || ['native_fips', 'native_timezone'].some(key => native[key] !== '')
      || ['analysis_rate_approved', 'map_approved'].some(key => native[key] !== 'False'))
      throw new Error(`Invalid reviewed county participation: ${id}`);
    const reporting = csv(resolve(directory, 'reporting.csv'));
    const quality = [
      'Separately reviewed whole-county participation and the same report registrations, not candidate selections or mail-process receipts.',
      'Native registered-voter fraction only, not CVAP, VAP, VEP, CPS or demographic turnout; individual ballot modes have no borrowed registration denominator.',
      'Unofficial status and reported precincts do not establish completed counting or certification. Native clocks have no declared timezone.',
      'Native FIPS and native approval flags remain unchanged; separate Census contextual identity does not certify 2026 election reporting boundaries.',
      ...(bedford ? [
        'Native Voters Cast and Cards Cast both 19,041; 16,138 Election Day + 2,903 Mail-In + explicit zero Provisional. Total is not a fourth additive mode.',
        'Both complete physical pages, all 12 candidate vectors, four contests and 16 native mode-accounting rows reconcile; literal candidate parties remain separate from participation.',
        'Native Total Votes excludes separate unresolved write-ins 8/23/34/339; do not add them again or infer their allocation to under/overvotes.',
        'Mode registrations are missing; separately rounded native mode rates need not sum to the separately rounded aggregate.',
      ] : [
        'Native Ballots Cast - Total 28,341 includes 24,393 Election Day + 3,948 Mail/Absentee + explicit zero Provisional; 28 blank ballots are already included.',
        'All three complete physical pages, 23 candidate/option vectors, six contests and 24 mode-accounting rows reconcile; native mode registrations and rates are missing.',
        'Vote For 7 city commission totals 9,450 Contest Totals / 5,588 Total Votes Cast are not county ballots or unique city voters; subcounty electorates are not added.',
        'All contest-total residuals are unclassified, not native undervotes, overvotes or missing people; do not subtract county blank ballots to invent an accounting category.',
        'The mixed 11/03/2026 22:18 PM source clock is preserved literally without normalized UTC or timezone inference.',
      ]),
    ];
    const updates = [{ source: 'county summary', native_update_literal: clock, declared_timezone: null }];
    return {
      year: 2026, state_code: 'PA', county_id: `reviewed:PA:${county}`, county,
      geography_level: 'county', ballots, denominator, denominator_basis: 'native_registered_voters',
      participation_measure_literal: bedford ? 'Voters Cast' : 'Ballots Cast - Total',
      reported_pct: 100 * ballots / denominator, native_printed_pct: `${percentage}%`,
      source_status_literal: native.native_status, reported_units: units, total_units: units,
      source_rows: 1, maps_approved: false, review_id: id, native_record: native,
      native_source_updates: updates,
      source_update_label: `county summary: ${clock} (timezone not declared)`,
      source_reporting_label: reporting.map(row =>
        `${row.scope ?? row.native_scope}: ${row.reported}/${row.total}`).join('; ') + '; ' + quality.join(' '),
      quality, source_url: `${review.base_url}county-participation.csv`,
      complete_download_url: review.complete_download_url,
    };
  });
}

export function loadReviewedUtahParticipation(reviews) {
  const id = 'utah-ballot-statistics-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  const manifest = readFileSync(resolve(directory, 'checksums.json'));
  if (createHash('sha256').update(manifest).digest('hex') !==
    'c40a3b04df58c359e20724b9a5cea90cd9d6e0ed9c1df4cd25ee918a7586c1e4')
    throw new Error(`Invalid reviewed county participation: ${id} / checksums.json`);
  const files = [...JSON.parse(manifest).files, { path: 'complete-query.zip', bytes: 33004,
    sha256: '6ef44592932d54e75f6a668ffa7ae2e3a2720992e3a982804d927106ccc64761' }];
  for (const expected of files) {
    const body = readFileSync(resolve(directory, expected.path));
    if (body.length !== expected.bytes || createHash('sha256').update(body).digest('hex') !== expected.sha256)
      throw new Error(`Invalid reviewed county participation: ${id} / ${expected.path}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv'));
  const source = JSON.parse(readFileSync(resolve(directory, 'source-qualification.json'), 'utf8'));
  if (rows.length !== 29 || new Set(rows.map(row => row.native_county)).size !== 29
    || rows.filter(row => row.ballots_counted !== '').length !== 19
    || rows.filter(row => row.ballots_counted !== '' && row.registered_voters !== '').length !== 18)
    throw new Error(`Incomplete reviewed county source: ${id}`);
  return rows.map(native => {
    const qualified = native.source_scope_review === 'native_counted_total';
    const ballots = native.ballots_counted === '' ? null : Number(native.ballots_counted);
    const denominator = native.registered_voters === '' ? null : Number(native.registered_voters);
    const report = native.source_ordinal === '' ? null
      : source.reports.find(row => row.source_ordinal === Number(native.source_ordinal));
    if (native.native_fips !== '' || native.analysis_rate_approved !== 'False'
      || native.map_approved !== 'False' || native.source_timezone_literal !== ''
      || qualified !== (ballots !== null)
      || ballots !== null && (!Number.isSafeInteger(ballots) || ballots < 0)
      || denominator !== null && (!Number.isSafeInteger(denominator) || denominator <= 0
        || ballots !== null && ballots > denominator)
      || report && (!report.latest_selection || report.county_literal !== native.native_county
        || report.fields.ballots_counted !== ballots || report.fields.registered_voters !== denominator))
      throw new Error(`Invalid reviewed county participation: ${id} / ${native.native_county}`);
    const quality = [
      'Source-defined county counted-ballot snapshot, not candidate selections, receipts, fully processed ballots, scans or voter-history credits.',
      'Same-report registered-voter fraction only when both values are supplied; approximate registration labels remain approximate. Not CVAP, VAP, VEP or demographic turnout.',
      'Counting is incomplete; no complete all-mode coverage, certification or final unique-voter count is inferred. Ballot-processing categories are not added as a partition.',
      'November 2 registration affiliations remain separate, not substituted denominators, party votes or group-specific participation.',
      'Literal source cutoffs retain missing years/timezones; source upload dates and portal publication clocks are not numerical update clocks.',
      report?.qualification ?? 'No declared ballot-statistics report; missing participation is not zero.',
    ];
    const clock = native.source_updated_literal;
    return {
      year: 2026, state_code: 'UT', county_id: `reviewed:UT:${native.native_county}`,
      county: native.native_county, geography_level: 'county', ballots, denominator,
      participation_measure_kind: 'source_defined_participation_count',
      participation_measure_literal: native.native_counted_label || 'County counted-ballot total not supplied',
      participation_measure_label: qualified ? `Native ${native.native_counted_label} (counted snapshot)`
        : 'County counted-ballot total not supplied',
      denominator_basis: 'native_registered_voters',
      reported_pct: ballots !== null && denominator !== null ? 100 * ballots / denominator : null,
      native_printed_pct: null, source_status_literal: native.native_status,
      reported_units: null, total_units: null, source_rows: report ? 1 : 0,
      maps_approved: false, review_id: id, native_record: native,
      native_source_updates: clock
        ? [{ source: 'county ballot statistics', native_update_literal: clock, declared_timezone: null }] : [],
      source_update_label: clock ? `${clock} (timezone not declared)`
        : 'Native statistics update clock not supplied; upload and fetch clocks are not substitutes.',
      source_reporting_label: `${native.source_scope_review}; `
        + (native.native_denominator_label ? `Native denominator: ${native.native_denominator_label}. ` : 'Native denominator missing. ')
        + quality.join(' '),
      quality, source_url: `${review.base_url}county-participation.csv`,
      complete_download_url: review.complete_download_url,
    };
  });
}

export function loadReviewedFloridaParticipation(reviews) {
  const id = 'florida-consolidated-turnout-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  const manifest = readFileSync(resolve(directory, 'checksums.json'));
  if (createHash('sha256').update(manifest).digest('hex') !==
    'f0e1d7685067483b4bb304557eb3244bcf4b4c4819ab8212718fcfc40d30b7ef')
    throw new Error(`Invalid reviewed county participation: ${id} / checksums.json`);
  const files = [...JSON.parse(manifest).files, { path: 'complete-query.zip', bytes: 25999,
    sha256: '977ca600f23e4ec6d87a56272e68e55534380c855b0866c6d0cd0b55174ce474' }];
  for (const expected of files) {
    const body = readFileSync(resolve(directory, expected.path));
    if (body.length !== expected.bytes || createHash('sha256').update(body).digest('hex') !== expected.sha256)
      throw new Error(`Invalid reviewed county participation: ${id} / ${expected.path}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv'));
  const source = JSON.parse(readFileSync(resolve(directory, 'source-qualification.json'), 'utf8'));
  if (rows.length !== 67 || new Set(rows.map(row => row.native_county)).size !== 67
    || source.source_as_of !== null || source.source_timezone !== null)
    throw new Error(`Incomplete reviewed county source: ${id}`);
  return rows.map(native => {
    const ballots = Number(native.reported_participants);
    const denominator = Number(native.eligible_active_registered_voters);
    if (native.native_fips !== '' || native.analysis_rate_approved !== 'False'
      || native.map_approved !== 'False' || native.source_as_of !== '' || native.source_timezone !== ''
      || !Number.isSafeInteger(ballots) || ballots < 0
      || !Number.isSafeInteger(denominator) || denominator <= 0 || ballots > denominator
      || Object.entries(native).some(([key, value]) => key.endsWith('_completed') && !['Y', 'N'].includes(value)))
      throw new Error(`Invalid reviewed county participation: ${id} / ${native.native_county}`);
    const quality = [
      'Source-defined reported participation snapshot from the official all-county general-election table, not candidate selections, receipts or processing counters.',
      'Same-table reported participants divided by Eligible Active Registered Voters; not CVAP, VAP, VEP or demographic turnout.',
      'Native provisional and ten-day overseas completion flags remain literal; 100% precinct reporting is not certification or proof of finished counting.',
      'No declared source-update time or timezone; fetch, HTTP and navigation clocks are not replacements.',
    ];
    const flags = Object.entries(native).filter(([key]) => key.endsWith('_completed'))
      .map(([key, value]) => `${key}=${value}`).join('; ');
    return {
      year: 2026, state_code: 'FL', county_id: `reviewed:FL:${native.native_county}`,
      county: native.native_county, geography_level: 'county', ballots, denominator,
      participation_measure_kind: 'source_defined_participation_count',
      participation_measure_literal: 'Voter Turnout',
      participation_measure_label: 'Native Voter Turnout (reported ballot-casting snapshot)',
      denominator_basis: 'native_registered_voters', reported_pct: 100 * ballots / denominator,
      native_printed_pct: native.native_turnout_percentage,
      source_status_literal: source.source_status, reported_units: null, total_units: null,
      source_rows: 1, maps_approved: false, review_id: id, native_record: native, native_source_updates: [],
      source_update_label: 'Native turnout update clock/timezone not supplied; HTTP/fetch clocks are not replacements.',
      source_reporting_label: `${flags}. ${quality.join(' ')}`, quality,
      source_url: `${review.base_url}county-participation.csv`,
      complete_download_url: review.complete_download_url,
    };
  });
}

export function loadReviewedRockParticipation(reviews) {
  const id = 'wisconsin-rock-turnout-20261106-01';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  const manifest = readFileSync(resolve(directory, 'checksums.json'));
  if (createHash('sha256').update(manifest).digest('hex') !==
    '83e0b77a2c8e5b54c670a8e8664d22146e374bb567875e744ca16b8b4457a95a')
    throw new Error(`Invalid reviewed county participation: ${id} / checksums.json`);
  const files = [...JSON.parse(manifest).files, { path: 'complete-query.zip', bytes: 84439,
    sha256: '63f277b2005438861fed666497e833180960b88c73f7333fa5f0746abb8fc45f' }];
  for (const expected of files) {
    const body = readFileSync(resolve(directory, expected.path));
    if (body.length !== expected.bytes || createHash('sha256').update(body).digest('hex') !== expected.sha256)
      throw new Error(`Invalid reviewed county participation: ${id} / ${expected.path}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv'));
  const source = JSON.parse(readFileSync(resolve(directory, 'source-qualification.json'), 'utf8'));
  if (rows.length !== 1 || source.source_timezone !== null || source.native_fips !== null)
    throw new Error(`Incomplete reviewed county source: ${id}`);
  const native = rows[0], ballots = Number(native.reported_ballots_cast);
  const denominator = Number(native.reported_registered_voters);
  if (native.native_county !== 'Rock County' || native.native_state !== 'Wisconsin'
    || native.native_fips !== '' || native.source_timezone !== ''
    || ['analysis_rate_approved', 'map_approved', 'all_mode_definition_approved', 'certified']
      .some(key => native[key] !== 'False')
    || !Number.isSafeInteger(ballots) || ballots < 0
    || !Number.isSafeInteger(denominator) || denominator <= 0 || ballots > denominator
    || native.native_update_literal !== source.native_update_literal
    || source.reporting_statements[0] !== 'Precincts Reporting: 106 of 106 for 100%')
    throw new Error(`Invalid reviewed county participation: ${id}`);
  const quality = [
    'Native whole-county Ballots Cast snapshot, not candidate selections, receipts or processing counters; all 106 unit totals independently reconcile.',
    'Same-report Registered Voters fraction only, not CVAP, VAP, VEP, CPS or demographic turnout. The source does not establish a separate denominator reference date.',
    'Unofficial results; complete precinct reporting is not certification, final counting or proof of complete all-mode coverage. Ballot-mode decomposition remains unspecified.',
    'Preserve the literal November 03, 2026 at 10:56 PM update with missing timezone; do not infer UTC or use receipt clocks.',
    'All 65 candidate/option totals and 3648 complete unit-candidate rows remain separate. Governor selections 67418 are not the 67812 Ballots Cast count.',
  ];
  return [{
    year: 2026, state_code: 'WI', county_id: 'reviewed:WI:Rock County',
    county: 'Rock County', geography_level: 'county', ballots, denominator,
    participation_measure_kind: 'source_defined_participation_count',
    participation_measure_literal: 'Ballots Cast',
    participation_measure_label: 'Native Ballots Cast (reported county snapshot)',
    denominator_basis: 'native_registered_voters', reported_pct: 100 * ballots / denominator,
    native_printed_pct: native.native_registered_percentage,
    source_status_literal: source.native_heading, reported_units: 106, total_units: 106,
    source_rows: 1, maps_approved: false, review_id: id, native_record: native,
    native_source_updates: [{ source: 'county summary',
      native_update_literal: source.native_update_literal, declared_timezone: null }],
    source_update_label: `${source.native_update_literal} (timezone not declared)`,
    source_reporting_label: `${source.reporting_statements[0]}; ${quality.join(' ')}`, quality,
    source_url: `${review.base_url}county-participation.csv`,
    complete_download_url: review.complete_download_url,
  }];
}

export function loadReviewedCountyParticipation(reviews) {
  const observations = [], seen = new Set();
  for (const [id, ballotField, denominatorField, printedField, code, names] of profiles) {
    const matches = reviews.filter(review => review.id === id);
    if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
    const review = matches[0], directory = resolve(review.data_directory);
    const newSummary = ['pennsylvania-juniata-20261106-01', 'pennsylvania-mercer-20261106-01',
      'pennsylvania-montour-20261106-01'].includes(id);
    const pinnedHashes = {
      'pennsylvania-perry-20261106-01': {
        'county-participation.csv': '710a64c3da639a698014f2e0766c5a40c7a9cdf7e7ee4832ad3b4442d8bb5499',
        'native-source-pages.csv': '74624adcd3146bb4527e883f4ac178b3c68cec1a89478b56a978d40be09103d3',
        'audit.json': 'dd9cf208f356d4bab5b69971eab10feb020960331b89d38b5edf33bfe6f8f1bb',
      },
      'pennsylvania-juniata-20261106-01': {
        'county-participation.csv': 'c01eb7c094fa96020be842202a546fd73977461dead7ad824c1738752773f3e9',
        'native-source-pages.csv': '5bf27310c278a1335be003fada48e96eba9b8a7653e31d26fbb67b110fe3b1b3',
        'audit.json': 'ce7feae7452169a58a5cf0e9c4a912bb547815ae89c363330c857b731e005445',
      },
      'pennsylvania-mercer-20261106-01': {
        'county-participation.csv': 'd84df1000513cc48baae68217d3afdb21e745ca0b5d352db6e58724c60d9deaa',
        'native-source-pages.csv': '2bc7a932687a1d8ba187e2cc018a0713928f6563c82bb843791d3be6efe873ae',
        'audit.json': 'b633061bfbf6dd8a1cff203b95539200198e6a29f608fb28d4c7e1402e53c163',
      },
      'pennsylvania-montour-20261106-01': {
        'county-participation.csv': '321db3b3c60d3fe917ea29ef7c67e89dda03464ccc2abd9792fa6fd873775801',
        'native-source-pages.csv': 'd57995255325a864cde8927813b72252c8074d6612e088ee55cf0eee19866931',
        'audit.json': '5d831b548e66aa1c996f46765d993e126b7d6876ce3ba855e005860f7a2574bf',
      },
      'pennsylvania-columbia-20261106-01': {
        'county-participation.csv': 'ee3c13fa8a5d9bbc3a545bedcec34af63eab597420f683ea53a249f7afeb9207',
        'native-source-pages.csv': '72cbed8c69094c833356d00fafd86f35e58b81a5c91e7663500f937c28e0dd81',
        'audit.json': '387a0af6b6f815da19a03bfc70019130a25b6280b0807b74fcb395adb0830077',
      },
      'pennsylvania-greene-20261106-01': {
        'county-participation.csv': '81f1b0f00db8dc60a32c641455df55e4ec682096ac7f6ae3a6043966520820e8',
        'native-reporting-statistics.csv': '8cd492f4a6e8fed3fb8e762e419891d3023f89df0bb6fe0d15e37b11fc29ddd7',
        'audit.json': '0660c64fa605450a2d6154b5e7138ec7abcd51fe5b9d6be7271bea9827f462f7',
      },
      'pennsylvania-lycoming-20261106-01': {
        'county-participation.csv': '03d3b078153e11ff5f3cf6369164f59ee82127c7b63e71c6ed05a4044d392392',
        'native-source-pages.csv': '88c9c684006799e315d76265ce688e0e5ec6dc7965c677acd116b8bfdd5f7e82',
        'audit.json': 'ad04c8ef11731442d5e88b8a2b566128cd68592b23853946e56f3fcd0b7d52b8',
      },
    }[id];
    for (const [file, digest] of Object.entries(pinnedHashes ?? {})) {
      if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
        throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
    }
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
    if (id === 'pennsylvania-clarion-20261106-01') {
      for (const [file, digest] of Object.entries({
        'county-participation.csv': '2ffea414bf7f6469e4f341efde85d6627079dbbdda02ab7f24db0e518a5bb76c',
        'native-source-pages.csv': '1d2a89ba763b4e9c0f987673c50d286926cf5d2f2ae599f56385b6ae49529c12',
        'audit.json': 'f4b13e48e86bae053332529e2a200c3d93cba6b489f9591bcf5be12186edc308',
      })) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    if (['pennsylvania-cameron-20261106-01', 'pennsylvania-carbon-20261106-01'].includes(id)) {
      const hashes = id === 'pennsylvania-cameron-20261106-01' ? {
        'county-participation.csv': 'b2cb38ef8cd0738ac69b53911c0f59ff2bd09f6c82b8c5163455bdfd3059d06e',
        'native-source-pages.csv': '04c094ab73e1bf1b13a51de3971e2ffb957aa26c240b5df1afe4a4996a6cb425',
        'audit.json': '4900f852c745f0f514fc0879fd55d781344b634178ea001f4b1512cc9bd471a0',
      } : {
        'county-participation.csv': '68ec38689b3af14ae221a3c577aa3aa3e08d05313d6cb0af39480a212642b607',
        'native-source-pages.csv': '5cc7fc5a94e644830836ce5f75aa187c10975f621741d030919211d6bd131a2b',
        'audit.json': '056db770be0a8c4cdc50f3986b0fecf9f8a87331b999b0df0f37482d64aef1c7',
      };
      for (const [file, digest] of Object.entries(hashes)) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
    if (id === 'pennsylvania-mifflin-20261106-01') {
      for (const [file, digest] of Object.entries({
        'county-participation.csv': 'fc44988e299256ae5fccb9e33a9f0eb049a37f184c2e7f9c3fb64d8b61f95eec',
        'native-source-pages.csv': 'a07daeade5b5a5537ee2fbe6d859e5f8b8d9c15e3d0415888d8ba85cd47ef834',
        'audit.json': '002cca74c5cb18d58c566bd591acc8b81f6fae463f28989e06a63565ac714436',
      })) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    if (id === 'pennsylvania-potter-20261106-01') {
      for (const [file, digest] of Object.entries({
        'county-participation.csv': '32e83977ce7b6679afbccaca04b775dad071abdb26a86497fbeebd66d132bac1',
        'native-source-pages.csv': 'ddd87ae40fef5ecb84f6412fe34b973efe83741823891f696c386de168bd8b00',
        'audit.json': '9a3290b08c635d69d1ead5b2fc68e59cfaa73fb77efe8e49ff53c4cf7a27647d',
      })) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    if (['pennsylvania-elk-20261106-01', 'pennsylvania-forest-20261106-01'].includes(id)) {
      const hashes = id === 'pennsylvania-elk-20261106-01' ? {
        'county-participation.csv': '9f3623d46f0df591b03a21fe759d9705228db9de0ab51e74230cd09a1fc34c65',
        'native-source-pages.csv': 'a0e7ac0ce6e5c364896d148ee9cf131315dfd4787f01cbc04ce435ace179176f',
        'audit.json': 'b3aa21eff714afb9084fb24974aa9b761b3d64ff5c5ebd4fc414001f3b9fd076',
      } : {
        'county-participation.csv': 'db9870d10c5f72159ee759a3c725d98635a89a96f7854638556791cee182a8dd',
        'native-source-pages.csv': 'cb36428e38f0ccac450b83f2b3b4622d79fa4193fa36937c99b4184278ce7604',
        'audit.json': 'fbcfe94d957be9ec41f35c459c0fb35c55629dcf89c8bc85bafff849bdc5b021',
      };
      for (const [file, digest] of Object.entries(hashes)) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    const rows = csv(resolve(directory, 'county-participation.csv'));
    if (rows.length !== names.length) throw new Error(`Incomplete reviewed county source: ${id}`);
    for (const native of rows) {
      const county = native.county ?? native.geography, identity = `${code}|${county}`;
      const nativeMifflinSummary = id === 'pennsylvania-mifflin-20261106-01';
      const unusableNativeZero = id === 'pennsylvania-lebanon-20261106-01' || nativeMifflinSummary;
      const excludesProvisionals = id === 'pennsylvania-armstrong-20261106-01';
      const nativeClarionSummary = id === 'pennsylvania-clarion-20261106-01';
      const nativeCameronSummary = id === 'pennsylvania-cameron-20261106-01';
      const nativeCarbonSummary = id === 'pennsylvania-carbon-20261106-01';
      const nativeElkSummary = id === 'pennsylvania-elk-20261106-01';
      const nativeForestSummary = id === 'pennsylvania-forest-20261106-01';
      const nativePotterSummary = id === 'pennsylvania-potter-20261106-01';
      const nativePerrySummary = id === 'pennsylvania-perry-20261106-01';
      const nativeColumbiaSummary = id === 'pennsylvania-columbia-20261106-01';
      const nativeGreeneSummary = id === 'pennsylvania-greene-20261106-01';
      const nativeLycomingSummary = id === 'pennsylvania-lycoming-20261106-01';
      const nativeVotersCast = excludesProvisionals || id === 'pennsylvania-jefferson-20261106-01'
        || nativeClarionSummary || nativeCarbonSummary;
      const nativeCountyHeader = id === 'pennsylvania-wayne-20261106-01';
      const ballots = Number(native[ballotField]);
      const denominator = unusableNativeZero || nativeGreeneSummary ? null : Number(native[denominatorField]);
      const invalidDenominator = nativeGreeneSummary
        ? native[denominatorField] !== '' || native.native_printed_turnout !== ''
          || native.registered_turnout_pct !== ''
        : unusableNativeZero
        ? nativeMifflinSummary
          ? native[denominatorField] !== '0' || native.registered_turnout_pct !== ''
            || native.native_printed_turnout !== '0.00%'
          : native[denominatorField] !== '' || native.native_registered_voters !== '0'
            || native.registered_turnout_percent !== '' || native.native_printed_turnout !== '0.00%'
        : !/^\d+$/.test(native[denominatorField]) || !Number.isSafeInteger(denominator)
          || denominator <= 0 || ballots > denominator;
      if (native.year !== '2026' || native.state_code !== code || !names.includes(county) || seen.has(identity)
        || !/^\d+$/.test(native[ballotField]) || !Number.isSafeInteger(ballots)
        || (unusableNativeZero && ballots <= 0) || invalidDenominator
        || (excludesProvisionals && (native.native_participation_measure_literal !== 'Voters Cast'
          || native.provisional_voters_cast !== ''
          || native.native_status_literal !== '2026 General Election Unofficial Results w/o PROV'))
        || (nativePerrySummary && (native.native_participation_measure_literal !== 'Total Ballots Cast'
          || native.source_status_literal !== '' || native.parent_status_literal !== 'Unofficial'
          || native.election_day_ballots !== '' || native.mail_ballots !== '' || native.provisional_ballots !== ''
          || native.native_fips !== '' || native.maps_approved !== 'False' || native.counting_complete !== 'False'
          || ballots !== audit.native_ballots_cast || denominator !== audit.native_registered_voters))
        || (nativeColumbiaSummary && (native.native_participation_measure_literal !== 'Total Ballots'
          || native.source_status_literal !== 'UNOFFICIAL ELECTION RESULTS'
          || native.declared_timezone !== 'EST' || native.source_fips !== ''
          || native.maps_approved !== 'False' || native.counting_complete !== 'False'
          || native.reported_precincts !== '42' || native.total_precincts !== '42'))
        || (nativeGreeneSummary && (native.native_participation_measure_literal !== 'Ballots Cast - Total'
          || native.source_status_literal !== 'Unofficial Results with MI and Absentee'
          || native.source_update_literal !== '' || native.declared_timezone !== ''
          || native.source_fips !== '' || native.maps_approved !== 'False'
          || native.counting_complete !== 'False' || native.blank_ballots !== '5'
          || ballots !== audit.ballots_cast || audit.native_registered_voters !== null
          || audit.turnout_rate !== null || native.reported_precincts !== '42'
          || native.total_precincts !== '42'))
        || (nativeLycomingSummary && (native.native_measure_literal !== 'Total Ballots Cast'
          || native.native_status_literal !== 'Unofficial Results'
          || native.source_update_literal !== '2026-11-05 10:37:43'
          || native.declared_timezone !== '' || native.source_fips !== ''
          || native.county_ballot_modes !== '' || native.blank_ballots !== ''
          || native.maps_approved !== 'False' || native.counting_complete !== 'False'
          || native.reported_precincts !== '80' || native.total_precincts !== '80'
          || ballots !== audit.ballots_cast || denominator !== audit.registered_voters
          || audit.native_parties_present !== false || audit.native_ballot_modes_present !== false))
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
      if (newSummary) reporting.push(
        `Native Ballots Cast - Total ${ballots.toLocaleString('en-US')} / ${denominator.toLocaleString('en-US')} registrations; blank ballots are already included.`,
        `All ${audit.complete_reviewed_native_units} unit participation headers and ${audit.complete_unit_contests} unit contests reconcile; zero complete and ${audit.native_precincts_partial} partially reported units do not establish completed ballot counting.`,
        'Candidate votes and literal party totals are separate from ballots; named write-in spellings remain unharmonized, not allocated between units.',
        'Summary and statement clocks remain distinct without an inferred timezone.');
      if (id === 'pennsylvania-juniata-20261106-01') reporting.push(
        'Separate 85th/86th legislative electorates contain 1,977/6,281 ballots, not the entire county assigned to either contest.',
        'Counted modes are 7,160 Election Day + 1,098 Mail Votes + explicit zero Provisional Votes.');
      if (id === 'pennsylvania-mercer-20261106-01') reporting.push(
        'Counted modes are 31,943 Election Day + 7,178 native Absentee + explicit zero provisional; Absentee is not silently renamed Mail Votes, and the wrapped native provisional label is preserved.',
        'Native overvotes and undervotes are absent; derived participation-minus-choice residuals remain unclassified.',
        'Separate Assembly 17/7 electorates contain 16,437/22,684 ballots; each Sandy Lake Borough question has 226 ballots, not county participation.',
        'Mill Creek Township prints 58.36% while 307/526 rounds to 58.37%; both remain distinct.');
      if (id === 'pennsylvania-montour-20261106-01') reporting.push(
        'Counted modes are 5,554 Election Day + 1,429 Mail Votes + 25 Provisional Votes; provisional participation is not zero.',
        'Contradictory reporting-mode counters remain literal: zero complete and 15 partial overall, despite Election Day complete 15. No counter is repaired into completed counting.');
      if (nativeColumbiaSummary) reporting.push(
        'Native Total Ballots 22,583 / 40,797 registered voters, printed 55.35%; 42 of 42 reported precincts does not establish completed ballot counting or certification.',
        'All three contests and ten candidate/write-in choices reconcile separately; ballot-minus-contest differences remain unclassified, not inferred blanks or over/undervotes.',
        'Election Day, mail and provisional participation are absent, not zero. Separate filtered SURE mail returned 3,785 and votes recorded 3,772 are not established components of county ballots; no Election Day remainder is inferred.',
        'All 105 mail cells, eight application categories, one blank-labeled ballot style and nine literal registration-party categories remain available; registration parties are not candidate parties.',
        'Results retain their printed 11/3/2026 10:37:16 PM EST clock. The mail report prints Tuesday, November 3, 2026 without a time or timezone; PDF creation metadata supplies neither a report update nor certification.');
      if (nativeGreeneSummary) reporting.push(
        'Native Ballots Cast - Total 11,105; five blank ballots are retained separately and not added to the total.',
        'Registrations and the turnout rate are not supplied, not zero; no denominator is inferred from candidate votes.',
        'Unofficial Results with MI and Absentee; 42 of 42 reported precincts does not establish completed counting or certification.',
        'All thirteen candidate/write-in choices across four contests reconcile separately; administrative pseudo-party labels are not party participation.',
        'Ballot-minus-candidate differences 115/208/557/187 remain unclassified, not inferred undervotes or mail counts.',
        'No report-update clock or timezone is supplied; the election date and retrieval clock are not report updates.');
      if (nativeLycomingSummary) reporting.push(
        'Native Total Ballots Cast 40,596 / 73,009 registered voters, printed 55.60%; 80 of 80 reporting is not completed counting or certification.',
        'Election Day, mail, provisional and blank-ballot participation are absent, not zero. ED/MI/PR are candidate-vote columns, not county ballot-mode counts.',
        'Separate 5,770 Act88 mail receipts are not added to ballots or equated to counted mail.',
        'All six contests, sixteen choices and 48 candidate-mode cells remain separate; native parties are missing and are not inferred.',
        'Per-contest printed turnout has an unspecified numerator; no district ballot counts or eligible-population turnout are inferred.',
        'Election-night results include in-person votes and most mail; remaining mail, overseas and eligible provisional ballots are subject to later canvass.',
        'The return notice prints Wednesday, November 10; its weekday/date conflict is retained without repair or an inference of completed canvass.');
      if (nativeClarionSummary) reporting.push(
        '40 of 40 reported precincts does not establish completed ballot counting.',
        'Election Day, mail and provisional participation are not separately reported; missing mode counts are not zero.',
        'Foxburg referendum Times Cast 82/116 is a separate electorate, not additional county participation.',
        'Native Total Votes excludes Unresolved Write-In; contest participation-minus-choice residuals remain unclassified.');
      if (nativeCameronSummary) reporting.push(
        'Native Ballots Cast - Total 1,624 = 1,305 Election Day + 319 Mail; provisional participation is absent, not zero.',
        '10 of 10 Election Day and Absentee/Early precincts reported; zero complete and ten partially reported does not establish completed ballot counting.',
        'Separate Act88 returned 324 / recorded 320 are not counted Mail 319; differences remain unexplained and unallocated.',
        'The Act88 Federal Voter filter is preserved; its source supplies no report clock or timezone, and the 12:01 link label does not supply one.',
        'Not Assigned is nested within Write-In Totals, not additional votes; one blank ballot is already within Ballots Cast.');
      if (nativeCarbonSummary) reporting.push(
        'Native Voters Cast 24,840 = 20,375 Election Day + 4,465 Mail-In + explicit zero Provisional.',
        '51 of 51 reported precincts does not establish completed ballot counting; the earlier Official Zero Report is a separate observation, not current participation.',
        'All 51 statement units reconcile to the county; both county footers and both Cumulative zero/N/A containers remain separate and are not added.',
        'Kidder referendum Times Cast 807/1,457 is a separate electorate, not additional county participation.',
        'Mode-specific registrations and native overvotes/undervotes are absent; 350/381/288/30 participation-minus-choice residuals remain unclassified.');
      if (nativeElkSummary) reporting.push(
        'Native Ballots Cast - Total 11,742 = 9,725 Election Day + 2,017 Absentee/Mail-In + explicit zero Provisional; five blank ballots are already included.',
        'All 29 units are partially reported and zero complete; reported precincts do not establish completed ballot counting.',
        'All 29 unit headers and 87 contests reconcile; ST MARYS 4TH prints 55.10% while its 319/579 fraction rounds to 55.09%, and both remain distinct.',
        'Separate filtered Act88 returned 2,035 / recorded 2,018 are not counted mail 2,017; differences 18/1 remain unexplained. Its election date and filename do not supply a report clock.',
        'The index calls links Official while the reports say UNOFFICIAL RESULTS; the contradictory 11/03/2026 22:08 PM clock is preserved without repair.',
        'Native summary overvotes/undervotes are absent; derived unit sums remain separate. The Act88 scan is visually reviewed, not a two-engine transcription.');
      if (nativeForestSummary) reporting.push(
        'Native Ballots Cast - Total 1,877 / 3,275 registrations is on physical summary page 2, which prints Page 1 of 2; physical page 1 prints Page 2 of 2.',
        'All nine units are partially reported and zero complete; reported precincts do not establish completed ballot counting.',
        'Election Day, mail and provisional participation are absent, not zero; separate 311 mail-in absentee receipts by 8 p.m. are not counted mail ballots.',
        'All eleven scanned pages and magnified choice panels were visually reviewed; both full text engines are empty, not independent transcriptions.',
        'Native county summary has overvotes/undervotes but lacks Total Votes Cast/Contest Totals; units lack all four rows and their derived residuals remain unclassified.',
        'The contradictory 11/03/2026 20:56 PM clock is preserved without repair or inferred timezone.');
      if (nativePotterSummary) reporting.push(
        'Native Ballots Cast - Total 6,244 = 5,389 Election Day + 855 Mail + explicit zero Provisional; two blank ballots are already included.',
        'All 32 units are partially reported and zero complete; the native Election Day complete column nevertheless says 32. This contradiction is preserved, not repaired or interpreted as completed ballot counting.',
        'All 32 unit participation headers and 96 contests reconcile in every reported counting mode.',
        'Separate 871 mail-in/absentee receipts by 8 p.m. are not counted mail 855; the difference 16 remains unexplained and unallocated. The receipt notice supplies no report clock or timezone.',
        'County named write-ins are breakdowns within Write-In Totals, not additional votes; unit named breakdowns are absent, not zero or county names allocated to units.',
        'Native unit Total Votes Cast and Contest Totals rows are absent; derived totals remain separate. Summary and statement clocks remain distinct without an inferred timezone.');
      if (nativeMifflinSummary) reporting.push(
        'Native Ballots Cast - Total 14,439 = 12,017 Election Day + 2,422 Mail + explicit zero Provisional; six blank ballots are already included.',
        'Native registrations zero and printed 0.00% do not establish zero participation; the calculated registration-based rate is unavailable.',
        'All 26 units are partially reported and zero complete; all 104 unit contests and five county contests reconcile without establishing completed ballot counting.',
        'The 85th and 171st Assembly electorates are separate 4,409/10,030-ballot subsets, not the whole county assigned to either contest.',
        'The parent receipt notice literally says Primary Election Day, November 3, 2026 despite the General section; 2,435 receipts are not counted mail 2,422, and the difference 13 remains unexplained.',
        'Not Assigned is nested within Write-In Totals, not additional votes; summary and statement clocks remain distinct without an inferred timezone.');
      if (nativePerrySummary) reporting.push(
        'Native Total Ballots Cast 18,064 / 31,391 registered voters, printed 57.55%; candidate votes are not ballots.',
        'All 31 actual unit participation rows reconcile across 124 unit-contest headers; four All Precincts aggregate headers are separate, not additional units.',
        '31 of 31 reported precincts does not establish completed ballot counting.',
        'Election Day, mail and provisional ballot participation are absent, not zero; ED/MI/PR are candidate-vote columns, and explicit zero PR votes do not establish zero provisional ballots.',
        'The complete scoped query includes both county candidate summaries and all unit participation rows; unresolved unit candidate cells are explicitly outside this query, not imputed or called absent.',
        'Native party labels are absent and not inferred from candidate names; county choice/overvote/undervote accounting reconciles separately.',
        'All 24 entire scanned pages were independently OCRed locally; both PDF text engines are empty. All 31 first participation headers, reporting lines and both whole county summaries were directly visually reviewed.',
        'Unofficial status comes from the declaring county page, not a separate PDF status literal; summary and statement clocks remain distinct without an inferred timezone.');
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
      } else if (nativeLycomingSummary) {
        nativeSourceUpdates = [{ source: 'results', native_update_literal: native.source_update_literal,
          declared_timezone: native.declared_timezone }];
      } else if (['pennsylvania-cumberland-20261106-01', 'pennsylvania-adams-20261106-01',
        'pennsylvania-lebanon-20261106-01', 'pennsylvania-blair-20261106-01',
        'pennsylvania-armstrong-20261106-01', 'pennsylvania-wayne-20261106-01',
        'pennsylvania-jefferson-20261106-01', 'pennsylvania-clarion-20261106-01',
        'pennsylvania-cameron-20261106-01', 'pennsylvania-carbon-20261106-01',
        'pennsylvania-elk-20261106-01', 'pennsylvania-forest-20261106-01',
        'pennsylvania-potter-20261106-01', 'pennsylvania-mifflin-20261106-01',
        'pennsylvania-perry-20261106-01', 'pennsylvania-juniata-20261106-01',
        'pennsylvania-mercer-20261106-01', 'pennsylvania-montour-20261106-01',
        'pennsylvania-columbia-20261106-01'].includes(id)) {
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
      if (nativeCountyHeader || nativePerrySummary)
        quality.push('Result status comes from the declaring county page; the PDF supplies no separate status literal.');
      if (id === 'pennsylvania-montgomery-20261105-01') quality.push(audit.limitations[0], audit.limitations[2]);
      if (id === 'dc-delegate-county-20261105-01') quality.push(
        'Citywide county-equivalent participation, separate from the 435 voting House districts.',
        `${native.unresolved_ballot_accounting_difference} ballots remain unresolved in the separate delegate accounting; not filled or allocated.`,
        audit.limitations[1], audit.limitations[4]);
      observations.push({
        year: 2026, state_code: code, county_id: native.county_fips || `reviewed:${code}:${county}`,
        county, geography_level: native.geography_level || 'county', ballots, denominator,
        ...(nativeVotersCast || nativeCameronSummary || nativeElkSummary || nativeForestSummary || nativePotterSummary || nativeMifflinSummary || nativePerrySummary || nativeColumbiaSummary || nativeGreeneSummary || newSummary
          ? { participation_measure_literal: native.native_participation_measure_literal } : {}),
        ...(nativeLycomingSummary ? { participation_measure_literal: native.native_measure_literal } : {}),
        denominator_basis: 'native_registered_voters', reported_pct: denominator === null ? null : 100 * ballots / denominator,
        native_printed_pct: printedPct, source_status_literal: nativePerrySummary
          ? native.parent_status_literal : nativeCountyHeader
            ? native.native_parent_status_literal : nativeClarionSummary || nativeCameronSummary || nativeCarbonSummary
            || nativeElkSummary || nativeForestSummary || nativePotterSummary || nativeMifflinSummary || nativeColumbiaSummary || nativeGreeneSummary || newSummary
            ? native.source_status_literal : native.native_status_literal ?? native.result_status ?? null,
        reported_units: nativeColumbiaSummary || nativeGreeneSummary || nativeLycomingSummary ? Number(native.reported_precincts) : null,
        total_units: nativeColumbiaSummary || nativeGreeneSummary || nativeLycomingSummary ? Number(native.total_precincts) : null,
        source_rows: nativeColumbiaSummary || nativeGreeneSummary || nativeLycomingSummary ? 1 : 0, maps_approved: false,
        review_id: id, native_record: native, native_source_updates: nativeSourceUpdates,
        source_update_label: updates.join('; ') || 'Not supplied',
        source_reporting_label: reporting.join('; ') || 'Counting completion not established by this participation table.',
        source_url: `${review.base_url}county-participation.csv`, complete_download_url: review.complete_download_url, quality,
      });
    }
  }
  return [...observations, ...loadNewJerseyParticipation(reviews),
    ...loadCaliforniaParticipation(reviews).filter(row => row.geography_level === 'county'),
    ...loadGeorgiaParticipation(reviews).counties, ...loadReviewedMinnesotaParticipation(reviews),
    ...loadLawrenceParticipation(reviews), ...loadHuntingdonParticipation(reviews),
    ...loadReviewedAdditionalPennsylvaniaParticipation(reviews), ...loadReviewedSomersetParticipation(reviews),
    ...loadReviewedSusquehannaParticipation(reviews), ...loadReviewedSullivanWyomingParticipation(reviews),
    ...loadReviewedBedfordNorthumberlandParticipation(reviews), ...loadReviewedUtahParticipation(reviews),
    ...loadReviewedFloridaParticipation(reviews)];
}

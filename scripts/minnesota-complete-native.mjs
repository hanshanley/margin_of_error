import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

export const minnesotaCompleteVersion = '20261110-minnesota-complete-native-03';
const directory = `data/county-source-reviews/${minnesotaCompleteVersion}`;
const digest = body => createHash('sha256').update(body).digest('hex');
const completeDownload = 'https://github.com/hanshanley/margin_of_error/releases/download/'
  + 'voter-minnesota-complete-native-statistics-20261110-03/complete-analysis.zip';

export function loadMinnesotaCompleteNative() {
  const inputs = JSON.parse(readFileSync(`${directory}/inputs.json`));
  if (inputs.version !== directory || Object.keys(inputs.files).length !== 8)
    throw new Error('Changed complete Minnesota sufficient-input scope');
  for (const [name, expected] of Object.entries(inputs.files)) {
    const body = readFileSync(`${directory}/${name}`);
    if (body.length !== expected.bytes || digest(body) !== expected.sha256)
      throw new Error(`Changed complete Minnesota sufficient input: ${name}`);
  }
  const raw = readFileSync(`${directory}/queries.json.gz`);
  if (raw.length !== 174495 || digest(raw) !== '1ba262816564a95f84c7800a68981a83eb968d4d83c06b4736f896d9995da764')
    throw new Error('Changed exact complete Minnesota query');
  const data = JSON.parse(gunzipSync(raw));
  if (data.summary.complete_counties !== 87 || data.summary.reported_statistics !== 4105
    || data.summary.missing_statistics !== 0 || data.summary.qualified_registration_fractions !== 73
    || data.summary.derived_complete_total_number_voted !== 2852618
    || data.summary.independently_printed_state_count !== null)
    throw new Error('Changed complete Minnesota count/registration qualification');
  const reference = { ...data.county_reference,
    geography_scope: 'native_county_statistics', certified_legal_boundaries: false };
  const counties = data.complete_county_decisions.map(row => {
    const facts = row.native_record;
    const native = {
      native_county_id: row.native_county_id, county_name: row.county,
      all_statistics_reported: 'true', registration_fraction_eligible: String(row.registration_fraction_eligible),
      native_numerator_label: 'Total Number Voted', native_status: 'Unofficial Results',
      native_update_clock: '11/10/26 8:08 AM', native_update_timezone: '',
      reported_statistics: String(row.reported_statistics), reference_precincts: String(row.reference_precincts),
      missing_statistics: '0', reported_total_number_voted_subtotal: String(row.complete_total_number_voted),
      complete_total_number_voted: String(row.complete_total_number_voted),
      complete_registered_7am: String(facts.registered_7am),
      complete_registered_election_day: String(facts.registered_election_day),
      complete_derived_7am_plus_election_day_registration: String(row.complete_registration_frame),
      precinct_component_conflicts: String(row.native_component_conflicts),
      precinct_electorate_excesses: String(row.native_electorate_excesses),
      current_native_factual_fields: facts,
    };
    return {
      year: 2026, state_code: 'MN', county: row.county, county_fips: row.county_fips,
      county_id: `additional:MN:followup:${row.native_county_id}`, geography_level: 'county',
      source_snapshot: minnesotaCompleteVersion, source_mode: 'all_method_native_statistics_snapshot',
      ballots: row.complete_total_number_voted, denominator: row.complete_registration_frame,
      reported_pct: row.registration_fraction === null ? null : 100 * row.registration_fraction,
      denominator_basis: 'native_7am_plus_election_day_registrations',
      participation_measure_literal: 'Total Number Voted',
      participation_measure_label: 'Native Total Number Voted (reported participation)',
      native_printed_pct: null, source_status_literal: 'Unofficial Results',
      reported_units: row.reported_statistics, total_units: row.reference_precincts,
      native_partial_subtotal: row.complete_total_number_voted, source_count_qualified: true,
      cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
      maps_approved: true, reference_geometry: reference,
      review_id: `additional:${minnesotaCompleteVersion}`, native_record: native,
      source_update_label: 'Native results-page update11/10/26 8:08 AM; timezone not supplied. Receipt time is separate.',
      source_reporting_label: `${row.reported_statistics}/${row.reference_precincts} native statistics rows reported. `
        + `${row.native_component_conflicts} component conflicts /${row.native_electorate_excesses} precinct electorate excesses retained. `
        + 'All87 counties now have complete source statistics, not certification or independently deduplicated people. '
        + 'The derived full-source sum2,852,618 equals the separately labelled Estimated Voters display, '
        + 'but that display is never used to fill counts. 7AM plus Election Day registrations remain separate from dated register stocks.',
      source_url: 'https://electionresultsfiles.sos.mn.gov/20261103/pctstats.txt',
      complete_download_url: completeDownload, county_parent_complete_download_url: completeDownload,
      quality: [
        'Literal native Total Number Voted, not candidate sums, independently unique people or certified ballots.',
        'All4105 source rows explicitly report;32 reported zeros remain observed zeros, not missing.',
        '73 qualified source-registration fractions;14 counties retain withheld rates. No precinct or demographic rate.',
        'Unchanged verified Census county/native September18,2026 precinct context, not certified legal boundaries.',
      ],
    };
  });
  const parents = new Map(counties.map(row => [row.native_record.native_county_id, row]));
  const precincts = data.all4105_native_precinct_decisions.map(row => ({
    ...parents.get(row.native_county_id),
    unit: row.native_precinct_name, unit_key: row.native_precinct_id,
    unit_kind: 'source_reporting_unit', geography_level: 'source_reporting_unit',
    ballots: row.total_number_voted, denominator: null, reported_pct: null, native_partial_subtotal: null,
    reported_units: 1, total_units: 1, native_record: row.source_record, source_count_qualified: true,
    maps_approved: false, reference_geometry: null, source_rows: 0,
    source_reporting_label: `Literal reported native count; component residual${row.native_component_residual}, `
      + `electorate difference${row.native_electorate_excess}, both unrepaired. `
      + 'All source rows report; no precinct rate or normalized mode. A separate checked layer supplies unchanged native coordinates.',
  }));
  return { counties, precincts, queries: data };
}

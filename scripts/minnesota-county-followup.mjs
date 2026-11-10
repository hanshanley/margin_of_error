import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

export const minnesotaFollowupVersion = '20261110-minnesota-followup-02';
const directory = `data/county-source-reviews/${minnesotaFollowupVersion}`;
const digest = body => createHash('sha256').update(body).digest('hex');
const completeDownload = 'https://github.com/hanshanley/margin_of_error/releases/download/'
  + 'voter-minnesota-native-county-followup-20261110-02/complete-analysis.zip';

export function loadMinnesotaFollowup() {
  const inputs = JSON.parse(readFileSync(`${directory}/inputs.json`));
  if (inputs.version !== directory || Object.keys(inputs.files).length !== 26)
    throw new Error('Changed Minnesota sufficient-input scope');
  for (const [name, pin] of Object.entries(inputs.files)) {
    const body = readFileSync(`${directory}/${name}`);
    if (body.length !== pin.bytes || digest(body) !== pin.sha256)
      throw new Error(`Changed Minnesota sufficient input: ${name}`);
  }
  const raw = readFileSync(`${directory}/queries.json.gz`);
  if (raw.length !== 170283 || digest(raw) !== '2938cc89dd1859fd19b40edbbc4d99b426b2ac3d54809774eeb5076895800455')
    throw new Error('Changed exact Minnesota numerical query');
  const data = JSON.parse(gunzipSync(raw));
  if (data.complete_county_decisions.length !== 87 || data.all4105_native_precinct_decisions.length !== 4105
    || data.summary.complete_counties !== 84 || data.summary.missing_statistics !== 26
    || data.summary.qualified_registration_fractions !== 71
    || data.summary.exact_statewide_total_number_voted !== null)
    throw new Error('Changed Minnesota count, partial-source or registration scope');
  const reference = { ...data.county_reference,
    geography_scope: 'native_county_statistics', certified_legal_boundaries: false };
  const counties = data.complete_county_decisions.map(row => {
    const complete = row.all_statistics_reported;
    return {
      year: 2026, state_code: 'MN', county: row.county,
      county_id: `additional:MN:followup:${row.native_county_id}`, county_fips: row.county_fips,
      geography_level: 'county', source_snapshot: minnesotaFollowupVersion,
      source_mode: 'all_method_native_statistics_snapshot',
      ballots: row.complete_total_number_voted, denominator: row.complete_registration_frame,
      reported_pct: row.registration_fraction === null ? null : 100 * row.registration_fraction,
      denominator_basis: 'native_7am_plus_election_day_registrations',
      participation_measure_kind: 'native_voting_statistics_total',
      participation_measure_literal: 'Total Number Voted',
      participation_measure_label: 'Native Total Number Voted (reported participation)',
      native_printed_pct: null, source_status_literal: 'Unofficial Results',
      reported_units: row.reported_statistics, total_units: row.reference_precincts,
      native_partial_subtotal: row.reported_total_number_voted_subtotal,
      source_count_qualified: complete, cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
      maps_approved: true, reference_geometry: reference,
      review_id: `additional:${minnesotaFollowupVersion}`, native_record: row.native_record,
      source_update_label: 'Official results-page update:11/07/26 5:18 PM; timezone not supplied. '
        + 'The native download receipt is separate, not a report-update clock.',
      source_reporting_label: `${row.reported_statistics}/${row.reference_precincts} native precinct statistics; `
        + `${row.missing_statistics} unreported. `
        + (complete ? 'Complete native statistics, not completed counting or certification. '
          : `Reported subtotal${row.reported_total_number_voted_subtotal} is not a complete county total. `)
        + `${row.native_component_conflicts} component conflicts /${row.native_electorate_excesses} precinct electorate excesses retained. `
        + '7AM plus Election Day registrations are not the separate November2 registered-only snapshot. '
        + 'Roster signatures and three absentee fields are not normalized modes. '
        + 'Separate state-page Estimated Voters2,852,528 is not substituted or used as an exact statewide parent.',
      source_url: 'https://electionresultsfiles.sos.mn.gov/20261103/pctstats.txt',
      complete_download_url: completeDownload, county_parent_complete_download_url: completeDownload,
      quality: [
        'Native Total Number Voted, not candidate sums, independently deduplicated people or certified cast ballots.',
        '84 complete counties and three partial:26 missing precinct rows remain unknown, not observed zero.',
        'Source-registration fractions only where native components and electorate checks pass; not population or demographic turnout.',
        'County IDs join by explicit Census name/case/County-suffix review, not native-ID padding into FIPS.',
        'Checksum-verified2026 Census county context, not certified2026 election-precinct boundaries.',
      ],
    };
  });
  const byCounty = new Map(counties.map(row => [row.native_record.native_county_id, row]));
  const precincts = data.all4105_native_precinct_decisions.map(row => {
    const county = byCounty.get(row.native_county_id);
    const native = row.source_record;
    return {
      ...county, unit: row.native_precinct_name, unit_key: row.native_precinct_id,
      unit_kind: 'source_reporting_unit', geography_level: 'source_reporting_unit',
      ballots: row.total_number_voted, denominator: null, reported_pct: null,
      native_printed_pct: null, native_record: native, native_partial_subtotal: null,
      source_count_qualified: row.reported_statistics, maps_approved: false, reference_geometry: null,
      reported_units: row.reported_statistics ? 1 : 0, total_units: 1,
      source_reporting_label: row.reported_statistics
        ? `Literal native reported Total Number Voted. Component residual${row.native_component_residual}; `
          + `electorate difference${row.native_electorate_excess}, both unrepaired. `
          + 'No precinct geography or analysis fraction is approved; no normalized mode is inferred.'
        : 'Native has_reported_statistics=0: participation remains unknown, even when original numeric fields are zero. '
          + 'No precinct geometry or analysis fraction is approved.',
      quality: [...county.quality, 'Reporting-unit table only; the county Census shape is not precinct geography.'],
    };
  });
  return { counties, precincts, queries: data };
}

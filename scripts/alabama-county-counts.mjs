import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

export const alabamaCountyVersion = '20261110-alabama-native-county-counts-02';
const directory = `data/county-source-reviews/${alabamaCountyVersion}`;
const digest = body => createHash('sha256').update(body).digest('hex');
const completeDownload = 'https://github.com/hanshanley/margin_of_error/releases/download/'
  + 'voter-alabama-native-county-counts-20261110-02/complete-analysis.zip';

export function loadAlabamaCountyCounts() {
  const inputs = JSON.parse(readFileSync(`${directory}/inputs.json`));
  if (inputs.version !== directory || Object.keys(inputs.files).length !== 11)
    throw new Error('Changed Alabama sufficient-input scope');
  for (const [name, pin] of Object.entries(inputs.files)) {
    const body = readFileSync(`${directory}/${name}`);
    if (body.length !== pin.bytes || digest(body) !== pin.sha256)
      throw new Error(`Changed Alabama sufficient input: ${name}`);
  }
  const raw = readFileSync(`${directory}/queries.json.gz`);
  if (raw.length !== 17913 || digest(raw) !== 'c970497bd40c5a6d226c40d51cdfd5e2d2be471e691287550c3fbf7e48854807')
    throw new Error('Changed exact Alabama county-count query');
  const data = JSON.parse(gunzipSync(raw));
  if (data.county_decisions.length !== 67 || data.summary.native_ballots !== 1693621
    || data.summary.native_registered !== 3852947 || data.summary.approved_analysis_rates !== 0
    || data.all2211_county_pair_decisions.length !== 2211)
    throw new Error('Changed Alabama county-count or registration scope');
  const receipts = JSON.parse(readFileSync(`${directory}/source-receipts-without-headers.json`));
  const reference = { ...data.county_reference,
    geography_scope: 'native_county_statistics', certified_legal_boundaries: false };
  const counties = data.county_decisions.map(row => ({
    year: 2026, state_code: 'AL', county: row.county,
    county_id: `additional:AL:${row.native_county_code}`, county_fips: row.county_fips,
    reference_county_name: row.reference_county_name,
    geography_level: 'county', source_snapshot: alabamaCountyVersion,
    source_mode: 'all_method_native_county_statistics',
    ballots: row.ballots, denominator: row.registered, reported_pct: null,
    denominator_basis: 'native_reported_registration_unreviewed',
    participation_measure_kind: 'native_reported_ballots_cast',
    participation_measure_literal: 'Ballots Cast', participation_measure_label: 'Native Ballots Cast',
    native_printed_pct: row.native_printed_pct, source_status_literal: null,
    reported_units: row.source_reported_units, total_units: row.source_total_units,
    source_count_qualified: true, cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
    registration_frame_qualified: false, maps_approved: true, reference_geometry: reference,
    review_id: `additional:${alabamaCountyVersion}`,
    native_record: { ...row.legacy_record,
      workbook_statistics: row.native_workbook_statistics, source_factual_fields: row.native_factual_fields },
    source_update_literal: row.source_update_literal, source_update_timezone: null,
    source_update_label: `${row.source_update_literal}; source timezone not supplied.`,
    source_reporting_label: `${row.source_reported_units}/${row.source_total_units} native precincts reported. `
      + 'All 67 native county Ballots Cast sum to the separately reported source state count1,693,621. '
      + 'Native registrations and printed percentages are retained, but all analysis rates remain withheld. '
      + 'The prior source review is unofficial; reporting is not certification or independently deduplicated people. '
      + 'County source codes are election ordinals, not FIPS. No new precinct count or geometry is inferred.',
    source_url: receipts[`official-county-${row.native_county_code}`].url,
    complete_download_url: completeDownload, county_parent_complete_download_url: completeDownload,
    quality: [
      'Literal native Ballots Cast, not candidate sums, unique people or certified final turnout.',
      'All 67 county names match the complete hash-verified2026 Census county reference; no aliases or repairs.',
      'Native source clocks and registrations are retained without qualifying an analysis fraction.',
      'County context only, not precinct geography or demographic participation.',
    ],
  }));
  return { counties, queries: data };
}

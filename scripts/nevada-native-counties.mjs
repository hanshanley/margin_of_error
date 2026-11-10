import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

export const nevadaCountyVersion = '20261110-nevada-native-counties-01';
const directory = `data/county-source-reviews/${nevadaCountyVersion}`;
const digest = body => createHash('sha256').update(body).digest('hex');
const completeDownload = 'https://github.com/hanshanley/margin_of_error/releases/download/'
  + 'voter-nevada-native-counties-20261110-01/complete-analysis.zip';

export function loadNevadaNativeCounties() {
  const inputs = JSON.parse(readFileSync(`${directory}/inputs.json`));
  if (inputs.version !== directory || Object.keys(inputs.files).length !== 18)
    throw new Error('Changed Nevada sufficient-input scope');
  for (const [name, expected] of Object.entries(inputs.files)) {
    const body = readFileSync(`${directory}/${name}`);
    if (body.length !== expected.bytes || digest(body) !== expected.sha256)
      throw new Error(`Changed Nevada sufficient input: ${name}`);
  }
  const raw = readFileSync(`${directory}/queries.json.gz`);
  if (raw.length !== 5491 || digest(raw) !== '6f5619ceea6ffdb6669f5cf851bb1647168ba421aed3a5084c4354ef1f2fca94')
    throw new Error('Changed complete Nevada county query');
  const data = JSON.parse(gunzipSync(raw));
  if (data.county_decisions.length !== 17 || data.summary.observed_counties !== 4
    || data.summary.unknown_counties !== 13 || data.summary.state_ballots !== null
    || data.summary.approved_analysis_rates !== 0 || data.all136_county_pairs.length !== 136)
    throw new Error('Changed Nevada source scope or missingness');
  const reference = { ...data.county_reference, certified_election_boundaries: false };
  const counties = data.county_decisions.map(row => {
    const native = row.native_record;
    return {
      year: 2026, state_code: 'NV', county: row.county, county_fips: row.county_fips,
      county_id: row.county === 'Washoe' ? 'additional:NV:Washoe' : `additional:NV:${row.county_fips}`,
      reference_county_name: row.reference_county_name, geography_level: 'county',
      source_snapshot: nevadaCountyVersion, source_mode: 'all_method_native_county_snapshot',
      ballots: row.source_count, denominator: row.registered, reported_pct: null,
      denominator_basis: 'native_reported_registration_unreviewed',
      participation_measure_literal: native?.source_measure_literal ?? null,
      participation_measure_label: 'Native county participation count',
      native_printed_pct: native?.native_printed_pct ?? null,
      native_record: native, source_rows: 0, reported_units: null, total_units: null,
      source_count_qualified: row.observed, maps_approved: true, reference_geometry: reference,
      cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
      registration_frame_qualified: false, source_update_timezone: null,
      source_update_literal: native?.source_clock_literal ?? null,
      source_update_label: native ? `${native.source_clock_literal}; ${native.source_clock_kind}; timezone not supplied.`
        : 'No qualified native participation snapshot supplied for this county.',
      source_status_literal: native?.source_status_literal ?? null,
      source_url: native?.source_url ?? completeDownload,
      complete_download_url: completeDownload, county_parent_complete_download_url: completeDownload,
      review_id: `additional:${nevadaCountyVersion}`,
      source_reporting_label: native
        ? 'A distinct unofficial county source snapshot; four observed counties and 13 unknown counties. '
          + 'Different clocks are not summed into a statewide result. Native registrations and printed percentages '
          + 'remain separate; all analysis rates are withheld. Counting groups are not precincts. '
          + (row.county === 'Churchill' ? 'The separate House District4 Times Cast1/register0/N/A remains literal, '
            + 'not a county denominator or a repaired count. ' : '')
        : 'County reference context only. No qualified participation count, registration or rate is supplied; '
          + 'unknown is not zero, candidate votes, or an allocated state estimate.',
      quality: [
        'Literal native county source counts, not independently unique people or certified final turnout.',
        'All 17 unchanged 2026 Census county references are retained; only four have participation observations.',
        'No new precinct data, demographic allocation, statewide total or inferred rate.',
      ],
    };
  });
  return { counties, queries: data };
}

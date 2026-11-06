import { readFileSync } from 'node:fs';
import { basename, resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { parse } from 'csv-parse/sync';

const json = path => JSON.parse(readFileSync(path, 'utf8'));
const compressed = path => JSON.parse(gunzipSync(readFileSync(path)).toString('utf8'));
const csv = path => parse(readFileSync(path, 'utf8'), { columns: true, bom: true, skip_empty_lines: true });

export function participationCount(value) {
  if (value === null || value === undefined || value === '') return null;
  if (!/^\d+$/.test(String(value)) || !Number.isSafeInteger(Number(value)))
    throw new Error(`Invalid native participation count: ${value}`);
  return Number(value);
}

function observation(review, file, code, name, identity, native, values = {}) {
  if (native.year != null && Number(native.year) !== 2026
    || native.state_code != null && native.state_code !== code)
    throw new Error(`Mismatched participation snapshot: ${code} / ${name}`);
  const ballots = participationCount(values.ballots), denominator = participationCount(values.denominator);
  const rate = values.reported_pct ?? null;
  if (rate !== null && (!Number.isFinite(rate) || rate < 0 || rate > 100 || !denominator || ballots === null))
    throw new Error(`Invalid reviewed participation fraction: ${code} / ${name}`);
  return {
    year: 2026, state_code: code, county_id: `additional:${code}:${identity}`, county: name,
    geography_level: 'county', ballots, denominator, denominator_basis: 'native_registered_voters',
    reported_pct: rate, native_printed_pct: null, source_status_literal: null,
    reported_units: null, total_units: null, source_rows: 0, maps_approved: false,
    review_id: `additional:${basename(review.data_directory)}`, native_record: native,
    source_update_label: 'Not supplied in this participation table',
    source_reporting_label: 'Counting completion and certification are not established by these observations.',
    source_url: review.base_url + file, complete_download_url: review.complete_download_url,
    quality: ['Frozen native participation observations, not candidate votes, final turnout or demographic rates.',
      'No new county or precinct map joins are approved. Missing counts and withheld rates are not zero.',
      ...(Array.isArray(native.quality_flags) ? native.quality_flags : native.quality_flags ? [native.quality_flags] : [])],
    ...values, ballots, denominator, reported_pct: rate,
  };
}

export function loadAdditionalParticipation() {
  const counties = [], precincts = [], nongeographic = [];
  const pointer = json('public/precinct-results.json');
  const reviews = pointer.source_reviews.map(path => json(path));
  const source = (code, suffix) => {
    const matches = reviews.filter(row => row.year === 2026 && row.state_code === code
      && row.data_directory.endsWith(suffix));
    if (matches.length !== 1) throw new Error(`Missing or duplicated participation source: ${code}`);
    return matches[0];
  };
  for (const code of ['AL', 'AZ']) {
    const review = source(code, `${code}-2026-native-counts`);
    const rows = csv(resolve(review.data_directory, 'county-participation.csv'));
    if (rows.length !== (code === 'AL' ? 67 : 15)) throw new Error(`Incomplete ${code} county inventory`);
    for (const native of rows) counties.push(observation(review, 'county-participation.csv',
      code, native.county, native.county_code, native, {
        ballots: native.ballots, denominator: native.registered_voters,
        native_printed_pct: code === 'AL' ? native.source_reported_turnout_percent
          : native.native_reported_fraction ? `${native.native_reported_fraction} (native fraction, not percent)` : null,
        source_update_label: native.last_updated_native || 'See frozen native source package',
        source_reporting_label: 'Native registrations are retained; electorate definitions and analysis rates remain unreviewed.',
      }));
  }
  const arkansas = source('AR', 'AR-2026-native-counts');
  const arRoot = resolve(arkansas.data_directory);
  const arNative = compressed(resolve(arRoot, 'native-source/originals/official-full-election-json.gz'));
  const arNames = new Map(csv(resolve(arRoot, 'precinct-participation.csv'))
    .map(row => [row.county_code, row.county]));
  const arRows = Object.entries(arNative.TurnoutData.Locations);
  if (arRows.length !== 75) throw new Error('Incomplete Arkansas county participation');
  for (const [id, native] of arRows) {
    if (native.LocationID !== id || !arNames.has(id)) throw new Error('Unmatched Arkansas county identity');
    counties.push(observation(arkansas, 'native-source/originals/official-full-election-json.gz',
      'AR', arNames.get(id), id, Object.fromEntries(Object.entries(native).filter(([key]) => key !== 'Locations')), {
        ballots: native.TotalBallotsCast, denominator: native.RegisteredVoters,
        native_printed_pct: native.VotePercent == null ? null : `${native.VotePercent}%`,
        source_reporting_label: `${native.PrecinctsReporting} of ${native.TotalPrecincts} source precincts reporting. `
          + 'Native source percentages are separate from withheld analysis rates.',
      }));
  }
  const virginia = source('VA', 'VA-2026-native-locality-counts');
  const vaRoot = resolve(virginia.data_directory), vaAudit = json(resolve(vaRoot, 'counts-review.json'));
  const vaNames = new Map(csv(resolve(vaRoot, 'locality-house-counts.csv'))
    .map(row => [row.locality_code, row.locality]));
  if (vaAudit.locality_versions.length !== 133) throw new Error('Incomplete Virginia locality participation');
  for (const native of vaAudit.locality_versions) {
    const name = vaNames.get(native.locality_code);
    if (!name) throw new Error('Unmatched Virginia locality identity');
    counties.push(observation(virginia, 'counts-review.json', 'VA', name, native.locality_code, native, {
      ballots: native.ballots_cast, denominator: null,
      geography_level: name.endsWith(' CITY') ? 'independent_city' : 'county',
      source_update_label: native.as_of,
      source_reporting_label: 'Native whole-locality ballots, not the incomplete precinct voter-turnout sum. '
        + 'No locality registration denominator or inferred rate is supplied here; county early/mail residuals stay unallocated.',
    }));
  }
  const localReviews = json('public/participation-source-reviews.json').reviews;
  for (const [id, code, ballotField] of [
    ['iowa-linn-20261105-01', 'IA', 'ballots_total'],
    ['kentucky-daviess-20261105-01', 'KY', 'ballots_cast_total'],
  ]) {
    const review = localReviews.find(row => row.id === id);
    if (!review) throw new Error(`Missing participation review: ${id}`);
    for (const native of csv(resolve(review.data_directory, 'county-participation.csv')))
      counties.push(observation(review, 'county-participation.csv', code, native.county, native.county, native, {
        ballots: native[ballotField], denominator: native.registered_voters_total,
        reported_pct: code === 'IA' ? Number(native.registered_turnout_percent) : null,
        native_printed_pct: native.native_registered_turnout_percent ? `${native.native_registered_turnout_percent}%` : null,
        source_reporting_label: native.native_reporting_counter || native.quality_flags,
      }));
  }
  for (const [code, suffix] of [
    ['MN', '20261105-expansion-01'], ['ND', '20261105-north-dakota-02'],
    ['ID', '20261105-idaho-01'], ['VT', '20261105-vermont-03'], ['RI', '20261105-rhode-island-02'],
  ]) {
    const review = pointer.additional_snapshots.find(row => row.data_directory.endsWith(suffix));
    if (!review) throw new Error(`Missing participation snapshot: ${suffix}`);
    const file = review.participation_file || 'participation.json.gz';
    const rows = compressed(resolve(review.data_directory, file));
    for (const native of rows) {
      const municipal = code === 'VT' || code === 'RI';
      const name = code === 'ND' ? native.county_name : municipal ? native.town || native.locality : native.county;
      const identity = municipal ? native.town_id ?? native.source_locality_id : native.county_code ?? native.county;
      if (!name || identity == null) throw new Error(`Missing ${code} participation identity`);
      const common = observation(review, file, code, name, identity, native, {
        ballots: native.ballots,
        denominator: native.registered_voters ?? native.registered ?? native.denominator,
        reported_pct: code === 'VT' ? native.registered_turnout_pct : native.reported_pct,
        denominator_basis: native.denominator_basis || (code === 'ND' ? 'electorate_not_supplied' : 'native_registered_voters'),
        geography_level: municipal ? 'municipality' : 'county',
        source_update_label: native.source_updated || 'See frozen source snapshot',
        source_reporting_label: [native.basis || native.denominator_basis || native.denominator,
          ...(native.quality_flags || []), native.quality].filter(Boolean).join('; '),
      });
      if (code === 'RI' && native.locality === 'Federal') {
        nongeographic.push({ ...common, geography_level: 'nongeographic_reporting_unit' });
        continue;
      }
      if (municipal) counties.push(common);
      else {
        precincts.push({ ...common, unit: native.precinct_name || native.precinct,
          unit_key: native.key, unit_kind: code === 'ID' ? native.reporting_unit_kind : 'source_reporting_unit' });
        if (!counties.some(row => row.county_id === common.county_id)) counties.push({
          ...common, ballots: null, denominator: null, reported_pct: null, native_record: null,
          quality: common.quality.slice(0, 2),
          source_reporting_label: 'No independently supplied county total in this imported reporting-unit table. '
            + 'Use the reporting-unit selector or complete data; rows are not summed or treated as a full-county total.',
        });
      }
    }
  }
  const michigan = localReviews.find(row => row.id === 'michigan-native-counties-20261105-01');
  if (!michigan) throw new Error('Missing Michigan participation source');
  for (const native of csv(resolve(michigan.data_directory, 'precinct-participation.csv'))) {
    const common = observation(michigan, 'precinct-participation.csv', 'MI', native.county,
      native.county_code, native, {
        ballots: native.ballots_cast_total, denominator: native.registered_voters_total,
        native_printed_pct: native.native_turnout_percent ? `${native.native_turnout_percent}%` : null,
        source_status_literal: native.native_reporting_status,
        source_reporting_label: native.quality_flags,
      });
    precincts.push({ ...common, unit: native.precinct, unit_key: native.source_row_id,
      unit_kind: 'source_reporting_unit' });
    if (!counties.some(row => row.county_id === common.county_id)) counties.push({
      ...common, ballots: null, denominator: null, reported_pct: null, native_printed_pct: null, native_record: null,
      quality: common.quality.slice(0, 2),
      source_reporting_label: 'Separate native reporting-unit observations; unit scope is not reconciled. '
        + 'No county total or registration sum is inferred.',
    });
  }
  const seen = new Set(), unitSeen = new Set();
  for (const row of counties) {
    if (seen.has(row.county_id)) throw new Error(`Duplicate participation locality: ${row.county_id}`);
    seen.add(row.county_id);
    row.source_rows = precincts.filter(unit => unit.county_id === row.county_id).length;
  }
  for (const row of precincts) {
    const id = `${row.county_id}|${row.unit_key}`;
    if (!row.unit_key || unitSeen.has(id)) throw new Error(`Duplicate participation reporting unit: ${id}`);
    unitSeen.add(id);
  }
  return { counties, precincts, nongeographic };
}

import { readFileSync } from 'node:fs';
import { basename, dirname, resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { parse } from 'csv-parse/sync';
import { loadNativeCountyParents } from './native-county-parents.mjs';
import { loadMichiganCountyParents } from './michigan-county-parents.mjs';
import { loadMarylandCardCounts } from './maryland-county-cards.mjs';
import { loadIndianaVoterStatistics } from './indiana-voter-statistics.mjs';
import { loadWestVirginiaCountyModes } from './west-virginia-county-modes.mjs';

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

export function loadAdditionalParticipation({ nativeCountyParents = false } = {}) {
  const counties = [], precincts = [], nongeographic = [];
  const pointer = json('public/precinct-results.json');
  const reviews = pointer.source_reviews.map(path => {
    const review = json(path);
    return { ...review, data_directory: review.data_directory || dirname(path) };
  });
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
  const florida = { ...source('FL', 'FL-2026-MON'),
    base_url: 'https://raw.githubusercontent.com/hanshanley/margin_of_error/d36753726cccfa696fc776328c22d9c5120ffa3d/data/precinct-source-reviews/20261105/FL-2026-MON/' };
  const flRows = compressed(resolve(florida.data_directory, 'participation.json.gz'));
  if (flRows.length !== 1 || flRows[0].source_unit_kind !== 'county')
    throw new Error('Invalid Monroe county participation scope');
  for (const native of flRows) counties.push(observation(florida, 'participation.json.gz',
    'FL', native.county_name, native.county_fips, native, {
      ballots: native.ballots, denominator: native.registered,
      native_printed_pct: native.source_reported_percent,
      source_reporting_label: native.basis + ' ' + native.denominator_scope
        + '. County counts only; no precinct denominators or analysis fraction are approved.',
    }));
  const missouri = { ...source('MO', 'MO-2026-CHRISTIAN'),
    base_url: 'https://raw.githubusercontent.com/hanshanley/margin_of_error/fe2e67af2c3e3181d46589fb18ede50e6a5716b8/data/precinct-source-reviews/20261105/MO-2026-CHRISTIAN/' };
  counties.push(observation(missouri, 'audit.json', 'MO', missouri.county_name,
    missouri.county_fips, json(resolve(missouri.data_directory, 'audit.json')), {
      ballots: missouri.county_ballots, denominator: missouri.county_registered,
      native_printed_pct: missouri.county_source_reported_percent,
      source_reporting_label: missouri.notes,
    }));
  const wyoming = source('WY', 'WY-2026-native-counts');
  const wyAudit = json(resolve(wyoming.data_directory, 'counts-review.json'));
  if (wyAudit.counties.length !== 23 || wyAudit.counties.some(row =>
    row.printed_county_ballots !== row.precinct_ballots))
    throw new Error('Unreconciled Wyoming county ballot counts');
  for (const native of wyAudit.counties) counties.push(observation(wyoming, 'counts-review.json',
    'WY', native.county, native.county, native, {
      ballots: native.printed_county_ballots, denominator: null,
      denominator_basis: 'electorate_not_supplied',
      source_reporting_label: 'Native county ballots independently reconcile to the separate precinct ballot counts. '
        + 'Registrations and rates are not supplied. The retained Washakie candidate-category conflict '
        + 'does not change reconciled ballot totals; no candidate categories are repaired or allocated.',
    }));
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
  const oregon = localReviews.find(row => row.id === 'oregon-counties-20261106-01');
  if (!oregon) throw new Error('Missing Oregon county participation review');
  const orRows = csv(resolve(oregon.data_directory, 'county-participation.csv'));
  const orHeaders = csv(resolve(oregon.data_directory, 'statewide-observations.csv'));
  if (orRows.length !== 36 || new Set(orRows.map(row => row.native_county_id)).size !== 36
    || orHeaders.length !== 2)
    throw new Error('Incomplete Oregon county participation');
  for (const native of orRows) counties.push(observation(oregon, 'county-participation.csv',
    'OR', native.county, native.native_county_id, native, {
      ballots: native.ballots_counted, denominator: native.active_registered_voters,
      denominator_basis: 'native_active_registered_voters',
      native_printed_pct: native.native_reported_percent,
      source_status_literal: native.source_status_literal,
      source_update_label: native.source_updated_at + ' (native county timestamp; timezone not supplied). '
        + 'Separate statewide headers: ' + orHeaders.map(row => `${row.source_file}: ${row.source_updated_at}`).join('; '),
      source_reporting_label: native.qualification + ' The complete download retains every native record '
        + 'and both independent statewide observations. Analysis fraction remains withheld.',
    }));
  const washoe = localReviews.find(row => row.id === 'nevada-washoe-participation-20261106-01');
  if (!washoe) throw new Error('Missing Washoe county participation review');
  const nvRows = csv(resolve(washoe.data_directory, 'county-participation.csv'));
  if (nvRows.length !== 1 || nvRows[0].county !== 'Washoe')
    throw new Error('Invalid Washoe county participation scope');
  for (const native of nvRows) counties.push(observation(washoe, 'county-participation.csv',
    'NV', native.county, native.county, native, {
      ballots: native.ballots_cast, denominator: native.registered_voters,
      native_printed_pct: native.native_reported_percent,
      source_status_literal: native.source_status_literal,
      source_update_label: native.source_generated_at + ' (native PDF generation; timezone not supplied)',
      source_reporting_label: native.qualification + ' The complete download retains all six counting groups, '
        + 'separate House candidate counts and native under/overvote accounting. Analysis fraction remains withheld.',
    }));
  const washington = localReviews.find(row => row.id === 'washington-counties-20261106-01');
  if (!washington) throw new Error('Missing Washington county participation review');
  const waRows = csv(resolve(washington.data_directory, 'county-participation.csv'));
  if (waRows.length !== 39) throw new Error('Incomplete Washington county participation');
  for (const native of waRows) counties.push(observation(washington, 'county-participation.csv',
    'WA', native.county, native.county_id, native, {
      ballots: native.ballots_cast, denominator: native.registered_voters,
      reported_pct: Number(native.registered_turnout_percent),
      source_status_literal: 'Native isOfficialResults=false (unofficial)',
      source_update_label: `County as-of: ${native.source_as_of}; last updated: ${native.source_last_updated}; `
        + `published: ${native.source_publish_date}; separate state-locality as-of: ${native.state_locality_source_as_of}; `
        + `state-locality last updated: ${native.state_locality_source_last_updated}`,
      source_reporting_label: native.quality_flags + ' The separate native statewide ballot field is zero, '
        + 'not this county total. Calculated ballots/native-registration fraction; counting completion is not established. '
        + 'All 9,588 native unit rows remain in complete downloads, without assigning county ballots to units.',
    }));
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
  for (const parent of nativeCountyParents ? loadNativeCountyParents(pointer) : []) {
    const index = counties.findIndex(row => row.state_code === parent.code
      && row.county_id === `additional:${parent.code}:${parent.identity}`);
    if (index < 0 || counties[index].ballots !== null)
      throw new Error('Native county parent must replace exactly one empty reporting-unit container');
    counties[index] = observation(parent.snapshot, parent.sourceFile, parent.code,
      parent.county, parent.identity, parent.native, {
        ballots: parent.ballots, denominator: parent.denominator, reported_pct: parent.reported_pct,
        denominator_basis: parent.denominator_basis, native_printed_pct: parent.native_printed_pct ?? null,
        source_update_label: parent.source_update_label, source_status_literal: parent.source_status_literal,
        reported_units: parent.reported_units, total_units: parent.total_units,
        source_reporting_label: parent.source_reporting_label,
        maps_approved: true, county_fips: parent.fips, reference_geometry: parent.reference,
        participation_measure_label: 'Native whole-county ballots reported',
        county_parent_complete_download_url: '/participation-county-parents/20261109-01/complete-analysis.zip',
        quality: ['Whole-county native parent, not candidate votes or a reporting-unit sum.',
          'Complete native county inventory matches the separately checksum-verified 2026 Census county reference; not certified election-precinct boundaries.',
          'Unofficial source snapshot, not final, CPS, demographic or precinct turnout.',
          ...parent.flags],
      });
  }
  for (const parent of nativeCountyParents ? loadMichiganCountyParents() : []) {
    const index = counties.findIndex(row => row.county_id === `additional:MI:${parent.identity}`);
    if (index < 0 || counties[index].ballots !== null)
      throw new Error('Michigan native parent must replace exactly one empty county container');
    counties[index] = observation(parent.snapshot, parent.sourceFile, 'MI',
      parent.county, parent.identity, parent.native, {
        ballots: parent.ballots, denominator: null, denominator_basis: parent.denominator_basis,
        reported_pct: null, native_printed_pct: parent.native_printed_pct,
        source_update_label: parent.source_update_label, source_status_literal: parent.source_status_literal,
        reported_units: parent.reported_units, total_units: parent.total_units,
        source_reporting_label: parent.source_reporting_label,
        maps_approved: true, county_fips: parent.fips, reference_geometry: parent.reference,
        participation_measure_label: 'Native whole-county ballots reported',
        county_parent_complete_download_url: '/participation-county-parents/20261109-02/complete-analysis.zip',
        quality: ['Explicit native county ballot parent, not candidate votes or a reporting-unit sum.',
          'Only Bay and Isabella are observed; the other 81 Michigan counties remain missing, not zero.',
          'Separately checksum-verified 2026 Census county references, not certified election-precinct boundaries.',
          'Unofficial captured source clocks; no county, population or demographic rate is inferred.',
          ...parent.flags],
      });
  }
  for (const row of nativeCountyParents ? loadMarylandCardCounts() : []) {
    const snapshot = { data_directory: 'data/county-source-reviews/20261109-maryland-cards-01',
      base_url: '', complete_download_url: row.complete_download_url };
    counties.push(observation(snapshot, '', 'MD', row.county, row.county_fips, row.native_record, {
      ballots: row.cards_cast, denominator: null, denominator_basis: 'source_electorate_not_qualified',
      reported_pct: null, maps_approved: true, county_fips: row.county_fips,
      reference_geometry: row.reference_geometry,
      participation_measure_label: row.participation_measure_label,
      source_url: row.source_url, source_update_label: row.source_update_label,
      source_status_literal: 'UNOFFICIAL Cards Cast; not certified unique voters or ballots',
      source_reporting_label: row.source_reporting_label,
      native_printed_pct: `${row.native_record.native_percentage} (native card-report field; analysis rate withheld)`,
      county_parent_complete_download_url: row.complete_download_url,
      cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
      quality: ['Native Cards Cast, not qualified cast ballots or unique voters.',
        'All 24 county equivalents join the checksum-verified 2026 Census county reference; Baltimore city stays separate.',
        'The explicit Saint Mary\'s / St. Mary\'s alias retains the unchanged native label.',
        'No demographic allocation, qualified denominator, turnout rate, precinct records or final-counting claim.'],
    }));
  }
  const indiana = nativeCountyParents ? loadIndianaVoterStatistics() : { counties: [], precincts: [] };
  for (const row of indiana.counties) {
    const snapshot = { data_directory: 'data/county-source-reviews/20261109-indiana-voter-statistics-01',
      base_url: '', complete_download_url: row.complete_download_url };
    counties.push(observation(snapshot, '', 'IN', row.county, row.county_fips, row.native_record, {
      ballots: row.source_count, denominator: null, denominator_basis: 'source_electorate_not_qualified',
      reported_pct: null, maps_approved: true, county_fips: row.county_fips,
      reference_geometry: row.reference_geometry, participation_measure_label: row.participation_measure_label,
      source_url: row.source_url, source_update_label: row.source_update_label,
      source_status_literal: row.source_status_literal, source_reporting_label: row.source_reporting_label,
      county_parent_complete_download_url: row.complete_download_url,
      cast_ballot_count_qualified: row.cast_ballot_count_qualified,
      unique_voter_count_qualified: false, source_count_qualified: row.source_count_qualified,
      selected_source_kind: row.selected_source_kind,
      statewide_statistics_native_record: row.statewide_statistics_native_record,
      source_candidate_votes_not_participation: row.source_candidate_votes_not_participation,
      quality: row.quality,
    }));
  }
  for (const row of indiana.precincts) {
    const snapshot = { data_directory: 'data/county-source-reviews/20261109-indiana-voter-statistics-01',
      base_url: '', complete_download_url: row.complete_download_url };
    precincts.push(observation(snapshot, '', 'IN', row.county, row.county_fips, row.native_record, {
      geography_level: 'reporting_unit', unit: row.unit, unit_key: row.unit_key,
      unit_kind: 'source_reporting_unit', ballots: row.ballots, denominator: null,
      denominator_basis: 'source_electorate_not_qualified', reported_pct: null,
      maps_approved: row.match_status === 'matched', county_fips: row.county_fips,
      match_status: row.match_status, geometry_withheld_reason: row.geometry_withheld_reason,
      participation_measure_label: 'Native Ballots Cast', source_url: row.source_url,
      source_update_label: row.source_update_label, source_reporting_label: row.source_reporting_label,
      quality: [row.source_reporting_label, row.boundary_label, row.rate_withheld_reason,
        ...(row.geometry_withheld_reason ? [row.geometry_withheld_reason] : [])],
    }));
  }
  const countyFrames = {};
  if (nativeCountyParents) {
    const westVirginia = loadWestVirginiaCountyModes();
    const imported = row => observation({
      data_directory: 'data/county-source-reviews/20261109-west-virginia-modes-01',
      base_url: '', complete_download_url: row.complete_download_url,
    }, '', 'WV', row.county, row.county_fips, row.native_record || {}, {
      ballots: row.source_count, denominator: null, denominator_basis: 'source_electorate_not_qualified',
      reported_pct: null, maps_approved: true, county_fips: row.county_fips,
      reference_geometry: row.reference_geometry, native_record: row.native_record,
      participation_measure_label: row.participation_measure_label,
      source_mode: row.mode || 'all_method_county_snapshot',
      native_party_counts: row.native_party_counts,
      source_url: row.source_url, source_update_label: row.source_update_label,
      source_status_literal: row.source_status_literal, source_reporting_label: row.source_reporting_label,
      cast_ballot_count_qualified: row.cast_ballot_count_qualified,
      unique_voter_count_qualified: false, source_count_qualified: row.source_count_qualified,
      quality: [row.source_reporting_label,
        'Full 55-county identities match the separately checksum-verified 2026 Census reference; not precincts.',
        'No mode addition, candidate-choice inference, demographic allocation or analysis rate.'],
    });
    counties.push(...westVirginia.counties.map(imported));
    countyFrames.WV = Object.fromEntries(Object.entries(westVirginia.county_frames)
      .map(([mode, rows]) => [mode, rows.map(imported)]));
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
  return { counties, precincts, nongeographic, ...(nativeCountyParents ? { county_frames: countyFrames } : {}) };
}

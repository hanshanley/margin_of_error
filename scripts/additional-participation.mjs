import { readFileSync } from 'node:fs';
import { basename, dirname, resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { parse } from 'csv-parse/sync';
import { loadNativeCountyParents } from './native-county-parents.mjs';
import { loadMichiganCountyParents } from './michigan-county-parents.mjs';
import { loadMarylandCardCounts } from './maryland-county-cards.mjs';
import { loadIndianaVoterStatistics } from './indiana-voter-statistics.mjs';
import { loadWestVirginiaCountyModes } from './west-virginia-county-modes.mjs';
import { loadColoradoCountyReturns } from './colorado-returned-counties.mjs';
import { loadHawaiiAdministrations } from './hawaii-administrations.mjs';
import { loadProviderCountyFrames } from './provider-county-frames.mjs';
import { loadConnecticutTowns } from './connecticut-town-counts.mjs';
import { loadMaineLocalityActivity } from './maine-locality-activity.mjs';
import { loadIllinoisCountyContext } from './illinois-county-context.mjs';
import { loadNewHampshireCityExtension } from './new-hampshire-city-extension.mjs';
import { massachusettsVersion } from './massachusetts-native-counts.mjs';
import { loadMassachusettsCityReference, massachusettsCityReferenceVersion } from './massachusetts-city-precinct-reference.mjs';

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
  if (nativeCountyParents) {
    for (const row of loadColoradoCountyReturns().counties) counties.push(observation({
      data_directory: 'data/county-source-reviews/20261109-colorado-returned-01',
      base_url: '', complete_download_url: row.complete_download_url,
    }, '', 'CO', row.county, row.county_fips, row.native_record, {
      ballots: row.source_count, denominator: null, denominator_basis: 'county_electorate_not_supplied',
      reported_pct: null, maps_approved: true, county_fips: row.county_fips,
      reference_geometry: row.reference_geometry, native_record: row.native_record,
      participation_measure_label: row.participation_measure_label,
      source_mode: 'native_all_returned_and_processed',
      source_count_qualified: true, cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
      source_url: row.source_url, source_update_label: row.source_update_label,
      source_status_literal: row.source_status_literal, source_reporting_label: row.source_reporting_label,
      quality: [row.source_reporting_label,
        'Separate exact county identity review against the complete 2026 Census reference; not precincts.',
        'Older provider mail-returned and early-in-person observations are not overwritten or relabelled.'],
    }));
  }
  if (nativeCountyParents) {
    for (const row of loadHawaiiAdministrations().administrations) counties.push(observation({
      data_directory: 'data/county-source-reviews/20261109-hawaii-administrations-01',
      base_url: '', complete_download_url: row.complete_download_url,
    }, '', 'HI', row.county, row.source_administration_id, row.native_record, {
      geography_level: 'election_administration', county_fips: null,
      source_administration_id: row.source_administration_id, component_county_fips: row.component_county_fips,
      ballots: row.source_count, denominator: null, denominator_basis: 'source_electorate_not_qualified',
      reported_pct: null, maps_approved: true, reference_geometry: row.reference_geometry,
      participation_measure_label: row.participation_measure_label, source_mode: 'native_TOTAL_TURNOUT',
      source_count_qualified: true, cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
      source_url: row.source_url, source_update_label: row.source_update_label,
      source_status_literal: row.source_status_literal, source_reporting_label: row.source_reporting_label,
      quality: [row.source_reporting_label,
        'Four election administrations use five full 2026 Census county components; Maui includes Kalawao.',
        'Original statewide/unit/report discrepancies and separate clocks survive; no rates or count allocation.'],
    }));
  }
  if (nativeCountyParents) {
    for (const row of loadConnecticutTowns().towns) counties.push(observation({
      data_directory: 'data/county-source-reviews/20261110-connecticut-towns-01',
      base_url: '', complete_download_url: row.complete_download_url,
    }, '', 'CT', row.county, row.source_administration_id, row.native_record, {
      geography_level: 'municipality', county_fips: null,
      source_administration_id: row.source_administration_id, source_town_id: row.source_town_id,
      source_election_id: row.source_election_id, native_election_id_qualified: true,
      ballots: row.source_count, denominator: null, denominator_basis: 'source_electorate_not_qualified',
      reported_pct: null, native_printed_pct: row.native_printed_pct,
      maps_approved: true, reference_geometry: row.reference_geometry,
      participation_measure_label: row.participation_measure_label, source_mode: 'native_town_VV',
      source_count_qualified: true, cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
      source_url: row.source_url, source_update_label: row.source_update_label,
      source_status_literal: row.source_status_literal, source_reporting_label: row.source_reporting_label,
      quality: [row.source_reporting_label,
        'Town observations, not county parents or precinct records. Native Total is separate, never added again.',
        'Contextual municipality reference year is 2024, not certified 2026 election geography.'],
    }));
  }
  if (nativeCountyParents) {
    const nh = loadNewHampshireCityExtension();
    const review = { data_directory: 'data/county-source-reviews/20261110-new-hampshire-cities-02',
      base_url: '', complete_download_url: nh.complete_download_url };
    const cityIdentity = row => `city:${row.reference_key}`;
    const reporting = {
      Manchester: 'Derived sum of all 12 printed native ward Total Ballots Cast fields, not a separately printed city parent. '
        + 'Ward7 prints 2712 while Election Day2694 + absentee103 =2797; the 85-ballot discrepancy is retained. '
        + 'Federal Office Only fields sum76 separately and are never added. Source totals are not repaired.',
      Concord: 'Native city Total Cast19234; 12 source columns include separate CSD/MVSD cells in Wards1/2. '
        + 'Printed ward subtotals are not added again. Opening register25879 + Election Day registrations1461 '
        + '= closing27340. Native Turn Out74.32% uses opening, not closing; all analysis rates remain withheld.',
      Nashua: 'Derived sum of all 9 printed native ward Total Ballots Cast fields33849, not a separately printed city parent. '
        + 'Election Day31952 + absentee1895 =33847; Ward3/4/8 source disagreements remain +1/-2/-1. '
        + 'Native Ward8 red amendments3349/3575 supersede cancelled3264/3489; absentee225 is unchanged. '
        + 'Separate federal-only92 is never added; no source counts are repaired.',
      Dover: 'Native printed city Total Ballots Cast15941; polling-place14632 + absentee1309 reconcile. '
        + 'Native checklist20972, verified October26, + Election Day registrations1484 = all registered22456. '
        + 'Native turnout71.0% explicitly uses those source registrations. Native2026 header overrides the2025 filename. '
        + 'Registration-affiliation stocks are not ballot choice or group turnout; all analysis rates remain withheld.',
    };
    for (const row of nh.municipalities) counties.push(observation(review, '', 'NH', row.city,
      cityIdentity(row), row.native_record, {
        geography_level: 'municipality', county_fips: null,
        reference_municipality_key: row.reference_key, reference_geometry: nh.reference_geometry,
        ballots: row.source_count, denominator: null, denominator_basis: 'native_register_definitions_not_analysis_denominator',
        reported_pct: null, maps_approved: true, source_count_qualified: true,
        source_count_basis: row.source_count_basis, source_city_name: row.city,
        native_city_parent_printed: row.native_city_parent_printed,
        native_election_id_qualified: true, source_election_date: '2026-11-03',
        cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
        source_url: row.source_url, participation_measure_label: row.measure,
        native_printed_pct: row.city === 'Concord' ? row.native_record.native_totals.printed_turnout
          : row.city === 'Dover' ? row.native_record.native_header_turnout : null,
        source_update_label: row.city === 'Manchester'
          ? 'Native election November 3, 2026; Wards4/5/10 explicitly revised November4. No common native clock/timezone.'
          : row.city === 'Nashua'
            ? 'Native election November 3, 2026; Wards1/3/4/5/7/8 amended November4; Ward6 amended November7. No common clock/timezone.'
            : 'Native election November 3, 2026; update clock/timezone not supplied.',
        source_status_literal: row.city === 'Manchester' ? 'FORM I - Official Return of Votes' : null,
        source_reporting_label: reporting[row.city],
        quality: ['Four native city source snapshots only; not statewide or county totals or demographic turnout.',
          'Full held 2024 municipality context; 255 reference areas have no source observation and remain unknown.',
          ...row.quality_flags],
      }));
    for (const row of nh.ward_rows) {
      const city = nh.municipalities.find(parent => parent.city === row.city);
      const parent = `additional:NH:${cityIdentity(city)}`;
      const unit = observation(review, '', 'NH', row.city, cityIdentity(city), row.native_record, {
        unit: row.unit, unit_key: row.source_unit_id, unit_kind: 'municipal_ward',
        geography_level: 'source_reporting_unit', ballots: row.source_count, denominator: null,
        denominator_basis: 'native_register_definitions_not_analysis_denominator', reported_pct: null,
        maps_approved: false, county_id: parent, source_url: row.source_url,
        participation_measure_label: row.participation_measure_label,
        native_printed_pct: row.city === 'Concord' ? row.native_record.printed_turnout
          : row.city === 'Dover' ? row.native_record.ballots.printed_turnout : null,
        source_update_label: row.native_revision_label || 'Native clock/timezone not supplied',
        source_reporting_label: ['Manchester', 'Nashua'].includes(row.city)
          ? 'Literal ward Total Ballots Cast; Election Day, absentee and federal-only cells remain separate. '
            + 'Federal-only inclusion is not inferred and no accounting disagreement is repaired.'
          : row.city === 'Dover'
            ? `Native ward Total Ballots Cast; polling-place and absentee components remain separate. `
              + `Checklist${row.native_record.registrations.checklist} + Election Day registrations`
              + `${row.native_record.registrations.new} = all registered${row.native_record.registrations.registered}. `
              + 'Native printed percentage uses that explicit source basis, not population or group turnout.'
            : 'Literal ward Total Cast; Wards1/2 retain separate school-district source cells and printed ward subtotals. '
              + 'Source opening/closing registers and printed percentages are not analysis denominators/rates.',
        quality: ['Native ward reporting row; no 2026 ward/precinct geometry join approved.',
          'No city/ward count allocated to county or other precinct geography.', ...row.quality_flags],
      });
      precincts.push(unit);
    }
  }
  if (nativeCountyParents) {
    const ma = loadMassachusettsCityReference();
    const reference = json(`public/participation-city-counts/${massachusettsVersion}/index.json`).reference_geometry;
    const review = { data_directory: `data/county-source-reviews/${massachusettsCityReferenceVersion}`,
      base_url: '', complete_download_url: ma.complete_download_url };
    const reporting = {
      Boston: 'Native declaring-page Ballots Cast 185,569 matches six complete statewide Times Cast frames across 275 precincts. '
        + 'The separate PDF summary prints Voters Cast 556,369 / registered 0 / N/A and is retained, not substituted or divided. '
        + 'Later question contexts have different native counts; they are not homogenized. No candidate votes are summed.',
      Somerville: 'Native BALLOTS CAST - TOTAL 64,597 and REGISTERED VOTERS - TOTAL 56,008 reconcile to all 32 printed precinct/subprecinct rows. '
        + 'Ballot counts above source registers remain literal, not unique-person counts or turnout rates. '
        + 'The page heading Official and PDF UnOfficial remain distinct. All 32 reporting units join direct city reference polygons; no remainder boundary is invented.',
    };
    for (const row of ma.cities) counties.push(observation(review, '', 'MA', row.city,
      `city:${row.reference_key}`, row.native_record, {
        geography_level: 'municipality', county_fips: null,
        reference_municipality_key: row.reference_key, reference_geometry: reference,
        ballots: row.count, denominator: null, denominator_basis: 'native_register_not_analysis_denominator',
        reported_pct: null, maps_approved: true, source_count_qualified: true,
        source_count_basis: 'literal_native_city_count_with_full_source_context',
        source_city_name: row.city, native_city_parent_printed: true,
        native_reporting_reference_snapshot: massachusettsCityReferenceVersion,
        held_reporting_reference_rows: ma.summary.split_parent_holds,
        native_election_id_qualified: true, source_election_date: '2026-11-03',
        cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
        source_mode: 'all_method_native_city_snapshot',
        source_url: row.source_url, participation_measure_label: row.measure,
        native_printed_pct: null, source_status_literal: row.source_status_literal,
        source_update_label: row.city === 'Boston'
          ? 'Native election November 3, 2026; page November 4, 03:46 AM and PDF 11:39:02 AM; timezone not supplied.'
          : 'Native election November 3, 2026; update clock/timezone not supplied.',
        source_reporting_label: reporting[row.city],
        quality: ['Two native city source snapshots only; not statewide/county totals or demographic turnout.',
          '350 valid unchanged native municipal references; 349 of 351 source areas have no count. Invalid Wayland geometry stays held.',
          ...row.quality_flags],
      }));
    for (const row of ma.reporting_rows) {
      const city = ma.cities.find(city => city.city === row.city);
      const referenceRow = ma.reporting_references.find(ref =>
        ref.city === row.city && ref.ward === row.ward && ref.precinct === row.precinct);
      const level = row.precinct.endsWith('A') ? 'subprecinct' : 'precinct';
      precincts.push(observation(review, '', 'MA', row.city, `city:${city.reference_key}`, row.native_record, {
        county_id: `additional:MA:city:${city.reference_key}`,
        unit: `Ward ${row.ward}, ${level === 'subprecinct' ? 'Subprecinct' : 'Precinct'} ${row.precinct}`,
        unit_key: row.source_unit_id, unit_kind: `municipal_${level}`,
        geography_level: 'source_reporting_unit', ballots: row.source_count,
        denominator: null, denominator_basis: 'native_register_not_analysis_denominator',
        reported_pct: null, maps_approved: false, source_mode: 'all_method_native_city_snapshot',
        source_url: row.source_url, participation_measure_label: row.participation_measure_label,
        source_election_date: '2026-11-03', native_election_id_qualified: true,
        source_status_literal: city.source_status_literal,
        source_update_label: row.city === 'Boston'
          ? 'Native PDF November 4, 2026, 11:39:02 AM; timezone not supplied.'
          : 'Native election November 3, 2026; update clock/timezone not supplied.',
        source_reporting_label: reporting[row.city],
        geometry_withheld_reason: referenceRow.qualified ? null
          : 'Native parent geometry contains a separately reported subprecinct; the remainder is not clipped or inferred.',
        quality: ['Literal native reporting-unit count; a separate checked reference layer controls map display.',
          ...row.quality_flags, ...(referenceRow.qualified ? [] : ['split_parent_reference_held_no_clipping'])],
      }));
    }
  }
  const countyFrames = /** @type {Record<string, Record<string, ReturnType<typeof observation>[]>>} */ ({});
  const countyFrameHolds = /** @type {Record<string, Record<string, unknown[]>>} */ ({});
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
  if (nativeCountyParents) {
    const maine = loadMaineLocalityActivity();
    countyFrames.ME = Object.fromEntries(Object.entries(maine.locality_frames).map(([mode, rows]) =>
      [mode, rows.map(row => observation({
        data_directory: 'data/county-source-reviews/20261110-maine-locality-activity-01',
        base_url: '', complete_download_url: row.complete_download_url,
      }, '', 'ME', row.source_region, `locality:${row.reference_key}`, {
        state: 'ME', category: mode === 'in_person_early' ? 'inperson' : 'returned',
        source_region: row.source_region, categories: row.native_categories,
        snapshot_date: row.source_date, election_name: row.native_election_name, literal_count_field: 'votes',
      }, {
        geography_level: 'source_locality_activity', county_fips: null,
        reference_municipality_key: row.reference_key, reference_geometry: maine.reference_geometry,
        ballots: row.source_count, denominator: null, denominator_basis: 'provider_electorate_not_qualified',
        reported_pct: null, maps_approved: true, source_mode: mode,
        source_provider: 'civicAPI early activity', source_date: row.source_date,
        native_election_id_qualified: false, cast_ballot_count_qualified: false,
        unique_voter_count_qualified: false, source_count_qualified: true,
        participation_measure_label: mode === 'in_person_early'
          ? 'Provider local in-person early activity (native votes counts)'
          : 'Provider local returned activity (native votes counts)',
        source_url: row.source_url,
        source_update_label: `${row.source_date} native provider date; clock/timezone absent. `
          + 'Collector 2026 context is not an independently qualified native election identifier.',
        source_status_literal: 'Provider-reported local activity, not certified government turnout',
        source_reporting_label: '480 of 584 source regions have one-to-one contextual identities in the full 528-area '
          + '2024 reference. 104 source regions and 48 reference areas remain held per mode. '
          + 'No historical voting count is transferred; no county/precinct totals or rates are allocated. '
          + 'Source party buckets are not candidate choices; early and returned frames are never added.',
        quality: ['Provider source activity, not certified cast ballots, unique people or full-election turnout.',
          '2024 contextual municipality geometry, not certified 2026 election or precinct boundaries.',
          'All source regions and reference decisions, including held matches, remain in the complete download.'],
      }))]));
  }
  if (nativeCountyParents) {
    const illinois = loadIllinoisCountyContext();
    countyFrameHolds.IL = illinois.held_city_regions;
    countyFrames.IL = Object.fromEntries(Object.entries(illinois.county_context_frames)
      .map(([mode, rows]) => [mode, rows.map(row => observation({
        data_directory: 'data/county-source-reviews/20261110-illinois-county-context-01',
        base_url: '', complete_download_url: illinois.complete_download_url,
      }, '', 'IL', row.county, row.contextual_county_fips, row.native_record, {
        ...row, reference_geometry: illinois.reference_geometry,
        denominator_basis: 'provider_electorate_not_qualified', maps_approved: true,
        source_count_qualified: true,
        participation_measure_label: mode === 'in_person_early'
          ? 'County-named source-region early activity' : 'County-named source-region returned activity',
        source_update_label: `${row.source_date} native provider date; clock/timezone absent. `
          + 'Collector 2026 context is not an independently qualified native election identifier.',
        source_status_literal: 'Source-region activity, not whole-county totals or certified turnout',
        source_reporting_label: 'Only this literal county-named source-region record is shown. '
          + 'Six separate city-named records remain held, never assigned or added into counties. '
          + 'The Census county shape is context, not a qualified source-authority territory. '
          + 'Early and returned frames are never added.',
        quality: ['Native votes-category activity, not whole-county counts, certified ballots, unique people or turnout.',
          'County identities are contextual, not native FIPS or source-authority/precinct boundaries.',
          'All 108 source records per mode, including six city holds, remain in the complete download.'],
      }))]));
  }
  if (nativeCountyParents) {
    const provider = loadProviderCountyFrames();
    for (const [code, frames] of Object.entries(provider.county_frames)) {
      countyFrames[code] ||= {};
      for (const [mode, rows] of Object.entries(frames)) {
        if (countyFrames[code][mode]) continue;
        countyFrames[code][mode] = rows.map(row => observation({
          data_directory: 'data/county-source-reviews/20261109-provider-county-frames-01',
          base_url: '', complete_download_url: row.complete_download_url,
        }, '', code, row.county, row.county_fips, row.native_record, {
          ballots: row.source_count, denominator: null, denominator_basis: 'provider_electorate_not_qualified',
          reported_pct: null, maps_approved: true, county_fips: row.county_fips,
          reference_geometry: row.reference_geometry, native_record: row.native_record,
          participation_measure_label: row.participation_measure_label, source_mode: mode,
          source_provider: row.source_provider, source_date: row.source_date,
          native_election_id_qualified: false, source_count_qualified: true,
          cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
          source_url: row.source_url, source_update_label: row.source_update_label,
          source_status_literal: row.source_status_literal, source_reporting_label: row.source_reporting_label,
          quality: [row.source_reporting_label,
            'Provider source activity, not an official all-method or independently certified 2026 turnout observation.',
            'Collector 2026 context and native snapshot date are retained separately; no native election ID is inferred.'],
        }));
      }
    }
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
  return { counties, precincts, nongeographic, ...(nativeCountyParents
    ? { county_frames: countyFrames, county_frame_holds: countyFrameHolds } : {}) };
}

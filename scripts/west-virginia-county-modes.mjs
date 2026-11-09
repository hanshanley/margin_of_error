import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const VERSION = 'data/county-source-reviews/20261109-west-virginia-modes-01';
const totals = { in_person_early: 162349, absentee_requested: 9735, mail_returned: 7001 };
const labels = {
  in_person_early: 'Early in-person cast period · source TOTAL VOTERS',
  mail_returned: 'Absentee returned · not qualified cast ballots',
  absentee_requested: 'Absentee requested · not cast or returned',
};
const parties = ['CONSTITUTION PARTY', 'DEMOCRATIC PARTY', 'REPUBLICAN PARTY', 'MOUNTAIN PARTY',
  'NO PARTY', 'LIBERTARIAN PARTY', 'OTHER PARTY'];
const count = value => {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Invalid WV native count; missing is not zero');
  return value;
};
const digest = value => createHash('sha256').update(value).digest('hex');
const nameKey = value => value.toLowerCase().replace(/ county$/, '').replace(/\s/g, '');

export function reviewWestVirginiaModes({ modes, parents, geometry, reference, definitions }) {
  if (reference.boundary_year !== 2026 || reference.counties !== 55
    || geometry.features.length !== 55 || new Set(geometry.features.map(row => row.properties.key)).size !== 55
    || geometry.features.some(({ properties: p }) => p.state_code !== 'WV' || p.boundary_year !== 2026)
    || definitions.publication_date !== '2026-11-02' || definitions.source_period_start !== '2026-10-21'
    || definitions.source_period_end !== '2026-10-31'
    || definitions.no_mode_addition !== true || definitions.combined_figure_qualified_as_cast !== false)
    throw new Error('Unqualified WV reference, source period or incompatible mode addition');
  const identities = new Map(geometry.features.map(row => [row.properties.key, row.properties.name]));
  const frames = {};
  const stateParents = {};
  for (const [mode, total] of Object.entries(totals)) {
    const data = modes[mode], rows = data?.counties;
    if (!rows || rows.length !== 55 || new Set(rows.map(row => row.county_fips)).size !== 55
      || data.original_state_row.native_record.COUNTY !== 'WEST VIRGINIA'
      || data.original_state_row.native_record['TOTAL VOTERS'] !== total)
      throw new Error('Incomplete WV native mode county query or explicit state parent');
    const state = data.original_state_row.native_record;
    for (const party of parties) {
      if (rows.reduce((sum, row) => sum + count(row.native_record[party]), 0) !== count(state[party]))
        throw new Error('WV native county/party cells disagree with the separate state parent');
    }
    if (rows.reduce((sum, row) => sum + count(row.source_count), 0) !== total)
      throw new Error('WV native county mode counts disagree with the separate state parent');
    frames[mode] = rows.map(row => {
      const native = row.native_record;
      if (row.year !== 2026 || row.state_code !== 'WV' || row.mode !== mode
        || !identities.has(row.county_fips) || nameKey(row.county) !== nameKey(identities.get(row.county_fips))
        || nameKey(native.COUNTY) !== nameKey(row.county)
        || row.source_count !== count(native['TOTAL VOTERS'])
        || parties.reduce((sum, party) => sum + count(native[party]), 0) !== row.source_count
        || parties.some(party => row.native_party_counts[party] !== native[party])
        || row.denominator !== null || row.reported_pct !== null || row.unique_voters_certified !== false)
        throw new Error('Changed WV native county identity, count, party category or rate');
      return {
        ...row, participation_measure_label: labels[mode], source_count_qualified: true,
        cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
        reference_geometry: reference,
        source_url: definitions.original_workbook_receipts[row.source_product].requested_url,
        source_update_label: 'Source period through October 31, 2026; native clock/timezone not supplied. '
          + 'Official release published November 2, 2026; publication/acquisition times are not count cutoffs.',
        source_status_literal: 'Source release calls early figures unofficial; no certification inferred.',
        source_reporting_label: labels[mode] + '. This is not full-election turnout. '
          + 'Native party categories are not candidate choices; their operational affiliation definition is unqualified. '
          + 'Do not add early, returned or requested counts. Every analysis denominator and rate is withheld.',
      };
    });
    stateParents[mode] = data.original_state_row;
  }
  if (parents.length !== 3 || new Set(parents.map(row => row.county_fips)).size !== 3)
    throw new Error('Changed WV independently reviewed whole-county snapshot scope');
  const byFips = new Map();
  for (const row of parents) {
    const original = row.native_record;
    const nativeCount = original.native_values
      ? Number(original.native_values.ballots.replaceAll(',', '')) : original.ballots_cast;
    if (row.year !== 2026 || row.state_code !== 'WV' || !identities.has(row.county_fips)
      || nameKey(row.county) !== nameKey(identities.get(row.county_fips))
      || original.election_date !== '2026-11-03' || original.state_code !== 'WV'
      || original.county_fips !== row.county_fips
      || row.measure_literal !== 'Ballots Cast - Total' || row.source_count !== count(nativeCount)
      || row.whole_county_parent_explicit !== true || row.unique_voters_certified !== false
      || row.denominator !== null || row.reported_pct !== null)
      throw new Error('Unqualified WV whole-county parent, not a candidate-vote sum');
    byFips.set(row.county_fips, row);
  }
  const counties = [...identities].map(([fips, name]) => {
    const parent = byFips.get(fips);
    return {
      year: 2026, state_code: 'WV', county_fips: fips, county: name,
      source_count: parent?.source_count ?? null, denominator: null, reported_pct: null,
      native_record: parent?.native_record ?? null, reference_geometry: reference,
      participation_measure_label: 'Native Ballots Cast · independent county snapshot',
      source_count_qualified: Boolean(parent), cast_ballot_count_qualified: Boolean(parent),
      unique_voter_count_qualified: false,
      source_url: parent?.source_url ?? definitions.source_url,
      source_update_label: parent ? `${parent.source_clock_literal}; timezone not supplied.`
        : 'No qualified county-wide all-method source snapshot; missing is not zero.',
      source_status_literal: parent?.source_status_literal ?? null,
      source_reporting_label: parent ? parent.reporting_note
        + ' Separate county snapshot, not one common statewide cutoff; rates withheld.'
        : 'No county-wide all-method parent qualified. Separate early and returned counts exist for all 55 counties; '
          + 'they are not substituted into this all-method frame or added together.',
    };
  });
  return { counties, county_frames: { in_person_early: frames.in_person_early, mail_returned: frames.mail_returned },
    absentee_requests: frames.absentee_requested, original_state_mode_parents: stateParents,
    summary: { all_method_county_queries: 55, all_method_counts: 3, all_method_holds: 52,
      early_county_queries: 55, returned_county_queries: 55, requested_county_queries: 55,
      native_source_party_categories: 7, no_additive_cast_total: true, analysis_rates_approved: false } };
}

export function loadWestVirginiaCountyModes() {
  const inputs = JSON.parse(readFileSync(`${VERSION}/inputs.json`, 'utf8'));
  if (inputs.analysis_rates_approved !== false || inputs.precincts_approved !== false
    || inputs.statewide_full_election_parent_qualified !== false)
    throw new Error('Do not promote WV source modes to certified people, rates or statewide full-election turnout');
  const verified = path => {
    const body = readFileSync(path), receipt = inputs.files[path];
    if (!receipt || receipt.bytes !== body.length || receipt.sha256 !== digest(body))
      throw new Error(`Changed sufficient WV source input: ${path}`);
    return body;
  };
  for (const path of Object.keys(inputs.files)) verified(path);
  const reference = verified(inputs.reference.path), decoded = gunzipSync(reference);
  if (digest(decoded) !== inputs.reference.uncompressed_sha256)
    throw new Error('Changed full WV county reference');
  const result = reviewWestVirginiaModes({
    modes: JSON.parse(gunzipSync(verified(`${VERSION}/native-mode-queries.json.gz`))),
    parents: JSON.parse(verified(`${VERSION}/native-county-parents.json`)),
    definitions: JSON.parse(verified(`${VERSION}/publisher-definitions.json`)),
    geometry: JSON.parse(decoded), reference: inputs.reference,
  });
  for (const row of [...result.counties, ...Object.values(result.county_frames).flat(), ...result.absentee_requests])
    row.complete_download_url = inputs.complete_download_url;
  return result;
}

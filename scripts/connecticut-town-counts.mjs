import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const VERSION = 'data/county-source-reviews/20261110-connecticut-towns-01';
const fields = ['EV', 'VV', 'ABR', 'ABC', 'EBR', 'EBC', 'EDR', 'EDC'];
const key = value => value.normalize('NFKD').toLowerCase().replace(/[^a-z0-9]/g, '');
const digest = value => createHash('sha256').update(value).digest('hex');
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const count = value => {
  if (typeof value !== 'string' || !/^(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(value)
    || !Number.isSafeInteger(Number(value.replaceAll(',', ''))))
    throw new Error('Invalid CT native count; missing is not zero');
  return Number(value.replaceAll(',', ''));
};

export function reviewConnecticutTowns({ inputs, turnout, after, election, elections, status, geometry, original,
  version, afterVersion }) {
  const event = elections.find(row => row.ID === '108');
  const reference = inputs.reference;
  if (inputs.year !== 2026 || inputs.state_code !== 'CT' || inputs.rates_approved !== false
    || inputs.cast_ballot_count_qualified !== false || inputs.unique_voter_count_qualified !== false
    || inputs.precincts_approved !== false || inputs.native_election_id !== '108'
    || version.Version !== 52337 || afterVersion.Version !== 52338
    || event?.Name !== '11/03/2026 -- November 2026 State Election'
    || election.ID !== '108' || reference.boundary_year !== 2024 || reference.localities !== 169
    || reference.geography_scope !== 'native_town_reporting_area'
    || reference.identity_field !== 'source_administration_id'
    || !same(turnout, after) || Object.keys(turnout).length !== 170 || Object.keys(status).length !== 169
    || geometry.features.length !== 169 || original.features.length !== 169)
    throw new Error('Unqualified CT election, source versions or contextual town scope');
  const originals = new Map(original.features.map(f => [key(f.properties.name), f]));
  const shapes = new Map(geometry.features.map(f => [f.properties.key, f]));
  if (originals.size !== 169 || shapes.size !== 169
    || original.features.some(f => f.properties.state_code !== 'CT'
      || f.properties.boundary_year !== 2024 || f.properties.level !== 'municipality'))
    throw new Error('Changed full CT contextual municipality reference');
  const total = turnout['170'];
  if (total?.NM !== 'Total' || count(total.VV) !== count(election.BC) || count(total.EV) !== count(election.RV))
    throw new Error('CT native Total disagrees with separate election parent');
  const sums = Object.fromEntries(fields.map(field => [field, 0]));
  const towns = Object.entries(turnout).filter(([id]) => id !== '170').map(([id, native]) => {
    const identity = `CT-TOWN-${id.padStart(3, '0')}`, feature = shapes.get(identity);
    const originalFeature = originals.get(key(native.NM)), p = feature?.properties;
    if (!/^(?:[1-9]|[1-9]\d|1[0-5]\d|16[0-9])$/.test(id) || !status[id] || !p || !originalFeature
      || p.source_administration_id !== identity || p.source_town_id !== id
      || p.state_code !== 'CT' || p.boundary_year !== 2024 || p.name !== native.NM
      || p.reference_municipality_key !== originalFeature.properties.key
      || !same(feature.geometry, originalFeature.geometry))
      throw new Error('Unmatched CT native town identity or altered contextual geometry');
    for (const field of fields) sums[field] += count(native[field]);
    return {
      year: 2026, state_code: 'CT', county: native.NM, county_fips: null,
      source_administration_id: identity, source_town_id: id, geography_level: 'municipality',
      source_election_id: '108',
      source_count: count(native.VV), denominator: null, reported_pct: null,
      native_printed_pct: native.TO, native_record: { ...native, source_town_id: id, town_status: status[id] },
      reference_geometry: reference, source_count_qualified: true, native_election_id_qualified: true,
      cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
      participation_measure_label: 'Native town participation count (VV)',
      complete_download_url: inputs.complete_download_url, source_url: inputs.turnout_receipt.url,
      source_status_literal: status[id].TS,
      source_update_label: 'Native election 108, November 3, 2026; source versions 52337 and 52338. '
        + 'Native update clock/timezone not supplied; retrieval is not an election-counting cutoff.',
      source_reporting_label: 'Native town VV field, not candidate votes, certified cast ballots or unique people. '
        + 'All 169 town rows remain separate from the native Total; eight native columns reconcile without adding Total again. '
        + 'EV, mode cells, printed TO and blank PR counters stay literal; analysis denominators/rates withheld. '
        + 'No separate nine-county totals, precinct counts or mode sums are invented. '
        + 'Full held 2024 municipality shapes are contextual, not certified 2026 election or precinct boundaries.',
    };
  });
  if (new Set(towns.map(r => r.source_town_id)).size !== 169)
    throw new Error('Incomplete CT town source inventory');
  const accounting = fields.map(field => ({ field, derived_town_sum: sums[field],
    native_total: count(total[field]), agrees: sums[field] === count(total[field]) }));
  if (accounting.some(row => !row.agrees)) throw new Error('CT native town column fails its explicit Total');
  return { towns, all_native_source_queries: turnout, native_election_parent: election,
    native_Total_not_an_additional_town: total, accounting,
    summary: { native_town_observations: 169, all_native_source_queries: 170,
      numeric_column_checks: 8, blank_town_reporting_counters: towns.filter(r => r.native_record.PR === '').length,
      contextual_boundary_year: 2024, election_year: 2026, county_totals_inferred: false,
      precinct_records_inferred: false, analysis_rates_approved: false, source_counts_sum: sums.VV } };
}

let cached;
export function loadConnecticutTowns() {
  if (cached) return cached;
  const inputs = JSON.parse(readFileSync(`${VERSION}/inputs.json`, 'utf8'));
  const verified = path => {
    const body = readFileSync(path), receipt = inputs.files[path];
    if (!receipt || body.length !== receipt.bytes || digest(body) !== receipt.sha256)
      throw new Error(`Changed sufficient CT town input: ${path}`);
    return body;
  };
  for (const path of Object.keys(inputs.files)) verified(path);
  const native = name => JSON.parse(gunzipSync(verified(`${VERSION}/originals/${name}.json.gz`)));
  return cached = reviewConnecticutTowns({ inputs, turnout: native('voterTurnout_Electiondata'),
    after: native('after-voterTurnout_Electiondata'), election: native('election_Electiondata'),
    elections: native('Elections'), status: native('townStatus_Electiondata'),
    version: native('Version'), afterVersion: native('Version-after-reports'),
    original: JSON.parse(gunzipSync(verified(`${VERSION}/originals/municipality-CT-2024.geojson.gz`))),
    geometry: JSON.parse(gunzipSync(verified(inputs.reference.path))) });
}

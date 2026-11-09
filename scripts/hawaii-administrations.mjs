import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const VERSION = 'data/county-source-reviews/20261109-hawaii-administrations-01';
const digest = value => createHash('sha256').update(value).digest('hex');
const expected = {
  'HI-HONOLULU': { name: 'Honolulu election administration', members: ['15003'], total: 228487 },
  'HI-HAWAII': { name: 'Hawaii election administration', members: ['15001'], total: 62453 },
  'HI-KAUAI': { name: 'Kauai election administration', members: ['15007'], total: 24635 },
  'HI-MAUI': { name: 'Maui election administration (includes Kalawao)', members: ['15009', '15005'], total: 50324 },
};
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const count = value => {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Invalid Hawaii native count; missing is not zero');
  return value;
};

export function reviewHawaiiAdministrations({ inputs, grid, scope, geometry, original, units, audit }) {
  if (inputs.year !== 2026 || inputs.state_code !== 'HI' || inputs.rates_approved !== false
    || inputs.cast_ballot_count_qualified !== false || inputs.unique_voter_count_qualified !== false
    || inputs.precincts_approved !== false || scope.administration_count !== 4 || scope.Census_counties !== 5
    || scope.counts_allocated !== false || scope.geometry_repaired !== false
    || scope.certified_election_day_geography !== false
    || inputs.reference.geography_scope !== 'native_election_administration'
    || inputs.reference.identity_field !== 'source_administration_id'
    || inputs.reference.boundary_year !== 2026 || inputs.reference.counties !== 4
    || grid.length !== 4 || new Set(grid.map(r => r.source_administration_id)).size !== 4
    || geometry.features.length !== 4 || new Set(geometry.features.map(f => f.properties.key)).size !== 4
    || original.features.length !== 5 || new Set(original.features.map(f => f.properties.key)).size !== 5)
    throw new Error('Unqualified Hawaii native administration, grouped reference or measure scope');
  const sourceIds = new Set(original.features.map(f => f.properties.key));
  if (!same([...sourceIds].sort(), ['15001', '15003', '15005', '15007', '15009'])
    || original.features.some(({ properties: p }) => p.state_code !== 'HI' || p.boundary_year !== 2026))
    throw new Error('Changed Hawaii full five-county source reference');
  const shapes = new Map(geometry.features.map(f => [f.properties.key, f.properties]));
  const administrations = grid.map(row => {
    const definition = expected[row.source_administration_id], p = shapes.get(row.source_administration_id);
    const values = row.native_values;
    if (!definition || row.administration !== definition.name || !p || p.name !== definition.name
      || p.source_administration_id !== row.source_administration_id || p.state_code !== 'HI' || p.boundary_year !== 2026
      || !same(row.component_county_fips, definition.members) || !same(p.component_county_fips, definition.members)
      || !same(scope.membership[row.source_administration_id], definition.members)
      || !row.source_header[0].startsWith('GENERAL ELECTION 2026 - State of Hawaii - ')
      || row.source_header[1] !== 'November 3, 2026' || row.source_header[3].trim() !== 'REPORT 3'
      || row.source_timezone !== null || !row.source_clock_literal.startsWith('Printed on: 11/04/2026 at ')
      || values['TOTAL TURNOUT'] !== definition.total
      || count(values['Mail TURNOUT']) + count(values['In-Person TURNOUT']) !== count(values['TOTAL TURNOUT'])
      || !Number.isSafeInteger(values['TOTAL REGISTRATION']) || values['TOTAL REGISTRATION'] < 0)
      throw new Error('Changed Hawaii native count, source clock, identity or Maui/Kalawao grouping');
    return {
      year: 2026, state_code: 'HI', source_administration_id: row.source_administration_id,
      county: row.administration, county_fips: null, component_county_fips: row.component_county_fips,
      source_count: values['TOTAL TURNOUT'], denominator: null, reported_pct: null,
      native_record: row, reference_geometry: inputs.reference, source_count_qualified: true,
      cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
      participation_measure_label: 'TOTAL TURNOUT (native report; not certified unique voters)',
      source_url: row.source_url, complete_download_url: inputs.complete_download_url,
      source_update_label: `${row.source_clock_literal}; timezone not supplied. Separate report clock, not one statewide cutoff.`,
      source_status_literal: 'SUMMARY REPORT / REPORT 3; certification not established',
      source_reporting_label: 'Four native election administrations, not five independent Census-county totals. '
        + 'Maui includes Kalawao; full Census components are grouped without count allocation. '
        + 'TOTAL TURNOUT is preserved literally, not promoted to certified cast ballots or unique people. '
        + 'All analysis denominators/rates withheld; no certified precinct geography claim.',
    };
  });
  if (units.length !== 496 || units.some(r => r.year !== 2026 || r.state_code !== 'HI')
    || units.reduce((sum, r) => sum + count(r.ballots), 0) !== 365903
    || audit.source_summary_ballots !== 365897 || audit.registrations !== 853399
    || audit.source_certified !== false || audit.year !== 2026 || audit.state_code !== 'HI'
    || audit.source_election_date !== '2026-11-03')
    throw new Error('Changed Hawaii original statewide/unit control or preserved discrepancy');
  const byComponent = new Map(administrations.flatMap(r =>
    r.component_county_fips.map(fips => [fips, r])));
  const censusCountyDecisions = original.features.map(({ properties: p }) => {
    const admin = byComponent.get(p.key);
    return { year: 2026, state_code: 'HI', county_fips: p.key, county: p.name,
      source_administration_id: admin.source_administration_id,
      source_count: admin.component_county_fips.length === 1 ? admin.source_count : null,
      denominator: null, reported_pct: null,
      disposition: admin.component_county_fips.length === 1 ? 'single_component_native_parent'
        : 'combined_Maui_Kalawao_parent_only_no_separate_Census_county_count',
    };
  });
  return { administrations, Census_county_decisions: censusCountyDecisions,
    diagnostics: { original_state_summary: 365897, original_source_units: 365903,
      administration_snapshot_sum_not_statewide_control: administrations.reduce((sum, r) => sum + r.source_count, 0),
      administration_sum_minus_state_summary: administrations.reduce((sum, r) => sum + r.source_count, 0)
        - audit.source_summary_ballots,
      original_units_minus_state_summary: units.reduce((sum, r) => sum + r.ballots, 0)
        - audit.source_summary_ballots,
      common_cutoff_qualified: false, analysis_rates_approved: false },
    summary: { native_administrations: 4, Census_county_decisions: 5, separate_Census_county_counts: 3,
      separate_Census_county_holds: 2, all496_native_unit_records_unchanged: true, no_count_allocation: true } };
}

export function loadHawaiiAdministrations() {
  const inputs = JSON.parse(readFileSync(`${VERSION}/inputs.json`, 'utf8'));
  const verified = path => {
    const body = readFileSync(path), receipt = inputs.files[path];
    if (!receipt || body.length !== receipt.bytes || digest(body) !== receipt.sha256)
      throw new Error(`Changed sufficient Hawaii source input: ${path}`);
    return body;
  };
  for (const path of Object.keys(inputs.files)) verified(path);
  const json = name => JSON.parse(verified(`${VERSION}/${name}`));
  const decoded = gunzipSync(verified(inputs.reference.path));
  const original = gunzipSync(verified(inputs.original_reference.path));
  if (digest(decoded) !== inputs.reference.uncompressed_sha256
    || digest(original) !== inputs.original_reference.uncompressed_sha256)
    throw new Error('Changed Hawaii original or grouped reference bytes');
  return reviewHawaiiAdministrations({ inputs, grid: json('native-administration-grid.json'),
    scope: json('scope-facts.json'), geometry: JSON.parse(decoded), original: JSON.parse(original),
    units: JSON.parse(gunzipSync(verified(`${VERSION}/native-unit-participation.json.gz`))),
    audit: json('source-audit.json') });
}

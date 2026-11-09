import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const VERSION = 'data/county-source-reviews/20261109-maryland-cards-01';
const digest = value => createHash('sha256').update(value).digest('hex');
const key = value => value.toLowerCase().replace(/ county$/, '').replace("saint mary's", "st. mary's");
const count = value => {
  if (typeof value !== 'string' || !/^(?:\d{1,3}(?:,\d{3})*|\d+)$/.test(value))
    throw new Error('Invalid Maryland native card-reference count');
  const result = Number(value.replaceAll(',', ''));
  if (!Number.isSafeInteger(result)) throw new Error('Unsafe Maryland native count');
  return result;
};

export function reviewMarylandCardCounts({ inputs, grid, scope, crosswalk, geometry }) {
  if (inputs.year !== 2026 || inputs.state_code !== 'MD'
    || inputs.count_reference_join_approved !== true || inputs.cast_ballot_count_qualified !== false
    || inputs.unique_voter_count_qualified !== false || inputs.rates_approved !== false
    || inputs.precincts_approved !== false || scope.election_date !== '2026-11-03'
    || scope.card_report_unofficial !== true || scope.cards_not_certified_unique_voters !== true
    || scope.full_ballot_canvass_certified !== false || scope.card_report_timezone !== null
    || scope.reporting_counters_not_precinct_records !== true
    || scope.group_or_county_model_allocation !== false)
    throw new Error('Do not promote Maryland cards into qualified ballots, people, rates or precincts');
  if (grid.title !== 'Unofficial MIB 1, Early Voting, Election Day, and MIB2 Turnout'
    || grid.election !== 'Election: 2026 Gubernatorial General'
    || grid.run_date !== scope.card_report_native_run_date
    || grid.run_time !== scope.card_report_native_run_time
    || grid.rows.length !== 25 || new Set(grid.rows.map(row => row.native_county_label)).size !== 25
    || grid.rows.at(-1).native_county_label !== 'Total')
    throw new Error('Changed Maryland report identity, source clock or complete query');
  const reference = inputs.reference;
  if (reference.boundary_year !== 2026 || reference.counties !== 24
    || geometry.features.length !== 24 || crosswalk.length !== 24
    || new Set(crosswalk.map(row => row.native_county_label)).size !== 24
    || new Set(crosswalk.map(row => row.county_fips)).size !== 24
    || new Set(geometry.features.map(row => row.properties.key)).size !== 24
    || geometry.features.some(({ properties: p }) =>
      p.state_code !== 'MD' || p.boundary_year !== 2026 || !/^24\d{3}$/.test(p.key)))
    throw new Error('Incomplete Maryland county-equivalent reference or identity inventory');
  const shapes = new Map(geometry.features.map(row => [row.properties.key, row.properties]));
  const identities = new Map(crosswalk.map(row => [row.native_county_label, row]));
  const rows = grid.rows.slice(0, -1).map(native => {
    const join = identities.get(native.native_county_label), shape = shapes.get(join?.county_fips);
    if (!shape || shape.name !== join.reference_name || key(native.native_county_label) !== key(shape.name))
      throw new Error('Unmatched Maryland county identity; never merge Baltimore city and county');
    if (!Number.isSafeInteger(native.reported_source_units) || !Number.isSafeInteger(native.expected_source_units)
      || native.reported_source_units < 0 || native.reported_source_units > native.expected_source_units)
      throw new Error('Invalid Maryland source reporting counter');
    return { county: shape.name, county_fips: join.county_fips,
      cards_cast: count(native.native_cards_cast), native_eligible_voters: count(native.native_eligible_voters),
      native_record: native };
  });
  const parent = grid.rows.at(-1);
  if (rows.reduce((total, row) => total + row.cards_cast, 0) !== count(parent.native_cards_cast)
    || rows.reduce((total, row) => total + row.native_eligible_voters, 0) !== count(parent.native_eligible_voters)
    || parent.reported_source_units !== null || parent.expected_source_units !== null)
    throw new Error('Maryland county card references disagree with the separate native state parent');
  return rows.map(row => ({
    ...row, year: 2026, state_code: 'MD', denominator: null, reported_pct: null,
    reference_geometry: reference, source_url: inputs.source_url,
    complete_download_url: inputs.complete_download_url,
    source_update_label: `${grid.title}; Run Date: ${grid.run_date} ${grid.run_time}; timezone not supplied`,
    participation_measure_label: 'Cards Cast (native report; not unique voters)',
    cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
    source_reporting_label: `Unofficial Cards Cast, not certified unique voters or cast ballots. `
      + `${row.native_record.reported_source_units} of ${row.native_record.expected_source_units} native source units reporting; `
      + 'these counters are not precinct records or proof of final counting. The native title includes MIB2. '
      + 'Native Eligible Voters and the printed percentage remain separate source fields, not qualified analysis denominators or rates.',
  }));
}

export function loadMarylandCardCounts() {
  const inputs = JSON.parse(readFileSync(`${VERSION}/inputs.json`, 'utf8'));
  const verified = path => {
    const body = readFileSync(path), receipt = inputs.files[path];
    if (!receipt || body.length !== receipt.bytes || digest(body) !== receipt.sha256)
      throw new Error(`Changed Maryland sufficient input: ${path}`);
    return body;
  };
  if (digest(verified(`${VERSION}/general-election-night-turnout.pdf`)) !== inputs.pdf_sha256)
    throw new Error('Changed original Maryland card report');
  const raw = verified(inputs.reference.path), decoded = gunzipSync(raw);
  if (digest(raw) !== inputs.reference.sha256 || digest(decoded) !== inputs.reference.uncompressed_sha256)
    throw new Error('Changed Maryland county-reference bytes');
  const json = name => JSON.parse(verified(`${VERSION}/${name}`));
  return reviewMarylandCardCounts({ inputs, grid: json('independent-card-grid.json'),
    scope: json('source-scope.json'), crosswalk: json('county-crosswalk.json'),
    geometry: JSON.parse(decoded) });
}

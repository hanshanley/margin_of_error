import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const VERSION = 'data/county-source-reviews/20261109-michigan-native-parents-01';
const digest = value => createHash('sha256').update(value).digest('hex');
const read = path => JSON.parse(readFileSync(path, 'utf8'));
const count = value => {
  if (!['number', 'string'].includes(typeof value))
    throw new Error('Invalid Michigan native count');
  if (typeof value === 'string' && !/^\d+$/.test(value))
    throw new Error('Invalid Michigan native count');
  if (value === null || value === undefined || !Number.isSafeInteger(Number(value)) || Number(value) < 0)
    throw new Error('Invalid Michigan native count');
  return Number(value);
};
const nameKey = value => value.trim().replace(/\s+county$/i, '').toLowerCase();
const english = values => {
  const rows = values.filter(row => row.languageId === 'en');
  if (rows.length !== 1 || !rows[0].text) throw new Error('Ambiguous Michigan native name');
  return rows[0].text;
};

export function reviewMichiganCountyParents({ bay, isabella, units, geometry, reference, snapshot }) {
  if (reference.boundary_year !== 2026 || reference.counties !== 83
    || geometry.features.length !== 83
    || new Set(geometry.features.map(row => row.properties.key)).size !== 83
    || geometry.features.some(({ properties: p }) =>
      p.state_code !== 'MI' || p.boundary_year !== 2026 || !/^26\d{3}$/.test(p.key))
    || JSON.stringify(reference.partial_county_fips) !== '["26017","26073"]')
    throw new Error('Incorrect Michigan county-reference inventory or partial scope');
  if (units.length !== 63 || new Set(units.map(row => row.source_row_id)).size !== 63
    || units.some(row => row.year !== '2026' || row.state_code !== 'MI'
      || !['bay', 'isabella'].includes(row.county_code) || row.turnout_rate !== ''))
    throw new Error('Incorrect Michigan native reporting-unit scope');
  const shapes = new Map(geometry.features.map(row => [row.properties.key, row.properties]));
  if (!shapes.has('26017') || !shapes.has('26073'))
    throw new Error('Missing Michigan native county reference identities');
  const grouped = code => units.filter(row => row.county_code === code);
  const sum = (rows, key) => rows.reduce((total, row) => total + count(row[key]), 0);
  const bayRows = grouped('bay'), isabellaRows = grouped('isabella');
  if (bay.year !== 2026 || bay.state_code !== 'MI' || bay.county !== 'Bay County'
    || bay.native_status !== 'UNOFFICIAL RESULTS' || bay.source_pdf_page !== 1
    || bayRows.length !== 35 || bay.native_election_day_reporting !== '43 of 43'
    || nameKey(shapes.get('26017').name) !== nameKey(bay.county)
    || bay.native_registered_voters_columns.slice(1).some(value => value !== null))
    throw new Error('Incorrect Bay native county parent');
  const modes = ['ballots_cast_total', 'ballots_cast_election_day',
    'ballots_cast_absentee_counting_board', 'ballots_cast_early_voting'];
  if (bay.native_ballots_cast_columns.length !== 4
    || modes.some((key, index) => count(bay.native_ballots_cast_columns[index]) !== sum(bayRows, key))
    || count(bay.native_ballots_cast_columns[0])
      !== bay.native_ballots_cast_columns.slice(1).reduce((total, value) => total + count(value), 0)
    || count(bay.native_registered_voters_columns[0]) !== sum(bayRows, 'registered_voters_total'))
    throw new Error('Bay county parent disagrees with independent reporting-unit counts');
  const e = isabella.election;
  if (e.electionDate !== '2026-11-03' || e.isPrimary !== false
    || e.isOfficialResults !== false || e.isProduction !== true
    || e.id !== '01000000-85aa-a19e-3fe4-08df1d7ec163'
    || e.jurisdictionId !== '01000000-3685-de5b-d9aa-08dc7c0a200b'
    || e.jurisdictionId !== isabella.jurisdiction.id
    || english(e.name) !== '2026 Isabella County November General Election'
    || nameKey(shapes.get('26073').name) !== 'isabella'
    || isabellaRows.length !== 28 || isabella.voterTurnout.length !== 28 || isabella.precincts.length !== 28)
    throw new Error('Incorrect Isabella native county parent');
  const turnout = new Map(isabella.voterTurnout.map(row => [row.id, row]));
  const precincts = new Map(isabella.precincts.map(row => [row.id, row]));
  if (turnout.size !== 28 || precincts.size !== 28 || isabellaRows.some(row => {
    const native = turnout.get(row.native_precinct_id), precinct = precincts.get(row.native_precinct_id);
    return !native || !precinct || native.precinctName !== row.precinct
      || english(precinct.name) !== row.precinct
      || count(native.ballotsCast) !== count(row.ballots_cast_total)
      || count(native.voterTurnout) !== count(row.ballots_cast_total)
      || count(native.voterRegistration) !== count(row.registered_voters_total);
  }) || count(e.ballotsCast) !== sum(isabellaRows, 'ballots_cast_total')
    || count(e.totalVoters) !== sum(isabellaRows, 'registered_voters_total'))
    throw new Error('Isabella county parent disagrees with complete native unit counts');
  const shared = { code: 'MI', denominator: null, denominator_basis: 'electorate_not_qualified',
    reported_pct: null, reference, snapshot };
  return [{
    ...shared, county: 'Bay County', identity: 'bay', fips: '26017', native: bay,
    sourceFile: 'source/originals/official-bay-general-summary-pdf.gz',
    ballots: count(bay.native_ballots_cast_columns[0]),
    native_printed_pct: `${bay.native_turnout_percent}% (native printed field; analysis rate withheld)`,
    source_update_label: `${bay.native_generated_label}; PDF creation: ${bay.native_pdf_creation_date}. Native labels retained; no common source clock inferred.`,
    source_status_literal: bay.native_status, reported_units: 43, total_units: 43,
    flags: ['native_43_reporting_counter_not_reconciled_to_35_report_sections',
      'registration_components_not_qualified_as_analysis_denominator'],
    source_reporting_label: 'Explicit whole-county Ballots Cast - Total from the independent native summary, '
      + 'equal to all 35 report sections and every separate ballot-mode total. The printed 43 of 43 counter '
      + 'is retained, not treated as 43 geographic precincts. No county rate or statewide total is inferred.',
  }, {
    ...shared, county: 'Isabella County', identity: 'isabella', fips: '26073', native: { election: e },
    sourceFile: 'source/dashboard-network/response-002.json.gz', ballots: count(e.ballotsCast),
    native_printed_pct: null,
    source_update_label: `County as-of: ${e.asOf}; last updated: ${e.lastUpdated}; publish date: ${e.publishDate}; version ${e.publishVersionId}`,
    source_status_literal: `isOfficialResults=${e.isOfficialResults}`, reported_units: 28, total_units: 28,
    flags: ['city_of_clare_22_election_ballots_not_house_scope_ballots',
      'registration_components_not_qualified_as_analysis_denominator'],
    source_reporting_label: 'Explicit native election ballotsCast parent, equal to all 28 native participation '
      + 'records. City of Clare retains 22 election ballots and zero House-scope ballots; the House total '
      + '26266 is not substituted for the election parent. Four neighboring-county zero-count records remain '
      + 'in the original source scope. No pooled ballots, House votes or source discrepancies are allocated.',
  }];
}

export function loadMichiganCountyParents() {
  const inputs = read(`${VERSION}/inputs.json`);
  const verified = path => {
    const body = readFileSync(path), receipt = inputs.files[path];
    if (!receipt || body.length !== receipt.bytes || digest(body) !== receipt.sha256)
      throw new Error(`Changed Michigan county-parent input: ${path}`);
    return body;
  };
  const bay = JSON.parse(verified(inputs.bay_parent));
  const pdf = gunzipSync(verified(bay.source_file));
  if (pdf.length !== bay.source_pdf_bytes || digest(pdf) !== bay.source_pdf_sha256)
    throw new Error('Bay parent extraction disagrees with its original PDF receipt');
  const rawGeometry = verified(inputs.reference.path), decodedGeometry = gunzipSync(rawGeometry);
  if (digest(rawGeometry) !== inputs.reference.sha256
    || digest(decodedGeometry) !== inputs.reference.uncompressed_sha256)
    throw new Error('Changed Michigan county-reference bytes');
  const snapshot = read('public/participation-source-reviews.json').reviews
    .find(row => row.id === 'michigan-native-counties-20261105-01');
  if (!snapshot) throw new Error('Missing Michigan source review');
  return reviewMichiganCountyParents({
    bay, isabella: JSON.parse(gunzipSync(verified(inputs.isabella_parent))),
    units: JSON.parse(gunzipSync(verified(inputs.units))),
    geometry: JSON.parse(decodedGeometry), reference: inputs.reference, snapshot,
  });
}

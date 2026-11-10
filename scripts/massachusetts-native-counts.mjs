import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

export const massachusettsVersion = '20261110-massachusetts-native-local-counts-01';
const directory = `data/county-source-reviews/${massachusettsVersion}`;
const number = value => {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Missing native MA count, not zero');
  return value;
};
const total = values => values.reduce((sum, value) => sum + number(value), 0);
const unitKey = (city, ward, precinct) => `${city}:Ward:${ward}:Precinct:${precinct}`;

export function reviewMassachusettsNativeCounts({ inputs, counts, reference, extension, receipts }) {
  if (inputs.version !== massachusettsVersion || inputs.state_code !== 'MA' || inputs.year !== 2026
    || inputs.native_election_date !== '2026-11-03' || inputs.native_reporting_rows !== 307
    || inputs.qualified_reporting_references !== 303 || inputs.native_municipal_references !== 351
    || inputs.valid_municipal_display_references !== 350
    || inputs.counts_repaired !== false || inputs.candidate_votes_used_as_ballots !== false
    || inputs.modes_added !== false || inputs.parent_geometries_clipped !== false
    || inputs.analysis_rates_approved !== false || inputs.certified_2026_election_boundaries !== false
    || counts.source_counts_repaired !== false || counts.candidate_votes_summed !== false
    || counts.central_tabulation_added_to_combined !== false
    || counts.maps_approved !== false || counts.boston_summary.length !== 275
    || Object.keys(counts.boston_all_times_cast_frames).length !== 44
    || reference.decisions.length !== 279 || extension.all_reference_decisions.length !== 379)
    throw new Error('Unqualified Massachusetts native source/count/reference scope');
  if (!receipts.boston.source.endsWith('/2026-Unofficial-Statement-Of-Votes-Cast.pdf')
    || !receipts.somerville.source.endsWith('/election-results-preliminary-20261103.pdf')
    || receipts.boston.pages !== 353 || receipts.somerville.pages !== 5)
    throw new Error('Changed native complete city originals');

  const senate = counts.boston_all_times_cast_frames['SENATOR IN CONGRESS (Vote for 1)'];
  const boston = new Map();
  for (const row of senate) {
    const key = unitKey('Boston', row.ward, row.precinct);
    if (!/^(?:[1-9]|1\d|2[0-2])$/.test(row.ward) || !/^[1-9]\d*$/.test(row.precinct)
      || boston.has(key) || row.city !== 'Boston'
      || row.analysis_denominator !== null || row.analysis_rate !== null
      || row.registered_voters_literal !== 0)
      throw new Error('Incomplete Boston precinct or native zero-register scope');
    boston.set(key, row);
    number(row.times_cast_literal);
  }
  if (boston.size !== 275 || total(senate.map(row => row.times_cast_literal)) !== 185569)
    throw new Error('Boston native Times Cast is not the complete declared 275-unit frame');
  for (const frame of counts.boston_frame_checks.slice(0, 6)) {
    const rows = counts.boston_all_times_cast_frames[frame.native_context];
    if (frame.precinct_rows !== 275 || frame.all_rows_match_senate_native_field !== true
      || frame.derived_times_cast_sum !== 185569 || rows.length !== 275
      || rows.some(row => boston.get(unitKey('Boston', row.ward, row.precinct))?.times_cast_literal
        !== row.times_cast_literal))
      throw new Error('Changed native statewide count cross-check; no candidate sums');
  }
  if (total(counts.boston_summary.map(row => row.voters_cast_literal)) !== 556369
    || counts.boston_summary_voters_cast_sum !== 556369
    || counts.boston_summary.some(row => row.registered_voters_literal !== 0
      || row.turnout_literal !== 'N/A' || row.analysis_denominator !== null || row.analysis_rate !== null))
    throw new Error('Native Boston summary/zero/N/A conflict must remain separate, not repaired');

  const somerville = counts.somerville_native_counts;
  const units = somerville.filter(row => row.native_level === 'precinct');
  const city = somerville.filter(row => row.native_level === 'city');
  if (somerville.length !== 40 || units.length !== 32 || city.length !== 1
    || city[0].ballots_cast_literal !== 64597 || city[0].registered_voters_literal !== 56008
    || total(units.map(row => row.ballots_cast_literal)) !== city[0].ballots_cast_literal
    || total(units.map(row => row.registered_voters_literal)) !== city[0].registered_voters_literal
    || somerville.some(row => row.source_document_literal_status !== 'UnOfficial'
      || row.declaring_page_heading_literal_status !== 'Official'
      || row.analysis_denominator !== null || row.analysis_rate !== null)
    || counts.somerville_all_accounting.length !== 16
    || counts.somerville_all_accounting.some(row => row.component_minus_printed !== 0))
    throw new Error('Changed Somerville source counts, split units or literal status disagreement');
  const nativeUnits = [
    ...senate.map(row => ({ city: 'Boston', ward: row.ward, precinct: row.precinct,
      source_count: row.times_cast_literal, native_record: row,
      participation_measure_label: 'Native Times Cast', source_page: row.source_page,
      source_url: receipts.boston.source, native_count_field: 'Times Cast',
      quality_flags: ['native_zero_registration_not_an_analysis_denominator',
        'separate_summary_Voters_Cast556369_not_substituted_for_selected_context185569'] })),
    ...units.map(row => ({ city: 'Somerville', ward: row.ward, precinct: row.precinct,
      source_count: row.ballots_cast_literal, native_record: row,
      participation_measure_label: 'Native BALLOTS CAST - TOTAL', source_page: 1,
      source_url: receipts.somerville.source, native_count_field: 'BALLOTS CAST - TOTAL',
      quality_flags: ['native_Official_page_and_UnOfficial_PDF_statuses_remain_distinct',
        ...(row.ballots_cast_literal > row.registered_voters_literal
          ? ['native_ballot_count_exceeds_native_register_not_unique_people_or_rate'] : [])] })),
  ];
  const identities = new Map();
  for (const row of nativeUnits) {
    row.source_unit_id = unitKey(row.city, row.ward, row.precinct);
    if (identities.has(row.source_unit_id)) throw new Error('Duplicate MA reporting-unit identity');
    identities.set(row.source_unit_id, row);
  }
  const reporting = [
    ...reference.decisions.map(row => ({
      city: row.city_source === 'boston' ? 'Boston' : 'Somerville',
      ward: row.ward, precinct: row.precinct, native_object_id: row.native_object_id,
      source: row.city_source, native_level: row.native_reference_level,
      native_properties: row.native_properties, source_count: row.native_count,
      qualified: row.qualified_unchanged_reference,
      disposition: 'qualified_unchanged_native_reporting_reference',
    })),
    ...extension.all_reference_decisions.filter(row => row.source === 'somerville-parent-precincts')
      .map(row => ({ city: 'Somerville', ward: row.ward, precinct: row.precinct,
        native_object_id: row.native_object_id, source: row.source, native_level: row.native_level,
        native_properties: row.native_properties, source_count: row.native_count,
        qualified: row.source_count_join_qualified, disposition: row.disposition })),
  ];
  const references = new Map();
  const held = [];
  for (const row of reporting) {
    const key = unitKey(row.city, row.ward, row.precinct);
    if (references.has(key) || !identities.has(key)
      || number(row.source_count) !== identities.get(key).source_count)
      throw new Error('Native MA reference/count join differs; no geography allocation');
    references.set(key, row);
    if (!row.qualified) held.push(key);
  }
  const expectedHolds = ['1:4', '2:1', '4:2', '6:3'].map(value => {
    const [ward, precinct] = value.split(':');
    return unitKey('Somerville', ward, precinct);
  });
  if (references.size !== 307 || held.length !== 4
    || expectedHolds.some(key => !held.includes(key))
    || reporting.filter(row => row.qualified).length !== 303
    || reporting.some(row => expectedHolds.includes(unitKey(row.city, row.ward, row.precinct))
      && row.disposition !== 'held_parent_geometry_contains_separately_reported_subprecinct_no_clipping'))
    throw new Error('Unqualified split-parent/remainder reference scope');

  const municipalities = extension.all_reference_decisions
    .filter(row => row.source === 'massachusetts-municipalities');
  const municipalityHolds = municipalities.filter(row => !row.geometry_qualified);
  if (municipalities.length !== 351
    || new Set(municipalities.map(row => row.native_properties.TOWN_ID)).size !== 351
    || municipalityHolds.length !== 1 || municipalityHolds[0].native_properties.TOWN !== 'WAYLAND'
    || municipalityHolds[0].native_properties.TOWN_ID !== 315)
    throw new Error('Changed complete municipality reference or unrepaired Wayland hold');
  const cityProfiles = [
    { city: 'Boston', town_id: 35, count: 185569,
      measure: 'Native Ballots Cast / Times Cast', source_url: receipts.boston.source,
      source_status_literal: 'Unofficial',
      native_record: { native_city_ballots_cast: 185569, native_count_field: 'Ballots Cast / Times Cast',
        selected_context: 'SENATOR IN CONGRESS (Vote for 1)',
        native_summary_voters_cast: 556369, native_summary_registered: 0,
        native_summary_pct: 'N/A', native_context_checks: counts.boston_frame_checks },
      quality_flags: ['native_summary_Voters_Cast556369_remains_distinct_from_selected185569',
        'zero_registers_and_NA_are_not_analysis_denominators_or_rates'] },
    { city: 'Somerville', town_id: 274, count: 64597,
      measure: 'Native BALLOTS CAST - TOTAL', source_url: receipts.somerville.source,
      source_status_literal: 'UnOfficial (PDF); Official (declaring-page heading)',
      native_record: { native_city_ballots_cast: 64597, native_registered_voters: 56008,
        native_count_field: 'BALLOTS CAST - TOTAL', all_source_reporting_rows: somerville,
        original_page_status: 'Official', original_document_status: 'UnOfficial' },
      quality_flags: ['native_ballots_exceed_native_register_not_unique_people_or_rate',
        'native_Official_page_and_UnOfficial_PDF_statuses_remain_distinct'] },
  ];
  for (const row of cityProfiles) {
    const matches = municipalities.filter(ref => ref.native_properties.TOWN_ID === row.town_id);
    if (matches.length !== 1 || !matches[0].source_count_join_qualified
      || matches[0].native_properties.TOWN !== row.city.toUpperCase()
      || matches[0].native_count !== row.count)
      throw new Error('Changed literal native city/municipality reference identity');
    row.reference_key = `MA:TOWN:${String(row.town_id).padStart(3, '0')}`;
  }
  return { inputs, cities: cityProfiles, reporting_rows: nativeUnits,
    reporting_references: reporting, municipality_references: municipalities,
    complete_download_url: inputs.complete_download_url,
    summary: { cities: 2, native_reporting_rows: 307, mapped_reporting_references: 303,
      split_parent_holds: 4, native_municipalities: 351, displayed_municipalities: 350,
      invalid_reference_holds: 1, analysis_rates_approved: false } };
}

export function loadMassachusettsNativeCounts() {
  const read = path => JSON.parse(readFileSync(`${directory}/${path}`, 'utf8'));
  const inputs = read('inputs.json');
  for (const [path, receipt] of Object.entries(inputs.files)) {
    const body = readFileSync(`${directory}/${path}`);
    if (body.length !== receipt.bytes || createHash('sha256').update(body).digest('hex') !== receipt.sha256)
      throw new Error(`Changed sufficient native Massachusetts input: ${path}`);
  }
  return reviewMassachusettsNativeCounts({ inputs, counts: read(inputs.queries.counts),
    reference: read(inputs.queries.reporting_reference),
    extension: JSON.parse(gunzipSync(readFileSync(`${directory}/${inputs.queries.reference_extension}`))),
    receipts: { boston: read('declared-results-01/boston-2026-Unofficial-Statement-Of-Votes-Cast.pdf.receipt.json'),
      somerville: read('declared-results-01/somerville-election-results-preliminary-20261103.pdf.receipt.json') } });
}

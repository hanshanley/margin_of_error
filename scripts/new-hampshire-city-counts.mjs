import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const version = 'data/county-source-reviews/20261110-new-hampshire-cities-01';
const fieldLabels = { election_day: 'Election Day Ballots Cast', absentee: 'Absentee Ballots Cast',
  total: 'Total Ballots Cast', federal_only: 'Federal Office Only Ballots Cast' };
const count = value => {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Missing or invalid native count; not zero');
  return value;
};
const total = values => values.reduce((sum, value) => sum + count(value), 0);

export function reviewNewHampshireCities({ inputs, readings, reference }) {
  if (readings.election_date !== '2026-11-03' || readings.analysis_rates_approved !== false
    || readings.candidate_counts_used_as_ballots !== false
    || inputs.reference.boundary_year !== 2024 || inputs.reference.localities !== 259
    || inputs.certified_election_boundaries !== false || inputs.analysis_rates_approved !== false
    || reference.features.length !== 259)
    throw new Error('Unqualified NH native election/count/reference scope');
  const identities = new Map(), names = new Map();
  for (const feature of reference.features) {
    const p = feature.properties;
    if (!/^33\d{5}$/.test(p.key) || p.state_code !== 'NH' || p.boundary_year !== 2024
      || p.level !== 'municipality' || !feature.geometry || identities.has(p.key))
      throw new Error('Incomplete or ambiguous full municipality reference');
    identities.set(p.key, p);
    names.set(p.name, [...(names.get(p.name) || []), p.key]);
  }
  if (JSON.stringify(names.get('Manchester')) !== '["3345140"]'
    || JSON.stringify(names.get('Concord')) !== '["3314200"]')
    throw new Error('Changed literal city contextual identities');
  const sourceQueries = [], unitRows = [], accounting = [];
  const add = (city, unit, field, label, value, sourceFile, nativePage, kind = 'count') => {
    if (kind === 'count') count(value);
    else if (!/^\d{1,3}\.\d{2}%$/.test(value)) throw new Error('Invalid printed native percent');
    sourceQueries.push({ state_code: 'NH', year: 2026, city, source_unit: unit,
      source_field: field, native_measure_label: label, native_value: value,
      native_value_kind: kind, source_file: sourceFile, native_page: nativePage,
      analysis_denominator: null, analysis_rate: null });
  };
  const m = readings.manchester, c = readings.concord;
  if (JSON.stringify(m.native_measure_labels) !== JSON.stringify(fieldLabels)
    || m.native_election_label !== 'General Election November 3, 2026'
    || m.federal_only_added_to_total !== false || m.federal_only_inclusion_in_total_independently_qualified !== false
    || m.native_page !== 1 || m.wards.length !== 12 || new Set(m.wards.map(r => r.ward)).size !== 12
    || m.wards.some(r => !Number.isInteger(r.ward) || r.ward < 1 || r.ward > 12))
    throw new Error('Changed Manchester native fields or complete ward inventory');
  for (const native of m.wards) {
    const file = `manchester-ward${String(native.ward).padStart(2, '0')}-20261103-original.pdf`;
    const receipt = inputs.originals[file];
    if (!receipt || !receipt.url.includes(`/2026-11-03_Ward${String(native.ward).padStart(2, '0')}_ElectionPaperwork.pdf`)
      || receipt.declared_ward !== native.ward || receipt.native_election_date !== '2026-11-03')
      throw new Error('Native Manchester packet is not the declared election/ward');
    for (const [field, label] of Object.entries(fieldLabels))
      add('Manchester', `Ward ${native.ward}`, field, label, native[field], file, 1);
    const difference = count(native.election_day) + count(native.absentee) - count(native.total);
    const flags = difference ? ['native_mode_components_disagree_with_printed_total_not_repaired'] : [];
    accounting.push({ city: 'Manchester', ward: native.ward, election_day: native.election_day,
      absentee: native.absentee, printed_total: native.total,
      component_sum: native.election_day + native.absentee,
      component_minus_printed_total: difference, federal_only_separate: native.federal_only,
      native_source_repaired: false });
    unitRows.push({ city: 'Manchester', native_ward: native.ward, unit: `Ward ${native.ward}`,
      source_unit_id: `Manchester:Ward:${native.ward}`, source_file: file, native_page: 1,
      source_url: receipt.url, source_count: native.total, native_record: native,
      participation_measure_label: 'Native Total Ballots Cast',
      quality_flags: flags, native_revision_label: native.native_revision_label,
      denominator: null, reported_pct: null, maps_approved: false });
  }
  if (c.native_election_label !== 'November 3, 2026 State General Election Results'
    || c.native_page !== 4 || c.literal_measure !== 'Total Cast'
    || c.total_cast_columns.length !== 12 || c.separate_printed_ward_subtotals.length !== 2
    || JSON.stringify(c.register_ward_order) !== '[1,2,3,4,5,6,7,8,9,10]'
    || c.analysis_denominator !== null || c.analysis_rate !== null)
    throw new Error('Unqualified Concord field or school-district/ward hierarchy');
  const concordFile = 'concord-20261103-original.pdf';
  const concordReceipt = inputs.originals[concordFile];
  if (!concordReceipt || concordReceipt.native_election_date !== '2026-11-03')
    throw new Error('Missing actual declared Concord general-election source');
  const sourceIds = new Set(), wardCounts = new Map();
  for (const row of c.total_cast_columns) {
    const district = row.school_district;
    if (!Number.isInteger(row.ward) || row.ward < 1 || row.ward > 10
      || (row.ward <= 2 ? !['Concord School District (CSD)', 'Merrimack Valley School District (MVSD)'].includes(district)
        : district !== null))
      throw new Error('Changed native Concord school-district scope');
    const id = `Ward ${row.ward}${district ? ' | ' + district : ''}`;
    if (sourceIds.has(id)) throw new Error('Duplicate Concord split source column');
    sourceIds.add(id);
    wardCounts.set(row.ward, (wardCounts.get(row.ward) || 0) + count(row.count));
    add('Concord', id, 'total_cast', c.literal_measure, row.count, concordFile, 4);
  }
  if (total(c.total_cast_columns.map(r => r.count)) !== count(c.native_city_total_cast) || wardCounts.size !== 10)
    throw new Error('Concord complete native cast columns disagree with printed parent');
  add('Concord', 'City total', 'total_cast', c.literal_measure, c.native_city_total_cast, concordFile, 4);
  const subtotals = new Map();
  for (const row of c.separate_printed_ward_subtotals) {
    if (![1, 2].includes(row.ward) || subtotals.has(row.ward) || row.count !== wardCounts.get(row.ward))
      throw new Error('Concord printed ward subtotal differs; no count allocation allowed');
    subtotals.set(row.ward, row.count);
    add('Concord', `Ward ${row.ward} printed subtotal`, 'printed_ward_total_cast',
      'Total Cast, separate printed ward subtotal', row.count, concordFile, 4);
  }
  const labels = c.native_register_labels;
  if (labels.opening !== 'Registered Voters at Opening of Polls'
    || labels.closing !== 'Registered Voters at Closing of Polls'
    || labels.election_day_registrations !== 'Election Day Registrations' || labels.printed_turnout !== 'Turn Out')
    throw new Error('Changed source register or printed rate definitions');
  for (const field of ['opening', 'election_day_registrations', 'closing', 'printed_turnout']) {
    if (c[field].length !== 10) throw new Error('Incomplete native Concord ward/register inventory');
    const kind = field === 'printed_turnout' ? 'printed_native_percent' : 'count';
    for (let i = 0; i < 10; i++) add('Concord', `Ward ${i + 1}`, field, labels[field],
      c[field][i], concordFile, 4, kind);
    add('Concord', 'City total', field, labels[field], c.native_totals[field], concordFile, 4, kind);
    if (field !== 'printed_turnout' && total(c[field]) !== c.native_totals[field])
      throw new Error('Concord native register column disagrees with printed total');
  }
  for (let i = 0; i < 10; i++) {
    if (count(c.opening[i]) + count(c.election_day_registrations[i]) !== count(c.closing[i]))
      throw new Error('Native Concord opening + Election Day registrations differs from closing');
    unitRows.push({ city: 'Concord', native_ward: i + 1, unit: `Ward ${i + 1}`,
      source_unit_id: `Concord:Ward:${i + 1}`, source_file: concordFile, native_page: 4,
      source_url: concordReceipt.url, source_count: wardCounts.get(i + 1),
      native_record: { total_cast_columns: c.total_cast_columns.filter(r => r.ward === i + 1),
        printed_ward_subtotal: subtotals.get(i + 1) ?? null, opening: c.opening[i],
        election_day_registrations: c.election_day_registrations[i], closing: c.closing[i],
        printed_turnout: c.printed_turnout[i] },
      participation_measure_label: 'Native Total Cast', quality_flags: [],
      native_revision_label: null, denominator: null, reported_pct: null, maps_approved: false });
  }
  if (sourceQueries.length !== 107 || unitRows.length !== 22)
    throw new Error('Incomplete native participation/register/printed-percent query set');
  const manchester = total(m.wards.map(r => r.total));
  const municipalities = [
    { city: 'Manchester', reference_key: '3345140', source_count: manchester,
      measure: 'Sum of 12 native ward Total Ballots Cast fields', source_url: inputs.indexes.manchester.url,
      native_record: m, native_city_parent_printed: false,
      source_count_basis: 'derived_sum_complete12_printed_totals_not_repaired',
      quality_flags: accounting.some(r => r.component_minus_printed_total !== 0)
        ? ['native_ward_mode_component_disagreement_retained_in_raw_total_sum'] : [] },
    { city: 'Concord', reference_key: '3314200', source_count: c.native_city_total_cast,
      measure: 'Native Total Cast', source_url: concordReceipt.url, native_record: c,
      native_city_parent_printed: true, source_count_basis: 'native_printed_city_total_cast',
      quality_flags: [] },
  ].map(row => ({ ...row, year: 2026, state_code: 'NH', source_election_date: '2026-11-03',
    native_election_id_qualified: true, cast_ballot_count_qualified: false,
    unique_voter_count_qualified: false, denominator: null, reported_pct: null }));
  const referenceQueries = reference.features.map(({ properties: p }) => ({
    contextual_municipality_key: p.key, municipality: p.name, reference_year: 2024,
    source_city: municipalities.find(r => r.reference_key === p.key)?.city ?? null,
    disposition: municipalities.some(r => r.reference_key === p.key)
      ? 'native_city_source_count_on_older_municipality_context' : 'held_no_city_source_observation',
    certified_election_boundaries: false }));
  const printedRateBasisQueries = [...c.register_ward_order.map((ward, i) => ({
    source_unit: `Ward ${ward}`, native_total_cast: wardCounts.get(ward),
    native_opening: c.opening[i], native_closing: c.closing[i], native_printed: c.printed_turnout[i] })),
  { source_unit: 'City total', native_total_cast: c.native_city_total_cast,
    native_opening: c.native_totals.opening, native_closing: c.native_totals.closing,
    native_printed: c.native_totals.printed_turnout }].map(row => {
    const printed = Number(row.native_printed.replace('%', ''));
    const matches = stock => stock > 0
      && Math.abs(Math.round(row.native_total_cast * 10000 / stock) / 100 - printed) < 1e-8;
    return { ...row, matches_opening_stock_arithmetic: matches(row.native_opening),
      matches_closing_stock_arithmetic: matches(row.native_closing),
      analysis_denominator: null, analysis_rate: null };
  });
  return { summary: { complete_source_field_queries: 107, complete_reference_queries: 259,
    source_city_observations: 2, native_ward_rows: 22, manchester_declared_wards: 12,
    manchester_printed_total_sum: manchester,
    manchester_native_component_disagreements: accounting.filter(r => r.component_minus_printed_total !== 0).length,
    manchester_component_minus_printed_sum: accounting.reduce((s, r) => s + r.component_minus_printed_total, 0),
    federal_only_separate_sum: total(m.wards.map(r => r.federal_only)), federal_only_added: false,
    concord_native_total_cast: c.native_city_total_cast, contextual_reference_year: 2024,
    unmapped_reference_areas: 257, analysis_rates_approved: false, source_counts_repaired: false },
  source_queries: sourceQueries, source_accounting_queries: accounting,
  source_printed_rate_basis_queries: printedRateBasisQueries,
  reference_queries: referenceQueries, municipalities, ward_rows: unitRows,
  reference_geometry: inputs.reference, complete_download_url: inputs.complete_download_url };
}

export function loadNewHampshireCities() {
  const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
  for (const [path, receipt] of Object.entries(inputs.files)) {
    const body = readFileSync(path);
    if (body.length !== receipt.bytes || createHash('sha256').update(body).digest('hex') !== receipt.sha256)
      throw new Error(`Changed sufficient NH original or exact visual reading: ${path}`);
  }
  return reviewNewHampshireCities({ inputs,
    readings: JSON.parse(readFileSync(inputs.readings_path, 'utf8')),
    reference: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))) });
}

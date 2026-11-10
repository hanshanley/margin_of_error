import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { loadNewHampshireCities } from './new-hampshire-city-counts.mjs';

const version = 'data/county-source-reviews/20261110-new-hampshire-cities-02';
const count = value => {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Missing native city count, not zero');
  return value;
};
const sum = values => values.reduce((total, value) => total + count(value), 0);

export function reviewNewHampshireCityExtension({ inputs, base, nashua, dover }) {
  if (inputs.reference.boundary_year !== 2024 || inputs.reference.localities !== 259
    || inputs.reference.mapped_localities !== 4 || inputs.certified_election_boundaries !== false
    || inputs.analysis_rates_approved !== false || base.source_queries.length !== 107
    || base.ward_rows.length !== 22 || base.municipalities.length !== 2
    || base.reference_queries.length !== 259)
    throw new Error('Changed native city extension or preserved first-release scope');
  for (const [name, key] of [['Nashua', '3350260'], ['Dover', '3318820']]) {
    const matches = base.reference_queries.filter(row => row.municipality === name);
    if (matches.length !== 1 || matches[0].contextual_municipality_key !== key)
      throw new Error('Ambiguous native city contextual identity');
  }
  const sourceQueries = [], wards = [], accounting = [], printedBasis = [];
  const add = (city, unit, field, label, value, file, page) => {
    const percent = field.includes('turnout');
    if (percent ? !/^\d{1,3}\.\d%$/.test(value) : !Number.isSafeInteger(value) || value < 0)
      throw new Error('Missing literal count or printed percentage');
    sourceQueries.push({ state_code: 'NH', year: 2026, city, source_unit: unit,
      source_field: field, native_measure_label: label, native_value: value,
      native_value_kind: percent ? 'printed_native_percent' : 'count',
      source_file: file, native_page: page, analysis_denominator: null, analysis_rate: null });
  };
  const pages = [1,7,9,11,14,19,22,24,26];
  if (nashua.election_date !== '2026-11-03'
    || nashua.native_election_label !== 'General Election November 3, 2026'
    || nashua.federal_only_added_to_total !== false || nashua.candidate_counts_used_as_ballots !== false
    || nashua.source_counts_repaired !== false || nashua.native_city_parent_printed !== false
    || nashua.wards.length !== 9 || new Set(nashua.wards.map(row => row.ward)).size !== 9
    || JSON.stringify(nashua.native_measure_labels) !== JSON.stringify(base.municipalities[0].native_record.native_measure_labels))
    throw new Error('Unqualified Nashua literal ballot fields or complete ward inventory');
  const nashuaFile = 'nashua-20261103-original.pdf';
  const nashuaReceipt = inputs.originals[nashuaFile];
  if (!nashuaReceipt?.url.endsWith('/DocumentCenter/View/37495'))
    throw new Error('Missing actual declared Nashua amended report');
  for (const native of nashua.wards) {
    if (!Number.isInteger(native.ward) || native.ward < 1 || native.ward > 9
      || native.native_page !== pages[native.ward - 1])
      throw new Error('Changed native Nashua ward/page identity');
    for (const [field, label] of Object.entries(nashua.native_measure_labels))
      add('Nashua', `Ward ${native.ward}`, field, label, native[field], nashuaFile, native.native_page);
    const difference = count(native.election_day) + count(native.absentee) - count(native.total);
    accounting.push({ city: 'Nashua', ward: native.ward, election_day: native.election_day,
      absentee: native.absentee, printed_total: native.total,
      component_sum: native.election_day + native.absentee,
      component_minus_printed_total: difference, federal_only_separate: count(native.federal_only),
      native_source_repaired: false });
    wards.push({ city: 'Nashua', native_ward: native.ward, unit: `Ward ${native.ward}`,
      source_unit_id: `Nashua:Ward:${native.ward}`, source_file: nashuaFile,
      native_page: native.native_page, source_url: nashuaReceipt.url, source_count: native.total,
      native_record: native, participation_measure_label: 'Native Total Ballots Cast',
      quality_flags: difference ? ['native_mode_components_disagree_with_printed_total_not_repaired'] : [],
      native_revision_label: native.native_revision_label, denominator: null, reported_pct: null,
      maps_approved: false });
  }
  const doverFile = 'dover-20261103-native-turnout-original.pdf';
  const doverReceipt = inputs.originals[doverFile];
  if (!doverReceipt?.url.includes('/2026-general-election/turnout/')
    || dover.election_date !== '2026-11-03'
    || dover.native_election_label !== 'NOVEMBER 3, 2026 GENERAL ELECTION'
    || dover.native_city_parent_printed !== true
    || dover.native_ballot_rows.length !== 7 || dover.native_register_rows.length !== 7
    || dover.native_checklist_verified_date !== '2026-10-26'
    || dover.native_printed_rate_basis !== 'Total ballots cast divided by total checklist and election day registered voters'
    || dover.native_new_voter_definition !== 'Those who registered at the polls on Election Day'
    || dover.registration_affiliation_is_not_ballot_choice !== true
    || dover.no_group_participation_numerators_observed !== true
    || dover.native_ballot_labels.total !== 'Total Ballots Cast'
    || dover.native_ballot_labels.registered !== 'All Registered Voters')
    throw new Error('Unqualified Dover native date, ballot measure or registered-electorate definition');
  const expectedWards = [1,2,3,4,5,6,'TOTAL'];
  const nativeTotal = dover.native_ballot_rows.at(-1);
  add('Dover', 'City header', 'header_printed_turnout', 'VOTER TURNOUT',
    dover.native_header_turnout, doverFile, 1);
  for (let index = 0; index < 7; index++) {
    const native = dover.native_ballot_rows[index], register = dover.native_register_rows[index];
    if (native.ward !== expectedWards[index] || register.ward !== native.ward)
      throw new Error('Changed complete Dover source ward/printed-total order');
    const unit = index === 6 ? 'City total' : `Ward ${native.ward}`;
    for (const [field, label] of Object.entries(dover.native_ballot_labels))
      add('Dover', unit, `ballot_${field}`, label, native[field], doverFile, 1);
    for (const [field, label] of Object.entries(dover.native_register_labels))
      add('Dover', unit, `register_${field}`, label, register[field], doverFile, 1);
    const registerSums = {
      checklist: sum(['republican_checklist','democratic_checklist','undeclared_checklist'].map(k => register[k])),
      new: sum(['republican_new','democratic_new','undeclared_new'].map(k => register[k])),
    };
    if (registerSums.checklist !== register.checklist || registerSums.new !== register.new
      || count(register.checklist) + count(register.new) !== count(register.registered)
      || register.registered !== native.registered)
      throw new Error('Dover native register stocks do not reconcile; no inferred group turnout');
    const difference = count(native.polling_place) + count(native.absentee) - count(native.total);
    accounting.push({ city: 'Dover', ward: native.ward, polling_place: native.polling_place,
      absentee: native.absentee, printed_total: native.total,
      component_sum: native.polling_place + native.absentee, component_minus_printed_total: difference,
      native_checklist: register.checklist, election_day_registrations: register.new,
      native_all_registered: register.registered, native_source_repaired: false });
    const calculated = native.registered > 0 ? native.total / native.registered : null;
    printedBasis.push({ city: 'Dover', source_unit: unit, native_total_cast: native.total,
      native_checklist: register.checklist, native_election_day_registrations: register.new,
      native_all_registered: native.registered, native_printed: native.printed_turnout,
      native_basis: dover.native_printed_rate_basis, source_defined_registered_fraction: calculated,
      matches_explicit_native_registered_basis: calculated !== null
        && (calculated * 100).toFixed(1) + '%' === native.printed_turnout,
      analysis_denominator: null, analysis_rate: null, not_group_or_population_turnout: true });
    if (index < 6) wards.push({ city: 'Dover', native_ward: native.ward, unit,
      source_unit_id: `Dover:Ward:${native.ward}`, source_file: doverFile, native_page: 1,
      source_url: doverReceipt.url, source_count: native.total,
      native_record: { ballots: native, registrations: register },
      participation_measure_label: 'Native Total Ballots Cast',
      quality_flags: difference ? ['native_mode_components_disagree_with_printed_total_not_repaired'] : [],
      native_revision_label: null, denominator: null, reported_pct: null, maps_approved: false });
  }
  for (const field of ['polling_place','absentee','total','registered'])
    if (sum(dover.native_ballot_rows.slice(0,6).map(row => row[field])) !== nativeTotal[field])
      throw new Error('Dover ward source counts differ from printed city parent');
  for (const field of Object.keys(dover.native_register_labels))
    if (sum(dover.native_register_rows.slice(0,6).map(row => row[field])) !== dover.native_register_rows[6][field])
      throw new Error('Dover ward source register differs from printed parent');
  if (sourceQueries.length !== 135 || wards.length !== 15
    || dover.native_header_turnout !== nativeTotal.printed_turnout)
    throw new Error('Incomplete new native city source fields');
  const profiles = [
    { city: 'Nashua', reference_key: '3350260', source_count: sum(nashua.wards.map(row => row.total)),
      measure: 'Sum of 9 native ward Total Ballots Cast fields', source_url: nashuaReceipt.url,
      native_record: nashua, native_city_parent_printed: false,
      source_count_basis: 'derived_sum_complete9_printed_totals_not_repaired',
      quality_flags: accounting.some(row => row.city === 'Nashua' && row.component_minus_printed_total !== 0)
        ? ['native_ward_mode_component_disagreement_retained_in_raw_total_sum'] : [] },
    { city: 'Dover', reference_key: '3318820', source_count: nativeTotal.total,
      measure: 'Native Total Ballots Cast', source_url: doverReceipt.url,
      native_record: dover, native_city_parent_printed: true,
      source_count_basis: 'native_printed_city_total_ballots_cast', quality_flags: [] },
  ].map(row => ({ ...row, year: 2026, state_code: 'NH', source_election_date: '2026-11-03',
    native_election_id_qualified: true, cast_ballot_count_qualified: false,
    unique_voter_count_qualified: false, denominator: null, reported_pct: null }));
  const municipalities = [...base.municipalities, ...profiles];
  const referenceQueries = base.reference_queries.map(row => {
    const city = municipalities.find(city => city.reference_key === row.contextual_municipality_key);
    return { ...row, source_city: city?.city ?? null, disposition: city
      ? 'native_city_source_count_on_older_municipality_context' : 'held_no_city_source_observation' };
  });
  return { ...base, summary: { ...base.summary, complete_source_field_queries: 242,
    source_city_observations: 4, native_ward_rows: 37, unmapped_reference_areas: 255,
    nashua_printed_total_sum: profiles[0].source_count,
    nashua_federal_only_separate_sum: sum(nashua.wards.map(row => row.federal_only)),
    nashua_component_minus_printed_sum: accounting.filter(row => row.city === 'Nashua')
      .reduce((total, row) => total + row.component_minus_printed_total, 0),
    dover_native_total_ballots: nativeTotal.total, dover_native_registered: nativeTotal.registered,
    dover_native_printed_turnout: nativeTotal.printed_turnout },
  source_queries: [...base.source_queries, ...sourceQueries],
  source_accounting_queries: [...base.source_accounting_queries, ...accounting],
  source_printed_rate_basis_queries: [...base.source_printed_rate_basis_queries, ...printedBasis],
  reference_queries: referenceQueries, municipalities, ward_rows: [...base.ward_rows, ...wards],
  reference_geometry: inputs.reference, complete_download_url: inputs.complete_download_url };
}

export function loadNewHampshireCityExtension() {
  const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
  for (const [path, receipt] of Object.entries(inputs.files)) {
    const body = readFileSync(path);
    if (body.length !== receipt.bytes || createHash('sha256').update(body).digest('hex') !== receipt.sha256)
      throw new Error(`Changed sufficient native city input: ${path}`);
  }
  return reviewNewHampshireCityExtension({ inputs, base: loadNewHampshireCities(),
    nashua: JSON.parse(readFileSync(inputs.readings_paths.nashua, 'utf8')),
    dover: JSON.parse(readFileSync(inputs.readings_paths.dover, 'utf8')) });
}

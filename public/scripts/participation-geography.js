export function countFill(value, maximum) {
  if (!Number.isFinite(value) || value < 0) return "#edf0f3";
  const t = maximum > 0 ? Math.sqrt(Math.min(1, value / maximum)) : 0;
  return `rgb(${[218, 230, 241].map((c, i) =>
    Math.round(c + t * ([40, 71, 102][i] - c))).join(",")})`;
}

export function precinctSelectionYears(loaded, requested, electionYears) {
  const years = new Set([...loaded, 2026]);
  const year = Number(requested);
  if (electionYears.includes(year)) years.add(year);
  return [...years].sort((a, b) => b - a);
}

export function qualifiedDcPrecinctParticipation(p, year) {
  const row = p.participation;
  return year === 2026 && p.year === year && p.state_code === "DC"
    && p.county_code === "11001" && p.match_status === "matched"
    && p.source_contest_id === "6"
    && p.key === `DC|11001|${p.precinct_code}|${p.source_contest_id}`
    && row?.key === p.key && row.year === year && row.state_code === "DC"
    && row.precinct === p.precinct_code && row.measure === "reported_ballots_and_registration"
    && Number.isSafeInteger(row.ballots) && row.ballots >= 0
    && Number.isSafeInteger(row.registered) && row.registered > 0 && row.ballots <= row.registered
    && Number.isFinite(row.reported_pct)
    && Math.abs(row.reported_pct - 100 * row.ballots / row.registered) < 1e-10;
}

export function qualifiedVaPrecinctParticipation(p, year) {
  const row = p.participation;
  return year === 2026 && p.year === year && p.state_code === "VA"
    && p.match_status === "matched" && p.reporting_unit_kind === "source_reporting_unit"
    && /^\d{3}$/.test(p.county_code) && typeof p.precinct_uuid === "string"
    && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(p.precinct_uuid)
    && (p.original_precinct_id === p.precinct_code
      || (/^\d{1,3}$/.test(p.original_precinct_id)
        && String(p.original_precinct_id).padStart(4, "0") === p.precinct_code))
    && p.key === `VA:${p.county_code}:${p.precinct_code}:${p.congressional_district}`
    && row?.measure === "reported_ballots_and_registration"
    && Number.isSafeInteger(row.ballots) && row.ballots >= 0
    && Number.isSafeInteger(row.registered) && row.registered >= 0
    && row.reported_pct === null;
}

export function qualifiedIndianaMonroePrecinct(p) {
  const row = p.native_record;
  return p.year === 2026 && p.state_code === "IN" && p.county_fips === "18105"
    && p.county_id === "additional:IN:18105" && p.match_status === "matched"
    && p.source_snapshot === "indiana-monroe-native-20261109-01"
    && Number.isSafeInteger(p.native_precinct_id) && p.native_precinct_id > 0
    && p.key === `IN|18105|${p.native_precinct_id}` && p.unit_key === String(p.native_precinct_id)
    && row?.Precinct_ID === p.native_precinct_id && row.Precinct === p.unit
    && Number.isSafeInteger(p.ballots) && p.ballots >= 0 && p.ballots === row.Ballots_Cast
    && row.Precinct_Reporting === "Partially Reporting"
    && p.denominator === null && p.reported_pct === null && p.geometry_withheld_reason === null;
}

export function qualifiedAlaskaNativePrecinct(p) {
  const native = p.native_record, reference = p.reference_geometry;
  return p.year === 2026 && p.state_code === "AK" && p.county_fips === null
    && p.source_snapshot === "alaska-native-display-20261110-01"
    && p.reporting_unit_kind === "geographic_precinct" && p.match_status === "matched"
    && p.count_scope === "native_geographic_house_unit_excludes_pooled_modes"
    && /^\d{2}-\d{3}$/.test(p.native_precinct_id) && /^\d+$/.test(p.source_sequence)
    && p.key === `AK|source-unit-${p.source_sequence}`
    && native?.number === p.native_precinct_id && p.unit === `${native.number} ${native.name}`
    && native.contest === "U.S. Representative"
    && Number.isSafeInteger(p.ballots) && p.ballots >= 0 && p.ballots === native.b
    && Number.isSafeInteger(native.v) && native.v >= 0
    && reference?.native_precinct_id === p.native_precinct_id
    && reference.source_selected_election_app === 2026 && reference.certified_legal_boundaries === false
    && reference.topology_valid_without_repairs === true && reference.single_path_per_polygon === true
    && /^[a-f0-9]{64}$/.test(reference.exact_millidegree_coordinate_sha256)
    && p.denominator === null && p.reported_pct === null && p.geometry_withheld_reason === null;
}

export function qualifiedManchesterWardReference(p) {
  const native = p.native_record, reference = p.reference_geometry, ward = p.native_ward_number;
  return p.year === 2026 && p.state_code === "NH" && p.county === "Manchester" && p.county_fips === null
    && p.county_id === "additional:NH:city:3345140"
    && p.source_snapshot === "manchester-native-ward-reference-20261110-01"
    && p.reporting_unit_kind === "municipal_ward" && p.unit_kind === "municipal_ward"
    && p.match_status === "matched_current_municipal_ward_reference"
    && Number.isInteger(ward) && ward >= 1 && ward <= 12
    && p.native_object_id === ward + 24 && p.key === `NH|Manchester|Ward:${ward}`
    && p.unit === `Ward ${ward}` && p.unit_key === `Manchester:Ward:${ward}`
    && p.source_election_date === "2026-11-03" && native?.ward === ward
    && Number.isSafeInteger(p.ballots) && p.ballots >= 0 && p.ballots === native.total
    && ["election_day", "absentee", "federal_only"].every(key => Number.isSafeInteger(native[key]) && native[key] >= 0)
    && p.source_count_qualified === true && p.cast_ballot_count_qualified === false
    && p.unique_voter_count_qualified === false && p.maps_approved === true
    && reference?.native_ward_number === ward && reference.native_ward_label === `Ward ${ward}`
    && reference.layer_name === "SDEweb.GISADMIN.Wards_2022" && reference.rest_layer_id === 3
    && reference.boundary_vintage === 2022 && reference.current_clerk_effective_date === "2021-12-21"
    && reference.certified_legal_boundaries === false && reference.topology_valid_without_repairs === true
    && reference.single_path_per_polygon === true && reference.native_overlaps_preserved === true
    && p.denominator === null && p.reported_pct === null && p.geometry_withheld_reason === null;
}

export function qualifiedConcordWardReference(p) {
  const native = p.native_record, reference = p.reference_geometry, ward = p.native_ward_number;
  const columns = native?.total_cast_columns;
  const objects = { 1: 11, 2: 7, 3: 6, 4: 9, 5: 10, 6: 5, 7: 8, 8: 3, 9: 4, 10: 12 };
  return p.year === 2026 && p.state_code === "NH" && p.county === "Concord" && p.county_fips === null
    && p.county_id === "additional:NH:city:3314200"
    && p.source_snapshot === "new-hampshire-native-ward-reference-20261110-02"
    && p.reporting_unit_kind === "municipal_ward" && p.unit_kind === "municipal_ward"
    && p.match_status === "matched_current_municipal_ward_reference"
    && Number.isInteger(ward) && ward >= 1 && ward <= 10 && p.native_object_id === objects[ward]
    && p.key === `NH|Concord|Ward:${ward}` && p.unit === `Ward ${ward}` && p.unit_key === `Concord:Ward:${ward}`
    && p.source_election_date === "2026-11-03"
    && Array.isArray(columns) && columns.length === (ward <= 2 ? 2 : 1)
    && columns.every(row => row.ward === ward && Number.isSafeInteger(row.count) && row.count >= 0)
    && (ward <= 2 ? new Set(columns.map(row => row.school_district)).size === 2
      && columns.every(row => ["Concord School District (CSD)", "Merrimack Valley School District (MVSD)"].includes(row.school_district))
      : columns[0].school_district === null)
    && Number.isSafeInteger(p.ballots) && p.ballots === columns.reduce((sum, row) => sum + row.count, 0)
    && native.printed_ward_subtotal === (ward <= 2 ? p.ballots : null)
    && ["opening", "election_day_registrations", "closing"].every(key => Number.isSafeInteger(native[key]) && native[key] >= 0)
    && native.opening + native.election_day_registrations === native.closing
    && p.source_count_qualified === true && p.cast_ballot_count_qualified === false
    && p.unique_voter_count_qualified === false && p.maps_approved === true
    && reference?.native_ward_number === ward && reference.native_ward_label === `Ward ${ward}`
    && reference.layer_name === "Voting Wards" && reference.rest_layer_id === 53
    && reference.boundary_vintage === null && reference.current_clerk_approval_date === "2021-11-08"
    && reference.native_projection_epsg === 3437 && reference.native_datum_operation?.wkid === 108190
    && reference.native_datum_operation.forward === false
    && reference.certified_legal_boundaries === false && reference.topology_valid_without_repairs === true
    && reference.single_path_per_polygon === true && reference.native_overlaps_preserved === true
    && p.denominator === null && p.reported_pct === null && p.geometry_withheld_reason === null;
}

export function qualifiedNashuaWardReference(p) {
  const native = p.native_record, reference = p.reference_geometry, ward = p.native_ward_number;
  const objects = { 1: 8, 2: 9, 3: 7, 4: 6, 5: 4, 6: 3, 7: 5, 8: 1, 9: 2 };
  return p.year === 2026 && p.state_code === "NH" && p.county === "Nashua" && p.county_fips === null
    && p.county_id === "additional:NH:city:3350260"
    && p.source_snapshot === "new-hampshire-native-ward-reference-20261110-03"
    && p.reporting_unit_kind === "municipal_ward" && p.unit_kind === "municipal_ward"
    && p.match_status === "matched_current_municipal_ward_reference"
    && Number.isInteger(ward) && ward >= 1 && ward <= 9 && p.native_object_id === objects[ward]
    && p.key === `NH|Nashua|Ward:${ward}` && p.unit === `Ward ${ward}` && p.unit_key === `Nashua:Ward:${ward}`
    && p.source_election_date === "2026-11-03" && native?.ward === ward
    && Number.isSafeInteger(p.ballots) && p.ballots >= 0 && p.ballots === native.total
    && ["election_day", "absentee", "federal_only"].every(key => Number.isSafeInteger(native[key]) && native[key] >= 0)
    && p.source_count_qualified === true && p.cast_ballot_count_qualified === false
    && p.unique_voter_count_qualified === false && p.maps_approved === true
    && reference?.native_ward_number === ward && reference.native_ward_label === `Ward ${ward}`
    && reference.layer_name === "Ward Boundary (Adopted December 28, 2021)" && reference.rest_layer_id === 7
    && reference.boundary_vintage === null && reference.adopted_date === "2021-12-28"
    && reference.effective_date === "2021-12-28" && reference.proposed_geometry_used === false
    && reference.native_projection_epsg === 3857
    && reference.current_map_effective_literal === "OCTOBER 2026" && reference.current_map_revised_literal === "OCTOBER 2026"
    && reference.certified_legal_boundaries === false && reference.topology_valid_without_repairs === true
    && reference.single_path_per_polygon === true && reference.native_overlaps_preserved === true
    && p.denominator === null && p.reported_pct === null && p.geometry_withheld_reason === null;
}

export function hasCountySourceMode(code, mode) {
  return ["WV", "ME", "IL"].includes(code) && ["in_person_early", "mail_returned"].includes(mode)
    || Boolean(providerCountyScopes[code]?.modes.includes(mode));
}

export function selectCountySourceFrame(data, code, mode) {
  if (["in_person_early", "mail_returned"].includes(mode)
    && data.counties.some(row => row.state_code === code && row.source_mode === "all_method_native_city_snapshot"))
    return [];
  if (code === "IL" && mode === "available"
    && !data.counties.some(row => row.state_code === code && row.ballots != null))
    return selectCountySourceFrame(data, code, "in_person_early");
  if (code === "ME" && mode === "available"
    && !data.counties.some(row => row.state_code === code && row.ballots != null))
    return selectCountySourceFrame(data, code, "in_person_early");
  if (mode === "available" && providerCountyScopes[code]
    && !data.counties.some(row => row.state_code === code && row.ballots != null)) {
    const preferred = ["in_person_early", "mail_returned"].find(m => providerCountyScopes[code].modes.includes(m));
    return selectCountySourceFrame(data, code, preferred);
  }
  if (!hasCountySourceMode(code, mode)) return data.counties;
  const rows = data.county_frames?.[mode];
  if (code === "IL") {
    if (!qualifiedIllinoisCountyContextFrame(rows, mode)
      || !qualifiedIllinoisCityHolds(data.county_frame_holds?.[mode], rows, mode))
      throw new Error("Unqualified Illinois source-region context; city counts and county totals are not substituted");
    return rows;
  }
  if (code === "ME") {
    if (!qualifiedMaineLocalityFrame(rows, mode))
      throw new Error("Unqualified Maine locality activity frame; county totals are not substituted");
    return rows;
  }
  if (Array.isArray(rows) && rows.length && rows.every(row => row.source_provider === "civicAPI early activity")) {
    if (!qualifiedProviderCountyFrame(rows, code, mode))
      throw new Error("Unqualified provider county activity frame; full-election counts are not substituted");
    return rows;
  }
  if (code !== "WV" || !Array.isArray(rows) || rows.length !== 55
    || new Set(rows.map(row => row.county_fips)).size !== 55
    || rows.some(row => row.year !== 2026 || row.state_code !== code || row.source_mode !== mode
      || !/^54\d{3}$/.test(row.county_fips) || row.county_id !== `additional:WV:${row.county_fips}`
      || !Number.isSafeInteger(row.ballots) || row.ballots < 0
      || row.ballots !== row.native_record?.["TOTAL VOTERS"]
      || row.denominator !== null || row.reported_pct !== null
      || row.unique_voter_count_qualified !== false || row.cast_ballot_count_qualified !== false))
    throw new Error(`Unqualified ${code} county source mode; all-method counts are not substituted`);
  return rows;
}

function qualifiedIllinoisCityHolds(holds, rows, mode) {
  const names = new Set(["City of Bloomington", "City of Chicago", "City of Danville",
    "City of East St Louis", "City of Galesburg", "City of Rockford"]);
  if (!Array.isArray(holds) || holds.length !== 6
    || new Set(holds.map(row => row.source_region)).size !== 6) return false;
  return holds.every(row => row.state_code === "IL" && row.mode === mode && names.has(row.source_region)
    && row.contextual_county_fips === null && row.whole_county_count_qualified === false
    && row.source_authority_territory_qualified === false && row.native_geography_id_qualified === false
    && row.source_date === "2026-11-04" && row.denominator === null && row.reported_pct === null
    && row.native_categories && Object.values(row.native_categories).length > 0
    && Object.values(row.native_categories).every(r => Number.isSafeInteger(r.votes) && r.votes >= 0)
    && row.source_count === Object.values(row.native_categories).reduce((s, r) => s + r.votes, 0))
    && [...rows.map(row => row.ballots), ...holds.map(row => row.source_count)].reduce((s, r) => s + r, 0)
      === (mode === "in_person_early" ? 1162828 : 892086);
}

export function qualifiedIllinoisCountyContextFrame(rows, mode) {
  if (!["in_person_early", "mail_returned"].includes(mode) || !Array.isArray(rows) || rows.length !== 102
    || new Set(rows.map(r => r.contextual_county_fips)).size !== 102) return false;
  return rows.every(row => {
    const native = row.native_record, categories = native?.categories;
    return row.year === 2026 && row.state_code === "IL" && row.source_mode === mode
      && row.source_provider === "civicAPI early activity"
      && row.geography_level === "provider_county_named_region_context"
      && /^17\d{3}$/.test(row.contextual_county_fips) && row.county_fips === row.contextual_county_fips
      && row.county_id === `additional:IL:source-region:${row.contextual_county_fips}`
      && row.count_scope === "literal_county_named_source_region_not_whole_county"
      && row.native_geography_id_qualified === false && row.whole_county_count_qualified === false
      && row.source_authority_territory_qualified === false && row.native_election_id_qualified === false
      && row.cast_ballot_count_qualified === false && row.unique_voter_count_qualified === false
      && native?.state === "IL" && native.source_region === row.county && !/^City of /i.test(row.county)
      && native.category === (mode === "in_person_early" ? "inperson" : "returned")
      && native.snapshot_date === "2026-11-04" && row.source_date === native.snapshot_date
      && native.literal_count_field === "votes"
      && categories && typeof categories === "object" && !Array.isArray(categories) && Object.keys(categories).length > 0
      && Object.values(categories).every(r => Number.isSafeInteger(r.votes) && r.votes >= 0)
      && Number.isSafeInteger(row.ballots) && row.ballots >= 0
      && row.ballots === Object.values(categories).reduce((s, r) => s + r.votes, 0)
      && row.denominator === null && row.reported_pct === null
      && row.reference_geometry?.geography_scope === "county_context_not_source_authority_territory"
      && row.reference_geometry.boundary_year === 2026 && row.reference_geometry.counties === 102
      && row.reference_geometry.source_authority_territories_qualified === false
      && row.reference_geometry.whole_county_counts_qualified === false;
  });
}

export function qualifiedIllinoisCountyContextReference(rows, reference, collection) {
  const mode = rows?.[0]?.source_mode;
  if (!qualifiedIllinoisCountyContextFrame(rows, mode)
    || reference.geography_scope !== "county_context_not_source_authority_territory"
    || reference.source_authority_territories_qualified !== false
    || reference.whole_county_counts_qualified !== false
    || !Array.isArray(collection?.features) || collection.features.length !== 102) return false;
  const identities = new Set(rows.map(r => r.contextual_county_fips));
  const keys = collection.features.map(f => f.properties?.key);
  return new Set(keys).size === 102 && keys.every(key => identities.has(key))
    && collection.features.every(f => f.geometry && f.properties.state_code === "IL"
      && f.properties.boundary_year === 2026);
}

export function qualifiedDoverWardReference(p) {
  const reference = p?.reference_geometry, native = p?.native_record;
  const ward = p?.native_ward_number;
  return p?.source_snapshot === "new-hampshire-native-ward-reference-20261110-04"
    && p.year === 2026 && p.state_code === "NH" && p.county === "Dover"
    && p.source_election_date === "2026-11-03"
    && Number.isInteger(ward) && ward >= 1 && ward <= 6 && p.native_object_id === 279 + ward
    && p.native_district === `Dover Ward ${ward}` && p.key === `NH|Dover|Ward:${ward}`
    && p.unit_key === `Dover:Ward:${ward}` && p.county_id === "additional:NH:city:3318820"
    && p.county_fips === null && p.unit_kind === "municipal_ward"
    && p.reporting_unit_kind === "municipal_ward"
    && Number.isSafeInteger(p.ballots) && p.ballots >= 0
    && p.denominator === null && p.reported_pct === null && p.geometry_withheld_reason === null
    && p.maps_approved === true && p.source_count_qualified === true
    && p.cast_ballot_count_qualified === false && p.unique_voter_count_qualified === false
    && native?.ballots?.ward === ward && native.registrations?.ward === ward
    && native.ballots.total === p.ballots && native.ballots.registered === native.registrations.registered
    && p.participation_measure_label === "Native Total Ballots Cast"
    && reference?.source_owner === "NHGRANIT"
    && reference.source_item_id === "3d1a8bdf3eaa49e09cf5d9da5b56bf9c"
    && reference.layer_name === "NHPolitDists_VW_2022" && reference.rest_layer_id === 11
    && reference.boundary_vintage === 2022 && reference.native_projection_epsg === 3437
    && reference.native_datum_operation?.authority === "ESRI"
    && reference.native_datum_operation.code === 108190 && reference.native_datum_operation.direction === "inverse"
    && reference.native_ward_number === ward && reference.native_ward_label === `Dover Ward ${ward}`
    && reference.native_fips === 17010 && reference.native_fips_is_not_a_county_id === true
    && reference.certified_legal_boundaries === false && reference.topology_valid_without_repairs === true
    && reference.single_path_per_polygon === true && reference.cyclic_vertex_adjacency_verified === true
    && reference.source_geometry_clipped === false && reference.native_overlaps_preserved === true;
}

export function qualifiedNewHampshireCityReference(rows, reference, collection) {
  const expected = new Map([["Concord", "3314200"], ["Manchester", "3345140"]]);
  if (reference?.review_id === "new-hampshire-native-cities-20261110-02") {
    expected.set("Nashua", "3350260"); expected.set("Dover", "3318820");
  } else if (reference?.review_id !== "new-hampshire-native-cities-20261110-01") return false;
  if (!Array.isArray(rows) || rows.length !== expected.size
    || reference.geography_scope !== "native_partial_city_reporting_context"
    || reference.boundary_year !== 2024 || reference.localities !== 259 || reference.mapped_localities !== expected.size
    || reference.certified_election_boundaries !== false
    || !Array.isArray(collection?.features) || collection.features.length !== 259) return false;
  const identities = new Set(collection.features.map(f => f.properties?.key));
  if (identities.size !== 259 || rows.some(row => expected.get(row.county) !== row.reference_municipality_key)
    || new Set(rows.map(row => row.county)).size !== expected.size
    || collection.features.some(f => !f.geometry || f.properties.state_code !== "NH"
      || f.properties.boundary_year !== 2024)) return false;
  return rows.every(row => {
    const source = row.native_record;
    if (row.year !== 2026 || row.state_code !== "NH" || row.geography_level !== "municipality"
      || row.county_fips !== null || row.county_id !== `additional:NH:city:${row.reference_municipality_key}`
      || !identities.has(row.reference_municipality_key) || row.source_city_name !== row.county
      || row.native_election_id_qualified !== true || row.source_election_date !== "2026-11-03"
      || row.cast_ballot_count_qualified !== false || row.unique_voter_count_qualified !== false
      || !Number.isSafeInteger(row.ballots) || row.ballots < 0
      || row.denominator !== null || row.reported_pct !== null) return false;
    if (row.county === "Concord")
      return row.source_count_basis === "native_printed_city_total_cast" && row.native_city_parent_printed === true
        && source?.native_election_label === "November 3, 2026 State General Election Results"
        && source.literal_measure === "Total Cast" && source.native_city_total_cast === row.ballots
        && source.total_cast_columns?.length === 12
        && source.total_cast_columns.every(r => Number.isSafeInteger(r.count) && r.count >= 0)
        && source.total_cast_columns.reduce((s, r) => s + r.count, 0) === row.ballots;
    if (row.county === "Dover") {
      const native = source?.native_ballot_rows, registers = source?.native_register_rows;
      return row.source_count_basis === "native_printed_city_total_ballots_cast"
        && row.native_city_parent_printed === true
        && source?.native_election_label === "NOVEMBER 3, 2026 GENERAL ELECTION"
        && source.native_ballot_labels?.total === "Total Ballots Cast"
        && source.native_ballot_labels?.registered === "All Registered Voters"
        && native?.length === 7 && registers?.length === 7
        && native.every((r, i) => r.ward === (i < 6 ? i + 1 : "TOTAL")
          && Number.isSafeInteger(r.total) && r.total >= 0
          && registers[i].ward === r.ward && registers[i].registered === r.registered)
        && native[6].total === row.ballots
        && native.slice(0,6).reduce((s, r) => s + r.total, 0) === row.ballots;
    }
    const wardCount = row.county === "Nashua" ? 9 : 12;
    return row.source_count_basis === `derived_sum_complete${wardCount}_printed_totals_not_repaired`
      && row.native_city_parent_printed === false
      && source?.native_election_label === "General Election November 3, 2026"
      && source.federal_only_added_to_total === false && source.wards?.length === wardCount
      && new Set(source.wards.map(r => r.ward)).size === wardCount
      && source.wards.every(r => Number.isInteger(r.ward) && r.ward >= 1 && r.ward <= wardCount
        && Number.isSafeInteger(r.total) && r.total >= 0)
      && source.wards.reduce((s, r) => s + r.total, 0) === row.ballots;
  });
}

export function qualifiedMassachusettsCityReference(rows, reference, collection) {
  const expected = new Map([["Boston", ["MA:TOWN:035", 185569]], ["Somerville", ["MA:TOWN:274", 64597]]]);
  if (!Array.isArray(rows) || rows.length !== 2
    || reference?.review_id !== "20261110-massachusetts-native-local-counts-01"
    || reference.geography_scope !== "native_partial_city_reporting_context"
    || reference.boundary_year !== null || reference.localities !== 350
    || reference.native_source_localities !== 351 || reference.mapped_localities !== 2
    || reference.certified_election_boundaries !== false || reference.source_geometries_repaired !== false
    || reference.geometry_holds?.length !== 1 || reference.geometry_holds[0].native_town_id !== 315
    || collection?.features?.length !== 350) return false;
  const identities = new Set(collection.features.map(feature => feature.properties?.key));
  if (identities.size !== 350 || new Set(rows.map(row => row.county)).size !== 2
    || collection.features.some(feature => !["Polygon", "MultiPolygon"].includes(feature.geometry?.type)
      || feature.properties.state_code !== "MA" || feature.properties.level !== "municipality"
      || feature.properties.boundary_year !== null || feature.properties.native_town_id === 315
      || feature.properties.topology_valid_without_repairs !== true
      || feature.properties.certified_legal_boundaries !== false)) return false;
  return rows.every(row => {
    const profile = expected.get(row.county), source = row.native_record;
    if (!profile || row.reference_municipality_key !== profile[0] || !identities.has(profile[0])
      || row.ballots !== profile[1] || row.year !== 2026 || row.state_code !== "MA"
      || row.geography_level !== "municipality" || row.county_fips !== null
      || row.county_id !== `additional:MA:city:${profile[0]}` || row.source_city_name !== row.county
      || row.source_mode !== "all_method_native_city_snapshot"
      || row.native_election_id_qualified !== true || row.source_election_date !== "2026-11-03"
      || row.cast_ballot_count_qualified !== false || row.unique_voter_count_qualified !== false
      || row.denominator !== null || row.reported_pct !== null
      || source?.native_city_ballots_cast !== row.ballots) return false;
    if (row.county === "Boston")
      return source.native_summary_voters_cast === 556369 && source.native_summary_registered === 0
        && source.native_summary_pct === "N/A" && source.native_context_checks?.length === 44
        && source.native_context_checks.slice(0, 6).every(check => check.precinct_rows === 275
          && check.derived_times_cast_sum === 185569 && check.all_rows_match_senate_native_field === true);
    return source.native_registered_voters === 56008 && source.original_page_status === "Official"
      && source.original_document_status === "UnOfficial" && source.all_source_reporting_rows?.length === 40
      && source.all_source_reporting_rows.filter(unit => unit.native_level === "precinct").length === 32
      && source.all_source_reporting_rows.filter(unit => unit.native_level === "precinct")
        .reduce((sum, unit) => sum + unit.ballots_cast_literal, 0) === 64597;
  });
}

export function qualifiedMassachusettsReportingReference(p) {
  const reference = p?.reference_geometry;
  const cityReference = p?.source_snapshot === "20261110-massachusetts-city-precinct-reference-02"
    && p.county === "Somerville";
  if (!["20261110-massachusetts-native-local-counts-01",
    "20261110-massachusetts-city-precinct-reference-02"].includes(p?.source_snapshot)
    || p.year !== 2026 || p.state_code !== "MA" || p.source_election_date !== "2026-11-03"
    || !["Boston", "Somerville"].includes(p.county) || p.county_fips !== null
    || p.source_count_qualified !== true || p.cast_ballot_count_qualified !== false
    || p.unique_voter_count_qualified !== false || p.maps_approved !== true
    || !Number.isSafeInteger(p.ballots) || p.ballots < 0
    || p.denominator !== null || p.reported_pct !== null || p.geometry_withheld_reason !== null
    || reference?.rest_layer_id !== (cityReference ? null : 0)
    || reference.boundary_vintage !== (cityReference ? null : 2022)
    || reference.certified_legal_boundaries !== false || reference.topology_valid_without_repairs !== true
    || reference.single_path_per_polygon !== true || reference.native_overlaps_preserved !== true
    || reference.source_geometry_clipped !== false) return false;
  const ward = String(p.native_ward_number), precinct = p.native_precinct_label;
  const unitKey = `${p.county}:Ward:${ward}:Precinct:${precinct}`;
  if (p.unit_key !== unitKey || p.key !== `MA|${unitKey}`
    || p.county_id !== `additional:MA:city:MA:TOWN:${p.county === "Boston" ? "035" : "274"}`
    || p.native_record?.ward !== ward || p.native_record?.precinct !== precinct
    || !Number.isInteger(p.native_object_id)) return false;
  if (p.county === "Boston")
    return /^[1-9]\d*$/.test(precinct) && p.native_ward_number >= 1 && p.native_ward_number <= 22
      && p.unit_kind === "municipal_precinct" && p.reporting_unit_kind === "municipal_precinct"
      && reference.source_item_id === "a8ae7fca286d4441901a97d116d6c9fa"
      && reference.native_reference_source === "boston" && reference.native_projection_epsg === 3857
      && p.native_record.times_cast_literal === p.ballots && p.native_record.registered_voters_literal === 0
      && p.participation_measure_label === "Native Times Cast";
  if (p.native_ward_number < 1 || p.native_ward_number > 7
    || p.native_record.ballots_cast_literal !== p.ballots
    || p.native_record.source_document_literal_status !== "UnOfficial"
    || p.native_record.declaring_page_heading_literal_status !== "Official"
    || p.participation_measure_label !== "Native BALLOTS CAST - TOTAL") return false;
  if (cityReference)
    return reference.source_item_id === null && reference.source_dataset_id === "da4y-vuae"
      && reference.native_reference_source === "somerville-city-precincts"
      && reference.native_projection_epsg === null
      && reference.native_projection_wkt_sha256 === "78723c57dc900ff30b1a01ba02ca9aeea20b7107f50a3f7ed86b50e45f2b5ad1"
      && reference.source_metadata_revision === "2023-09-22" && reference.source_census_basis === 2020
      && reference.cyclic_vertex_adjacency_verified === true && reference.duplicate_native_ids_preserved === true
      && p.native_source_label === `${ward}-${precinct}`
      && (precinct?.endsWith("A")
        ? ["1:4A", "2:1A", "4:2A", "6:3A"].includes(`${ward}:${precinct}`)
          && p.unit_kind === "municipal_subprecinct" && p.reporting_unit_kind === "municipal_subprecinct"
        : /^[1-4]$/.test(precinct)
          && p.unit_kind === "municipal_precinct" && p.reporting_unit_kind === "municipal_precinct");
  if (reference.native_projection_epsg !== 26986) return false;
  if (precinct?.endsWith("A"))
    return ["1:4A", "2:1A", "4:2A", "6:3A"].includes(`${ward}:${precinct}`)
      && p.unit_kind === "municipal_subprecinct" && p.reporting_unit_kind === "municipal_subprecinct"
      && reference.source_item_id === "c96fa785cc694bcdbc07032be7d9365a"
      && reference.native_reference_source === "somerville-subprecincts";
  return /^[1-4]$/.test(precinct) && !["1:4", "2:1", "4:2", "6:3"].includes(`${ward}:${precinct}`)
    && p.unit_kind === "municipal_precinct" && p.reporting_unit_kind === "municipal_precinct"
    && reference.source_item_id === "6d4ae7efad4f4c77907db7cbfb012e64"
    && reference.native_reference_source === "somerville-parent-precincts";
}

export function qualifiedProviderCountyFrame(rows, code, mode) {
  const scope = providerCountyScopes[code];
  if (!scope?.modes.includes(mode) || !Array.isArray(rows) || rows.length !== scope.counties
    || new Set(rows.map(r => r.county_fips)).size !== scope.counties) return false;
  return rows.every(row => {
    const source = row.native_record, categories = source?.categories;
    return row.year === 2026 && row.state_code === code && row.source_mode === mode
      && row.source_provider === "civicAPI early activity"
      && /^\d{5}$/.test(row.county_fips) && row.county_id === `additional:${code}:${row.county_fips}`
      && source?.state === code && source.category === (mode === "in_person_early" ? "inperson" : "returned")
      && source.literal_count_field === "votes" && /^2026-\d{2}-\d{2}$/.test(source.snapshot_date)
      && row.source_date === source.snapshot_date && row.native_election_id_qualified === false
      && categories && typeof categories === "object" && !Array.isArray(categories)
      && Object.keys(categories).length > 0
      && Object.values(categories).every(r => Number.isSafeInteger(r.votes) && r.votes >= 0)
      && Number.isSafeInteger(row.ballots) && row.ballots >= 0
      && row.ballots === Object.values(categories).reduce((sum, r) => sum + r.votes, 0)
      && row.reference_geometry?.counties === scope.counties && row.reference_geometry.boundary_year === 2026
      && row.denominator === null && row.reported_pct === null
      && row.cast_ballot_count_qualified === false && row.unique_voter_count_qualified === false;
  });
}

export function qualifiedMaineLocalityFrame(rows, mode) {
  if (!["in_person_early", "mail_returned"].includes(mode) || !Array.isArray(rows) || rows.length !== 480
    || new Set(rows.map(r => r.reference_municipality_key)).size !== 480) return false;
  return rows.every(row => {
    const native = row.native_record, categories = native?.categories;
    return row.year === 2026 && row.state_code === "ME" && row.source_mode === mode
      && row.source_provider === "civicAPI early activity" && row.county_fips === null
      && row.geography_level === "source_locality_activity" && /^23\d{5}$/.test(row.reference_municipality_key)
      && row.county_id === `additional:ME:locality:${row.reference_municipality_key}`
      && row.reference_geometry?.boundary_year === 2024 && row.reference_geometry.localities === 528
      && row.reference_geometry.geography_scope === "provider_partial_locality_activity"
      && native?.state === "ME" && native.source_region === row.county
      && native.category === (mode === "in_person_early" ? "inperson" : "returned")
      && native.literal_count_field === "votes" && /^2026-\d{2}-\d{2}$/.test(native.snapshot_date)
      && row.source_date === native.snapshot_date && row.native_election_id_qualified === false
      && categories && typeof categories === "object" && !Array.isArray(categories) && Object.keys(categories).length > 0
      && Object.values(categories).every(r => Number.isSafeInteger(r.votes) && r.votes >= 0)
      && Number.isSafeInteger(row.ballots) && row.ballots >= 0
      && row.ballots === Object.values(categories).reduce((sum, r) => sum + r.votes, 0)
      && row.denominator === null && row.reported_pct === null
      && row.cast_ballot_count_qualified === false && row.unique_voter_count_qualified === false;
  });
}

export function qualifiedMaineLocalityReference(rows, reference, collection) {
  if (!qualifiedMaineLocalityFrame(rows, rows?.[0]?.source_mode)
    || reference?.boundary_year !== 2024 || reference.localities !== 528
    || reference.identity_field !== "reference_municipality_key"
    || reference.geography_scope !== "provider_partial_locality_activity"
    || !Array.isArray(collection?.features) || collection.features.length !== 528
    || new Set(collection.features.map(f => f.properties.key)).size !== 528
    || collection.features.some(f => f.properties.state_code !== "ME"
      || f.properties.boundary_year !== 2024 || f.properties.level !== "municipality")) return false;
  const keys = new Set(collection.features.map(f => f.properties.key));
  return rows.every(row => keys.has(row.reference_municipality_key));
}

export function qualifiedConnecticutTownReference(rows, reference, collection) {
  if (reference?.geography_scope !== "native_town_reporting_area"
    || reference.identity_field !== "source_administration_id"
    || reference.boundary_year !== 2024 || reference.localities !== 169
    || !Array.isArray(rows) || rows.length !== 169
    || new Set(rows.map(r => r.source_administration_id)).size !== 169
    || !Array.isArray(collection?.features) || collection.features.length !== 169
    || new Set(collection.features.map(f => f.properties.key)).size !== 169) return false;
  const shapes = new Map(collection.features.map(f => [f.properties.key, f.properties]));
  return rows.every(row => {
    const p = shapes.get(row.source_administration_id), native = row.native_record;
    return p && typeof row.source_town_id === "string"
      && row.source_administration_id === `CT-TOWN-${row.source_town_id.padStart(3, "0")}`
      && /^(?:[1-9]|[1-9]\d|1[0-5]\d|16[0-9])$/.test(row.source_town_id)
      && p.source_town_id === row.source_town_id && p.source_administration_id === row.source_administration_id
      && p.name === row.county && native?.NM === row.county
      && p.state_code === "CT" && p.boundary_year === 2024
      && row.year === 2026 && row.state_code === "CT" && row.county_fips === null
      && row.geography_level === "municipality" && row.source_election_id === "108"
      && row.county_id === `additional:CT:${row.source_administration_id}`
      && native.source_town_id === row.source_town_id && row.native_election_id_qualified === true
      && /^\d+$/.test(native.VV) && row.ballots === Number(native.VV)
      && Number.isSafeInteger(row.ballots) && row.ballots >= 0
      && row.denominator === null && row.reported_pct === null
      && row.cast_ballot_count_qualified === false && row.unique_voter_count_qualified === false;
  });
}

export function qualifiedHawaiiAdministrationReference(rows, reference, collection) {
  const members = {
    "HI-HONOLULU": ["15003"], "HI-HAWAII": ["15001"], "HI-KAUAI": ["15007"],
    "HI-MAUI": ["15009", "15005"],
  };
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  if (reference?.geography_scope !== "native_election_administration"
    || reference.identity_field !== "source_administration_id" || reference.boundary_year !== 2026
    || reference.administration_count !== 4 || reference.Census_counties !== 5 || reference.counties !== 4
    || !Array.isArray(rows) || rows.length !== 4
    || new Set(rows.map(r => r.source_administration_id)).size !== 4
    || !Array.isArray(collection?.features) || collection.features.length !== 4
    || new Set(collection.features.map(f => f.properties.key)).size !== 4) return false;
  const shapes = new Map(collection.features.map(f => [f.properties.key, f.properties]));
  return rows.every(row => {
    const identity = row.source_administration_id, p = shapes.get(identity);
    return members[identity] && p && p.source_administration_id === identity && p.name === row.county
      && p.state_code === "HI" && p.boundary_year === 2026
      && same(p.component_county_fips, members[identity]) && same(row.component_county_fips, members[identity])
      && row.year === 2026 && row.state_code === "HI" && row.county_fips === null
      && row.geography_level === "election_administration" && row.county_id === `additional:HI:${identity}`
      && row.native_record?.source_administration_id === identity
      && row.ballots === row.native_record.native_values?.["TOTAL TURNOUT"]
      && Number.isSafeInteger(row.ballots) && row.ballots >= 0
      && row.denominator === null && row.reported_pct === null
      && row.cast_ballot_count_qualified === false && row.unique_voter_count_qualified === false;
  });
}
import { providerCountyScopes } from "./provider-county-scopes.js";

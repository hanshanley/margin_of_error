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

export function hasCountySourceMode(code, mode) {
  return ["WV", "ME", "IL"].includes(code) && ["in_person_early", "mail_returned"].includes(mode)
    || Boolean(providerCountyScopes[code]?.modes.includes(mode));
}

export function selectCountySourceFrame(data, code, mode) {
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

export function qualifiedNewHampshireCityReference(rows, reference, collection) {
  if (!Array.isArray(rows) || rows.length !== 2
    || reference.geography_scope !== "native_partial_city_reporting_context"
    || reference.boundary_year !== 2024 || reference.localities !== 259 || reference.mapped_localities !== 2
    || reference.certified_election_boundaries !== false
    || !Array.isArray(collection?.features) || collection.features.length !== 259) return false;
  const expected = new Map([["Concord", "3314200"], ["Manchester", "3345140"]]);
  const identities = new Set(collection.features.map(f => f.properties?.key));
  if (identities.size !== 259 || rows.some(row => expected.get(row.county) !== row.reference_municipality_key)
    || new Set(rows.map(row => row.county)).size !== 2
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
    return row.source_count_basis === "derived_sum_complete12_printed_totals_not_repaired"
      && row.native_city_parent_printed === false
      && source?.native_election_label === "General Election November 3, 2026"
      && source.federal_only_added_to_total === false && source.wards?.length === 12
      && new Set(source.wards.map(r => r.ward)).size === 12
      && source.wards.every(r => Number.isInteger(r.ward) && r.ward >= 1 && r.ward <= 12
        && Number.isSafeInteger(r.total) && r.total >= 0)
      && source.wards.reduce((s, r) => s + r.total, 0) === row.ballots;
  });
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

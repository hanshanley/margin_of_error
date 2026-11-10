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

export function hasCountySourceMode(code, mode) {
  return code === "WV" && ["in_person_early", "mail_returned"].includes(mode)
    || Boolean(providerCountyScopes[code]?.modes.includes(mode));
}

export function selectCountySourceFrame(data, code, mode) {
  if (mode === "available" && providerCountyScopes[code]
    && !data.counties.some(row => row.state_code === code && row.ballots != null)) {
    const preferred = ["in_person_early", "mail_returned"].find(m => providerCountyScopes[code].modes.includes(m));
    return selectCountySourceFrame(data, code, preferred);
  }
  if (!hasCountySourceMode(code, mode)) return data.counties;
  const rows = data.county_frames?.[mode];
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

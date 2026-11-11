export const pointSourceURL = "https://raw.githubusercontent.com/hanshanley/voter-participation/043ece3c29e501f4f691cb87fc497da7e90d159d/data/participation-cps-2002/20261111-01/observations.json";
export const pointSourceSHA256 = "9d9fe04a02ca1aec9563699d4145e6657777cb01d3af0dbfec69ecf85df0de2d";
export const pointOnlyGroups = [
  "White (2002 native category)", "Non-Hispanic White (2002 native category)",
  "Black (2002 native category)", "Non-Hispanic Black (2002 native category)",
  "Asian and Pacific Islander (2002 native category)",
];
const labels = new Map([
  ["Total", ["sex_race", ".Total"]], ["Male", ["sex_race", ".Male"]],
  ["Female", ["sex_race", ".Female"]],
  ["Hispanic (any race)", ["sex_race", ".Hispanic (of any race)"]],
  ...["18 to 24", "25 to 44", "45 to 64", "65 to 74", "75+"].map(group => [group, ["age", "." + group]]),
  ...pointOnlyGroups.map(group => [group, ["sex_race", "." + group.replace(" (2002 native category)", "")]]),
]);

export function validatePointSource(data) {
  if (data?.contract !== "participation.cps_2002_reported_points.v1"
      || data.records?.length !== 832 || data.summary?.selected_reported_point_rows !== 693
      || data.policy?.new_intervals_allowed !== false
      || data.policy?.race_harmonization_allowed !== false)
    throw new Error("Unqualified 2002 point source");
  const keys = new Set();
  for (const row of data.records) {
    if (!row.source_key || keys.has(row.source_key) || row.native?.year !== 2002
        || row.standard_error !== null || row.interpreted_workbook_interval !== null
        || row.population_frame !== (row.native.role === "citizen_overall" ? "cvap" : "vap")
        || row.native.denominator !== (row.population_frame === "cvap" ? "citizen" : "18+")
        || (row.decision === "selected_reported_point_only"
          ? typeof row.selected_voted_pct !== "number" || row.selected_voted_pct < 0
            || row.selected_voted_pct > 100 || row.native.native_flags.length > 0
          : row.selected_voted_pct !== null))
      throw new Error("2002 point identity, frame, source hold or precision differs");
    keys.add(row.source_key);
  }
  return data;
}

export function pointFor2002(data, geography, group, citizen = false) {
  const nativeGeography = geography === "United States (including D.C.)" ? "UNITED STATES" : geography.toUpperCase();
  const definition = citizen ? group === "Total" ? ["citizen_overall", null] : null : labels.get(group);
  const row = definition ? data.records.find(record =>
    record.native.geography === nativeGeography && record.native.role === definition[0]
    && (definition[1] === null || record.native.native_label === definition[1])) : null;
  const rate = row?.decision === "selected_reported_point_only" ? row.selected_voted_pct : null;
  const decision = row?.decision || "not_supplied";
  const reason = decision === "withheld_cross_table_total_count_conflict" ? "Withheld: conflicting native totals"
    : decision === "withheld_native_inconsistency" ? "Withheld: native source inconsistency"
      : decision === "withheld_native_missing_or_suppressed_rate" ? "Not published: missing or suppressed source rate"
        : decision === "withheld_weighted_population_caution" ? "Withheld: weighted population-base caution"
          : "Not supplied for this source population/group";
  return { sourceKey: row?.source_key || "", rate, decision,
    text: rate === null ? reason : `${rate.toFixed(1)}% · workbook margin not qualified` };
}

export async function load2002Points() {
  const response = await fetch(pointSourceURL);
  if (!response.ok) throw new Error("2002 source unavailable");
  const body = await response.arrayBuffer();
  const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))]
    .map(value => value.toString(16).padStart(2, "0")).join("");
  if (hash !== pointSourceSHA256) throw new Error("2002 source checksum differs");
  return validatePointSource(JSON.parse(new TextDecoder().decode(body)));
}

export const pointSourceURL = "https://raw.githubusercontent.com/hanshanley/voter-participation/e6e85ce7e8b371ebd952f5173b60df43869e8832/data/participation-cps-1996-state-points/20261112-01/complete-result.json";
export const pointSourceSHA256 = "5132058d432233e18d249f6d9371e2ce454bb8ecc5ba895c23b521ef96adc622";
const definitions = new Map([
  ["Total", ["A", "ALL RACES", "18_plus"]],
  ["Male", ["B", "MALE", "18_plus"]], ["Female", ["B", "FEMALE", "18_plus"]],
  ["Hispanic (any race)", ["A", "HISPANIC ORIGIN", "18_plus"]],
  ["White (1998/2002 native category)", ["A", "WHITE", "18_plus"]],
  ["Black (1998/2002 native category)", ["A", "BLACK", "18_plus"]],
  ...[["18 to 24", "18_24"], ["25 to 44", "25_44"], ["45 to 64", "45_64"], ["65+", "65_plus"]]
    .map(([label, age]) => [label, ["A", "ALL RACES", age]]),
]);
const percent = value => typeof value === "string" && /^\d+(?:\.\d+)?$/.test(value)
  && Number(value) <= 100 ? Number(value) : null;

export function validate1996Points(data) {
  if (data?.contract !== "participation.cps_1996_state_points.v1" || data.records?.length !== 1923
      || data.summary?.native_cells !== 19539 || data.summary?.metric_decisions !== 4576
      || data.summary?.dispositions?.selected_native_percentage !== 4142
      || data.policy?.count_unit !== "rounded_thousands_not_sample_N"
      || data.policy?.unknown_voting_is_nonvote !== false
      || data.policy?.citizen_state_totals_from_sex_sums !== false
      || data.policy?.standard_errors !== null || data.policy?.confidence_intervals !== null)
    throw new Error("Unqualified 1996 source frames");
  const keys = new Set(), coordinates = new Set(), counts = { A: 0, B: 0, C: 0 };
  for (const row of data.records) {
    const coordinate = [row.table, row.reference_state_code, row.native_group, row.age].join("|");
    if (!Object.hasOwn(counts, row.table) || !row.source_key || keys.has(row.source_key)
        || coordinates.has(coordinate) || row.year !== 1996 || row.election_type !== "presidential"
        || row.population_frame !== (row.table === "C" ? "cvap" : "vap")
        || row.count_unit !== "rounded_thousands_not_sample_N" || row.local_allocation !== false
        || !/^\d+$/.test(row.raw_values?.population_thousands))
      throw new Error("1996 source identity or denominator differs");
    const metrics = row.table === "C" ? ["not_registered", "registered", "unknown_registration",
      "not_voted", "voted", "unknown_voting"] : ["registered", "voted"];
    for (const metric of metrics) {
      const measure = row.measures?.[metric], raw = row.raw_values[metric + "_pct"];
      const rate = percent(raw);
      const expected = raw === "(B)" ? "withheld_native_B" : rate === null
        ? "withheld_invalid_native_percentage" : Number(row.raw_values.population_thousands) === 0
          ? "withheld_rounded_zero_base" : "selected_native_percentage";
      if (!measure || measure.raw_percentage !== raw || measure.disposition !== expected
          || (expected === "selected_native_percentage" ? percent(measure.selected_percentage) !== rate
            : measure.selected_percentage !== null)
          || measure.sample_n !== null || measure.standard_error !== null || measure.confidence_interval !== null)
        throw new Error("1996 source point, missingness or uncertainty differs");
    }
    keys.add(row.source_key); coordinates.add(coordinate); counts[row.table]++;
  }
  if (counts.A !== 1040 || counts.B !== 780 || counts.C !== 103)
    throw new Error("1996 source inventory differs");
  return data;
}

export function pointFor1996(data, geography, group, citizen = false) {
  const nativeGeography = geography === "United States (including D.C.)" ? "TOTAL" : geography.toUpperCase();
  const definition = citizen ? group === "Total" ? ["C", "ALL", "18_plus"]
    : ["Male", "Female"].includes(group) ? ["C", group, "18_plus"] : null : definitions.get(group);
  const row = definition ? data.records.find(record => record.geography === nativeGeography
    && record.table === definition[0] && record.native_group === definition[1] && record.age === definition[2]) : null;
  const measure = row?.measures.voted;
  const rate = measure?.disposition === "selected_native_percentage" ? percent(measure.selected_percentage) : null;
  const unknown = citizen && row ? percent(row.measures.unknown_voting.selected_percentage) : null;
  return { sourceKey: row?.source_key || "", rate, votingNonresponse: unknown,
    decision: measure?.disposition || "not_supplied",
    text: rate === null ? measure?.disposition === "withheld_native_B"
      ? "Not published: source base too small (B)" : measure?.disposition === "withheld_rounded_zero_base"
        ? "Withheld: source population rounds to zero"
        : "Not supplied for this source population/group"
      : `${rate.toFixed(1)}%${unknown === null ? "" : ` · voting nonresponse ${unknown.toFixed(1)}%`} · uncertainty not supplied` };
}

export async function load1996Points() {
  const response = await fetch(pointSourceURL);
  if (!response.ok) throw new Error("1996 source unavailable");
  const body = await response.arrayBuffer();
  const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))]
    .map(value => value.toString(16).padStart(2, "0")).join("");
  if (hash !== pointSourceSHA256) throw new Error("1996 source checksum differs");
  return validate1996Points(JSON.parse(new TextDecoder().decode(body)));
}

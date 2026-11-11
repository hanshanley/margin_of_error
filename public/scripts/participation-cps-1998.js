export const pointSourceURL = "https://raw.githubusercontent.com/hanshanley/voter-participation/2b6cbcb3218b492e3391bb7d73b384cf28ff45be/data/participation-cps-1998-state-points/20261111-01/complete-result.json";
export const pointSourceSHA256 = "0b1e80744e3a24145aa2494c3581e602b458cb3330806d64f8757a32ab4c6a19";
export const pointOnly1998Groups = ["Non-Hispanic Asian and Pacific Islander (1998 native category)"];
const labels = new Map([
  ["Total", "Total"], ["Male", "Male"], ["Female", "Female"], ["Hispanic (any race)", "Hispanic"],
  ["White (1998/2002 native category)", "White"],
  ["Non-Hispanic White (1998/2002 native category)", "N-H White"],
  ["Black (1998/2002 native category)", "Black"],
  ["Non-Hispanic Black (1998/2002 native category)", "N-H Black"],
  [pointOnly1998Groups[0], "N-H API"],
]);
const percent = value => typeof value === "string" && /^\d+(?:\.\d*)?$/.test(value)
  && Number(value) >= 0 && Number(value) <= 100 ? Number(value) : null;

export function validate1998Points(data) {
  if (data?.contract !== "participation.cps_1998_native_state_points.v1"
      || data.records?.length !== 468 || data.summary?.native_metric_cells !== 4680
      || data.summary?.metric_decisions?.selected_reported_native_point !== 1060
      || data.policy?.population_frame !== "vap" || data.policy?.derived_intervals !== false
      || data.policy?.derived_citizen_turnout !== false || data.policy?.race_harmonization !== false)
    throw new Error("Unqualified 1998 point source");
  const keys = new Set();
  for (const row of data.records) {
    if (!row.source_key || keys.has(row.source_key) || row.year !== 1998
        || row.population_frame !== "vap" || row.sample_n !== null || row.citizen_turnout !== null
        || row.local_allocation !== false || row.race_categories_harmonized !== false)
      throw new Error("1998 point identity, population or missingness differs");
    for (const metric of ["citizen_adults", "registered", "voted"]) {
      const measure = row.measures?.[metric];
      if (!measure || measure.derived_interval !== null) throw new Error("1998 source precision differs");
      const rate = percent(measure.raw_percentage);
      const error = rate === null ? null : percent(measure.raw_standard_error);
      if ((rate === null ? measure.selected_percentage !== null
          : percent(measure.selected_percentage) !== rate)
          || (error === null ? measure.selected_source_standard_error_pp !== null
            : percent(measure.selected_source_standard_error_pp) !== error)
          || (measure.disposition === "selected_reported_native_point") !== (rate !== null))
        throw new Error("1998 native value, source hold or printed error differs");
    }
    keys.add(row.source_key);
  }
  return data;
}

export function pointFor1998(data, geography, group) {
  const nativeGeography = geography === "United States (including D.C.)" ? "UNITED STATES" : geography.toUpperCase();
  const label = labels.get(group);
  const row = label ? data.records.find(record =>
    record.geography === nativeGeography && record.native_group === label) : null;
  const measure = row?.measures.voted;
  const rate = measure?.disposition === "selected_reported_native_point" ? percent(measure.selected_percentage) : null;
  const standardError = rate === null ? null : percent(measure.selected_source_standard_error_pp);
  return { sourceKey: row?.source_key || "", rate, standardError,
    decision: measure?.disposition || "not_supplied",
    text: rate === null ? measure?.disposition === "withheld_native_small_base"
      ? "Not published: source base too small (B)" : "Not supplied for this source population/group"
      : `${rate.toFixed(1)}% · source SE ${measure.selected_source_standard_error_pp} pp (not a margin)` };
}

export async function load1998Points() {
  const response = await fetch(pointSourceURL);
  if (!response.ok) throw new Error("1998 source unavailable");
  const body = await response.arrayBuffer();
  const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))]
    .map(value => value.toString(16).padStart(2, "0")).join("");
  if (hash !== pointSourceSHA256) throw new Error("1998 source checksum differs");
  return validate1998Points(JSON.parse(new TextDecoder().decode(body)));
}

import { checkedDatasetFile, loadDataset } from "./participation-dataset.js";
import { rejectAutomaticRuntime, setAutomaticRuntimeStatus } from "./participation-automatic-runtime.js";

export const countStates = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(" ");
export const countModes = ["available", "official", "uf_vep", "uf_vap", "in_person_early", "mail_returned"];
const sha = /^[a-f0-9]{64}$/;
const levels = new Set(["state", "county", "county_equivalent", "municipality",
  "election_administration", "source_region", "precinct", "ward", "reporting_unit", "nongeographic"]);
const kinds = new Set(["ballots_cast", "voters_reported", "cards_cast", "returned",
  "early_activity", "source_activity", "participation_reported"]);
const integer = value => Number.isSafeInteger(value) && value >= 0;
const text = value => typeof value === "string" && value.length > 0;
const nullableText = value => value === null || text(value);

export function validateCountObservation(row, code) {
  const { election: e, geography: g, measure: m, count: c, denominator: d,
    source_clock: clock, reporting_status: reporting, source: s, quality: q, view } = row || {};
  if (row?.contract !== "participation.observation.v1" || !/^[a-f0-9]{32}$/.test(row.id)
      || !e || !text(e.id) || !Number.isSafeInteger(e.year) || !text(e.type)
      || !["native", "collector_context", "previously_reviewed"].includes(e.qualification)
      || !(e.date === null || /^\d{4}-\d\d-\d\d$/.test(e.date) && Number(e.date.slice(0, 4)) === e.year)
      || !g || g.state_code !== code || !countStates.includes(code) || !levels.has(g.level)
      || !text(g.id) || !text(g.name) || !nullableText(g.parent_id)
      || !["approved", "unreviewed", "unmatched", "nongeographic"].includes(g.join?.status)
      || !["reference_id", "feature_key", "evidence"].every(key => nullableText(g.join[key]))
      || g.join.status === "approved" && !["reference_id", "feature_key", "evidence"].every(key => text(g.join[key]))
      || !m || !["id", "literal", "unit"].every(key => text(m[key])) || !kinds.has(m.kind)
      || !["all_methods", "in_person_early", "mail_returned", "source_defined"].includes(m.mode)
      || !c || !["reported", "unknown", "withheld"].includes(c.status)
      || (c.status === "reported") !== (c.value !== null) || !(c.value === null || integer(c.value))
      || !clock || !nullableText(clock.literal) || !nullableText(clock.timezone)
      || clock.literal === null && clock.timezone !== null
      || !reporting || !nullableText(reporting.literal)
      || !["reported_units", "total_units"].every(key => reporting[key] === null || integer(reporting[key]))
      || !(reporting.complete === null || typeof reporting.complete === "boolean")
      || reporting.reported_units !== null && reporting.total_units !== null
        && (reporting.reported_units > reporting.total_units
          || reporting.complete === true && reporting.reported_units !== reporting.total_units)
      || !s || !text(s.id) || !/^https:\/\//.test(s.url) || !sha.test(s.input_sha256)
      || s.classification !== "public_aggregate" || !s.selector || !s.fields
      || !q || !Array.isArray(q.notes) || q.notes.some(note => typeof note !== "string")
      || !Array.isArray(q.conflicts) || q.conflicts.some(conflict => !text(conflict.code) || conflict.repaired === true)
      || !view || view.year !== e.year || view.state_code !== code || view.ballots !== c.value
      || (view.denominator ?? null) !== (d?.value ?? null)
      || (view.source_update_label || null) !== clock.literal)
    throw new Error("Unqualified canonical participation observation");
  if (d !== null && (!d || !(d.value === null || integer(d.value)) || !text(d.literal)
      || !text(d.basis) || typeof d.qualified !== "boolean"
      || d.qualified && (c.value === null || !integer(d.value) || d.value === 0
        || c.value > d.value || q.conflicts.length)))
    throw new Error("Unqualified canonical participation denominator");
  if (view.reported_pct !== null && view.reported_pct !== undefined
      && (!d?.qualified || !Number.isFinite(view.reported_pct)
        || view.reported_pct < 0 || view.reported_pct > 100))
    throw new Error("Unqualified canonical participation fraction");
  return row;
}

export function validateCountShard(data, code, declaration) {
  if (data?.contract !== "participation.count_snapshot.v1" || data.state_code !== code
      || data.year !== 2026 || !Array.isArray(data.records) || !data.views
      || data.records.length !== declaration.records)
    throw new Error("Canonical participation coverage differs");
  const records = new Map();
  for (const row of data.records) {
    validateCountObservation(row, code);
    if (records.has(row.id)) throw new Error("Duplicate canonical participation identity");
    records.set(row.id, row);
  }
  for (const mode of countModes) {
    const frame = data.views[mode];
    if (!frame || typeof frame.qualified !== "boolean" || !Array.isArray(frame.holds))
      throw new Error("Missing canonical participation mode disposition");
    for (const partition of ["counties", "precincts", "nongeographic"]) {
      const ids = frame[partition];
      if (!Array.isArray(ids) || new Set(ids).size !== ids.length
          || ids.some(id => !records.has(id))
          || !frame.qualified && ids.length
          || ["in_person_early", "mail_returned"].includes(mode)
            && ids.some(id => records.get(id).measure.mode !== mode))
        throw new Error("Unqualified canonical participation frame; no mode substitution");
    }
    if (declaration.views?.[mode] && ["counties", "precincts", "nongeographic", "holds"]
      .some(key => frame[key].length !== declaration.views[mode][key]))
      throw new Error("Canonical participation frame coverage differs");
    const contexts = frame.administrative_contexts ?? [];
    if (!Array.isArray(contexts) || new Set(contexts).size !== contexts.length
        || mode !== "available" && contexts.length
        || contexts.some(id => !records.has(id))
        || contexts.length !== (declaration.views?.[mode]?.administrative_contexts ?? contexts.length))
      throw new Error("Unqualified administrative context inventory");
    for (const id of contexts) {
      const row = records.get(id), view = row.view;
      if (row.measure.kind !== "source_activity" || row.measure.mode !== "source_defined"
          || row.measure.unit !== "current_registration_records"
          || row.election.type !== "date_coded_history_context"
          || row.election.qualification !== "collector_context"
          || row.denominator !== null || view.reported_pct !== null || view.maps_approved !== false
          || view.source_frame_kind !== "current_registry_date_token"
          || view.administrative_history_context_only !== true
          || row.source.fields.source_input_kind !== "person_record_file_retained_privately"
          || row.source.fields.derived_aggregate !== true)
        throw new Error("Unqualified current-registry context");
    }
  }
  const contextIds = new Set(data.views.available.administrative_contexts || []);
  for (const mode of countModes)
    if (["counties", "precincts", "nongeographic"].some(key =>
      data.views[mode][key].some(id => contextIds.has(id)
        || records.get(id).view.administrative_history_context_only === true)))
      throw new Error("Administrative context cannot substitute for participation counts");
  return data;
}

export function countFrame(data, mode) {
  if (!countModes.includes(mode)) throw new Error("Unknown participation mode");
  const records = new Map(data.records.map(row => [row.id, row.view]));
  const frame = data.views[mode];
  return {
    counties: frame.counties.map(id => records.get(id)),
    precincts: frame.precincts.map(id => records.get(id)),
    nongeographic: frame.nongeographic.map(id => records.get(id)),
    unmapped_source_regions: frame.holds,
    source_mode_unavailable: frame.unavailable_note || undefined,
    mode_review_complete_download: frame.mode_review_complete_download,
    administrative_contexts: (frame.administrative_contexts || []).map(id => records.get(id)),
  };
}

const states = new Map();
let dataset;
export function rejectCountRuntime(error) {
  rejectAutomaticRuntime("counts", error);
  states.clear();
  dataset = null;
}
export function clearCountState(code) {
  states.delete(code);
}
function validateCountIndex(value) {
  const { entry, index, automatic_runtime: runtime } = value;
  if (index.contract !== "participation.count_index.v1" || index.year !== 2026
      || Object.keys(index.states || {}).sort().join() !== [...countStates].sort().join())
    throw new Error("Canonical participation jurisdiction inventory differs");
  if (runtime) {
    const declarations = [index.current_snapshot, ...Object.values(index.states)];
    for (const declaration of declarations) {
      const expected = entry.files?.[declaration.file];
      if (!expected || expected.bytes !== declaration.bytes || expected.sha256 !== declaration.sha256)
        throw new Error("Automatic count index and committed file inventory differ");
    }
    if (runtime.election_date !== "2026-11-03"
        || Object.keys(index.states).length !== countStates.length)
      throw new Error("Automatic count election identity differs");
  }
  return value;
}
async function resolveCountIndex(automatic) {
  const value = await loadDataset("participation-counts-2026", { automatic });
  try {
    return validateCountIndex(value);
  } catch (error) {
    if (!value.automatic_runtime) throw error;
    rejectAutomaticRuntime("counts", error);
    return validateCountIndex(await loadDataset("participation-counts-2026", { automatic: false }));
  }
}
export async function loadCountIndex() {
  dataset ||= resolveCountIndex(true).catch(error => { dataset = null; throw error; });
  return dataset;
}

async function checkedCountState(code, source) {
  const declaration = source.index.states[code];
  const data=validateCountShard(
    await checkedDatasetFile(source.entry.base_url,declaration),code,declaration);
  if (source.automatic_runtime) for (const row of data.records)
    if (row.view.automatic_source_refresh===true) {
      if (row.view.complete_download_url
          && row.view.complete_download_url!==source.automatic_runtime.complete_download.url)
        row.view.accepted_complete_download_url=row.view.complete_download_url;
      row.view.complete_download_url=source.automatic_runtime.complete_download.url;
    }
  return data;
}
export async function loadCountState(code) {
  if (!countStates.includes(code)) throw new Error("Unknown participation jurisdiction");
  if (!states.has(code)) states.set(code, loadCountIndex().then(async source => {
    try {
      const result = await checkedCountState(code, source);
      if (source.automatic_runtime)
        setAutomaticRuntimeStatus("counts", "active", "county/precinct counts", source.automatic_runtime);
      return result;
    } catch (error) {
      if (!source.automatic_runtime) throw error;
      rejectCountRuntime(error);
      return loadAcceptedCountState(code);
    }
  }).catch(error => { states.delete(code); throw error; }));
  return states.get(code);
}

export async function loadAcceptedCountState(code) {
  if (!countStates.includes(code)) throw new Error("Unknown participation jurisdiction");
  const source = validateCountIndex(
    await loadDataset("participation-counts-2026", { automatic: false }));
  return checkedCountState(code, source);
}

export function validateCurrentCountSnapshot(data) {
  if (data?.contract !== "participation.current_snapshot.v1" || !data.snapshot
      || !Array.isArray(data.reviewed_states)
      || !Array.isArray(data.snapshot.reporting) || !Array.isArray(data.snapshot.early_voting)
      || !Array.isArray(data.snapshot.coverage)
      || data.snapshot.coverage.map(row => row.state_code).sort().join() !== [...countStates].sort().join()
      || [...data.snapshot.reporting, ...data.snapshot.early_voting].some(row =>
        !countStates.includes(row.state_code) || !(row.ballots === null || integer(row.ballots))))
    throw new Error("Unqualified current participation snapshot");
  return data;
}

export async function loadCurrentCountSnapshot() {
  const source = await loadCountIndex();
  try {
    const data = validateCurrentCountSnapshot(
      await checkedDatasetFile(source.entry.base_url, source.index.current_snapshot));
    if (source.automatic_runtime) for (const rows of [
      data.snapshot.reporting,data.snapshot.early_voting])
      for (const row of rows) if (row.automatic_source_refresh===true) {
        if (row.complete_download_url
            && row.complete_download_url!==source.automatic_runtime.complete_download.url)
          row.accepted_complete_download_url=row.complete_download_url;
        row.complete_download_url=source.automatic_runtime.complete_download.url;
      }
    if (source.automatic_runtime)
      setAutomaticRuntimeStatus("counts", "active", "county/precinct counts", source.automatic_runtime);
    return { ...data, original_base: source.index.original_current_base };
  } catch (error) {
    if (!source.automatic_runtime) throw error;
    rejectCountRuntime(error);
    const fallback = validateCountIndex(
      await loadDataset("participation-counts-2026", { automatic: false }));
    const data = validateCurrentCountSnapshot(
      await checkedDatasetFile(fallback.entry.base_url, fallback.index.current_snapshot));
    return { ...data, original_base: fallback.index.original_current_base };
  }
}

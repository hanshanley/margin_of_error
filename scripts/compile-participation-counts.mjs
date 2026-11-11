import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { pathToFileURL } from "node:url";
import { gzipSync, gunzipSync } from "node:zlib";
import { countStates, countModes, validateCountShard } from "../public/scripts/participation-counts.js";
import { hasCountySourceMode, selectCountySourceFrame } from "../public/scripts/participation-geography.js";

export function encoded(value) {
  const sorted = item => Array.isArray(item) ? item.map(sorted) : item && typeof item === "object"
    ? Object.fromEntries(Object.keys(item).sort().map(key => [key, sorted(item[key])])) : item;
  return Buffer.from((JSON.stringify(sorted(value)).replace(/[\u007f-\uffff]/g,
    char => "\\u" + char.charCodeAt(0).toString(16).padStart(4, "0"))) + "\n");
}
export const digest = body => createHash("sha256").update(body).digest("hex");
export const pin = body => ({ bytes: body.length, sha256: digest(body) });
const nameKey = value => value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
  .toUpperCase().replace(/\s*\(VOTE CENTER\)/g, "").replace(/\b(COUNTY|PARISH)\b/g, "").replace(/[^A-Z0-9]/g, "");
const empty = () => ({ counties: [], precincts: [], nongeographic: [] });
const modeRelease = "https://github.com/hanshanley/margin_of_error/releases/download/voter-native-mode-frames-20261110-01/complete-analysis.zip";

export function selectedFrame(base, additional, code, mode) {
  if (["in_person_early", "mail_returned"].includes(mode) && !hasCountySourceMode(code, mode))
    return { ...empty(), qualified: false, holds: [], mode_review_complete_download: modeRelease,
      unavailable_note: `No qualified ${mode === "in_person_early" ? "in-person early" : "mail-returned"} local frame for ${code}. `
        + "Other source counts are retained under Available / official source, not reused for this mode. Missing mode counts are unknown, not zero." };
  if (!additional) return { ...base, qualified: true, holds: [] };
  const combined = [...base.counties, ...additional.counties.filter(row =>
    !base.counties.some(other => other.state_code === row.state_code && nameKey(other.county) === nameKey(row.county)))];
  const selected = selectCountySourceFrame({ ...additional, counties: combined }, code, mode);
  const scoped = hasCountySourceMode(code, mode) || selected !== combined;
  const snapshot = code === "MN" && ["available", "official"].includes(mode)
    ? selected.find(row => ["20261110-minnesota-followup-02", "20261110-minnesota-complete-native-03"]
      .includes(row.source_snapshot))?.source_snapshot : null;
  return {
    counties: scoped ? selected.filter(row => row.state_code === code) : combined,
    precincts: snapshot ? additional.precincts.filter(row => row.source_snapshot === snapshot)
      : scoped ? [] : [...base.precincts, ...additional.precincts],
    nongeographic: scoped ? [] : additional.nongeographic || [],
    qualified: true,
    holds: scoped ? additional.county_frame_holds?.[selected[0]?.source_mode] || [] : [],
  };
}

export function canonicalObservation(view, input, partition, ordinal) {
  const mode = ["in_person_early", "mail_returned"].includes(view.source_mode) ? view.source_mode
    : view.source_mode?.startsWith("all_method") ? "all_methods" : "source_defined";
  const sourceId = `accepted-export:${input.sha256}:${partition}`;
  const election = { id: "us-2026-general-previously-reviewed", year: 2026,
    date: view.source_election_date || null, type: "general",
    qualification: view.native_election_id_qualified === false ? "collector_context" : "previously_reviewed" };
  const level = view.unit_key ? "reporting_unit" : ({
    statewide: "state", independent_city: "county_equivalent", source_locality_activity: "source_region",
    provider_county_named_region_context: "source_region", source_reporting_unit: "reporting_unit",
    nongeographic_reporting_unit: "nongeographic",
  })[view.geography_level] || view.geography_level || "county";
  const identity = `${view.state_code}|${view.county_id ?? "state"}|${view.unit_key ?? ""}`;
  const measure = { id: "previously-reviewed-participation-count",
    literal: view.participation_measure_literal || view.participation_measure_label
      || "Reported ballots (previously reviewed export label, not a new native qualification)",
    kind: mode === "mail_returned" ? "returned" : mode === "in_person_early" ? "early_activity" : "participation_reported",
    mode, unit: "source_reported_count" };
  const count = view.ballots;
  if (count === undefined) throw new Error("Missing explicit count in accepted export");
  const denominator = view.denominator === null || view.denominator === undefined ? null : {
    value: view.denominator, literal: view.denominator_basis,
    basis: view.denominator_basis, qualified: view.reported_pct !== null && view.reported_pct !== undefined,
  };
  const row = {
    contract: "participation.observation.v1",
    id: digest(encoded([sourceId, election.id, identity, measure.id, mode])).slice(0, 32),
    election,
    geography: { id: identity, name: view.unit || view.county || view.state, state_code: view.state_code, level,
      parent_id: view.unit_key ? `${view.state_code}|${view.county_id}` : null,
      join: { status: level === "nongeographic" ? "nongeographic" : "unreviewed",
        reference_id: null, feature_key: null,
        evidence: "Existing export map qualifications and reference bindings remain literal in source.fields and view; this migration approves no new join." } },
    measure,
    count: { value: count, status: count !== null ? "reported"
      : view.native_record?.source_scope_review?.startsWith("withheld_") ? "withheld" : "unknown", literal: count },
    denominator,
    source_clock: { literal: view.source_update_label || null, timezone: view.source_update_timezone || null,
      qualification: "previously_reviewed_export_label_not_new_native_clock" },
    reporting_status: { literal: view.source_status_literal || null,
      reported_units: view.reported_units ?? null, total_units: view.total_units ?? null, complete: null },
    source: { id: sourceId, url: input.url, input_sha256: input.sha256,
      selector: { input: input.file, partition, ordinal }, classification: "public_aggregate",
      fields: view },
    quality: { conflicts: [], native_conflict_status: "retained_in_source_fields_not_newly_classified",
      notes: [...(view.quality || []),
      "One-time migration of accepted public aggregate export; not a new source parse, conflict adjudication, election/boundary certification or independent validation.",
      "All native fields, conflicts, holds and existing rate decisions remain unchanged in source.fields and view. Export partitions are separate appearances, never additive populations."] },
    view,
  };
  return row;
}

export function compileCounts(inputs, metadata) {
  const originals = new Map();
  const reviewed = JSON.parse(inputs["reviewed.json"]);
  const base = JSON.parse(inputs["local.json"]);
  const current = inputs["current.json"] ? JSON.parse(inputs["current.json"]) : null;
  const supplemental = Object.fromEntries(metadata.additional_states.map(code =>
    [code, JSON.parse(gunzipSync(inputs[`additional/${code}.json.gz`]))]));
  const recordsByState = Object.fromEntries(countStates.map(code => [code, []]));
  const register = (rows, file, partition) => rows.forEach((view, ordinal) => {
    if (!countStates.includes(view.state_code)) throw new Error("Foreign jurisdiction in held export");
    const input = { file, ...metadata.inputs[file] };
    const record = canonicalObservation(view, input, partition, ordinal);
    recordsByState[view.state_code].push(record);
    originals.set(view, record.id);
  });
  register(base.counties, "local.json", "counties");
  register(base.precincts, "local.json", "precincts");
  register(reviewed.counties, "reviewed.json", "counties");
  register(reviewed.states, "reviewed.json", "states");
  if (current) for (const partition of ["reporting", "early_voting"]) {
    const views = current[partition].map(native => ({
      ...native, year: 2026,
      county: native.geography || native.state,
      county_id: `current:${native.geography_level || "state"}:${native.geography || native.state}:${native.source_url}`,
      geography_level: native.geography_level || "state",
      denominator: native.denominator ?? null, reported_pct: native.validated_pct ?? null,
      source_mode: native.mode, native_record: native,
      native_election_id_qualified: false,
    }));
    register(views, "current.json", partition);
  }
  for (const [code, data] of Object.entries(supplemental)) {
    for (const partition of ["counties", "precincts", "nongeographic"])
      register(data[partition], `additional/${code}.json.gz`, partition);
    for (const [mode, rows] of Object.entries(data.county_frames || {}))
      register(rows, `additional/${code}.json.gz`, "county_frames/" + mode);
  }
  const merged = [...base.counties, ...reviewed.counties.filter(row =>
    !base.counties.some(other => other.state_code === row.state_code
      && (other.county_id === row.county_id || nameKey(other.county) === nameKey(row.county))))];
  const files = {}, declarations = {}, sourceTotals = {};
  for (const code of countStates) {
    const local = { counties: merged.filter(row => row.state_code === code),
      precincts: base.precincts.filter(row => row.state_code === code), nongeographic: [] };
    const views = Object.fromEntries(countModes.map(mode => {
      const frame = selectedFrame(local, supplemental[code], code, mode);
      return [mode, { ...frame, ...Object.fromEntries(["counties", "precincts", "nongeographic"]
        .map(key => [key, frame[key].map(row => {
          const id = originals.get(row);
          if (!id) throw new Error("Selected observation not retained in full query");
          return id;
        })])) }];
    }));
    const records = recordsByState[code];
    const byId = new Map(records.map(row => [row.id, row]));
    const file = `states/${code}.json.gz`;
    const declaration = { file, records: records.length,
      views: Object.fromEntries(Object.entries(views).map(([mode, frame]) =>
        [mode, {
          ...Object.fromEntries(["counties", "precincts", "nongeographic", "holds"].map(key => [key, frame[key].length])),
          qualified: frame.qualified,
          dispositions: Object.fromEntries(["counties", "precincts", "nongeographic"].map(key => [key, {
            reported: frame[key].filter(id => byId.get(id).count.status === "reported").length,
            unknown: frame[key].filter(id => byId.get(id).count.status === "unknown").length,
            withheld: frame[key].filter(id => byId.get(id).count.status === "withheld").length,
            qualified_fractions: frame[key].filter(id => byId.get(id).denominator?.qualified).length,
            geography_levels: [...new Set(frame[key].map(id => byId.get(id).geography.level))].sort(),
          }])),
        }])) };
    const shard = validateCountShard({ contract: "participation.count_snapshot.v1", year: 2026,
      state_code: code, records, views }, code, declaration);
    const body = gzipSync(encoded(shard), { level: 9 });
    files[file] = body;
    declarations[code] = { ...declaration, ...pin(body) };
    sourceTotals[code] = { records: records.length, reported: records.filter(row => row.count.status === "reported").length,
      zeros: records.filter(row => row.count.value === 0).length,
      unknown: records.filter(row => row.count.status === "unknown").length,
      withheld: records.filter(row => row.count.status === "withheld").length,
      qualified_fractions: records.filter(row => row.denominator?.qualified).length };
  }
  const index = { contract: "participation.count_index.v1", year: 2026, states: declarations,
    source_export_revision: metadata.source_export_revision,
    coverage: sourceTotals, additional_states: metadata.additional_states,
    migration_qualifies_no_new_science_or_geography: true };
  if (current) {
    const file = "current.json.gz";
    files[file] = gzipSync(encoded({ contract: "participation.current_snapshot.v1",
      snapshot: current, reviewed_states: reviewed.states }), { level: 9 });
    index.current_snapshot = { file, ...pin(files[file]) };
    index.original_current_base = metadata.inputs["local.json"].url.replace(/local\.json$/, "");
  }
  files["index.json"] = encoded(index);
  const declarationsAll = Object.fromEntries(Object.entries(files).sort().map(([file, body]) => [file, pin(body)]));
  const record_contract = "participation.count_snapshot.v1";
  const version = digest(encoded({ files: declarationsAll, contract: record_contract }));
  return { files, index, descriptor: { contract: "participation.dataset.v1", id: "participation-counts-2026",
    version, record_contract, files: declarationsAll, index: { file: "index.json", ...declarationsAll["index.json"] },
    complete_download: null } };
}

export function readCountInputs(root) {
  const metadata = JSON.parse(readFileSync(resolve(root, "inputs.json")));
  const inputs = {};
  for (const [file, expected] of Object.entries(metadata.inputs)) {
    const body = readFileSync(resolve(root, "inputs", file));
    if (body.length !== expected.bytes || digest(body) !== expected.sha256)
      throw new Error("Accepted count input changed: " + file);
    inputs[file] = body;
  }
  return { inputs, metadata };
}

export function writeCounts(root, output) {
  if (existsSync(output)) throw new Error("Refuse to replace an immutable compiled count dataset");
  const { inputs, metadata } = readCountInputs(root);
  const compiled = compileCounts(inputs, metadata);
  for (const [file, body] of Object.entries(compiled.files)) {
    mkdirSync(dirname(resolve(output, file)), { recursive: true });
    writeFileSync(resolve(output, file), body);
  }
  writeFileSync(resolve(output, "dataset.json"), encoded(compiled.descriptor));
  return compiled;
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const result = writeCounts(resolve(process.argv[2]), resolve(process.argv[3]));
  console.log(JSON.stringify({ version: result.descriptor.version, states: countStates.length,
    records: Object.values(result.index.coverage).reduce((sum, row) => sum + row.records, 0) }));
}

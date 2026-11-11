import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { pathToFileURL } from "node:url";
import { gzipSync, gunzipSync } from "node:zlib";
import { encoded, digest, pin } from "./compile-participation-counts.mjs";
import { countModes, validateCountObservation, validateCountShard } from "../public/scripts/participation-counts.js";

const partitions = ["counties", "precincts", "nongeographic"];
const integer = literal => {
  if (literal === "") return null;
  if (typeof literal !== "string" || !/^(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)$/.test(literal))
    throw new Error("Unqualified native count literal");
  const result = Number(literal.replaceAll(",", ""));
  if (!Number.isSafeInteger(result)) throw new Error("Native count is not a safe integer");
  return result;
};

export function registeredTableCounts(facts, recipe, input) {
  if (facts.contract !== "participation.native_table_counts.v1"
      || recipe.contract !== "participation.count_extension.v1"
      || digest(input.body) !== recipe.input_sha256 || input.sha256 !== recipe.input_sha256
      || new Set(facts.reports.map(report => report.key)).size !== facts.reports.length)
    throw new Error("Unqualified registered sufficient input");
  return recipe.sources.map(source => {
    const report = facts.reports.find(row => row.key === source.report_key);
    if (!report || report.source.status !== 200 || report.election.id !== source.election.id
        || source.selected_labels.length < 2
        || new Set(source.selected_labels).size !== source.selected_labels.length
        || !source.count_columns.length || new Set(source.count_columns).size !== source.count_columns.length)
      throw new Error("Registered source identity differs");
    const indices = source.count_columns.map(name => report.columns.indexOf(name));
    if (indices.some(index => index < 0)) throw new Error("Unknown registered count column");
    const rows = source.selected_labels.map(label => {
      const selected = report.rows.filter(row => row.label === label);
      if (selected.length !== 1) throw new Error("Ambiguous native aggregate selector");
      if (selected[0].count_literals.length !== report.columns.length)
        throw new Error("Incomplete native aggregate vector");
      return selected[0].count_literals.map(integer);
    });
    const components = rows.map(row => indices.map(index => row[index]));
    if (components.some(row => row.some(value => value === null))
        || components.some(row => row.some((value, i) => value !== components[0][i])))
      throw new Error("Selected participation aggregates disagree or are missing");
    const conflicts = report.columns.flatMap((field, i) => {
      const values = rows.map(row => row[i]);
      return values.every(value => value === values[0]) ? [] : [{
        code: "native_aggregate_alternative_disagreement", field, values,
        repaired: false, affects_selected_count: indices.includes(i),
      }];
    });
    const value = components[0].reduce((a, b) => a + b, 0);
    const identity = `${source.geography.state_code}|${source.geography.view_id}|`;
    const record = {
      contract: "participation.observation.v1",
      id: digest(encoded([source.id, source.election.id, identity, source.measure.id, source.measure.mode])).slice(0, 32),
      election: source.election,
      geography: { id: identity, name: source.geography.name,
        state_code: source.geography.state_code, level: source.geography.level, parent_id: null,
        join: { status: "unreviewed", reference_id: null, feature_key: null,
          evidence: "Existing county contextual identity only; no new boundary or map approval." } },
      measure: source.measure, count: { value, status: "reported", literal: value }, denominator: null,
      source_clock: { ...report.source_clock, qualification: "native_report_table_literal_timezone_undeclared" },
      reporting_status: { literal: report.native_status_literal, reported_units: null, total_units: null, complete: null },
      source: { id: source.id, url: recipe.facts_url, input_sha256: input.sha256,
        selector: { input: input.file, report: source.report_key,
          labels: source.selected_labels, count_columns: source.count_columns },
        classification: "public_aggregate", fields: report },
      quality: { conflicts, notes: source.notes },
    };
    const native = {
      source_url: report.source.url, native_original_sha256: report.source.sha256,
      selected_native_aggregate_literal: source.selected_labels.join(" and "),
      reported_participation_subtotal: String(value),
      source_counting_complete: null,
    };
    for (const [field, column] of Object.entries(source.native_view_fields || {})) {
      const index = report.columns.indexOf(column);
      if (index < 0) throw new Error("Unregistered native provenance column");
      native[field] = String(rows[0][index] ?? "");
    }
    record.view = {
      year: source.election.year, state_code: source.geography.state_code,
      county: source.geography.name, county_id: source.geography.view_id,
      geography_level: source.geography.level, maps_approved: false, ballots: value,
      denominator: null, denominator_basis: "native_registered_voters",
      reported_pct: null, native_printed_pct: null, native_record: native,
      source_url: recipe.facts_url, complete_download_url: recipe.complete_download_url,
      review_id: recipe.id, reported_units: null, total_units: null, source_rows: report.rows.length,
      participation_measure_kind: "derived_reported_mode_subtotal",
      participation_measure_label: source.measure.literal,
      source_status_literal: report.native_status_literal,
      source_update_label: report.source_clock.literal, source_update_timezone: null,
      source_reporting_label: source.notes.join(" "),
      native_source_updates: [{ native_update_literal: report.source_clock.literal, declared_timezone: "" }],
      quality: source.notes,
    };
    validateCountObservation(record, source.geography.state_code);
    return { record, modes: source.bindings, partition: "counties" };
  });
}

export function declarationFor(shard, previous, body) {
  const records = new Map(shard.records.map(row => [row.id, row]));
  return { ...previous, ...pin(body), records: shard.records.length,
    views: Object.fromEntries(Object.entries(shard.views).map(([mode, frame]) => [mode, {
      ...Object.fromEntries([...partitions, "holds"].map(key => [key, frame[key].length])),
      qualified: frame.qualified,
      dispositions: Object.fromEntries(partitions.map(key => [key, {
        reported: frame[key].filter(id => records.get(id).count.status === "reported").length,
        unknown: frame[key].filter(id => records.get(id).count.status === "unknown").length,
        withheld: frame[key].filter(id => records.get(id).count.status === "withheld").length,
        qualified_fractions: frame[key].filter(id => records.get(id).denominator?.qualified).length,
        geography_levels: [...new Set(frame[key].map(id => records.get(id).geography.level))].sort(),
      }])),
    }])) };
}

export function extendCountDataset(baseFiles, additions, extension) {
  const files = { ...baseFiles }, index = JSON.parse(files["index.json"]);
  const changed = new Map();
  for (const { record, modes, partition } of additions) {
    const code = record.geography.state_code, declaration = index.states[code];
    if (!declaration || !partitions.includes(partition) || !modes.length
        || new Set(modes).size !== modes.length || modes.some(mode => !countModes.includes(mode)))
      throw new Error("Unknown source/view binding");
    validateCountObservation(record, code);
    if (!changed.has(code)) changed.set(code, JSON.parse(gunzipSync(files[declaration.file])));
    const shard = changed.get(code);
    if (shard.records.some(row => row.id === record.id
        || row.geography.id === record.geography.id && row.measure.id === record.measure.id))
      throw new Error("An extension cannot overwrite an accepted observation");
    for (const mode of modes) {
      const frame = shard.views[mode];
      if (!frame.qualified || ["in_person_early", "mail_returned"].includes(mode) && record.measure.mode !== mode)
        throw new Error("An extension cannot approve or substitute a source mode");
      if (frame[partition].some(id => shard.records.find(row => row.id === id).geography.id === record.geography.id))
        throw new Error("Ambiguous simultaneous source selection");
      frame[partition].push(record.id);
    }
    shard.records.push(record);
  }
  for (const [code, shard] of changed) {
    const body = gzipSync(encoded(shard), { level: 9 }), previous = index.states[code];
    files[previous.file] = body;
    index.states[code] = declarationFor(shard, previous, body);
    index.coverage[code] = { records: shard.records.length,
      reported: shard.records.filter(row => row.count.status === "reported").length,
      unknown: shard.records.filter(row => row.count.status === "unknown").length,
      withheld: shard.records.filter(row => row.count.status === "withheld").length,
      zeros: shard.records.filter(row => row.count.value === 0).length,
      qualified_fractions: shard.records.filter(row => row.denominator?.qualified).length };
    validateCountShard(shard, code, index.states[code]);
  }
  index.extensions = [...(index.extensions || []), extension];
  index.migration_qualifies_no_new_science_or_geography = false;
  index.extensions_approve_no_new_geometry = true;
  files["index.json"] = encoded(index);
  const pins = Object.fromEntries(Object.entries(files).sort().map(([name, body]) => [name, pin(body)]));
  const record_contract = "participation.count_snapshot.v1";
  const descriptor = { contract: "participation.dataset.v1", id: "participation-counts-2026",
    version: digest(encoded({ files: pins, contract: record_contract })), record_contract,
    index: { file: "index.json", ...pins["index.json"] }, files: pins, complete_download: null };
  return { files, descriptor, changed_states: [...changed.keys()] };
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const args = Object.fromEntries(process.argv.slice(2).reduce((rows, value, i, all) =>
    i % 2 ? rows : [...rows, [value.replace(/^--/, ""), all[i + 1]]], []));
  if (!args.base || !args.facts || !args.recipe || !args.output || existsSync(args.output))
    throw new Error("Supply a complete baseline, frozen input, registered recipe and fresh output");
  const base = JSON.parse(readFileSync(resolve(args.base, "dataset.json")));
  const files = Object.fromEntries(Object.entries(base.files).map(([name, expected]) => {
    const body = readFileSync(resolve(args.base, name));
    if (JSON.stringify(pin(body)) !== JSON.stringify(expected)) throw new Error("Changed baseline file");
    return [name, body];
  }));
  const body = readFileSync(args.facts), recipe = JSON.parse(readFileSync(args.recipe));
  const additions = registeredTableCounts(JSON.parse(body), recipe, {
    body, file: "native-facts.json", sha256: digest(body) });
  const result = extendCountDataset(files, additions, {
    id: recipe.id, source_input_sha256: digest(body), source_url: recipe.facts_url,
    new_observations: additions.length, qualified_new_geometry: false });
  for (const [name, bytes] of Object.entries(result.files)) {
    const path = resolve(args.output, name); mkdirSync(dirname(path), { recursive: true }); writeFileSync(path, bytes);
  }
  writeFileSync(resolve(args.output, "dataset.json"), encoded(result.descriptor));
  console.log(JSON.stringify({ version: result.descriptor.version, changed_states: result.changed_states,
    observations_added: additions.length, old_observations_preserved: true,
    unchanged_runtime_files: Object.keys(files).length - result.changed_states.length - 1 }));
}

import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import { join } from "node:path";
import { norcRecordedComparison, validateNorcHouse } from "../public/scripts/participation-norc-house.js";

const { values } = parseArgs({ options: {
  source: { type: "string" }, output: { type: "string" }, "source-sha256": { type: "string" },
} });
if (!values.source || !values.output || !/^[a-f0-9]{64}$/.test(values["source-sha256"] || ""))
  throw new Error("Provide --source, --source-sha256 and a fresh --output directory");
const body = await readFile(values.source);
if (createHash("sha256").update(body).digest("hex") !== values["source-sha256"])
  throw new Error("Pinned source bytes changed");
const source = JSON.parse(body);
const model = validateNorcHouse(source.families?.accepted_ridge_multinomial || source);
const records = model.rows.map(row => {
  const recorded = norcRecordedComparison(row);
  return { state_code: row.state_code, recorded_counts_available: Boolean(recorded),
    previous: recorded?.previous ?? null, current: recorded?.current ?? null,
    previous_D_two_party_share: recorded?.previous_share ?? null,
    current_D_two_party_share: recorded?.current_share ?? null,
    D_two_party_share_change_pp: recorded?.share_change_pp ?? null,
    D_minus_R_margin_change_pp: recorded ? recorded.share_change_pp * 2 : null,
    model_eligible: row.source_comparison_available,
    model_hold_reason: row.source_comparison_available ? null : row.reported_comparison.reason,
    unadjusted_party_totals_not_voter_preference_swing: true,
    snapshot: recorded?.snapshot ?? null };
}).sort((a, b) => a.state_code.localeCompare(b.state_code));
const flattened = records.map(row => ({
  state_code: row.state_code, recorded_counts_available: row.recorded_counts_available,
  ...Object.fromEntries(["previous", "current"].flatMap(phase =>
    ["D", "R", "O"].map(party => [phase + "_" + party, row[phase]?.[party] ?? null]))),
  ...Object.fromEntries(Object.entries(row).filter(([key]) =>
    !["state_code", "recorded_counts_available", "previous", "current"].includes(key))),
}));
const fields = Object.keys(flattened[0]);
const csv = value => value == null ? "" : `"${String(value).replaceAll('"', '""')}"`;
const dataset = { contract: "participation.house_recorded_counts.v1",
  source_sha256: values["source-sha256"], jurisdictions: records.length,
  source_counts_changed: false, new_model_fits: 0,
  ...(model.comparison_policy?.input_source_counts_revised_from_previous_release
    ? { input_source_counts_revised_from_previous_release: true, source_count_repairs: 0,
      official_source_revisions: model.endpoint_update.official_source_revisions } : {}),
  records };
await mkdir(values.output);
await writeFile(join(values.output, "complete-recorded-counts.json"), JSON.stringify(dataset) + "\n");
await writeFile(join(values.output, "complete-recorded-counts.csv"),
  fields.join(",") + "\n" + flattened.map(row => fields.map(key => csv(row[key])).join(",")).join("\n") + "\n");
console.log(JSON.stringify({ records: records.length, output: values.output,
  raw_changes_are_not_preference_swings: true, model_eligibility_unchanged: true }));

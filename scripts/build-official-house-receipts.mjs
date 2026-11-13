import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { norcFamilies, norcGroups, norcMapValue, norcViews,
  validateNorcAssociation, validateNorcFamilies } from "../public/scripts/participation-norc-house.js";

const { values } = parseArgs({ options: {
  models: { type: "string" }, previous: { type: "string" }, science: { type: "string" },
  output: { type: "string" }, "source-commit": { type: "string" }, "release-tag": { type: "string" },
} });
if (!values.models || !values.previous || !values.science || !values.output
    || !/^[a-f0-9]{40}$/.test(values["source-commit"] || "")
    || !/^participation-house-official-refresh-20261113-\d{2}$/.test(values["release-tag"] || "")
    || existsSync(values.output))
  throw new Error("Provide verified model/science paths, exact source commit/release tag and a fresh output");
const pin = body => ({ bytes: body.length, sha256: createHash("sha256").update(body).digest("hex") });
const read = path => JSON.parse(readFileSync(path));
const download = `https://github.com/hanshanley/margin_of_error/releases/download/${values["release-tag"]}/complete-analysis.zip`;
const datasets = {}, receipts = {};
for (const profile of ["original", "attenuated", "full"]) {
  const body = readFileSync(join(values.models, `viewer-${profile}.json`));
  datasets[profile] = profile === "original" ? validateNorcFamilies(JSON.parse(body))
    : validateNorcAssociation(JSON.parse(body), datasets.original);
  const policy = datasets[profile].comparison_policy;
  if (policy.input_source_counts_revised_from_previous_release !== true
      || policy.native_source_counts_changed !== false
      || [...policy.changed_state_scenarios_recomputed].sort().join(",") !== "HI,WY")
    throw new Error("An unreviewed source revision cannot become a current receipt");
  receipts[profile] = { ...pin(body), source_commit: values["source-commit"],
    url: `https://raw.githubusercontent.com/hanshanley/voter-participation/${values["source-commit"]}/data/house-official-source-update/20261113-01/viewer-${profile}.json`,
    complete_download_url: download, contest_comparability_required: true,
    official_source_revision_required: true };
}
const original = datasets.original;
const models = Object.values(datasets).flatMap(data => Object.values(data.families));
const groups = new Set(["", ...models.flatMap(model => norcGroups(model).map(group => group.value))]);
const shared = {};
for (const group of groups) {
  let maximum = 0;
  for (const model of models) for (const row of model.rows) for (const [view] of norcViews) {
    if (view === "retaining") continue;
    const value = norcMapValue(row, view, group, "margin");
    if (value !== null) maximum = Math.max(maximum, Math.abs(value));
  }
  shared[group] = maximum;
}
const association = { ...read(join(values.previous, "copula-receipt.json")),
  profiles: { attenuated: receipts.attenuated, full: receipts.full },
  comparison_policy: original.comparison_policy, shared_max_abs_margin: shared,
  complete_science: pin(readFileSync(values.science)), complete_science_url: download,
  state_margin_MAE_pp: Object.fromEntries(Object.entries(datasets)
    .map(([profile, data]) => [profile, data.summary.margin_MAE_pp])) };
const baseline = original.families[norcFamilies[0][0]];
const points = { preconditioning_margin_MAE_pp: baseline.preconditioning_margin_MAE_pp,
  summary: baseline.summary, validation: baseline.validation,
  rows: baseline.rows.map(row => Object.fromEntries([
    "state_code", "source_comparison_available", "reported_comparison", "contest_comparability", "point",
  ].map(key => [key, row[key]]))) };
const familySummary = Object.fromEntries([
  "comparison_policy", "family_labels", "source_validation", "summary",
].map(key => [key, original[key]]));
mkdirSync(values.output, { recursive: true });
for (const [name, data] of Object.entries({
  "norc-receipt.json": receipts.original, "copula-receipt.json": association,
  "norc-point-summary.json": points, "family-summary.json": familySummary,
})) writeFileSync(join(values.output, name), JSON.stringify(data) + "\n");
console.log(JSON.stringify({ status: "all_nine_actual_models_and_current_receipts_validated",
  states: baseline.rows.length, qualified: baseline.summary.return_anchored,
  profiles: Object.keys(datasets), groups: groups.size, science: association.complete_science }));

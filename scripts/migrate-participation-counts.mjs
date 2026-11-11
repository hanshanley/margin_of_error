import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { load } from "cheerio";
import { encoded, pin, writeCounts } from "./compile-participation-counts.mjs";

export function migrateCounts(source, output, acceptance) {
  if (existsSync(output)) throw new Error("Refuse to replace an existing count migration");
  if (acceptance.status !== "PASS_actual_one_map_and_live_resident_dataset_update_without_site_build"
      || acceptance.code_publication.commit !== "21d3d60333606adb6b11b3dac89d6976087ad439")
    throw new Error("Migration requires the actual accepted source export");
  const $ = load(readFileSync(resolve(source, "dist/voter-participation/index.html"), "utf8"));
  const attribute = name => JSON.parse($(`[${name}]`).attr(name));
  const additional = attribute("data-additional-participation");
  const reviewed = { counties: attribute("data-reviewed-county-participation"),
    states: attribute("data-reviewed-state-participation"),
    county_context: attribute("data-county-context-review") };
  const publication = "https://www.themarginoferror.com/";
  const current = "public/participation-current/20261104T220424Z/";
  const snapshot = JSON.parse(readFileSync(resolve(source, current, "snapshot.json")));
  const factualSnapshot = { ...snapshot, sources: snapshot.sources.map(receipt =>
    Object.fromEntries(Object.entries(receipt).filter(([key]) => !["etag", "last_modified", "http_status"].includes(key)))) };
  const bodies = {
    "local.json": { body: readFileSync(resolve(source, current, snapshot.local_file)),
      url: "https://raw.githubusercontent.com/hanshanley/margin_of_error/dc81c095cec959910c6dfb82da8c9184d7a993f9/"
        + current + snapshot.local_file },
    "reviewed.json": { body: encoded(reviewed), url: publication + "voter-participation/",
      extraction: "Complete accepted public aggregate data attributes; compiled HTML/scripts are excluded." },
    "current.json": { body: encoded(factualSnapshot),
      url: "https://raw.githubusercontent.com/hanshanley/margin_of_error/dc81c095cec959910c6dfb82da8c9184d7a993f9/"
        + current + "snapshot.json",
      extraction: "All accepted aggregate data and source facts; acquisition etag/last_modified/http_status excluded." },
  };
  for (const { state_code: code } of additional) {
    const file = `additional/${code}.json.gz`;
    bodies[file] = { body: readFileSync(resolve(source, "dist/participation-local", `${code}.json.gz`)),
      url: publication + `participation-local/${code}.json.gz` };
  }
  const metadata = { contract: "participation.accepted_export_inputs.v1",
    source_export_revision: acceptance.code_publication.commit,
    pages_run_id: acceptance.code_publication.pages_run_id,
    source_exports_not_native_reacquisition: true,
    additional_states: additional.map(row => row.state_code),
    inputs: {} };
  for (const [file, { body, ...details }] of Object.entries(bodies)) {
    const target = resolve(output, "inputs", file);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, body);
    metadata.inputs[file] = { ...pin(body), ...details };
  }
  writeFileSync(resolve(output, "inputs.json"), encoded(metadata));
  return writeCounts(output, resolve(output, "runtime"));
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const result = migrateCounts(resolve(process.argv[2]), resolve(process.argv[3]),
    JSON.parse(readFileSync(resolve(process.argv[4]))));
  console.log(JSON.stringify({ version: result.descriptor.version,
    states: Object.keys(result.index.states).length,
    records: Object.values(result.index.coverage).reduce((sum, row) => sum + row.records, 0) }));
}

import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { gunzipSync } from "node:zlib";
import { countStates, validateCountShard } from "../public/scripts/participation-counts.js";

export const countPublicationDirectory = "data/participation-counts/20261110-02";
const root = resolve(countPublicationDirectory);
const digest = body => createHash("sha256").update(body).digest("hex");
/**
 * @typedef {Record<string, any> & {state_code: string, year: number, county: string,
 * ballots: number|null, denominator: number|null, reported_pct: number|null, quality: string[]}} CountView
 * @typedef {{additional: {counties: CountView[], precincts: CountView[], nongeographic: CountView[],
 * county_frames: Record<string, Record<string, CountView[]>>, county_frame_holds: Record<string, any>},
 * reviewedCounties: CountView[], reviewedStates: CountView[], countyContext: any, index: any,
 * descriptor: any, metadata: any}} CountPublication
 */
/** @type {CountPublication|undefined} */
let publication;

export function countyContextSuccessor(baseline, successor) {
  const pointer = successor?.pointer;
  if (successor?.predecessor_review_sha256 !== baseline.review_sha256
    || pointer?.schema_version !== 1
    || !/^https:\/\/raw\.githubusercontent\.com\/hanshanley\/voter-participation\/[a-f0-9]{40}\/data\/participation-access\/[a-z0-9-]+\/context\/$/.test(pointer.base_url)
    || !/^[a-f0-9]{64}$/.test(pointer.review_sha256)
    || !Number.isSafeInteger(pointer.review_bytes) || pointer.review_bytes <= 0
    || !/^[a-f0-9]{64}$/.test(pointer.complete_download_sha256)
    || !Number.isSafeInteger(pointer.complete_download_bytes) || pointer.complete_download_bytes <= 0)
    throw new Error("Invalid pinned contextual county review successor");
  return { ...baseline, ...pointer, downloads: [...pointer.downloads, ...baseline.downloads] };
}

export function loadCountPublication() {
  if (publication) return publication;
  const metadata = JSON.parse(readFileSync(resolve(root, "inputs.json")));
  const input = file => {
    const body = readFileSync(resolve(root, "inputs", file));
    const expected = metadata.inputs[file];
    if (!expected || body.length !== expected.bytes || digest(body) !== expected.sha256)
      throw new Error("Frozen count publication input differs: " + file);
    return file.endsWith(".gz") ? JSON.parse(gunzipSync(body)) : JSON.parse(body);
  };
  const descriptor = JSON.parse(readFileSync(resolve(root, "runtime/dataset.json")));
  const runtime = file => {
    if (!/^(index\.json|states\/[A-Z]{2}\.json\.gz)$/.test(file))
      throw new Error("Unknown count publication path");
    const body = readFileSync(resolve(root, "runtime", file));
    const expected = descriptor.files[file];
    if (!expected || body.length !== expected.bytes || digest(body) !== expected.sha256)
      throw new Error("Frozen canonical count shard differs: " + file);
    return file.endsWith(".gz") ? JSON.parse(gunzipSync(body)) : JSON.parse(body);
  };
  const index = runtime("index.json");
  if (index.contract !== "participation.count_index.v1"
      || Object.keys(index.states).sort().join() !== [...countStates].sort().join())
    throw new Error("Frozen canonical count inventory differs");
  for (const code of countStates)
    validateCountShard(runtime(index.states[code].file), code, index.states[code]);
  const reviewed = input("reviewed.json");
  const additional = { counties: [], precincts: [], nongeographic: [], county_frames: {}, county_frame_holds: {} };
  for (const code of metadata.additional_states) {
    const data = input(`additional/${code}.json.gz`);
    for (const key of ["counties", "precincts", "nongeographic"]) additional[key].push(...data[key]);
    if (data.county_frames) additional.county_frames[code] = data.county_frames;
    if (data.county_frame_holds) additional.county_frame_holds[code] = data.county_frame_holds;
  }
  const successorPath = resolve("data/participation-counts/context-review.json");
  const countyContext = existsSync(successorPath)
    ? countyContextSuccessor(reviewed.county_context, JSON.parse(readFileSync(successorPath)))
    : reviewed.county_context;
  publication = { additional, reviewedCounties: reviewed.counties, reviewedStates: reviewed.states,
    countyContext, index, descriptor, metadata };
  return publication;
}

export function legacyCountExport(code) {
  const { metadata } = loadCountPublication();
  if (!metadata.additional_states.includes(code)) throw new Error("Unknown retained count export");
  return readFileSync(resolve(root, "inputs/additional", `${code}.json.gz`));
}

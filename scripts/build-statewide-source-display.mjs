import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, existsSync, writeFileSync } from "node:fs";
import { resolve, join } from "node:path";
import { gunzipSync } from "node:zlib";
import { validateStatewideIndex, validateStatewideProfile } from "../public/scripts/participation-statewide-source.js";

const args=Object.fromEntries(Array.from({length:(process.argv.length-2)/2},(_,i)=>process.argv.slice(2+2*i,4+2*i)));
assert.ok(args["--input"] && args["--output"] && /^[a-f0-9]{40}$/.test(args["--source-commit"] || ""),
  "Use --input PRODUCT --output DIRECTORY --source-commit IMMUTABLE_RESEARCH_COMMIT");
const sourcePath=args["--source-path"] || "data/statewide-source-model/20261124-01/";
assert.match(sourcePath,/^data\/[A-Za-z0-9_/-]+\/$/);assert.ok(!sourcePath.split("/").includes(".."));
const input=resolve(args["--input"]),output=resolve(args["--output"]);
const bytes=readFileSync(join(input,"house/statewide-source/index.json.gz"));
const decoded=gunzipSync(bytes),index=validateStatewideIndex(JSON.parse(decoded));
const digest=value=>createHash("sha256").update(value).digest("hex");
let baseline;
for (const [profile,pin] of Object.entries(index.profiles)) {
  const body=readFileSync(join(input,pin.path)),json=gunzipSync(body);
  assert.equal(body.length,pin.bytes);assert.equal(digest(body),pin.sha256);
  assert.equal(json.length,pin.decoded_bytes);assert.equal(digest(json),pin.decoded_sha256);
  const value=validateStatewideProfile(JSON.parse(json),index,profile);
  if(profile==="original")baseline=value.models[index.metadata.default_family];
}
const summaryBytes=readFileSync(join(input,"display-summary.json")),summary=JSON.parse(summaryBytes);
assert.deepEqual(summary,{metadata:index.metadata,rows:baseline.rows.map(row=>({
  state_code:row.state_code,point:row.point,sensitivity:row.sensitivity}))});
const base_url=`https://raw.githubusercontent.com/hanshanley/voter-participation/${args["--source-commit"]}/${sourcePath}`;
const receipt={contract:index.contract,version:index.metadata.version,path:"house/statewide-source/index.json.gz",
  base_url,url:base_url+"house/statewide-source/index.json.gz",compression:"gzip",media_type:"application/json",
  bytes:bytes.length,sha256:digest(bytes),decoded_bytes:decoded.length,decoded_sha256:digest(decoded),
  display_summary:{bytes:summaryBytes.length,sha256:digest(summaryBytes)}};
const files={"display-summary.json":summaryBytes,"receipt.json":Buffer.from(JSON.stringify(receipt,null,2)+"\n")};
if(existsSync(output)) {
  for(const [name,body] of Object.entries(files))assert.deepEqual(readFileSync(join(output,name)),body,"Use a new display directory for changed fitted inputs");
} else {
  mkdirSync(output,{recursive:true});for(const [name,body] of Object.entries(files))writeFileSync(join(output,name),body);
}
console.log(JSON.stringify({status:"passed",states:50,version:index.metadata.version,source_commit:args["--source-commit"]}));

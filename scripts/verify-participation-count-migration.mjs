import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { gunzipSync } from "node:zlib";
import vm from "node:vm";
import { readCountInputs, encoded, compileCounts } from "./compile-participation-counts.mjs";
import { countStates, countModes, countFrame, validateCountShard } from "../public/scripts/participation-counts.js";
import { hasCountySourceMode, selectCountySourceFrame } from "../public/scripts/participation-geography.js";

export async function verifyMigration(root, legacySource, runtimeRoot) {
  const { inputs, metadata } = readCountInputs(root);
  const reviewed = JSON.parse(inputs["reviewed.json"]);
  const start = legacySource.indexOf("    const additionalLocal = new Map();");
  const end = legacySource.indexOf("    const electorateLabel", start);
  assert.ok(start > 0 && end > start, "Use the actual previously accepted count reader as the oracle");
  let code, mode;
  const state = { reviewedCounties: reviewed.counties,
    additionalCoverage: metadata.additional_states.map(state_code => ({ state_code })),
    current: { local_file: "local.json" }, currentPath: "/base/", selectedState: "" };
  const reader = vm.runInNewContext(`(() => {
    ${legacySource.slice(start, end)}
    return currentLocal;
  })()`, {
    state, stateCode: () => code, $: () => ({ value: mode }), hasCountySourceMode, selectCountySourceFrame,
    globalThis: { DecompressionStream }, DecompressionStream, Response,
    fetch: async path => path === "/base/local.json" ? new Response(inputs["local.json"])
      : new Response(inputs[`additional/${String(path).split("/").at(-1)}`] || null,
        { status: inputs[`additional/${String(path).split("/").at(-1)}`] ? 200 : 404 }),
  });
  const index = JSON.parse(readFileSync(resolve(runtimeRoot, "index.json")));
  const cases = [];
  let records = 0, zeros = 0, unknown = 0, withheld = 0;
  for (code of countStates) {
    const data = validateCountShard(JSON.parse(gunzipSync(readFileSync(
      resolve(runtimeRoot, index.states[code].file)))), code, index.states[code]);
    records += data.records.length;
    zeros += data.records.filter(row => row.count.value === 0).length;
    unknown += data.records.filter(row => row.count.status === "unknown").length;
    withheld += data.records.filter(row => row.count.status === "withheld").length;
    for (mode of countModes) {
      state.selectedState = code;
      const before = await reader(), after = countFrame(data, mode);
      for (const key of ["counties", "precincts", "nongeographic", "unmapped_source_regions"]) {
        const old = (before[key] || []).filter(row => !row.state_code || row.state_code === code);
        assert.equal(encoded(after[key]).toString(), encoded(old).toString(),
          `Changed accepted ${code}/${mode}/${key}`);
      }
      assert.equal(Boolean(after.source_mode_unavailable), Boolean(before.source_mode_unavailable));
      cases.push({ state: code, mode, exact_all_fields: true,
        counties: after.counties.length, units: after.precincts.length,
        nongeographic: after.nongeographic.length, held_regions: after.unmapped_source_regions.length });
    }
  }
  const reproduction = compileCounts(inputs, metadata);
  for (const [file, body] of Object.entries(reproduction.files))
    assert.deepEqual(body, readFileSync(resolve(runtimeRoot, file)), "Runtime reproduction differs: " + file);
  return { status: "PASS_actual_accepted_reader_exact_all_fields_all_views_and_offline_reproduction",
    source_export_revision: metadata.source_export_revision,
    version: reproduction.descriptor.version, jurisdictions: countStates.length,
    retained_source_appearances_not_people: records, zeros, unknown, withheld,
    cases, exact_runtime_files: Object.keys(reproduction.files).length,
    native_sources_reparsed: 0, new_geographic_approvals: 0 };
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const result = await verifyMigration(resolve(process.argv[2]),
    readFileSync(resolve(process.argv[3]), "utf8"), resolve(process.argv[4]));
  writeFileSync(resolve(process.argv[5]), JSON.stringify(result, null, 2) + "\n");
  console.log(JSON.stringify({ status: result.status, jurisdictions: result.jurisdictions,
    cases: result.cases.length, records: result.retained_source_appearances_not_people,
    zeros: result.zeros, unknown: result.unknown, version: result.version }));
}

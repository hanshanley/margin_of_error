import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { coverageRows } from "../public/scripts/participation-coverage.js";

const catalog = { datasets: {
  "participation-counts-2026": { status: "loaded" },
  "participation-native-bindings-2026": { status: "loaded" },
} };
const counts = { states: { MN: { views: {
  available: { counties: 87, precincts: 4105, holds: 0,
    dispositions: { counties: { reported: 87, unknown: 0, withheld: 0, qualified_fractions: 73 } } },
} } } };
test("coverage uses the actual selected frame, not an old audit badge or source-row sum", () => {
  const rows = coverageRows(catalog, counts, {}, { year: 2026, mode: "available", level: "county" });
  assert.equal(rows.length, 51);
  const mn = rows.find(row => row.code === "MN");
  assert.equal(mn.source_rows, 87); assert.equal(mn.reported, 87); assert.equal(mn.fractions, 73);
  assert.equal(rows.find(row => row.code === "AK").status, "Missing for this scope");
  const early = coverageRows(catalog, counts, {}, { year: 2026, mode: "mail_returned", level: "precinct" });
  assert.equal(early.find(row => row.code === "MN").status, "Missing for this scope");
});
test("awaiting and rejected datasets are not disguised as ordinary geographic missingness", () => {
  const scope = { year: 2026, mode: "available", level: "county" };
  assert.equal(coverageRows({ datasets: {} }, null, null, scope)[0].status, "Awaiting publication");
  assert.equal(coverageRows({ datasets: {} }, null, null, scope)[0].reported, null);
  assert.equal(coverageRows(catalog, counts, {}, scope,
    { "participation-counts-2026": "checksum differs" })[0].status, "Rejected by reader");
  assert.deepEqual(coverageRows(catalog, counts, {}, { ...scope, year: 2024 }), []);
});
test("table-only reporting units are loaded without inventing geographic references or rates", () => {
  const native = { reporting_tables: { AZ: { rows: 1763, eligible_modes: ["official"],
    coverage: { source_rows: 1763, reported: 1762, unknown: 1, withheld: 0, fractions: 0 } } } };
  const row = coverageRows(catalog, {}, native, { year: 2026, mode: "official", level: "precinct" })
    .find(row => row.code === "AZ");
  assert.equal(row.status, "Loaded (table only)");
  assert.equal(row.source_rows, 1763);
  assert.equal(row.reference_units, 0);
  assert.equal(row.unknown, 1);
  assert.equal(row.fractions, 0);
});

test("coverage links the validated scope package and clears rejected, historical or unsafe links", async () => {
  const source = readFileSync(new URL("../public/scripts/participation-coverage.js", import.meta.url), "utf8");
  const start = source.indexOf("export function installCoverage(");
  assert(start >= 0);
  const element = tag => ({
    tag, children: [], dataset: {},
    set textContent(value) { this.text = value; this.children = []; },
    get textContent() { return this.text; },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
  });
  const caption = element("p"), body = element("tbody");
  const host = { dataset: {}, querySelector: selector =>
    selector === "tbody" ? body : caption };
  const pointers = {
    counts: { version: "counts-version", complete_download: { url: "https://example.org/complete-counts.zip" } },
    native: { version: "native-version", complete_download: { url: "https://example.org/complete-native.zip" } },
  };
  const rejected = new Set();
  const install = runInNewContext(`(${source.slice(start + "export ".length)})`, {
    document: { createElement: element }, coverageRows,
    loadDatasetCatalog: async () => catalog,
    loadCountIndex: async () => {
      if (rejected.has("counts")) throw new Error("counts checksum differs");
      return { index: counts, entry: pointers.counts };
    },
    loadNativeIndex: async () => {
      if (rejected.has("native")) throw new Error("native checksum differs");
      return { index: {}, entry: pointers.native };
    },
  });
  const coverage = install(host);
  const scope = { year: 2026, mode: "available", level: "county" };
  const links = () => caption.children.filter(node => node?.tag === "a");
  await coverage.setScope(scope);
  assert.equal(links().length, 1);
  assert.equal(links()[0].href, pointers.counts.complete_download.url);
  assert.equal(links()[0].textContent, "Complete numerical inputs, queries and results");
  await coverage.setScope({ ...scope, level: "precinct" });
  assert.equal(links()[0].href, pointers.native.complete_download.url);
  for (const [level, dataset] of [["county", "counts"], ["precinct", "native"]]) {
    rejected.add(dataset);
    await coverage.setScope({ ...scope, level });
    assert.equal(links().length, 0);
    rejected.clear();
  }
  await coverage.setScope(scope);
  await coverage.setScope({ ...scope, year: 2024 });
  assert.equal(links().length, 0);
  for (const url of [null, undefined, "javascript:alert(1)", "http://example.org/complete.zip"]) {
    pointers.counts.complete_download.url = url;
    await coverage.setScope(scope);
    assert.equal(links().length, 0);
  }
});

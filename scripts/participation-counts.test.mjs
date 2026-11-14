import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { canonicalObservation, encoded, digest, pin, selectedFrame } from "./compile-participation-counts.mjs";
import { countModes, countStates, validateCountObservation, validateCountShard,
  validateCurrentCountSnapshot, countFrame } from "../public/scripts/participation-counts.js";

const view = () => ({ year: 2026, state_code: "MN", county_id: "native:1", county: "Example",
  ballots: 0, denominator: 100, denominator_basis: "native_registered_voters",
  reported_pct: 0, source_update_label: "November 3; timezone not supplied",
  source_url: "https://example.org/counts", quality: ["Native conflict remains in original fields."] });
const input = { file: "original.json", sha256: "a".repeat(64), url: "https://example.org/export.json" };
const observation = () => canonicalObservation(view(), input, "counties", 0);

test("canonical migration preserves zero, unknown, withheld fraction and literal source fields", () => {
  const row = observation();
  validateCountObservation(row, "MN");
  assert.equal(row.count.value, 0);
  assert.equal(row.count.status, "reported");
  assert.equal(row.source_clock.timezone, null);
  assert.equal(row.reporting_status.complete, null);
  assert.equal(row.geography.join.status, "unreviewed");
  assert.deepEqual(row.view, row.source.fields);
  const unknown = view();
  unknown.ballots = null; unknown.reported_pct = null;
  const absent = canonicalObservation(unknown, input, "counties", 0);
  validateCountObservation(absent, "MN");
  assert.equal(absent.count.status, "unknown");
  assert.equal(absent.denominator.qualified, false);
  const held = canonicalObservation({ ...unknown,
    native_record: { source_scope_review: "withheld_processed_not_defined_as_counted" } }, input, "counties", 0);
  validateCountObservation(held, "MN");
  assert.equal(held.count.status, "withheld");
  assert.equal(held.count.value, null);
  assert.notEqual(row.id, canonicalObservation({ ...view(), source_mode: "mail_returned" }, input, "counties", 0).id);
});

test("common contract rejects state/count changes, candidate substitution, false zeros and rate promotion", () => {
  for (const mutate of [
    row => { row.geography.state_code = "NM"; },
    row => { row.count.value = null; },
    row => { row.count.value = false; row.view.ballots = false; },
    row => { row.count.value = Number.MAX_SAFE_INTEGER + 1; },
    row => { row.measure.kind = "candidate_votes"; },
    row => { row.denominator.qualified = false; },
    row => { row.source_clock.literal = null; row.source_clock.timezone = "UTC"; },
    row => { row.geography.join.status = "approved"; },
    row => { row.reporting_status.reported_units = 2; row.reporting_status.total_units = 1; },
    row => { row.quality.conflicts = [{ code: "native_disagreement", repaired: true }]; },
  ]) {
    const row = observation(); mutate(row);
    assert.throws(() => validateCountObservation(row, "MN"), /Unqualified/);
  }
});

function shard() {
  const row = observation();
  return { contract: "participation.count_snapshot.v1", year: 2026, state_code: "MN",
    records: [row], views: Object.fromEntries(countModes
      .map(mode => [mode, { qualified: mode === "available" || mode === "official",
        counties: mode === "available" || mode === "official" ? [row.id] : [],
        precincts: [], nongeographic: [], holds: [] }])) };
}

test("canonical mode bindings reject missing references, duplicate identities and all-method substitution", () => {
  validateCountShard(shard(), "MN", { records: 1 });
  assert.equal(countFrame(shard(), "available").counties[0].ballots, 0);
  for (const mutate of [
    data => { data.records.push(data.records[0]); },
    data => { data.views.available.counties.push(data.records[0].id); },
    data => { data.views.available.counties = ["b".repeat(32)]; },
    data => { data.views.mail_returned.qualified = true; data.views.mail_returned.counties = [data.records[0].id]; },
    data => { data.views.official.qualified = false; },
  ]) {
    const data = shard(); mutate(data);
    assert.throws(() => validateCountShard(data, "MN", { records: data.records.length }), /Duplicate|Unqualified/);
  }
});

function registryShard() {
  const data = shard(), context = observation();
  context.id = "c".repeat(32);
  context.measure = { id: "registry-date-token", literal: "Current registration records",
    kind: "source_activity", mode: "source_defined", unit: "current_registration_records" };
  context.election.type = "date_coded_history_context";
  context.election.qualification = "collector_context";
  context.denominator = null;
  context.view = { ...context.view, denominator: null, reported_pct: null, maps_approved: false,
    administrative_history_context_only: true, source_frame_kind: "current_registry_date_token",
    source_input_kind: "person_record_file_retained_privately", derived_aggregate: true };
  context.source.fields = context.view;
  data.records.push(context);
  data.views.available.administrative_contexts = [context.id];
  return data;
}

test("registry context is a separate optional channel and preserves the original county inventory", () => {
  const data = registryShard();
  validateCountShard(data, "MN", { records: 2 });
  assert.equal(countFrame(data, "available").counties.length, 1);
  assert.equal(countFrame(data, "available").administrative_contexts.length, 1);
  assert.equal(countFrame(data, "available").administrative_contexts[0].ballots, 0);
  assert.deepEqual(countFrame(shard(), "available").administrative_contexts, []);
  assert.deepEqual(countFrame(data, "official").administrative_contexts, []);
});

test("registry context rejects ballot, electorate, map and ordinary-frame promotions", () => {
  for (const mutate of [
    data => { data.records[1].measure.kind = "ballots_cast"; },
    data => { data.records[1].measure.mode = "all_methods"; },
    data => { data.records[1].measure.unit = "voters"; },
    data => { data.records[1].election.type = "general"; },
    data => { data.records[1].view.maps_approved = true; },
    data => { data.records[1].view.derived_aggregate = false; },
    data => { data.views.available.administrative_contexts.push(data.records[1].id); },
    data => { data.views.official.administrative_contexts = [data.records[1].id]; },
    data => { data.views.available.counties.push(data.records[1].id); },
    data => { data.views.official.counties.push(data.records[1].id); },
  ]) {
    const data = registryShard();
    mutate(data);
    assert.throws(() => validateCountShard(data, "MN", { records: 2 }));
  }
});

test("old frame migration keeps unmatched source regions separate and never enables an unsupported mode", () => {
  const unavailable = selectedFrame({ counties: [view()], precincts: [], nongeographic: [] }, null, "NH", "mail_returned");
  assert.equal(unavailable.qualified, false);
  assert.deepEqual(unavailable.counties, []);
  const accepted = selectedFrame({ counties: [view()], precincts: [], nongeographic: [] }, null, "MN", "available");
  assert.equal(accepted.counties[0].ballots, 0);
  assert.deepEqual(accepted.holds, []);
});

test("content identity uses the same canonical ASCII/sorted JSON as the intake backend", () => {
  assert.equal(encoded({ z: "é", a: [true, null, 0] }).toString(), '{"a":[true,null,0],"z":"\\u00e9"}\n');
  assert.equal(pin(Buffer.from("a")).sha256, digest(Buffer.from("a")));
});

test("the current statewide/provider snapshot requires all distinct jurisdictions and exact counts", () => {
  const current = () => ({ contract: "participation.current_snapshot.v1", reviewed_states: [],
    snapshot: { coverage: countStates.map(state_code => ({ state_code })),
      reporting: [{ state_code: "AL", ballots: 0 }], early_voting: [{ state_code: "AK", ballots: null }] } });
  validateCurrentCountSnapshot(current());
  for (const mutate of [
    data => { data.snapshot.coverage[0].state_code = "AK"; },
    data => { data.snapshot.reporting[0].ballots = undefined; },
    data => { data.snapshot.early_voting[0].ballots = 1.5; },
  ]) {
    const data = current(); mutate(data);
    assert.throws(() => validateCurrentCountSnapshot(data), /Unqualified/);
  }
});

function detailHarness() {
  const source = readFileSync(new URL("../public/scripts/participation-explorer.js", import.meta.url), "utf8");
  const start = source.indexOf("const electorateLabel =");
  const end = source.indexOf("\n    async function currentNavigation(", start);
  assert(start >= 0 && end > start);
  const html = (tag, className, textContent) => ({ tag, className, textContent });
  const detail = runInNewContext(`(() => { ${source.slice(start, end)}; return currentCountDetail; })()`, {
    residentSource() {}, html, state: { currentPrecinctShapes: new Map() },
    fmt: value => value == null ? "\u2014" : String(value),
    pct: () => "Unavailable",
    sourceLink: row => ({ ...html("a", "source-link", "Original source"), href: row.source_url }),
  });
  const host = { children: [], replaceChildren(...children) { this.children = children; },
    append(...children) { this.children.push(...children); } };
  return { detail, host };
}

test("legacy reporting details expose supplied complete packages without claiming a native review", () => {
  const { detail, host } = detailHarness();
  const row = { ...view(), unit: "Native reporting row", unit_kind: "precinct",
    denominator: null, reported_pct: null, source_update_label: null,
    complete_download_url: "https://example.org/complete-source.zip" };
  const before = structuredClone(row);
  detail(host, row);
  const links = host.children.filter(node => node.tag === "a");
  assert.deepEqual(links.map(node => node.href), [row.source_url, row.complete_download_url]);
  assert.equal(links[1].textContent, "Complete source tables and source package");
  assert(!host.children.some(node => node.textContent?.startsWith("Native result-status literal:")));
  assert.deepEqual(row, before);
  for (const complete_download_url of [null, undefined]) {
    detail(host, { ...row, complete_download_url });
    assert.deepEqual(host.children.filter(node => node.tag === "a").map(node => node.href),
      [row.source_url]);
  }
});

test("non-review details honor the source measure label and literal while preserving the ballot fallback", () => {
  const { detail, host } = detailHarness();
  for (const [fields, label] of [
    [{ participation_measure_label: "Current-registration records",
      participation_measure_literal: "Native history tokens" }, "Current-registration records"],
    [{ participation_measure_literal: "Absentee In-person" }, "Absentee In-person"],
    [{}, "ballots reported"],
  ]) {
    detail(host, { ...view(), ...fields }, true);
    assert.equal(host.children.find(node => node.className === "selection-basis").textContent,
      `2026 ${label} · unofficial`);
  }
});

test("registry-history details disclose their record frame without ballot fractions or precinct reporting", () => {
  const { detail, host } = detailHarness();
  const row = { ...view(), ballots: 12, denominator: null, reported_pct: null,
    administrative_history_context_only: true, source_frame_kind: "current_registry_date_token",
    participation_measure_label: "Current-registration records with a date-coded history token",
    source_update_label: "Native file-update literal; timezone unknown" };
  const before = structuredClone(row);
  detail(host, row, true);
  const text = host.children.map(node => node.textContent).filter(Boolean).join("\n");
  assert.match(text, /current registry, not an election ballot total/);
  assert.match(text, /Registry file update: Native file-update literal/);
  assert.match(text, /Missing history is not observed nonparticipation/);
  assert.doesNotMatch(text, /source precincts reporting|fraction\. Not final turnout|2026 ballots reported/);
  assert.deepEqual(row, before);
});

test("non-review county details retain literal source status and only supplied reporting metadata", () => {
  const { detail, host } = detailHarness();
  const row = { ...view(), source_status_literal: "Official results following county canvass" };
  detail(host, row, true);
  assert.equal(host.children.find(node => node.className === "selection-basis").textContent,
    "2026 ballots reported · Official results following county canvass");
  assert(!host.children.some(node => node.textContent?.includes("source precincts reporting")));
  detail(host, { ...row, reported_units: null, total_units: null, source_rows: null }, true);
  assert(!host.children.some(node => node.textContent?.includes("source precincts reporting")));
  detail(host, { ...row, reported_units: 0, total_units: 10, source_rows: 0 }, true);
  assert(host.children.some(node => node.textContent?.startsWith("0 / 10 source precincts reporting.")));
});

test("unknown source electorate metadata renders as unknown without inventing a denominator", () => {
  const { detail, host } = detailHarness();
  for (const denominator_basis of [null, undefined]) {
    const row = { ...view(), denominator: null, denominator_basis, reported_pct: null };
    const before = structuredClone(row);
    detail(host, row, true);
    assert(host.children.some(node => node.textContent?.includes("source electorate not supplied")));
    assert.equal(host.children.find(node => node.className === "selection-rate").textContent, "0");
    assert.deepEqual(row, before);
  }
});

test("native reporting identifiers are not called ordinals and adjacent source downloads stay distinct", () => {
  const { detail, host } = detailHarness();
  const row = { ...view(), unit: "5-3", unit_kind: "source_native_precinct_code",
    complete_download_url: "https://example.org/complete-source.zip" };
  detail(host, row);
  const text = host.children.map(node => node.textContent).filter(Boolean).join("\n");
  assert.match(text, /source native precinct code/);
  assert.doesNotMatch(text, /row ordinal/);
  detail(host, row, true);
  const source = host.children.findIndex(node => node.tag === "a");
  assert.equal(host.children[source + 1].textContent, " · ");
  assert.equal(host.children[source + 2].href, row.complete_download_url);
});

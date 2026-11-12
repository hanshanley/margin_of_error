import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { validateNorcHouse, norcGroups, norcEstimate, norcMapValue,
  roundedNorcContributions, norcTerms } from "../public/scripts/participation-norc-house.js";

const bytes = readFileSync("data/participation-return-attribution/20261112-01/norc-test-oracle.json");
const source = JSON.parse(bytes);
const fresh = () => structuredClone(source);
const receipt = JSON.parse(readFileSync("data/participation-return-attribution/20261112-01/norc-receipt.json"));

test("all House mechanisms and separate demographic partitions reconcile to each state", () => {
  validateNorcHouse(source);
  for (const row of source.rows) {
    const rounded = roundedNorcContributions(row.point);
    assert.ok(Math.abs(Object.values(rounded).reduce((a,b)=>a+b,0)-Number(row.point.total_change_pp.toFixed(2)))<1e-8);
    for (const dimension of new Set(row.groups.map(g=>g.dimension))) {
      const groups=row.groups.filter(g=>g.dimension===dimension && g.available);
      assert.ok(Math.abs(groups.reduce((sum,g)=>sum+g.total_contribution_pp,0)-row.point.total_change_pp)<1e-7);
      for (const group of groups) {
        const values=roundedNorcContributions(group);
        assert.ok(Math.abs(Object.values(values).reduce((a,b)=>a+b,0)-Number(group.total_contribution_pp.toFixed(2)))<1e-8);
      }
    }
    assert.equal(norcMapValue(row,"modeled_nonparticipation"),row.point.contributions_pp.entry+row.point.contributions_pp.exit);
    for (const [key] of norcTerms) assert.equal(norcMapValue(row,key),row.point.contributions_pp[key]);
  }
});

test("held groups and missing observed comparisons never become zero or another frame", () => {
  assert.equal(norcMapValue(null,"switching"),null);
  let held=0, missing=0;
  for (const row of source.rows) {
    if (!row.source_comparison_available) {assert.equal(norcMapValue(row,"reported_total"),null);missing++;}
    for (const group of row.groups.filter(g=>!g.available)) {
      const id=group.dimension+"|"+group.group;
      assert.equal(norcEstimate(row,id),null);assert.equal(norcMapValue(row,"switching",id),null);held++;
    }
  }
  assert.ok(missing>0 && held>0);
  assert.ok(norcGroups(source).every(g=>!g.value.endsWith("|unshown")));
});

test("reject altered endpoints, mechanisms, missing states, and promoted behavioral claims", () => {
  for (const mutate of [
    d=>{d.rows[0].state_code="ZZ";d.rows[0].id="ZZ-house";},
    d=>{d.rows[0].point.contributions_pp.entry+=1;},
    d=>{d.rows.find(r=>r.source_comparison_available).reported_comparison.previous.D+=10;},
    d=>{d.rows[0].joint[0][0]=-1;},
    d=>{d.rows[0].groups.find(g=>g.available).contributions_pp.entry+=1;},
    d=>{d.current_party_totals_used_in_source_model_training=true;},
    d=>{d.source_likelihood_is_completed_voting=true;},
    d=>{d.demographic_dimensions_are_additive_together=true;},
    d=>{d.rows[0].measured_staying_home=0;},
    d=>{d.rows.find(r=>!r.source_comparison_available).assumed_accounting_frame_units=1;},
  ]) {
    const value=fresh();mutate(value);assert.throws(()=>validateNorcHouse(value));
  }
});

test("prediction error stays separate from a fitted behavioral contribution", () => {
  for (const row of source.rows.filter(r=>r.source_comparison_available)) {
    const check=row.before_current_party_conditioning;
    assert.equal(check.current_party_totals_used,false);
    assert.ok(Math.abs(row.reported_comparison.current_margin_pp-check.current_margin_pp
      -check.prediction_error_observed_minus_predicted_pp)<1e-8);
    assert.equal(norcMapValue(row,"prediction_error"),null);
  }
  const tx=source.rows.find(r=>r.state_code==="TX");
  assert.ok(tx.before_current_party_conditioning.prediction_error_observed_minus_predicted_pp>10);
  assert.notEqual(norcMapValue(tx,"switching","AGE6|30_49"),norcMapValue(tx,"switching","AGE6|65_plus"));
});

test("exact frozen source loads once; corruption fails and a fresh retry succeeds", async () => {
  const { loadNorcHouse }=await import("../public/scripts/participation-norc-house.js?loader-test");
  let calls=0;
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>{calls++;return new Response(calls===1 ? Buffer.concat([bytes,Buffer.from(" ")]) : bytes);};
    await assert.rejects(loadNorcHouse(receipt),/checksum/);
    assert.equal((await loadNorcHouse(receipt)).rows.length,50);
    await loadNorcHouse(receipt);assert.equal(calls,2);
    await assert.rejects(loadNorcHouse({...receipt,url:receipt.url.replace(receipt.source_commit,"main")}),/Unpinned/);
    assert.equal(createHash("sha256").update(bytes).digest("hex"),receipt.sha256);
  } finally {globalThis.fetch=original;}
});

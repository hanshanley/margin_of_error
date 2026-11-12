import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { validateNorcHouse, norcGroups, norcEstimate, norcMapValue,
  roundedNorcContributions, norcTerms, validateNorcFamilies, norcFamilies,
  norcContributionScale } from "../public/scripts/participation-norc-house.js";

const bytes = readFileSync("data/participation-return-attribution/20261112-02/norc-test-oracle.json");
const source = JSON.parse(bytes);
const fresh = () => structuredClone(source);
const receipt = JSON.parse(readFileSync("data/participation-return-attribution/20261112-02/norc-receipt.json"));

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

const scores=JSON.parse(readFileSync("data/participation-return-attribution/20261112-03/family-summary.json"));
const comparison=()=>({contract:"participation.house_model_families.v1",
  no_independent_behavioral_identification:true,family_spread_is_not_confidence_interval:true,
  preferred_family:scores.summary.preferred_family,family_labels:scores.family_labels,
  source_validation:structuredClone(scores.source_validation),
  families:Object.fromEntries(norcFamilies.map(([family])=>[family,fresh()]))});

test("family selection uses source validation, not lower current-return MAE",()=>{
  assert.equal(validateNorcFamilies(comparison()).preferred_family,"accepted_ridge_multinomial");
  for(const mutate of [
    d=>{d.preferred_family="histogram_gradient_boosting";},
    d=>{d.source_validation[0].current_returns_used_for_fit_or_selection=true;},
    d=>{d.source_validation[1]=d.source_validation[0];},
    d=>{d.families.extra_randomized_trees.rows[0].reported_comparison.qualification="different scope";},
    d=>{d.families.extra_randomized_trees.rows[0].groups[0].label="different group";},
  ]){
    const data=comparison();mutate(data);assert.throws(()=>validateNorcFamilies(data));
  }
});

test("share units halve all signed terms and preserve gross retention and missingness",()=>{
  assert.throws(()=>norcContributionScale("all_candidate_share"));
  for(const row of source.rows){
    for(const group of ["",...row.groups.map(g=>g.dimension+"|"+g.group)]){
      for(const field of ["reported_total",...norcTerms.map(([key])=>key),"modeled_nonparticipation","retaining"]){
        const margin=norcMapValue(row,field,group),share=norcMapValue(row,field,group,"democratic_two_party_share");
        assert.equal(share,margin===null?null:field==="retaining"?margin:margin/2);
      }
      const estimate=norcEstimate(row,group);
      if(estimate){
        const rounded=roundedNorcContributions(estimate,"democratic_two_party_share");
        const target=Number(((estimate.total_contribution_pp??estimate.total_change_pp)/2).toFixed(2));
        assert.ok(Math.abs(Object.values(rounded).reduce((a,b)=>a+b,0)-target)<1e-8);
      }
    }
  }
});

test("pinned family envelopes load through the same checksum and retry contract",async()=>{
  const {loadNorcHouse}=await import("../public/scripts/participation-norc-house.js?family-loader-test");
  const bytes=Buffer.from(JSON.stringify(comparison()));
  const receipt={url:"https://raw.githubusercontent.com/hanshanley/voter-participation/"+"a".repeat(40)
    +"/data/house-model-families/20261112-01/viewer-data.json",
    bytes:bytes.length,sha256:createHash("sha256").update(bytes).digest("hex")};
  const original=globalThis.fetch;
  try{
    globalThis.fetch=async()=>new Response(Buffer.concat([bytes,Buffer.from(" ")]));
    await assert.rejects(loadNorcHouse(receipt),/checksum/);
    globalThis.fetch=async()=>new Response(bytes);
    assert.equal((await loadNorcHouse(receipt)).preferred_family,"accepted_ridge_multinomial");
  }finally{globalThis.fetch=original;}
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

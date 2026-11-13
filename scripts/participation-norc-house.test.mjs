import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { validateNorcHouse, norcGroups, norcEstimate, norcMapValue,
  roundedNorcContributions, norcTerms, validateNorcFamilies, norcFamilies,
  norcContributionScale, norcSharedBound, norcRecordedComparison, norcRecordedBound,
  validateNorcAssociation, renderNorcSelection } from "../public/scripts/participation-norc-house.js";

const bytes = readFileSync("data/participation-return-attribution/20261112-02/norc-test-oracle.json");
const source = JSON.parse(bytes);
const fresh = () => structuredClone(source);
const receipt = JSON.parse(readFileSync("data/participation-return-attribution/20261112-02/norc-receipt.json"));

const withComparability=()=>{
  const model=fresh();
  model.comparison_policy={contract:"participation.house_comparability.v1",all_districts_audited:435,
    all_states_audited:50,unchanged_major_party_coverage_required:true,
    raw_aggregate_is_not_preference_swing:true,native_source_counts_changed:false};
  for(const row of model.rows) row.contest_comparability={state_code:row.state_code,
    raw_aggregate_is_not_voter_preference_swing:true,common_source_id_is_not_statewide_estimate:true,
    common_source_id_boundary_stability_qualified:false,like_for_like_statewide_source_comparison:true,
    coverage_changed_districts:[],missing_count_districts:[],multiple_same_party_nominee_districts:[],
    previous_counts:structuredClone(row.reported_comparison.previous),
    current_counts:structuredClone(row.reported_comparison.current)};
  return model;
};

const recordedTexas=()=>({
  state_code:"TX",source_comparison_available:false,
  reported_comparison:{status:"unavailable",reported_change_pp:null},
  contest_comparability:{
    previous_counts:{D:4310913,R:6234918,O:128081},
    current_counts:{D:5147146,R:4591278,O:44093},
  },
});

test("held Texas counts expose +12 share points without authorizing a behavioral explanation",()=>{
  const row=recordedTexas(),comparison=norcRecordedComparison(row);
  assert.ok(Math.abs(comparison.share_change_pp-11.97610547994342)<1e-10);
  assert.equal(comparison.model_eligible,false);
  assert.equal(comparison.raw_party_totals_are_not_preference_swing,true);
  assert.equal(norcMapValue(row,"reported_counts","","democratic_two_party_share"),comparison.share_change_pp);
  assert.equal(norcMapValue(row,"reported_counts"),comparison.share_change_pp*2);
  for(const key of ["reported_total","switching","entry","modeled_nonparticipation"])
    assert.equal(norcMapValue(row,key),null);
});

test("recorded state summaries need counts and qualifications, not fitted model points",()=>{
  class Node {
    dataset={};children=[];hidden=true;
    append(...nodes){this.children.push(...nodes);}
    replaceChildren(...nodes){this.children=nodes;}
  }
  const original=globalThis.document;
  globalThis.document={createElement:()=>new Node()};
  try{
    for(const eligible of [false,true]){
      const row=recordedTexas(),summary=new Node(),detail=new Node();
      row.source_comparison_available=eligible;
      row.reported_comparison.reason="Changed candidate coverage";
      renderNorcSelection(row,"","Texas",summary,detail,{view:"reported_counts",units:"democratic_two_party_share"});
      assert.equal(summary.hidden,false);
      assert.equal(detail.hidden,true);
      assert.equal(summary.dataset.norcState,"TX");
      assert.ok(summary.children.some(node=>node.textContent?.includes("+11.98 pp share change")));
      assert.equal(summary.dataset.norcHold,eligible?undefined:"true");
    }
  }finally{globalThis.document=original;}
});

test("recorded counts preserve unknowns and reject invalid count denominators",()=>{
  for(const mutate of [
    row=>{row.contest_comparability.current_counts.D=null;},
    row=>{row.contest_comparability.current_counts.R=-1;},
    row=>{row.contest_comparability.current_counts.D=.5;},
    row=>{row.contest_comparability.current_counts={D:0,R:0,O:12};},
  ]){
    const row=recordedTexas();mutate(row);
    assert.equal(norcRecordedComparison(row),null);
    assert.equal(norcMapValue(row,"reported_counts"),null);
  }
});

test("unadjusted negative changes are preserved and have a separate recorded-count scale",()=>{
  const positive=recordedTexas(),negative=recordedTexas();
  negative.state_code="MA";
  [negative.contest_comparability.previous_counts,negative.contest_comparability.current_counts]
    =[negative.contest_comparability.current_counts,negative.contest_comparability.previous_counts];
  assert.equal(norcMapValue(negative,"reported_counts"),-norcMapValue(positive,"reported_counts"));
  assert.equal(norcRecordedBound({rows:[positive,negative]}),25);
  assert.equal(norcRecordedBound({rows:[positive,negative]},"democratic_two_party_share"),15);
});

test("changed candidate coverage and native-count substitutions cannot condition behavioral models",()=>{
  validateNorcHouse(withComparability());
  for(const mutate of [
    row=>{row.contest_comparability.like_for_like_statewide_source_comparison=false;},
    row=>{row.contest_comparability.coverage_changed_districts=["MA-03"];},
    row=>{row.contest_comparability.missing_count_districts=["MA-03"];},
    row=>{row.contest_comparability.multiple_same_party_nominee_districts=["MA-03"];},
    row=>{row.contest_comparability.current_counts.D+=1;},
  ]){
    const model=withComparability(),ma=model.rows.find(row=>row.state_code==="MA");mutate(ma);
    assert.throws(()=>validateNorcHouse(model));
  }
});

test("current comparability receipts reject a correctly hashed legacy model",async()=>{
  const {loadNorcHouse}=await import("../public/scripts/participation-norc-house.js?comparability-loader");
  const body=Buffer.from(JSON.stringify(comparison()));
  const receipt={url:"https://raw.githubusercontent.com/hanshanley/voter-participation/"+"d".repeat(40)
    +"/data/house-comparability/20261112-01/viewer-original.json",
    bytes:body.length,sha256:createHash("sha256").update(body).digest("hex"),contest_comparability_required:true};
  const original=globalThis.fetch;
  try{
    globalThis.fetch=async()=>new Response(body);
    await assert.rejects(loadNorcHouse(receipt),/comparability audit is missing/);
  }finally{globalThis.fetch=original;}
});

const officialRevision=()=>{
  const data=comparison();
  data.official_source_revisions=["HI","WY"].map(state_code=>({
    state_code,year:2026,office:"house",stage:"general",native_updated_at:null,
    independent_behavioral_validation:false,counting_complete_independently_qualified:false,
    query_pin:{sha256:"e398311dcecd7607ec41a1af7fda21f99b1e023405503979beb3667941a82f1a"},
  }));
  for(const [family] of norcFamilies){
    const model=withComparability();
    model.comparison_policy.input_source_counts_revised_from_previous_release=true;
    model.endpoint_update={native_source_counts_revised_from_previous_release:true,
      source_count_repairs:0,source_model_refitted:false,survey_weights_changed:false,changed_states:["HI","WY"]};
    for(const row of model.rows.filter(row=>["HI","WY"].includes(row.state_code)))
      row.reported_comparison.current_native_clock=null;
    data.families[family]=model;
  }
  data.comparison_policy=data.families.accepted_ridge_multinomial.comparison_policy;
  return data;
};

test("official source receipts require the pinned review, unchanged fits, and absent native clocks",async()=>{
  const {loadNorcHouse}=await import("../public/scripts/participation-norc-house.js?official-revision-loader");
  const original=globalThis.fetch;
  try{
    for(const mutate of [
      null,
      data=>{delete data.official_source_revisions;},
      data=>{data.official_source_revisions[0].query_pin.sha256="a".repeat(64);},
      data=>{data.families.accepted_ridge_multinomial.endpoint_update.source_model_refitted=true;},
      data=>{data.families.accepted_ridge_multinomial.endpoint_update.source_count_repairs=1;},
      data=>{data.families.accepted_ridge_multinomial.rows.find(row=>row.state_code==="HI")
        .reported_comparison.current_native_clock="2026-11-12T23:06:26Z";},
    ]){
      const data=officialRevision();mutate?.(data);
      const body=Buffer.from(JSON.stringify(data));
      const receipt={url:"https://raw.githubusercontent.com/hanshanley/voter-participation/"+"e".repeat(40)
        +"/data/house-official-source-update/20261113-01/viewer-original.json",
        bytes:body.length,sha256:createHash("sha256").update(body).digest("hex")};
      globalThis.fetch=async()=>new Response(body);
      if(mutate)await assert.rejects(loadNorcHouse(receipt));
      else assert.equal((await loadNorcHouse(receipt)).official_source_revisions.length,2);
    }
  }finally{globalThis.fetch=original;}
});

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
    assert.equal(norcMapValue(row,"modeled_nonparticipation"),row.source_comparison_available
      ?row.point.contributions_pp.entry+row.point.contributions_pp.exit:null);
    for (const [key] of norcTerms) assert.equal(norcMapValue(row,key),row.source_comparison_available
      ?row.point.contributions_pp[key]:null);
  }
});

const scores=JSON.parse(readFileSync("data/participation-return-attribution/20261112-03/family-summary.json"));
const comparison=()=>({contract:"participation.house_model_families.v1",
  no_independent_behavioral_identification:true,family_spread_is_not_confidence_interval:true,
  preferred_family:scores.summary.preferred_family,family_labels:scores.family_labels,
  source_validation:structuredClone(scores.source_validation),
  families:Object.fromEntries(norcFamilies.map(([family])=>[family,fresh()]))});

const association=(profile="full")=>{
  const data=comparison(),theta=profile==="full"?8:Math.sqrt(8);
  data.association_profile={profile,requested_theta:theta,source_primary_history_theta_median:8,
    historical_parameter_not_validated_for2026:true,applied_postaggregation_not_per_case:true,
    demographic_partition_year_margins_preserved:true,source_only_feasibility_backoff:true,
    default_accepted_model_changed:false};
  for(const model of Object.values(data.families)) model.historical_association_stress={
    profile,default_accepted_model_changed:false,unvalidated_source_cycle_predictor_and_aggregation_transport:true,
    current_return_targets_used_to_select_association:false,fitted_source_state_and_group_year_marginals_preserved:true,
    state_parameters:Object.fromEntries(model.rows.map(row=>[row.state_code,{
      requested_theta:theta,effective_theta:Math.sqrt(theta),feasibility_exponent:.5,maximum_constraint_error:1e-12}]))};
  return data;
};

test("association stresses preserve qualifications, applied strength and accepted comparison",()=>{
  assert.equal(validateNorcAssociation(association(),comparison()).association_profile.profile,"full");
  for(const mutate of [
    d=>{d.association_profile.historical_parameter_not_validated_for2026=false;},
    d=>{d.association_profile.applied_postaggregation_not_per_case=false;},
    d=>{d.association_profile.demographic_partition_year_margins_preserved=false;},
    d=>{d.association_profile.default_accepted_model_changed=true;},
    d=>{d.association_profile.source_primary_history_theta_median=4;},
    d=>{d.families.accepted_ridge_multinomial.historical_association_stress.current_return_targets_used_to_select_association=true;},
    d=>{d.families.accepted_ridge_multinomial.historical_association_stress.state_parameters.TX.effective_theta=8;},
    d=>{d.families.accepted_ridge_multinomial.historical_association_stress.state_parameters.TX.maximum_constraint_error=-1;},
    d=>{for(const m of Object.values(d.families)) m.rows[0].reported_comparison.qualification="different scope";},
  ]){
    const data=association();mutate(data);assert.throws(()=>validateNorcAssociation(data,comparison()));
  }
});

test("shared profile bounds cover all families, halve signed units and exclude retention",()=>{
  const data=comparison();
  for(const group of ["",...norcGroups(source).map(g=>g.value)]){
    assert.equal(norcSharedBound(data,group,"margin",120),120);
    assert.equal(norcSharedBound(data,group,"democratic_two_party_share",120),60);
  }
  assert.throws(()=>norcSharedBound(data,"","margin",0),/omits/);
});

test("reported totals remain in demographic scales even when that state's group is withheld",()=>{
  const data=comparison();
  const row=data.families.accepted_ridge_multinomial.rows.find(row=>row.source_comparison_available);
  for(const model of Object.values(data.families)){
    const state=model.rows.find(value=>value.state_code===row.state_code);
    state.reported_comparison.reported_change_pp=200;
    state.groups.find(group=>group.dimension==="AGE6" && group.group==="65_plus").available=false;
  }
  assert.throws(()=>norcSharedBound(data,"AGE6|65_plus","margin",100),/omits/);
  assert.equal(norcSharedBound(data,"AGE6|65_plus","margin",200),200);
});

test("flipping pinned profiles reuses each checksum cache; failed and mismatched profiles never substitute",async()=>{
  const {loadNorcHouse}=await import("../public/scripts/participation-norc-house.js?association-loader-test");
  const records=new Map();
  for(const key of ["original","attenuated","full"]){
    const bytes=Buffer.from(JSON.stringify(key==="original"?comparison():association(key)));
    const url="https://raw.githubusercontent.com/hanshanley/voter-participation/"+"b".repeat(40)
      +`/data/${key==="original"?"house-model-families/20261112-01/viewer-data":"house-fixed-copula/20261112-01/viewer-"+key}.json`;
    records.set(key,{bytes,receipt:{url,bytes:bytes.length,sha256:createHash("sha256").update(bytes).digest("hex")}});
  }
  const original=globalThis.fetch,counts=new Map();
  try{
    globalThis.fetch=async url=>{
      counts.set(url,(counts.get(url)||0)+1);
      const {bytes}=Array.from(records.values()).find(v=>v.receipt.url===url);
      return new Response(url===records.get("full").receipt.url && counts.get(url)===1
        ? Buffer.concat([bytes,Buffer.from(" ")]) : bytes);
    };
    const base=records.get("original").receipt;
    await Promise.all([loadNorcHouse(base),loadNorcHouse(base)]);
    for(const key of ["attenuated","original","attenuated"]) await loadNorcHouse(records.get(key).receipt);
    await assert.rejects(loadNorcHouse(records.get("full").receipt),/checksum/);
    await loadNorcHouse(records.get("full").receipt);
    assert.deepEqual([...counts.values()],[1,1,2]);
    const {bytes,receipt}=records.get("full");
    const wrong={...receipt,url:receipt.url.replace("b".repeat(40),"c".repeat(40)).replace("viewer-full","viewer-attenuated")};
    globalThis.fetch=async()=>new Response(bytes);
    await assert.rejects(loadNorcHouse(wrong),/profile differ/);
  }finally{globalThis.fetch=original;}
});

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
    if (!row.source_comparison_available) {
      for (const view of ["reported_total","retaining","modeled_nonparticipation",...norcTerms.map(([key])=>key)])
        assert.equal(norcMapValue(row,view),null);
      missing++;
    }
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

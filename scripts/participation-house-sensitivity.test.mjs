import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {gzipSync} from "node:zlib";
import {norcAssociations, norcFamilies, norcEstimate, renderNorcSelection,
  roundedNorcSensitivityRange} from "../public/scripts/participation-norc-house.js";
import {validateHouseSensitivity, houseSensitivityScope, loadHouseSensitivity} from "../public/scripts/participation-house-sensitivity.js";

const model=JSON.parse(readFileSync("data/participation-return-attribution/20261112-02/norc-test-oracle.json"));
const sources=Object.fromEntries(norcAssociations.map(([key])=>[key,{url:"fixture:"+key,bytes:1,sha256:"a".repeat(64)}]));
const fixture=()=>{
  const rows=model.rows.map(row=>{
    const scopes={};
    for (const key of ["",...row.groups.map(g=>g.dimension+"|"+g.group)]) {
      const value=norcEstimate(row,key),available=Boolean(row.source_comparison_available && value);
      const values=available?{...value.contributions_pp,modeled_nonparticipation:value.net_participation_pp,
        total:value.total_contribution_pp,retaining:value.gross_outcomes?.retaining}:{};
      scopes[key]={available,metrics:Object.fromEntries(["switching","exit","entry","modeled_nonparticipation",
        "other_choice","unresolved","total","retaining"].map(metric=>{
        const v=values[metric];
        return [metric,typeof v==="number"?{minimum:metric==="retaining"?Math.max(0,v-.01):v-1,
          maximum:metric==="retaining"?Math.min(1,v+.01):v+1,default:v,variants:9}:null];
      }))};
    }
    return {state_code:row.state_code,qualified:row.source_comparison_available,
      endpoint:{snapshot:row.reported_comparison.current_snapshot??null,native_clock:row.reported_comparison.current_native_clock??null},
      scopes};
  });
  const qualified=rows.filter(r=>r.qualified).length;
  return {contract:"participation.house_model_sensitivity.v1",variant_count:9,confidence_intervals:null,
    source_fits_reproduced:false,fitted_aggregate_projection_replay_only:true,new_models_or_weights_or_source_counts:false,
    not_all_model_survey_transport_or_endpoint_uncertainty:true,group_ranges_are_not_group_vote_shares:true,
    contribution_units:"statewide_D_minus_R_margin_percentage_points",
    retaining_units:"fraction_of_model_assigned_prior_DR_mass",default_variant:"original|accepted_ridge_multinomial",
    profiles:norcAssociations.map(([key])=>key),families:norcFamilies.map(([key])=>key),source_pins:sources,
    summary:{states:50,qualified_states:qualified,held_states:50-qualified,
      group_decisions:rows.reduce((n,r)=>n+Object.keys(r.scopes).length-1,0),
      supported_group_decisions:rows.reduce((n,r)=>n+Object.entries(r.scopes).filter(([k,s])=>k && s.available).length,0)},
    rows};
};

test("sensitivity keeps exact state/group identity and rejects source, endpoint and disclosure changes",()=>{
  const data=validateHouseSensitivity(fixture(),sources);
  const row=model.rows.find(r=>r.source_comparison_available);
  const group=row.groups.find(g=>g.available);
  assert.equal(houseSensitivityScope(data,row),data.rows.find(r=>r.state_code===row.state_code).scopes[""]);
  const key=group.dimension+"|"+group.group;
  assert.equal(houseSensitivityScope(data,row,key),data.rows.find(r=>r.state_code===row.state_code).scopes[key]);
  assert.throws(()=>validateHouseSensitivity(fixture(),{...sources,original:{...sources.original,sha256:"b".repeat(64)}}));
  assert.throws(()=>houseSensitivityScope(data,{...row,reported_comparison:{...row.reported_comparison,current_snapshot:"other"}}));
  assert.throws(()=>houseSensitivityScope(data,row,"AGE6|not-a-source-group"));
  const held=fixture(),scope=held.rows[0].scopes[""];
  scope.available=false;scope.metrics.switching={minimum:0,maximum:1,default:0,variants:9};
  assert.throws(()=>validateHouseSensitivity(held,sources));
  const omitted=fixture();
  omitted.rows.find(r=>r.state_code===row.state_code).scopes[""].metrics.switching.maximum=-1000;
  assert.throws(()=>houseSensitivityScope(omitted,row));
});

test("compressed checksum cache retries failures and cannot substitute other source pins",async()=>{
  const data=fixture(),decoded=Buffer.from(JSON.stringify(data)),bytes=gzipSync(decoded);
  const receipt={url:"https://raw.githubusercontent.com/hanshanley/voter-participation/"+"d".repeat(40)
    +"/data/house-model-disclosures/test-01/sensitivity.json.gz",compression:"gzip",bytes:bytes.length,
    sha256:createHash("sha256").update(bytes).digest("hex"),decoded_bytes:decoded.length,
    decoded_sha256:createHash("sha256").update(decoded).digest("hex")};
  const original=globalThis.fetch;
  let requests=0;
  try {
    globalThis.fetch=async()=>{requests++;return new Response(requests===1?Buffer.from("bad"):bytes);};
    await assert.rejects(loadHouseSensitivity(receipt,sources),/checksum/);
    await loadHouseSensitivity(receipt,sources);
    await loadHouseSensitivity(receipt,sources);
    assert.equal(requests,2);
    await assert.rejects(loadHouseSensitivity(receipt,{...sources,full:{...sources.full,bytes:2}}),/source versions/);
    assert.equal(requests,3);
  } finally {globalThis.fetch=original;}
});

class Node {
  dataset={};children=[];hidden=true;
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
  addEventListener(){}
}
const descendants=node=>[node,...node.children.flatMap(descendants)];
const texts=node=>descendants(node).map(n=>n.textContent||"").join("\n");
test("range display rounds outward without halving retention or moving exact numerical endpoints",()=>{
  const range={minimum:-.09152224545848667,maximum:7.046114715265968};
  assert.deepEqual(roundedNorcSensitivityRange(range,"switching","democratic_two_party_share"),
    {minimum:-.05,maximum:3.53});
  assert.deepEqual(roundedNorcSensitivityRange({minimum:.80123,maximum:.81912},"retaining","democratic_two_party_share"),
    {minimum:80.1,maximum:82});
  assert.deepEqual(roundedNorcSensitivityRange({minimum:1.096,maximum:2.86},"modeled_nonparticipation"),
    {minimum:1.08,maximum:2.87});
  assert.deepEqual(range,{minimum:-.09152224545848667,maximum:7.046114715265968});
  assert.equal(roundedNorcSensitivityRange(null,"switching"),null);
});

test("selected points retain units beside same-group ranges, exact versions and non-predictive total labels",()=>{
  const previous=globalThis.document;globalThis.document={createElement:()=>new Node()};
  try {
    const row=structuredClone(model.rows.find(r=>r.source_comparison_available));
    row.reported_comparison.current_snapshot="native-query:"+"e".repeat(64);
    const scope=houseSensitivityScope(fixture(),model.rows.find(r=>r.state_code===row.state_code));
    for (const units of ["margin","democratic_two_party_share"]) {
      const summary=new Node(),detail=new Node();
      renderNorcSelection(row,"","Example",summary,detail,{units,sensitivityScope:scope});
      const nodes=descendants(summary),metric=key=>nodes.find(n=>n.dataset.norcMechanism===key);
      const range=key=>nodes.find(n=>n.dataset.norcSensitivityMetric===key);
      assert.equal(metric("retaining").textContent,`${(100*row.gross_outcomes.retaining).toFixed(1)}%`);
      assert.ok(range("retaining").textContent.includes("%"));
      assert.ok(texts(summary).includes(row.reported_comparison.current_snapshot));
      assert.ok(texts(summary).includes("by construction, not predictive accuracy"));
      assert.ok(texts(summary).includes("not a confidence interval"));
      const expected=row.point.total_change_pp*(units==="margin"?1:.5);
      assert.equal(metric("total").textContent,`${expected>0?"+":""}${expected.toFixed(2)} pp`);
    }
    row.gross_outcomes.retaining=null;
    const summary=new Node(),detail=new Node();
    renderNorcSelection(row,"","Example",summary,detail,{sensitivityState:"failed",onSensitivityRetry:()=>{}});
    assert.equal(descendants(summary).find(n=>n.dataset.norcMechanism==="retaining").textContent,"Unavailable");
    assert.ok(texts(summary).includes("Retry sensitivity ranges"));
    assert.ok(texts(summary).includes("point estimates are unchanged"));
  } finally {globalThis.document=previous;}
});

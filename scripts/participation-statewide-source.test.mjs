import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";
import test from "node:test";
import { automaticStatewideSourceReceipt } from "../public/scripts/participation-automatic-runtime.js";
import { norcFamilies, norcAssociations } from "../public/scripts/participation-norc-house.js";
import { validateStatewideIndex, validateStatewideProfile, sourceMetric, sourceMetricScale,
  fetchSourceBody } from "../public/scripts/participation-statewide-source.js";

const states="AK AL AR AZ CA CO CT DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY".split(" ").sort();
const metrics=["switching","exit","entry","other_choice","unresolved","net_participation","total_change","retaining"];
const digest=body=>createHash("sha256").update(body).digest("hex");
const base="https://raw.githubusercontent.com/hanshanley/voter-participation/"+"a".repeat(40)+"/fixture/";
function receipt(value) {
  const decoded=Buffer.from(JSON.stringify(value)),body=gzipSync(decoded);
  return {body,url:base+"house/statewide-source/index.json.gz",path:"house/statewide-source/index.json.gz",
    compression:"gzip",media_type:"application/json",bytes:body.length,sha256:digest(body),
    decoded_bytes:decoded.length,decoded_sha256:digest(decoded)};
}
function fixture() {
  const metadata={method:"uniform_source_frame_house24_bridge_to_house26_v1",version:"c".repeat(64),states:50,
    profiles:norcAssociations.map(([key])=>key),families:norcFamilies.map(([key])=>key),
    default_family:norcFamilies[0][0],default_profile:"original",return_conditioned:false,population_calibrated:false,
    previous_partisan_return_constraints_used:false,current_partisan_return_constraints_used:false,
    source_weight_calibration_independent_of_returns_qualified:false,source_models_refitted:false,model_units_are_people:false,
    estimated_baseline_not_actual_2024_house_counts:true,nonmajor_choices_remain_other:true,unresolved_response_is_not_nonvote:true,
    synthetic_flow_table_is_not_linked_histories:true,measured_staying_home:null,actual_first_ever_voting:null,
    confidence_intervals:null,local_allocation:false,interview_dates:null,source_fit_date:null,
    input_years:{ap2024:2024,chep:2026},source_input_sha256:{ap2024:"1".repeat(64),chep:"2".repeat(64)},
    sensitivity:{variants:27,confidence_interval:false,complete_sampling_or_transport_uncertainty:false}};
  const joint=[[.3,.05,0,.05,0],[.1,.25,0,.05,0],[0,0,0,0,0],[.1,.05,0,.05,0],[0,0,0,0,0]];
  const point={previous_margin_pp:0,current_margin_pp:300/17,total_change_pp:300/17,allocated_change_pp:300/17,
    net_participation_pp:375/68,contributions_pp:{switching:825/68,exit:75/68,entry:75/17,other_choice:0,unresolved:0}};
  const gross_outcomes={retaining:11/16};
  const row={available:true,joint,point,gross_outcomes};
  row.sensitivity=Object.fromEntries(metrics.map(key=>{const value=sourceMetric(row,key);return[key,{minimum:value,maximum:value}];}));
  const held={dimension:"AGE6",group:"hidden",label:"Withheld synthetic cell",available:false,joint:null,
    point:null,gross_outcomes:null,sensitivity:Object.fromEntries(metrics.map(key=>[key,null]))};
  row.groups=[{...structuredClone(row),dimension:"AGE6",group:"all",label:"Synthetic all-source group"},held];
  const profile={contract:"participation.statewide_source_model.v1",profile:"original",metadata,
    models:Object.fromEntries(metadata.families.map(key=>[key,{rows:states.map(state_code=>({...structuredClone(row),state_code}))}]))};
  const index={contract:"participation.statewide_source_index.v1",metadata,
    profiles:Object.fromEntries(metadata.profiles.map(key=>[key,{...receipt({}),path:`house/statewide-source/${key}.json.gz`}]))};
  return {index,profile};
}

test("one unconditioned method supplies all 50 states independently of old return holds",()=>{
  const {index,profile}=fixture();validateStatewideIndex(index);validateStatewideProfile(profile,index,"original");
  for(const model of Object.values(profile.models)) for(const row of model.rows) {
    row.source_comparison_available=false;row.reported_comparison={status:"unavailable"};
    assert.ok(Number.isFinite(sourceMetric(row,"total_change")));assert.equal(sourceMetric(row,"other_choice"),0);
    assert.equal(sourceMetric(row,"total_change","AGE6|hidden"),null);
  }
  const missing=structuredClone(profile);Object.values(missing.models)[0].rows.pop();
  assert.throws(()=>validateStatewideProfile(missing,index,"original"),/50/);
  assert.equal(sourceMetric(null,"total_change"),null);
});

test("a genuine zero source partition is zero contribution but has no retention denominator",()=>{
  const {index,profile}=fixture();
  for(const model of Object.values(profile.models)) for(const row of model.rows) {
    row.groups.push({dimension:"AGE6",group:"zero",label:"Synthetic zero partition",available:true,
      joint:Array.from({length:5},()=>Array(5).fill(0)),gross_outcomes:null,
      point:{contributions_pp:Object.fromEntries(["switching","exit","entry","other_choice","unresolved"].map(key=>[key,0])),
        allocated_change_pp:0,net_participation_pp:0},
      sensitivity:Object.fromEntries(metrics.map(key=>[key,key==="retaining"?null:{minimum:0,maximum:0}]))});
    assert.equal(sourceMetric(row,"total_change","AGE6|zero"),0);
    assert.equal(sourceMetric(row,"retaining","AGE6|zero"),null);
  }
  validateStatewideProfile(profile,index,"original");
});

test("source qualifications, endpoint accounting and complementary masks cannot be promoted",()=>{
  for(const key of ["return_conditioned","population_calibrated","source_models_refitted","model_units_are_people",
    "previous_partisan_return_constraints_used","current_partisan_return_constraints_used","local_allocation",
    "source_weight_calibration_independent_of_returns_qualified"]) {
    const {index}=fixture();index.metadata[key]=true;assert.throws(()=>validateStatewideIndex(index),/source-only/);
  }
  for(const mutate of [
    value=>value.metadata.version="f".repeat(64),
    value=>Object.values(value.models)[0].rows[0].point.current_margin_pp++,
    value=>Object.values(value.models)[0].rows[0].point.contributions_pp.switching++,
    value=>Object.values(value.models)[0].rows[0].groups[1].point={allocated_change_pp:0},
    value=>Object.values(value.models)[0].rows[0].sensitivity.total_change.maximum=0,
    value=>Object.values(value.models)[1].rows[0].groups[0].label="Different disclosure identity",
    value=>Object.values(value.models)[0].rows[0].joint[0][0]=NaN,
    value=>{const row=Object.values(value.models)[0].rows[0];row.gross_outcomes.retaining=.9;
      row.sensitivity.retaining={minimum:.9,maximum:.9};},
  ]) {const {index,profile}=fixture();const bad=structuredClone(profile);mutate(bad);
    assert.throws(()=>validateStatewideProfile(bad,index,"original"));}
});

test("D-share changes halve margins but retention retains its own denominator",()=>{
  const {profile}=fixture(),row=Object.values(profile.models)[0].rows[0];
  assert.equal(sourceMetric(row,"retaining")*sourceMetricScale("retaining","margin"),68.75);
  assert.equal(sourceMetric(row,"retaining")*sourceMetricScale("retaining","democratic_two_party_share"),68.75);
  assert.equal(sourceMetricScale("switching","democratic_two_party_share"),.5);
  assert.equal(sourceMetricScale("switching","margin"),1);
  assert.throws(()=>sourceMetricScale("switching","percent"),/units/);
});

test("browser fetch verifies both hashes, sizes and immutable project ownership",async()=>{
  const value={synthetic_test:true},pin=receipt(value),fetcher=async()=>new Response(pin.body);
  assert.deepEqual(await fetchSourceBody(pin,fetcher),value);
  for(const changed of [{sha256:"0".repeat(64)},{decoded_sha256:"0".repeat(64)},
    {bytes:pin.bytes+1},{decoded_bytes:pin.decoded_bytes+1},{url:base.replace("a".repeat(40),"main")},
    {url:base.replace("hanshanley","someone-else")}])
    await assert.rejects(fetchSourceBody({...pin,...changed},fetcher));
  await assert.rejects(fetchSourceBody(pin,async()=>new Response("denied",{status:403})),/403/);
});

test("optional automatic source pointer fails independently and must bind to the same runtime",()=>{
  const pin=receipt({}),version="d".repeat(64),base_url=`https://raw.githubusercontent.com/hanshanley/margin_of_error/${"a".repeat(40)}/automatic/versions/${version}/`;
  const source={...pin,contract:"participation.statewide_source_index.v1",version:"c".repeat(64),url:base_url+pin.path};
  const manifest={version,house_sources:{base_url,statewide_source_models:source}};
  assert.equal(automaticStatewideSourceReceipt(manifest),source);
  assert.equal(automaticStatewideSourceReceipt({house_sources:{}}),null);
  for(const change of [{contract:"old"},{version:"unknown"},{path:"other.json.gz"},{url:source.url.replace(version,"e".repeat(64))}]) {
    const bad=structuredClone(manifest);Object.assign(bad.house_sources.statewide_source_models,change);
    const before=structuredClone(bad);assert.throws(()=>automaticStatewideSourceReceipt(bad));assert.deepEqual(bad,before);
  }
});

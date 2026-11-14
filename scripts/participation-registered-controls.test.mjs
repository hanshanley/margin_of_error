import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validateAutomaticRegisteredControls } from
  "../public/scripts/participation-registered-controls.js";

const accepted=JSON.parse(readFileSync(
  "data/participation-registered-controls/20261114-35/display-model.json"));

function fixture() {
  const data=structuredClone(accepted);
  data.automatic_update={
    contract:"participation.automatic_registered_control_update.v1",
    base_native_control_version:35,accepted_state_decisions_retained:51,
    accepted_scenarios_retained:34,fresh_compatible_scenarios:1,
    changed_registered_frames:1,fresh_jurisdictions:["OR"],
    new_scenarios_created:0,source_weights_probabilities_or_fits_changed:false,
    frame_exchangeability_or_observed_staying_home_qualified:false,
    native_outcome_fitting_applied:false,unsupported_local_or_demographic_estimates_created:false,
    coverage_claim:"Only explicitly listed compatible frames changed.",
    decisions:[{
      state_code:"OR",control_id:"reporting-OR",
      previous_registered_denominator:"3109123",current_registered_denominator:"3109133",
      registered_denominator_difference:"10",
      conditional_modeled_voter_unit_difference:"6.700752995209252457750266407",
      conditional_modeled_nonvoter_unit_difference:"3.299247004790747542249733593",
      native_clock:null,native_clock_supplied:false,
      source_weights_probabilities_and_fits_unchanged:true,
      native_outcome_fitting_applied:false,local_or_demographic_estimate:false,
      frame_exchangeability_or_observed_staying_home_qualified:false,
    }],
  };
  const scenario=data.scenarios.find(row=>row.control_id==="reporting-OR");
  scenario.native_registered_denominator="3109133";
  scenario.conditional_modeled_voter_count=
    "2083353.226225392872172245904417727434009097671801690689929620984192418584893296964730697370287376858";
  scenario.conditional_modeled_nonvoter_count=
    "1025779.773774607127827754095582272565990902328198309310070379015807581415106703035269302629712623142";
  scenario.source_time_label=null;
  data.states.find(row=>row.state_code==="OR").control_registered_denominator="3109133";
  return data;
}

function baselines() {
  const scenarioRows=new Map(accepted.scenarios.map(row=>[row.control_id,{baseline:{
    state:row.state_code,basis:row.native_denominator_basis,civicN:row.civic_source_n,
    sourceUrl:row.source_url,values:[row.native_registered_denominator,
      row.conditional_modeled_voter_count,row.conditional_modeled_nonvoter_count,
      row.source_time_label||""],
  }}]));
  return {scenarioRows,stateRows:new Map(accepted.states.map(row=>[row.state_code,{}]))};
}

test("changed registered frame updates one existing scenario and preserves every accepted identity",()=>{
  const data=fixture(),{scenarioRows,stateRows}=baselines();
  const value=validateAutomaticRegisteredControls(data,scenarioRows,stateRows);
  assert.deepEqual([...value.fresh],["OR"]);
  assert.equal(value.scenarios.size,34);
  assert.equal(value.states.size,51);
  assert.equal(value.scenarios.get("reporting-OR").source_time_label,null);
  assert.equal(value.scenarios.get("reporting-OR").native_registered_denominator,"3109133");
  assert.equal(value.scenarios.get("reporting-AL").native_registered_denominator,
    accepted.scenarios.find(row=>row.control_id==="reporting-AL").native_registered_denominator);
});

test("missing, unlisted, relabeled and model-changing automatic values fail closed",()=>{
  for(const mutate of [
    data=>data.scenarios.pop(),
    data=>{data.scenarios.find(row=>row.control_id==="reporting-AL")
      .native_registered_denominator="3852948";},
    data=>{data.scenarios.find(row=>row.control_id==="reporting-OR")
      .native_denominator_basis="different";},
    data=>{data.automatic_update.source_weights_probabilities_or_fits_changed=true;},
    data=>{data.automatic_update.fresh_jurisdictions=[];},
  ]){
    const data=fixture(),{scenarioRows,stateRows}=baselines();mutate(data);
    assert.throws(()=>validateAutomaticRegisteredControls(data,scenarioRows,stateRows));
  }
});

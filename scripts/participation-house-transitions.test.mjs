import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {validateHouseTransitions,roundedTransitionContributions,transitionReceipt} from '../public/scripts/participation-house-transitions.js';

const data=JSON.parse(readFileSync('data/participation-house-transition-model/20261127-01/viewer-data.json'));

test('all 50 states retain whole-state targets, including the 17 old comparison holds',()=>{
  validateHouseTransitions(data);
  assert.equal(data.rows.length,50);
  assert.equal(data.rows.filter(row=>row.context_holds.length>0).length,17);
  for(const row of data.rows){
    assert.equal(row.available,true);
    assert.ok(Number.isFinite(row.point.gross_pct.switching));
    assert.ok(Number.isFinite(row.point.gross_pct.no_ballot));
    for(const units of ['margin','democratic_two_party_share']){
      const rounded=roundedTransitionContributions(row.point,units),factor=units==='margin'?2:1;
      assert.equal(Math.round(Object.values(rounded).reduce((a,b)=>a+b,0)*100),
        Math.round(Number((row.point.recorded_change_pp*factor).toFixed(2))*100));
    }
  }
});

test('missing states, no-House-choice/nonvoting conflation and validated-history claims fail closed',()=>{
  for(const mutate of [
    value=>value.rows.pop(),
    value=>{value.rows[1]=value.rows[0];},
    value=>{value.rows[0].point.columns[3]++;},
    value=>{value.rows[0].point.gross_pct.no_ballot++;},
    value=>{value.identified_individual_histories=true;},
    value=>{value.confidence_intervals=[0,1];},
    value=>{value.quick_development_preview=true;},
  ]){const changed=structuredClone(data);mutate(changed);assert.throws(()=>validateHouseTransitions(changed));}
});

test('optional automatic transitions bind independently to both House and turnout snapshots',()=>{
  assert.equal(transitionReceipt({house_sources:{}}),null);
  const base='https://raw.githubusercontent.com/hanshanley/margin_of_error/'+'a'.repeat(40)+'/automatic/versions/'+'b'.repeat(64)+'/';
  const value={contract:data.contract,states:50,path:'house/statewide-transitions/viewer.json.gz',
    url:base+'house/statewide-transitions/viewer.json.gz',house_results_sha256:'c'.repeat(64),count_snapshot_sha256:'d'.repeat(64),source_models_refitted:false,legacy_behavioral_gates_changed:false};
  const manifest={house_sources:{base_url:base,statewide_house_transitions:value},congressional:{sha256:'c'.repeat(64)},counts:{files:{'current.json.gz':{sha256:'d'.repeat(64)}}}};
  assert.equal(transitionReceipt(manifest),value);
  for(const mutate of [
    m=>{m.congressional.sha256='e'.repeat(64);},
    m=>{m.counts.files['current.json.gz'].sha256='e'.repeat(64);},
    m=>{m.house_sources.statewide_house_transitions.url=base+'wrong.json.gz';},
    m=>{m.house_sources.statewide_house_transitions.legacy_behavioral_gates_changed=true;},
  ]){const changed=structuredClone(manifest);mutate(changed);assert.throws(()=>transitionReceipt(changed));}
});

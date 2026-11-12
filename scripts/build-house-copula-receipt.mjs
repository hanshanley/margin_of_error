import {readFileSync,writeFileSync,mkdirSync,existsSync} from "node:fs";
import {dirname,join} from "node:path";
import {createHash} from "node:crypto";
import {validateNorcFamilies,validateNorcAssociation,norcGroups,norcViews,norcMapValue}
  from "../public/scripts/participation-norc-house.js";

const args=Object.fromEntries(Array.from({length:(process.argv.length-2)/2},(_,i)=>
  [process.argv[2+i*2].replace(/^--/,""),process.argv[3+i*2]]));
if(!/^[a-f0-9]{40}$/.test(args["source-commit"]) || !args.dataset || !args.baseline || !args.science || !args.output)
  throw new Error("Provide exact source commit, verified datasets, complete science and fresh output");
if(existsSync(args.output)) throw new Error("Use a fresh versioned receipt");
const pin=bytes=>({bytes:bytes.length,sha256:createHash("sha256").update(bytes).digest("hex")});
const original=validateNorcFamilies(JSON.parse(readFileSync(args.baseline)));
const profiles={},datasets=[original];
for(const profile of ["attenuated","full"]){
  const bytes=readFileSync(join(args.dataset,`viewer-${profile}.json`));
  datasets.push(validateNorcAssociation(JSON.parse(bytes),original));
  profiles[profile]={...pin(bytes),source_commit:args["source-commit"],
    url:`https://raw.githubusercontent.com/hanshanley/voter-participation/${args["source-commit"]}/data/house-fixed-copula/20261112-01/viewer-${profile}.json`};
}
const models=datasets.flatMap(data=>Object.values(data.families));
const groups=new Set(["",...models.flatMap(model=>norcGroups(model).map(group=>group.value))]);
const shared_max_abs_margin={};
for(const group of groups){
  let maximum=0;
  for(const model of models) for(const row of model.rows) for(const [key] of norcViews){
    if(key==="retaining") continue;
    const value=norcMapValue(row,key,group,"margin");
    if(value!==null) maximum=Math.max(maximum,Math.abs(value));
  }
  shared_max_abs_margin[group]=maximum;
}
const summary=JSON.parse(readFileSync(join(args.dataset,"outputs/summary.json")));
if(!summary.conditional_transport_gate_passed || summary.population_or2026_parameter_validation
  || summary.default_accepted_model_changed) throw new Error("Unqualified historical transport gate");
const score=(level,kind,metric)=>{
  const value=Number(summary.primary_scores.find(r=>r.level===level&&r.kind===kind&&r.metric===metric).value);
  if(!Number.isFinite(value)||value<0) throw new Error("Invalid source validation score");
  return value;
};
const source_validation=["history","demographic"].map(level=>({
  label:level==="history"?"2020 vote history":"2020 history + age / education / state",
  baseline_logloss:score(level,"baseline","House_logloss"),calibrated_logloss:score(level,"calibrated","House_logloss"),
  baseline_Brier:score(level,"baseline","House_Brier"),calibrated_Brier:score(level,"calibrated","House_Brier")}));
const result={contract:"participation.house_copula_receipt.v1",profiles,shared_max_abs_margin,source_validation,
  complete_science_url:"https://github.com/hanshanley/margin_of_error/releases/download/participation-house-fixed-copula-20261112-01/complete-analysis.zip",
  complete_science:pin(readFileSync(args.science)),
  state_margin_MAE_pp:Object.fromEntries(datasets.map((data,i)=>[
    ["original","attenuated","full"][i],data.summary.margin_MAE_pp])),
  source_history_theta_median:summary.source_primary_history_theta_median,
  historical_transport_validated:false,default_accepted_model_changed:false};
mkdirSync(dirname(args.output),{recursive:true});
writeFileSync(args.output,JSON.stringify(result,null,2)+"\n");
console.log(JSON.stringify({status:"all_actual_profile_envelopes_validated",groups:groups.size,profiles}));

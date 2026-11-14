import { loadAutomaticRegisteredControlDisplay, rejectAutomaticRuntime,
  setAutomaticRuntimeStatus } from "./participation-automatic-runtime.js";

const integer=value=>typeof value==="string" && /^\d+$/.test(value) && Number.isSafeInteger(Number(value));
const finite=value=>typeof value==="string" && Number.isFinite(Number(value));
const count=value=>Number(value).toLocaleString("en-US",{maximumFractionDigits:0});
const signed=value=>Number(value).toLocaleString("en-US",{maximumFractionDigits:3,signDisplay:"always"});

export function validateAutomaticRegisteredControls(data,scenarioRows,stateRows) {
  const update=data.automatic_update;
  if (update?.contract!=="participation.automatic_registered_control_update.v1"
      || update.base_native_control_version!==35
      || update.accepted_state_decisions_retained!==51
      || update.accepted_scenarios_retained!==34
      || update.new_scenarios_created!==0
      || update.source_weights_probabilities_or_fits_changed!==false
      || update.frame_exchangeability_or_observed_staying_home_qualified!==false
      || update.native_outcome_fitting_applied!==false
      || update.unsupported_local_or_demographic_estimates_created!==false
      || !Array.isArray(update.fresh_jurisdictions) || !Array.isArray(update.decisions)
      || new Set(update.fresh_jurisdictions).size!==update.fresh_jurisdictions.length)
    throw new Error("Automatic registered-control update policy differs");
  if (data.model_variant_or_study_probabilities_changed!==false
      || data.frame_exchangeability_or_observed_staying_home_qualified!==false
      || data.native_outcome_fitting_applied!==false)
    throw new Error("Automatic registered controls changed the accepted model");
  const states=new Map(data.states.map(row=>[row.state_code,row]));
  const scenarios=new Map(data.scenarios.map(row=>[row.control_id,row]));
  if (states.size!==51 || scenarios.size!==34
      || [...stateRows.keys()].some(code=>!states.has(code))
      || [...scenarioRows.keys()].some(id=>!scenarios.has(id)))
    throw new Error("Automatic registered-control identity inventory differs");
  const fresh=new Set(update.fresh_jurisdictions);
  const compatible=update.decisions.filter(row=>typeof row?.control_id==="string");
  if (update.fresh_compatible_scenarios!==compatible.length
      || update.changed_registered_frames!==compatible
        .filter(row=>Number(row.registered_denominator_difference)!==0).length)
    throw new Error("Automatic registered-control decision counts differ");
  for (const [id,{baseline}] of scenarioRows) {
    const row=scenarios.get(id);
    if (row.state_code!==baseline.state || row.native_denominator_basis!==baseline.basis
        || row.civic_source_n!==baseline.civicN || row.source_url!==baseline.sourceUrl
        || !integer(row.native_registered_denominator)
        || !finite(row.conditional_modeled_voter_count)
        || !finite(row.conditional_modeled_nonvoter_count)
        || Math.abs(Number(row.conditional_modeled_voter_count)
          +Number(row.conditional_modeled_nonvoter_count)
          -Number(row.native_registered_denominator))>1e-6)
      throw new Error("Automatic registered-control scenario scope differs");
    const expected=Number(baseline.values[1])*Number(row.native_registered_denominator)
      /Number(baseline.values[0]);
    if (!(Number(row.native_registered_denominator)>0)
        || !Number.isFinite(expected)
        || Math.abs(Number(row.conditional_modeled_voter_count)-expected)>1e-6)
      throw new Error("Registered-control scenario changed its frozen Civic probability");
  }
  for (const decision of update.decisions) {
    if (!decision.control_id) {
      if (!states.has(decision.state_code)
          || !["held_invalid_native_reference","held_registration_frame_check_failed",
            "held_ambiguous_registered_frame","native_registered_reference_only"]
            .includes(decision.decision))
        throw new Error("Unknown held native registered-control reference");
      continue;
    }
    const row=scenarios.get(decision.control_id);
    if (!row || row.state_code!==decision.state_code || !fresh.has(row.state_code)
        || decision.native_clock_supplied!==Boolean(decision.native_clock)
        || decision.source_weights_probabilities_and_fits_unchanged!==true
        || decision.native_outcome_fitting_applied!==false
        || decision.local_or_demographic_estimate!==false
        || decision.frame_exchangeability_or_observed_staying_home_qualified!==false)
      throw new Error("Automatic registered-control decision differs");
  }
  return {states,scenarios,update,fresh};
}

function renderChanges(host,update,names) {
  const paragraphs=update.decisions.map(decision=>{
    const p=document.createElement("p");
    p.className="caption";
    if (!decision.control_id) {
      p.dataset.nativeAutomaticReference=decision.state_code;
      p.textContent=`Native reference held · ${names[decision.state_code]||decision.state_code}: `
        +decision.decision.replaceAll("_"," ")
        +". No registered-control scenario or frozen Civic probability is changed by this reference.";
      return p;
    }
    p.dataset.nativeAutomaticDecision=decision.control_id;
    const time=decision.native_clock_supplied
      ?` Native clock: ${decision.native_clock}.`
      :" No native source clock was supplied; no prior or retrieval time is substituted.";
    p.textContent=`Automatic source refresh · ${names[decision.state_code]||decision.state_code}: `
      +`${Number(decision.previous_registered_denominator).toLocaleString("en-US")} → `
      +`${Number(decision.current_registered_denominator).toLocaleString("en-US")} registered source units. `
      +`Conditional modeled voter units ${signed(decision.conditional_modeled_voter_unit_difference)}; `
      +`modeled nonvoter units ${signed(decision.conditional_modeled_nonvoter_unit_difference)}.`
      +time+" Frozen Civic probabilities; not observed turnout or staying home.";
    return p;
  });
  if (!paragraphs.length) {
    const p=document.createElement("p");
    p.className="caption";
    p.textContent="No compatible registered source frame changed in this automatic snapshot.";
    paragraphs.push(p);
  }
  host.replaceChildren(...paragraphs);
}

export async function installAutomaticRegisteredControls() {
  const root=document.querySelector("[data-native-registered-controls]");
  if (!root) return;
  const token=String((Number(root.dataset.automaticGeneration)||0)+1);
  root.dataset.automaticGeneration=token;
  const status=root.querySelector("[data-native-automatic-status]");
  const scenarioRows=new Map([...root.querySelectorAll("[data-native-registered-scenario]")]
    .map(node=>[node.dataset.nativeRegisteredScenario,{node,baseline:{
      state:node.dataset.nativeState,basis:node.dataset.nativeBasis,
      civicN:node.dataset.nativeCivicN,sourceUrl:node.dataset.nativeSourceUrl,
      values:[node.dataset.nativeRegistered,node.dataset.nativeModeledVoter,
        node.dataset.nativeModeledNonvoter,node.dataset.nativeTime||""],
    }}]));
  const stateRows=new Map([...root.querySelectorAll("[data-native-registered-state]")]
    .map(node=>[node.dataset.nativeRegisteredState,node]));
  try {
    const {data,manifest}=await loadAutomaticRegisteredControlDisplay();
    if (root.dataset.automaticGeneration!==token) return;
    const validated=validateAutomaticRegisteredControls(data,scenarioRows,stateRows);
    for (const [id,{node}] of scenarioRows) {
      const row=validated.scenarios.get(id);
      const registered=node.querySelector("[data-native-registered]");
      const voter=node.querySelector("[data-native-modeled-voter]");
      const nonvoter=node.querySelector("[data-native-modeled-nonvoter]");
      const time=node.querySelector("[data-native-time]");
      registered.dataset.nativeRegistered=row.native_registered_denominator;
      registered.textContent=count(row.native_registered_denominator);
      voter.dataset.nativeModeledVoter=row.conditional_modeled_voter_count;
      voter.textContent=count(row.conditional_modeled_voter_count);
      nonvoter.dataset.nativeModeledNonvoter=row.conditional_modeled_nonvoter_count;
      nonvoter.textContent=count(row.conditional_modeled_nonvoter_count);
      time.textContent=row.source_time_label || "Native source clock not supplied";
      node.dataset.nativeFresh=String(validated.fresh.has(row.state_code));
    }
    const byState=new Map();
    for (const row of data.scenarios)
      byState.set(row.state_code,(byState.get(row.state_code)||0)+1);
    for (const [code,node] of stateRows) {
      const row=validated.states.get(code);
      node.querySelector("[data-native-state-registered]").textContent=
        row.control_registered_denominator?count(row.control_registered_denominator):"Not supplied";
      node.querySelector("[data-native-state-scenarios]").textContent=
        String(byState.get(code)||"No source-frame scenario");
      node.querySelector("[data-native-state-study-n]").textContent=row.civic_source_n||"Not sampled";
      node.dataset.nativeFresh=String(validated.fresh.has(code));
    }
    root.querySelector("[data-native-summary]").textContent=
      `Native registration frames: ${data.scenarios.length} conditional scenarios in `
      +`${new Set(data.scenarios.map(row=>row.state_code)).size} jurisdictions`;
    renderChanges(root.querySelector("[data-native-reference-changes]"),validated.update,
      JSON.parse(root.querySelector("[data-native-names]").textContent));
    const modelDownload=root.querySelector('[data-native-registered-download="model-zip"]');
    const countDownload=root.querySelector('[data-native-registered-download="count-zip"]');
    const automaticDownload=root.querySelector("[data-native-automatic-download]");
    if (automaticDownload) {
      automaticDownload.href=manifest.complete_download.url;
      automaticDownload.hidden=false;
    }
    if (modelDownload) modelDownload.href=manifest.complete_download.url;
    if (countDownload && manifest.counts?.complete_download?.url)
      countDownload.href=manifest.counts.complete_download.url;
    const publication=root.querySelector("[data-native-publication-status]");
    if (publication) {
      publication.dataset.nativePublicationStatus="automatic_verified";
      publication.textContent="Verified automatic runtime: the displayed registration scenarios use the pinned whole-snapshot download.";
    }
    const fingerprint=root.querySelector("[data-native-runtime-fingerprint]");
    if (fingerprint) {
      const code=document.createElement("code");
      code.textContent=manifest.complete_download.sha256;
      fingerprint.replaceChildren(document.createTextNode(
        `${manifest.complete_download.bytes.toLocaleString("en-US")} bytes · SHA-256 `),code);
    }
    root.dataset.nativeAutomaticVersion=manifest.version;
    status.textContent=validated.fresh.size
      ?`Automatic registered frames active for ${[...validated.fresh].join(", ")}; all other accepted values retained.`
      :"Automatic snapshot checked; last verified registered-control scenarios retained.";
    status.dataset.state="active";
    setAutomaticRuntimeStatus("civic","active","registered-control estimates",manifest);
  } catch (error) {
    if (root.dataset.automaticGeneration!==token) return;
    status.textContent=`Automatic registered-control update unavailable; accepted revision 35 values retained. ${error.message}`;
    status.dataset.state="error";
    rejectAutomaticRuntime("civic",error);
  }
}

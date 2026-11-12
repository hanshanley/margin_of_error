export const norcTerms = [
  ["switching", "Switching"],
  ["exit", "Previous voters absent"],
  ["entry", "New / returning to the contest"],
  ["other_choice", "Other-party choice"],
  ["unresolved", "Unresolved responses"],
];
export const norcViews = [
  ["reported_total", "Observed House swing"],
  ["switching", "Switching · NORC estimate"],
  ["modeled_nonparticipation", "Net participation · NORC estimate"],
  ["entry", "New / returning · NORC estimate"],
  ["exit", "Previous voters absent · NORC estimate"],
  ["other_choice", "Other-party choice · NORC estimate"],
  ["unresolved", "Unresolved responses · NORC estimate"],
  ["retaining", "Kept party · modeled share"],
];
export const demographicLabels = {
  AGE6: "Age", RACETH5: "Race / ethnicity", EDUC: "Education",
  SEX: "Reported sex", INCOME: "Reported household income", RUCC: "County context",
};
const finite = value => typeof value === "number" && Number.isFinite(value);
const close = (a, b) => finite(a) && finite(b) && Math.abs(a-b) < 1e-7;
const cached = new Map();
export const norcAssociations = [
  ["original", "Original association"],
  ["attenuated", "Historical association · attenuated stress"],
  ["full", "Historical association · stronger stress"],
];
export const norcFamilies = [
  ["accepted_ridge_multinomial", "Multinomial ridge · accepted baseline"],
  ["histogram_gradient_boosting", "Histogram gradient boosting"],
  ["extra_randomized_trees", "Extra-randomized trees"],
];
export const norcContributionScale = units => {
  if (units === "margin") return 1;
  if (units === "democratic_two_party_share") return .5;
  throw new Error("Unknown House change denominator");
};

export function norcSharedBound(comparison, group="", units="margin", sharedMaximum=null) {
  const factor=norcContributionScale(units);
  const models=comparison?.families?Object.values(comparison.families):[comparison];
  const local=Math.max(0,...models.flatMap(model=>(model?.rows || []).flatMap(row=>
    norcViews.filter(([key])=>key!=="retaining").map(([key])=>Math.abs(norcMapValue(row,key,group,"margin")??0)))));
  if (sharedMaximum!==null && (!finite(sharedMaximum) || sharedMaximum<local-1e-7))
    throw new Error("Association comparison scale omits a displayed estimate");
  return Math.max(5,Math.ceil((sharedMaximum??local)*factor/5)*5);
}

export function validateNorcHouse(data) {
  if (data?.contract !== "participation.norc_house_demographic_model.v1"
      || data.confidence_intervals !== null || data.model_units_are_people !== false
      || data.local_allocation !== false || data.current_party_totals_used_in_source_model_training !== false
      || data.return_constraints_used_only_in_separate_conditional_reconstruction !== true
      || data.source_likelihood_is_completed_voting !== false
      || data.demographic_dimensions_are_additive_together !== false
      || !Array.isArray(data.rows) || data.rows.length !== 50)
    throw new Error("Unqualified NORC House model");
  const identities = new Set();
  for (const row of data.rows) {
    if (!("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(" ").includes(row.state_code))
        || identities.has(row.state_code) || row.office !== "house" || row.id !== row.state_code+"-house")
      throw new Error("Invalid NORC state identity");
    identities.add(row.state_code);
    if (!finite(row.point?.total_change_pp) || !close(row.point.current_margin_pp-row.point.previous_margin_pp,
      row.point.total_change_pp) || !close(norcTerms.reduce((s,[key])=>s+row.point.contributions_pp[key],0),
      row.point.total_change_pp) || !close(row.point.net_participation_pp,
      row.point.contributions_pp.entry+row.point.contributions_pp.exit))
      throw new Error("NORC transition accounting differs");
    if (!Array.isArray(row.joint) || row.joint.length !== 5
        || row.joint.some(values=>values.length !== 5 || values.some(v=>!finite(v) || v<0))
        || !close(row.joint.flat().reduce((s,v)=>s+v,0),1))
      throw new Error("Invalid NORC DRONU flow table");
    const rr=row.joint.map(values=>values.reduce((s,v)=>s+v,0));
    const cc=Array.from({length:5},(_,j)=>row.joint.reduce((s,values)=>s+values[j],0));
    if (row.estimated_house_baseline_year!==2024 || !close(100*(rr[0]-rr[1])/(rr[0]+rr[1]),row.point.previous_margin_pp)
        || !close(100*(cc[0]-cc[1])/(cc[0]+cc[1]),row.point.current_margin_pp))
      throw new Error("NORC House baseline or flow margins differ");
    if (row.measured_staying_home !== null || row.actual_first_ever_voting !== null
        || row.unknown_source_response_is_not_nonvote !== true)
      throw new Error("Model histories were mislabeled as observed people");
    if (row.source_comparison_available) {
      if (row.reported_comparison.status !== "reported_source_comparison"
          || !close(row.point.total_change_pp,row.reported_comparison.reported_change_pp))
        throw new Error("NORC reconstruction differs from its return endpoints");
      if (!finite(row.assumed_accounting_frame_units) || row.assumed_accounting_frame_units<=0
          || row.before_current_party_conditioning?.current_party_totals_used!==false)
        throw new Error("Invalid conditioned frame or preconditioning diagnostic");
      for (const [index,party] of ["D","R","O"].entries()) {
        if (Math.abs(rr[index]*row.assumed_accounting_frame_units-row.reported_comparison.previous[party])>.0001
            || Math.abs(cc[index]*row.assumed_accounting_frame_units-row.reported_comparison.current[party])>.0001)
          throw new Error("NORC reconstruction substituted native counts");
      }
    } else if (row.reported_comparison.status !== "unavailable" || row.assumed_accounting_frame_units !== null)
      throw new Error("Missing observed comparisons must remain unavailable");
    const groups = new Set();
    for (const group of row.groups) {
      const id = group.dimension+"|"+group.group;
      if (!demographicLabels[group.dimension] || groups.has(id)) throw new Error("Invalid demographic identity");
      groups.add(id);
      if (!group.available) {
        if (group.contributions_pp !== null || group.total_contribution_pp !== null)
          throw new Error("Held demographic results must not become zero estimates");
      } else if (!finite(group.total_contribution_pp)
          || !close(norcTerms.reduce((s,[key])=>s+group.contributions_pp[key],0),group.total_contribution_pp)
          || !close(group.net_participation_pp,group.contributions_pp.entry+group.contributions_pp.exit))
        throw new Error("Demographic model contribution does not reconcile");
    }
    for (const dimension of Object.keys(demographicLabels))
      for (const [key] of norcTerms)
        if (!close(row.groups.filter(g=>g.dimension===dimension && g.available)
          .reduce((s,g)=>s+g.contributions_pp[key],0),row.point.contributions_pp[key]))
          throw new Error("Demographic partition differs from its state");
  }
  if (data.summary?.return_anchored !== data.rows.filter(row=>row.source_comparison_available).length
      || data.summary.states !== 50 || !finite(data.preconditioning_margin_MAE_pp))
    throw new Error("NORC source coverage differs");
  return data;
}

export function validateNorcFamilies(data) {
  if (data?.contract !== "participation.house_model_families.v1"
      || data.no_independent_behavioral_identification !== true
      || data.family_spread_is_not_confidence_interval !== true
      || Object.keys(data.families || {}).length !== 3 || data.source_validation?.length !== 9)
    throw new Error("Unqualified model-family comparison");
  const baseline = data.families.accepted_ridge_multinomial;
  for (const [family] of norcFamilies) {
    const model = validateNorcHouse(data.families[family]);
    for (const row of model.rows) {
      const original = baseline.rows.find(value=>value.state_code===row.state_code);
      if (JSON.stringify(row.reported_comparison) !== JSON.stringify(original.reported_comparison)
          || JSON.stringify(row.groups.map(g=>[g.dimension,g.group,g.label,g.available])) !==
            JSON.stringify(original.groups.map(g=>[g.dimension,g.group,g.label,g.available])))
        throw new Error("Family comparison substituted endpoints or disclosure masks");
    }
  }
  if (data.association_profile) {
    const profile=data.association_profile;
    if (!["attenuated","full"].includes(profile.profile)
        || profile.historical_parameter_not_validated_for2026!==true
        || profile.applied_postaggregation_not_per_case!==true
        || profile.demographic_partition_year_margins_preserved!==true
        || profile.source_only_feasibility_backoff!==true || profile.default_accepted_model_changed!==false
        || !finite(profile.requested_theta) || profile.requested_theta<=1
        || !finite(profile.source_primary_history_theta_median) || profile.source_primary_history_theta_median<=1
        || !close(profile.requested_theta,Math.pow(profile.source_primary_history_theta_median,
          profile.profile==="attenuated"?.5:1)))
      throw new Error("Unqualified historical association stress");
    for (const [family] of norcFamilies) {
      const stress=data.families[family].historical_association_stress;
      if (stress?.profile!==profile.profile || stress.default_accepted_model_changed!==false
          || stress.unvalidated_source_cycle_predictor_and_aggregation_transport!==true
          || stress.current_return_targets_used_to_select_association!==false
          || stress.fitted_source_state_and_group_year_marginals_preserved!==true
          || Object.keys(stress.state_parameters || {}).length!==50)
        throw new Error("Association stress changed its source or validation status");
      for (const row of data.families[family].rows) {
        const parameter=stress.state_parameters[row.state_code];
        if (!finite(parameter?.requested_theta) || !close(parameter.requested_theta,profile.requested_theta)
            || !finite(parameter.effective_theta) || parameter.effective_theta<1
            || parameter.effective_theta>profile.requested_theta+1e-7
            || ![0,.125,.25,.5,1].includes(parameter.feasibility_exponent)
            || !close(parameter.effective_theta,Math.pow(parameter.requested_theta,parameter.feasibility_exponent))
            || !finite(parameter.maximum_constraint_error) || parameter.maximum_constraint_error<0
            || parameter.maximum_constraint_error>1e-9)
          throw new Error("Invalid source-only association feasibility decision");
      }
    }
  }
  const metrics = new Map();
  for (const row of data.source_validation) {
    const key=row.family+"|"+row.role;
    if (metrics.has(key) || !norcFamilies.some(([family])=>family===row.family)
        || !["house24_bridge","house26_response","historical_transfer"].includes(row.role)
        || !finite(row.source_weighted_log_loss) || row.source_weighted_log_loss<0
        || !finite(row.source_weighted_multiclass_brier) || row.source_weighted_multiclass_brier<0
        || row.current_returns_used_for_fit_or_selection!==false)
      throw new Error("Invalid source-only family validation");
    metrics.set(key,row);
  }
  const reference=metrics.get("accepted_ridge_multinomial|historical_transfer");
  const current=metrics.get("accepted_ridge_multinomial|house26_response");
  const eligible=norcFamilies.map(([family])=>family).filter(family=>{
    const historical=metrics.get(family+"|historical_transfer"),response=metrics.get(family+"|house26_response");
    return historical.source_weighted_log_loss<=reference.source_weighted_log_loss
      && historical.source_weighted_multiclass_brier<=reference.source_weighted_multiclass_brier
      && response.source_weighted_multiclass_brier<=current.source_weighted_multiclass_brier;
  }).sort((a,b)=>metrics.get(a+"|historical_transfer").source_weighted_log_loss
      -metrics.get(b+"|historical_transfer").source_weighted_log_loss);
  if (data.preferred_family!==eligible[0]) throw new Error("Model chosen using undeclared criteria");
  return data;
}

export function validateNorcAssociation(data, original) {
  validateNorcFamilies(data);
  validateNorcFamilies(original);
  if (!data.association_profile || original.association_profile
      || data.preferred_family!==original.preferred_family
      || JSON.stringify(data.source_validation)!==JSON.stringify(original.source_validation))
    throw new Error("Association profile substituted the accepted source comparison");
  for (const [family] of norcFamilies) for (const row of data.families[family].rows) {
    const baseline=original.families[family].rows.find(value=>value.state_code===row.state_code);
    if (JSON.stringify(row.reported_comparison)!==JSON.stringify(baseline.reported_comparison)
        || JSON.stringify(row.groups.map(g=>[g.dimension,g.group,g.label,g.available]))!==
          JSON.stringify(baseline.groups.map(g=>[g.dimension,g.group,g.label,g.available])))
      throw new Error("Association profile substituted endpoints or disclosure masks");
  }
  return data;
}

export async function loadNorcHouse(receipt) {
  if (!receipt || !/^[a-f0-9]{64}$/.test(receipt.sha256)
      || !Number.isSafeInteger(receipt.bytes) || receipt.bytes<=0 || receipt.bytes>10_000_000
      || !/^https:\/\/raw\.githubusercontent\.com\/hanshanley\/voter-participation\/[a-f0-9]{40}\/data\/(?:(?:norc-house-demographic\/20261111-01|house-clerk-norc-endpoints\/20261112-01|pa-house-native-controls\/20261112-01|house-model-families\/20261112-01)\/viewer-data|house-fixed-copula\/20261112-01\/viewer-(?:attenuated|full))\.json$/.test(receipt.url))
    throw new Error("Unpinned NORC model input");
  const pin = `${receipt.url}|${receipt.sha256}|${receipt.bytes}`;
  if (!cached.has(pin)) {
    const promise = (async()=>{
      const controller = new AbortController(), timer = setTimeout(()=>controller.abort(),20_000);
      try {
        const response = await fetch(receipt.url,{signal:controller.signal});
        if (!response.ok) throw new Error(`NORC model HTTP ${response.status}`);
        const bytes = await response.arrayBuffer();
        const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),
          v=>v.toString(16).padStart(2,"0")).join("");
        if (bytes.byteLength !== receipt.bytes || digest !== receipt.sha256) throw new Error("NORC model checksum mismatch");
        const data=JSON.parse(new TextDecoder().decode(bytes));
        const result=data.contract==="participation.house_model_families.v1"?validateNorcFamilies(data):validateNorcHouse(data);
        const profile=receipt.url.match(/viewer-(attenuated|full)\.json$/)?.[1];
        if ((profile || result.association_profile) && result.association_profile?.profile!==profile)
          throw new Error("Association receipt and source profile differ");
        return result;
      } finally { clearTimeout(timer); }
    })().catch(error=>{if(cached.get(pin)===promise) cached.delete(pin);throw error;});
    cached.set(pin,promise);
  }
  return cached.get(pin);
}

export function norcGroups(data) {
  const groups = new Map();
  for (const row of data.rows) for (const group of row.groups)
    if (group.group !== "unshown" && group.available)
      groups.set(group.dimension+"|"+group.group,{value:group.dimension+"|"+group.group,
        label:`${demographicLabels[group.dimension]} · ${group.label}`});
  return [...groups.values()];
}

export function norcEstimate(row, group="") {
  if (!row) return null;
  if (!group) return { ...row.point, total_contribution_pp:row.point.total_change_pp,
    gross_outcomes:row.gross_outcomes, joint:row.joint, sensitivity_ranges_pp:row.sensitivity_ranges_pp };
  const selected = row.groups.find(g=>g.dimension+"|"+g.group===group);
  return selected?.available ? selected : null;
}

export function norcMapValue(row, key, group="", units="margin") {
  if (!row) return null;
  const factor=norcContributionScale(units);
  if (key === "reported_total") return row.source_comparison_available ? row.reported_comparison.reported_change_pp*factor : null;
  const value = norcEstimate(row,group);
  if (!value) return null;
  if (key === "modeled_nonparticipation") return value.net_participation_pp*factor;
  if (key === "retaining") return value.gross_outcomes?.retaining == null ? null : value.gross_outcomes.retaining*100;
  return value.contributions_pp[key] == null ? null : value.contributions_pp[key]*factor;
}

export function roundedNorcContributions(value,units="margin") {
  const factor=norcContributionScale(units);
  const raw = norcTerms.map(([key])=>({key,scaled:value.contributions_pp[key]*factor*100}));
  const output = Object.fromEntries(raw.map(({key,scaled})=>[key,Math.floor(scaled)]));
  const total = (value.total_contribution_pp ?? value.total_change_pp)*factor;
  const target = Math.round(Number(total.toFixed(2))*100);
  const count = target-Object.values(output).reduce((s,v)=>s+v,0);
  if (count < 0 || count > raw.length) throw new Error("Invalid NORC contribution rounding");
  raw.sort((a,b)=>(b.scaled-Math.floor(b.scaled))-(a.scaled-Math.floor(a.scaled)));
  for (let i=0;i<count;i++) output[raw[i].key]++;
  return Object.fromEntries(Object.entries(output).map(([k,v])=>[k,v/100]));
}

const element = (tag,text,className="") => {
  const node=document.createElement(tag); if (text!=null) node.textContent=text; node.className=className; return node;
};
const pp=value=>`${value>0?"+":""}${value.toFixed(2)} pp`;
const margin=value=>`${value<0?"R":"D"}+${Math.abs(value).toFixed(2)}`;

export function renderNorcSelection(row, group, name, summary, detail,options={}) {
  const units=options.units || "margin",factor=norcContributionScale(units);
  const signed=value=>pp(value*factor),share=units==="democratic_two_party_share";
  const unitLabel=share?"Democratic two-party share change":"margin change";
  const endpoint=value=>share?`${(50+value/2).toFixed(2)}% Democratic two-party share`:margin(value);
  const estimate=norcEstimate(row,group), selected=group ? row?.groups.find(g=>g.dimension+"|"+g.group===group) : null;
  summary.replaceChildren(element("h3",`${name} · House ${unitLabel}`));
  delete summary.dataset.norcState;delete summary.dataset.norcGroup;
  delete summary.dataset.norcAssociation;
  detail.replaceChildren();
  if (!row) {
    summary.append(element("p","D.C. has no NORC CHEP sample; no House transition estimate is invented.","caption"));
    summary.hidden=false; detail.hidden=true; return;
  }
  const point=row.point;
  summary.append(element("p",row.source_comparison_available
    ? `2024 ${endpoint(row.reported_comparison.previous_margin_pp)} → held 2026 ${endpoint(row.reported_comparison.current_margin_pp)}. ${signed(point.total_change_pp)} ${share?"change in Democratic two-party share":"change in the Democratic–Republican margin"}.`
    : `Observed House comparison unavailable: ${row.reported_comparison.reason} The NORC source scenario is shown separately, not as a recorded result.`,
  "driver-endpoints"));
  const association=options.association?.profile || "original";
  const associationLabel=norcAssociations.find(([key])=>key===association)?.[1] || "Original association";
  summary.dataset.norcAssociation=association;
  summary.append(element("p",association==="original"
    ? "Original conditional-association construction. Historical dependence stresses are alternatives, not validated 2026 histories."
    : `${associationLabel}. This is an unvalidated state-level transport of historical D/R persistence, not a new turnout measurement.`,
  "caption"));
  if (row.source_comparison_available) summary.append(element("p",
    `Democratic two-party share: ${(50+point.previous_margin_pp/2).toFixed(2)}% → ${(50+point.current_margin_pp/2).toFixed(2)}%, `
    +`${pp(point.total_change_pp/2)} change. D−R margin change: ${pp(point.total_change_pp)}. `
    +"Two-party shares exclude Other; neither is population turnout.","caption"));
  if (typeof row.reported_comparison.current_native_control_scope_qualification === "string")
    summary.append(element("p",row.reported_comparison.current_native_control_scope_qualification,"caption"));
  if (!estimate) {
    summary.append(element("p",`${selected?.label || "This source group"} is withheld or unsupported in this state. No other group or state is substituted.`,"caption"));
    summary.hidden=false; detail.hidden=true; return;
  }
  const rounded=roundedNorcContributions(estimate,units);
  const table=element("table"), body=element("tbody");
  table.append(element("caption",group
    ? `${selected.label}: contribution to the statewide modeled shift, not this group's vote share`
    : "NORC-informed, return-constrained reconstruction · not observed individual histories"));
  for (const [label,value,key] of [
    ["Switching",rounded.switching,"switching"],
    ["Net participation",Number((rounded.entry+rounded.exit).toFixed(2)),"net_participation"],
    ["Other-party choice",rounded.other_choice,"other_choice"],
    ["Unresolved responses",rounded.unresolved,"unresolved"],
    [group?"Group contribution":`Modeled ${unitLabel}`,estimate.total_contribution_pp*factor,"total"],
  ]) {
    const tr=element("tr"), th=element("th",label);th.scope="row";
    const td=element("td",pp(value),"numeric");td.dataset.norcMechanism=key;
    tr.append(th,td);body.append(tr);
  }
  table.append(body);
  const wrap=element("div",null,"table-wrap");wrap.append(table);
  summary.append(wrap,element("p",
    `Net participation includes ${pp(rounded.exit)} from modeled nonparticipation and ${pp(rounded.entry)} from entry/return. `
    +"Positive contributions move the result toward Democrats; negative contributions move it toward Republicans. "
    +"NORC responses inform the marginal models; temporal dependence and the accounting frame remain assumptions. Reported results constrain the reconstruction, not its validation.",
    "caption"));
  summary.dataset.norcState=row.state_code;summary.dataset.norcGroup=group;
  summary.dataset.norcUnits=units;summary.dataset.norcFamily=options.family || "accepted_ridge_multinomial";
  const dimension=selected?.dimension || "AGE6";
  const groupTable=element("table"), groupBody=element("tbody"), head=element("thead"), headings=element("tr");
  groupTable.append(element("caption",`${demographicLabels[dimension]} breakdown · rows add to the state; different demographic dimensions overlap`));
  for (const label of ["Group","Switching","Participation","Other / unresolved","Total"]) headings.append(element("th",label));
  head.append(headings);groupTable.append(head);
  for (const g of row.groups.filter(g=>g.dimension===dimension)) {
    const tr=element("tr"), th=element("th",g.label);th.scope="row";
    tr.dataset.norcGroupRow=g.dimension+"|"+g.group;
    const values=g.available ? [g.contributions_pp.switching,g.net_participation_pp,
      g.contributions_pp.other_choice+g.contributions_pp.unresolved,g.total_contribution_pp] : [null,null,null,null];
    tr.append(th,...values.map(v=>element("td",v===null?"Unavailable":signed(v),"numeric")));groupBody.append(tr);
  }
  groupTable.append(groupBody);
  const grouped=element("div",null,"table-wrap");grouped.append(groupTable);
  detail.append(grouped);
  if (options.associationState) {
    const value=options.associationState;
    detail.append(element("p",`Requested D–D/R–R kernel multiplier ${value.requested_theta.toFixed(3)}; applied ${value.effective_theta.toFixed(3)} `
      +`after source-only demographic feasibility checks. Unconditional fitted state and group year-specific margins are preserved. `
      +`This multiplies the source D/R cross-product odds by ${(value.effective_theta**2).toFixed(3)}, not the retained-choice percentage. `
      +"The parameter is not validated for the different 2026 predictors, electorate or election direction.","caption"));
  }
  if (options.originalComparison && association!=="original") {
    const original=options.originalComparison.families[options.family]?.rows.find(value=>value.state_code===row.state_code);
    const before=norcEstimate(original,group);
    if (before) {
      const comparison=element("table"),head=element("thead"),labels=element("tr"),body=element("tbody");
      comparison.dataset.norcAssociationComparison=row.state_code;
      comparison.append(element("caption",`Original versus selected association · ${group?"same selected group; ":""}conditional estimates`));
      for (const label of ["Association","Switching","Net participation","Kept party"]) labels.append(element("th",label));
      head.append(labels);comparison.append(head);
      for (const [label,value] of [["Original association",before],[associationLabel,estimate]]) {
        const tr=element("tr"),th=element("th",label);th.scope="row";
        tr.append(th,element("td",signed(value.contributions_pp.switching),"numeric"),
          element("td",signed(value.net_participation_pp),"numeric"),
          element("td",value.gross_outcomes?`${(100*value.gross_outcomes.retaining).toFixed(1)}%`:"Unavailable","numeric"));
        body.append(tr);
      }
      comparison.append(body);
      const wrap=element("div",null,"table-wrap");wrap.append(comparison);detail.append(wrap);
    }
  }
  const flow=estimate.joint, flows=element("table"), flowBody=element("tbody"), flowHead=element("thead"), flowLabels=element("tr");
  flows.append(element("caption","Model-assigned outcomes within previous D/R choices · percentages, not margin points"));
  for (const label of ["Previous choice","Kept party","Switched party","Absent","Other / unresolved"]) flowLabels.append(element("th",label));
  flowHead.append(flowLabels);flows.append(flowHead);
  for (let i=0;i<2;i++) {
    const denominator=flow[i].reduce((s,v)=>s+v,0), tr=element("tr"), th=element("th",i?"Republican":"Democratic");th.scope="row";
    tr.append(th,...[flow[i][i],flow[i][1-i],flow[i][3],flow[i][2]+flow[i][4]]
      .map(v=>element("td",denominator?`${(100*v/denominator).toFixed(1)}%`:"Unavailable","numeric")));
    flowBody.append(tr);
  }
  flows.append(flowBody);
  const flowWrap=element("div",null,"table-wrap");flowWrap.append(flows);detail.append(flowWrap);
  const ranges=estimate.sensitivity_ranges_pp;
  if (ranges) detail.append(element("p",`Assumption range: switching ${signed(ranges.switching.minimum)} to ${signed(ranges.switching.maximum)}; `
    +`net participation ${signed(ranges.net_participation.minimum)} to ${signed(ranges.net_participation.maximum)}. `
    +"These vary accounting-frame size and latent House-choice affinity; they are not confidence intervals.","caption"));
  if (row.before_current_party_conditioning) {
    const check=row.before_current_party_conditioning;
    detail.append(element("p",`Before conditioning on current party totals, the NORC model projects ${endpoint(check.current_margin_pp)}; `
      +`the observed result is ${endpoint(row.reported_comparison.current_margin_pp)}. `
      +`The ${signed(check.prediction_error_observed_minus_predicted_pp)} prediction gap is model error, not another behavioral mechanism.`,
    "caption"));
  }
  if (options.comparison) {
    const table=element("table"),head=element("thead"),labels=element("tr"),body=element("tbody");
    table.dataset.norcFamilyComparison=row.state_code;
    table.append(element("caption",`Three model families · ${group?"same selected group; ":""}${unitLabel} contributions`));
    for (const label of ["Model","Switching","Net participation","State prediction error","Kept party"])
      labels.append(element("th",label));
    head.append(labels);table.append(head);
    for (const [family,label] of norcFamilies) {
      const state=options.comparison.families[family].rows.find(r=>r.state_code===row.state_code);
      const value=norcEstimate(state,group),tr=element("tr"),th=element("th",label);th.scope="row";
      const error=state.before_current_party_conditioning?.prediction_error_observed_minus_predicted_pp;
      tr.dataset.norcFamilyRow=family;
      tr.append(th,element("td",value?signed(value.contributions_pp.switching):"Unavailable","numeric"),
        element("td",value?signed(value.net_participation_pp):"Unavailable","numeric"),
        element("td",error==null?"Unavailable":signed(error),"numeric"),
        element("td",value?.gross_outcomes?`${(100*value.gross_outcomes.retaining).toFixed(1)}%`:"Unavailable","numeric"));
      body.append(tr);
    }
    table.append(body);
    const wrap=element("div",null,"table-wrap");wrap.append(table);detail.append(wrap,
      element("p","All three use the same source records, held endpoints, frame/affinity settings and simulation seeds. "
        +"Family spread is model sensitivity, not a confidence interval. Matching observed totals is imposed and does not identify behavior. "
        +"Retained-voter percentages and state prediction errors use their own stated denominators.","caption"));
  }
  detail.append(element("p",
    "The 2024 House baseline is bridged from AP/NORC's actual President/House association and recalled 2022 House choice. "
    +"Current demographics and current residence are transported under assumptions. Modeled absence is not confirmed staying home; entry/return is not proven first-ever voting. "
    +"Unknown source responses remain separate. Changed candidate availability and incomplete reporting can affect state totals.","caption"));
  summary.hidden=false;detail.hidden=false;
}

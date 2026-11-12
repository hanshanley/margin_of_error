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
let cached, cachedPin;

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

export async function loadNorcHouse(receipt) {
  if (!receipt || !/^[a-f0-9]{64}$/.test(receipt.sha256)
      || !Number.isSafeInteger(receipt.bytes) || receipt.bytes<=0 || receipt.bytes>10_000_000
      || !/^https:\/\/raw\.githubusercontent\.com\/hanshanley\/voter-participation\/[a-f0-9]{40}\/data\/(?:norc-house-demographic\/20261111-01|house-clerk-norc-endpoints\/20261112-01)\/viewer-data\.json$/.test(receipt.url))
    throw new Error("Unpinned NORC model input");
  const pin = `${receipt.url}|${receipt.sha256}|${receipt.bytes}`;
  if (!cached || cachedPin !== pin) {
    cachedPin = pin;
    cached = (async()=>{
      const controller = new AbortController(), timer = setTimeout(()=>controller.abort(),20_000);
      try {
        const response = await fetch(receipt.url,{signal:controller.signal});
        if (!response.ok) throw new Error(`NORC model HTTP ${response.status}`);
        const bytes = await response.arrayBuffer();
        const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),
          v=>v.toString(16).padStart(2,"0")).join("");
        if (bytes.byteLength !== receipt.bytes || digest !== receipt.sha256) throw new Error("NORC model checksum mismatch");
        return validateNorcHouse(JSON.parse(new TextDecoder().decode(bytes)));
      } finally { clearTimeout(timer); }
    })().catch(error=>{if(cachedPin===pin) cached=undefined;throw error;});
  }
  return cached;
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

export function norcMapValue(row, key, group="") {
  if (!row) return null;
  if (key === "reported_total") return row.source_comparison_available ? row.reported_comparison.reported_change_pp : null;
  const value = norcEstimate(row,group);
  if (!value) return null;
  if (key === "modeled_nonparticipation") return value.net_participation_pp;
  if (key === "retaining") return value.gross_outcomes?.retaining == null ? null : value.gross_outcomes.retaining*100;
  return value.contributions_pp[key] ?? null;
}

export function roundedNorcContributions(value) {
  const raw = norcTerms.map(([key])=>({key,scaled:value.contributions_pp[key]*100}));
  const output = Object.fromEntries(raw.map(({key,scaled})=>[key,Math.floor(scaled)]));
  const total = value.total_contribution_pp ?? value.total_change_pp;
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

export function renderNorcSelection(row, group, name, summary, detail) {
  const estimate=norcEstimate(row,group), selected=group ? row?.groups.find(g=>g.dimension+"|"+g.group===group) : null;
  summary.replaceChildren(element("h3",`${name} · House margin change`));
  delete summary.dataset.norcState;delete summary.dataset.norcGroup;
  detail.replaceChildren();
  if (!row) {
    summary.append(element("p","D.C. has no NORC CHEP sample; no House transition estimate is invented.","caption"));
    summary.hidden=false; detail.hidden=true; return;
  }
  const point=row.point;
  summary.append(element("p",row.source_comparison_available
    ? `2024 ${margin(row.reported_comparison.previous_margin_pp)} → held 2026 ${margin(row.reported_comparison.current_margin_pp)}. ${pp(point.total_change_pp)} change in the Democratic–Republican margin.`
    : `Observed House comparison unavailable: ${row.reported_comparison.reason} The NORC source scenario is shown separately, not as a recorded result.`,
  "driver-endpoints"));
  if (!estimate) {
    summary.append(element("p",`${selected?.label || "This source group"} is withheld or unsupported in this state. No other group or state is substituted.`,"caption"));
    summary.hidden=false; detail.hidden=true; return;
  }
  const rounded=roundedNorcContributions(estimate);
  const table=element("table"), body=element("tbody");
  table.append(element("caption",group
    ? `${selected.label}: contribution to the statewide modeled shift, not this group's vote share`
    : "NORC-informed, return-constrained reconstruction · not observed individual histories"));
  for (const [label,value,key] of [
    ["Switching",rounded.switching,"switching"],
    ["Net participation",Number((rounded.entry+rounded.exit).toFixed(2)),"net_participation"],
    ["Other-party choice",rounded.other_choice,"other_choice"],
    ["Unresolved responses",rounded.unresolved,"unresolved"],
    [group?"Group contribution":"Modeled margin change",estimate.total_contribution_pp,"total"],
  ]) {
    const tr=element("tr"), th=element("th",label);th.scope="row";
    const td=element("td",pp(value),"numeric");td.dataset.norcMechanism=key;
    tr.append(th,td);body.append(tr);
  }
  table.append(body);
  const wrap=element("div",null,"table-wrap");wrap.append(table);
  summary.append(wrap,element("p",
    `Net participation includes ${pp(rounded.exit)} from modeled nonparticipation and ${pp(rounded.entry)} from entry/return. `
    +"Positive contributions move the margin toward Democrats; negative contributions move it toward Republicans. "
    +"Retention, switching and nonparticipation are learned from NORC responses; reported results constrain the reconstruction, not its validation.",
    "caption"));
  summary.dataset.norcState=row.state_code;summary.dataset.norcGroup=group;
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
    tr.append(th,...values.map(v=>element("td",v===null?"Unavailable":pp(v),"numeric")));groupBody.append(tr);
  }
  groupTable.append(groupBody);
  const grouped=element("div",null,"table-wrap");grouped.append(groupTable);
  detail.append(grouped);
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
  if (ranges) detail.append(element("p",`Assumption range: switching ${pp(ranges.switching.minimum)} to ${pp(ranges.switching.maximum)}; `
    +`net participation ${pp(ranges.net_participation.minimum)} to ${pp(ranges.net_participation.maximum)}. `
    +"These vary accounting-frame size and latent House-choice affinity; they are not confidence intervals.","caption"));
  if (row.before_current_party_conditioning) {
    const check=row.before_current_party_conditioning;
    detail.append(element("p",`Before conditioning on current party totals, the NORC model projects ${margin(check.current_margin_pp)}; `
      +`the observed result is ${margin(row.reported_comparison.current_margin_pp)}. `
      +`The ${pp(check.prediction_error_observed_minus_predicted_pp)} prediction gap is model error, not another behavioral mechanism.`,
    "caption"));
  }
  detail.append(element("p",
    "The 2024 House baseline is bridged from AP/NORC's actual President/House association and recalled 2022 House choice. "
    +"Current demographics and current residence are transported under assumptions. Modeled absence is not confirmed staying home; entry/return is not proven first-ever voting. "
    +"Unknown source responses remain separate. Changed candidate availability and incomplete reporting can affect state totals.","caption"));
  summary.hidden=false;detail.hidden=false;
}

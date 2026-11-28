import { fetchSourceBody } from "./participation-statewide-source.js";
import { loadAutomaticRuntime } from "./participation-automatic-runtime.js";

export const transitionViews = [
  ["house_transition_home", "Modeled staying-home contribution · all 50 states"],
  ["house_transition_switching", "Modeled D↔R switching contribution · all 50 states"],
];
export const isTransitionView = view => transitionViews.some(([key]) => key === view);
const TERMS = ["switching","staying_home","entry_return","other_choice","house_choice","eligibility_change"];
const LABELS = ["D↔R switching","Modeled no ballot","Entry / return","Other / unassigned choice","House-choice / reporting changes","Eligibility / frame changes"];
const STATES = "AK AL AR AZ CA CO CT DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY".split(" ").sort();
const finite = value => typeof value === "number" && Number.isFinite(value);
const close = (a,b,tolerance=1e-6) => finite(a) && finite(b) && Math.abs(a-b)<=tolerance;

export function validateHouseTransitions(data) {
  if (data?.contract!=="participation.statewide_house_transitions.v1" || !/^[a-f0-9]{64}$/.test(data.version)
      || data.categories?.join()!=="D,R,O,H,N,E" || data.states!==50 || data.quick_development_preview!==false
      || data.population_or_individual_histories_validated!==false || data.confidence_intervals!==null
      || data.model_units_are_people!==false || data.identified_individual_histories!==false
      || data.measured_staying_home!==null || data.candidate_votes_are_not_ballots!==true
      || data.source_unknown_responses_are_not_nonvoting!==true
      || data.gross_percentage_denominator!=="all_2024_reported_D_R_Other_or_unassigned_House_votes"
      || !Array.isArray(data.rows) || data.rows.length!==50
      || data.rows.map(row=>row.state_code).sort().join()!==STATES.join())
    throw new Error("Unqualified all-state House-transition model");
  for (const row of data.rows) {
    const p=row.point;
    if (row.available!==true || row.previous?.year!==2024 || row.current?.year!==2026
        || !finite(p?.frame) || p.frame<=0 || p.rows?.length!==6 || p.columns?.length!==6
        || p.joint?.length!==6 || p.joint.some(values=>values.length!==6 || values.some(v=>!finite(v)||v<0))
        || !Array.isArray(row.context_holds) || row.population_or_individual_histories_validated!==false)
      throw new Error("A whole state was omitted or its model frame changed");
    for (let i=0;i<6;i++) {
      if (!close(p.joint[i].reduce((a,b)=>a+b,0),p.rows[i],.001)
          || !close(p.joint.reduce((a,b)=>a+b[i],0),p.columns[i],.001))
        throw new Error("Statewide model does not retain its endpoint constraints");
    }
    for (const [phase,values] of [[row.previous,p.rows],[row.current,p.columns]]) {
      if (phase.house.length!==3 || phase.house.some((n,i)=>!close(n,values[i],.001))
          || !close(phase.ballots-phase.house.reduce((a,b)=>a+b,0),values[3],.001)
          || !close(phase.eligible-phase.ballots,values[4],.001)
          || !close(p.frame-phase.eligible,values[5],.001))
        throw new Error("House omissions, no ballots and eligibility were conflated");
    }
    const prior=p.rows.slice(0,3).reduce((a,b)=>a+b,0);
    if (!close(100*(p.joint[0][1]+p.joint[1][0])/prior,p.gross_pct.switching)
        || !close(100*p.joint.slice(0,3).reduce((a,b)=>a+b[4],0)/prior,p.gross_pct.no_ballot)
        || !close(Object.values(p.gross_pct).reduce((a,b)=>a+b,0),100)
        || !close(TERMS.reduce((sum,key)=>sum+p.contributions_pp[key],0),p.recorded_change_pp)
        || !close(100*(p.columns[0]/(p.columns[0]+p.columns[1])-p.rows[0]/(p.rows[0]+p.rows[1])),p.recorded_change_pp))
      throw new Error("Statewide transition quantities do not reconcile");
    for (const [prefix,values] of [["gross_",p.gross_pct],["contribution_",p.contributions_pp]])
      for (const [key,value] of Object.entries(values)) {
        const bounds=row.sensitivity[prefix+key];
        if (!finite(value) || !finite(bounds?.minimum) || !finite(bounds?.maximum)
            || bounds.minimum>value+1e-7 || bounds.maximum<value-1e-7)
          throw new Error("Statewide sensitivity omits its point estimate");
      }
  }
  return data;
}

export function transitionReceipt(manifest) {
  const value=manifest?.house_sources?.statewide_house_transitions;
  if (!value) return null;
  const base=manifest.house_sources.base_url.replace(/\/?$/,"/");
  if (value.contract!=="participation.statewide_house_transitions.v1" || value.states!==50
      || value.path!=="house/statewide-transitions/viewer.json.gz"
      || value.url!==new URL(value.path,base).href
      || value.house_results_sha256!==manifest.congressional?.sha256
      || value.count_snapshot_sha256!==manifest.counts?.files?.["current.json.gz"]?.sha256
      || value.source_models_refitted!==false || value.legacy_behavioral_gates_changed!==false)
    throw new Error("All-state transition model is not bound to the accepted House/turnout snapshot");
  return value;
}

const pp=value=>`${value>0?"+":""}${value.toFixed(2)} pp`;
const percent=value=>`${value.toFixed(1)}%`;
const scale=units=>units==="margin"?2:1;

export function roundedTransitionContributions(point, units="democratic_two_party_share") {
  const factor=scale(units),raw=TERMS.map(key=>({key,value:point.contributions_pp[key]*factor*100}));
  const result=Object.fromEntries(raw.map(({key,value})=>[key,Math.floor(value)]));
  const target=Math.round(Number((point.recorded_change_pp*factor).toFixed(2))*100);
  const remaining=target-Object.values(result).reduce((a,b)=>a+b,0);
  if(remaining<0||remaining>TERMS.length)throw Error("Invalid displayed transition rounding");
  raw.sort((a,b)=>(b.value-Math.floor(b.value))-(a.value-Math.floor(a.value)));
  for(let i=0;i<remaining;i++)result[raw[i].key]++;
  return Object.fromEntries(TERMS.map(key=>[key,result[key]/100]));
}

export function houseTransitionController(root, fallback, {items,names,effectFill,element,svgElement,onSelectState}) {
  const host=root.querySelector("[data-driver-map]"),summary=root.querySelector("[data-driver-summary]"),detail=root.querySelector("[data-driver-detail]");
  const table=root.querySelector("[data-house-transition-table]"),methods=root.querySelector("[data-house-transition-methods]");
  const legend=root.querySelector(".driver-no-model").lastChild,legacyLegend=legend.textContent;
  const key=root.querySelector(".driver-map-key"),legacyKey=key.getAttribute("aria-label");
  let data,promise,automatic=false,active=false,ticket=0,selected="TX",view="house_transition_home",units="democratic_two_party_share",observer;
  const field=()=>view==="house_transition_switching"?"switching":"staying_home";
  const select=code=>{
    selected=code;onSelectState?.(code);
    if (!active||!data) return;
    root.querySelector("[data-driver-state]").value=code;
    for (const path of host.querySelectorAll(".driver-state")) {
      const current=path.dataset.stateCode===code;path.classList.toggle("selected",current);path.tabIndex=current?0:-1;
    }
    const path=host.querySelector(".selected");if(path)path.parentNode.append(path);
    for(const hit of host.querySelectorAll("[data-driver-hit]"))hit.parentNode.append(hit);
    summary.replaceChildren();detail.replaceChildren();summary.hidden=false;detail.hidden=true;
    const row=data.rows.find(row=>row.state_code===code),primary=element("div",null,"driver-equation");summary.append(primary);
    for(const key of Object.keys(summary.dataset))if(key.startsWith("norc")||key.startsWith("recorded")||key.startsWith("sourceModel"))delete summary.dataset[key];
    summary.dataset.transitionState=code;summary.dataset.transitionVersion=data.version;
    primary.append(element("h3",`${names[code]||"Select a state"} · statewide House model`));
    if(!row){primary.append(element("p",code==="DC"?"D.C. has no voting House seat; no statewide voting-House model is invented.":"Choose a state for its whole-state House comparison.","caption"));return;}
    const p=row.point,factor=scale(units),rounded=roundedTransitionContributions(p,units),label=units==="margin"?"D−R margin":"Democratic share of D+R";
    primary.append(element("p",`Reported House ${label} change: ${pp(p.recorded_change_pp*factor)}.`,"driver-recorded-endpoints"));
    const values=element("table"),head=element("thead"),heading=element("tr"),body=element("tbody");
    for(const text of ["Modeled contribution","Estimate / assumption range"])heading.append(element("th",text));head.append(heading);values.append(head);
    for(const [key,name]of [["switching","D↔R switching"],["staying_home","No counted 2026 ballot"]]){
      const tr=element("tr"),r=row.sensitivity["contribution_"+key];tr.dataset.transitionTerm=key;
      tr.dataset.value=String(p.contributions_pp[key]*factor);
      const estimate=element("td",null,"numeric");estimate.append(element("strong",pp(rounded[key])),element("small",`${pp(Math.floor(r.minimum*factor*100)/100)} to ${pp(Math.ceil(r.maximum*factor*100)/100)}`));
      tr.append(element("th",name),estimate);body.append(tr);
    }values.append(body);const wrap=element("div",null,"table-wrap");wrap.append(values);primary.append(wrap);
    primary.append(element("p",`Within the modeled pool of 2024 recorded House votes: ${percent(p.gross_pct.switching)} switch D↔R; ${percent(p.gross_pct.no_ballot)} have no counted 2026 ballot. These percentages are not the contributions in points above.`,"caption"),
      element("p","Other-party choices, entry/return, House-choice/reporting changes and eligibility changes remain separate. Ranges are model sensitivity, not confidence intervals.","caption"));
    if(row.context_holds.length)primary.append(element("p","Changed candidate coverage or stage affects interpretation; these are recorded-category transitions, not evidence of persuasion. See assumptions below.","caption"));
    primary.append(element("p",automatic?"Updated model bound to this page's accepted House and turnout snapshot.":"Saved, fully reproducible model snapshot; automatic model update unavailable on this page.","caption"));
    detail.append(element("h4","Complete statewide accounting"));
    const accounting=element("table"),rows=element("tbody");
    for(const [i,key]of TERMS.entries()){
      const tr=element("tr");tr.append(element("th",LABELS[i]),element("td",pp(rounded[key]),"numeric"));rows.append(tr);
    }accounting.append(rows);const box=element("div",null,"table-wrap");box.append(accounting);detail.append(box);
    detail.append(element("p",`Whole-state House D/R/Other recorded votes: 2024 ${row.previous.house.map(v=>Math.round(v).toLocaleString("en-US")).join(" / ")}; 2026 ${row.current.house.map(v=>Math.round(v).toLocaleString("en-US")).join(" / ")}.`,"caption"),
      element("p",`Ballot benchmarks: 2024 ${Math.round(row.previous.ballots).toLocaleString("en-US")}; 2026 ${Math.round(row.current.ballots).toLocaleString("en-US")}. Ballots without a reported House choice are not staying home. Eligibility/frame changes are modeled separately.`,"caption"),
      element("p",`2026 UF source status: ${row.current.source_status||"estimate"}; not independently certified here. Source periods, priors and eligibility overlap remain assumptions, not linked voter histories.`,"caption"),
      element("p",row.context_holds.length?row.context_holds.join(" "):"All statewide recorded vote categories are retained; no common-district subset is substituted.","caption"));
    detail.hidden=false;
  };
  const load=async()=>{
    try{
      const manifest=await loadAutomaticRuntime(),receipt=transitionReceipt(manifest);
      if(receipt){const body=validateHouseTransitions(await fetchSourceBody(receipt));if(body.version!==receipt.version)throw Error("Model version differs");automatic=true;return body;}
    }catch{ /* The complete saved model remains a separate immutable fallback. */ }
    automatic=false;const body=validateHouseTransitions(await fetchSourceBody(fallback));
    if(body.version!==fallback.version)throw Error("Saved model version differs");return body;
  };
  return {select,
    leave(){active=false;ticket++;observer?.disconnect();delete summary.dataset.transitionState;delete summary.dataset.transitionVersion;
      legend.textContent=legacyLegend;key.setAttribute("aria-label",legacyKey);
      delete host.dataset.transitionVersion;delete host.dataset.transitionAutomatic;
      if(table)table.hidden=true;if(methods)methods.hidden=true;
      for(const selector of ["#estimate-outcome-check","[data-statewide-source-table]",".driver-research"]){const node=root.querySelector(selector);if(node)node.hidden=false;}},
    async render(options){
      active=true;const current=++ticket;selected=options.state;view=options.view;units=options.units;observer?.disconnect();
      host.replaceChildren(element("p","Loading the complete all-50-state House transition model…","caption"));summary.replaceChildren();detail.replaceChildren();summary.hidden=true;detail.hidden=true;
      if(table)table.hidden=false;if(methods)methods.hidden=false;
      for(const selector of ["#estimate-outcome-check","[data-statewide-source-table]",".driver-research"]){const node=root.querySelector(selector);if(node)node.hidden=true;}
      try{
        data ||= await(promise ||= load());if(!active||current!==ticket||!options.isCurrent())return;
        const factor=scale(units),metric=field();
        if(table)table.querySelector("p").textContent=`Modeled contributions to the reported ${units==="margin"?"D−R margin":"Democratic share of D+R"} change, in percentage points. Every state uses whole-state totals; changed candidate coverage is context, not a reason to omit the state. Matching totals is a constraint, not validation of individual histories.`;
        const bound=Math.max(1,Math.ceil(Math.max(...data.rows.flatMap(row=>["switching","staying_home"].flatMap(key=>{const r=row.sensitivity["contribution_"+key];return[Math.abs(r.minimum*factor),Math.abs(r.maximum*factor)];})))/5)*5);
        host.dataset.driverMap=view;host.dataset.transitionVersion=data.version;host.dataset.transitionAutomatic=String(automatic);
        root.querySelector("[data-driver-map-title]").textContent=transitionViews.find(([key])=>key===view)[1];
        root.querySelector("[data-driver-scale-min]").textContent=`−${bound} pp`;root.querySelector("[data-driver-scale-max]").textContent=`+${bound} pp`;
        root.querySelector(".driver-map-ticks").children[1].textContent="0";root.querySelector(".driver-map-ramp").style.background="";
        root.querySelector(".driver-map-key").setAttribute("aria-label","Shared signed modeled House contribution scale in percentage points");
        const directions=root.querySelector(".driver-map-directions").children;directions[0].textContent="Republican direction";directions[1].textContent="Democratic direction";
        root.querySelector(".driver-reading-note").textContent="All 50 states have a modeled comparison. Contributions are points, not percentages of people. Gray is D.C., which has no voting House seat.";
        root.querySelector(".driver-no-model").lastChild.textContent="No voting-House model · D.C.";
        root.querySelector("[data-driver-comparison-caution]").hidden=true;
        root.querySelector("[data-driver-reading-title]").textContent=`Modeled contribution to ${units==="margin"?"the D−R margin":"Democratic share of D+R"} change`;
        root.querySelector("[data-driver-reading-meaning]").textContent="Switching and prior House voters casting no ballot are estimated together from whole-state House counts and turnout benchmarks. Missing House choices and eligibility changes are not counted as staying home.";
        root.querySelector("[data-driver-reading-example]").textContent="Positive points move the reported result toward Democrats; negative points toward Republicans. Conditional models are not identified histories or evidence of persuasion.";
        const svg=svgElement("svg",{viewBox:"0 0 1000 640",role:"group","aria-label":"All 50 states · modeled "+metric+" contribution","data-scale":bound});
        for(const item of items){
          const code=item.feature.properties.STUSAB,row=data.rows.find(row=>row.state_code===code),value=row?row.point.contributions_pp[metric]*factor:null;
          const path=svgElement("path",{d:item.d,fill:effectFill(value,bound),class:"driver-state","fill-rule":"evenodd","pointer-events":"visibleFill","data-state-code":code,"data-model-value":value??"","data-house-transition":String(value!==null),role:"button",tabindex:"-1","aria-label":`${names[code]} · modeled ${metric}: ${value===null?"unavailable":pp(value)}`});
          const title=svgElement("title",{});title.textContent=path.getAttribute("aria-label");path.append(title);
          path.addEventListener("click",()=>select(code));path.addEventListener("keydown",e=>{if(["Enter"," "].includes(e.key)){e.preventDefault();select(code);}});svg.append(path);
        }
        for(const [x,text]of [[60,"Alaska"],[310,"Hawaii · insets not to scale"]]){const label=svgElement("text",{x,y:625,class:"driver-inset-label"});label.textContent=text;svg.append(label);}
        host.replaceChildren(svg);
        const hits=()=>{svg.querySelectorAll("[data-driver-hit]").forEach(e=>e.remove());const s=svg.getBoundingClientRect().width/1000;if(s>0)for(const path of svg.querySelectorAll(".driver-state")){const b=path.getBBox();if(b.width*s>=6||b.height*s>=6)continue;const hit=svgElement("circle",{cx:b.x+b.width/2,cy:b.y+b.height/2,r:3/s,fill:"transparent","data-driver-hit":path.dataset.stateCode,"aria-hidden":"true"});hit.addEventListener("click",()=>select(path.dataset.stateCode));svg.append(hit);}};
        hits();observer=new ResizeObserver(hits);observer.observe(svg);
        if(table){const tbody=table.querySelector("tbody");tbody.replaceChildren();for(const row of data.rows){const tr=element("tr"),name=element("button",names[row.state_code]),rounded=roundedTransitionContributions(row.point,units);name.type="button";name.addEventListener("click",()=>select(row.state_code));const th=element("th");th.scope="row";th.append(name);tr.append(th);tr.dataset.houseTransitionState=row.state_code;for(const value of [row.point.recorded_change_pp*factor,rounded.switching,rounded.staying_home])tr.append(element("td",pp(value),"numeric"));tbody.append(tr);}}
        select(selected);
      }catch(error){if(!active||current!==ticket||!options.isCurrent())return;promise=null;host.replaceChildren(element("p",`All-state model unavailable: ${error.message}. Saved state comparisons remain below; no values are filled with zero.`,"caption"));}
    },
  };
}

import { loadAutomaticRuntime, setAutomaticRuntimeStatus, automaticStatewideSourceReceipt } from "./participation-automatic-runtime.js";
import { demographicLabels, norcFamilies, norcAssociations } from "./participation-norc-house.js";

const PREFIX = "house/statewide-source/";
const CONTRACT = "participation.statewide_source_model.v1";
const INDEX = "participation.statewide_source_index.v1";
const METHOD = "uniform_source_frame_house24_bridge_to_house26_v1";
const STATES = "AK AL AR AZ CA CO CT DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY".split(" ").sort();
const PROFILES = norcAssociations.map(([key]) => key);
const FAMILIES = norcFamilies.map(([key]) => key);
const TERMS = ["switching", "exit", "entry", "other_choice", "unresolved"];
const METRICS = [...TERMS, "net_participation", "total_change", "retaining"];
const hash = /^[a-f0-9]{64}$/;
const finite = value => typeof value === "number" && Number.isFinite(value);
const close = (a,b) => finite(a) && finite(b) && Math.abs(a-b) < 1e-7;
const require = (condition, message) => { if (!condition) throw new Error(message); };
const equal = (a,b) => JSON.stringify(a) === JSON.stringify(b);

export const statewideSourceViews = [
  ["source_total", "Modeled House change · all 50 states"],
  ["source_switching", "Modeled switching contribution · source frame"],
  ["source_participation", "Modeled net participation contribution · source frame"],
  ["source_entry", "Modeled no House choice → D/R · source frame"],
  ["source_exit", "Modeled D/R → no House choice · source frame"],
  ["source_other", "Other / unassigned choice · source frame"],
  ["source_unresolved", "Unresolved responses · source frame"],
  ["source_retaining", "Kept party · source-model share"],
];
export const isStatewideSourceView = key => statewideSourceViews.some(([value]) => value === key);
const viewMetric = {source_total:"total_change",source_switching:"switching",
  source_participation:"net_participation",source_entry:"entry",source_exit:"exit",
  source_other:"other_choice",source_unresolved:"unresolved",source_retaining:"retaining"};

export function sourceMetricScale(metric, units) {
  require(["margin","democratic_two_party_share"].includes(units),"Unknown source-model change units");
  return metric === "retaining" ? 100 : units === "margin" ? 1 : .5;
}

function metadata(value) {
  require(value?.method === METHOD && hash.test(value.version) && value.states === 50
    && equal(value.profiles,PROFILES) && equal(value.families,FAMILIES)
    && value.default_family === FAMILIES[0] && value.default_profile === "original"
    && value.return_conditioned === false && value.population_calibrated === false
    && value.previous_partisan_return_constraints_used === false
    && value.current_partisan_return_constraints_used === false
    && value.source_weight_calibration_independent_of_returns_qualified === false
    && value.source_models_refitted === false && value.model_units_are_people === false
    && value.estimated_baseline_not_actual_2024_house_counts === true
    && value.nonmajor_choices_remain_other === true && value.unresolved_response_is_not_nonvote === true
    && value.synthetic_flow_table_is_not_linked_histories === true
    && value.measured_staying_home === null && value.actual_first_ever_voting === null
    && value.confidence_intervals === null && value.local_allocation === false
    && value.interview_dates === null && value.source_fit_date === null
    && value.input_years?.ap2024 === 2024 && value.input_years.chep === 2026
    && Object.keys(value.source_input_sha256 || {}).sort().join() === "ap2024,chep"
    && Object.values(value.source_input_sha256).every(v=>typeof v === "string" && hash.test(v))
    && value.sensitivity?.variants === 27 && value.sensitivity.confidence_interval === false
    && value.sensitivity.complete_sampling_or_transport_uncertainty === false,
  "Statewide estimates must remain uniform, source-only and explicitly uncalibrated");
  return value;
}

function bodyPin(value) {
  require(value?.compression === "gzip" && value.media_type === "application/json"
    && Number.isSafeInteger(value.bytes) && value.bytes > 0 && value.bytes < 5_000_000
    && Number.isSafeInteger(value.decoded_bytes) && value.decoded_bytes > 0 && value.decoded_bytes < 30_000_000
    && hash.test(value.sha256) && hash.test(value.decoded_sha256), "Invalid source-model body pin");
}

export function validateStatewideIndex(value) {
  require(value?.contract === INDEX, "Unknown statewide source index");
  metadata(value.metadata);
  require(equal(Object.keys(value.profiles || {}).sort(),[...PROFILES].sort()), "Source profile inventory differs");
  for (const profile of PROFILES) {
    bodyPin(value.profiles[profile]);
    require(value.profiles[profile].path === PREFIX + profile + ".json.gz", "Source profile path differs");
  }
  return value;
}

function matrix(value, normalized=false) {
  require(Array.isArray(value) && value.length === 5
    && value.every(row=>Array.isArray(row) && row.length === 5 && row.every(v=>finite(v) && v >= 0)),
  "Invalid source DRONU matrix");
  const mass=value.flat().reduce((a,b)=>a+b,0);
  require(normalized ? close(mass,1) : mass <= 1+1e-7, "Source matrix mass differs");
}

function point(value, overall=false) {
  require(value && TERMS.every(key=>finite(value.contributions_pp?.[key]))
    && close(TERMS.reduce((sum,key)=>sum+value.contributions_pp[key],0),value.allocated_change_pp)
    && close(value.net_participation_pp,value.contributions_pp.entry+value.contributions_pp.exit),
  "Source contributions do not reconcile");
  if (overall) require(close(value.current_margin_pp-value.previous_margin_pp,value.total_change_pp)
    && close(value.allocated_change_pp,value.total_change_pp), "Source endpoints do not reconcile");
}

export function sourceMetric(row, metric, group="") {
  const selected=group ? row?.groups.find(g=>g.dimension+"|"+g.group === group) : row;
  if (!selected?.available) return null;
  if (metric === "retaining") return selected.gross_outcomes?.retaining ?? null;
  if (metric === "total_change") return selected.point.allocated_change_pp;
  if (metric === "net_participation") return selected.point.net_participation_pp;
  return selected.point.contributions_pp[metric] ?? null;
}

export function validateStatewideProfile(value, index, profile) {
  require(value?.contract === CONTRACT && value.profile === profile && PROFILES.includes(profile)
    && equal(value.metadata,index.metadata), "Statewide profile belongs to a different source version");
  metadata(value.metadata);
  require(equal(Object.keys(value.models || {}).sort(),[...FAMILIES].sort()), "Source model families differ");
  let masks;
  for (const model of Object.values(value.models)) {
    require(Array.isArray(model.rows) && model.rows.length === 50
      && equal(model.rows.map(row=>row.state_code).sort(),STATES), "All 50 source states are required");
    for (const row of model.rows) {
      require(row.available === true && Array.isArray(row.groups), "A source state was silently withheld");
      matrix(row.joint,true);point(row.point,true);
      const before=row.joint.map(values=>values.reduce((a,b)=>a+b,0));
      const after=Array.from({length:5},(_,j)=>row.joint.reduce((sum,values)=>sum+values[j],0));
      require(close(100*(before[0]-before[1])/(before[0]+before[1]),row.point.previous_margin_pp)
        && close(100*(after[0]-after[1])/(after[0]+after[1]),row.point.current_margin_pp),
      "Source matrix and displayed endpoints differ");
      const ids=new Set();
      for (const item of [row,...row.groups]) {
        if (item !== row) {
          const key=item.dimension+"|"+item.group;
          require(demographicLabels[item.dimension] && !ids.has(key) && typeof item.group === "string"
            && typeof item.label === "string" && typeof item.available === "boolean", "Source demographic identity differs");
          ids.add(key);
          if (item.available) {matrix(item.joint);point(item.point);}
          else require(item.point === null && item.joint === null && item.gross_outcomes === null,
            "Held demographic source statistics were exposed");
        }
        if (item.available) {
          const previousMajor=item.joint[0].reduce((a,b)=>a+b,0)+item.joint[1].reduce((a,b)=>a+b,0);
          const retaining=item.gross_outcomes?.retaining ?? null;
          require(previousMajor>0?close(retaining,(item.joint[0][0]+item.joint[1][1])/previousMajor):retaining===null,
            "Source retention denominator differs from its matrix");
        }
        for (const metric of METRICS) {
          const estimate=sourceMetric(row,metric,item===row?"":item.dimension+"|"+item.group);
          const range=item.sensitivity?.[metric];
          require(estimate === null ? range === null : range && finite(range.minimum) && finite(range.maximum)
            && range.minimum <= estimate+1e-7 && range.maximum >= estimate-1e-7,
          "Source sensitivity omits an estimate or invents a held statistic");
        }
      }
      for (const dimension of new Set(row.groups.map(g=>g.dimension)))
        for (const key of TERMS) require(close(row.groups.filter(g=>g.available && g.dimension===dimension)
          .reduce((sum,g)=>sum+g.point.contributions_pp[key],0),row.point.contributions_pp[key]),
        "Source demographic partition differs from its state");
    }
    const mask=model.rows.map(row=>[row.state_code,row.groups.map(g=>[g.dimension,g.group,g.label,g.available])]);
    if (masks) require(equal(mask,masks), "Source families changed their demographic disclosure masks");
    masks=mask;
  }
  return value;
}

export async function fetchSourceBody(receipt, fetcher=fetch) {
  bodyPin(receipt);
  require(/^https:\/\/raw\.githubusercontent\.com\/hanshanley\/(?:voter-participation|margin_of_error)\/[a-f0-9]{40}\//.test(receipt.url),
    "Source estimates must have an immutable project URL");
  const response=await fetcher(receipt.url,{signal:AbortSignal.timeout(20000)});
  require(response.ok,`Source model: HTTP ${response.status}`);
  const bytes=await response.arrayBuffer();
  const digest=async data=>Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",data)),
    b=>b.toString(16).padStart(2,"0")).join("");
  require(bytes.byteLength===receipt.bytes && await digest(bytes)===receipt.sha256,"Source-model checksum differs");
  const decoded=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
  require(decoded.byteLength===receipt.decoded_bytes && await digest(decoded)===receipt.decoded_sha256,
    "Decoded source-model checksum differs");
  return JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(decoded));
}

export function statewideSourceController(root, fallback, {items,names,effectFill,element,svgElement,onSelectState}) {
  const host=root.querySelector("[data-driver-map]"),status=root.querySelector("[data-driver-status]");
  const summary=root.querySelector("[data-driver-summary]"),detail=root.querySelector("[data-driver-detail]");
  const group=root.querySelector("[data-driver-group]"),family=root.querySelector("[data-driver-family]");
  const association=root.querySelector("[data-driver-association]"),units=root.querySelector("[data-driver-units]");
  let bundle,bundlePromise,fallbackPromise,model,active=false,ticket=0,selected="TX",view="source_total",observer;
  let selectedUnits="democratic_two_party_share",isCurrent=()=>true;
  const profiles=new Map();
  const rangeFor=row=>{
    const item=group.value?row?.groups.find(g=>g.dimension+"|"+g.group===group.value):row;
    return item?.sensitivity?.[viewMetric[view]] ?? null;
  };
  const factor=()=>sourceMetricScale(viewMetric[view],selectedUnits);
  const points=(value,retention=viewMetric[view]==="retaining")=>value===null?"Unavailable":retention
    ?`${value.toFixed(1)}%`:`${value>0?"+":""}${value.toFixed(2)} pp`;
  const fallbackBundle=async()=>{
    const index=validateStatewideIndex(await fetchSourceBody(fallback));
    require(index.metadata.version===fallback.version && fallback.url===new URL(PREFIX+"index.json.gz",fallback.base_url).href,
      "Saved source model belongs to a different immutable bundle");
    return {index,base:fallback.base_url,automatic:false};
  };
  const loadProfile=(profile,owner)=>{
    const receipt=owner.index.profiles[profile],key=receipt.sha256;
    if (!profiles.has(key)) {
      const request=fetchSourceBody({...receipt,url:new URL(receipt.path,owner.base).href})
        .then(value=>validateStatewideProfile(value,owner.index,profile))
        .catch(error=>{if(profiles.get(key)===request)profiles.delete(key);throw error;});
      profiles.set(key,request);
    }
    return profiles.get(key);
  };
  const loadBundle=async()=>{
    try {
      const manifest=await loadAutomaticRuntime(),receipt=automaticStatewideSourceReceipt(manifest);
      if (receipt) {
        require(receipt.contract===INDEX && receipt.path===PREFIX+"index.json.gz"
          && receipt.url===new URL(receipt.path,manifest.house_sources.base_url.replace(/\/?$/,"/")).href,
        "Automatic source index is not bound to the accepted runtime");
        const index=validateStatewideIndex(await fetchSourceBody(receipt));
        require(index.metadata.version===receipt.version,"Automatic source index version differs");
        return {index,base:manifest.house_sources.base_url.replace(/\/?$/,"/"),automatic:true};
      }
    } catch { /* The complete immutable source release remains an independent fallback. */ }
    return fallbackBundle();
  };
  const select=code=>{
    if (!active || !isCurrent()) return;
    selected=code;
    onSelectState?.(code);
    root.querySelector("[data-driver-state]").value=code;
    if (!model || !bundle) return;
    const row=model.rows.find(r=>r.state_code===code);
    for (const path of host.querySelectorAll("path.driver-state")) {
      const chosen=path.dataset.stateCode===code;path.classList.toggle("selected",chosen);path.tabIndex=chosen?0:-1;
      if (chosen) path.parentNode.append(path);
    }
    for (const hit of host.querySelectorAll("[data-driver-hit]")) hit.parentNode.append(hit);
    const primary=element("div",null,"driver-equation");
    primary.append(element("h3",`${names[code] || "Select a state"}${row?" · source model":""}`));
    summary.replaceChildren(primary);
    for (const key of Object.keys(summary.dataset))
      if (key.startsWith("norc") || key.startsWith("recorded")) delete summary.dataset[key];
    summary.dataset.sourceModelState=code;summary.dataset.sourceModelVersion=bundle.index.metadata.version;
    detail.replaceChildren();summary.hidden=false;detail.hidden=true;
    if (!row) {
      primary.append(element("p",code==="DC"?"D.C. has no CHEP sample; no estimate is invented.":"Select a state for its source-model estimate.","caption"));return;
    }
    const metric=viewMetric[view],value=sourceMetric(row,metric,group.value),range=rangeFor(row);
    const headline=element("p",null,"driver-primary");
    if (value===null) headline.textContent=metric==="retaining" && row.groups.find(g=>g.dimension+"|"+g.group===group.value)?.available
      ?"Retention is unavailable: this source group has no previous-D/R denominator.":"This source demographic cell is withheld, not zero.";
    else headline.append(element("span",points(value*factor()),"driver-value"),
      element("span",` ${metric==="retaining"?"retained previous-D/R source share":
        group.value?"contribution to statewide change":"source-model estimate"}`,"driver-value-label"));
    primary.append(headline,
    element("p",range?`Model sensitivity: ${points(range.minimum*factor())} to ${points(range.maximum*factor())}. Not a confidence interval.`:
      "No demographic estimate is filled from another category.","caption"),
    element("p","Unconditioned survey-source model · not population calibrated.","caption"),
    element("p","Input vintages: AP 2024 / CHEP 2026. Interview dates not supplied.","caption"));
    summary.dataset.sourceModelState=code;summary.dataset.sourceModelVersion=bundle.index.metadata.version;
    delete summary.dataset.norcHold;delete summary.dataset.norcState;
    detail.append(element("h4","What this estimate means"),element("p",
      "The same fitted-source method is used in all 50 states. The modeled 2024 House baseline is bridged from AP2024 President/House responses and CHEP recalled presidential choice. Both endpoints describe the CHEP2026 source-weighted frame, not either year's observed statewide electorate.","caption"));
    if (value!==null) {
      const table=element("table"),head=element("thead"),heading=element("tr"),body=element("tbody");
      for (const text of ["Term","Estimate","Model sensitivity"]) heading.append(element("th",text));head.append(heading);table.append(head);
      for (const [key,label] of [["switching","Modeled switching"],["net_participation","Modeled net participation"],
        ["other_choice","Other / unassigned choice"],["unresolved","Unresolved responses"],["total_change","Total modeled change"]]) {
        const item=group.value?row.groups.find(g=>g.dimension+"|"+g.group===group.value):row;
        const value=sourceMetric(row,key,group.value),bounds=item.sensitivity[key],tr=element("tr");
        tr.append(element("th",label),element("td",points(value* (selectedUnits==="margin"?1:.5),false),"numeric"),
          element("td",`${points(bounds.minimum*(selectedUnits==="margin"?1:.5),false)} to ${points(bounds.maximum*(selectedUnits==="margin"?1:.5),false)}`,"numeric"));body.append(tr);
      }
      table.append(body);const wrap=element("div",null,"table-wrap");wrap.append(table);detail.append(wrap);
    }
    detail.append(element("p","Ranges span three model families, three association profiles and half/base/double persistence. They omit unquantified sampling, weight-target, recall, baseline-bridge and population-transport uncertainty. They are not design confidence intervals.","caption"),
      element("p","N is a modeled or source-reported no-House-choice category; U remains unresolved. Neither category measures confirmed staying home, first-ever voting, deaths or migration. Nonmajor-party choices stay Other; no coalition is reassigned. D/R shares exclude Other. Group contributions are not group turnout rates.","caption"),
      element("p",`Source version ${bundle.index.metadata.version.slice(0,12)}. Survey field and fit dates are not supplied by these public fitted priors. Publication or election-return update times are not substituted for those dates.`,"caption"),
      element("p","Source weight targets are not independently qualified here. No partisan returns constrain this projection; that is not proof that the original source weights were independent of election outcomes. Recorded and return-constrained comparisons remain separate choices.","caption"));
    detail.hidden=false;
  };
  return {
    leave(){active=false;ticket++;observer?.disconnect();delete summary.dataset.sourceModelState;
      delete summary.dataset.sourceModelVersion;
      for (const key of Object.keys(host.dataset)) if(key.startsWith("sourceModel"))delete host.dataset[key];},select,
    async render(options) {
      active=true;const current=++ticket;isCurrent=options.isCurrent;selected=options.state;
      view=options.view;selectedUnits=options.units;observer?.disconnect();model=undefined;
      host.replaceChildren();summary.replaceChildren();detail.replaceChildren();summary.hidden=true;detail.hidden=true;
      status.textContent="Loading checksum-verified source-model estimates for all 50 states.";
      for (const control of [family,association,units,group]) control.disabled=true;
      root.querySelector("[data-driver-group-control]").hidden=false;
      for (const control of [family,association,units]) control.closest("label").hidden=false;
      try {
        bundle ||= await (bundlePromise ||= loadBundle());
        const profile=association.value || "original";
        let owner=bundle,loaded;
        try {loaded=await loadProfile(profile,owner);}
        catch(error) {
          if (!owner.automatic) throw error;
          bundle=await (fallbackPromise ||= fallbackBundle());bundlePromise=Promise.resolve(bundle);
          owner=bundle;loaded=await loadProfile(profile,owner);
        }
        if (owner!==bundle) loaded=await loadProfile(profile,bundle);
        if (!active || current!==ticket || !isCurrent()) return;
        const selectedFamily=FAMILIES.includes(family.value)?family.value:FAMILIES[0];
        family.replaceChildren(...norcFamilies.map(([value,label])=>new Option(label,value)));family.value=selectedFamily;
        model=loaded.models[selectedFamily];
        const previous=group.value,groups=new Map();
        for (const row of model.rows) for (const g of row.groups) if (g.available)
          groups.set(g.dimension+"|"+g.group,`${demographicLabels[g.dimension]} · ${g.label}`);
        group.replaceChildren(new Option("Overall source frame",""),...[...groups].map(([value,label])=>new Option(label,value)));
        root.querySelector("[data-driver-group-control]").childNodes[0].textContent="Demographic group";
        if ([...group.options].some(o=>o.value===previous)) group.value=previous;
        for (const control of [family,association,units,group]) control.disabled=false;
        if (options.groupReset) group.value="";
        const metric=viewMetric[view],retention=metric==="retaining",multiplier=factor();
        const bound=retention?100:Math.max(1,Math.ceil(Math.max(0,...model.rows.flatMap(row=>{
          const item=group.value?row.groups.find(g=>g.dimension+"|"+g.group===group.value):row;
          const range=item?.sensitivity?.[metric];return range?[Math.abs(range.minimum*multiplier),Math.abs(range.maximum*multiplier)]:[];
        }))/5)*5);
        const label=statewideSourceViews.find(([key])=>key===view)[1];
        host.dataset.driverMap=view;host.dataset.sourceModelVersion=bundle.index.metadata.version;
        host.dataset.sourceModelFamily=selectedFamily;host.dataset.sourceModelProfile=profile;
        host.dataset.sourceModelUnits=selectedUnits;host.dataset.sourceModelGroup=group.value;
        root.querySelector("[data-driver-map-title]").textContent=label;
        root.querySelector("[data-driver-map-caption]").textContent="Uniform 2024-to-2026 House source-frame model, without partisan-return constraints. Not observed election swing, population turnout or individual histories.";
        root.querySelector(".driver-map-note").textContent="Every state uses the same source-only method. Gray demographic cells are withheld, not zero. Source D/R changes do not identify persuasion, staying home, entry, death or migration.";
        root.querySelector(".driver-reading-note").textContent="Gray means unavailable, not zero. All 50 states have overall source-model estimates; D.C. has no CHEP sample.";
        root.querySelector("[data-driver-scale-min]").textContent=retention?"0%":`-${bound} pp`;
        root.querySelector("[data-driver-scale-max]").textContent=retention?"100%":`+${bound} pp`;
        root.querySelector(".driver-map-ticks").children[1].textContent=retention?"50%":"0";
        root.querySelector(".driver-map-ramp").style.background=retention?"linear-gradient(to right,#f1eee6,#2c6c75)":"";
        root.querySelector(".driver-map-key").setAttribute("aria-label",retention?"Modeled retained-party share":`Modeled ${selectedUnits==="margin"?"D-R margin":"Democratic two-party-share"} change`);
        const directions=root.querySelector(".driver-map-directions").children;
        directions[0].textContent=retention?"Less retained":"Republican direction";
        directions[1].textContent=retention?"More retained":"Democratic direction";
        root.querySelector(".driver-no-model").lastChild.textContent="D.C. / held source group";
        const caution=root.querySelector("[data-driver-comparison-caution]");if(caution)caution.hidden=true;
        const count=model.rows.filter(row=>sourceMetric(row,metric,group.value)!==null).length;
        status.textContent=`${count} statewide source-model estimates${group.value?" for the selected group":"; all 50 states"}. No partisan returns constrain them. D.C. has no CHEP sample. Model sensitivity is not a confidence interval.`;
        setAutomaticRuntimeStatus("statewide-source",bundle.automatic?"active":"fallback",
          "Uniform fitted-source model; source dates do not advance with election returns.");
        const svg=svgElement("svg",{viewBox:"0 0 1000 640",role:"group","aria-label":label+" by state","data-scale":bound});
        for (const item of items) {
          const code=item.feature.properties.STUSAB,row=model.rows.find(r=>r.state_code===code);
          const value=sourceMetric(row,metric,group.value),scaled=value===null?null:value*multiplier;
          const path=svgElement("path",{d:item.d,fill:effectFill(scaled,bound),
            class:"driver-state","fill-rule":"evenodd","pointer-events":"visibleFill","data-state-code":code,
            "data-model-value":scaled??"","data-source-model":String(value!==null),"data-return-conditioned":"false",
            role:"button",tabindex:"-1","aria-label":`${names[code]} · ${label}: ${points(scaled)}. Source frame; not observed swing.`});
          path.append(svgElement("title",{}));path.firstChild.textContent=path.getAttribute("aria-label");
          path.addEventListener("click",()=>select(code));path.addEventListener("keydown",event=>{
            if(["Enter"," "].includes(event.key)){event.preventDefault();select(code);}
          });svg.append(path);
        }
        for(const [x,text] of [[60,"Alaska"],[310,"Hawaii · insets not to scale"]]){
          const label=svgElement("text",{x,y:625,class:"driver-inset-label"});label.textContent=text;svg.append(label);
        }
        host.replaceChildren(svg);
        const hits=()=>{
          svg.querySelectorAll("[data-driver-hit]").forEach(e=>e.remove());const scale=svg.getBoundingClientRect().width/1000;
          if(scale>0)for(const path of svg.querySelectorAll(".driver-state")){
            const box=path.getBBox();if(box.width*scale>=6||box.height*scale>=6)continue;
            const hit=svgElement("circle",{cx:box.x+box.width/2,cy:box.y+box.height/2,r:3/scale,
              fill:"transparent","data-driver-hit":path.dataset.stateCode,"aria-hidden":"true"});
            hit.addEventListener("click",()=>select(path.dataset.stateCode));svg.append(hit);
          }
        };hits();observer=new ResizeObserver(hits);observer.observe(svg);select(selected);
      } catch(error) {
        if(!active||current!==ticket||!isCurrent())return;
        status.textContent=`Source-model map unavailable: ${error.message}. The saved 50-state source-model table remains below; no values are zero-filled.`;
        const retry=element("button","Retry statewide source model");retry.type="button";
        retry.addEventListener("click",()=>{bundle=null;bundlePromise=null;fallbackPromise=null;profiles.clear();this.render(options);});host.replaceChildren(retry);
      }
    },
  };
}

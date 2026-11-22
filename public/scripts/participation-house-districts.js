import { loadAutomaticCongress } from "./participation-automatic-runtime.js";
import { validateCongressionalResults } from "./participation-congress.js";

const require = (condition, message) => { if (!condition) throw new Error(message); };
const fingerprint = value => /^[a-f0-9]{64}$/.test(value);
const fips = {
  AL:"01",AK:"02",AZ:"04",AR:"05",CA:"06",CO:"08",CT:"09",DE:"10",FL:"12",GA:"13",
  HI:"15",ID:"16",IL:"17",IN:"18",IA:"19",KS:"20",KY:"21",LA:"22",ME:"23",MD:"24",
  MA:"25",MI:"26",MN:"27",MS:"28",MO:"29",MT:"30",NE:"31",NV:"32",NH:"33",NJ:"34",
  NM:"35",NY:"36",NC:"37",ND:"38",OH:"39",OK:"40",OR:"41",PA:"42",RI:"44",SC:"45",
  SD:"46",TN:"47",TX:"48",UT:"49",VT:"50",VA:"51",WA:"53",WV:"54",WI:"55",WY:"56",
};
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const number = value => value == null ? "Not supplied" : value.toLocaleString("en-US");
const points = value => value === null ? "Not comparable" : `${value > 0 ? "+" : ""}${value.toFixed(2)} pp`;
const element = (tag, text, attrs = {}) => {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
};
const svgElement = (tag, attrs = {}) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
};

export function validateDistrictGeometry(data) {
  require(data?.contract === "participation.house_district_geometry.v1"
    && data.election_year === 2026 && data.congress === 120 && data.baseline_congress === 119
    && data.voting_districts === 435 && data.state_count === 50 && data.native_crs === "EPSG:4269"
    && data.display_method === "nad83_albers_north_up_display_only_topology_preserving_0.25_viewbox_units"
    && same(data.view_box, [0, 0, 1000, 640]) && Array.isArray(data.paths)
    && data.historical_votes_allocated === false && data.behavioral_models_allocated === false
    && data.legal_boundary_certification === false, "District geometry contract or vintage differs");
  for (const [phase, year, session] of [["previous",2025,119],["current",2026,120]]) {
    const sources = data.sources?.[phase];
    require(sources && same(Object.keys(sources).sort(), Object.keys(fips).sort())
      && Object.entries(fips).every(([state, code]) => {
        const source = sources[state], file = `tl_${year}_${code}_cd${session}.zip`;
        return source?.file === file && source.url === `https://www2.census.gov/geo/tiger/TIGER${year}/CD/${file}`
          && Number.isSafeInteger(source.bytes) && source.bytes > 0 && fingerprint(source.sha256);
      }), "District original source inventory differs");
  }
  const seen = new Set(), seats = new Map(), unassigned = [];
  for (const row of data.paths) {
    const code = row?.district_code, state = row?.state_code;
    require(Object.hasOwn(fips, state) && row.state_fips === fips[state]
      && typeof code === "string" && /^(?:[0-9]{2}|ZZ)$/.test(code)
      && row.geoid === fips[state] + code && !seen.has(row.geoid)
      && row.district === `${state}-${code === "00" ? "AL" : code}`
      && row.unassigned_area === (code === "ZZ") && fingerprint(row.native_rings_sha256),
    "District state, leading-zero identity or uniqueness differs");
    seen.add(row.geoid);
    require(typeof row.d === "string" && row.d.length > 10 && row.d.length < 500000
      && /^M[-0-9.,MLZ]+Z$/.test(row.d)
      && Array.isArray(row.point) && row.point.length === 2 && row.point.every(Number.isFinite)
      && Array.isArray(row.bounds) && row.bounds.length === 4 && row.bounds.every(Number.isFinite)
      && row.bounds[0] <= row.point[0] && row.point[0] <= row.bounds[2]
      && row.bounds[1] <= row.point[1] && row.point[1] <= row.bounds[3]
      && row.bounds[0] >= 0 && row.bounds[1] >= 0 && row.bounds[2] <= 1000 && row.bounds[3] <= 640,
    "District screen path or representative point differs");
    if (row.unassigned_area) unassigned.push(row.district);
    else {
      if (!seats.has(state)) seats.set(state, []);
      seats.get(state).push(code);
    }
  }
  require(seats.size === 50 && [...seats.values()].reduce((n, rows) => n + rows.length, 0) === 435
    && [...seats.values()].every(rows => same(rows.sort(), rows.length === 1 ? ["00"]
      : Array.from({length:rows.length}, (_, i) => String(i + 1).padStart(2, "0"))))
    && same(unassigned.sort(), ["CT-ZZ", "IL-ZZ", "NH-ZZ"]),
  "District voting-seat or unassigned-area inventory differs");
  return data;
}

export function bindDistrictResults(geometry, raw) {
  validateDistrictGeometry(geometry);
  const data = validateCongressionalResults(raw);
  const rows = data.races.filter(row => row.chamber === "house" && row.voting_house_seat
    && row.superseded_by_race_id === undefined);
  require(rows.length === 435 && new Set(rows.map(row => row.baseline?.district)).size === 435,
    "Current voting House district inventory differs");
  const byDistrict = new Map(rows.map(row => [row.baseline.district, row]));
  return geometry.paths.filter(path => !path.unassigned_area).map(path => {
    const row = byDistrict.get(path.district), boundary = row?.baseline?.boundary_eligibility;
    require(row && row.state_code === path.state_code && boundary?.state_fips === path.state_fips
      && boundary.district_code === path.district_code && boundary.current_congress === geometry.congress
      && boundary.previous_congress === geometry.baseline_congress
      && row.election_date === "2026-11-03" && row.candidate_votes_are_not_ballots_or_turnout === true,
    "District return and geometry identity differ");
    return {path, row};
  });
}

export function districtValue(row, units) {
  require(["margin", "democratic_two_party_share"].includes(units), "Unknown district change units");
  return row.qualified_comparison ? row.qualified_margin_change_pp
    * (units === "margin" ? 1 : .5) : null;
}

export function districtFill(value, bound) {
  require(value === null || Number.isFinite(value), "Invalid district map value");
  require(Number.isFinite(bound) && bound > 0, "Invalid district scale");
  if (value === null) return "#dadbd6";
  const neutral = [243,241,234], end = value < 0 ? [170,81,78] : [53,107,158];
  const weight = Math.min(1, Math.abs(value) / bound);
  return "#" + neutral.map((v, i) => Math.round(v + weight * (end[i] - v))
    .toString(16).padStart(2, "0")).join("");
}

export async function fetchDistrictGeometry(receipt, fetcher = fetch) {
  require(receipt?.contract === "participation.house_district_geometry.v1"
    && /^https:\/\/raw\.githubusercontent\.com\/hanshanley\/voter-participation\/[a-f0-9]{40}\/data\/congressional-geometry\/20261118-02\/district-paths\.json\.gz$/.test(receipt.url)
    && Number.isSafeInteger(receipt.bytes) && receipt.bytes > 0 && receipt.bytes < 1000000
    && Number.isSafeInteger(receipt.decoded_bytes) && receipt.decoded_bytes > 0
    && receipt.decoded_bytes < 5000000 && fingerprint(receipt.sha256)
    && fingerprint(receipt.decoded_sha256), "District geometry receipt differs");
  const response = await fetcher(receipt.url, {signal:AbortSignal.timeout(20000)});
  require(response.ok, `District geometry: HTTP ${response.status}`);
  const bytes = await response.arrayBuffer();
  const digest = async body => Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", body)),
    byte => byte.toString(16).padStart(2, "0")).join("");
  require(bytes.byteLength === receipt.bytes && await digest(bytes) === receipt.sha256,
    "District geometry checksum differs");
  const decoded = await new Response(new Blob([bytes]).stream().pipeThrough(
    new DecompressionStream("gzip"))).arrayBuffer();
  require(decoded.byteLength === receipt.decoded_bytes
    && await digest(decoded) === receipt.decoded_sha256, "District decoded geometry checksum differs");
  return validateDistrictGeometry(JSON.parse(new TextDecoder("utf-8", {fatal:true}).decode(decoded)));
}

export function houseDistrictController(root, receipt, {loadCongress = loadAutomaticCongress,
  loadGeometry = fetchDistrictGeometry, onSelectState = () => {}} = {}) {
  const host = root.querySelector("[data-driver-map]");
  const status = root.querySelector("[data-driver-status]");
  const detail = root.querySelector("[data-driver-detail]");
  const summary = root.querySelector("[data-driver-summary]");
  const control = root.querySelector("[data-driver-district]");
  let ticket = 0, geometryPromise, frame, selected, units, scope = "", observer, hitGroup;
  let visible = [], paths = new Map(), active = false;
  const stop = () => { active = false; ticket++; observer?.disconnect(); };
  const select = (district, focus = false) => {
    const item = visible.find(item => item.path.district === district);
    if (!active || !item) return;
    selected = district; control.value = district;
    const {row, path} = item, value = districtValue(row, units);
    for (const [key, node] of paths) {
      node.classList.toggle("selected", key === district);
      node.setAttribute("tabindex", key === district ? "0" : "-1");
    }
    const node = paths.get(district); node.parentNode.append(node);
    if (hitGroup) node.parentNode.append(hitGroup);
    if (focus) node.focus();
    onSelectState(path.state_code);
    summary.replaceChildren(element("h3", `${district} · House · 2024 to 2026`),
      element("p", row.qualified_comparison ? `${points(value)} ${units === "margin"
        ? "D-R margin" : "Democratic two-party-share"} change.` : "Comparison held; raw counts remain available.",
      {class:"driver-equation"}));
    detail.replaceChildren(element("h4", `${district} · recorded candidate counts`));
    const table = element("table"), head = element("tr"), body = element("tbody");
    for (const label of ["Party group","2024","2026"]) head.append(element("th",label,{scope:"col"}));
    const thead = element("thead"); thead.append(head); table.append(thead);
    for (const [party,label] of [["D","Democratic"],["R","Republican"],["O","Other / write-in"],["U","Unresolved party"]]) {
      const tr = element("tr",null,{"data-district-party":party});
      tr.append(element("th",label,{scope:"row"}),element("td",number(row.previous?.[party]),{class:"numeric"}),
        element("td",number(row[party]),{class:"numeric"})); body.append(tr);
    }
    table.append(body);
    const wrapper = element("div",null,{class:"table-wrap"}); wrapper.append(table); detail.append(wrapper);
    detail.append(element("p", row.comparison_holds.length
      ? `Held: ${row.comparison_holds.join("; ")}.`
      : "Recorded comparison passes the exported election, party and block-boundary rules. It is not measured preference change.",
    {class:"caption", "data-district-hold":String(!row.qualified_comparison)}),
    element("p", `Source status: ${row.freshness.replaceAll("_"," ")}. Native update: `
      + `${row.source_updated_at || "Not supplied"}. Round: ${row.round}. `
      + "Counting status and source clocks are not certification.", {class:"caption"}),
    element("p", "Candidate votes are not ballots cast or unique voters. Other/write-ins are retained but excluded "
      + "from the two-party denominator. No district turnout, switching or staying-home model is inferred.",
    {class:"caption"}),
    element("p", "Outlines: native Census CD120/2026 TIGER display context; CD119/2025 originals are retained. "
      + "Screen simplification is not analytical geography or legal boundary certification.", {class:"caption"}));
    if (path.state_code === "MO") detail.append(element("p",
      "Missouri version caution: the native archive was acquired November 18. Its metadata describes a plan reversion; "
      + "the separate Census correction page could not be acquired. This display does not certify the effective legal plan "
      + "or override any exported boundary hold.",{class:"caption"}));
    const links = [
      [row.source.url,"Original return source"],
      [new URL("congressional/congress-comparisons.csv", frame.declaration.base_url.replace(/\/?$/,"/")).href,
        "Every raw and qualified comparison · CSV"],
      [new URL("congressional/queries.json.gz", frame.declaration.base_url.replace(/\/?$/,"/")).href,
        "Complete candidate and boundary queries · JSON gzip"],
      [frame.manifest.complete_download.url,"Complete current source and analytical package · ZIP"],
    ];
    if (receipt?.complete_download?.url) links.push([receipt.complete_download.url,
      "All 100 geography originals, queries and reproduction code · ZIP"]);
    for (const [href,label] of links) detail.append(element("a",label,{href}),document.createTextNode(" · "));
    summary.hidden = false; detail.hidden = false;
  };
  const draw = () => {
    if (!active || !frame) return;
    observer?.disconnect();hitGroup=null;
    visible = frame.items.filter(item => !scope || item.path.state_code === scope);
    const values = frame.items.map(item => districtValue(item.row, units)).filter(value => value !== null);
    const bound = Math.max(1, Math.ceil(Math.max(0,...values.map(Math.abs)) / 5) * 5);
    control.replaceChildren(new Option("Select a district...", ""),
      ...visible.map(item => new Option(`${item.path.district}${item.row.qualified_comparison ? "" : " · held"}`,item.path.district)));
    control.disabled = !visible.length;
    const qualified = frame.items.filter(item => item.row.qualified_comparison).length;
    status.textContent = `${qualified} comparable district changes; ${435-qualified} held. `
      + "All 435 voting districts have current source records and Census outlines. "
      + "Blue is a Democratic shift; red is a Republican shift; intensity shows magnitude. "
      + `Snapshot ${frame.manifest.version.slice(0,12)}. `
      + (scope === "DC" ? "D.C. has no voting House seat in this 435-seat product." : "");
    root.querySelector("[data-driver-map-title]").textContent = "House district change";
    root.querySelector("[data-driver-map-caption]").textContent = "2024 to automatically refreshed 2026 House returns. "
      + "Neutral hatching means held, not zero change. Select a district for both years, source dates and the exact reason. "
      + "Use State to enlarge an area, or the District list for small districts.";
    root.querySelector(".driver-map-note").textContent = "Only exported qualified district comparisons receive directional color. "
      + "Changed or split-block boundaries and incompatible party, coverage or election rounds remain held. "
      + "No historical votes are allocated; no statewide behavioral estimates are spread onto districts.";
    root.querySelector("[data-driver-scale-min]").textContent = `-${bound} pp`;
    root.querySelector("[data-driver-scale-max]").textContent = `+${bound} pp`;
    root.querySelector(".driver-map-ticks").children[1].textContent = "0";
    root.querySelector(".driver-map-ramp").style.background = "linear-gradient(to right,#aa514e,#f3f1ea,#356b9e)";
    root.querySelector(".driver-map-key").setAttribute("aria-label", `Signed ${units === "margin"
      ? "D-R margin" : "Democratic two-party-share"} change by district`);
    const directions = root.querySelector(".driver-map-directions").children;
    directions[0].textContent = "Republican shift"; directions[1].textContent = "Democratic shift";
    root.querySelector(".driver-no-model").lastChild.textContent = "Held comparison";
    const caution = root.querySelector("[data-driver-comparison-caution]"); if (caution) caution.hidden = true;
    let box = [0,0,1000,640];
    if (scope && visible.length) {
      const bounds = visible.map(item => item.path.bounds);
      const x = Math.min(...bounds.map(b => b[0])), y = Math.min(...bounds.map(b => b[1]));
      const width = Math.max(...bounds.map(b => b[2])) - x, height = Math.max(...bounds.map(b => b[3])) - y;
      const size = Math.max(width,height,10), padding = size * .05;
      box = [x-padding,y-padding,width+padding*2,height+padding*2];
    }
    const svg = svgElement("svg",{viewBox:box.join(" "),role:"group","aria-label":"House districts · recorded change",
      "data-scale":bound,"data-district-snapshot":frame.manifest.version});
    const defs = svgElement("defs"), pattern = svgElement("pattern",{id:"driver-district-held",width:6,height:6,
      patternUnits:"userSpaceOnUse",patternTransform:`scale(${box[2]/1000})`});
    pattern.append(svgElement("rect",{width:6,height:6,fill:"#dadbd6"}),
      svgElement("path",{d:"M-1 1L1-1M0 6L6 0M5 7L7 5",stroke:"#68716d","stroke-width":.6}));
    defs.append(pattern); svg.append(defs); paths = new Map();
    for (const {path,row} of visible) {
      const value = districtValue(row,units), label = `${path.district}: ${points(value)}. `
        + `${row.qualified_comparison ? "Qualified recorded comparison." : row.comparison_holds.join("; ")} `
        + `2026 D ${number(row.D)}, R ${number(row.R)}, Other ${number(row.O)}.`;
      const node = svgElement("path",{d:path.d,"fill-rule":"evenodd",
        fill:value === null ? "url(#driver-district-held)" : districtFill(value,bound),
        class:"driver-state driver-district","data-district":path.district,"data-state-code":path.state_code,
        "data-model-value":value ?? "","data-comparison-caution":String(value === null),
        "data-district-qualified":String(row.qualified_comparison),role:"button",tabindex:"-1",
        "aria-label":label,"pointer-events":"visibleFill","vector-effect":"non-scaling-stroke"});
      const title = svgElement("title"); title.textContent = label; node.append(title);
      node.addEventListener("click",()=>select(path.district));
      node.addEventListener("keydown",event => {
        if (["Enter"," "].includes(event.key)) {event.preventDefault();select(path.district);}
        const move = {ArrowRight:1,ArrowDown:1,ArrowLeft:-1,ArrowUp:-1}[event.key];
        if (move || ["Home","End"].includes(event.key)) {
          event.preventDefault();
          const index = event.key === "Home" ? 0 : event.key === "End" ? visible.length-1
            : (visible.findIndex(item => item.path.district === path.district)+move+visible.length)%visible.length;
          select(visible[index].path.district,true);
        }
      });
      paths.set(path.district,node); svg.append(node);
    }
    if (!scope) for (const [x,text] of [[60,"Alaska"],[310,"Hawaii · insets not to scale"]]) {
      const label = svgElement("text",{x,y:625,class:"driver-inset-label"}); label.textContent=text;svg.append(label);
    }
    host.dataset.driverMap = "district_reported_counts"; host.replaceChildren(svg);
    hitGroup=svgElement("g",{"aria-hidden":"true","data-district-hit-targets":""});
    const updateHits = () => {
      hitGroup.replaceChildren();
      const scale=svg.getBoundingClientRect().width/box[2];
      if (!(scale>0)) return;
      for (const {path} of visible) {
        const bounds=path.bounds;
        if (Math.min(bounds[2]-bounds[0],bounds[3]-bounds[1])*scale>=10) continue;
        const hit=svgElement("circle",{cx:path.point[0],cy:path.point[1],r:5/scale,
          fill:"transparent","pointer-events":"all","data-district-hit":path.district});
        hit.addEventListener("click",()=>select(path.district));
        hitGroup.append(hit);
      }
    };
    svg.append(hitGroup);updateHits();
    observer=new ResizeObserver(updateHits);observer.observe(svg);
    if (visible.length) select(visible.some(item => item.path.district === selected) ? selected : visible[0].path.district);
    else {
      summary.replaceChildren(element("h3","No voting district in this selection"));
      detail.replaceChildren();summary.hidden=false;detail.hidden=true;
    }
  };
  control?.addEventListener("change",()=>select(control.value));
  return {
    leave:stop,
    filter(state) { scope=state; draw(); },
    async render({units:requestedUnits,isCurrent,state=scope}) {
      stop(); active=true; const current=ticket; units=requestedUnits;scope=state;frame=null;
      host.replaceChildren();summary.replaceChildren();detail.replaceChildren();summary.hidden=true;detail.hidden=true;
      control.disabled=true;control.replaceChildren(new Option("Loading verified districts...",""));
      status.textContent="Loading checksum-verified district outlines and the shared automatic congressional snapshot.";
      try {
        if (!geometryPromise) geometryPromise=loadGeometry(receipt).catch(error=>{geometryPromise=null;throw error;});
        const [geometry, congress]=await Promise.all([geometryPromise,loadCongress()]);
        if (!active || current!==ticket || !isCurrent()) return;
        frame={...congress,items:bindDistrictResults(geometry,congress.data)};
        draw();
      } catch (error) {
        if (!active || current!==ticket || !isCurrent()) return;
        frame=null;host.replaceChildren();summary.replaceChildren();detail.replaceChildren();
        summary.hidden=true;detail.hidden=true;
        status.textContent=`District map unavailable: ${error.message}. No stale values or zero-filled comparisons are shown.`;
        const retry=element("button","Retry district map",{type:"button"});
        retry.addEventListener("click",()=>this.render({units:requestedUnits,isCurrent,state:scope}));host.append(retry);
      }
    },
  };
}

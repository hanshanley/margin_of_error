import { checkedCountyBody } from "./participation-historical-county-map.js";
import { projectFeatures } from "./participation-map-projection.js";

const root = new URL("../participation-archive-geometry/mn-precinct/", import.meta.url);
const measures = ["reported_total_voters", "registered_at_7am", "same_day_registrations"];
const dates = {
  "2012-11-06": [4102, 2950780], "2014-11-04": [4106, 1992566],
  "2016-11-08": [4120, 2968281], "2018-11-06": [4113, 2611365], "2020-11-03": [4110, 3292997],
  "2022-11-08": [4103, 2525873], "2024-11-05": [4103, 3272414],
};
const exactCount = s => /^(?:0|[1-9]\d*)$/.test(s) && Number.isSafeInteger(Number(s));

export function minnesotaPrecinctFrames(csv, parseLine) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const fields = parseLine(header), frames = new Map(), ids = new Set();
  const required = ["state_code", "election_date", "county_geoid", "county", "precinct_id",
    "precinct_name", "source_status", "rate_hold_reason", ...measures];
  if (!lines.length || lines.length > 28757 || new Set(fields).size !== fields.length
      || required.some(name => !fields.includes(name))) throw new Error("Missing Minnesota precinct data");
  for (const line of lines) {
    const row = parseLine(line);
    if (row.length !== fields.length) throw new Error("Unexpected Minnesota column count");
    const get = name => row[fields.indexOf(name)];
    const code = get("county_geoid"), id = get("precinct_id"), date = get("election_date");
    const status = get("source_status"), name = get("county"), precinct = get("precinct_name");
    if (!Object.hasOwn(dates, date) || get("state_code") !== "MN" || !/^27\d{3}$/.test(code)
        || !/^\d{9}$/.test(id) || id.slice(0, 5) !== code || ids.has(`${date}/${id}`) || !name || !precinct
        || !["reported", "retained_after_failure"].includes(status)
        || get("rate_hold_reason") !== "pre_registration_excludes_same_day_registrants"
        || !measures.every(key => exactCount(get(key)))) throw new Error("Invalid Minnesota participation record");
    ids.add(`${date}/${id}`);
    if (!frames.has(date)) frames.set(date, { status, counties: new Map(), n: 0, count: 0 });
    const frame = frames.get(date);
    if (!frame.counties.has(code)) frame.counties.set(code, { name, rows: [] });
    const county = frame.counties.get(code);
    if (frame.status !== status || county.name !== name) throw new Error("Mixed Minnesota report identity");
    const [count, registered, sameDay] = measures.map(key => Number(get(key)));
    county.rows.push({ id, precinct, count, registered, sameDay });
    ++frame.n;
    frame.count += count;
  }
  for (const [date, frame] of frames)
    if (frame.counties.size !== 87 || frame.n !== dates[date][0] || frame.count !== dates[date][1])
      throw new Error("Incomplete Minnesota precinct workbook");
  return frames;
}

export function bindMinnesotaPrecinctLayer(layer, date, county, rows) {
  if (layer?.contract !== "participation.mn_historical_precinct_display.v1" || layer.state_code !== "MN"
      || layer.election_date !== date || layer.county_geoid !== county || layer.coordinate_system !== "EPSG:4326"
      || layer.display_only !== true || layer.ballots_allocated_by_geometry !== false
      || !Array.isArray(layer.features) || layer.features.length !== rows.length)
    throw new Error("Minnesota precinct layer has the wrong scope");
  const byId = new Map(rows.map(row => [row.id, row]));
  return layer.features.map(f => {
    const key = f.properties?.precinct_id, row = byId.get(key);
    if (!row || row.count !== f.properties.reported_total_voters
        || !["Polygon", "MultiPolygon"].includes(f.geometry?.type))
      throw new Error("Minnesota precinct polygon or voter count differs");
    byId.delete(key);
    return row;
  });
}

async function loadGzip(url, pin, retry) {
  const bytes = await checkedCountyBody(url, pin, retry);
  return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip")));
}

export function installMinnesotaPrecinctMap(file, parseLine) {
  const panel = document.createElement("details"), title = document.createElement("summary");
  const note = document.createElement("p"), load = document.createElement("button"), status = document.createElement("p");
  const download = document.createElement("a"), replay = document.createElement("a");
  title.textContent = "Minnesota historical precinct participation";
  note.textContent = "Official people voting, not candidate votes. Pre-registration and same-day registrations "
    + "are separate counts; neither supplies a comparable all-voter turnout rate.";
  download.href = file.url;
  download.textContent = "Complete Minnesota precinct participation (CSV · gzip)";
  replay.href = new URL("minnesota-precinct-map-reproduction.zip", root);
  replay.textContent = "Complete Minnesota map data and reproduction (ZIP)";
  load.type = "button";
  load.textContent = "Load precinct map and table";
  status.setAttribute("role", "status");
  panel.append(title, note, download, " · ", replay, " · ", load, status);
  let retry = false;
  load.addEventListener("click", async () => {
    load.disabled = true;
    status.textContent = "Checking Minnesota participation records…";
    try {
      const frames = minnesotaPrecinctFrames(await (await loadGzip(file.url, file, retry)).text(), parseLine);
      const election = document.createElement("select"), county = document.createElement("select");
      for (const date of [...frames.keys()].sort().reverse()) election.add(new Option(date));
      const electionLabel = document.createElement("label"), countyLabel = document.createElement("label");
      electionLabel.append("Election date ", election);
      countyLabel.append("County ", county);
      const figure = document.createElement("figure"), caption = document.createElement("figcaption");
      caption.setAttribute("role", "status");
      figure.style.marginInline = "0";
      figure.append(caption);
      const wrapper = document.createElement("div"), table = document.createElement("table");
      wrapper.className = "table-wrap";
      wrapper.tabIndex = 0;
      wrapper.setAttribute("role", "region");
      wrapper.setAttribute("aria-label", title.textContent);
      const tableCaption = table.createCaption(), head = table.createTHead().insertRow(), body = table.createTBody();
      for (const label of ["Precinct", "People voting", "Registered at 7 a.m.", "Same-day registrations"]) {
        const cell = document.createElement("th");
        cell.scope = "col"; cell.textContent = label; head.append(cell);
      }
      wrapper.append(table);
      let renderId = 0;
      async function render() {
        const token = ++renderId, date = election.value, code = county.value, frame = frames.get(date);
        const { name, rows } = frame.counties.get(code);
        tableCaption.textContent = `${name} County · ${date}`;
        status.textContent = `${rows.length} reported precincts.${frame.status === "reported" ? "" : " Showing last verified edition."}`;
        body.replaceChildren();
        for (const value of rows) {
          const row = body.insertRow(), id = document.createElement("th");
          id.scope = "row"; id.textContent = `${value.precinct} (${value.id})`; row.append(id);
          for (const n of [value.count, value.registered, value.sameDay])
            row.insertCell().textContent = n.toLocaleString("en-US");
        }
        figure.querySelector("svg")?.remove();
        caption.textContent = "Checking election-year precinct boundaries…";
        try {
          const manifest = await fetch(new URL("mn-precinct-geometry.json", root)).then(r => {
            if (!r.ok) throw new Error("Geometry index unavailable");
            return r.json();
          });
          const filename = `precinct-MN-${date.slice(0, 4)}-${code}.json.gz`;
          const pin = manifest[date]?.counties?.[code];
          if (pin?.filename !== filename || !Number.isSafeInteger(pin.bytes) || pin.bytes <= 0
              || pin.bytes > 2_000_000 || !/^[a-f0-9]{64}$/.test(pin.sha256))
            throw new Error("Invalid Minnesota geometry pin");
          const layer = await (await loadGzip(new URL(filename, root), pin, false)).json();
          const matched = bindMinnesotaPrecinctLayer(layer, date, code, rows);
          const items = projectFeatures(layer.features, ([x,y]) => [x * .69, -y], [10, 10, 580, 340]);
          if (items.length !== rows.length || items.some(({ d }) => !d || /NaN|Infinity/.test(d)))
            throw new Error("Invalid Minnesota map paths");
          if (token !== renderId) return;
          const make = tag => document.createElementNS("http://www.w3.org/2000/svg", tag);
          const svg = make("svg");
          svg.setAttribute("viewBox", "0 0 600 360"); svg.setAttribute("width", "600");
          svg.style.maxWidth = "100%"; svg.style.height = "auto";
          svg.setAttribute("role", "img");
          svg.setAttribute("aria-label", `${name} County precinct counts, ${date}; exact values follow in the table.`);
          const palette = ["#fcfdfd", "#d9e8ed", "#b3d2dc", "#79afbf", "#48879d", "#24586d"];
          for (const [i, { d }] of items.entries()) {
            const value = matched[i], n = value.count, path = make("path"), tooltip = make("title");
            path.setAttribute("d", d);
            path.setAttribute("fill", palette[n === 0 ? 0 : n < 250 ? 1 : n < 500 ? 2 : n < 1000 ? 3 : n < 2000 ? 4 : 5]);
            path.setAttribute("stroke", "#4d6269"); path.setAttribute("stroke-width", ".4");
            path.setAttribute("fill-rule", "evenodd");
            tooltip.textContent = `${value.precinct}: ${n.toLocaleString("en-US")} people voting`;
            path.append(tooltip); svg.append(path);
          }
          figure.prepend(svg);
          caption.textContent = "People voting: 0 (white), 1–249, 250–499, 500–999, 1,000–1,999, 2,000 or more (dark blue). "
            + "Election-year display boundaries: Minnesota Secretary of State and MnGeo.";
        } catch {
          if (token === renderId) caption.textContent = "The election-year map could not be verified. The table remains available.";
        }
      }
      function selectCounties() {
        const previous = county.value;
        const choices = [...frames.get(election.value).counties].sort((a, b) => a[1].name.localeCompare(b[1].name));
        county.replaceChildren(...choices.map(([code, { name }]) => new Option(name, code)));
        if (choices.some(([code]) => code === previous)) county.value = previous;
        render();
      }
      election.addEventListener("change", selectCounties);
      county.addEventListener("change", render);
      load.remove();
      panel.append(electionLabel, " · ", countyLabel, figure, wrapper);
      selectCounties();
    } catch {
      retry = true;
      load.disabled = false;
      load.textContent = "Retry Minnesota precinct data";
      status.textContent = "The stored Minnesota precinct records could not be verified.";
    }
  });
  return panel;
}

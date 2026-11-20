import { checkedCountyBody } from "./participation-historical-county-map.js";
import { projectFeatures } from "./participation-map-projection.js";

const root = new URL("../participation-archive-geometry/", import.meta.url);
const election = "2022-11-08";
const precincts = new Map([["Howard", 118], ["Talbot", 12]]);
const pin = { bytes: 810376, sha256: "7a0dc10e93ea1118760128856b59175271371c1b63e2bd9cf620181abd4a3515" };

export function bindMarylandPrecinctLayer(layer, frame) {
  const county = layer?.counties?.[frame.county];
  if (frame.date !== election || !precincts.has(frame.county)
      || layer?.contract !== "participation.md_precinct_activity_display.v1"
      || layer.election_date !== frame.date || layer.source_sha256 !== frame.sha
      || layer.participation_measure !== "reported_ballot_activity_voter_file_snapshot"
      || layer.display_only !== true || county?.features?.length !== precincts.get(frame.county)
      || county.activity_without_precinct !== frame.unplaced)
    throw new Error("Maryland turnout and precinct map source scope differ");
  const keys = new Set();
  let total = county.activity_without_precinct;
  for (const f of county.features) {
    const { precinct, activity } = f.properties;
    if (!/^0\d{2}-\d{3}$/.test(precinct) || keys.has(precinct)
        || !Number.isSafeInteger(activity) || activity < 0
        || !["Polygon", "MultiPolygon"].includes(f.geometry?.type))
      throw new Error("Invalid Maryland precinct activity");
    keys.add(precinct);
    total += activity;
  }
  if (total !== frame.activity) throw new Error("Maryland map does not reconcile to the locality total");
  return county.features;
}

export function installMarylandPrecinctMap(parent) {
  const container = document.createElement("details");
  const title = document.createElement("summary"), figure = document.createElement("figure");
  const status = document.createElement("figcaption"), download = document.createElement("a");
  title.textContent = "2022 precinct activity map";
  status.setAttribute("role", "status");
  figure.style.marginInline = "0";
  figure.append(status);
  download.href = new URL("precinct-MD-2022-reproduction.zip", root);
  download.textContent = "Complete Maryland 2022 map data and reproduction (ZIP)";
  container.append(title, figure, download);
  parent.append(container);
  let frame, token = 0, retry = false;
  container.addEventListener("toggle", async () => {
    if (!container.open || container.hidden || !frame || figure.querySelector("svg")) return;
    const current = ++token;
    status.textContent = "Checking the election-year map…";
    try {
      const body = await checkedCountyBody(new URL("precinct-MD-2022.json.gz", root), pin, retry);
      const layer = await new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream("gzip"))).json();
      if (current !== token || !container.open) return;
      const features = bindMarylandPrecinctLayer(layer, frame);
      const items = projectFeatures(features, ([x,y]) => [x * .78, -y], [10, 10, 580, 340]);
      if (items.length !== features.length || items.some(({ d }) => !d || /NaN|Infinity/.test(d)))
        throw new Error("Invalid Maryland map paths");
      const make = tag => document.createElementNS("http://www.w3.org/2000/svg", tag);
      const svg = make("svg");
      svg.setAttribute("viewBox", "0 0 600 360"); svg.setAttribute("width", "600");
      svg.style.maxWidth = "100%"; svg.style.height = "auto";
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", `${frame.county} County 2022 precinct ballot activity`);
      const colors = ["#fcfdfd", "#d9e8ed", "#b3d2dc", "#79afbf", "#48879d", "#24586d"];
      for (const [i, { d }] of items.entries()) {
        const { precinct, activity } = features[i].properties;
        const path = make("path"), tooltip = make("title");
        path.setAttribute("d", d);
        path.setAttribute("fill", colors[activity === 0 ? 0 : activity < 250 ? 1 : activity < 500 ? 2
          : activity < 1000 ? 3 : activity < 2000 ? 4 : 5]);
        path.setAttribute("fill-rule", "evenodd"); path.setAttribute("stroke", "#4d6269");
        path.setAttribute("stroke-width", ".4");
        tooltip.textContent = `${precinct}: ${activity.toLocaleString("en-US")} reported ballot activity`;
        path.append(tooltip); svg.append(path);
      }
      figure.prepend(svg);
      status.textContent = "Reported ballot activity: 0 (white), 1–249, 250–499, 500–999, 1,000–1,999, "
        + `2,000 or more (dark blue). ${frame.unplaced.toLocaleString("en-US")} records without a precinct are not mapped. `
        + layer.attribution + ".";
      retry = false;
    } catch {
      if (current !== token) return;
      retry = true;
      status.textContent = "The map could not be verified against this edition. The full data and table remain available.";
    }
  });
  return next => {
    ++token;
    frame = next;
    container.hidden = next.date !== election || !precincts.has(next.county);
    container.open = false;
    figure.querySelector("svg")?.remove();
    status.textContent = "";
  };
}

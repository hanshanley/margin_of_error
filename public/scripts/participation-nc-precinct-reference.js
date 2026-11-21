import { checkedCountyBody } from "./participation-historical-county-map.js";

const root = new URL("../participation-archive-geometry/nc-precinct-reference/", import.meta.url);
const references = {
  "2012-11-06": [1464759, "955cd7e78b993b21e8b3d9728f3e724104a0feb6cb85783be7ba96523fdf2c21"],
  "2014-11-04": [1750544, "5884e206d172b7eebc664822cbda5684af84faf384c16c94aa542ff2c5b6191c"],
  "2016-11-08": [1776239, "e466e65b13d509ce6a13950520ec1b75b05720a926686c326fd79f7e609f1ee1"],
  "2018-11-06": [1775733, "c965291a0f2e804f11b3a0f2841d58cfac2548f5d2cc867c5e662a6ea78e4d37"],
  "2020-11-03": [1855062, "233faac733aa573af3ce843aaf59529f0e9534690c2d0010e6574f70bd0d5093"],
  "2022-11-08": [1754142, "986bd68e500bd069066a75196b33b1e212e7cd00fcd1a14fe5a91ed91f7751fa"],
  "2024-11-05": [1640253, "a18596a549c918cc646bc135351e312779b29cab02a246fe352ed8974da83747"],
};
const colors = ["#fcfdfd", "#d9e8ed", "#b3d2dc", "#79afbf", "#48879d", "#24586d"];
const bins = [1, 500, 1000, 2000, 3500];
const key = (county, precinct) => JSON.stringify([county, precinct]);

export function bindNorthCarolinaReference(layer, date, counts) {
  if (layer?.contract !== "participation.nc_precinct_reference.v1" || layer.election !== date
      || !/^\d{8}(?: and \d{8})?$/.test(layer.edition)
      || !Array.isArray(layer.roster) || !Array.isArray(layer.paths))
    throw new Error("Unverified precinct reference");
  const roster = new Set(layer.roster.map(([county, precinct]) => key(county, precinct)));
  if (roster.size !== layer.roster.length || roster.size !== counts.size || [...counts.keys()].some(id => !roster.has(id)))
    throw new Error("The accepted precinct roster differs from the reference");
  const mapped = new Set();
  return layer.paths.map(([county, precinct, path]) => {
    const id = key(county, precinct), count = counts.get(id);
    if (!Number.isSafeInteger(count) || count < 0 || !precinct.trim() || mapped.has(id)
        || typeof path !== "string" || !path.startsWith("M") || !path.endsWith("Z") || /[^MLZ0-9.,-]/.test(path))
      throw new Error("Invalid precinct reference path or count");
    mapped.add(id);
    return { county, precinct, path, count, fill: colors[bins.filter(threshold => count >= threshold).length] };
  });
}

export function installNorthCarolinaPrecinctReference(host, election, getFrame, getCounts) {
  const details = document.createElement("details"), summary = document.createElement("summary");
  const figure = document.createElement("figure"), caption = document.createElement("figcaption");
  const links = document.createElement("p"), download = document.createElement("a");
  summary.textContent = "Precinct reference map (counts only)";
  figure.style.marginInline = "0";
  caption.setAttribute("role", "status");
  figure.append(caption);
  download.href = "https://github.com/hanshanley/voter-participation/releases/download/"
    + "north-carolina-general-participation-demographics-2008-2024/north-carolina-precinct-reference-display-layers.zip";
  download.textContent = "All reference maps, decision tables and reproduction (ZIP)";
  links.append(download);
  details.append(summary, figure, links);
  host.append(details);
  const number = new Intl.NumberFormat("en-US");
  let generation = 0;
  const layers = new Map();
  const load = async () => {
    const token = ++generation;
    figure.querySelector("svg")?.remove();
    if (!details.open) return;
    const frame = getFrame();
    if (!Object.hasOwn(references, frame.date)) {
      caption.textContent = "No reference map matches this source edition. Use the complete precinct download.";
      return;
    }
    caption.textContent = "Checking the precinct reference map…";
    try {
      const [bytes, sha256] = references[frame.date];
      if (!layers.has(frame.date)) {
        const url = new URL(`${frame.date}-precinct-reference.json.gz`, root);
        layers.set(frame.date, checkedCountyBody(url, { bytes, sha256 }).then(body =>
          new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream("gzip"))).json())
          .catch(error => { layers.delete(frame.date); throw error; }));
      }
      const [layer, counts] = await Promise.all([layers.get(frame.date), getCounts(frame)]);
      if (token !== generation || !details.open) return;
      const items = bindNorthCarolinaReference(layer, frame.date, counts);
      const make = tag => document.createElementNS("http://www.w3.org/2000/svg", tag);
      const svg = make("svg");
      for (const [k, v] of Object.entries({ viewBox: "0 57 960 318", width: "960", role: "img",
        "aria-label": `North Carolina count-only precinct reference, ${frame.date}; complete counts in the CSV` }))
        svg.setAttribute(k, v);
      svg.style.maxWidth = "100%"; svg.style.height = "auto";
      for (const item of items) {
        const node = make("path"), title = make("title");
        for (const [k, v] of Object.entries({ d: item.path, fill: item.fill, "fill-rule": "evenodd",
          stroke: "#596875", "stroke-width": ".15" })) node.setAttribute(k, v);
        title.textContent = `${item.county} · ${item.precinct}: ${number.format(item.count)} voter-history credits`;
        node.append(title); svg.append(node);
      }
      const shown = items.reduce((total, item) => total + item.count, 0);
      caption.textContent = `${number.format(items.length)} of ${number.format(counts.size)} units shown; `
        + `${number.format(shown)} of ${number.format(frame.rows.get("state").count)} credits mapped. `
        + "White outlines: reported zero. Light to dark blue: 1–499, 500–999, 1,000–1,999, 2,000–3,499, 3,500 or more. "
        + `Missing areas are not zero. Dated reference: ${layer.edition}; not turnout rates.`
        + (frame.status === "retained_after_failure" ? " The last verified source edition is retained." : "");
      figure.prepend(svg);
    } catch {
      if (token === generation) caption.textContent = "The map could not be verified. The full data and maps remain downloadable.";
    }
  };
  details.addEventListener("toggle", load);
  election.addEventListener("change", load);
}

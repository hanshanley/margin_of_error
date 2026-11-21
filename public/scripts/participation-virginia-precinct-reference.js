import { checkedCountyBody } from "./participation-historical-county-map.js";
import { conicProjection, projectFeatures } from "./participation-map-projection.js";

const asset = "/participation-archive-geometry/precinct-VA-Suffolk-2022.geojson";
const pin = { bytes: 439437, sha256: "713e74f1d9ada76fbb96280683fed602fa330d19bbe4a836fe685af50e396604" };
const localityName = "SUFFOLK CITY";
const key = name => name.toUpperCase().replace(/[^A-Z0-9]/g, "");
const colors = ["#f0f3f5", "#c5e1e3", "#84bdc4", "#428a9d", "#24596e"];
// Reviewed crosswalk in GIS P1–P30 order. P15 is intentionally unbound.
const referenceCodes = "105 704 204 504 502 104 703 402 601 501 304 403 202 102 - 301 604 602 404 401 203 405 302 101 305 505 201 605 306 706".split(" ");

export function bindVirginiaPrecinctReference(layer, locality) {
  if (layer?.type !== "FeatureCollection" || !Array.isArray(layer.features) || layer.features.length !== 30
      || locality?.electionDay.size !== 30) throw new Error("Suffolk reference inventory differs");
  const counts = new Map(), ids = new Set(), names = new Set();
  for (const [code, row] of locality.electionDay) {
    const name = key(row.name.slice(3));
    if (!name || counts.has(name) || !Number.isSafeInteger(row.ballots) || row.ballots < 0)
      throw new Error("Suffolk count identities differ");
    counts.set(name, { ...row, code });
  }
  const rows = layer.features.map(feature => {
    const { Precinct_Number: id, Precinct_Name: name } = feature.properties;
    const identity = typeof name === "string" ? key(name) : "";
    if (!/^P(?:[1-9]|[12]\d|30)$/.test(id) || !identity || ids.has(id) || names.has(identity)
        || !["Polygon", "MultiPolygon"].includes(feature.geometry?.type))
      throw new Error("Suffolk geometry identities differ");
    ids.add(id);
    names.add(identity);
    const row = counts.get(identity);
    if ((row?.code ?? "-") !== referenceCodes[Number(id.slice(1)) - 1])
      throw new Error("Suffolk reference join changed");
    return { feature, id, name, row };
  });
  const unmatched = rows.filter(item => !item.row);
  const countOnly = [...counts].filter(([name]) => !names.has(name));
  if (unmatched.length !== 1 || unmatched[0].id !== "P15" || unmatched[0].name !== "ELEPHANTS FORK"
      || countOnly.length !== 1 || countOnly[0][1].code !== "603"
      || countOnly[0][0] !== "ELEPHANTSFORKWESTHAVEN")
    throw new Error("Suffolk reference join changed");
  return rows;
}

export function installVirginiaPrecinctReference(parent, select, localities) {
  if (!localities.has(localityName)) return;
  const container = document.createElement("div"), button = document.createElement("button");
  const figure = document.createElement("figure"), caption = document.createElement("figcaption");
  const status = document.createElement("span");
  const download = document.createElement("a");
  download.href = "https://github.com/hanshanley/voter-participation/releases/download/"
    + "suffolk-2022-precinct-reference-map/suffolk-2022-reference-map.zip";
  download.textContent = "Offline map, original geometry, and baseline counts (ZIP)";
  button.type = "button";
  button.textContent = "Show Suffolk precinct reference map";
  button.setAttribute("aria-expanded", "false");
  status.setAttribute("role", "status");
  figure.hidden = true;
  figure.style.marginInline = "0";
  caption.append(status, download);
  figure.append(caption);
  container.append(button, figure);
  container.hidden = select.value !== localityName;
  parent.append(container);
  let generation = 0, retry = false;
  const close = () => {
    ++generation;
    figure.hidden = true;
    button.textContent = "Show Suffolk precinct reference map";
    button.setAttribute("aria-expanded", "false");
    figure.querySelector("svg")?.remove();
  };
  select.addEventListener("change", () => {
    container.hidden = select.value !== localityName;
    if (container.hidden) close();
  });
  button.addEventListener("click", async () => {
    if (!figure.hidden && !retry) return close();
    const token = ++generation;
    button.textContent = "Hide Suffolk precinct reference map";
    button.setAttribute("aria-expanded", "true");
    figure.hidden = false;
    status.textContent = "Checking Suffolk precinct reference boundaries… ";
    try {
      const body = await checkedCountyBody(asset, pin, retry);
      const layer = JSON.parse(new TextDecoder().decode(body));
      const locality = localities.get(localityName);
      const rows = bindVirginiaPrecinctReference(layer, locality);
      const items = projectFeatures(layer.features, conicProjection(-77, 29.5, 45.5), [8, 8, 454, 352]);
      if (items.some(({ d }) => !d || /NaN|Infinity/.test(d))) throw new Error("Unusable mapped polygons");
      if (token !== generation) return;
      const make = tag => document.createElementNS("http://www.w3.org/2000/svg", tag);
      const svg = make("svg");
      svg.setAttribute("viewBox", "0 0 470 368");
      svg.setAttribute("width", "470");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", "Suffolk, Virginia: 2022 Election Day ballot counts on reference boundaries. Exact counts are in the table.");
      svg.style.maxWidth = "100%";
      svg.style.height = "auto";
      const format = new Intl.NumberFormat("en-US");
      for (const [i, { d }] of items.entries()) {
        const { id, name, row } = rows[i], path = make("path"), title = make("title");
        path.setAttribute("d", d);
        path.setAttribute("fill", colors[row ? 1 + Math.min(Math.floor(row.ballots / 500), 3) : 0]);
        path.setAttribute("stroke", "#4d6870");
        path.setAttribute("stroke-width", ".65");
        path.setAttribute("fill-rule", "evenodd");
        path.dataset.precinct = id;
        title.textContent = `${name}: ${row ? `${format.format(row.ballots)} Election Day ballots` : "no verified match"}`;
        path.append(title);
        svg.append(path);
      }
      figure.prepend(svg);
      const central = [...locality.central.values()].reduce((sum, row) => sum + row.ballots, 0);
      const unmatched = locality.electionDay.get("603");
      status.textContent = `City GIS reference boundaries, November 8, 2022. ${format.format(central)} central ballots `
        + `and precinct 603’s ${format.format(unmatched.ballots)} Election Day ballots stay off the map. `
        + "Gray: unmatched. Light to dark: 0–499, 500–999, 1,000–1,499, 1,500+ ballots. No rates. ";
      retry = false;
    } catch {
      if (token !== generation) return;
      retry = true;
      button.textContent = "Retry Suffolk precinct reference map";
      status.textContent = "The Suffolk map could not be verified. The precinct table and download remain available. ";
    }
  });
}

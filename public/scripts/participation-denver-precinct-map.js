import { checkedCountyBody, countyMapFill } from "./participation-historical-county-map.js";
import { projectFeatures } from "./participation-map-projection.js";

const date = "2022-11-08", countyName = "Denver";
const pin = { bytes: 502999, sha256: "8dc28d1ed015d32376986e1c795417f47e46aa182fbb15bc75f7f796e69eaf59" };
const asset = new URL("../participation-archive-geometry/precinct-CO-Denver-2022.json.gz", import.meta.url);
const svgNS = "http://www.w3.org/2000/svg";

export function bindDenverPrecinctMap(layer, rows) {
  if (layer?.contract !== "participation.denver_precinct_display.v1" || layer.state_code !== "CO"
      || layer.county !== countyName || layer.election_date !== date || layer.coordinate_system !== "EPSG:4326"
      || layer.display_only !== true || layer.ballots_allocated_by_geometry !== false
      || !Array.isArray(layer.features) || layer.features.length !== 301 || rows?.length !== 301
      || rows.some(row => !/^\d{5}16\d{3}$/.test(row.precinct)))
    throw new Error("Denver precinct map scope differs");
  const byKey = new Map(rows.map(row => [row.precinct, row]));
  return layer.features.map(feature => {
    const key = feature.properties?.precinct;
    const row = byKey.get(key);
    if (!row || !["Polygon", "MultiPolygon"].includes(feature.geometry?.type))
      throw new Error("Denver precinct roster differs from its reviewed layer");
    byKey.delete(key);
    return row;
  });
}

export function installDenverPrecinctMap(parent, election, county, frames) {
  const container = document.createElement("div"), button = document.createElement("button");
  const figure = document.createElement("figure"), caption = document.createElement("figcaption");
  const download = document.createElement("a");
  download.href = new URL("../participation-archive-geometry/precinct-CO-Denver-2022-reproduction.zip", import.meta.url);
  download.textContent = "Reproduce 2022 Denver map (ZIP)";
  download.hidden = true;
  button.type = "button";
  button.textContent = "Show Denver precinct map";
  button.setAttribute("aria-expanded", "false");
  caption.setAttribute("role", "status");
  figure.hidden = true;
  figure.style.marginInline = "0";
  figure.append(caption, download);
  container.append(button, figure);
  parent.append(container);
  let generation = 0, opened = false, retry = false;
  const sync = () => {
    ++generation;
    opened = false;
    container.hidden = election.value !== date || county.value !== countyName;
    figure.hidden = true;
    figure.querySelector("svg")?.remove();
    button.textContent = "Show Denver precinct map";
    button.setAttribute("aria-expanded", "false");
  };
  for (const select of [election, county]) select.addEventListener("change", sync);
  sync();

  button.addEventListener("click", async () => {
    if (opened) return sync();
    opened = true;
    const token = ++generation;
    button.textContent = "Hide Denver precinct map";
    button.setAttribute("aria-expanded", "true");
    figure.hidden = false;
    download.hidden = true;
    caption.textContent = "Checking Denver precinct boundaries and participation…";
    try {
      const bytes = await checkedCountyBody(asset, pin, retry);
      const layer = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).json();
      const rows = bindDenverPrecinctMap(layer, frames.get(date)?.counties.get(countyName));
      const projection = ([x, y]) => [x * Math.cos(39.7 * Math.PI / 180), -y];
      const items = projectFeatures(layer.features, projection, [10, 10, 580, 340]);
      if (items.length !== rows.length || items.some(({ d }) => !d || /NaN|Infinity/.test(d)))
        throw new Error("Unusable Denver precinct polygons");
      if (token !== generation) return;
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", "0 0 600 360");
      svg.setAttribute("width", "600");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", "Denver 2022 precinct participation; exact values are in the table.");
      svg.style.maxWidth = "100%";
      svg.style.height = "auto";
      for (const [i, { d }] of items.entries()) {
        const row = rows[i], path = document.createElementNS(svgNS, "path");
        path.setAttribute("d", d);
        path.setAttribute("fill", countyMapFill(row, false));
        path.setAttribute("stroke", "#4d6269");
        path.setAttribute("stroke-width", ".4");
        path.setAttribute("fill-rule", "evenodd");
        path.dataset.precinct = row.precinct;
        const title = document.createElementNS(svgNS, "title");
        title.textContent = `${row.precinct}: ${row.count.toLocaleString("en-US")} ballots; `
          + (row.rate === null ? "rate withheld" : `${row.rate.toFixed(2)}% of same-report registrations`);
        path.append(title);
        svg.append(path);
      }
      figure.prepend(svg);
      caption.textContent = "Denver, November 8, 2022. Darker blue means a higher fraction of registered voters (0–100%). "
        + "Blue-gray means count only. Denver Elections Division boundaries, adjusted for display only.";
      download.hidden = false;
      retry = false;
    } catch {
      if (token !== generation) return;
      retry = true;
      opened = false;
      button.textContent = "Retry Denver precinct map";
      button.setAttribute("aria-expanded", "false");
      caption.textContent = "The Denver map could not be verified. The precinct table and download remain available.";
    }
  });
}

import { checkedCountyBody } from "./participation-historical-county-map.js";
import { projectFeatures } from "./participation-map-projection.js";

const svgNS = "http://www.w3.org/2000/svg";
const asset = "/participation-archive-geometry/precinct-WY-Teton-2026.json.gz";
const pin = { bytes: 412266, sha256: "334f96f95800357061fe90f91dabf57ed958f9c9d4665fce521528061f0d1a8a" };

export function bindTetonPrecinctMap(layer, canvass) {
  const date = "2026-11-03";
  if (layer?.contract !== "participation.teton_precinct_display.v1"
      || layer.state_code !== "WY" || layer.county !== "Teton" || layer.election_date !== date
      || layer.coordinate_system !== "EPSG:3739" || layer.display_only !== true
      || layer.ballots_allocated_by_geometry !== false || !Array.isArray(layer.features)
      || layer.features.length !== 17 || canvass?.election_date !== date || canvass.state_code !== "WY")
    throw new Error("Teton map scope differs");

  const rows = canvass.complete_native_query.filter(row => row.county === "Teton");
  const byKey = new Map(rows.map(row => [row.precinct_key, row]));
  if (rows.length !== 17 || byKey.size !== 17
      || rows.some(row => row.election_date !== date || row.state_code !== "WY"
        || !Number.isSafeInteger(row.ballots_cast) || row.ballots_cast < 0))
    throw new Error("Teton count inventory differs");

  const seen = new Set();
  return layer.features.map(feature => {
    const key = feature.properties?.precinct_key, row = byKey.get(key);
    if (!row || seen.has(key) || !["Polygon", "MultiPolygon"].includes(feature.geometry?.type))
      throw new Error("Teton precinct IDs or polygons differ");
    seen.add(key);
    return row;
  });
}

export function installTetonPrecinctMap(parent, data, select) {
  const container = document.createElement("div");
  const button = document.createElement("button");
  const figure = document.createElement("figure");
  const caption = document.createElement("figcaption"), status = document.createElement("span");
  const download = document.createElement("a");
  download.href = "/participation-archive-geometry/precinct-WY-Teton-2026-reproduction.zip";
  download.textContent = "Download map and pinned baseline counts (ZIP)";
  download.className = "source-link";
  download.hidden = true;
  container.hidden = select.value !== "Teton";
  button.type = "button";
  button.textContent = "Show Teton precinct map";
  button.setAttribute("aria-expanded", "false");
  figure.hidden = true;
  figure.style.marginInline = "0";
  status.setAttribute("role", "status");
  caption.append(status, download);
  figure.append(caption);
  container.append(button, figure);
  parent.append(container);
  let generation = 0, opened = false, retry = false;
  const close = () => {
    ++generation;
    opened = false;
    figure.hidden = true;
    button.textContent = "Show Teton precinct map";
    button.setAttribute("aria-expanded", "false");
    figure.querySelector("svg")?.remove();
  };
  select.addEventListener("change", () => {
    container.hidden = select.value !== "Teton";
    if (container.hidden) close();
  });

  button.addEventListener("click", async () => {
    if (opened) return close();
    opened = true;
    const token = ++generation;
    button.textContent = "Hide Teton precinct map";
    button.setAttribute("aria-expanded", "true");
    figure.hidden = false;
    download.hidden = true;
    status.textContent = "Checking Teton precinct boundaries and counts…";
    try {
      const bytes = await checkedCountyBody(asset, pin, retry);
      const layer = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).json();
      const rows = bindTetonPrecinctMap(layer, data);
      const items = projectFeatures(layer.features, ([x, y]) => [x, -y], [10, 10, 500, 300]);
      if (items.some(({ d }) => !d || /NaN|Infinity/.test(d))) throw new Error("Unusable mapped polygons");
      if (token !== generation) return;
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", "0 0 520 320");
      svg.setAttribute("width", "520");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", "Teton County, 2026 precinct ballot counts. Exact counts are in the table.");
      svg.style.maxWidth = "100%";
      svg.style.height = "auto";
      for (const [i, { d }] of items.entries()) {
        const row = rows[i], path = document.createElementNS(svgNS, "path");
        path.setAttribute("d", d);
        path.setAttribute("fill", row.ballots_cast < 500 ? "#dae7ea"
          : row.ballots_cast < 1000 ? "#8ab0b9" : "#3e7887");
        path.setAttribute("stroke", "#4d6269");
        path.setAttribute("stroke-width", ".65");
        path.setAttribute("fill-rule", "evenodd");
        path.dataset.precinct = row.native_precinct;
        const title = document.createElementNS(svgNS, "title");
        title.textContent = `${row.native_precinct}: ${row.ballots_cast.toLocaleString("en-US")} ballots`;
        path.append(title);
        svg.append(path);
      }
      figure.prepend(svg);
      status.textContent = "Teton County, 2026. Ballots cast: 0–499 (light), 500–999 (medium), 1,000 or more (dark). "
        + "County GIS boundaries were repaired for display only. Counts are not turnout rates. ";
      download.hidden = false;
      retry = false;
    } catch {
      if (token !== generation) return;
      retry = true;
      opened = false;
      button.textContent = "Retry Teton precinct map";
      button.setAttribute("aria-expanded", "false");
      status.textContent = "The Teton map could not be verified. The precinct table and complete download remain available.";
    }
  });
}

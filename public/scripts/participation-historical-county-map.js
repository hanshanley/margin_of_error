import { conicProjection, projectFeatures } from "./participation-map-projection.js";

const referenceBase = "https://raw.githubusercontent.com/hanshanley/margin_of_error/"
  + "87402220be76ca71e4407132e81cc24a2df71fd9/data/participation-local/20261104T220000Z-identity-audit/";
const inventoryPin = "d3efe485646356b30e3929f1e9aa51efdb6e99732db848e7a8fdcad18aa8eaed";
const svgNS = "http://www.w3.org/2000/svg";
const ohio2008Archive = "https://www.eac.gov/sites/default/files/eac_assets/1/6/2008%20eavs%20xls%20august%2011%202010.zip";
const countedBallots2008 = "Number of ballots counted at precincts and/or at a central location "
  + "(including UOCAVA and other absentee or early vote ballots)";
const officialCountySizes = { AL: 67, CA: 58, CO: 64, KS: 105, NC: 100, NE: 93, NJ: 21, VA: 133, WA: 39, WV: 55, WY: 23 };
const geometryReleases = "https://github.com/hanshanley/voter-participation/releases/download/";
const nebraskaGeometryRelease = geometryReleases + "nebraska-legacy-county-geometry-20261120/";
export const officialArchiveGeometry = {
  "CA/1990": {
    path: "participation-archive-geometry/county-CA-1990.geojson.gz",
    bytes: 149674,
    sha256: "ae2d02864d93e39719ce1d3d280984a96d995d9c2c6ab20b1c06a97cc623b28e",
  },
  "CA/2000": {
    path: "participation-archive-geometry/county-CA-2000.geojson.gz",
    bytes: 238216,
    sha256: "45c07057063363c464169885be7158aa0225da9c9c0df94c38bc17b232ec47fe",
  },
  "CA/2006": {
    path: "participation-archive-geometry/county-CA-2006.geojson.gz",
    bytes: 1227706,
    sha256: "43e5fbcd88f268e84fa6e667f172539a835ff46878137137af7dee8df15dfc0c",
    referenceDate: "2006-01-01",
  },
  "CA/2026": {
    path: "participation-archive-geometry/county-CA-2026.geojson.gz",
    bytes: 1743930,
    sha256: "3a422ef0e610eb98d0a16d1fd8b28a403bff1b31dded6bc2874b15e6c607e635",
    boundaryLabel: "2026 Census TIGER/Line county boundaries.",
  },
  "CO/2000": {
    path: "participation-archive-geometry/county-CO-2000.geojson.gz",
    bytes: 121966,
    sha256: "d066e3986aaff57ef8690cdde73216d4dcb7bb42b801243116874cc8fc9a9b9a",
    reproduction: "co-2000-county-map-reproduction.zip",
    reproductionBase: geometryReleases + "colorado-2000-county-geometry-20261120/",
  },
  "NC/2006": {
    path: "participation-archive-geometry/county-NC-2006.geojson.gz",
    bytes: 1333876,
    sha256: "85d9377888d95c012d10654d17b9b1eb4cbdbea9036e1c8f1d8a4a1b45508d63",
    referenceDate: "2006-01-01",
  },
  "NE/2000": {
    path: "participation-archive-geometry/county-NE-2000.geojson.gz",
    bytes: 95038,
    sha256: "22d07562f91c6b4021d1dc95abdd9046e92f7f0b1c43e4bb74587fcb0444a4c6",
    reproduction: "ne-2000-county-map-reproduction.zip",
  },
  "NE/2002": {
    path: "participation-archive-geometry/county-NE-2002.geojson.gz",
    bytes: 243116,
    sha256: "2d6ddc575dacad67fef84107f4b48164e71749da4043be21f4f9b383006464f1",
    referenceDate: "2002-01-01",
    partialGeometry: true,
    reproduction: "ne-2002-county-map-reproduction.zip",
  },
  "NE/2006": {
    path: "participation-archive-geometry/county-NE-2006.geojson.gz",
    bytes: 742132,
    sha256: "7a85788d1e30c4f490a6bce5be943304eae4eeeb830f6b5eba4b30489561360a",
    referenceDate: "2006-01-01",
    reproduction: "ne-2006-county-map-reproduction.zip",
  },
  "NE/2026": {
    path: "participation-archive-geometry/county-NE-2026.geojson.gz",
    bytes: 730273,
    sha256: "0dbd9e78623afb6dba1be348113778d471d9cb5c41549fc9887f3f5d3b4e7dbc",
    boundaryLabel: "2026 Census TIGER/Line county boundaries.",
  },
  "NJ/2023": {
    path: "participation-archive-geometry/county-NJ-2023.geojson.gz",
    bytes: 62105,
    sha256: "76c1610cf67ef5a7544e4c0a81588f4b8f0a40c89d9752a8323d382dbd22355b",
  },
  "NJ/2025": {
    path: "participation-archive-geometry/county-NJ-2025.geojson.gz",
    bytes: 62203,
    sha256: "2c7db843a5fae1d58e539969da1a2b38ff8ddcab26405ff0ab4a6039c6c72151",
  },
  "WY/2006": {
    path: "participation-archive-geometry/county-WY-2006.geojson.gz",
    bytes: 222451,
    sha256: "6eeb4e5c783d0602903136f032b0050d3216db2893ed1f5c308bdd8e4efb6c8f",
    referenceDate: "2006-01-01",
  },
  "WY/2026": {
    path: "participation-archive-geometry/county-WY-2026.geojson.gz",
    bytes: 383495,
    sha256: "c73b0ac8381b6ac77ebc8d9d018d103916e1cf9d05ec8f995c8511d3f3ad7be3",
    boundaryLabel: "2026 Census TIGER/Line county boundaries.",
  },
};
const countyName = name => name.trim().toUpperCase().replace(/\s+(COUNTY|PARISH|BOROUGH)$/, "")
  .replace(/[^A-Z0-9]/g, "");

export async function checkedCountyBody(url, { sha256, bytes }, retry) {
  const response = await fetch(url, {
    cache: retry ? "reload" : "default",
    signal: AbortSignal.timeout(20_000),
  });
  if (!response.ok) throw new Error("Historical county file could not be loaded");
  const body = await response.arrayBuffer();
  if ((bytes !== undefined && body.byteLength !== bytes) || body.byteLength > 2_000_000)
    throw new Error("Historical county file length differs");
  const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))]
    .map(byte => byte.toString(16).padStart(2, "0")).join("");
  if (digest !== sha256) throw new Error("Historical county file checksum differs");
  return body;
}

async function referenceJson(path, pin, retry) {
  const bytes = await checkedCountyBody(referenceBase + path, pin, retry);
  const stream = new Blob([bytes]).stream();
  return new Response(path.endsWith(".gz") ? stream.pipeThrough(new DecompressionStream("gzip")) : stream).json();
}

export function bindHistoricalCountyMap(collection, prior, rows, code, year) {
  const features = collection?.features;
  if (collection?.type !== "FeatureCollection" || !Array.isArray(features) || !features.length
      || !Array.isArray(prior)) throw new Error("Missing historical county reference");
  const references = new Map(), current = new Map(), seen = new Set();
  const ohio2008 = code === "OH" && year === 2008;
  // Census TIGER/Line 2015 User Note 1: the name and code changed on May 1, 2015.
  const shannon = code === "SD" && [2008, 2010, 2012, 2014].includes(year);
  for (const row of prior) {
    if (row.year !== year) continue;
    // The original Ohio county returns use native five-digit IDs, unlike the harmonized workbook.
    const key = row.geography?.level === "county" ? row.geography.key
      : ohio2008 && row.geography == null && /^39\d{3}$/.test(row.jurisdiction_id)
        ? row.jurisdiction_id : null;
    if (key === null) continue;
    if (row.state_code !== code || references.has(key))
      throw new Error("Ambiguous historical county reference");
    references.set(key, row);
  }
  for (const row of rows) {
    if (row.code !== code || row.year !== year || row.count === null) continue;
    const key = shannon && row.fips === "46102" && countyName(row.name) === "OGLALALAKOTA"
      ? "46113" : row.fips;
    if (current.has(key)) throw new Error("Ambiguous reconciled county count");
    current.set(key, row);
  }
  return features.map(feature => {
    const p = feature.properties;
    if (feature.type !== "Feature" || p?.state_code !== code || p.boundary_year !== year
        || p.level !== "county" || !/^[0-9]{5}$/.test(p.key) || seen.has(p.key)
        || !["Polygon", "MultiPolygon"].includes(feature.geometry?.type))
      throw new Error("Historical county geometry identity differs");
    seen.add(p.key);
    const row = current.get(p.key), reference = references.get(p.key);
    let method = null;
    if (row && reference && !reference.statewide_unit && !reference.supplemental_unit
      && reference.total_participation === row.count) {
      const sameName = countyName(reference.jurisdiction) === countyName(row.name);
      if (reference.geography?.level === "county" && reference.jurisdiction_id === `${p.key}00000`) {
        if (row.fips === p.key && sameName) method = "prior_reviewed_county";
        else if (shannon && p.key === "46113" && row.fips === "46102"
            && typeof p.name === "string" && countyName(p.name) === "SHANNON"
            && countyName(reference.jurisdiction) === "SHANNON"
            && (row.rate === null || reference.registered === row.registered)) {
          method = "sd_shannon_county_pre_2015_code";
        }
      } else if (sameName && ohio2008 && reference.geography == null && reference.jurisdiction_id === p.key
          && reference.source_url === ohio2008Archive && typeof p.name === "string"
          && countyName(p.name) === countyName(row.name)) {
        const detail = reference.source_details;
        if (detail?.f2 === countedBallots2008 && !detail.f1_comments
            && (!detail.f2_comments || detail.f2_comments === "Total also contains provisional ballots counted")
            && (row.rate === null || reference.registered === row.registered)) {
          method = "ohio_2008_native_counted_ballot_report";
        }
      }
    }
    return { feature, value: method ? row : null, method };
  });
}

export function bindOfficialCountyArchive(collection, frame, allowPartialGeometry = false) {
  const { code, date, rows } = frame;
  const year = Number(date.slice(0, 4));
  const size = code === "CO" && year === 2000 ? 63 : officialCountySizes[code];
  const partial = frame.partialCountyReports === true && code === "NE" && date === "2026-11-03";
  const localityCountsOnly = frame.localityCountsOnly === true && code === "VA" && date === "2024-11-05";
  const missing = allowPartialGeometry && code === "NE" && date === "2002-11-05"
    && collection?.reference_date === "2002-01-01" && Array.isArray(collection.missing_counties)
    ? new Set(collection.missing_counties) : new Set();
  if (missing.size && (missing.size !== collection.missing_counties.length || missing.size >= size
      || [...missing].some(key => !/^31\d{3}$/.test(key) || Number(key.slice(2)) % 2 !== 1
        || Number(key.slice(2)) > 185))) throw new Error("Unverified missing county boundary inventory");
  if (!size || collection?.type !== "FeatureCollection" || !Array.isArray(collection.features)
      || collection.features.length + missing.size !== size
      || (partial || localityCountsOnly ? rows.size !== size || rows.has("state")
        : rows.size !== size + 1 || !rows.has("state")))
    throw new Error("Missing complete official county frame");
  const byName = new Map(), keys = new Set();
  const virginia = code === "VA" && (date === "2022-11-08" || localityCountsOnly);
  const localityName = name => name.trim().toUpperCase().replace("KING & QUEEN COUNTY", "KING AND QUEEN COUNTY");
  for (const [key, row] of rows) {
    if (key === "state") continue;
    const name = virginia ? localityName(row.name) : countyName(row.name);
    if (!name || byName.has(name)) throw new Error("Ambiguous official county name");
    byName.set(name, row);
  }
  return collection.features.map(feature => {
    const p = feature.properties;
    if (feature.type !== "Feature" || p?.state_code !== code || p.boundary_year !== year
        || p.level !== "county" || !/^[0-9]{5}$/.test(p.key) || keys.has(p.key) || missing.has(p.key)
        || (missing.size && (!/^31\d{3}$/.test(p.key) || Number(p.key.slice(2)) % 2 !== 1
          || Number(p.key.slice(2)) > 185))
        || typeof p.name !== "string" || !["Polygon", "MultiPolygon"].includes(feature.geometry?.type))
      throw new Error("Official county geometry identity differs");
    keys.add(p.key);
    const name = virginia ? localityName(`${p.name} ${Number(p.key.slice(2)) >= 500 ? "CITY" : "COUNTY"}`)
      : countyName(p.name);
    const value = byName.get(name);
    if (!value || (frame.rateOnly && (rows.get(p.key) !== value
        || !Number.isInteger(value.rate) || value.rate < 0 || value.rate > 100)))
      throw new Error("Official county roster differs from its dated reference");
    byName.delete(name);
    return { feature, value: (partial || frame.measure === "group_report_ballots") && value.count === null ? null : value };
  });
}

const countMapColors = ["#fcfdfd", "#d9e8ed", "#b3d2dc", "#79afbf", "#48879d", "#24586d"];
const countMapLegend = "Light to dark blue: 1–999; 1,000–4,999; 5,000–19,999; 20,000–99,999; "
  + "100,000 or more. White means reported zero; light gray means no verified count. ";

export function countyMapFill(value, countOnly) {
  if (!value) return "#ebedf0";
  if (countOnly) {
    const count = value.count;
    return countMapColors[count === 0 ? 0 : count < 1_000 ? 1 : count < 5_000 ? 2
      : count < 20_000 ? 3 : count < 100_000 ? 4 : 5];
  }
  return value.rate == null ? "#c4d2d7" : `hsl(193 47% ${90 - value.rate * 0.62}%)`;
}

export function installHistoricalCountyMap(panel, state, year, rows, names, officialFrame) {
  const button = document.createElement("button"), figure = document.createElement("figure");
  const status = document.createElement("figcaption");
  const reproduction = document.createElement("a");
  reproduction.hidden = true;
  status.setAttribute("role", "status");
  figure.hidden = true;
  figure.style.marginInline = "0";
  figure.append(status, reproduction);
  button.type = "button";
  button.textContent = "Show county map";
  panel.append(button, figure);
  let generation = 0, inventory, opened = false;
  const load = async (retry = false) => {
    const token = ++generation, code = state.value, vintage = Number(year.value.slice(0, 4));
    const label = `${names[code] || code} · ${vintage}`;
    const legacy = officialFrame && officialArchiveGeometry[`${code}/${vintage}`];
    figure.querySelector("svg")?.remove();
    reproduction.hidden = !legacy?.reproduction;
    reproduction.removeAttribute("href");
    if (legacy?.reproduction) {
      reproduction.href = (legacy.reproductionBase ?? nebraskaGeometryRelease) + legacy.reproduction;
      reproduction.textContent = `Reproduce ${vintage} county boundaries (ZIP)`;
    }
    figure.hidden = false;
    button.textContent = "Hide county map";
    if ((!legacy && vintage < 2008) || (officialFrame && !officialCountySizes[code])) {
      status.textContent = `${label}: no reviewed same-year county shapes; use the table.`;
      return;
    }
    status.textContent = `Checking county map for ${label}…`;
    try {
      const geography = `geometry/${vintage}/county-${code}.geojson.gz`, sources = `states/${code}.json.gz`;
      const frame = officialFrame?.();
      let collection, prior;
      if (legacy) {
        const url = new URL(`../${legacy.path}`, import.meta.url).href;
        const bytes = await checkedCountyBody(url, legacy, retry);
        const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
        collection = await new Response(stream).json();
        if (legacy.referenceDate ? collection.reference_date !== legacy.referenceDate
          : collection.boundary_vintage !== vintage) throw new Error("County reference vintage differs");
      } else {
        inventory ??= referenceJson("checksums.json", { sha256: inventoryPin }, retry)
          .catch(error => { inventory = undefined; throw error; });
        const files = await inventory;
        if (token !== generation) return;
        if (!files[geography] || (!officialFrame && !files[sources])) {
          status.textContent = `${label}: no reviewed same-year county shapes; use the table.`;
          return;
        }
        [collection, prior] = await Promise.all([referenceJson(geography, files[geography], retry),
          frame ? null : referenceJson(sources, files[sources], retry)]);
      }
      if (token !== generation) return;
      const bound = frame ? bindOfficialCountyArchive(collection, frame, legacy?.partialGeometry)
        : bindHistoricalCountyMap(collection, prior, rows, code, vintage);
      const counts = bound.filter(item => item.value).length;
      const rates = bound.filter(item => item.value?.rate != null).length;
      const countOnly = Boolean(frame && !frame.rateOnly && !rates && (counts || frame.measure === "group_report_ballots"));
      const projection = code === "AK" ? conicProjection(-154, 55, 65)
        : code === "HI" ? conicProjection(-157, 8, 18) : conicProjection(-96, 29.5, 45.5);
      const items = projectFeatures(collection.features, projection, [12, 12, 576, 336]);
      if (items.length !== bound.length || items.some(({ d }) => !d || /NaN|Infinity/.test(d)))
        throw new Error("County shapes could not be projected");
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", "0 0 600 360");
      svg.setAttribute("width", "600");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", `${label} county participation; values and evidence are in the table`);
      svg.style.maxWidth = "100%";
      svg.style.height = "auto";
      const number = new Intl.NumberFormat("en-US");
      for (const [i, { d }] of items.entries()) {
        const { feature, value } = bound[i], rate = value?.rate;
        const path = document.createElementNS(svgNS, "path");
        path.setAttribute("d", d);
        path.setAttribute("fill", countyMapFill(value, countOnly));
        path.setAttribute("stroke", "#70828a");
        path.setAttribute("stroke-width", ".65");
        path.setAttribute("fill-rule", "evenodd");
        path.dataset.county = feature.properties.key;
        const title = document.createElementNS(svgNS, "title");
        const area = frame?.code === "VA" ? value?.name ?? feature.properties.name : feature.properties.name;
        title.textContent = `${area}: ${frame?.rateOnly ? `${rate}% published turnout`
          : value && frame?.measure === "group_report_ballots" ? `${number.format(value.count)} reported ballots`
          : value ? `${number.format(value.count)} ${frame?.measure === "voter_history_credits"
            ? "voter-history credits" : "reported"}; `
          + (rate == null ? "rate withheld" : `${rate.toFixed(2)}% of same-report registrations`)
          : "no verified mapped count"}`;
        path.append(title);
        svg.append(path);
      }
      const missingGeometry = legacy?.partialGeometry ? collection.missing_counties?.length ?? 0 : 0;
      status.textContent = frame?.measure === "group_report_ballots"
        ? `${label}: ${counts} of ${bound.length} counties have ballot counts for the selected group. `
          + countMapLegend + "Shading shows ballot counts, not rates. Boundaries are for this election year only."
        : frame?.rateOnly
        ? `${label}: ${rates} of ${bound.length} counties have published whole-percent rates. `
          + "Darker blue indicates higher reported turnout (0–100%). "
          + "The report does not specify the count or denominator. Census reference boundaries dated January 1, 2006."
        : frame?.partialCountyReports
          ? `${label}: ${counts} of ${bound.length} county reports have verified counts. `
            + countMapLegend
            + "Reports have separate editions; no statewide total or rates are calculated."
        : (missingGeometry
          ? `${label}: ${counts} of ${bound.length + missingGeometry} counties are mapped; ${rates} have mapped rates. `
            + `${missingGeometry} counties are not drawn because matching outlines were unavailable; see the complete table. `
          : `${label}: ${counts} of ${bound.length} areas have verified counts; ${rates} have rates. `)
        + (frame?.measure === "voter_history_credits" ? "Counts are voter-history credits, not physical ballot counts. " : "")
        + (countOnly ? countMapLegend + "Shading shows counts, not turnout rates. "
          : "Darker blue means a higher fraction of registered voters (0–100%). Blue-gray means count only; "
            + "light gray means no verified mapped count, not zero. ")
        + (legacy?.referenceDate ? `Census reference boundaries dated January 1, ${vintage}.`
          : legacy ? legacy.boundaryLabel ?? `${vintage} Census cartographic county boundaries (simplified).`
          : "Boundaries are for this election year only.");
      figure.append(svg);
    } catch {
      if (token !== generation) return;
      status.textContent = `${label}: the county map could not be verified. The table and download are still available.`;
      button.textContent = "Retry county map";
    }
  };
  for (const select of [state, year]) select.addEventListener("change", () => { if (opened) load(); });
  button.addEventListener("click", () => {
    if (button.textContent === "Retry county map") return load(true);
    opened = !opened;
    button.setAttribute("aria-expanded", String(opened));
    if (opened) return load();
    ++generation;
    figure.hidden = true;
    figure.querySelector("svg")?.remove();
    button.textContent = "Show county map";
  });
  button.setAttribute("aria-expanded", "false");
}

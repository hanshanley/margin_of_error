import { loadDatasetCatalog } from "./participation-dataset.js";
import { countStates, loadCountIndex } from "./participation-counts.js";
import { loadNativeIndex } from "./participation-native-bindings.js";
import { loadAutomaticRuntime } from "./participation-automatic-runtime.js";

const coveragePath = "release/participation-administrative-coverage.csv.gz";
const historicalCountyPath = "participation/eac-county-year-decisions.csv.gz";
const scopes = ["statewide", "county_or_equivalent", "precinct"];
const metrics = scopes.flatMap(scope => ["count", "rate"].map(kind =>
  `${scope}_election_participation_${kind}_records`));

export function administrativeRows(csv) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const columns = header.split(",");
  const fields = ["state_code", "year", ...metrics];
  if (fields.some(field => columns.indexOf(field) < 0 || columns.indexOf(field) !== columns.lastIndexOf(field)))
    throw new Error("Missing or repeated administrative coverage field");
  const seen = new Set();
  const rows = lines.map(line => {
    const cells = line.split(",");
    const [code, year, ...values] = fields.map(field => cells[columns.indexOf(field)]);
    if (cells.length !== columns.length || !countStates.includes(code) || seen.has(code) || year !== "2026"
        || values.some(value => !/^(?:0|[1-9][0-9]*)$/.test(value) || !Number.isSafeInteger(Number(value))))
      throw new Error("Invalid jurisdiction or administrative coverage count");
    seen.add(code);
    const counts = values.map(Number);
    if (counts.some((value, i) => i % 2 && value > counts[i - 1]))
      throw new Error("Qualified rates exceed count-bearing records");
    return { code, counts };
  });
  if (seen.size !== countStates.length) throw new Error("Incomplete administrative coverage export");
  return rows;
}

export function historicalCountyDownload(sources) {
  const series = sources?.historical_eac_counties;
  const file = series?.downloads?.[historicalCountyPath];
  if (series?.contract !== "participation.eac_county_counted_ballot_reconciliation.v1"
      || series.historical_not_2026 !== true || series.no_county_boundary_equivalence_inferred !== true
      || typeof sources.base_url !== "string" || !sources.base_url.startsWith("https://")
      || file?.path !== historicalCountyPath || file.url !== `${sources.base_url}/${historicalCountyPath}`
      || !Number.isSafeInteger(file.bytes) || file.bytes <= 0 || !/^[a-f0-9]{64}$/.test(file.sha256)
      || !Number.isSafeInteger(series.direct_count_rows) || series.direct_count_rows < 1
      || !Number.isSafeInteger(series.county_rows) || series.county_rows < series.direct_count_rows) return null;
  return { url: file.url, counts: series.direct_count_rows, rows: series.county_rows };
}

async function loadAdministrativeCoverage() {
  const manifest = await loadAutomaticRuntime();
  const sources = manifest.house_sources;
  const file = sources?.supported_release?.downloads?.[coveragePath];
  if (!file) return null;
  if (file.path !== coveragePath || file.url !== `${sources.base_url}/${coveragePath}`
      || file.media_type !== "text/csv" || file.compression !== "gzip"
      || !Number.isSafeInteger(file.bytes) || file.bytes < 1 || file.bytes > 65536
      || !/^[a-f0-9]{64}$/.test(file.sha256))
    throw new Error("Administrative coverage is not bound to the accepted runtime");
  const response = await fetch(file.url);
  if (!response.ok) throw new Error("Administrative coverage could not be loaded");
  const body = await response.arrayBuffer();
  const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))]
    .map(byte => byte.toString(16).padStart(2, "0")).join("");
  if (body.byteLength !== file.bytes || digest !== file.sha256)
    throw new Error("Administrative coverage checksum differs");
  const csv = await new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  return { rows: administrativeRows(csv), file, manifest };
}

function installAdministrativeCoverage(host) {
  const panel = document.createElement("details");
  const heading = document.createElement("summary");
  heading.textContent = "Election participation by jurisdiction";
  const content = document.createElement("div");
  panel.append(heading, content);
  host.append(panel);
  let names = {}, pending = false;
  panel.addEventListener("toggle", async () => {
    if (!panel.open || pending) return;
    pending = true;
    content.textContent = "Checking the accepted administrative coverage export…";
    try {
      const coverage = await loadAdministrativeCoverage();
      if (!coverage) {
        content.textContent = "This release has no administrative coverage export.";
        return;
      }
      const { rows, file, manifest } = coverage;
      const note = document.createElement("p");
      note.textContent = `2026 · Accepted source check ${new Date(manifest.checked_at).toISOString()}. `
        + `${rows.filter(row => row.counts[0]).length} of 51 jurisdictions have a statewide count. `
        + "Zeros mean no qualifying records, not zero votes. Counts are records, not people or proof of complete coverage. "
        + "The strict precinct class is not the inventory of separate reporting-unit and matched precinct layers.";
      const download = document.createElement("a");
      download.href = file.url; download.textContent = "Coverage audit (CSV · gzip)";
      const complete = document.createElement("a");
      complete.href = manifest.complete_download.url; complete.textContent = "Complete inputs, queries and results (ZIP)";
      const scroller = document.createElement("div");
      scroller.className = "table-wrap"; scroller.tabIndex = 0;
      scroller.setAttribute("role", "region"); scroller.setAttribute("aria-label", heading.textContent);
      const table = document.createElement("table");
      table.createCaption().textContent = "Qualifying 2026 participation records (excludes early or returned-only activity)";
      const header = table.createTHead().insertRow();
      for (const label of ["Jurisdiction", "State counts", "State rates", "County counts", "County rates",
        "Precinct counts", "Precinct rates"]) {
        const cell = document.createElement("th");
        cell.scope = "col"; cell.textContent = label; header.append(cell);
      }
      const tbody = table.createTBody();
      for (const { code, counts } of rows) {
        const row = tbody.insertRow(); row.dataset.stateCode = code;
        const key = document.createElement("th");
        key.scope = "row"; key.textContent = names[code] || code; row.append(key);
        for (const value of counts) row.insertCell().textContent = String(value);
      }
      scroller.append(table);
      content.replaceChildren(note, download, " · ", complete, scroller);
      const historical = historicalCountyDownload(manifest.house_sources);
      if (historical) {
        const history = document.createElement("p");
        const link = document.createElement("a");
        link.href = historical.url; link.textContent = "EAC county-year counts and decisions, 2004–2024 (CSV · gzip)";
        history.append(link, `: ${historical.counts.toLocaleString("en-US")} of `
          + `${historical.rows.toLocaleString("en-US")} rows match direct county reports. `
          + "Held rows remain in the download. This does not fill 2026 gaps or establish comparable boundaries.");
        content.append(history);
      }
      panel.dataset.runtimeVersion = manifest.version;
    } catch {
      content.textContent = "Administrative coverage could not be verified. Close and reopen to retry.";
      pending = false;
    }
  });
  return scopeNames => { names = scopeNames; };
}

export function coverageRows(catalog, countIndex, nativeIndex, scope, rejected = {}) {
  if (scope.year !== 2026) return [];
  const precinct = scope.level === "precinct";
  const datasetId = precinct ? "participation-native-bindings-2026" : "participation-counts-2026";
  const entry = catalog?.datasets?.[datasetId];
  return countStates.map(code => {
    const frame = countIndex?.states?.[code]?.views?.[scope.mode];
    const layer = nativeIndex?.layers?.["precinct/" + code]
      || nativeIndex?.layers?.["matched/" + code];
    const native = precinct && layer?.eligible_modes?.includes(scope.mode) ? layer : null;
    const tableDeclaration = nativeIndex?.reporting_tables?.[code];
    const table = precinct && tableDeclaration?.eligible_modes?.includes(scope.mode) ? tableDeclaration : null;
    const available = precinct ? native?.features || table?.rows || 0 : frame?.counties ?? 0;
    const disposition = precinct ? table?.coverage || native?.coverage : frame?.dispositions?.counties;
    const status = rejected[datasetId] ? "Rejected by reader"
      : entry?.status === "rejected" ? "Rejected"
        : !entry || entry.status !== "loaded" ? "Awaiting publication"
          : available ? precinct && !native && table ? "Loaded (table only)" : "Loaded" : "Missing for this scope";
    const known = entry?.status === "loaded" && !rejected[datasetId];
    return { code, status,
      source_rows: known ? precinct ? table?.rows || frame?.precincts || native?.coverage.source_rows || 0 : frame?.counties ?? 0 : null,
      reference_units: known && precinct ? native?.features ?? 0 : null,
      reported: known ? disposition?.reported ?? 0 : null,
      unknown: known ? disposition?.unknown ?? 0 : null, withheld: known ? disposition?.withheld ?? 0 : null,
      fractions: known ? precinct ? disposition?.fractions ?? 0 : disposition?.qualified_fractions ?? 0 : null,
      held_regions: known ? frame?.holds ?? 0 : null,
      reason: rejected[datasetId] || (status === "Missing for this scope"
        ? "No qualified source frame/reference for this selection; not zero participation."
        : status.startsWith("Loaded")
          ? "Source-defined partial coverage; unknown, withheld and unmapped areas are not zero."
          : "No unverified or rejected values are substituted.") };
  });
}

export function installCoverage(host = document.getElementById("participation-coverage")) {
  let generation = 0;
  const caption = host?.querySelector("[data-coverage-caption]");
  const body = host?.querySelector("tbody");
  const updateAdministrativeNames = host && installAdministrativeCoverage(host);
  return { async setScope(scope) {
    if (!host) return;
    updateAdministrativeNames(scope.names || {});
    const token = ++generation;
    body.replaceChildren();
    host.dataset.year = scope.year;
    host.dataset.mode = scope.mode;
    host.dataset.level = scope.level;
    if (scope.year !== 2026) {
      caption.textContent = "This intake catalog covers 2026. Historical observations use their separate source readers and are not classified as missing here.";
      return;
    }
    caption.textContent = "Loading source coverage...";
    try {
      const catalog = await loadDatasetCatalog(), rejected = {};
      const counts = await loadCountIndex().catch(error => {
        rejected["participation-counts-2026"] = error.message; return null;
      });
      const native = await loadNativeIndex().catch(error => {
        rejected["participation-native-bindings-2026"] = error.message; return null;
      });
      if (token !== generation) return;
      const selectedCatalog = { datasets: { ...catalog.datasets } };
      for (const source of [counts, native]) {
        if (source?.entry) selectedCatalog.datasets[source.entry.id] = source.entry;
      }
      const rows = coverageRows(selectedCatalog, counts?.index, native?.index, scope, rejected);
      const names = scope.names || {};
      for (const row of rows) {
        const tr = document.createElement("tr"); tr.dataset.stateCode = row.code; tr.dataset.status = row.status;
        const values = [names[row.code] || row.code, row.status, row.source_rows,
          row.reported, row.reference_units, row.fractions, row.unknown, row.withheld, row.held_regions];
        for (const [index, value] of values.entries()) {
          const cell = document.createElement(index ? "td" : "th");
          cell.textContent = value === null ? index === 4 && scope.level !== "precinct"
            ? "Not applicable" : "Unavailable" : String(value);
          tr.append(cell);
        }
        tr.title = row.reason;
        body.append(tr);
      }
      const loaded = rows.filter(row => row.status.startsWith("Loaded")).length;
      caption.textContent = `2026 · ${scope.mode.replaceAll("_", " ")} · ${scope.level === "precinct" ? "precinct/reference" : "county/local"} scope: `
        + `${loaded} of 51 jurisdictions have a loaded frame. Counts, reference units and source rows are separate; these are not people or national coverage percentages.`;
      const selected = scope.level === "precinct" ? native?.entry : counts?.entry;
      const download = selected?.complete_download;
      if (typeof download?.url === "string" && download.url.startsWith("https://")) {
        const complete = document.createElement("a");
        complete.href = download.url; complete.textContent = "Complete numerical inputs, queries and results";
        caption.append(" ", complete);
      }
      host.dataset.datasetVersion = counts?.entry.version || "";
    } catch (error) {
      if (token === generation) caption.textContent = `${error.message}. Coverage unavailable; missing data are not zero.`;
    }
  } };
}

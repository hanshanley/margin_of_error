import { loadDatasetCatalog } from "./participation-dataset.js";
import { countStates, loadCountIndex } from "./participation-counts.js";
import { loadNativeIndex } from "./participation-native-bindings.js";

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
  return { async setScope(scope) {
    if (!host) return;
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
      const rows = coverageRows(catalog, counts?.index, native?.index, scope, rejected);
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

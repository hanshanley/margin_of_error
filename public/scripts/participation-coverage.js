import { loadDatasetCatalog } from "./participation-dataset.js";
import { countStates, loadCountIndex, validateCurrentCountSnapshot } from "./participation-counts.js";
import { loadNativeIndex } from "./participation-native-bindings.js";
import { loadAutomaticRuntime, loadWyomingPrecinctCanvass } from "./participation-automatic-runtime.js";
import { checkedCountyBody, installHistoricalCountyMap } from "./participation-historical-county-map.js";
import { installDenverPrecinctMap } from "./participation-denver-precinct-map.js";
import { installMinnesotaPrecinctMap } from "./participation-minnesota-precinct-map.js";
import { installMarylandPrecinctMap } from "./participation-maryland-precinct-map.js";
import { participationDownload } from "./participation-downloads.js";
import { projectStateContext } from "./participation-map-projection.js";

const coveragePath = "release/participation-administrative-coverage.csv.gz";
const historicalCountyPath = "participation/eac-county-year-decisions.csv.gz";
const countyYears = Array.from({ length: 11 }, (_, i) => 2004 + 2 * i);
const countyDecisions = {
  reconciled_direct_county_turnout: "Matches the direct county report",
  county_turnout_missing_or_noninteger: "Count missing or not a whole number",
  direct_and_county_turnout_disagree: "County and jurisdiction reports disagree",
  highest_office_source_reported: "Source reports votes for highest office, not ballots",
  no_unambiguous_direct_county_report: "No unambiguous direct county report",
  not_a_county_scope: "Not a county observation",
  ambiguous_county_workbook_identity: "County identity is ambiguous",
};
const ncAgePath = "release/participation-nc-vote-history-age.csv.gz";
const indianaTurnoutPath = "release/participation-indiana-general-turnout-history.csv.gz";
const stateCountyArchivesPath = "release/participation-state-county-turnout-archives.csv.gz";
const coloradoPrecinctStatisticsPath = "release/participation-co-precinct-voting-statistics.csv.gz";
const minnesotaPrecinctStatisticsPath = "release/participation-mn-historical-precinct-turnout.csv.gz";
const marylandPrecinctPath = "release/participation-md-precinct-affiliation-snapshots.csv.gz";
const marylandGroupPath = "release/participation-md-county-affiliation-snapshots.csv.gz";
const marylandArchiveDownload = "https://github.com/hanshanley/voter-participation/releases/download/"
  + "maryland-2016-2024-turnout-archive-20261120/maryland-five-election-turnout-archive.zip";
const marylandArchive = [
  [marylandGroupPath, 22982, "6d3041c95f0712d57ec38b8000507415662e1ffb809b5452280b0bfeeef054c2"],
  [marylandPrecinctPath, 1089244, "5d2281078f76889e4977b52483334a5cba682454d306193cf9e7a09f599ff5f2"],
].map(([path, bytes, sha256]) => ({
  url: new URL(`../participation-archive-geometry/${path.slice("release/".length)}`, import.meta.url).href,
  bytes, sha256,
}));
const californiaCurrentReportPath = "release/participation-ca-2026-county-turnout-report.csv.gz";
const nebraskaCurrentReportPath = "release/participation-ne-2026-county-canvass.csv.gz";
const nebraskaCountyReportsPath = "release/participation-ne-2026-county-reports.csv.gz";
const publishedCpsPath = "release/participation-cps-published-state-tables.csv.gz";
const archivedCpsPath = "release/participation-cps-archived-state-tables.csv.gz";
const overallCpsPath = "release/participation-cps-state-overall-history.csv.gz";
const nc2006CountyCsv = {
  bytes: 23208,
  sha256: "8f41611649303cd067dccf790c2c7f188de379d278951b1991c209296cf1a83d",
};
const ncAges = ["Age 18 - 25", "Age 26 - 40", "Age 41 - 65", "Age Over 66"];
const scopes = [
  ["statewide", "State"], ["county_or_equivalent", "County"],
  ["municipality", "Municipal", true], ["reporting_unit", "Reporting-unit", true],
  ["precinct", "Strict precinct"],
];

export function administrativeRows(csv) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const columns = header.split(",");
  const fields = ["state_code", "year", ...scopes.flatMap(([scope, , optional]) => {
    const pair = ["count", "rate"].map(kind => `${scope}_election_participation_${kind}_records`);
    return optional && pair.every(field => !columns.includes(field)) ? [null, null] : pair;
  })];
  if (fields.some(field => field !== null
      && (columns.indexOf(field) < 0 || columns.indexOf(field) !== columns.lastIndexOf(field))))
    throw new Error("Missing or repeated administrative coverage field");
  const seen = new Set();
  const rows = lines.map(line => {
    const cells = line.split(",");
    const [code, year, ...values] = fields.map(field => field === null ? null : cells[columns.indexOf(field)]);
    if (cells.length !== columns.length || !countStates.includes(code) || seen.has(code) || year !== "2026"
        || values.some(value => value !== null
          && (!/^(?:0|[1-9][0-9]*)$/.test(value) || !Number.isSafeInteger(Number(value)))))
      throw new Error("Invalid jurisdiction or administrative coverage count");
    seen.add(code);
    const counts = values.map(value => value === null ? null : Number(value));
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

// The producer emits one CSV record per physical line, with standard quoting for fields.
function historicalCsvLine(line) {
  const cells = [];
  const field = /(?:"((?:[^"]|"")*)"|([^",]*))(,|$)/y;
  for (;;) {
    const match = field.exec(line);
    if (!match) throw new Error("Invalid historical county CSV field");
    cells.push(match[1] === undefined ? match[2] : match[1].replaceAll('""', '"'));
    if (!match[3]) return cells;
  }
}

export function historicalCountyRows(csv, series) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const fields = ["state", "year", "county_fips", "county_name", "county_registered",
    "county_turnout", "county_highest_office_flag", "direct_registered", "direct_turnout",
    "direct_highest_office_flag", "decision", "direct_reported_turnout", "same_report_registration_fraction_pct"];
  const columns = historicalCsvLine(header);
  const indices = fields.map(field => columns.indexOf(field));
  if (new Set(columns).size !== columns.length || indices.includes(-1)
      || lines.length !== series.county_rows) throw new Error("Historical county inventory differs");
  const integer = value => /^[0-9]+$/.test(value) && Number.isSafeInteger(Number(value));
  const seen = new Set(), decisions = new Map(), years = new Set();
  let counts = 0, rates = 0;
  const rows = lines.map(line => {
    const cells = historicalCsvLine(line);
    const [code, yearText, fips, name, stock, collapsed, collapsedFlag, nativeStock, direct,
      directFlag, decision, countText, rateText] = indices.map(i => cells[i]);
    const year = Number(yearText);
    if (cells.length !== columns.length || !/^[A-Z]{2}$/.test(code) || !/^\d{4}$/.test(yearText)
        || !countyYears.includes(year) || !Object.hasOwn(countyDecisions, decision))
      throw new Error("Invalid historical county identity or decision");
    const qualified = decision === "reconciled_direct_county_turnout";
    const count = qualified ? Number(countText) : null;
    const key = `${code}/${year}/${fips}`;
    if (qualified ? !name || !/^\d{5}$/.test(fips) || fips.endsWith("000") || seen.has(key)
          || ![countText, collapsed, direct].every(integer)
          || count !== Number(collapsed) || count !== Number(direct) : countText !== "")
      throw new Error("Historical county count does not meet its decision");
    const rate = rateText === "" ? null : Number(rateText);
    if (rate !== null && (!qualified || !/^\d+(?:\.\d+)?(?:e[+-]?\d+)?$/i.test(rateText)
        || !Number.isFinite(rate) || !integer(stock) || !integer(nativeStock)
        || Number(stock) !== Number(nativeStock) || Number(stock) <= 0 || count > Number(stock)
        || collapsedFlag !== "0" || directFlag !== "0"
        || Math.abs(rate - 100 * count / Number(stock)) > 1e-10))
      throw new Error("Historical county registration fraction differs");
    if (qualified) { seen.add(key); counts++; }
    if (rate !== null) rates++;
    decisions.set(decision, (decisions.get(decision) || 0) + 1);
    years.add(year);
    return { code, year, fips, name, count, registered: rate === null ? null : Number(stock), rate, decision };
  });
  if (counts !== series.direct_count_rows || rates !== series.same_report_registration_fraction_rows
      || years.size !== series.election_years?.length || [...years].some(year => !series.election_years.includes(year))
      || decisions.size !== Object.keys(series.decisions || {}).length
      || [...decisions].some(([key, value]) => series.decisions[key] !== value))
    throw new Error("Historical county summary differs");
  return rows;
}

export async function loadHistoricalCountyRows(sources, { retry = false } = {}) {
  const historical = historicalCountyDownload(sources);
  const series = sources?.historical_eac_counties;
  const file = series?.downloads?.[historicalCountyPath];
  if (!historical || file.bytes > 2_000_000 || historical.rows > 40_000
      || !series.held_rows_are_not_zero || !series.source_registered_voter_fraction_not_populational_turnout)
    throw new Error("Historical county export is not qualified");
  const body = await checkedCountyBody(historical.url, file, retry);
  const csv = await new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  return historicalCountyRows(csv, series);
}

function installHistoricalCounties(sources, historical, names) {
  const panel = document.createElement("details");
  const heading = document.createElement("summary");
  heading.textContent = "Browse historical county participation (2004–2024)";
  const note = document.createElement("p");
  const link = document.createElement("a");
  link.href = historical.url; link.textContent = "Complete EAC county-year counts and decisions (CSV · gzip)";
  note.append(link, `: ${historical.counts.toLocaleString("en-US")} of `
    + `${historical.rows.toLocaleString("en-US")} rows match direct county reports. `
    + "These are separate general-election snapshots, not 2026 results. County boundaries are not matched across years. "
    + "Rates, where supported, use registered voters in the same report, not eligible population. "
    + "A dash means no qualified registration figure or rate; a reported zero is shown as 0.");
  const status = document.createElement("p");
  status.setAttribute("role", "status");
  const button = document.createElement("button");
  button.type = "button"; button.textContent = "Load county reports";
  panel.append(heading, button, status);
  let retry = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    status.textContent = "Checking the stored EAC reports…";
    try {
      const rows = await loadHistoricalCountyRows(sources, { retry });
      const state = document.createElement("select"), year = document.createElement("select");
      for (const code of countStates) state.add(new Option(names[code] || code, code));
      for (const value of [...countyYears].reverse()) year.add(new Option(String(value), String(value)));
      const stateLabel = document.createElement("label"), yearLabel = document.createElement("label");
      stateLabel.append("State or D.C. ", state); yearLabel.append(" Election year ", year);
      const scroller = document.createElement("div");
      scroller.className = "table-wrap"; scroller.tabIndex = 0;
      scroller.setAttribute("role", "region"); scroller.setAttribute("aria-label", "Historical county reports");
      const table = document.createElement("table");
      const caption = table.createCaption(), header = table.createTHead().insertRow();
      for (const label of ["Reporting county", "Reported turnout count", "Registered voters (rate basis)",
        "Registered-voter fraction", "Evidence"]) {
        const cell = document.createElement("th");
        cell.scope = "col"; cell.textContent = label; header.append(cell);
      }
      const body = table.createTBody();
      const number = new Intl.NumberFormat("en-US");
      function render() {
        const selected = rows.filter(row => row.code === state.value && row.year === Number(year.value)
          && row.decision !== "not_a_county_scope");
        caption.textContent = `${names[state.value] || state.value} · ${year.value} general election`;
        body.replaceChildren();
        for (const row of selected) {
          const tr = body.insertRow(), key = document.createElement("th");
          key.scope = "row"; key.textContent = row.name || row.fips || "Unidentified county"; tr.append(key);
          tr.insertCell().textContent = row.count === null ? "Withheld" : number.format(row.count);
          tr.insertCell().textContent = row.registered === null ? "—" : number.format(row.registered);
          tr.insertCell().textContent = row.rate === null ? "—" : `${row.rate.toFixed(2)}%`;
          tr.insertCell().textContent = countyDecisions[row.decision];
        }
        status.textContent = selected.length ? `${selected.length} county records; `
          + `${selected.filter(row => row.count !== null).length} with qualified counts.`
          : "No county reports in this selection. This does not mean zero ballots.";
        scroller.hidden = !selected.length;
      }
      for (const select of [state, year]) select.addEventListener("change", render);
      scroller.append(table);
      button.replaceWith(stateLabel, yearLabel);
      installHistoricalCountyMap(panel, state, year, rows, names);
      panel.append(scroller);
      render();
      state.focus();
    } catch {
      retry = true;
      status.textContent = "Historical county reports could not be verified. The complete download remains available.";
      button.disabled = false;
      button.textContent = "Retry county reports";
    }
  });
  return [note, panel];
}

export function coverageCsvFile(sources, path) {
  const file = sources?.supported_release?.downloads?.[path];
  if (!file) return null;
  const maxBytes = [coloradoPrecinctStatisticsPath, minnesotaPrecinctStatisticsPath, marylandPrecinctPath].includes(path)
    ? 2_000_000 : [stateCountyArchivesPath, publishedCpsPath, overallCpsPath].includes(path) ? 524288 : 65536;
  if (typeof sources.base_url !== "string" || !sources.base_url.startsWith("https://")
      || file.path !== path || file.url !== `${sources.base_url}/${path}`
      || file.media_type !== "text/csv" || file.compression !== "gzip"
      || !Number.isSafeInteger(file.bytes) || file.bytes < 1
      || file.bytes > maxBytes
      || !/^[a-f0-9]{64}$/.test(file.sha256))
    throw new Error("Administrative coverage is not bound to the accepted runtime");
  return file;
}

export function installMarylandAffiliationSnapshots(groupFile, precinctFile, { archival = false } = {}) {
  const panel = document.createElement("details"), title = document.createElement("summary");
  const note = document.createElement("p"), load = document.createElement("button"), status = document.createElement("p");
  title.textContent = "Maryland turnout activity by registration affiliation";
  note.textContent = "Affiliation is registration, not vote choice. These snapshots count ballot activity, including rejected "
    + "ballots and occasional duplicate activity. They do not measure unique voters or counted ballots.";
  for (const [file, text] of [[groupFile, "Complete county and state data"], [precinctFile, "Complete precinct data"]]) {
    const link = document.createElement("a");
    link.href = file.url; link.textContent = `${text} (CSV · gzip)`;
    note.append(" ", link);
  }
  const replay = document.createElement("a");
  replay.href = marylandArchiveDownload;
  replay.textContent = "2016–2024 historical archive and offline reproduction (ZIP)";
  note.append(" ", replay);
  if (archival) note.append(" Showing the verified historical archive; these data are not refreshed by the hosted collector.");
  status.setAttribute("role", "status");
  load.type = "button"; load.textContent = "Compare registration groups";
  panel.append(title, note, load, status);
  let retry = false;
  load.addEventListener("click", async () => {
    load.disabled = true;
    status.textContent = "Checking the stored group counts…";
    try {
      const bytes = await checkedCountyBody(groupFile.url, groupFile, retry);
      const csv = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
      const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
      const keys = historicalCsvLine(header), frames = new Map(), seen = new Set();
      const columns = ["election_date", "geography", "registration_affiliation", "reported_ballot_activity",
        "eligible_registered", "reported_ballot_activity_without_precinct", "participation_measure", "source_status",
        "report_edition", "source_sha256"];
      const editions = new Map([
        ["2016-11-08", [6, ""]], ["2018-11-06", [6, ""]], ["2020-11-03", [8, ""]],
        ["2022-11-08", [7, "December 8, 2022"]], ["2024-11-05", [7, "April 29, 2026"]],
      ]);
      if (!lines.length || lines.length > 850 || columns.some(c => !keys.includes(c)))
        throw new Error("Missing Maryland profile");
      for (const line of lines) {
        const row = historicalCsvLine(line);
        const [date, place, party, activity, registered, unplaced, measure, sourceStatus, edition, sha] =
          columns.map(key => row[keys.indexOf(key)]);
        const id = `${date}/${place}/${party}`;
        if (row.length !== keys.length || !editions.has(date) || !place || !party
            || seen.has(id) || measure !== "reported_ballot_activity_voter_file_snapshot"
            || !["reported", "retained_after_failure"].includes(sourceStatus) || edition !== editions.get(date)[1]
            || !/^[a-f0-9]{64}$/.test(sha)
            || ![activity, registered, unplaced].every(n => /^\d+$/.test(n) && Number.isSafeInteger(Number(n)))
            || Number(unplaced) > Number(activity)) throw new Error("Invalid Maryland profile");
        seen.add(id);
        if (!frames.has(date)) frames.set(date, { places: new Map(), sourceStatus, edition, sha });
        const frame = frames.get(date);
        if (frame.sourceStatus !== sourceStatus || frame.edition !== edition || frame.sha !== sha)
          throw new Error("Mixed Maryland editions");
        if (!frame.places.has(place)) frame.places.set(place, []);
        frame.places.get(place).push([party, Number(activity), Number(registered), Number(unplaced)]);
      }
      if ([...frames].some(([date, { places }]) => places.size !== 25 || !places.has("Maryland")
          || [...places.values()].some(rows => rows.length !== editions.get(date)[0])))
        throw new Error("Incomplete Maryland profile");
      const election = document.createElement("select"), area = document.createElement("select");
      election.setAttribute("aria-label", "Maryland election");
      area.setAttribute("aria-label", "Maryland locality");
      for (const date of [...frames.keys()].sort().reverse()) election.add(new Option(date));
      const wrapper = document.createElement("div"), table = document.createElement("table");
      wrapper.className = "table-wrap"; wrapper.tabIndex = 0;
      wrapper.setAttribute("role", "region"); wrapper.setAttribute("aria-label", title.textContent);
      const caption = table.createCaption(), head = table.createTHead().insertRow(), body = table.createTBody();
      for (const text of ["Registration affiliation", "Ballot activity", "Eligible registrations", "Activity without precinct"]) {
        const cell = document.createElement("th");
        cell.scope = "col"; cell.textContent = text; head.append(cell);
      }
      const updateMap = installMarylandPrecinctMap(panel);
      const render = () => {
        const { places, sourceStatus, edition, sha } = frames.get(election.value);
        const rows = places.get(area.value);
        updateMap({ date: election.value, county: area.value, sha,
          activity: rows.reduce((sum, row) => sum + row[1], 0),
          unplaced: rows.reduce((sum, row) => sum + row[3], 0) });
        caption.textContent = `${area.value} · ${election.value}`;
        status.textContent = (edition ? `Voter-file snapshot dated ${edition}.` : "The archive does not give a voter-file snapshot date.")
          + (sourceStatus === "reported" ? "" : " Showing last verified edition.");
        body.replaceChildren();
        for (const [name, ...values] of rows) {
          const row = body.insertRow(), label = document.createElement("th");
          label.scope = "row"; label.textContent = name; row.append(label);
          for (const n of values) row.insertCell().textContent = n.toLocaleString("en-US");
        }
      };
      const selectAreas = () => {
        const previous = area.value;
        const choices = ["Maryland", ...[...frames.get(election.value).places.keys()].filter(k => k !== "Maryland").sort()];
        area.replaceChildren(...choices.map(k => new Option(k === "Maryland" ? "Statewide" : k, k)));
        if (choices.includes(previous)) area.value = previous;
        render();
      };
      election.addEventListener("change", selectAreas);
      area.addEventListener("change", render);
      wrapper.append(table);
      panel.append(election, " · ", area, wrapper);
      selectAreas();
      load.remove();
    } catch {
      retry = true;
      load.disabled = false;
      status.textContent = "The stored Maryland group counts could not be verified.";
      load.textContent = "Retry Maryland group counts";
    }
  });
  return panel;
}

export function installMarylandCoverage(parent, sources) {
  try {
    const groups = coverageCsvFile(sources, marylandGroupPath);
    const precincts = coverageCsvFile(sources, marylandPrecinctPath);
    if (groups && precincts) {
      parent.append(installMarylandAffiliationSnapshots(groups, precincts));
      return;
    }
  } catch {
    const notice = document.createElement("p");
    notice.textContent = "The Maryland participation download descriptors could not be verified.";
    parent.append(notice);
  }
  parent.append(installMarylandAffiliationSnapshots(...marylandArchive, { archival: true }));
}

function installNorthCarolina2006CountyRates() {
  const panel = document.createElement("details"), heading = document.createElement("summary");
  const note = document.createElement("p"), download = document.createElement("a");
  const source = document.createElement("a");
  const button = document.createElement("button"), status = document.createElement("p");
  heading.textContent = "North Carolina county turnout, 2006";
  download.href = new URL("../participation-archive-geometry/nc-2006-county-turnout.csv", import.meta.url).href;
  download.download = "nc-2006-county-turnout.csv";
  download.textContent = "All 100 county rates (CSV)";
  source.href = "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2006_11_07/voter_turnout_data_20061107.pdf";
  source.textContent = "Original report (PDF)";
  note.append("The state election office published these rounded percentages without the underlying count or denominator. "
    + "They are separate from EAC counts and rates. ", download, " · ", source);
  button.type = "button"; button.textContent = "Load published county rates";
  status.setAttribute("role", "status");
  panel.append(heading, note, button, status);
  let retry = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const body = await checkedCountyBody(download.href, nc2006CountyCsv, retry);
      const [header, ...lines] = new TextDecoder().decode(body).trimEnd().split(/\r?\n/);
      if (header !== "election_date,county_fips,county,published_turnout_pct,measure,denominator_basis,source_page,source_url,source_sha256"
          || lines.length !== 100) throw new Error("County rate inventory differs");
      const rows = new Map([["state", null]]);
      for (const line of lines) {
        const [date, id, name, rate, measure, basis] = historicalCsvLine(line);
        if (date !== "2006-11-07" || !/^37[0-9]{3}$/.test(id) || rows.has(id) || !name
            || !/^(?:\d{1,2}|100)$/.test(rate) || measure !== "published_overall_turnout"
            || basis !== "not_specified_in_report") throw new Error("County rate record differs");
        rows.set(id, { name, rate: Number(rate) });
      }
      const state = document.createElement("select"), year = document.createElement("select");
      state.add(new Option("North Carolina", "NC"));
      year.add(new Option("2006", "2006"));
      installHistoricalCountyMap(panel, state, year, [], { NC: "North Carolina" },
        () => ({ code: "NC", date: "2006-11-07", rows, rateOnly: true }));
      const wrap = document.createElement("div"), table = document.createElement("table");
      wrap.className = "table-wrap"; wrap.tabIndex = 0;
      wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", "Published county rates");
      table.createCaption().textContent = "November 7, 2006 general election";
      const headerRow = table.createTHead().insertRow(), tbody = table.createTBody();
      for (const label of ["County", "Published turnout"]) {
        const th = document.createElement("th");
        th.scope = "col"; th.textContent = label; headerRow.append(th);
      }
      for (const row of rows.values()) {
        if (!row) continue;
        const tr = tbody.insertRow(), nameCell = document.createElement("th");
        nameCell.scope = "row"; nameCell.textContent = row.name; tr.append(nameCell);
        tr.insertCell().textContent = `${row.rate}%`;
      }
      const verifiedDownload = URL.createObjectURL(new Blob([body], { type: "text/csv" }));
      download.href = verifiedDownload;
      window.addEventListener("pagehide", event => {
        if (!event.persisted) URL.revokeObjectURL(verifiedDownload);
      });
      wrap.append(table); panel.append(wrap); button.remove();
      status.textContent = "";
    } catch {
      retry = true; button.disabled = false;
      status.textContent = "The county rate table could not be verified.";
      button.textContent = "Retry published county rates";
    }
  });
  return panel;
}

export function indianaTurnoutDownload(sources) {
  try {
    return coverageCsvFile(sources, indianaTurnoutPath)?.url ?? null;
  } catch {
    return null;
  }
}

export function stateCountyArchivesDownload(sources) {
  try {
    return coverageCsvFile(sources, stateCountyArchivesPath)?.url ?? null;
  } catch {
    return null;
  }
}

export function publishedCpsRows(csv, summary, { archived = false } = {}) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const columns = historicalCsvLine(header);
  const rates = ["vap_voted", "cvap_voted", "vap_registered", "cvap_registered"];
  const required = ["year", "election_type", "state_code", "dimension", "group", "source_table",
    "source_url", "confidence_level_pct", ...rates.flatMap(key => [`${key}_pct`, `${key}_moe_pp`])];
  if (summary?.separate_from_other_survey_series !== true || summary.administratively_observed_turnout !== false
      || summary.states_and_dc !== 51 || lines.length !== summary.rows || lines.length > 20000
      || required.some(key => !columns.includes(key)) || new Set(columns).size !== columns.length)
    throw new Error("Incomplete published Census tables");
  const seen = new Set(), byYear = new Map(), expectedStates = new Set([...countStates, "US"]);
  const rows = lines.map(line => {
    const cells = historicalCsvLine(line);
    if (cells.length !== columns.length) throw new Error("Census CSV record differs");
    const row = Object.fromEntries(columns.map((key, index) => [key, cells[index]]));
    const year = Number(row.year), code = row.state_code;
    const earlyVolume = year === 2000 ? 542 : year === 2002 ? 552 : year === 2004 ? 556 : null;
    const earlyText = year === 1996 ? `504/tab${row.source_table}.txt`
      : year === 1998 ? "523-rv/tab04.txt" : null;
    const nativeTables = year === 1996
      ? { overall: ["4a", "4b", "4c"], age: ["4b"], sex: ["4b", "4c"], race_or_hispanic_origin: ["4a"] }
      : year === 1998 ? { overall: ["4"], sex: ["4"], race_or_hispanic_origin: ["4"] }
      : earlyVolume ? { overall: ["4a", "4b", "4c"], age: ["4b"], sex: ["4a"], race_or_hispanic_origin: ["4a"] }
      : { overall: ["4b", "4c"], age: ["4c"], sex: ["4b"], race_or_hispanic_origin: ["4b"] };
    const key = `${year}/${code}/${row.group}/${row.source_table}`;
    const uncertainty = year === 1996 ? "not_published" : year === 1998 ? "standard_error" : "margin_90";
    const numeric = v => typeof v === "string" && /^\d+(?:\.\d+)?$/.test(v) && Number(v) <= 100;
    if (!summary.years.includes(year) || !expectedStates.has(code) || seen.has(key)
        || archived !== [1996, 1998, 2000].includes(year)
        || row.election_type !== (year % 4 === 0 ? "presidential" : "midterm")
        || !Object.hasOwn(nativeTables, row.dimension) || !nativeTables[row.dimension].includes(row.source_table)
        || row.confidence_level_pct !== (earlyText ? "" : "90")
        || (archived && row.source_uncertainty !== uncertainty)
        || !(earlyText
          ? row.source_url === `https://www2.census.gov/programs-surveys/cps/tables/p20/${earlyText}`
          : earlyVolume
          ? row.source_url === `https://www2.census.gov/programs-surveys/cps/tables/p20/${earlyVolume}/tab0${row.source_table}.xls`
          : year === 2008
          ? row.source_url === `https://www2.census.gov/programs-surveys/cps/tables/p20/562-rv/table-0${row.source_table}.xls`
          : /^https:\/\/www2\.census\.gov\/programs-surveys\/cps\/tables\/p20\/(?:\d+|voting-registration-2010-election)\/[a-z0-9_]+\.xlsx?$/.test(row.source_url)))
      throw new Error("Census cohort or source identity differs");
    for (const prefix of rates) {
      const point = row[`${prefix}_pct`], moe = row[`${prefix}_moe_pp`];
      const se = row[`${prefix}_se_pp`] ?? "";
      if (((earlyVolume || earlyText) && !prefix.startsWith(row.source_table === "4c" ? "cvap_" : "vap_") && point !== "")
        || (earlyText ? moe !== "" : (point === "") !== (moe === ""))
        || (year === 1998 && prefix.startsWith("vap_") ? (point === "") !== (se === "") : se !== "")
        || [point, moe, se].some(v => v !== "" && !numeric(v)))
        throw new Error("Census point or margin differs");
    }
    seen.add(key);
    if (!byYear.has(year)) byYear.set(year, new Set());
    byYear.get(year).add(code);
    return row;
  });
  if (byYear.size !== summary.years.length || [...byYear.values()].some(states => states.size !== expectedStates.size)
      || rows.filter(r => r.cvap_voted_pct !== "").length !== summary.cvap_voting_rates)
    throw new Error("Census coverage differs from the accepted runtime");
  return rows.filter(r => r.dimension !== "overall" || (Number(r.year) <= 2004
    ? r.source_table !== "4b" : r.source_table === "4b"));
}

export function cpsRowsForBasis(rows, basis) {
  return rows.filter(r => {
    const year = Number(r.year);
    if ([1996, 1998, 2000].includes(year)) return basis === (r.source_table === "4c" ? "cvap" : "vap");
    return r.group !== "Total" || year > 2004 || r.source_table === (basis === "cvap" ? "4c" : "4a");
  });
}

export function overallCpsRows(csv, summary) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const columns = historicalCsvLine(header);
  const required = ["year", "election_type", "state_code", "denominator_basis", "citizenship_measurement_caution",
    "reported_voted_pct", "reported_registered_pct", "voted_source_marker", "registered_source_marker",
    "voted_source_url", "registered_source_url"];
  const states = new Set(countStates), seen = new Set();
  const years = new Set(summary?.years);
  if (summary?.administratively_observed_turnout !== false || summary.published_margins_of_error !== false
      || summary.states_and_dc !== states.size || lines.length !== summary.rows || lines.length > 10000
      || lines.length !== years.size * states.size * 2 || required.some(key => !columns.includes(key))
      || new Set(columns).size !== columns.length)
    throw new Error("Incomplete statewide Census history");
  const counts = {voted: 0, registered: 0};
  const base = "https://www2.census.gov/programs-surveys/cps/tables/time-series/voting-historical-time-series/";
  return lines.map((line, index) => {
    const cells = historicalCsvLine(line);
    if (cells.length !== columns.length) throw new Error("Census history row differs");
    const row = Object.fromEntries(columns.map((key, idx) => [key, cells[idx]]));
    const year = Number(row.year), basis = row.denominator_basis;
    const presidential = year % 4 === 0;
    const key = `${year}/${row.state_code}/${basis}`;
    if (!years.has(year) || !states.has(row.state_code) || !["vap", "cvap"].includes(basis) || seen.has(key)
        || row.election_type !== (presidential ? "presidential" : "midterm")
        || row.citizenship_measurement_caution !== (basis === "cvap" && year < 1996 ? "True" : "False"))
      throw new Error("Census history cohort differs");
    seen.add(key);
    for (const [measure, suffix] of [["voted", "a"], ["registered", "b"]]) {
      const point = row[`reported_${measure}_pct`], marker = row[`${measure}_source_marker`];
      if (row[`${measure}_source_url`] !== `${base}${presidential ? "a5" : "hst_vote03"}${suffix}.xlsx`
          || (point === "" ? !["N", "not_in_table"].includes(marker)
            : marker !== "" || !/^\d+(?:\.\d+)?$/.test(point) || Number(point) > 100))
        throw new Error("Census history source cell differs");
      counts[measure] += Number(point !== "");
    }
    if (index === lines.length - 1 && (counts.voted !== summary.reported_voting_rates
        || counts.registered !== summary.reported_registration_rates))
      throw new Error("Census history coverage differs");
    return row;
  });
}

export function cpsMapCells(rows, year, basis, group) {
  const cells = new Map();
  for (const row of rows) {
    if (row.year !== year || row.state_code === "US"
        || (group ? row.group !== group : row.denominator_basis !== basis)) continue;
    const point = group ? row[`${basis}_voted_pct`] : row.reported_voted_pct;
    if (point !== "") cells.set(row.state_code, { point, moe: group ? row[`${basis}_voted_moe_pp`] || null : null });
  }
  return cells;
}

function addCpsMap(panel, rows, summary, basis, state, names, group) {
  const load = document.createElement("button"), status = document.createElement("p");
  load.type = "button"; load.textContent = group ? "Show turnout map by group" : "Show statewide turnout map";
  status.setAttribute("role", "status");
  panel.append(load, status);
  load.addEventListener("click", async () => {
    load.disabled = true;
    status.textContent = "Loading state outlines…";
    try {
      const response = await fetch(participationDownload("/voter-participation/data/states.geojson"),
        { signal: AbortSignal.timeout(20_000) });
      if (!response.ok) throw new Error("State outlines could not be loaded");
      const collection = await response.json();
      const shapes = projectStateContext(collection.features);
      const codes = new Set(shapes.map(({ feature }) => feature.properties.STUSAB));
      if (shapes.length !== countStates.length || !countStates.every(code => codes.has(code))
          || shapes.some(({ d }) => !d || /NaN|Infinity/.test(d)))
        throw new Error("State map inventory differs");
      const figure = document.createElement("figure"), caption = document.createElement("figcaption");
      const label = document.createElement("label"), year = document.createElement("select");
      for (const value of [...summary.years].reverse()) year.add(new Option(String(value), String(value)));
      label.append("Map election year ", year);
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 1000 640");
      svg.setAttribute("width", "100%");
      svg.setAttribute("role", "img");
      const colors = ["#eef5f3", "#c5e0d9", "#87bbac", "#458778", "#23564f"];
      const paint = () => {
        const byCode = cpsMapCells(rows, year.value, basis.value, group?.value);
        svg.replaceChildren();
        const metric = basis.selectedOptions[0].textContent;
        const cohort = group ? `, ${group.selectedOptions[0].textContent}` : "";
        svg.setAttribute("aria-label", `${year.value} reported voting rates by state${cohort}, ${metric}`);
        for (const { feature, d } of shapes) {
          const code = feature.properties.STUSAB, row = byCode.get(code);
          const shade = row ? colors.filter((_, i) => i === 0 || Number(row.point) >= 30 + i * 10).at(-1) : "#dededb";
          const path = document.createElementNS(svg.namespaceURI, "path");
          const title = document.createElementNS(svg.namespaceURI, "title");
          path.setAttribute("d", d);
          path.setAttribute("fill", shade);
          path.setAttribute("fill-rule", "evenodd");
          path.setAttribute("stroke", code === state.value ? "#222" : "#fcfcfa");
          path.setAttribute("stroke-width", code === state.value ? "2" : "1");
          path.dataset.state = code;
          path.dataset.rate = row ? row.point : "";
          title.textContent = `${names[code] || feature.properties.NAME}: `
            + (row ? `${row.point}%${row.moe === null ? "" : ` ± ${row.moe} pp`}` : "not available");
          path.append(title); svg.append(path);
        }
        caption.textContent = `${byCode.size} of 51 jurisdictions with published rates. `
          + "Light to dark: below 40%, 40–49%, 50–59%, 60–69%, 70% or more. Gray: not available. "
          + "State outlines are for display; Alaska and Hawaii are insets. "
          + (group ? "Colors show point estimates, not statistical differences. See the table for uncertainty and holds."
            : basis.value === "cvap" && Number(year.value) < 1996 ? "Earlier citizenship measure; not directly comparable." : "");
      };
      for (const control of [year, basis, state, group].filter(Boolean)) control.addEventListener("change", paint);
      figure.append(label, svg, caption);
      load.replaceWith(figure);
      status.textContent = "";
      paint();
    } catch {
      load.disabled = false;
      status.textContent = "The state map is unavailable; the table and CSV still work.";
    }
  });
}

function installOverallCps(file, summary, names) {
  const panel = document.createElement("details"), heading = document.createElement("summary");
  const note = document.createElement("p"), download = document.createElement("a");
  const button = document.createElement("button"), status = document.createElement("p");
  heading.textContent = "Compare statewide Census turnout since 1972";
  download.href = file.url;
  download.textContent = "Complete statewide Census history (CSV · gzip)";
  note.append("Self-reported survey rates, not ballot counts. These workbooks do not publish margins of error. "
    + "Early state coverage is partial, and citizen voting-age estimates before 1996 are not directly comparable with later years. ",
    download);
  button.type = "button"; button.textContent = "Load statewide Census history";
  status.setAttribute("role", "status");
  panel.append(heading, note, button, status);
  let retry = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    status.textContent = "Checking the statewide Census history…";
    try {
      const body = await checkedCountyBody(file.url, file, retry);
      const text = await new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
      const rows = overallCpsRows(text, summary);
      const state = document.createElement("select"), basis = document.createElement("select");
      const election = document.createElement("select");
      for (const code of countStates) state.add(new Option(names[code] || code, code));
      basis.add(new Option("Total voting-age population", "vap"));
      basis.add(new Option("Citizen voting-age population", "cvap"));
      election.append(new Option("All elections", ""), new Option("Presidential", "presidential"), new Option("Midterm", "midterm"));
      const scroller = document.createElement("div"), table = document.createElement("table");
      scroller.className = "table-wrap"; scroller.tabIndex = 0;
      scroller.setAttribute("role", "region"); scroller.setAttribute("aria-label", "Statewide Census history");
      const caption = table.createCaption(), header = table.createTHead().insertRow(), tbody = table.createTBody();
      for (const label of ["Election", "Reported voted", "Reported registered", "Census workbooks"]) {
        const th = document.createElement("th");
        th.scope = "col"; th.textContent = label; header.append(th);
      }
      const render = () => {
        caption.textContent = `${names[state.value] || state.value} · ${basis.selectedOptions[0].textContent}`;
        tbody.replaceChildren();
        for (const row of rows.filter(r => r.state_code === state.value && r.denominator_basis === basis.value
          && (!election.value || r.election_type === election.value))) {
          const tr = tbody.insertRow(), label = document.createElement("th");
          label.scope = "row"; label.textContent = `${row.year} ${row.election_type}`; tr.append(label);
          for (const measure of ["voted", "registered"]) {
            const point = row[`reported_${measure}_pct`];
            tr.insertCell().textContent = point === "" ? "Not available" : `${point}%`;
          }
          const source = tr.insertCell();
          for (const [i, measure] of ["voted", "registered"].entries()) {
            const link = document.createElement("a");
            link.href = row[`${measure}_source_url`];
            link.textContent = measure === "voted" ? "Voting" : "Registration";
            source.append(i ? " · " : "", link);
          }
          if (row.citizenship_measurement_caution === "True" && row.reported_voted_pct !== "")
            source.append(" · Earlier citizenship measure");
        }
      };
      for (const [slug, name, control] of [["state", "State", state], ["denominator", "Denominator", basis],
        ["election", "Election type", election]]) {
        const label = document.createElement("label");
        control.id = `cps-overall-${slug}`;
        label.htmlFor = control.id; label.textContent = `${name} `;
        panel.append(label, control, " ");
        control.addEventListener("change", render);
      }
      addCpsMap(panel, rows, summary, basis, state, names);
      scroller.append(table); panel.append(scroller);
      render();
      status.textContent = ""; button.remove();
    } catch {
      retry = true; button.disabled = false;
      button.textContent = "Retry statewide Census history";
      status.textContent = "The statewide Census history could not be verified.";
    }
  });
  return panel;
}

export function publishedCpsStatus(check) {
  if (!check) return "";
  if (check.status === "reported" && check.rows > 0) return "The November 2026 Census tables are included.";
  if (check.status === "retained_after_failure" && check.rows > 0)
    return "The latest November 2026 Census check failed; the last verified tables are still included.";
  if (check.status === "report_not_linked")
    return "The latest Census check did not find both November 2026 tables.";
  if (check.status === "source_stopped")
    return "Access to the November 2026 Census source was denied; no 2026 tables were accepted.";
  return "The latest November 2026 Census check could not verify the tables.";
}

function installPublishedCps(sources, file, names, { archived = false } = {}) {
  const panel = document.createElement("details"), heading = document.createElement("summary");
  const note = document.createElement("p"), download = document.createElement("a");
  const button = document.createElement("button"), status = document.createElement("p");
  heading.textContent = archived ? "Compare Census survey turnout by group, 1996–2000"
    : "Compare Census survey turnout by state and group";
  download.href = file.url;
  download.textContent = "Complete Census state turnout tables (CSV · gzip)";
  note.append("Census survey estimates of reported voting and registration, not official ballot counts. "
    + (archived ? "The 1998 tables give standard errors, not margins of error. The 1996 tables shown here do not report uncertainty. "
      : "The margins of error are for individual estimates at the 90% confidence level, not for changes across years. ")
    + "Race and Hispanic-origin categories can overlap. The age bands available vary by election. ", download);
  button.type = "button"; button.textContent = "Load Census turnout comparisons";
  status.setAttribute("role", "status");
  panel.append(heading, note, button, status);
  const survey = sources.supported_release.coverage.historical_survey;
  const series = archived ? survey.archived_state_tables : survey.published_state_tables;
  const checkMessage = archived ? "" : publishedCpsStatus(survey.current_published_state_tables);
  if (checkMessage) {
    const sourceStatus = document.createElement("p");
    sourceStatus.textContent = checkMessage;
    note.after(sourceStatus);
  }
  let retry = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    status.textContent = "Checking the Census turnout tables…";
    try {
      const body = await checkedCountyBody(file.url, file, retry);
      const text = await new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
      const rows = publishedCpsRows(text, series, { archived });
      const state = document.createElement("select"), group = document.createElement("select");
      const basis = document.createElement("select");
      state.append(new Option("United States", "US"), ...countStates.map(code => new Option(names[code] || code, code)));
      const groups = new Map(rows.map(r => [r.group, r.dimension]));
      for (const label of groups.keys())
        group.add(new Option(label === "Total" ? "All adults" : label, label));
      basis.add(new Option("Citizen voting-age population", "cvap"));
      basis.add(new Option("Total voting-age population", "vap"));
      const scroller = document.createElement("div"), table = document.createElement("table");
      scroller.className = "table-wrap"; scroller.tabIndex = 0;
      scroller.setAttribute("role", "region"); scroller.setAttribute("aria-label", "Census turnout comparisons");
      const caption = table.createCaption(), header = table.createTHead().insertRow();
      for (const label of ["Election", "Reported voted", "Reported registered", "Census workbook"]) {
        const th = document.createElement("th");
        th.scope = "col"; th.textContent = label; header.append(th);
      }
      const tbody = table.createTBody();
      const render = () => {
        caption.textContent = `${names[state.value] || (state.value === "US" ? "United States" : state.value)} · `
          + `${group.selectedOptions[0].textContent} · ${basis.selectedOptions[0].textContent}`;
        tbody.replaceChildren();
        const selected = new Map(cpsRowsForBasis(rows, basis.value)
          .filter(r => r.state_code === state.value && r.group === group.value)
          .map(r => [Number(r.year), r]));
        for (const year of series.years) {
          const r = selected.get(year);
          const tr = tbody.insertRow(), label = document.createElement("th");
          label.scope = "row"; label.textContent = `${year} ${year % 4 === 0 ? "presidential" : "midterm"}`;
          tr.append(label);
          if (!r) {
            const missing = tr.insertCell();
            missing.colSpan = 3;
            const heldAge = year === 2008 ? series.held_2008_age_frames
              : series.held_vap_age_frames?.[String(year)];
            missing.textContent = groups.get(group.value) === "age" && heldAge?.includes(state.value)
              ? "Age estimates withheld: Census tables disagree"
              : "Group not published for this state and election";
            continue;
          }
          for (const measure of ["voted", "registered"]) {
            const key = `${basis.value}_${measure}`;
            const withheld = r.source_markers?.includes(`"${key}_pct":"invalid_published_rate"`);
            const notInTable = r.source_markers?.includes(`"${key}_pct":"not_in_table"`);
            const disagreement = r.source_markers?.includes(`"${key}_pct":"source_control_disagreement"`);
            const moe = r[`${key}_moe_pp`], se = r[`${key}_se_pp`];
            tr.insertCell().textContent = r[`${key}_pct`] === "" ? (withheld ? "Withheld: invalid source rate"
              : disagreement ? "Withheld: Census counts disagree"
              : notInTable ? "Not published for this denominator" : "Not published")
              : `${r[`${key}_pct`]}%` + (moe ? ` ± ${moe} pp` : se ? ` (SE ${se} pp)` : "");
          }
          const source = document.createElement("a");
          source.href = r.source_url; source.textContent = `Table ${r.source_table}`;
          tr.insertCell().append(source);
        }
      };
      button.replaceWith(...[[state, "State or U.S."], [group, "Census group"], [basis, "Denominator"]]
        .map(([select, text]) => {
          const label = document.createElement("label");
          label.append(`${text} `, select, " ");
          select.addEventListener("change", render);
          return label;
        }));
      status.textContent = "";
      addCpsMap(panel, rows, series, basis, state, names, group);
      scroller.append(table); panel.append(scroller); render(); state.focus();
    } catch {
      retry = true;
      status.textContent = "The Census tables could not be verified. The complete download remains available.";
      button.disabled = false;
      button.textContent = "Retry Census turnout comparisons";
    }
  });
  return panel;
}

const coloradoStateBallotGaps = new Map([["1992-11-03", 30], ["2012-11-06", 1240], ["2014-11-04", 36]]);
const coloradoCountyBallotGaps = new Map([
  ...Object.entries({
    Broomfield: 474, "Clear Creek": 126, Conejos: 59, Delta: 224, Dolores: 27,
    Douglas: 3635, Grand: 168, Gunnison: 97, "Kit Carson": 178, Larimer: 2052,
    Moffat: 126, Montrose: 383, Pitkin: 205, "Rio Blanco": 43, "San Miguel": 2,
    Summit: 229, Weld: 2662, Yuma: 64,
  }).map(([county, gap]) => [`2012-11-06/${county}`, gap]),
  ["2014-11-04/Larimer", 43], ["2014-11-04/Rio Grande", 48],
  ["2014-11-04/Summit", 78], ["2016-11-08/Larimer", 32],
]);
const coloradoCountOnlyReasons = new Map([
  ...["1992-11-03", "1996-11-05", "2002-11-05", "2012-11-06", "2018-11-06", "2020-11-03"]
    .map(date => [date, "registration_column_party_labeled"]),
  ...["2004-11-02", "2006-11-07"].map(date => [date, "registration_not_in_report"]),
  ...["2008-11-04", "2010-11-02"].map(date => [date, "active_registration_only"]),
]);

export function stateCountyArchiveFrames(csv, { currentCalifornia = false, currentNebraska = false } = {}) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const columns = historicalCsvLine(header);
  const required = ["state_code", "year", "election_date", "geography_level", "geography",
    "reported_ballots_cast", "reported_registered_voters", "qualified_same_report_registration_fraction_pct",
    "rate_hold_reason", "source_status", "source_url", "source_sha256", "report_edition"];
  const sourceMeasures = ["participation_measure", "reported_total_voters", "registration_basis"];
  const hasMeasures = sourceMeasures.some(field => columns.includes(field));
  if (new Set(columns).size !== columns.length || !lines.length || lines.length > 12_000
      || [...required, ...(hasMeasures ? sourceMeasures : [])].some(field => !columns.includes(field)))
    throw new Error("Incomplete election-office archive");
  const frames = new Map(), integer = text => /^\d+$/.test(text) && Number.isSafeInteger(Number(text));
  for (const line of lines) {
    const cells = historicalCsvLine(line);
    if (cells.length !== columns.length) throw new Error("Invalid election-office archive record");
    const field = key => cells[columns.indexOf(key)];
    const code = field("state_code"), date = field("election_date"), year = field("year");
    const level = field("geography_level"), name = field("geography");
    const measure = hasMeasures ? field("participation_measure") : "ballots_cast";
    const ballots = field("reported_ballots_cast"), voters = hasMeasures ? field("reported_total_voters") : "";
    const credits = field("reported_voter_history_credits") ?? "";
    const value = measure === "ballots_cast" && voters === "" && credits === "" ? ballots
      : measure === "total_voters" && ballots === "" && credits === "" ? voters
      : measure === "voter_history_credits" && code === "WV" && ["2008", "2010"].includes(year)
        && ballots === "" && voters === "" ? credits : "";
    const stock = field("reported_registered_voters"), fraction = field("qualified_same_report_registration_fraction_pct");
    const rate = fraction === "" ? null : Number(fraction), hold = field("rate_hold_reason");
    const status = field("source_status"), url = field("source_url"), sha = field("source_sha256");
    const basis = hasMeasures ? field("registration_basis") : "Report's registered voters";
    const stateGap = field("state_ballot_shortfall") ?? "";
    const countyGap = field("county_ballot_shortfall") ?? "";
    const virginia = code === "VA" && date === "2022-11-08";
    const minnesota = code === "MN" && measure === "total_voters" && basis === "Pre-registered at 7 a.m."
      && stock === "" && rate === null && hold === "pre_registration_excludes_same_day_registrants";
    const countOnly = minnesota || (measure === "ballots_cast" && basis === "" && stock === "" && rate === null
      && ((code === "WY" && hold === "registration_not_in_report")
        || (virginia && hold === "registration_not_in_report")
        || (code === "CO" && hold === coloradoCountOnlyReasons.get(date))));
    const edition = field("report_edition"), note = field("report_note") || "";
    if (!countStates.includes(code) || !/^\d{4}$/.test(year) || !/^\d{4}-11-\d{2}$/.test(date)
        || !date.startsWith(`${year}-`) || (!["state", "county"].includes(level)
          && !(virginia && level === "county_equivalent"))
        || (code === "VA" && (!virginia || !countOnly
          || (level === "state" ? name !== "Virginia" : !name.endsWith(level === "county" ? " COUNTY" : " CITY"))))
        || (currentCalifornia || currentNebraska
          ? code !== (currentCalifornia ? "CA" : "NE") || date !== "2026-11-03" || measure !== "total_voters"
          : Number(year) >= 2026)
        || !name || !integer(value) || (!countOnly && (!basis || !integer(stock)))
        || (stateGap !== "" && (code !== "CO" || level !== "state" || !integer(stateGap)
          || Number(stateGap) !== coloradoStateBallotGaps.get(date)
          || (!countOnly && hold !== "state_ballot_control_disagrees")))
        || (hold === "state_ballot_control_disagrees" && !stateGap)
        || (countyGap !== "" && (code !== "CO" || level !== "county"
          || !integer(countyGap) || Number(countyGap) !== coloradoCountyBallotGaps.get(`${date}/${name}`)))
        || !["reported", "retained_after_failure"].includes(status)
        || !/^https:\/\/[^/@?#\s]+\/[^#\s]+$/.test(url) || !/^[a-f0-9]{64}$/.test(sha)
        || (rate === null ? !hold : hold || !/^\d+(?:\.\d+)?(?:e[+-]?\d+)?$/i.test(fraction)
          || !Number.isFinite(rate) || Number(stock) <= 0 || Number(value) > Number(stock)
          || Math.abs(rate - 100 * Number(value) / Number(stock)) > 1e-10))
      throw new Error("Election-office count, fraction or report identity differs");
    const key = `${code}/${date}`;
    if (!frames.has(key)) frames.set(key, { code, date, measure, basis, edition, status, url, sha, note, rows: new Map() });
    const frame = frames.get(key), rowKey = level === "state" ? "state" : `county/${name}`;
    if (frame.rows.has(rowKey) || frame.measure !== measure || frame.basis !== basis || frame.edition !== edition
        || frame.status !== status || frame.url !== url || frame.sha !== sha || frame.note !== note)
      throw new Error("Mixed or repeated election-office report rows");
    frame.rows.set(rowKey, { name, count: Number(value), registered: countOnly ? null : Number(stock), rate, hold,
      ...(stateGap || countyGap ? { shortfall: Number(stateGap || countyGap) } : {}) });
  }
  if ([...frames.values()].some(frame => !frame.rows.has("state") || frame.rows.size < 2))
    throw new Error("Election-office archive lacks a state or county total");
  if (currentCalifornia && [...frames.values()].some(frame => frame.rows.size !== 59))
    throw new Error("Incomplete California statewide and county report");
  if ([...frames.values()].some(frame => frame.code === "NE" && frame.rows.size !== 94))
    throw new Error("Incomplete Nebraska statewide and county report");
  for (const frame of frames.values()) {
    if (!["CO", "VA", "MN"].includes(frame.code)) continue;
    const state = frame.rows.get("state");
    const countySum = [...frame.rows.entries()].reduce((sum, [key, row]) => sum + (key === "state" ? 0 : row.count), 0);
    if (frame.code === "MN") {
      if (frame.rows.size !== 88 || state.count !== countySum || state.name !== "Minnesota"
          || [...frame.rows.values()].some(row => row.registered !== null || row.rate !== null))
        throw new Error("Incomplete or inconsistent Minnesota county report");
      continue;
    }
    if (frame.code === "VA") {
      if (frame.rows.size !== 134 || state.count !== countySum
          || [...frame.rows.keys()].filter(key => key.endsWith(" CITY")).length !== 38)
        throw new Error("Incomplete or inconsistent Virginia locality report");
      continue;
    }
    const beforeBroomfield = frame.date < "2002";
    if (frame.rows.size !== (beforeBroomfield ? 64 : 65)
        || frame.rows.has("county/Broomfield") === beforeBroomfield
        || state.count - countySum !== (state.shortfall ?? 0))
      throw new Error("Incomplete or inconsistent Colorado statewide and county report");
  }
  if ([...frames.values()].some(frame => frame.code === "WY" && frame.rows.size !== 24))
    throw new Error("Incomplete Wyoming statewide and county report");
  return [...frames.values()].sort((a, b) => a.code.localeCompare(b.code) || b.date.localeCompare(a.date));
}

const archiveMeasureLabel = measure => measure === "voter_history_credits" ? "Voter-history credits"
  : measure === "total_voters" ? "Total Voters" : "Ballots Cast";

export function nebraskaCountyReportsFrame(csv) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const columns = historicalCsvLine(header);
  const fields = ["county", "election_date", "disposition", "ballots", "election_day", "early", "provisional",
    "source_status", "report_status", "report_clock", "index_clock", "source_url", "source_sha256", "source_bytes"];
  if (lines.length !== 93 || new Set(columns).size !== columns.length
      || fields.some(field => !columns.includes(field))) throw new Error("Incomplete Nebraska county reports");
  const rows = new Map(), integer = text => /^\d+$/.test(text) && Number.isSafeInteger(Number(text));
  const clock = /^\d{1,2}\/\d{1,2}\/2026 \d{1,2}:\d{2} [AP]M$/;
  for (const line of lines) {
    const cells = historicalCsvLine(line), field = key => cells[columns.indexOf(key)];
    const name = field("county"), disposition = field("disposition"), url = field("source_url");
    const reportStatus = field("report_status"), sourceStatus = field("source_status");
    const measures = ["ballots", "election_day", "early", "provisional"].map(field);
    if (cells.length !== columns.length || !/^[A-Za-z]+(?: [A-Za-z]+)*$/.test(name)
        || rows.has(`county/${name}`) || field("election_date") !== "2026-11-03"
        || !/^[a-z_]+$/.test(disposition)) throw new Error("Invalid Nebraska county report identity");
    const observed = measures[0] !== "";
    const modes = measures.slice(1);
    if (observed ? (!integer(measures[0]) || (!modes.every(value => value === "")
        && (!modes.every(integer) || Number(measures[0]) !== modes.reduce((a, v) => a + Number(v), 0)))
        || sourceStatus !== (disposition === "reported" ? "reported" : "retained_after_failure")
        || !["official", "unofficial"].includes(reportStatus) || !clock.test(field("report_clock"))
        || !clock.test(field("index_clock")) || !/^[a-f0-9]{64}$/.test(field("source_sha256"))
        || !integer(field("source_bytes")) || Number(field("source_bytes")) <= 0
        || url !== `https://countyelectionresults.nebraska.gov/election_files/${encodeURIComponent(name)}/2026_General_${reportStatus}_results.pdf`)
      : (disposition === "reported" || fields.slice(3).some(key => field(key) !== "")))
      throw new Error("Invalid Nebraska county count or provenance");
    rows.set(`county/${name}`, { name, count: observed ? Number(measures[0]) : null, rate: null,
      disposition, sourceStatus, reportStatus, url, clock: field("report_clock") });
  }
  if (![...rows.values()].some(row => row.count !== null)) throw new Error("No verified county counts");
  return { code: "NE", date: "2026-11-03", measure: "ballots_cast", partialCountyReports: true, rows };
}

export function coloradoPrecinctFrames(csv) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const columns = historicalCsvLine(header);
  const fields = ["state_code", "election_date", "county", "precinct", "registered", "active", "inactive",
    "ballots_cast", "qualified_same_report_registration_fraction_pct", "rate_hold_reason", "source_status",
    "source_url", "source_sha256", "source_bytes", "registration_basis"];
  if (!lines.length || lines.length > 30_000 || new Set(columns).size !== columns.length
      || fields.some(field => !columns.includes(field))) throw new Error("Incomplete Colorado precinct statistics");
  const frames = new Map(), integer = text => /^\d+$/.test(text) && Number.isSafeInteger(Number(text));
  const editions = new Map([["2010-11-02", "25359"], ["2012-11-06", "25363"],
    ["2014-11-04", "25361"], ["2016-11-08", "25362"], ["2018-11-06", "25360"],
    ["2020-11-03", "25358"], ["2022-11-08", "25989"], ["2024-11-05", "26759"]]);
  for (const line of lines) {
    const cells = historicalCsvLine(line), field = key => cells[columns.indexOf(key)];
    const date = field("election_date"), id = editions.get(date);
    const county = field("county"), precinct = field("precinct"), disposition = field("rate_hold_reason");
    const integers = ["registered", "active", "inactive", "ballots_cast", "source_bytes"].map(field);
    const [registered, active, inactive, count, bytes] = integers.map(Number);
    const url = field("source_url"), sha = field("source_sha256"), status = field("source_status");
    const literalRate = field("qualified_same_report_registration_fraction_pct");
    const rate = literalRate === "" ? null : Number(literalRate);
    const gapLiteral = field("county_ballot_shortfall") ?? "";
    const shortfall = gapLiteral === "" ? 0 : Number(gapLiteral);
    const countOnly = coloradoCountOnlyReasons.has(date) && integers.slice(0, 3).every(value => value === "")
      && field("registration_basis") === "";
    const hold = countOnly ? coloradoCountOnlyReasons.get(date)
      : shortfall ? "county_ballot_control_disagrees"
      : count > registered ? "ballots_exceed_registered" : registered === 0 ? "no_positive_registration_denominator" : "";
    if (cells.length !== columns.length || field("state_code") !== "CO" || !id || !county || !/^\d{10}$/.test(precinct)
        || !(countOnly ? integers.slice(3) : integers).every(integer) || !bytes
        || (gapLiteral !== "" && (!integer(gapLiteral)
          || shortfall !== coloradoCountyBallotGaps.get(`${date}/${county}`)))
        || registered !== active + inactive || disposition !== hold
        || (hold ? rate !== null : rate === null || !Number.isFinite(rate) || Math.abs(rate - 100 * count / registered) > 1e-10)
        || !/^[a-f0-9]{64}$/.test(sha) || !["reported", "retained_after_failure"].includes(status)
        || (!countOnly && field("registration_basis") !== "Total registration (active plus inactive)")
        || url !== `https://co.elstats3.civera.com/api/download_contest/${id}_table.csv?split_party=false`)
      throw new Error("Colorado precinct statistics or provenance differ");
    if (!frames.has(date)) frames.set(date, { url, sha, bytes, status, counties: new Map(), ids: new Set() });
    const frame = frames.get(date);
    if (frame.ids.has(precinct) || frame.sha !== sha || frame.bytes !== bytes || frame.status !== status)
      throw new Error("Colorado precinct statistics mix editions or repeat a precinct");
    frame.ids.add(precinct);
    if (!frame.counties.has(county)) frame.counties.set(county, []);
    const units = frame.counties.get(county);
    if (units.length && (units[0].shortfall ?? 0) !== shortfall)
      throw new Error("Mixed Colorado county control dispositions");
    units.push({ precinct, count, registered: countOnly ? null : registered, rate, hold, ...(shortfall ? { shortfall } : {}) });
  }
  if ([...frames.values()].some(frame => frame.counties.size !== 64)) throw new Error("Incomplete Colorado precinct counties");
  return frames;
}

export function installColoradoPrecinctStatistics(file) {
  const panel = document.createElement("details"), title = document.createElement("summary");
  title.textContent = "Colorado historical precinct participation";
  const note = document.createElement("p"), load = document.createElement("button"), status = document.createElement("p");
  note.textContent = "Official ballots cast and total registration (active plus inactive). "
    + "A map appears only for an election and county with verified boundaries.";
  load.type = "button";
  load.textContent = "Load precinct statistics";
  status.setAttribute("role", "status");
  const download = document.createElement("a");
  download.href = file.url;
  download.textContent = "Complete Colorado precinct statistics (CSV · gzip)";
  panel.append(title, note, download, " · ", load, status);
  load.addEventListener("click", async () => {
    const retry = load.textContent === "Retry precinct statistics";
    load.disabled = true;
    status.textContent = "Checking the stored precinct statistics…";
    try {
      const bytes = await checkedCountyBody(file.url, file, retry);
      const csv = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
      const frames = coloradoPrecinctFrames(csv);
      const election = document.createElement("select"), county = document.createElement("select");
      election.setAttribute("aria-label", "Election date");
      county.setAttribute("aria-label", "County");
      for (const date of [...frames.keys()].sort().reverse()) election.add(new Option(date));
      const electionLabel = document.createElement("label"), countyLabel = document.createElement("label");
      electionLabel.append("Election date ", election);
      countyLabel.append("County ", county);
      const original = document.createElement("a");
      original.textContent = "Original voting statistics CSV";
      const wrapper = document.createElement("div"), table = document.createElement("table");
      wrapper.className = "table-wrap";
      wrapper.tabIndex = 0;
      wrapper.setAttribute("role", "region");
      wrapper.setAttribute("aria-label", "Colorado historical precinct participation");
      const caption = table.createCaption(), head = table.createTHead().insertRow(), body = table.createTBody();
      for (const label of ["Precinct", "Ballots cast", "Total registration", "Same-report registration fraction"]) {
        const cell = document.createElement("th");
        cell.scope = "col"; cell.textContent = label; head.append(cell);
      }
      const number = new Intl.NumberFormat("en-US");
      function render() {
        const frame = frames.get(election.value), rows = frame.counties.get(county.value);
        caption.textContent = `${county.value} County · ${election.value}`;
        original.href = frame.url;
        status.textContent = `${rows.length} reported precincts.${frame.status === "reported" ? "" : " Showing last verified edition."}`;
        if (rows[0].shortfall)
          status.textContent += ` The reported precinct counts sum to ${rows[0].shortfall} fewer ballots than the county control.`;
        body.replaceChildren();
        for (const value of [...rows].sort((a, b) => a.precinct.localeCompare(b.precinct))) {
          const row = body.insertRow(), id = document.createElement("th");
          id.scope = "row"; id.textContent = value.precinct; row.append(id);
          row.insertCell().textContent = number.format(value.count);
          row.insertCell().textContent = value.registered === null ? "Not qualified" : number.format(value.registered);
          row.insertCell().textContent = value.rate !== null ? `${value.rate.toFixed(2)}%`
            : value.hold === "ballots_exceed_registered" ? "Withheld: ballots exceed registration"
            : value.hold === "registration_column_party_labeled" ? "Withheld: registration column carries a party label"
            : value.hold === "active_registration_only" ? "Withheld: only active registration was reported"
            : value.hold === "county_ballot_control_disagrees" ? "Withheld: precinct sum differs from the county control"
            : "Withheld: no positive registration count";
        }
      }
      function selectCounties() {
        const previous = county.value, choices = [...frames.get(election.value).counties.keys()].sort();
        county.replaceChildren(...choices.map(name => new Option(name)));
        if (choices.includes(previous)) county.value = previous;
        render();
      }
      election.addEventListener("change", selectCounties);
      county.addEventListener("change", render);
      wrapper.append(table);
      selectCounties();
      load.remove();
      panel.append(electionLabel, " · ", countyLabel, " · ", original);
      installDenverPrecinctMap(panel, election, county, frames);
      panel.append(wrapper);
    } catch {
      load.disabled = false;
      load.textContent = "Retry precinct statistics";
      status.textContent = "The stored Colorado precinct statistics could not be verified.";
    }
  });
  return panel;
}

export function installNebraskaCountyReports(file) {
  const panel = document.createElement("details"), title = document.createElement("summary");
  title.textContent = "Nebraska’s 2026 county ballot reports";
  const note = document.createElement("p"), load = document.createElement("button"), status = document.createElement("p");
  note.textContent = "County reports may reflect different editions. These are counts, not turnout rates or a statewide total.";
  load.type = "button";
  load.textContent = "Load county reports";
  status.setAttribute("role", "status");
  const download = document.createElement("a");
  download.href = file.url;
  download.textContent = "Complete county reports (CSV · gzip)";
  panel.append(title, note, download, " · ", load, status);
  load.addEventListener("click", async () => {
    const retry = load.textContent === "Retry county reports";
    load.disabled = true;
    status.textContent = "Checking the stored reports…";
    try {
      const bytes = await checkedCountyBody(file.url, file, retry);
      const csv = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
      const frame = nebraskaCountyReportsFrame(csv), wrapper = document.createElement("div");
      const table = document.createElement("table"), caption = table.createCaption();
      caption.textContent = "November 3, 2026 · Nebraska county ballot counts";
      wrapper.className = "table-wrap";
      wrapper.tabIndex = 0;
      wrapper.setAttribute("role", "region");
      wrapper.setAttribute("aria-label", "Nebraska county ballot reports");
      const head = table.createTHead().insertRow(), body = table.createTBody();
      for (const label of ["County", "Ballots cast", "Source status", "Report clock", "Original report"]) {
        const cell = document.createElement("th");
        cell.scope = "col"; cell.textContent = label; head.append(cell);
      }
      const number = new Intl.NumberFormat("en-US");
      let qualified = 0;
      for (const value of frame.rows.values()) {
        const row = body.insertRow(), name = document.createElement("th");
        name.scope = "row"; name.textContent = value.name; row.append(name);
        const reported = value.count !== null;
        if (reported) qualified++;
        row.insertCell().textContent = reported ? number.format(value.count) : "Not verified";
        row.insertCell().textContent = reported
          ? `${value.reportStatus === "official" ? "Official" : "Unofficial"}${value.sourceStatus === "reported" ? "" : " · last verified"}`
          : value.disposition === "compatible_report_not_linked" ? "No compatible PDF linked" : "Report not qualified";
        row.insertCell().textContent = value.clock || "—";
        const source = row.insertCell();
        if (reported) {
          const link = document.createElement("a");
          link.href = value.url; link.textContent = `${value.name} PDF`; source.append(link);
        } else source.textContent = "—";
      }
      wrapper.append(table);
      panel.append(wrapper);
      const state = document.createElement("input"), year = document.createElement("input");
      state.value = frame.code; year.value = frame.date;
      installHistoricalCountyMap(panel, state, year, null, { NE: "Nebraska" }, () => frame);
      load.remove();
      status.textContent = `${qualified} of 93 county counts verified.`;
    } catch {
      load.disabled = false;
      load.textContent = "Retry county reports";
      status.textContent = "The stored Nebraska county reports could not be verified.";
    }
  });
  return panel;
}

function archiveStateHistory(panel, frames, name) {
  const table = document.createElement("table"), chart = document.createElement("figure");
  const note = document.createElement("figcaption"), scroller = document.createElement("div");
  const heading = document.createElement("summary");
  heading.textContent = "Statewide participation across elections";
  scroller.className = "table-wrap";
  scroller.tabIndex = 0;
  scroller.setAttribute("role", "region");
  scroller.setAttribute("aria-label", "Statewide turnout history");
  scroller.append(table);
  chart.style.marginInline = "0";
  chart.append(note);
  const caption = table.createCaption(), header = table.createTHead().insertRow(), body = table.createTBody();
  for (const label of ["Election", "Reported count", "Registrations", "Registration basis", "Same-report registration fraction"]) {
    const th = document.createElement("th");
    th.scope = "col"; th.textContent = label; header.append(th);
  }
  panel.append(heading, chart, scroller);
  const number = new Intl.NumberFormat("en-US");
  const svgNode = (tag, attrs, text) => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  };
  return code => {
    const reports = frames.filter(frame => frame.code === code).reverse();
    panel.hidden = reports.length < 2;
    body.replaceChildren();
    chart.querySelector("svg")?.remove();
    if (panel.hidden) return;
    const label = name(code);
    caption.textContent = `${label} statewide reports`;
    const hasRates = reports.some(frame => frame.rows.get("state").rate !== null);
    note.textContent = hasRates
      ? "Each dot uses that election report’s own registration count. Reports can use different "
        + "count definitions and registration dates. Withheld rates have no dot."
      : "No comparable registration fractions are available. See the table for reported counts.";
    const svg = svgNode("svg", { viewBox: "0 0 480 156", width: "480", role: "img",
      "aria-label": `${label} statewide registration fractions by election; exact values in the table` });
    svg.style.maxWidth = "100%";
    svg.style.height = "auto";
    const dates = reports.map(frame => Number(frame.date.slice(0, 4)));
    const position = year => dates[0] === dates.at(-1) ? 250
      : 54 + 392 * (year - dates[0]) / (dates.at(-1) - dates[0]);
    for (const rate of [0, 50, 100]) {
      const y = 124 - rate;
      svg.append(svgNode("line", { x1: 46, x2: 454, y1: y, y2: y, stroke: "currentColor", opacity: ".2" }),
        svgNode("text", { x: 41, y: y + 4, "text-anchor": "end", "font-size": 13, fill: "currentColor" }, `${rate}%`));
    }
    for (const year of new Set([dates[0], dates.at(-1)])) {
      svg.append(svgNode("text", { x: position(year), y: 145, "text-anchor": "middle",
        "font-size": 13, fill: "currentColor" }, year));
    }
    for (const [i, frame] of reports.entries()) {
      const row = frame.rows.get("state"), tr = body.insertRow(), key = document.createElement("th");
      const link = document.createElement("a");
      link.href = frame.url; link.textContent = frame.date;
      key.scope = "row"; key.append(link); tr.append(key);
      const measure = archiveMeasureLabel(frame.measure);
      tr.insertCell().textContent = `${number.format(row.count)} (${measure})`;
      tr.insertCell().textContent = row.registered === null ? "Not reported" : number.format(row.registered);
      tr.insertCell().textContent = frame.basis || "Not in report";
      const fraction = row.rate === null ? `Withheld · ${row.hold.replaceAll("_", " ")}` : `${row.rate.toFixed(2)}%`;
      const retained = frame.status === "retained_after_failure";
      tr.insertCell().textContent = fraction + (retained ? " · Last verified report" : "");
      if (row.rate !== null) {
        const color = "#286477";
        const dot = svgNode("circle", { cx: position(dates[i]), cy: 124 - row.rate,
          r: 4, fill: retained ? "none" : color, stroke: color, "data-election": frame.date });
        dot.append(svgNode("title", {}, `${frame.date}: ${fraction}${retained ? " (last verified report)" : ""}`));
        svg.append(dot);
      }
    }
    if (hasRates) chart.prepend(svg);
  };
}

export function wyomingCurrentCountyFrame(reporting) {
  const candidates = reporting.filter(row => row.state_code === "WY" && row.year === 2026
    && row.statewide_ballot_parent);
  const row = candidates[0], parent = row?.statewide_ballot_parent;
  const url = "https://sos.wyo.gov/Elections/Docs/2026/Results/General/2026_Wyoming_General_Results.zip";
  const count = value => Number.isSafeInteger(value) && value >= 0;
  if (candidates.length !== 1 || row.cast_ballot_count_qualified !== true
      || row.participation_measure_literal !== "Total Ballots Cast" || row.denominator !== null
      || !["reported", "retained_after_failure"].includes(row.status)
      || parent.contract !== "participation.reviewed_statewide_ballot_parent.v1"
      || parent.workbook !== "2026 General Results Summaries - OFFICIAL.xlsx"
      || parent.sheet !== "Statewide Total Ballots Cast" || parent.cell !== "B28"
      || row.source_url !== url || parent.source?.url !== url
      || !/^[a-f0-9]{64}$/.test(row.source_sha256) || parent.source.sha256 !== row.source_sha256
      || !count(row.ballots) || parent.ballots !== row.ballots
      || !Array.isArray(parent.counties) || parent.counties.length !== 23)
    throw new Error("Unverified Wyoming county ballot workbook");
  const makeRow = (name, count) => ({ name, count, registered: null, rate: null, hold: "registration_not_in_report" });
  const rows = new Map([["state", makeRow("Wyoming", row.ballots)]]);
  let total = 0;
  for (const [index, item] of parent.counties.entries()) {
    if (item?.physical_row !== index + 5 || typeof item.county !== "string"
        || !/^[A-Za-z]+(?: [A-Za-z]+)*$/.test(item.county)
        || !count(item.ballots) || rows.has(`county/${item.county}`))
      throw new Error("Incomplete or ambiguous Wyoming county workbook");
    rows.set(`county/${item.county}`, makeRow(item.county, item.ballots));
    total += item.ballots;
  }
  if (total !== row.ballots) throw new Error("Wyoming county ballot counts do not match the statewide total");
  return { code: "WY", date: "2026-11-03", measure: "ballots_cast", basis: null, rows, url,
    status: row.status, note: "The workbook reports ballots, not unique voters, and does not establish certification." };
}

export function wyomingCanvassCountyFrame(data) {
  const makeRow = (name, count) => ({ name, count, registered: null, rate: null, hold: "registration_not_in_report" });
  const rows = new Map([["state", makeRow("Wyoming", data.state_ballots_cast)]]);
  for (const { county, ballots_cast } of data.county_controls)
    rows.set(`county/${county}`, makeRow(county, ballots_cast));
  return { code: "WY", date: data.election_date, measure: "ballots_cast", basis: null, rows,
    url: data.source.url, status: data.status,
    note: "The official canvass reports ballots, not unique voters. County totals reconcile to the precinct tables." };
}

function installStateCountyArchives(sources, url, names, { currentCalifornia = false, currentNebraska = false, wyomingCounts = null,
  wyomingCanvass = false } = {}) {
  const panel = document.createElement("details"), heading = document.createElement("summary");
  const download = document.createElement("a"), note = document.createElement("p");
  const button = document.createElement("button"), status = document.createElement("p");
  const wyoming = wyomingCanvass || wyomingCounts;
  heading.textContent = wyoming ? "Wyoming county ballots cast, 2026"
    : currentCalifornia ? "California’s 2026 statewide and county turnout report"
    : currentNebraska ? "Nebraska’s 2026 statewide and county canvass"
    : "Browse official state and county turnout archives";
  download.href = url;
  download.textContent = wyomingCanvass ? "Complete analysis with Wyoming canvass queries (ZIP)"
    : wyomingCounts ? "Complete analysis with Wyoming workbook queries (ZIP)"
    : currentCalifornia ? "Complete California 2026 report query (CSV · gzip)"
    : currentNebraska ? "Complete Nebraska 2026 canvass query (CSV · gzip)"
    : "State election office turnout archives (CSV · gzip)";
  note.append(download, wyomingCanvass ? ". County ballot counts from the same canvass as the precinct table; no turnout rates."
    : wyomingCounts ? ". County ballot counts from the accepted Wyoming workbook; no turnout rates."
    : currentCalifornia
    ? ". This report is separate from the live election-results feed and does not establish certification."
    : currentNebraska ? ". Official canvass totals and same-report registration, separate from candidate returns."
    : ". These official reports are separate from EAC data and the 2026 map.");
  status.setAttribute("role", "status");
  button.type = "button"; button.textContent = "Load election-office reports";
  panel.append(heading, note, button, status);
  let retry = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    status.textContent = "Checking the stored election-office reports…";
    try {
      let frames;
      if (wyomingCanvass) {
        const canvass = await loadWyomingPrecinctCanvass();
        if (!canvass) throw new Error("Missing Wyoming canvass in accepted runtime");
        frames = [wyomingCanvassCountyFrame(canvass.data)];
      } else if (wyomingCounts) {
        const path = "current.json.gz", file = wyomingCounts.files[path];
        const bytes = await checkedCountyBody(new URL(path, wyomingCounts.base_url).href, file, retry);
        const json = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).json();
        frames = [wyomingCurrentCountyFrame(validateCurrentCountSnapshot(json).snapshot.reporting)];
      } else {
        const file = coverageCsvFile(sources, currentCalifornia ? californiaCurrentReportPath
          : currentNebraska ? nebraskaCurrentReportPath : stateCountyArchivesPath);
        const bytes = await checkedCountyBody(file.url, file, retry);
        const csv = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
        frames = stateCountyArchiveFrames(csv, { currentCalifornia, currentNebraska });
      }
      const state = document.createElement("select"), year = document.createElement("select");
      for (const code of new Set(frames.map(frame => frame.code))) state.add(new Option(names[code] || code, code));
      const stateLabel = document.createElement("label"), yearLabel = document.createElement("label");
      stateLabel.append("Report state ", state); yearLabel.append(" Election date ", year);
      const report = document.createElement("p"), original = document.createElement("a");
      original.textContent = "Original report";
      const scroller = document.createElement("div"), table = document.createElement("table");
      scroller.className = "table-wrap"; scroller.tabIndex = 0;
      scroller.setAttribute("role", "region"); scroller.setAttribute("aria-label", "Official turnout archive");
      const caption = table.createCaption(), header = table.createTHead().insertRow();
      for (const label of ["Reporting area", "Reported count", "Reported registered voters", "Same-report registration fraction"]) {
        const th = document.createElement("th");
        th.scope = "col"; th.textContent = label; header.append(th);
      }
      const body = table.createTBody(), number = new Intl.NumberFormat("en-US");
      const currentFrame = () => frames.find(item => item.code === state.value && item.date === year.value);
      const history = document.createElement("details");
      const historical = !currentCalifornia && !currentNebraska && !wyoming;
      const renderHistory = historical ? archiveStateHistory(history, frames, code => names[code] || code) : () => {};
      const render = () => {
        const frame = currentFrame();
        const measure = archiveMeasureLabel(frame.measure);
        caption.textContent = `${names[frame.code] || frame.code} · ${frame.date} · ${measure}`;
        original.href = frame.url;
        report.replaceChildren(original, (frame.basis ? `. Registration basis: ${frame.basis}. `
          + "Not a rate among all eligible residents." : ". The report supplies no registration denominator.")
          + (frame.edition ? ` Report edition: ${frame.edition}.` : "")
          + (frame.note ? ` ${frame.note}` : ""));
        status.textContent = `${frame.rows.size - 1} ${frame.code === "VA" ? "localities" : "counties"} and one state total.`
          + (frame.status === "retained_after_failure" ? " Latest check failed; showing the last verified report." : "");
        body.replaceChildren();
        for (const row of [frame.rows.get("state"), ...[...frame.rows].filter(([key]) => key !== "state").map(([, row]) => row)]) {
          const tr = body.insertRow(), key = document.createElement("th");
          key.scope = "row"; key.textContent = row.name; tr.append(key);
          tr.insertCell().textContent = number.format(row.count);
          tr.insertCell().textContent = row.registered === null ? "Not reported" : number.format(row.registered);
          const rate = tr.insertCell();
          rate.textContent = row.rate === null ? "Withheld" : `${row.rate.toFixed(2)}%`;
          if (row.hold) rate.append(` · ${row.hold.replaceAll("_", " ")}`);
        }
      };
      function selectYears() {
        year.replaceChildren(...frames.filter(frame => frame.code === state.value)
          .map(frame => new Option(frame.date, frame.date)));
        render();
        renderHistory(state.value);
      }
      scroller.append(table);
      button.replaceWith(stateLabel, yearLabel);
      panel.append(report);
      state.addEventListener("change", selectYears);
      year.addEventListener("change", render);
      selectYears();
      installHistoricalCountyMap(panel, state, year, null, names, currentFrame);
      panel.append(scroller);
      if (historical) panel.append(history);
      state.focus();
    } catch {
      retry = true;
      status.textContent = "The election-office reports could not be verified. The complete download remains available.";
      button.disabled = false;
      button.textContent = "Retry election-office reports";
    }
  });
  return panel;
}

async function loadCoverageCsv(sources, path) {
  const file = coverageCsvFile(sources, path);
  if (!file) return null;
  const response = await fetch(file.url);
  if (!response.ok) throw new Error("Administrative coverage could not be loaded");
  const body = await response.arrayBuffer();
  const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))]
    .map(byte => byte.toString(16).padStart(2, "0")).join("");
  if (body.byteLength !== file.bytes || digest !== file.sha256)
    throw new Error("Administrative coverage checksum differs");
  const csv = await new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  return { csv, file };
}

export function northCarolinaAgeRows(csv) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const fields = header.split(",");
  const columns = ["state_code", "election_date", "geography_level", "native_age_label",
    "voters_with_history", "active_and_inactive_registered_voters", "source_defined_rate_pct",
    "history_edition", "registration_edition", "status"];
  const indexes = columns.map(field => fields.indexOf(field));
  if (indexes.some((index, i) => index < 0 || index !== fields.lastIndexOf(columns[i]))
      || lines.length !== ncAges.length) throw new Error("Incomplete North Carolina age results");
  const rows = lines.map((line, i) => {
    const cells = line.split(",");
    const [state, date, geography, age, history, register, rate, historyEdition, registrationEdition, status] =
      indexes.map(index => cells[index]);
    const [voted, registered] = [Number(history), Number(register)];
    const fraction = voted <= registered ? 100 * voted / registered : null;
    if (cells.length !== fields.length || state !== "NC" || date !== "2026-11-03" || geography !== "state"
        || age !== ncAges[i] || ![history, register].every(value => /^[1-9][0-9]*$/.test(value))
        || ![voted, registered].every(Number.isSafeInteger)
        || (fraction === null ? rate !== "" : !rate || Math.abs(Number(rate) - fraction) > 1e-8
          || !Number.isFinite(Number(rate)))
        || ![historyEdition, registrationEdition].every(value =>
          /^\d{4}-\d{2}-\d{2}$/.test(value) && value >= date)
        || !["reported", "retained_after_failure"].includes(status))
      throw new Error("Invalid North Carolina age results");
    return { age, voted, registered, fraction, historyEdition, registrationEdition, status };
  });
  const [first] = rows;
  if (rows.some(row => row.historyEdition !== first.historyEdition
      || row.registrationEdition !== first.registrationEdition || row.status !== first.status))
    throw new Error("Mixed North Carolina age statistics editions");
  return rows;
}

function installNorthCarolinaAge(host, sources) {
  if (!sources?.supported_release?.downloads?.[ncAgePath]) return;
  const panel = document.createElement("details");
  const heading = document.createElement("summary");
  heading.textContent = "North Carolina statewide vote history by age";
  const content = document.createElement("div");
  panel.append(heading, content);
  host.append(panel);
  let pending = false;
  panel.addEventListener("toggle", async () => {
    if (!panel.open || pending) return;
    pending = true;
    content.textContent = "Checking the paired age statistics…";
    try {
      const { csv, file } = await loadCoverageCsv(sources, ncAgePath);
      const rows = northCarolinaAgeRows(csv);
      const [first] = rows;
      const note = document.createElement("p");
      note.textContent = `${first.status === "retained_after_failure" ? "Last verified edition retained. " : ""}`
        + `Voter history: ${first.historyEdition}. Registration: ${first.registrationEdition}. `
        + "Fractions use active and inactive registrations, not ballots cast or eligible population. "
        + "The archives do not establish completeness or certification.";
      const download = document.createElement("a");
      download.href = file.url;
      download.textContent = "North Carolina statewide age statistics (CSV · gzip)";
      const table = document.createElement("table");
      table.createCaption().textContent = "November 3, 2026 general election";
      const header = table.createTHead().insertRow();
      for (const label of ["Source age group", "Voters with history", "Registered voters", "Reported fraction"]) {
        const cell = document.createElement("th");
        cell.scope = "col"; cell.textContent = label; header.append(cell);
      }
      const tbody = table.createTBody();
      for (const row of rows) {
        const tr = tbody.insertRow();
        const label = document.createElement("th");
        label.scope = "row"; label.textContent = row.age; tr.append(label);
        for (const value of [row.voted.toLocaleString("en-US"), row.registered.toLocaleString("en-US"),
          row.fraction === null ? "Withheld" : `${row.fraction.toFixed(1)}%`]) tr.insertCell().textContent = value;
      }
      const region = document.createElement("div");
      region.className = "table-wrap"; region.tabIndex = 0;
      region.setAttribute("role", "region"); region.setAttribute("aria-label", heading.textContent);
      region.append(table);
      content.replaceChildren(note, download, region);
    } catch {
      content.textContent = "The age statistics could not be verified. Close and reopen to retry.";
      pending = false;
    }
  });
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
      const manifest = await loadAutomaticRuntime();
      const coverage = await loadCoverageCsv(manifest.house_sources, coveragePath);
      if (!coverage) {
        content.textContent = "This release has no administrative coverage export.";
        return;
      }
      const { csv, file } = coverage;
      const rows = administrativeRows(csv);
      const note = document.createElement("p");
      note.textContent = `2026 · Accepted source check ${new Date(manifest.checked_at).toISOString()}. `
        + `${rows.filter(row => row.counts[0]).length} of 51 jurisdictions have a statewide count. `
        + "Zeros mean no qualifying records, not zero votes. Counts are records, not people or proof of complete coverage. "
        + "Municipal and reporting-unit rows are separate from strict precinct rows and should not be added together. "
        + "Not supplied means the release did not include that coverage measure.";
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
      for (const label of ["Jurisdiction", ...scopes.flatMap(([, level]) => [`${level} counts`, `${level} rates`])]) {
        const cell = document.createElement("th");
        cell.scope = "col"; cell.textContent = label; header.append(cell);
      }
      const tbody = table.createTBody();
      for (const { code, counts } of rows) {
        const row = tbody.insertRow(); row.dataset.stateCode = code;
        const key = document.createElement("th");
        key.scope = "row"; key.textContent = names[code] || code; row.append(key);
        for (const value of counts) row.insertCell().textContent = value === null ? "Not supplied" : String(value);
      }
      scroller.append(table);
      content.replaceChildren(note, download, " · ", complete, scroller);
      const historical = historicalCountyDownload(manifest.house_sources);
      if (historical) content.append(...installHistoricalCounties(manifest.house_sources, historical, names));
      const indiana = indianaTurnoutDownload(manifest.house_sources);
      if (indiana) {
        const history = document.createElement("p");
        const link = document.createElement("a");
        link.href = indiana; link.textContent = "Indiana statewide and county turnout history (CSV · gzip)";
        history.append(link, ": official report counts, registration fractions and reconciliation holds. "
          + "This is separate from the current administrative map.");
        content.append(history);
      }
      const stateCountyArchives = stateCountyArchivesDownload(manifest.house_sources);
      if (stateCountyArchives) content.append(installStateCountyArchives(manifest.house_sources, stateCountyArchives, names));
      try {
        const statistics = coverageCsvFile(manifest.house_sources, coloradoPrecinctStatisticsPath);
        if (statistics) content.append(installColoradoPrecinctStatistics(statistics));
      } catch {
        const notice = document.createElement("p");
        notice.textContent = "The Colorado precinct download descriptor could not be verified.";
        content.append(notice);
      }
      try {
        const statistics = coverageCsvFile(manifest.house_sources, minnesotaPrecinctStatisticsPath);
        if (statistics) content.append(installMinnesotaPrecinctMap(statistics, historicalCsvLine));
      } catch {
        const notice = document.createElement("p");
        notice.textContent = "The Minnesota precinct download descriptor could not be verified.";
        content.append(notice);
      }
      installMarylandCoverage(content, manifest.house_sources);
      if (manifest.house_sources?.wyoming_precinct_canvass) content.append(installStateCountyArchives(
        manifest.house_sources, manifest.complete_download.url, names, { wyomingCanvass: true }));
      else if (manifest.counts?.files["current.json.gz"]) content.append(installStateCountyArchives(
        manifest.house_sources, manifest.complete_download.url, names, { wyomingCounts: manifest.counts }));
      content.append(installNorthCarolina2006CountyRates());
      try {
        const report = coverageCsvFile(manifest.house_sources, californiaCurrentReportPath);
        if (report) content.append(installStateCountyArchives(manifest.house_sources, report.url, names, { currentCalifornia: true }));
      } catch {
        const notice = document.createElement("p");
        notice.textContent = "The California 2026 county report descriptor could not be verified.";
        content.append(notice);
      }
      try {
        const report = coverageCsvFile(manifest.house_sources, nebraskaCurrentReportPath);
        if (report) content.append(installStateCountyArchives(
          manifest.house_sources, report.url, names, { currentNebraska: true }));
        else {
          const countyReports = coverageCsvFile(manifest.house_sources, nebraskaCountyReportsPath);
          if (countyReports) content.append(installNebraskaCountyReports(countyReports));
        }
      } catch {
        const notice = document.createElement("p");
        notice.textContent = "The Nebraska 2026 canvass descriptor could not be verified.";
        content.append(notice);
      }
      try {
        const census = coverageCsvFile(manifest.house_sources, publishedCpsPath);
        if (census) content.append(installPublishedCps(manifest.house_sources, census, names));
        const archived = coverageCsvFile(manifest.house_sources, archivedCpsPath);
        if (archived) content.append(installPublishedCps(manifest.house_sources, archived, names, { archived: true }));
        const overall = coverageCsvFile(manifest.house_sources, overallCpsPath);
        const summary = manifest.house_sources.supported_release?.coverage?.historical_survey?.published_state_overall_history;
        if (overall && summary) content.append(installOverallCps(overall, summary, names));
      } catch {
        const notice = document.createElement("p");
        notice.textContent = "The published Census state tables descriptor could not be verified.";
        content.append(notice);
      }
      installNorthCarolinaAge(content, manifest.house_sources);
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

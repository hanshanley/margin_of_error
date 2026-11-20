import { loadDatasetCatalog } from "./participation-dataset.js";
import { countStates, loadCountIndex } from "./participation-counts.js";
import { loadNativeIndex } from "./participation-native-bindings.js";
import { loadAutomaticRuntime } from "./participation-automatic-runtime.js";
import { checkedCountyBody, installHistoricalCountyMap } from "./participation-historical-county-map.js";

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
const californiaCurrentReportPath = "release/participation-ca-2026-county-turnout-report.csv.gz";
const publishedCpsPath = "release/participation-cps-published-state-tables.csv.gz";
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

function coverageCsvFile(sources, path) {
  const file = sources?.supported_release?.downloads?.[path];
  if (!file) return null;
  if (typeof sources.base_url !== "string" || !sources.base_url.startsWith("https://")
      || file.path !== path || file.url !== `${sources.base_url}/${path}`
      || file.media_type !== "text/csv" || file.compression !== "gzip"
      || !Number.isSafeInteger(file.bytes) || file.bytes < 1
      || file.bytes > ([stateCountyArchivesPath, publishedCpsPath].includes(path) ? 524288 : 65536)
      || !/^[a-f0-9]{64}$/.test(file.sha256))
    throw new Error("Administrative coverage is not bound to the accepted runtime");
  return file;
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

export function publishedCpsRows(csv, summary) {
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
    const key = `${year}/${code}/${row.group}/${row.source_table}`;
    if (!summary.years.includes(year) || !expectedStates.has(code) || seen.has(key)
        || row.election_type !== (year % 4 === 0 ? "presidential" : "midterm")
        || !["overall", "age", "sex", "race_or_hispanic_origin"].includes(row.dimension)
        || (row.dimension !== "overall" && row.source_table !== (row.dimension === "age" ? "4c" : "4b"))
        || !["4b", "4c"].includes(row.source_table) || row.confidence_level_pct !== "90"
        || !/^https:\/\/www2\.census\.gov\/programs-surveys\/cps\/tables\/p20\/\d+\/[a-z0-9_]+\.xlsx$/.test(row.source_url))
      throw new Error("Census cohort or source identity differs");
    for (const prefix of rates) {
      const point = row[`${prefix}_pct`], moe = row[`${prefix}_moe_pp`];
      if ((point === "") !== (moe === "") || [point, moe].some(v =>
        v !== "" && (!/^\d+(?:\.\d+)?$/.test(v) || Number(v) > 100)))
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
  // Both source tables publish the same totals. Keep both in the CSV, show one.
  return rows.filter(r => r.dimension !== "overall" || r.source_table === "4b");
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

function installPublishedCps(sources, file, names) {
  const panel = document.createElement("details"), heading = document.createElement("summary");
  const note = document.createElement("p"), download = document.createElement("a");
  const button = document.createElement("button"), status = document.createElement("p");
  heading.textContent = "Compare Census survey turnout by state and group";
  download.href = file.url;
  download.textContent = "Complete Census state turnout tables (CSV · gzip)";
  note.append("Census survey estimates of reported voting and registration, not official ballot counts. "
    + "The margins of error are for individual estimates at the 90% confidence level, not for changes across years. "
    + "Race and Hispanic-origin categories can overlap. ", download);
  button.type = "button"; button.textContent = "Load Census turnout comparisons";
  status.setAttribute("role", "status");
  panel.append(heading, note, button, status);
  const survey = sources.supported_release.coverage.historical_survey;
  const checkMessage = publishedCpsStatus(survey.current_published_state_tables);
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
      const rows = publishedCpsRows(text, survey.published_state_tables);
      const state = document.createElement("select"), group = document.createElement("select");
      const basis = document.createElement("select");
      state.append(new Option("United States", "US"), ...countStates.map(code => new Option(names[code] || code, code)));
      for (const label of new Set(rows.filter(r => r.state_code === "US").map(r => r.group)))
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
        for (const r of rows.filter(r => r.state_code === state.value && r.group === group.value)) {
          const tr = tbody.insertRow(), label = document.createElement("th"), source = document.createElement("a");
          label.scope = "row"; label.textContent = `${r.year} ${r.election_type}`; tr.append(label);
          for (const measure of ["voted", "registered"]) {
            const key = `${basis.value}_${measure}`;
            tr.insertCell().textContent = r[`${key}_pct`] === "" ? "Not published"
              : `${r[`${key}_pct`]}% ± ${r[`${key}_moe_pp`]} pp`;
          }
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

export function stateCountyArchiveFrames(csv, { currentCalifornia = false } = {}) {
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
    const value = measure === "ballots_cast" && voters === "" ? ballots
      : measure === "total_voters" && ballots === "" ? voters : "";
    const stock = field("reported_registered_voters"), fraction = field("qualified_same_report_registration_fraction_pct");
    const rate = fraction === "" ? null : Number(fraction), hold = field("rate_hold_reason");
    const status = field("source_status"), url = field("source_url"), sha = field("source_sha256");
    const basis = hasMeasures ? field("registration_basis") : "Report's registered voters";
    const edition = field("report_edition"), note = field("report_note") || "";
    if (!countStates.includes(code) || !/^\d{4}$/.test(year) || !/^\d{4}-11-\d{2}$/.test(date)
        || !date.startsWith(`${year}-`) || !["state", "county"].includes(level)
        || (currentCalifornia ? code !== "CA" || date !== "2026-11-03" || measure !== "total_voters" : Number(year) >= 2026)
        || !name || !basis || ![value, stock].every(integer)
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
    frame.rows.set(rowKey, { name, count: Number(value), registered: Number(stock), rate, hold });
  }
  if ([...frames.values()].some(frame => !frame.rows.has("state") || frame.rows.size < 2))
    throw new Error("Election-office archive lacks a state or county total");
  if (currentCalifornia && [...frames.values()].some(frame => frame.rows.size !== 59))
    throw new Error("Incomplete California statewide and county report");
  return [...frames.values()].sort((a, b) => a.code.localeCompare(b.code) || b.date.localeCompare(a.date));
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
  note.textContent = "Each dot uses that election report’s own registration count. Reports can use different "
    + "count definitions and registration dates. Withheld rates have no dot.";
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
      const measure = frame.measure === "total_voters" ? "Total Voters" : "Ballots Cast";
      tr.insertCell().textContent = `${number.format(row.count)} (${measure})`;
      tr.insertCell().textContent = number.format(row.registered);
      tr.insertCell().textContent = frame.basis;
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
    chart.prepend(svg);
  };
}

function installStateCountyArchives(sources, url, names, currentCalifornia = false) {
  const panel = document.createElement("details"), heading = document.createElement("summary");
  const download = document.createElement("a"), note = document.createElement("p");
  const button = document.createElement("button"), status = document.createElement("p");
  heading.textContent = currentCalifornia ? "California’s 2026 statewide and county turnout report"
    : "Browse official state and county turnout archives";
  download.href = url;
  download.textContent = currentCalifornia ? "Complete California 2026 report query (CSV · gzip)"
    : "State election office turnout archives (CSV · gzip)";
  note.append(download, currentCalifornia
    ? ". This report is separate from the live election-results feed and does not establish certification."
    : ". These official reports are separate from EAC data and the 2026 map.");
  status.setAttribute("role", "status");
  button.type = "button"; button.textContent = "Load election-office reports";
  panel.append(heading, note, button, status);
  let retry = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    status.textContent = "Checking the stored election-office reports…";
    try {
      const file = coverageCsvFile(sources, currentCalifornia ? californiaCurrentReportPath : stateCountyArchivesPath);
      const bytes = await checkedCountyBody(file.url, file, retry);
      const csv = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
      const frames = stateCountyArchiveFrames(csv, { currentCalifornia });
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
      const renderHistory = currentCalifornia ? () => {} : archiveStateHistory(history, frames, code => names[code] || code);
      const render = () => {
        const frame = currentFrame();
        const measure = frame.measure === "total_voters" ? "Total Voters" : "Ballots Cast";
        caption.textContent = `${names[frame.code] || frame.code} · ${frame.date} · ${measure}`;
        original.href = frame.url;
        report.replaceChildren(original, `. Registration basis: ${frame.basis}. `
          + "Not a rate among all eligible residents."
          + (frame.edition ? ` Report edition: ${frame.edition}.` : "")
          + (frame.note ? ` ${frame.note}` : ""));
        status.textContent = `${frame.rows.size - 1} county reports and one state total.`
          + (frame.status === "retained_after_failure" ? " Latest check failed; showing the last verified report." : "");
        body.replaceChildren();
        for (const row of [frame.rows.get("state"), ...[...frame.rows].filter(([key]) => key !== "state").map(([, row]) => row)]) {
          const tr = body.insertRow(), key = document.createElement("th");
          key.scope = "row"; key.textContent = row.name; tr.append(key);
          tr.insertCell().textContent = number.format(row.count);
          tr.insertCell().textContent = number.format(row.registered);
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
      if (!currentCalifornia) panel.append(history);
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
        const report = coverageCsvFile(manifest.house_sources, californiaCurrentReportPath);
        if (report) content.append(installStateCountyArchives(manifest.house_sources, report.url, names, true));
      } catch {
        const notice = document.createElement("p");
        notice.textContent = "The California 2026 county report descriptor could not be verified.";
        content.append(notice);
      }
      try {
        const census = coverageCsvFile(manifest.house_sources, publishedCpsPath);
        if (census) content.append(installPublishedCps(manifest.house_sources, census, names));
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

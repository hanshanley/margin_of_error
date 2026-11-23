import { loadAutomaticRuntime } from "./participation-automatic-runtime.js";

const path = "release/participation-nm-historical-native-turnout.csv.gz";
const editions = {"2016-11-08": 1492, "2018-11-06": 1492, "2020-11-03": 1925,
  "2022-11-08": 2163, "2024-11-05": 2169};

function csvFields(line) {
  const cells = [], field = /(?:"((?:[^"]|"")*)"|([^",]*))(,|$)/y;
  for (;;) {
    const match = field.exec(line);
    if (!match) throw new Error("Invalid New Mexico CSV field");
    cells.push(match[1] === undefined ? match[2] : match[1].replaceAll('""', '"'));
    if (!match[3]) return cells;
  }
}

export function newMexicoHistoryRows(csv) {
  const [header, ...lines] = csv.trimEnd().split(/\r?\n/);
  const columns = csvFields(header);
  const fields = ["state_code", "election_date", "geography_level", "county_id", "county", "unit",
    "source_reported_count", "source_eligible_voters", "source_eligible_rate_pct", "rate_hold",
    "source_status", "source_clock", "native_numerator_label", "native_denominator_label"];
  const positions = fields.map(field => columns.indexOf(field));
  if (positions.includes(-1) || new Set(columns).size !== columns.length)
    throw new Error("Missing New Mexico history fields");
  const seen = new Set(), totals = new Map(), counties = new Map(), units = new Map();
  for (const line of lines) {
    const cells = csvFields(line);
    const [state, date, level, id, county, unit, ballots, eligible, fraction, hold, status, clock, numerator, denominator] =
      positions.map(i => cells[i]);
    const key = JSON.stringify([date, level, id, unit]), count = Number(ballots), voters = Number(eligible);
    const rate = fraction === "" ? null : Number(fraction);
    if (cells.length !== columns.length || state !== "NM" || !Object.hasOwn(editions, date) || seen.has(key)
        || !["state", "county", "reporting_unit"].includes(level)
        || (level === "state" ? id || county || unit : !/^\d+$/.test(id) || !county || Boolean(unit) !== (level === "reporting_unit"))
        || !/^\d+$/.test(ballots) || !/^-?\d+$/.test(eligible)
        || !Number.isSafeInteger(count) || !Number.isSafeInteger(voters)
        || !["reported", "retained_after_failure"].includes(status) || !clock
        || numerator !== "Ballots Cast" || denominator !== "Eligible Voters"
        || (hold ? rate !== null : voters <= 0 || count > voters || !Number.isFinite(rate)
          || Math.abs(rate - 100 * count / voters) > 1e-9))
      throw new Error("New Mexico history row differs");
    seen.add(key);
    const row = {date, level, county, count, voters, rate, hold, status, clock};
    const group = JSON.stringify([date, id]);
    if (level === "state") totals.set(date, row);
    if (level === "county") counties.set(group, row);
    if (level !== "reporting_unit") continue;
    const sum = units.get(group) ?? {count: 0, voters: 0, rows: 0, invalid: false, county, status, clock};
    if (sum.county !== county || sum.status !== status || sum.clock !== clock
        || Boolean(hold) !== (voters <= 0 || count > voters)) throw new Error("New Mexico unit scope differs");
    sum.count += count; sum.voters += voters; sum.rows++; sum.invalid ||= voters < 0 || count > voters;
    units.set(group, sum);
  }
  if (!totals.size || units.size !== counties.size) throw new Error("Incomplete New Mexico history");
  for (const [date, total] of totals) {
    const names = new Set();
    let rows = 0, count = 0, voters = 0;
    for (const [key, row] of counties) {
      if (row.date !== date) continue;
      const sum = units.get(key);
      if (!sum || names.has(row.county) || ["count", "voters", "county", "status", "clock"].some(field => sum[field] !== row[field])
          || row.status !== total.status || row.clock !== total.clock
          || Boolean(row.hold) !== (sum.invalid || row.voters <= 0 || row.count > row.voters))
        throw new Error("New Mexico county totals or rate hold differ");
      names.add(row.county); rows += sum.rows; count += sum.count; voters += sum.voters;
    }
    if (names.size !== 33 || rows !== editions[date] || count !== total.count || voters !== total.voters || total.hold)
      throw new Error("New Mexico statewide totals differ");
  }
  if ([...counties.values()].some(row => !totals.has(row.date))) throw new Error("New Mexico county lacks statewide control");
  return [...totals.values(), ...counties.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export async function loadNewMexicoHistory(sources, fetchBody = fetch) {
  const file = sources?.supported_release?.downloads?.[path];
  if (!file) return null;
  if (file.path !== path || file.url !== `${sources.base_url}/${path}`
      || file.media_type !== "text/csv" || file.compression !== "gzip"
      || !Number.isSafeInteger(file.bytes) || file.bytes < 1 || file.bytes > 524288
      || !/^[a-f0-9]{64}$/.test(file.sha256))
    throw new Error("New Mexico history is not bound to the accepted runtime");
  const response = await fetchBody(file.url);
  if (!response.ok) throw new Error("New Mexico history could not be loaded");
  const body = await response.arrayBuffer();
  const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))]
    .map(byte => byte.toString(16).padStart(2, "0")).join("");
  if (body.byteLength !== file.bytes || digest !== file.sha256)
    throw new Error("New Mexico history checksum differs");
  const csv = await new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  return {rows: newMexicoHistoryRows(csv), file};
}

export function installNewMexicoHistory(panel) {
  const content = panel.querySelector("[data-nm-history]");
  let loading = false;
  panel.addEventListener("toggle", async () => {
    if (!panel.open || loading) return;
    loading = true;
    content.textContent = "Checking the rolling turnout archive…";
    try {
      const history = await loadNewMexicoHistory((await loadAutomaticRuntime()).house_sources);
      if (!history) {
        content.textContent = "Turnout history is not available right now.";
        loading = false;
        return;
      }
      const {rows} = history;
      const select = document.createElement("select"), label = document.createElement("label");
      label.textContent = "Area ";
      const names = [...new Set(rows.filter(row => row.county).map(row => row.county))].sort();
      select.append(new Option("Statewide", ""), ...names.map(name => new Option(name, name)));
      label.append(select);
      const scroller = document.createElement("div"), table = document.createElement("table");
      scroller.className = "table-wrap"; scroller.tabIndex = 0;
      scroller.setAttribute("role", "region");
      scroller.setAttribute("aria-label", "New Mexico turnout history table");
      const header = table.createTHead().insertRow();
      for (const title of ["Election", "Ballots Cast", "Eligible Voters", "Same-report rate", "Report clock"]) {
        const th = document.createElement("th");
        th.scope = "col"; th.textContent = title; header.append(th);
      }
      const body = table.createTBody();
      const draw = () => {
        body.replaceChildren();
        for (const r of rows.filter(row => row.county === select.value)) {
          const tr = body.insertRow(), th = document.createElement("th");
          th.scope = "row"; th.textContent = r.date; tr.append(th);
          tr.insertCell().textContent = r.count.toLocaleString("en-US");
          tr.insertCell().textContent = r.voters.toLocaleString("en-US");
          tr.insertCell().textContent = r.rate === null ? "Withheld: invalid denominator" : `${r.rate.toFixed(2)}%`;
          tr.insertCell().textContent = r.clock + (r.status === "retained_after_failure" ? " · Last verified report" : "");
        }
      };
      select.addEventListener("change", draw);
      scroller.append(table); content.replaceChildren(label, scroller); draw();
    } catch {
      loading = false;
      content.textContent = "Turnout history could not be verified. Close and reopen this section to retry.";
    }
  });
}

if (typeof document !== "undefined") {
  const panel = document.querySelector("[data-nm-history-panel]");
  if (panel) installNewMexicoHistory(panel);
}

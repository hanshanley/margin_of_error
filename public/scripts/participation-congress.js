import { loadAutomaticCongress } from "./participation-automatic-runtime.js";

const count = value => value === null || (Number.isSafeInteger(value) && value >= 0);
const close = (a, b) => a === null ? b === null : typeof b === "number"
  && Number.isFinite(b) && Math.abs(a - b) < 1e-9;
const number = value => value === null ? "Not supplied" : value.toLocaleString("en-US");
const points = value => value === null ? "Unavailable" : `${value > 0 ? "+" : ""}${value.toFixed(2)} pp`;
const percent = value => value === null ? "Unavailable" : `${value.toFixed(2)}%`;
const require = (condition, message) => { if (!condition) throw new Error(message); };

export function validateCongressionalResults(data) {
  require(data?.contract === "participation.congressional_results.v1"
    && data.election_date === "2026-11-03" && data.source_models_refitted === false
    && data.observed_individual_behavior === false && Array.isArray(data.races)
    && Array.isArray(data.candidates) && Array.isArray(data.coverage), "Congressional result contract differs");
  const races = new Map(), candidates = new Map();
  for (const row of data.races) {
    require(typeof row.id === "string" && !races.has(row.id)
      && ["house", "senate"].includes(row.chamber) && /^[A-Z]{2}$/.test(row.state_code)
      && /^[1-9][0-9]*$/.test(row.seat) && typeof row.stage === "string"
      && typeof row.round === "string" && typeof row.seat_label === "string"
      && typeof row.ranked_choice === "boolean" && typeof row.advertised === "boolean"
      && ["source_verified", "retained_last_good"].includes(row.freshness)
      && ["reported", "retained_after_failure"].includes(row.status)
      && (row.status === "reported") === (row.freshness === "source_verified")
      && typeof row.source_updated_at === "string" && Number.isFinite(Date.parse(row.source_updated_at))
      && Number.isSafeInteger(row.source_updated_epoch_ms)
      && Date.parse(row.source_updated_at) === row.source_updated_epoch_ms
      && ["D", "R", "O", "U"].every(key => count(row[key]))
      && row.candidate_votes_are_not_ballots_or_turnout === true
      && row.behavioral_estimate_updated === false && Array.isArray(row.comparison_holds)
      && typeof row.qualified_comparison === "boolean", "Congressional race identity, clock or counts differ");
    require(row.election_date === data.election_date
      && row.id === `npr:${row.chamber}:${row.state_code}:${row.seat}:${row.election_kind}:${row.stage}:${row.round}`,
    "Congressional seat, stage or round identity differs");
    races.set(row.id, row);
    candidates.set(row.id, []);
  }
  const keys = new Set();
  for (const row of data.candidates) {
    const parent = races.get(row.id), key = `${row.id}|${row.candidate_id}`;
    require(parent && !keys.has(key) && typeof row.candidate_id === "string"
      && typeof row.name === "string" && row.name.length > 0
      && (row.literal_party === null || typeof row.literal_party === "string")
      && ["D", "R", "O", "U"].includes(row.party_group) && count(row.votes)
      && row.state_code === parent.state_code && row.stage === parent.stage && row.round === parent.round
      && row.source_updated_at === parent.source_updated_at && row.freshness === parent.freshness,
    "Congressional candidate inventory differs");
    const expected = row.literal_party === "Dem" ? "D" : row.literal_party === "GOP" ? "R"
      : row.literal_party ? "O" : "U";
    require(row.party_group === expected, "Congressional literal party classification differs");
    keys.add(key);
    candidates.get(row.id).push(row);
  }
  for (const row of races.values()) {
    const selected = candidates.get(row.id), totals = { D: 0, R: 0, O: 0, U: 0 };
    require(selected.length > 0 && Array.isArray(row.candidate_ids)
      && new Set(row.candidate_ids).size === row.candidate_ids.length
      && [...row.candidate_ids].sort().join("|") === selected.map(c => c.candidate_id).sort().join("|"),
    "Congressional candidate inventory is empty or incomplete");
    for (const candidate of selected) {
      if (candidate.votes === null) totals[candidate.party_group] = null;
      else if (totals[candidate.party_group] !== null) totals[candidate.party_group] += candidate.votes;
    }
    require(Object.keys(totals).every(key => row[key] === totals[key])
      && row.count_coverage_complete === selected.every(candidate => candidate.votes !== null),
    "Congressional candidate totals do not reconcile");
    const denominator = row.D !== null && row.R !== null ? row.D + row.R : null;
    const margin = denominator ? 100 * (row.D - row.R) / denominator : null;
    require(close(margin, row.D_minus_R_margin_pp)
      && close(denominator ? 100 * row.D / denominator : null, row.D_two_party_share_pct)
      && close(denominator ? 100 * row.R / denominator : null, row.R_two_party_share_pct),
    "Congressional shares or margin do not reconcile");
    const previous = row.previous;
    const raw = previous && margin !== null ? margin - previous.D_minus_R_margin_pp : null;
    if (previous) require(previous.D >= 0 && previous.R >= 0 && previous.D + previous.R > 0
      && Number.isSafeInteger(previous.D) && Number.isSafeInteger(previous.R)
      && close(100 * (previous.D - previous.R) / (previous.D + previous.R),
        previous.D_minus_R_margin_pp), "Congressional previous-election counts differ");
    require(close(raw, row.raw_recorded_margin_change_pp)
      && close(raw === null ? null : raw / 2, row.raw_recorded_D_share_change_pp)
      && close(row.qualified_comparison ? raw : null, row.qualified_margin_change_pp),
    "Congressional recorded change does not reconcile");
    if (row.qualified_comparison) require(previous && row.comparison_holds.length === 0
      && row.status === "reported" && row.stage === "general" && !row.ranked_choice
      && row.count_coverage_complete && row.D > 0 && row.R > 0
      && previous.D > 0 && previous.R > 0
      && (row.chamber === "house" ? row.baseline.year === 2024
        : row.seat === "2" && row.election_kind === "regular" && row.baseline.seat === "2")
      && row.baseline.stage === row.stage, "Congressional comparison qualification differs");
  }
  require(new Set(data.coverage.map(row => row.id)).size === data.coverage.length,
    "Congressional coverage identities are duplicated");
  const coverageById = new Map(data.coverage.map(row => [row.id, row]));
  for (const race of races.values()) {
    const row = coverageById.get(race.id);
    require(row && ["chamber", "state_code", "status", "freshness", "advertised",
      "source_updated_at"].every(key => row[key] === race[key]),
    "Congressional coverage differs from its race");
  }
  for (const row of data.coverage)
    require(races.has(row.id) || (row.status === "held" && row.freshness === "unavailable"
      && typeof row.hold_reason === "string" && row.hold_reason.length > 0),
    "Congressional unavailable race lacks an explicit hold");
  for (const chamber of ["house", "senate"]) {
    const rows = [...races.values()].filter(row => row.chamber === chamber);
    const coverage = data.coverage.filter(row => row.chamber === chamber), summary = data.summary?.[chamber];
    require(summary && summary.refreshed === rows.filter(row => row.status === "reported").length
      && summary.retained === rows.filter(row => row.status !== "reported").length
      && summary.held === coverage.filter(row => row.status === "held").length
      && summary.discovered === coverage.filter(row => row.advertised).length,
    "Congressional freshness summary differs");
  }
  require(Array.isArray(data.house_states)
    && new Set(data.house_states.map(row => row.state_code)).size === data.house_states.length,
  "Congressional House-state comparison inventory differs");
  for (const row of data.house_states) {
    require(row.office === "house" && row.previous_year === 2024 && row.current_year === 2026
      && row.behavioral_estimate_updated === false && Array.isArray(row.comparison_holds)
      && typeof row.qualified_comparison === "boolean" && Array.isArray(row.selected_race_ids)
      && row.selected_race_ids.every(id => races.get(id)?.state_code === row.state_code
        && races.get(id)?.chamber === "house"), "House-state comparison identity differs");
    const current = row.selected_race_ids.map(id => races.get(id));
    for (const party of ["D", "R", "O", "U"])
      if (row.current[party] !== null) require(row.current[party] === current.reduce(
        (sum, race) => sum === null || race[party] === null ? null : sum + race[party], 0),
      "House-state totals differ from their complete race inventory");
    for (const value of [row.previous, row.current]) {
      require(["D", "R", "O"].every(key => count(value[key])), "House-state candidate counts differ");
      const denominator = value.D === null || value.R === null ? null : value.D + value.R;
      require(close(denominator ? 100 * (value.D - value.R) / denominator : null,
        value.D_minus_R_margin_pp), "House-state margin does not reconcile");
    }
    const raw = row.previous.D_minus_R_margin_pp === null || row.current.D_minus_R_margin_pp === null
      ? null : row.current.D_minus_R_margin_pp - row.previous.D_minus_R_margin_pp;
    require(close(raw, row.raw_recorded_margin_change_pp)
      && close(raw === null ? null : raw / 2, row.raw_recorded_D_share_change_pp)
      && close(row.qualified_comparison ? raw : null, row.qualified_margin_change_pp)
      && (!row.qualified_comparison || (raw !== null && row.comparison_holds.length === 0
        && row.selected_race_ids.length === row.expected_voting_seats)),
    "House-state comparison arithmetic or qualification differs");
  }
  return data;
}

function node(tag, text, attributes = {}) {
  const element = document.createElement(tag);
  if (text !== null) element.textContent = text;
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  return element;
}

export function installCongressionalReturns(root) {
  const disclosure = root.querySelector("[data-congressional-results]");
  if (!disclosure) return;
  const status = disclosure.querySelector("[data-congress-status]");
  const controls = disclosure.querySelector("[data-congress-controls]");
  const table = disclosure.querySelector("[data-congress-table]");
  const detail = disclosure.querySelector("[data-congress-detail]");
  const states = disclosure.querySelector("[data-congress-house-states]");
  const downloads = disclosure.querySelector("[data-congress-downloads]");
  let loading = false, loaded = false;
  const load = async () => {
    if (!disclosure.open || loaded || loading) return;
    loading = true;
    status.textContent = "Loading the complete national House and Senate snapshot...";
    try {
      const { data: raw, manifest, declaration } = await loadAutomaticCongress();
      const data = validateCongressionalResults(raw);
      disclosure.dataset.runtimeVersion = manifest.version;
      const chamber = node("select", null, { "aria-label": "Congressional chamber" });
      for (const [value, label] of [["house", "House"], ["senate", "Senate"]])
        chamber.append(node("option", label, { value }));
      const state = node("select", null, { "aria-label": "Congressional state" });
      state.append(node("option", "All states", { value: "" }));
      for (const code of [...new Set(data.races.map(row => row.state_code))].sort())
        state.append(node("option", code, { value: code }));
      const existingOffice = root.querySelector("[data-driver-office]");
      if (["house", "senate"].includes(existingOffice?.value)) chamber.value = existingOffice.value;
      controls.replaceChildren(chamber, state);
      const candidateRows = new Map(data.races.map(row =>
        [row.id, data.candidates.filter(candidate => candidate.id === row.id)]));
      const show = row => {
        detail.replaceChildren(
          node("h4", `${row.state_code} · ${row.chamber} · ${row.seat_label} · ${row.election_kind}`),
          node("p", `${row.native_type} · ${row.round} · ${row.freshness.replaceAll("_", " ")}. `
            + `Native count update: ${row.source_updated_at}. `
            + `Source results type: ${row.native_results_type ?? "not supplied"}. `
            + `Certification flag: ${row.native_certified ?? "not supplied"}.`),
          node("p", row.comparison_holds.length ? `Comparison held: ${row.comparison_holds.join("; ")}.`
            : row.chamber === "senate" ? "Qualified recorded comparison for the same Senate seat and election stage."
              : "Qualified recorded source-ID comparison; cross-year district boundaries are not independently certified."),
          node("p", `Previous ${row.baseline.year ?? "unavailable"} D/R: `
            + `${number(row.previous?.D ?? null)} / ${number(row.previous?.R ?? null)}. `
            + `Current D/R: ${number(row.D)} / ${number(row.R)}. `
            + `D-minus-R margin: ${points(row.D_minus_R_margin_pp)}. `
            + `Raw recorded margin change: ${points(row.raw_recorded_margin_change_pp)}. `
            + `Democratic two-party share change: ${points(row.raw_recorded_D_share_change_pp)}.`),
        );
        const list = node("ul", null);
        for (const candidate of candidateRows.get(row.id))
          list.append(node("li", `${candidate.name} · literal party: ${candidate.literal_party || "not supplied"}`
            + ` · ${number(candidate.votes)}${candidate.role === "provider_aggregate_other" ? " (source aggregate Other)" : ""}`));
        detail.append(list, node("p",
          "Candidate selections are not ballots or turnout. These new returns do not update the fitted behavioral explanations: "
          + "a separately reviewed candidate/source/frame match to the frozen model is required."));
        const source = row.source?.url;
        if (typeof source === "string" && source.startsWith("https://apps.npr.org/"))
          detail.append(node("a", "Native national results feed", { href: source }));
      };
      const draw = () => {
        const selected = data.races.filter(row => row.chamber === chamber.value
          && (!state.value || row.state_code === state.value));
        const totals = data.summary[chamber.value];
        status.textContent = `${totals.discovered} advertised ${chamber.value} contests: `
          + `${totals.refreshed} source-verified, ${totals.retained} retained, ${totals.held} unavailable holds. `
          + (totals.discovered === 0 ? "The live inventory is unavailable, not proof that no contests exist. " : "")
          + `Checked ${manifest.checked_at}; native count dates are shown separately. `
          + `${selected.filter(row => row.qualified_comparison).length} qualified recorded comparisons in this selection.`;
        const body = node("tbody", null);
        for (const row of selected) {
          const tr = node("tr", null, { "data-congress-race": row.id });
          const cell = node("th", null, { scope: "row" });
          const button = node("button", `${row.state_code} · ${row.seat_label} · ${row.native_type} · ${row.round}`,
            { type: "button" });
          button.addEventListener("click", () => show(row));
          cell.append(button);
          tr.append(cell);
          for (const value of [number(row.D), number(row.R), number(row.O), number(row.U),
            percent(row.D_two_party_share_pct),
            points(row.D_minus_R_margin_pp), points(row.raw_recorded_margin_change_pp),
            row.qualified_comparison ? "Qualified recorded" : "Held; raw arithmetic only",
            row.freshness.replaceAll("_", " "), row.source_updated_at])
            tr.append(node("td", value));
          body.append(tr);
        }
        table.querySelector("tbody")?.remove();
        table.append(body);
        states.replaceChildren();
        if (chamber.value === "house") {
          states.append(node("h4", "Statewide House comparisons"));
          const stateTable = node("table", null), header = node("tr", null), stateBody = node("tbody", null);
          for (const label of ["State", "2024 D", "2024 R", "2026 D", "2026 R",
            "Raw margin change", "Qualified margin change", "Qualification"])
            header.append(node("th", label, { scope: "col" }));
          const head = node("thead", null);
          head.append(header);
          stateTable.append(head);
          for (const row of data.house_states.filter(row => !state.value || row.state_code === state.value)) {
            const tr = node("tr", null, { "data-congress-house-state": row.state_code });
            for (const value of [row.state_code, number(row.previous.D), number(row.previous.R),
              number(row.current.D), number(row.current.R), points(row.raw_recorded_margin_change_pp),
              points(row.qualified_margin_change_pp),
              row.comparison_holds.join("; ") || "Complete same-office statewide source frame"])
              tr.append(node("td", value));
            stateBody.append(tr);
          }
          stateTable.append(stateBody);
          states.append(node("p", "These complete statewide totals do not assert matched district boundaries or individual histories."),
            stateTable);
        }
        detail.replaceChildren();
        if (selected.length) show(selected[0]);
      };
      chamber.addEventListener("change", draw);
      state.addEventListener("change", draw);
      existingOffice?.addEventListener("change", () => {
        if (["house", "senate"].includes(existingOffice.value)) {
          chamber.value = existingOffice.value; draw();
        }
      });
      downloads.replaceChildren();
      for (const [file, label] of [
        ["congress-races.csv", "All race totals and source dates"],
        ["congress-candidates.csv", "Every literal candidate and count"],
        ["congress-coverage.csv", "Every coverage and freshness decision"],
        ["congress-comparisons.csv", "All raw and qualified comparisons"],
        ["congress-house-states.csv", "Complete statewide House comparisons"],
        ["queries.json.gz", "Complete current and previous queries (JSON gzip)"],
      ])
        downloads.append(node("a", `${label} · ${file.endsWith(".csv") ? "CSV" : "JSON"}`, {
          href: new URL("congressional/" + file, declaration.base_url.replace(/\/?$/, "/")).href,
        }), document.createTextNode(" · "));
      downloads.append(node("a", "Complete reproducible runtime and source package · ZIP",
        { href: manifest.complete_download.url }));
      draw();
      loaded = true;
    } catch (error) {
      status.textContent = `Current congressional results unavailable: ${error.message} `
        + "Previously published analyses and complete downloads remain available.";
      controls.replaceChildren();
      table.querySelector("tbody")?.remove();
      detail.replaceChildren();
      status.append(document.createTextNode(" "), node("button", "Retry", { type: "button" }));
      status.lastChild.addEventListener("click", load);
    } finally {
      loading = false;
    }
  };
  disclosure.addEventListener("toggle", load);
  load();
}

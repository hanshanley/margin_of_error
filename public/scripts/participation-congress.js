import { loadAutomaticCongress } from "./participation-automatic-runtime.js";

const count = value => value === null || (Number.isSafeInteger(value) && value >= 0);
const close = (a, b) => a === null ? b === null : typeof b === "number"
  && Number.isFinite(b) && Math.abs(a - b) < 1e-9;
const number = value => value === null ? "Not supplied" : value.toLocaleString("en-US");
const points = value => value === null ? "Unavailable" : `${value > 0 ? "+" : ""}${value.toFixed(2)} pp`;
const percent = value => value === null ? "Unavailable" : `${value.toFixed(2)}%`;
const require = (condition, message) => { if (!condition) throw new Error(message); };

const equal = (a, b) => a === b || (a !== null && b !== null
  && typeof a === "object" && typeof b === "object"
  && Array.isArray(a) === Array.isArray(b)
  && Object.keys(a).length === Object.keys(b).length
  && Object.keys(a).every(key => Object.hasOwn(b, key) && equal(a[key], b[key])));
const finalElectionPolicy = "latest_completed_same_seat_final_election_to_final_election";
const readerLimit = "Reviewed same-seat comparison is qualified in congress-comparisons.csv; "
  + "the deployed v1 reader can badge only regular Class II, same-stage comparisons. "
  + "Raw counts and changes remain available here.";
const historicalParties = { D: "D", DEM: "D", DFL: "D", R: "R",
  "DEM/IP/WF": "D", "D/IP/WF": "D", "D/IP": "D", "R/CON": "R",
  Democratic: "D", Republican: "R" };

function reviewedSenateFrame(row, candidates) {
  const baseline = row.baseline, facts = row.previous_candidates;
  require(baseline?.comparison_policy === finalElectionPolicy
    && ["1", "2", "3"].includes(row.seat) && baseline.seat === row.seat
    && ["regular", "special"].includes(row.election_kind)
    && ["regular", "special"].includes(baseline.election_kind)
    && ["general", "general_runoff"].includes(baseline.stage)
    && Number.isSafeInteger(baseline.year) && baseline.year < 2026
    && [2020, 2022, 2024].includes(baseline.cycle_year)
    && [baseline.cycle_year, baseline.cycle_year + 1].includes(baseline.year)
    && baseline.previous_stage_differs === (baseline.stage !== row.stage)
    && baseline.previous_regular_special_differs === (baseline.election_kind !== row.election_kind)
    && row.round === "not_ranked" && (row.native_runoff === false || row.native_runoff === null)
    && Array.isArray(baseline.source_urls) && baseline.source_urls.length === 1
    && baseline.source_urls[0] === (baseline.cycle_year === 2024
      ? "https://sos.nebraska.gov/sites/default/files/doc/elections/2024/2024%20General%20Canvass%20Book.pdf"
      : `https://www.fec.gov/resources/cms-content/documents/federalelections${baseline.cycle_year}.xlsx`)
    && Array.isArray(facts) && facts.length > 0,
  "Senate reviewed seat or final-election policy differs");
  const totals = { D: 0, R: 0, O: 0 };
  for (const fact of facts) {
    require(fact.state_code === row.state_code && fact.seat === row.seat
      && fact.stage === baseline.stage && fact.year === baseline.year
      && fact.cycle_year === baseline.cycle_year && fact.election_kind === baseline.election_kind
      && fact.ranked_choice === false && fact.round === "not_ranked"
      && typeof fact.candidate === "string" && fact.candidate.length > 0
      && typeof fact.literal_party === "string" && fact.literal_party.length > 0
      && baseline.source_urls.includes(fact.source_url)
      && ["D", "R", "O"].includes(fact.party_group)
      && fact.party_group === (historicalParties[fact.literal_party.trim()] ?? "O")
      && Number.isSafeInteger(fact.votes) && fact.votes >= 0,
    "Senate historical candidate, seat, stage, round, source or count differs");
    totals[fact.party_group] += fact.votes;
  }
  require(Object.keys(totals).every(party => Number.isSafeInteger(totals[party])
    && totals[party] === row.previous[party])
    && ["D", "R"].every(party =>
      facts.filter(fact => fact.party_group === party).length === 1
      && candidates.filter(candidate => candidate.party_group === party
        && candidate.role === "named_candidate").length === 1),
  "Senate historical counts or unique major-party coverage differ");
}

function validatePayload(data, reviewed = false) {
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
      && row.chamber === parent.chamber && row.seat === parent.seat
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
      && (row.chamber === "house" ? row.baseline.year === 2024 && row.baseline.stage === row.stage
        : reviewed || (row.seat === "2" && row.election_kind === "regular"
          && row.baseline.seat === "2" && row.baseline.stage === row.stage)),
    "Congressional comparison qualification differs");
    if (reviewed && row.chamber === "senate" && row.qualified_comparison)
      reviewedSenateFrame(row, selected);
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

export function validateCongressionalResults(data) {
  validatePayload(data);
  if (data.reviewed_races === undefined) return data;
  require(data.analytical_handoff?.review_version === "20261116-01"
    && Array.isArray(data.reviewed_races) && data.reviewed_races.length === data.races.length,
  "Congressional reviewed comparison version or inventory differs");
  const legacy = new Map(data.races.map(row => [row.id, row]));
  const presentationFields = new Set(["qualified_comparison", "qualified_margin_change_pp",
    "comparison_holds", "legacy_reader_display_limit", "reviewed_qualified_comparison",
    "reviewed_qualified_margin_change_pp"]);
  for (const row of data.reviewed_races) {
    const old = legacy.get(row.id);
    require(old, "Congressional reviewed race identity differs");
    if (old.legacy_reader_display_limit === true) {
      require(old.chamber === "senate" && old.qualified_comparison === false
        && old.qualified_margin_change_pp === null && old.reviewed_qualified_comparison === true
        && equal(old.comparison_holds, [readerLimit]) && row.qualified_comparison === true
        && equal(row.comparison_holds, [])
        && row.qualified_margin_change_pp === old.reviewed_qualified_margin_change_pp
        && equal(Object.fromEntries(Object.entries(old).filter(([key]) => !presentationFields.has(key))),
          Object.fromEntries(Object.entries(row).filter(([key]) => !presentationFields.has(key)))),
      "Congressional reader-only hold or native frame differs");
    } else require(equal(old, row), "Congressional reviewed comparison changes a non-reader hold");
  }
  const result = validatePayload({ ...data, races: data.reviewed_races }, true);
  const coverage = data.scientific_comparison_coverage;
  const qualified = rows => rows.filter(row => row.chamber === "senate" && row.qualified_comparison).length;
  require(coverage?.reviewed_qualified_senate === qualified(result.races)
    && coverage.legacy_reader_qualified_senate === qualified(data.races)
    && coverage.reviewed_qualified_house_states === data.house_states.filter(row => row.qualified_comparison).length,
  "Congressional reviewed comparison coverage differs");
  return result;
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
            : row.chamber === "senate" ? `Qualified recorded comparison for the same Senate seat: `
              + `${row.baseline.year} ${row.baseline.election_kind ?? "regular"} ${row.baseline.stage}`
              + ` to 2026 ${row.election_kind} ${row.stage}. `
              + (row.baseline.previous_stage_differs
                ? "Final election to final election; the prior decisive runoff is not a preliminary round."
                : "Election kinds and stages are preserved separately.")
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

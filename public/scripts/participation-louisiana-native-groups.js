import { loadDataset, checkedDatasetFile } from "./participation-dataset.js";
import { conicProjection, projectFeatures } from "./participation-map-projection.js";

const datasetId = "source-native-la-early-group-data";
const contract = "participation.louisiana_native_early_groups.v1";
const referencePin = {
  bytes: 1288586,
  sha256: "7eeec4d3ebb2ca1fd2897e5f914e925a3b1fb88748bc25c51bd7977bfd930eac",
};
const nativeFields = ["VOTES", "WHITE", "BLACK", "OTHER", "MALE", "FEMALE", "DEM", "REP",
  "NO PARTY", "OTH", "INPER", "ABS", "UOCAVA IN", "UOCAVA OUT", "ASST D", "ASST I"];
const groups = [
  ["WHITE", "race", "Race · WHITE"], ["BLACK", "race", "Race · BLACK"],
  ["OTHER", "race", "Race · OTHER"], ["MALE", "sex", "Sex · MALE"],
  ["FEMALE", "sex", "Sex · FEMALE"], ["INPER", "native_method", "Native method · INPER"],
  ["ABS", "native_method", "Native method · ABS"],
];
const require = (condition, message) => {
  if (!condition) throw new Error("Unqualified Louisiana native groups: " + message);
};
const https = value => typeof value === "string" && value.startsWith("https://");
const unique = values => new Set(values).size === values.length;

export function canonicalOwnVotesShare(count, votes) {
  require(Number.isSafeInteger(count) && count >= 0
    && Number.isSafeInteger(votes) && votes > 0 && count <= votes, "share inputs");
  const scale = 10n ** 18n, denominator = BigInt(votes);
  const numerator = BigInt(count) * 100n * scale;
  let quotient = numerator / denominator;
  const remainder = numerator % denominator, twice = remainder * 2n;
  if (twice > denominator || twice === denominator && quotient % 2n === 1n) quotient += 1n;
  const text = quotient.toString().padStart(19, "0");
  return `${text.slice(0, -18)}.${text.slice(-18)}`;
}

export function validateLouisianaGroupIndex(index) {
  require(index?.contract === contract && index.year === 2026
    && JSON.stringify(index.states) === '["LA"]', "contract/year/state");
  require(index.state?.file === "states/LA.json.gz" && index.state.profiles === 65
    && index.state.parishes === 64 && index.state.group_bindings === 448
    && index.state.state_parent_separate === true, "profile inventory");
  require(index.reference?.file === "references/LA-context.json.gz"
    && index.reference.features === 64
    && index.reference.bytes === referencePin.bytes
    && index.reference.sha256 === referencePin.sha256
    && index.reference.scope === "reviewed 2026 parish context shapes, not 2026 voting precincts"
    && index.reference.scope.includes("not 2026 voting precincts"), "context reference");
  require(index.observations?.records === 1040
    && index.observations.contract === "participation.observation.v1"
    && index.source_parent_and_children_additive === false
    && index.source_parent_and_children_independent === false
    && index.unknowns_are_zero === false && index.zeros_preserved === 21, "source accounting");
  require(index.groups.length === groups.length && index.groups.every((row, position) =>
    row.native_group === groups[position][0] && row.dimension === groups[position][1]),
  "native group inventory");
  return index;
}

function validateProfile(row, parish) {
  require(row?.scope_kind === (parish ? "parish" : "state_parent")
    && typeof row.source_key === "string" && typeof row.native_label === "string"
    && (parish ? /^[0-9]{2}$/.test(row.native_code) : row.native_code === null)
    && Number.isSafeInteger(row.votes)
    && row.votes >= 0 && row.native_fields?.VOTES === row.votes, "native profile");
  require(Object.keys(row.native_fields).sort().join("|") === [...nativeFields].sort().join("|")
    && nativeFields.every(field => Number.isSafeInteger(row.native_fields[field])
      && row.native_fields[field] >= 0), "complete native fields");
  require(Array.isArray(row.groups) && row.groups.length === 7
    && JSON.stringify(row.groups.map(group => group.native_group)) === JSON.stringify(groups.map(([name]) => name)),
  "seven native groups");
  for (const [position, group] of row.groups.entries())
    require(group.dimension === groups[position][1]
      && Number.isSafeInteger(group.count) && group.count >= 0
      && group.count === row.native_fields[group.native_group]
      && group.denominator === "own_native_VOTES_not_registered_population"
      && group.turnout_rate === null
      && group.share_of_own_native_votes === canonicalOwnVotesShare(group.count, row.votes),
    "composition semantics");
  const totals = Object.fromEntries(["race", "sex", "native_method"].map(dimension =>
    [dimension, row.groups.filter(group => group.dimension === dimension)
      .reduce((sum, group) => sum + group.count, 0)]));
  require(totals.race === row.votes && totals.native_method === row.votes
    && row.votes - totals.sex === row.margin_residuals.sex, "margin accounting");
  if (parish)
    require(/^[0-9]{5}$/.test(row.reference?.feature_key)
      && row.reference.reference_sha256 === referencePin.sha256
      && typeof row.reference.name === "string" && row.reference.name.endsWith(" Parish")
      && row.reference.native_code_is_fips === false
      && row.reference.context_not_2026_voting_precinct === true, "reviewed context binding");
}

export function validateLouisianaGroupState(data) {
  require(data?.contract === contract && data.state_code === "LA" && data.year === 2026
    && Array.isArray(data.parishes) && data.parishes.length === 64, "state inventory");
  validateProfile(data.state_parent, false);
  data.parishes.forEach(row => validateProfile(row, true));
  const profiles = [data.state_parent, ...data.parishes];
  require(unique(profiles.map(row => row.source_key))
    && unique(data.parishes.map(row => row.native_code))
    && unique(data.parishes.map(row => row.native_label))
    && unique(data.parishes.map(row => row.reference.feature_key))
    && unique(data.parishes.map(row => row.reference.name)), "unique profile identities");
  require(data.state_parent.votes === 536190
    && data.state_parent.native_fields.INPER === 448588
    && data.state_parent.native_fields.ABS === 87602
    && data.state_parent.native_fields.WHITE === 328590
    && data.state_parent.native_fields.BLACK === 184348
    && data.state_parent.native_fields.OTHER === 23252
    && data.state_parent.native_fields.MALE === 224376
    && data.state_parent.native_fields.FEMALE === 311536
    && data.state_parent.margin_residuals.sex === 278, "state controls");
  require(data.counts?.native_count_cells === 1040 && data.counts.group_bindings === 448
    && data.counts.provider_comparisons === 128 && data.counts.source_scope_decisions === 51
    && data.counts.zero_cells === 21 && data.counts.parish_sex_residuals === 37
    && data.source?.original_template_redistributed === false
    && data.source?.replay_basis === "complete permitted reviewed aggregate facts", "complete review");
  require(data.semantics?.native_abs_is_mail_returned === false
    && data.semantics.party_is_vote_choice === false
    && data.semantics.marginals_are_joint_groups === false
    && data.semantics.source_codes_are_fips === false
    && data.semantics.geometry_is_2026_voting_precincts === false
    && data.semantics.group_turnout === false, "source-scope promotion");
  return data;
}

export function validateLouisianaGeometry(data, state) {
  require(data?.type === "FeatureCollection" && data.features?.length === 64, "geometry inventory");
  const references = new Map(state.parishes.map(row => [row.reference.feature_key, row.reference]));
  const geometryKeys = data.features.map(feature => String(feature.properties?.key));
  require(unique(geometryKeys) && data.features.every(feature => {
    const key = String(feature.properties?.key), reference = references.get(key);
    return reference && feature.properties.name === reference.name
    && feature.properties.state_code === "LA"
    && feature.properties.geometry_scope?.includes("not precincts")
    && ["Polygon", "MultiPolygon"].includes(feature.geometry?.type);
  }), "geometry identity/scope");
  return data;
}

export function createLouisianaGroupReader(dependencies = { loadDataset, checkedDatasetFile }) {
  let indexPending, bodyPending;
  const loadIndex = () => indexPending ||= dependencies.loadDataset(datasetId).then(({ entry, index }) => {
      validateLouisianaGroupIndex(index);
      const stateFile = entry.files?.[index.state.file], referenceFile = entry.files?.[index.reference.file];
      require(entry.id === datasetId && stateFile && referenceFile
        && referenceFile.bytes === index.reference.bytes
        && referenceFile.sha256 === index.reference.sha256, "dataset declaration");
      return { entry, index };
    }).catch(error => { indexPending = null; throw error; });
  return { loadIndex, load() {
    bodyPending ||= loadIndex().then(async ({ entry, index }) => {
      const [state, geometry] = await Promise.all([
        dependencies.checkedDatasetFile(entry.base_url,
          { file: index.state.file, ...entry.files[index.state.file] }),
        dependencies.checkedDatasetFile(entry.base_url,
          { file: index.reference.file, ...entry.files[index.reference.file] }),
      ]);
      validateLouisianaGroupState(state);
      validateLouisianaGeometry(geometry, state);
      return { entry, index, state, geometry };
    }).catch(error => { bodyPending = null; throw error; });
    return bodyPending;
  } };
}

const reader = createLouisianaGroupReader();
export function installLouisianaNativeGroups(anchor = document.getElementById("participation-coverage"),
  source = reader) {
  if (!anchor) return { setScope() {} };
  const node = (tag, text, className) => {
    const result = document.createElement(tag);
    if (text !== undefined) result.textContent = text;
    if (className) result.className = className;
    return result;
  };
  const svgNode = (tag, attributes = {}) => {
    const result = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [name, value] of Object.entries(attributes)) result.setAttribute(name, value);
    return result;
  };
  const panel = node("details", undefined, "source-coverage louisiana-native-groups");
  panel.id = "louisiana-native-groups"; panel.hidden = true;
  const summary = node("summary"), content = node("div");
  panel.append(summary, content); anchor.after(panel);
  let generation = 0, scope, loaded = false;
  const load = async () => {
    if (!panel.open || panel.hidden || loaded) return;
    loaded = true;
    const token = generation;
    content.replaceChildren(node("p", "Loading checksum-verified Louisiana native group counts..."));
    let verifiedEntry;
    try {
      verifiedEntry = (await source.loadIndex()).entry;
      const result = await source.load();
      if (token !== generation) return;
      const { entry, index, state, geometry } = result;
      content.replaceChildren(node("p",
        "Official native early/absentee-report VOTES by 64 parishes and a separate state parent. "
        + "These are not full-election ballots, unique people, eligible-population turnout, or demographic group turnout. "
        + "Race, sex and method are separate margins; party fields are accounting, not vote choice. "
        + "All 21 literal zero count cells remain zero; unknown quantities remain unknown."));
      const controls = node("div", undefined, "controls");
      const groupLabel = node("label", "Native group"), group = node("select");
      group.setAttribute("aria-label", "Louisiana native group");
      for (const [value, , label] of groups) {
        const option = node("option", label); option.value = value; group.append(option);
      }
      const displayLabel = node("label", "Map value"), display = node("select");
      display.setAttribute("aria-label", "Louisiana group map value");
      for (const [value, label] of [["count", "Source count"], ["share", "Share of own native VOTES"]]) {
        const option = node("option", label); option.value = value; display.append(option);
      }
      groupLabel.append(group); displayLabel.append(display); controls.append(groupLabel, displayLabel);
      const sourceNote = node("p", undefined, "caption"), stateSummary = node("p");
      const svg = svgNode("svg", { viewBox: "0 0 760 520", role: "group",
        "aria-label": "Louisiana parish context map for native early and absentee report groups" });
      svg.style.maxWidth = "100%";
      svg.style.width = "100%";
      svg.style.height = "auto";
      const detail = node("div"), downloads = node("ul");
      const links = [
        [state.source.url, "Official source publication"],
        [entry.base_url + index.state.file, "Complete Louisiana typed source data (JSON.gz)"],
        [entry.base_url + index.reference.file, "Full 64-parish context geometry (GeoJSON.gz)"],
      ];
      if (https(entry.complete_download?.url))
        links.unshift([entry.complete_download.url,
          "Complete numerical facts, queries, decisions, code, tests and reproduction"]);
      for (const [href, label] of links) {
        const item = node("li"), link = node("a", label, "source-link");
        link.href = href; item.append(link); downloads.append(item);
      }
      if (!https(entry.complete_download?.url))
        downloads.prepend(node("li", "Complete fact-only SDK publication pending; catalog activation remains blocked."));
      const projected = projectFeatures(geometry.features, conicProjection(-92.2, 28.5, 33.5), [20, 20, 720, 470]);
      const byKey = new Map(state.parishes.map(row => [row.reference.feature_key, row]));
      let selected = state.parishes[0];
      const selectedGroup = row => row.groups.find(item => item.native_group === group.value);
      const renderDetail = row => {
        selected = row;
        const chosen = selectedGroup(row);
        detail.replaceChildren(
          node("h3", row.reference.name),
          node("p", `${chosen.native_group}: ${chosen.count.toLocaleString("en-US")} of `
            + `${row.votes.toLocaleString("en-US")} own native VOTES (${chosen.share_of_own_native_votes}%).`),
          node("p", `Native code ${row.native_code} is not FIPS. Sex arithmetic residual: `
            + `${row.margin_residuals.sex.toLocaleString("en-US")}. Literal zero cells remain zero; `
            + "unknown full-election, unique-person and group-turnout quantities remain unknown.")
        );
      };
      const draw = () => {
        const parentGroup = selectedGroup(state.state_parent);
        stateSummary.textContent = `State parent: ${parentGroup.native_group} `
          + `${parentGroup.count.toLocaleString("en-US")} of ${state.state_parent.votes.toLocaleString("en-US")} `
          + `own native VOTES (${parentGroup.share_of_own_native_votes}%). State sex residual 278; `
          + "37 parish sex residuals remain. Parent and parish margins are controls, not additive independent populations.";
        sourceNote.textContent = "Printed 11/10/2026 3:10:06 AM; timezone unknown. "
          + "Query filter 1900-01-01 through 2026-11-09 is not an observed voting period or finality claim. "
          + "Shapes are reviewed 2026 parish context, not 2026 voting precincts; upstream lineage is not established.";
        svg.replaceChildren();
        const values = state.parishes.map(row => {
          const chosen = selectedGroup(row);
          return display.value === "count" ? chosen.count : Number(chosen.share_of_own_native_votes);
        });
        const maximum = Math.max(...values, 1);
        for (const item of projected) {
          const row = byKey.get(String(item.feature.properties.key)), chosen = selectedGroup(row);
          const value = display.value === "count" ? chosen.count : Number(chosen.share_of_own_native_votes);
          const shade = Math.round(245 - 150 * value / maximum);
          const path = svgNode("path", { d: item.d, tabindex: "0", role: "button",
            fill: `rgb(${shade},${Math.min(245, shade + 15)},${Math.min(250, shade + 28)})`,
            stroke: row === selected ? "#102a43" : "#ffffff",
            "stroke-width": row === selected ? "2.5" : "0.8",
            "aria-label": `${row.reference.name}: ${chosen.native_group} ${chosen.count.toLocaleString("en-US")}, `
              + `${chosen.share_of_own_native_votes}% of own native VOTES` });
          const title = svgNode("title");
          title.textContent = path.getAttribute("aria-label"); path.append(title);
          const choose = () => { renderDetail(row); draw(); };
          path.addEventListener("click", choose);
          path.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); }
          });
          svg.append(path);
        }
      };
      group.addEventListener("change", () => { renderDetail(selected); draw(); });
      display.addEventListener("change", draw);
      renderDetail(selected); draw();
      content.append(controls, stateSummary, sourceNote, svg, detail, downloads);
    } catch (error) {
      if (token !== generation) return;
      content.replaceChildren(node("p", `${error.message}. No Louisiana values, shares or rates were substituted.`));
      if (https(verifiedEntry?.complete_download?.url)) {
        const complete = node("a", "Complete verified numerical package", "source-link");
        complete.href = verifiedEntry.complete_download.url; content.append(complete);
      }
      const retry = node("button", "Retry verified Louisiana source data");
      retry.type = "button";
      retry.addEventListener("click", () => { loaded = false; load(); });
      content.append(retry);
    }
  };
  panel.addEventListener("toggle", load);
  return { setScope(value) {
    if (scope && ["year", "code", "enabled", "name"].every(key => scope[key] === value[key])) return;
    generation += 1; scope = { ...value }; loaded = false;
    panel.hidden = !value.enabled || value.year !== 2026 || value.code !== "LA";
    summary.textContent = `2026 Louisiana native early/absentee group counts · ${value.name || "Louisiana"}`;
    content.replaceChildren();
    if (!panel.hidden && panel.open) load();
  } };
}

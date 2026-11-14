import { norcAssociations, norcFamilies, norcEstimate } from "./participation-norc-house.js";

const finite = value => typeof value === "number" && Number.isFinite(value);
const metrics = ["switching", "exit", "entry", "modeled_nonparticipation",
  "other_choice", "unresolved", "total", "retaining"];
const states = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(" ");
const cached = new Map();
const digest = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
  value => value.toString(16).padStart(2, "0")).join("");

export function validateHouseSensitivity(data, sources) {
  if (data?.contract !== "participation.house_model_sensitivity.v1"
      || data.variant_count !== 9 || data.confidence_intervals !== null
      || data.source_fits_reproduced !== false || data.fitted_aggregate_projection_replay_only !== true
      || data.new_models_or_weights_or_source_counts !== false
      || data.not_all_model_survey_transport_or_endpoint_uncertainty !== true
      || data.group_ranges_are_not_group_vote_shares !== true
      || data.contribution_units !== "statewide_D_minus_R_margin_percentage_points"
      || data.retaining_units !== "fraction_of_model_assigned_prior_DR_mass"
      || data.default_variant !== "original|accepted_ridge_multinomial"
      || JSON.stringify(data.profiles) !== JSON.stringify(norcAssociations.map(([key]) => key))
      || JSON.stringify(data.families) !== JSON.stringify(norcFamilies.map(([key]) => key))
      || !Array.isArray(data.rows) || data.rows.length !== 50)
    throw new Error("Unqualified model-sensitivity projection");
  for (const [profile] of norcAssociations) {
    const declared=data.source_pins?.[profile],source=sources?.[profile];
    const addressMatches=declared?.url===source?.url
      || typeof declared?.path==="string" && source?.url?.endsWith("/"+declared.path);
    if (!source || !addressMatches || ["bytes", "sha256"].some(key =>
      declared?.[key] !== source[key])
      || ["decoded_bytes","decoded_sha256"].some(key =>
        declared?.[key]!==undefined && declared[key]!==source[key]))
      throw new Error("Sensitivity and current model source versions differ");
  }
  const seen = new Set();
  let groups = 0, supported = 0;
  for (const row of data.rows) {
    if (!states.includes(row.state_code) || seen.has(row.state_code)
        || typeof row.qualified !== "boolean" || !row.scopes?.[""] || !row.endpoint)
      throw new Error("Sensitivity state inventory differs");
    seen.add(row.state_code);
    if (row.scopes[""].available !== row.qualified)
      throw new Error("Sensitivity state qualification differs");
    for (const [group, scope] of Object.entries(row.scopes)) {
      if (typeof scope.available !== "boolean" || (!row.qualified && scope.available)
          || Object.keys(scope.metrics || {}).sort().join() !== [...metrics].sort().join())
        throw new Error("Sensitivity disclosure mask differs");
      if (group) { groups++; supported += Number(scope.available); }
      for (const [key, range] of Object.entries(scope.metrics)) {
        if (range === null) continue;
        if (!scope.available || range.variants !== 9
            || ![range.minimum, range.maximum, range.default].every(finite)
            || range.minimum > range.default || range.default > range.maximum
            || (key === "retaining" && (range.minimum < 0 || range.maximum > 1)))
          throw new Error("Invalid or disclosed held sensitivity range");
      }
    }
  }
  const qualified = data.rows.filter(row => row.qualified).length;
  if (data.summary?.states !== 50 || data.summary.qualified_states !== qualified
      || data.summary.held_states !== 50-qualified || data.summary.group_decisions !== groups
      || data.summary.supported_group_decisions !== supported)
    throw new Error("Sensitivity coverage summary differs");
  return data;
}

export function houseSensitivityScope(data, row, group="") {
  if (!data || !row) return null;
  const state = data.rows.find(value => value.state_code === row.state_code);
  const comparison = row.reported_comparison;
  if (!state || state.qualified !== row.source_comparison_available
      || state.endpoint.snapshot !== (comparison.current_snapshot ?? null)
      || state.endpoint.native_clock !== (comparison.current_native_clock ?? null))
    throw new Error("Sensitivity endpoint or qualification does not match the selected estimate");
  const value = norcEstimate(row, group);
  const scope = state.scopes[group];
  if (!scope || scope.available !== Boolean(row.source_comparison_available && value))
    throw new Error("Sensitivity group is not the selected model group");
  if (!scope.available) return null;
  const selected = {...value.contributions_pp, modeled_nonparticipation:value.net_participation_pp,
    total:value.total_contribution_pp, retaining:value.gross_outcomes?.retaining};
  for (const [key, range] of Object.entries(scope.metrics))
    if (range !== null && (!finite(selected[key]) || selected[key] < range.minimum-1e-8
        || selected[key] > range.maximum+1e-8))
      throw new Error("Sensitivity omits the selected model value");
  return scope;
}

export async function loadHouseSensitivity(receipt, sources) {
  const research=/^https:\/\/raw\.githubusercontent\.com\/hanshanley\/voter-participation\/[a-f0-9]{40}\/data\/house-model-disclosures\/[a-zA-Z0-9-]+\/sensitivity\.json\.gz$/;
  const runtime=/^https:\/\/raw\.githubusercontent\.com\/hanshanley\/margin_of_error\/([a-f0-9]{40})\/automatic\/versions\/([a-f0-9]{64})\/house\/[A-Za-z0-9_./-]+\.json\.gz$/;
  const runtimeMatch=runtime.exec(receipt?.url || "");
  if (!(research.test(receipt?.url) || runtimeMatch)
      || runtimeMatch && (receipt.automatic_runtime_commit!==runtimeMatch[1]
        || receipt.automatic_runtime_version!==runtimeMatch[2])
      || receipt.compression !== "gzip"
      || !Number.isSafeInteger(receipt.bytes) || receipt.bytes <= 0
      || !Number.isSafeInteger(receipt.decoded_bytes) || receipt.decoded_bytes <= 0
      || !/^[a-f0-9]{64}$/.test(receipt.sha256)
      || !/^[a-f0-9]{64}$/.test(receipt.decoded_sha256))
    throw new Error("Missing pinned model-sensitivity receipt");
  const key = JSON.stringify([receipt, norcAssociations.map(([profile]) =>
    [profile, sources?.[profile]?.url, sources?.[profile]?.bytes, sources?.[profile]?.sha256])]);
  if (!cached.has(key)) {
    const promise = (async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 20000);
      try {
        const response = await fetch(receipt.url, {signal:controller.signal});
        if (!response.ok) throw new Error(`Sensitivity HTTP ${response.status}`);
        const bytes = await response.arrayBuffer();
        if (bytes.byteLength !== receipt.bytes || await digest(bytes) !== receipt.sha256)
          throw new Error("Sensitivity checksum mismatch");
        const decoded = await new Response(new Blob([bytes]).stream()
          .pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
        if (decoded.byteLength !== receipt.decoded_bytes || await digest(decoded) !== receipt.decoded_sha256)
          throw new Error("Sensitivity decoded checksum mismatch");
        return validateHouseSensitivity(JSON.parse(new TextDecoder("utf-8", {fatal:true}).decode(decoded)), sources);
      } finally { clearTimeout(timer); }
    })().catch(error => { if (cached.get(key) === promise) cached.delete(key); throw error; });
    cached.set(key, promise);
  }
  return cached.get(key);
}

export const automaticRuntimeURL =
  "https://raw.githubusercontent.com/hanshanley/margin_of_error/participation-data/automatic/latest.json";

const hash = /^[a-f0-9]{64}$/;
const commit = /^[a-f0-9]{40}$/;
const immutableRaw = /^https:\/\/raw\.githubusercontent\.com\/hanshanley\/margin_of_error\/([a-f0-9]{40})\/(.+)$/;
// Astro bundles and standalone map modules must select the same page-session snapshot.
const session = globalThis[Symbol.for("participation.automatic-runtime.v1")] ||= {
  runtimeStates: new Map(), rejected: new Set(), automaticBodies: new Map(), manifestPromise: null,
};
const { runtimeStates, rejected, automaticBodies } = session;

const text = value => typeof value === "string" && value.length > 0;
const pin = value => value && Number.isSafeInteger(value.bytes) && value.bytes > 0
  && hash.test(value.sha256);

function rawCommit(url) {
  return typeof url === "string" ? immutableRaw.exec(url)?.[1] || null : null;
}

function validateCompleteDownload(value) {
  if (!pin(value) || value.immutable !== true || value.verified_anonymously !== true
      || !/^https:\/\/github\.com\/hanshanley\/margin_of_error\/releases\/download\/[^/]+\/[^/]+$/.test(value.url))
    throw new Error("Automatic runtime complete download is not immutable and byte-pinned");
  return value;
}

function validateDatasetDescriptor(entry, id, recordContract) {
  const baseCommit = rawCommit(entry?.base_url);
  if (entry?.contract !== "participation.dataset.v1"
      || entry.id !== id || entry.status !== "loaded"
      || entry.record_contract !== recordContract
      || !hash.test(entry.version) || !commit.test(entry.staged_commit)
      || baseCommit !== entry.staged_commit || !pin(entry.index)
      || entry.index.file !== "index.json" || !entry.files
      || Array.isArray(entry.files) || typeof entry.files !== "object"
      || entry.files["index.json"]?.bytes !== entry.index.bytes
      || entry.files["index.json"]?.sha256 !== entry.index.sha256)
    throw new Error("Automatic count descriptor is not the existing pinned dataset contract");
  validateCompleteDownload(entry.complete_download);
  for (const [file, declaration] of Object.entries(entry.files))
    if (!/^[A-Za-z0-9_./-]+\.(json|json\.gz)$/.test(file) || file.startsWith("/")
        || file.split("/").includes("..") || !pin(declaration))
      throw new Error("Automatic count file inventory is not byte-pinned");
  return baseCommit;
}

function validateBodyPin(value) {
  if (!value || typeof value.path !== "string"
      || !/^[A-Za-z0-9_./-]+\.json\.gz$/.test(value.path)
      || value.path.startsWith("/") || value.path.split("/").includes("..")
      || value.compression !== "gzip" || value.media_type !== "application/json"
      || !pin(value) || !Number.isSafeInteger(value.decoded_bytes) || value.decoded_bytes < 1
      || !hash.test(value.decoded_sha256))
    throw new Error("Automatic House body is not an existing-shape byte-pinned JSON viewer");
  return value;
}

function validateAutomaticHouseSources(sources, version) {
  const profiles = ["original", "attenuated", "full"];
  const families = ["accepted_ridge_multinomial", "histogram_gradient_boosting",
    "extra_randomized_trees"];
  const base = immutableRaw.exec((sources?.base_url || "").replace(/\/?$/, "/"));
  if (sources?.contract !== "participation.automatic_house_sources.v1"
      || !hash.test(sources.version) || sources.publication_bound !== true
      || !base || base[2] !== `automatic/versions/${version}/`
      || sources.election_date !== "2026-11-03"
      || JSON.stringify(sources.profiles) !== JSON.stringify(profiles)
      || JSON.stringify(sources.families) !== JSON.stringify(families)
      || sources.atomic_rejection_required_if_any_selected_body_pin_or_identity_fails !== true
      || !sources.controls || !sources.descriptors || !sources.profile_viewers)
    throw new Error("Unknown automatic House source contract");
  const expectedControls = Object.fromEntries(profiles.flatMap(profile =>
    families.map(family => [`${profile}|${family}`, `${profile}/${family}`])));
  const controls = {};
  for (const profile of profiles) for (const family of families)
    controls[`${profile}|${family}`] = sources.controls?.[profile]?.[family];
  if (JSON.stringify(controls) !== JSON.stringify(expectedControls)
      || Object.keys(sources.descriptors).sort().join() !== Object.values(expectedControls).sort().join())
    throw new Error("Automatic House nine-control inventory differs");
  let identities;
  for (const [key, descriptor] of Object.entries(sources.descriptors)) {
    const [profile, family] = key.split("/");
    const qualified = descriptor?.qualified_state_codes;
    const held = descriptor?.held_state_codes;
    if (descriptor?.contract !== "participation.automatic_house_source_descriptor.v1"
        || descriptor.control_key !== key || descriptor.profile !== profile
        || descriptor.family !== family || descriptor.election_date !== "2026-11-03"
        || !hash.test(descriptor.version) || !text(descriptor.estimate_contract)
        || !Array.isArray(qualified) || qualified.length !== 33
        || !Array.isArray(held) || held.length !== 17
        || new Set([...qualified, ...held]).size !== 50
        || [...qualified, ...held].some(code => code === "DC" || !/^[A-Z]{2}$/.test(code))
        || !["qualification_mask_sha256", "hold_identity_sha256", "gate_identity_sha256",
          "official_source_guard_sha256"].every(name => hash.test(descriptor[name]))
        || JSON.stringify(descriptor.official_source_states) !== JSON.stringify(["HI", "WY"])
        || !Array.isArray(descriptor.changed_states)
        || descriptor.source_model_refitted !== false || descriptor.source_weights_changed !== false
        || descriptor.existing_17_behavioral_holds_preserved !== true
        || descriptor.official_HI_WY_scope_guarded !== true
        || descriptor.unchanged_state_numerics_and_complete_queries_reused !== true)
      throw new Error("Automatic House model gate, hold identity or official scope differs");
    for (const body of [descriptor.complete_result, descriptor.viewer_data]) {
      validateBodyPin(body);
      if (body.url !== new URL(body.path, sources.base_url.replace(/\/?$/, "/")).href)
        throw new Error("Automatic House selected body URL is not publication-bound");
    }
    const current = JSON.stringify([qualified, held, descriptor.qualification_mask_sha256,
      descriptor.hold_identity_sha256, descriptor.gate_identity_sha256,
      descriptor.official_source_guard_sha256]);
    identities ||= current;
    if (current !== identities) throw new Error("Automatic House controls do not share one qualification gate");
  }
  for (const profile of profiles) {
    const viewer = sources.profile_viewers[profile];
    if (viewer?.contract !== "participation.automatic_house_profile_viewer.v1"
        || viewer.profile !== profile
        || JSON.stringify(viewer.families) !== JSON.stringify(families)
        || JSON.stringify(viewer.control_keys) !==
          JSON.stringify(families.map(family => `${profile}/${family}`)))
      throw new Error("Automatic House profile viewer inventory differs");
    validateBodyPin(viewer.viewer_data);
    if (viewer.viewer_data.url !== new URL(viewer.viewer_data.path,
      sources.base_url.replace(/\/?$/, "/")).href)
      throw new Error("Automatic House profile viewer URL is not publication-bound");
  }
  if (sources.recorded_states?.contract !== "participation.automatic_recorded_house_states.v1")
    throw new Error("Automatic recorded House state contract differs");
  validateBodyPin(sources.recorded_states);
  validateBodyPin(sources.sensitivity);
  validateBodyPin(sources.participation_state_projections);
  if (sources.participation_state_projections.contract !==
      "participation.registered_control_display.v2")
    throw new Error("Automatic state participation projection contract differs");
  for (const body of [sources.recorded_states, sources.sensitivity,
    sources.participation_state_projections])
    if (body.url !== new URL(body.path, sources.base_url.replace(/\/?$/, "/")).href)
      throw new Error("Automatic House companion body URL is not publication-bound");
  if (sources.sensitivity.contract !== "participation.house_model_sensitivity.v1"
      || !sources.shared_max_abs_margin || Array.isArray(sources.shared_max_abs_margin)
      || typeof sources.shared_max_abs_margin !== "object"
      || Object.values(sources.shared_max_abs_margin)
        .some(value => typeof value !== "number" || !Number.isFinite(value) || value < 0))
    throw new Error("Automatic House sensitivity or shared scale differs");
  if (sources.complete_download?.required !== true
      || sources.complete_download.media_type !== "application/zip"
      || !pin(sources.complete_download)
      || !/^https:\/\/github\.com\/hanshanley\/margin_of_error\/releases\/download\/[^/]+\/[^/]+$/
        .test(sources.complete_download.url))
    throw new Error("Automatic House complete download is missing");
  const qualification=sources.qualification;
  if (qualification?.districts!==435 || qualification.candidate_inventory_rows!==1401
      || qualification.mask_sha256!==sources.descriptors["original/accepted_ridge_multinomial"].qualification_mask_sha256
      || qualification.hold_identity_sha256!==sources.descriptors["original/accepted_ridge_multinomial"].hold_identity_sha256
      || qualification.gate_identity_sha256!==sources.descriptors["original/accepted_ridge_multinomial"].gate_identity_sha256
      || qualification.official_source_guard_sha256!==
        sources.descriptors["original/accepted_ridge_multinomial"].official_source_guard_sha256
      || JSON.stringify(qualification.qualified_state_codes)!==
        JSON.stringify(sources.descriptors["original/accepted_ridge_multinomial"].qualified_state_codes)
      || JSON.stringify(qualification.held_state_codes)!==
        JSON.stringify(sources.descriptors["original/accepted_ridge_multinomial"].held_state_codes))
    throw new Error("Automatic House aggregate qualification differs");
  return base[1];
}

export function validateAutomaticRuntime(manifest) {
  if (manifest?.contract !== "participation.automatic_runtime.v1"
      || !hash.test(manifest.version) || !hash.test(manifest.input_results_version)
      || manifest.election_date !== "2026-11-03" || !text(manifest.processing_version)
      || !text(manifest.checked_at)
      || !/(?:Z|\+00:00)$/.test(manifest.checked_at)
      || !Number.isFinite(Date.parse(manifest.checked_at))
      || manifest.source_models_refitted !== false
      || manifest.geographic_joins_changed !== false
      || manifest.all_states_certified_or_precinct_complete !== false)
    throw new Error("Unknown automatic runtime manifest");
  validateCompleteDownload(manifest.complete_download);
  const commits = new Set();
  if (manifest.counts) commits.add(validateDatasetDescriptor(manifest.counts,
    "participation-counts-2026", "participation.count_snapshot.v1"));
  if (manifest.native) commits.add(validateDatasetDescriptor(manifest.native,
    "participation-native-bindings-2026", "participation.native_bindings.v1"));
  if (manifest.house_sources) {
    commits.add(validateAutomaticHouseSources(manifest.house_sources, manifest.version));
    if (manifest.complete_download.url !== manifest.house_sources.complete_download.url
        || manifest.complete_download.bytes !== manifest.house_sources.complete_download.bytes
        || manifest.complete_download.sha256 !== manifest.house_sources.complete_download.sha256)
      throw new Error("Automatic runtime and House complete download differ");
  }
  if (!manifest.counts && !manifest.native && !manifest.house_sources)
    throw new Error("Automatic runtime contains no consumable snapshot");
  if (commits.size !== 1)
    throw new Error("Automatic counts and House sources are not one committed snapshot");
  manifest.runtime_commit = [...commits][0];
  return manifest;
}

export function setAutomaticRuntimeStatus(component, state, detail, manifest=null) {
  runtimeStates.set(component, { state, detail, manifest });
  if (typeof document === "undefined") return;
  const failed = [...runtimeStates.values()].find(value => value.state === "error");
  const active = [...runtimeStates.values()].filter(value => value.state === "active");
  const checked = manifest || active.at(-1)?.manifest;
  const message = failed
    ? `Automatic update unavailable; accepted website sources retained. ${failed.detail}`
    : active.length
      ? `Automatic ${active.map(value => value.detail).join(" and ")} active`
        + `${checked?.checked_at ? ` · checked ${checked.checked_at}` : ""}.`
      : `Automatic update checked; accepted website sources retained. ${detail}`;
  for (const node of document.querySelectorAll("[data-automatic-runtime-status]")) {
    node.textContent = message;
    node.dataset.state = failed ? "error" : active.length ? "active" : state;
    if (checked?.version) node.dataset.version = checked.version;
  }
}

export function rejectAutomaticRuntime(component, error) {
  rejected.add(component);
  setAutomaticRuntimeStatus(component, "error", error?.message || String(error));
  if (typeof globalThis.dispatchEvent === "function" && typeof CustomEvent === "function")
    globalThis.dispatchEvent(new CustomEvent("participation:automatic-runtime-rejected",
      { detail: { component, error: error?.message || String(error) } }));
}

export function automaticRuntimeRejected(component) {
  return rejected.has(component);
}

export function resetAutomaticRuntimeForTests() {
  session.manifestPromise = null;
  rejected.clear();
  runtimeStates.clear();
  automaticBodies.clear();
}

export function loadAutomaticRuntime() {
  session.manifestPromise ||= (async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(automaticRuntimeURL, { cache: "no-cache", signal: controller.signal });
      if (!response.ok) throw new Error(`Automatic runtime: HTTP ${response.status}`);
      return validateAutomaticRuntime(await response.json());
    } finally {
      clearTimeout(timer);
    }
  })().catch(error => {
    session.manifestPromise = null;
    throw error;
  });
  return session.manifestPromise;
}

export async function automaticHouseSources(fallback) {
  if (automaticRuntimeRejected("house")) return { ...fallback, automatic: null };
  try {
    const manifest = await loadAutomaticRuntime();
    if (!manifest.house_sources) {
      setAutomaticRuntimeStatus("house", "fallback", "No automatic House descriptor was supplied.", manifest);
      return { ...fallback, automatic: null };
    }
    return { contract: manifest.house_sources, automatic: manifest, fallback };
  } catch (error) {
    rejectAutomaticRuntime("house", error);
    return { ...fallback, automatic: null };
  }
}

export function automaticHouseProfileReceipt(selection, profile) {
  const declaration = selection?.contract?.profile_viewers?.[profile]?.viewer_data;
  if (!selection?.automatic || !declaration) throw new Error("Missing automatic House profile viewer");
  return {
    url: declaration.url,
    bytes: declaration.bytes,
    sha256: declaration.sha256,
    compression: declaration.compression,
    media_type: declaration.media_type,
    decoded_bytes: declaration.decoded_bytes,
    decoded_sha256: declaration.decoded_sha256,
    contest_comparability_required: true,
    official_source_revision_required: true,
    automatic_profile: profile,
    automatic_runtime_version: selection.automatic.version,
    automatic_runtime_commit: selection.automatic.runtime_commit,
  };
}

export function automaticHouseDescriptor(selection, profile, family) {
  const key = selection?.contract?.controls?.[profile]?.[family];
  const descriptor = selection?.contract?.descriptors?.[key];
  if (!descriptor || descriptor.control_key !== key)
    throw new Error("Missing automatic House profile/family descriptor");
  return descriptor;
}

export function automaticHouseSensitivityReceipt(selection) {
  const value = selection?.contract?.sensitivity;
  if (!selection?.automatic || !value) throw new Error("Missing automatic House sensitivity");
  return {
    ...value,
    url: value.url,
    fitted_aggregate_projection_replay_only: true,
    source_fits_reproduced: false,
    automatic_runtime_version: selection.automatic.version,
    automatic_runtime_commit: selection.automatic.runtime_commit,
  };
}

async function checkedAutomaticBody(declaration) {
  const key = `${declaration.url}|${declaration.sha256}|${declaration.decoded_sha256}`;
  if (!automaticBodies.has(key)) {
    const promise = (async () => {
      const response = await fetch(declaration.url);
      if (!response.ok) throw new Error(`Automatic House body: HTTP ${response.status}`);
      const bytes = await response.arrayBuffer();
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
        value => value.toString(16).padStart(2, "0")).join("");
      if (bytes.byteLength !== declaration.bytes || digest !== declaration.sha256)
        throw new Error("Automatic House body checksum mismatch");
      const decoded = await new Response(new Blob([bytes]).stream()
        .pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
      const decodedDigest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", decoded)),
        value => value.toString(16).padStart(2, "0")).join("");
      if (decoded.byteLength !== declaration.decoded_bytes
          || decodedDigest !== declaration.decoded_sha256)
        throw new Error("Automatic House decoded checksum mismatch");
      return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(decoded));
    })().catch(error => {
      if (automaticBodies.get(key) === promise) automaticBodies.delete(key);
      throw error;
    });
    automaticBodies.set(key, promise);
  }
  return automaticBodies.get(key);
}

export async function loadAutomaticRecordedHouse(selection) {
  const data = await checkedAutomaticBody(selection.contract.recorded_states);
  if (data?.contract !== "participation.automatic_recorded_house_states.v1"
      || data.election_date !== "2026-11-03" || !Array.isArray(data.states)
      || data.states.length !== 50
      || new Set(data.states.map(row => row.state_code)).size !== 50)
    throw new Error("Automatic recorded House state inventory differs");
  return data;
}

export async function loadAutomaticRegisteredControlDisplay() {
  const manifest=await loadAutomaticRuntime();
  const declaration=manifest.house_sources?.participation_state_projections;
  if (!declaration) throw new Error("Missing automatic registered-control display");
  const data=await checkedAutomaticBody(declaration);
  if (data?.contract!=="participation.registered_control_display.v2"
      || data.year!==2026 || data.native_control_version!==35
      || !Array.isArray(data.states) || data.states.length!==51
      || !Array.isArray(data.scenarios) || data.scenarios.length!==34)
    throw new Error("Automatic registered-control display contract differs");
  return {data,manifest,declaration};
}

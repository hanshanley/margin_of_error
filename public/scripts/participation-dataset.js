import { automaticRuntimeRejected, loadAutomaticRuntime, rejectAutomaticRuntime,
  setAutomaticRuntimeStatus } from "./participation-automatic-runtime.js";

export const datasetCatalogURL = "https://raw.githubusercontent.com/hanshanley/margin_of_error/participation-data/catalog.json";
const hash = /^[a-f0-9]{64}$/;
const immutableBase = /^https:\/\/raw\.githubusercontent\.com\/hanshanley\/margin_of_error\/[a-f0-9]{40}\//;

export async function checkedDatasetFile(base, declaration) {
  if (!immutableBase.test(base) || !declaration
      || !Number.isSafeInteger(declaration.bytes) || declaration.bytes < 1
      || !hash.test(declaration.sha256) || typeof declaration.file !== "string"
      || !/^[A-Za-z0-9_/-]+\.(json|json\.gz)$/.test(declaration.file)
      || declaration.file.startsWith("/") || declaration.file.split("/").includes(".."))
    throw new Error("Unqualified immutable dataset declaration");
  const response = await fetch(new URL(declaration.file, base));
  if (!response.ok) throw new Error(`Dataset: HTTP ${response.status}`);
  const body = await response.arrayBuffer();
  const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))]
    .map(value => value.toString(16).padStart(2, "0")).join("");
  if (body.byteLength !== declaration.bytes || digest !== declaration.sha256)
    throw new Error("Dataset checksum differs; no values substituted");
  if (!declaration.file.endsWith(".gz")) return JSON.parse(new TextDecoder().decode(body));
  if (!globalThis.DecompressionStream)
    throw new Error("Compressed datasets are unsupported; use the complete download");
  return new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream("gzip"))).json();
}

export function validateCatalog(catalog) {
  if (catalog?.contract !== "participation.dataset_catalog.v1" || !catalog.datasets
      || Array.isArray(catalog.datasets) || typeof catalog.datasets !== "object")
    throw new Error("Unknown data catalog contract");
  for (const [id, entry] of Object.entries(catalog.datasets)) {
    if (entry?.contract !== "participation.dataset.v1" || entry.id !== id || !entry.status)
      throw new Error("Invalid dataset identity");
    if (entry.status !== "loaded") continue;
    if (!hash.test(entry.version) || !entry.index || !immutableBase.test(entry.base_url)
        || entry.complete_download?.verified_anonymously !== true
        || entry.complete_download?.immutable !== true
        || !hash.test(entry.complete_download.sha256))
      throw new Error("Incomplete or unverified dataset catalog entry");
  }
  return catalog;
}

let catalogPromise;
export function loadDatasetCatalog() {
  catalogPromise ||= fetch(datasetCatalogURL, { cache: "no-cache" }).then(response => {
    if (!response.ok) throw new Error(`Data catalog: HTTP ${response.status}`);
    return response.json();
  }).then(validateCatalog).catch(error => { catalogPromise = null; throw error; });
  return catalogPromise;
}

async function loadEntry(entry, automatic_runtime=null) {
  return { entry, index: await checkedDatasetFile(entry.base_url, entry.index), automatic_runtime };
}

export async function loadDataset(id, { automatic=true }={}) {
  const catalog = await loadDatasetCatalog(), entry = catalog.datasets[id];
  if (!entry || entry.status !== "loaded") throw new Error("This dataset is awaiting publication");
  const runtimeKey = id === "participation-counts-2026" ? "counts"
    : id === "participation-native-bindings-2026" ? "native" : null;
  if (!runtimeKey || !automatic || automaticRuntimeRejected("counts"))
    return loadEntry(entry);
  try {
    const manifest = await loadAutomaticRuntime();
    if (!manifest[runtimeKey]) {
      setAutomaticRuntimeStatus("counts", "fallback",
        `No automatic ${runtimeKey} descriptor was supplied.`, manifest);
      return loadEntry(entry);
    }
    return await loadEntry(manifest[runtimeKey], manifest);
  } catch (error) {
    rejectAutomaticRuntime("counts", error);
    return loadEntry(entry);
  }
}

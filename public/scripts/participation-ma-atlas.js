const repo = "https://raw.githubusercontent.com/hanshanley/voter-participation/";
const latest = `${repo}ma-historical-data/latest.json`;

export function atlasDownload(pointer) {
  const { version, complete_download: zip } = pointer ?? {};
  if (pointer?.contract !== "participation.massachusetts_historical_atlas.v1"
      || JSON.stringify(pointer.years) !== "[2020,2022,2024]"
      || typeof version !== "string" || !/^[a-f0-9]{64}$/.test(version)
      || zip?.sha256 !== version || zip.verified_anonymously !== true
      || zip.media_type !== "application/zip" || !Number.isSafeInteger(zip.bytes)
      || zip.bytes < 1 || zip.bytes > 90_000_000
      || typeof zip.url !== "string")
    throw new Error("Unverified Massachusetts atlas pointer");
  const commit = zip.url.slice(repo.length, repo.length + 40);
  if (!/^[a-f0-9]{40}$/.test(commit)
      || zip.url !== `${repo}${commit}/versions/${version}/complete-analysis.zip`)
    throw new Error("Massachusetts atlas download is not pinned to its publication commit");
  return zip.url;
}

export function installAtlasDownload(panel) {
  const link = panel.querySelector("[data-ma-atlas-download]");
  const status = panel.querySelector("[data-ma-atlas-status]");
  let loading = false;
  const update = async () => {
    if (!panel.open || loading) return;
    loading = true;
    try {
      const response = await fetch(latest, { cache: "no-cache", signal: AbortSignal.timeout(8000) });
      if (!response.ok) throw new Error("Massachusetts atlas unavailable");
      link.href = atlasDownload(await response.json());
      link.hidden = false;
      status.textContent = "";
    } catch {
      status.textContent = link.hidden
        ? "The latest atlas could not be verified. The fixed archives below are still available."
        : "The latest check failed. Showing the last verified atlas link.";
    } finally {
      loading = false;
    }
  };
  panel.addEventListener("toggle", update);
  if (panel.open) update();
}

if (typeof document !== "undefined") {
  const panel = document.getElementById("historical-massachusetts-maps");
  if (panel) installAtlasDownload(panel);
}

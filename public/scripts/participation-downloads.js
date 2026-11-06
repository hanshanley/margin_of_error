export const participationRelease = "voter-participation-data-20261104";
export const participationReleaseRoot = `https://github.com/hanshanley/margin_of_error/releases/download/${participationRelease}/`;
export const participationCurrentRoot = "https://raw.githubusercontent.com/hanshanley/margin_of_error/dc81c095cec959910c6dfb82da8c9184d7a993f9/public/participation-current/";
export const participationHistoricalRoot = "https://raw.githubusercontent.com/hanshanley/voter-participation/792e3d91609f7ee929c35b5ec15c13710db94be8/public/data/nc/";
export const participationCountyContextRoots = {
  "20261106-12": "https://raw.githubusercontent.com/hanshanley/margin_of_error/efd750acd9aa1b021b7de9c24b42b8aeecc32e1a/public/participation-county-context/20261106-12/",
  "20261106-13": "https://raw.githubusercontent.com/hanshanley/margin_of_error/70c141f45dae29980f2871a300934688035a2177/public/participation-county-context/20261106-13/",
  "20261106-14": "https://raw.githubusercontent.com/hanshanley/margin_of_error/5d2e25f80be9f9361cc37a4131eb274323c42e75/public/participation-county-context/20261106-14/",
  "20261106-15": "https://raw.githubusercontent.com/hanshanley/margin_of_error/635697084ec43e996662eb5efe55d154fe187405/public/participation-county-context/20261106-15/",
};

export function participationDownload(path) {
  const contextArchive = /^\/participation-county-context\/(20261106-(0[1-9]|1[0-5]))\/complete-county-participation-context-\2\.zip$/.exec(path);
  if (contextArchive)
    return `https://github.com/hanshanley/margin_of_error/releases/download/voter-county-participation-context-${contextArchive[1]}/complete-county-participation-context-${contextArchive[2]}.zip`;
  const contextGeometry = /^\/participation-county-context\/(20261106-1[34])\/(geometry\/county-(?:AL|AR|AZ|CA|DC|FL|GA|IA|KY|MO|NJ|NV|OR|PA|VA|WA|WY)\.geojson)$/.exec(path)
    || /^\/participation-county-context\/(20261106-12)\/(geometry\/county-(?:AL|AR|AZ|CA|DC|FL|IA|KY|MO|NJ|NV|OR|PA|VA|WA|WY)\.geojson)$/.exec(path)
    || /^\/participation-county-context\/(20261106-15)\/(geometry\/county-(?:AL|AR|AZ|CA|DC|FL|GA|IA|KY|MN|MO|NJ|NV|OR|PA|VA|WA|WY)\.geojson)$/.exec(path);
  if (contextGeometry) return participationCountyContextRoots[contextGeometry[1]] + contextGeometry[2];
  if (/^\/voter-participation\/data\/nc\/\d{4}\.json$/.test(path))
    return participationHistoricalRoot + path.split("/").at(-1);
  if (path.startsWith("/participation-current/20261104T220424Z/") && /\.(csv|zip|json)$/.test(path))
    return participationCurrentRoot + path.slice("/participation-current/".length);
  if (!/^\/(?:voter-participation\/data|participation-context|participation-methods)\//.test(path)
    || !(/\.(csv|zip)$/.test(path) || /\/jurisdictions-\d{4}\.json$/.test(path))) return path;
  return participationReleaseRoot + path.slice(1).replaceAll("/", "__");
}

export function installParticipationDownloads(root) {
  const rewrite = () => {
    for (const link of root.querySelectorAll("a[download]")) {
      const path = link.getAttribute("href");
      const url = participationDownload(path);
      if (url !== path) link.setAttribute("href", url);
    }
  };
  rewrite();
  new MutationObserver(rewrite).observe(root, {
    subtree: true, childList: true, attributes: true, attributeFilter: ["href"],
  });
}

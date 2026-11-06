export const participationRelease = "voter-participation-data-20261104";
export const participationReleaseRoot = `https://github.com/hanshanley/margin_of_error/releases/download/${participationRelease}/`;
export const participationCurrentRoot = "https://raw.githubusercontent.com/hanshanley/margin_of_error/dc81c095cec959910c6dfb82da8c9184d7a993f9/public/participation-current/";
export const participationHistoricalRoot = "https://raw.githubusercontent.com/hanshanley/voter-participation/792e3d91609f7ee929c35b5ec15c13710db94be8/public/data/nc/";
export const participationCountyContextRoots = {
  "20261106-10": "https://raw.githubusercontent.com/hanshanley/margin_of_error/47a0efe3e75e9498d89340a7c50e3b311f55c5dc/public/participation-county-context/20261106-10/",
  "20261106-11": "https://raw.githubusercontent.com/hanshanley/margin_of_error/784d261600f349073d3cf74ba8d168595cf6a46e/public/participation-county-context/20261106-11/",
  "20261106-12": "https://raw.githubusercontent.com/hanshanley/margin_of_error/efd750acd9aa1b021b7de9c24b42b8aeecc32e1a/public/participation-county-context/20261106-12/",
  "20261106-13": "https://raw.githubusercontent.com/hanshanley/margin_of_error/70c141f45dae29980f2871a300934688035a2177/public/participation-county-context/20261106-13/",
  "20261106-14": "https://raw.githubusercontent.com/hanshanley/margin_of_error/5d2e25f80be9f9361cc37a4131eb274323c42e75/public/participation-county-context/20261106-14/",
  "20261106-15": "https://raw.githubusercontent.com/hanshanley/margin_of_error/635697084ec43e996662eb5efe55d154fe187405/public/participation-county-context/20261106-15/",
  "20261106-16": "https://raw.githubusercontent.com/hanshanley/margin_of_error/833c309f83efa6280eb9a5cfee7a17b2faff4211/public/participation-county-context/20261106-16/",
  "20261106-17": "https://raw.githubusercontent.com/hanshanley/margin_of_error/62f1665b3cfec842e89682537ee288ee6cf1dce6/public/participation-county-context/20261106-17/",
  "20261106-18": "https://raw.githubusercontent.com/hanshanley/margin_of_error/b3d8eb533a5ade421f569c62db9b8a7d8c4a6220/public/participation-county-context/20261106-18/",
  "20261106-19": "https://raw.githubusercontent.com/hanshanley/margin_of_error/de77fd199364c95f4459cc4ba00d09500cc5843d/public/participation-county-context/20261106-19/",
  "20261106-20": "https://raw.githubusercontent.com/hanshanley/margin_of_error/7ad830f70be4a8eb47d9c95896c9c99985228467/public/participation-county-context/20261106-20/",
  "20261106-21": "https://raw.githubusercontent.com/hanshanley/margin_of_error/ed629325b3c70256304c06221228247dc92ab426/public/participation-county-context/20261106-21/",
  "20261106-22": "https://raw.githubusercontent.com/hanshanley/margin_of_error/4f8c93d70a6d405519789ee4c5f7a631749e3829/public/participation-county-context/20261106-22/",
  "20261106-23": "https://raw.githubusercontent.com/hanshanley/margin_of_error/e32e64f6a5301d10df1bd72974975bc0f8cd3749/public/participation-county-context/20261106-23/",
};

export function participationDownload(path) {
  const contextArchive = /^\/participation-county-context\/(20261106-(0[1-9]|1[0-9]|2[0123]))\/complete-county-participation-context-\2\.zip$/.exec(path);
  if (contextArchive)
    return `https://github.com/hanshanley/margin_of_error/releases/download/voter-county-participation-context-${contextArchive[1]}/complete-county-participation-context-${contextArchive[2]}.zip`;
  const contextGeometry = /^\/participation-county-context\/(20261106-23)\/(geometry\/county-(?:AL|AR|AZ|CA|DC|FL|GA|IA|KY|MN|MO|NJ|NV|OR|PA|UT|VA|WA|WY)\.geojson)$/.exec(path)
    || /^\/participation-county-context\/(20261106-1[34])\/(geometry\/county-(?:AL|AR|AZ|CA|DC|FL|GA|IA|KY|MO|NJ|NV|OR|PA|VA|WA|WY)\.geojson)$/.exec(path)
    || /^\/participation-county-context\/(20261106-1[012])\/(geometry\/county-(?:AL|AR|AZ|CA|DC|FL|IA|KY|MO|NJ|NV|OR|PA|VA|WA|WY)\.geojson)$/.exec(path)
    || /^\/participation-county-context\/(20261106-(?:1[56789]|2[012]))\/(geometry\/county-(?:AL|AR|AZ|CA|DC|FL|GA|IA|KY|MN|MO|NJ|NV|OR|PA|VA|WA|WY)\.geojson)$/.exec(path);
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

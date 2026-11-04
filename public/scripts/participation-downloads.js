export const participationRelease = "voter-participation-data-20261104";
export const participationReleaseRoot = `https://github.com/hanshanley/margin_of_error/releases/download/${participationRelease}/`;

export function participationDownload(path) {
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

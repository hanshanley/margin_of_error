export function isParticipationArchiveLink(href, download = false) {
  if (download) return true;
  const path = (href || "").split(/[?#]/, 1)[0];
  if (/\.(?:zip|tgz|tar\.gz|7z)$/i.test(path)) return true;
  if (/^\/(?:voter-participation\/data|participation-[^/]+)\//i.test(path))
    return /\.(?:csv|tsv|json|zip|gz|xlsx?|txt|geojson|pdf)$/i.test(path);
  if (/^\/participation-downloads\.json$/i.test(path)) return true;
  return /^https:\/\/(?:github\.com|raw\.githubusercontent\.com)\/hanshanley\/(?:voter-participation|margin_of_error)\//i.test(path)
    && (/\/releases\/download\//.test(path) || /\.(?:csv|tsv|json|zip|gz|xlsx?|txt|geojson|pdf)$/i.test(path));
}

export function removeParticipationArchiveLinks(root) {
  for (const link of root.querySelectorAll("a[href], a[download]")) {
    if (isParticipationArchiveLink(link.getAttribute("href"), link.hasAttribute("download")))
      link.remove();
  }
  for (const group of root.querySelectorAll(".download-links"))
    if (!group.querySelector("a") && group.textContent) group.replaceChildren();
}

export function installParticipationPublicationUI(root) {
  if (!root) return;
  const clean = () => removeParticipationArchiveLinks(root);
  clean();
  new MutationObserver(clean).observe(root, {
    subtree: true, childList: true, attributes: true, attributeFilter: ["href", "download"],
  });
}

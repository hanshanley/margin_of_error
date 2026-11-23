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

export function organizeStateDetails(panel) {
  const basis = panel.querySelector(":scope > .selection-basis");
  if (!basis) return;
  const extra = panel.ownerDocument.createElement("details");
  extra.className = "selection-more";
  const heading = panel.ownerDocument.createElement("summary");
  heading.textContent = "Details and local data";
  extra.append(heading);
  while (basis.nextSibling) extra.append(basis.nextSibling);
  panel.append(extra);
}

export function installComparisonSummary(panel) {
  if (!panel) return;
  const organize = () => {
    const heading = panel.querySelector(":scope > h3");
    if (!heading || panel.querySelector(":scope > .comparison-more") || panel.children.length < 2) return;
    const notes = panel.ownerDocument.createElement("details");
    notes.className = "comparison-more";
    const title = panel.ownerDocument.createElement("summary");
    title.textContent = "Comparison details";
    notes.append(title);
    const primary = panel.querySelector(":scope > .driver-equation, :scope > .driver-recorded-endpoints, :scope > .table-wrap");
    while (heading.nextSibling) notes.append(heading.nextSibling);
    if (primary) panel.append(primary);
    else {
      const state = panel.ownerDocument.createElement("p");
      state.className = "comparison-qualification";
      state.textContent = panel.dataset.norcHold === "true" || /not comparable|unavailable/.test(heading.textContent)
        ? "No like-for-like comparison is available in this view." : "See details for the source frame and qualifications.";
      panel.append(state);
    }
    panel.append(notes);
  };
  new MutationObserver(organize).observe(panel, { childList: true });
  organize();
}

export function installParticipationPublicationUI(root) {
  if (!root) return;
  const clean = () => removeParticipationArchiveLinks(root);
  clean();
  new MutationObserver(clean).observe(root, {
    subtree: true, childList: true, attributes: true, attributeFilter: ["href", "download"],
  });
}

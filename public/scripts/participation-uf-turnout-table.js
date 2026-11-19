const formatNumber = new Intl.NumberFormat("en-US");
const number = value => value == null ? "Not reported" : formatNumber.format(value);
const rate = value => value == null ? "Not reported" : `${value.toFixed(2)}%`;

export function updateUfTurnoutTable(section, edition, rows) {
  const table = section?.querySelector('table[data-uf-turnout="2026"]');
  const tbody = table?.tBodies[0];
  const label = section?.querySelector("[data-uf-edition]");
  const downloads = section?.querySelector("[data-uf-edition-downloads]");
  if (!tbody || !label || !downloads) return;

  const doc = section.ownerDocument;
  const rendered = rows.map(row => {
    const tr = doc.createElement("tr");
    for (const [key, value] of Object.entries({
      stateCode: row.state_code, ballots: row.ballots, vep: row.vep, vap: row.vap,
      vepRate: row.vep_rate, vapRate: row.vap_rate, sourceStatus: row.source_status,
      ballotsStatus: row.ballots_status,
    })) tr.dataset[key] = value ?? "";
    const th = doc.createElement("th");
    th.scope = "row";
    th.textContent = row.state;
    tr.append(th);
    for (const value of [number(row.ballots), row.source_status, number(row.vep),
      rate(row.vep_rate), rate(row.vap_rate)]) {
      const td = doc.createElement("td");
      td.textContent = value;
      tr.append(td);
    }
    return tr;
  });
  tbody.replaceChildren(...rendered);
  const estimates = rows.filter(row => row.ballots_status === "estimate").length;
  const retained = edition.status === "retained_after_failure" ? "Last verified edition retained after a source failure. " : "";
  label.textContent = `${retained}UF version ${edition.version}; first observed ${edition.first_observed_at}. `
    + `The publisher does not supply a count-update time. ${estimates} of ${rows.length} rows use estimated counts.`;
  table.dataset.sourceVersion = edition.version;
  downloads.replaceChildren();
  for (const [url, title] of [
    [edition.source.url, "Source-edition CSV"],
    [edition.complete_download?.url, "Complete data and offline reproduction"],
  ]) {
    if (!url) continue;
    const link = doc.createElement("a");
    link.href = url;
    link.textContent = title;
    if (downloads.childNodes.length) downloads.append(" · ");
    downloads.append(link);
  }
  downloads.hidden = false;
}

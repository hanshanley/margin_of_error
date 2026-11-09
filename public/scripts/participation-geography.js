export function countFill(value, maximum) {
  if (!Number.isFinite(value) || value < 0) return "#edf0f3";
  const t = maximum > 0 ? Math.sqrt(Math.min(1, value / maximum)) : 0;
  return `rgb(${[218, 230, 241].map((c, i) =>
    Math.round(c + t * ([40, 71, 102][i] - c))).join(",")})`;
}

export function precinctSelectionYears(loaded, requested, electionYears) {
  const years = new Set([...loaded, 2026]);
  const year = Number(requested);
  if (electionYears.includes(year)) years.add(year);
  return [...years].sort((a, b) => b - a);
}

export function qualifiedDcPrecinctParticipation(p, year) {
  const row = p.participation;
  return year === 2026 && p.year === year && p.state_code === "DC"
    && p.county_code === "11001" && p.match_status === "matched"
    && p.source_contest_id === "6"
    && p.key === `DC|11001|${p.precinct_code}|${p.source_contest_id}`
    && row?.key === p.key && row.year === year && row.state_code === "DC"
    && row.precinct === p.precinct_code && row.measure === "reported_ballots_and_registration"
    && Number.isSafeInteger(row.ballots) && row.ballots >= 0
    && Number.isSafeInteger(row.registered) && row.registered > 0 && row.ballots <= row.registered
    && Number.isFinite(row.reported_pct)
    && Math.abs(row.reported_pct - 100 * row.ballots / row.registered) < 1e-10;
}

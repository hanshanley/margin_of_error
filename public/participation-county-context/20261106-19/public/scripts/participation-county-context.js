export function canonicalJson(value) {
  const sort = item => Array.isArray(item) ? item.map(sort)
    : item !== null && typeof item === "object"
      ? Object.fromEntries(Object.keys(item).sort().map(key => [key, sort(item[key])])) : item;
  return JSON.stringify(sort(value));
}

export async function jsonDigest(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalJson(value)));
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}

export async function contextualCountyRows(rows, review, collection, code, contextPath, file) {
  const geometry = review?.geometry?.[code];
  if (!geometry || contextPath !== review.context_base_url || file !== geometry.file
    || await jsonDigest(collection) !== geometry.canonical_sha256) return new Map();
  const joins = review.observations.filter(row => row.state_code === code);
  const sourceKeys = new Set(), geographicKeys = new Set();
  for (const join of joins) {
    if (sourceKeys.has(join.county_id) || geographicKeys.has(join.contextual_geoid)) return new Map();
    sourceKeys.add(join.county_id); geographicKeys.add(join.contextual_geoid);
  }
  const matches = new Map(), duplicates = new Set();
  for (const row of rows) {
    const join = joins.find(item => item.county_id === row.county_id);
    if (!join || row.state_code !== code || row.year !== 2026 || row.ballots === null
      || !["county", "county_equivalent", "independent_city"].includes(row.geography_level)
      || await jsonDigest(row) !== join.source_record_sha256) continue;
    if (matches.has(join.contextual_geoid)) duplicates.add(join.contextual_geoid);
    matches.set(join.contextual_geoid, row);
  }
  for (const key of duplicates) matches.delete(key);
  return matches;
}

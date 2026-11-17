const contract = "participation.county_candidate_subsets.v1";
const integer = value => Number.isSafeInteger(value) && value >= 0;
const same = (left, right) => left.length === right.length && left.every((v, i) => v === right[i]);
const close = (left, right) => Number.isFinite(left) && Math.abs(left - right) < 1e-10;
const clock = value => typeof value === "string" && value.endsWith("Z") && Number.isFinite(Date.parse(value));
const fail = () => { throw new Error("Unqualified county candidate-subset evidence"); };

export function subsetMarginLabel(row) {
  const bounds = row.margin_bounds_pp;
  if (!bounds) return "Margin unavailable";
  const side = bounds[0] >= 0 ? "D+" : bounds[1] <= 0 ? "R+" : "";
  const values = bounds.map(Math.abs).sort((a, b) => a - b);
  return row.complete_vector_qualified ? `${side}${values[0].toFixed(2)} pp`
    : `${side}${(Math.floor(values[0] * 100) / 100).toFixed(2)}–${(Math.ceil(values[1] * 100) / 100).toFixed(2)} pp`;
}

export function subsetColorValue(row) {
  const bounds = row.margin_bounds_pp;
  return !bounds ? null : bounds[0] > 0 ? bounds[0] : bounds[1] < 0 ? bounds[1] : 0;
}

export function validateCountySubsets(data, scope) {
  if (data?.contract !== contract || data.year !== scope.year || data.state_code !== scope.state_code
    || data.state_fips !== scope.state_fips || data.office !== "U.S. House" || data.stage !== "General"
    || data.source_round !== 1 || data.boundary_reference_year !== data.year
    || data.freshness !== "retained_historical_observation" || data.complete_state_vector_qualified !== false
    || data.participation_qualified !== false || data.swing_qualified !== false || data.model_update_qualified !== false
    || !integer(data.unlocated_other_votes) || !Array.isArray(data.rows) || data.rows.length !== scope.counties
    || !Array.isArray(data.district_decisions) || !data.district_decisions.length) fail();
  const decisions = new Map(), expectedFragments = new Map();
  let unlocated = 0;
  for (const decision of data.district_decisions) {
    if (!new RegExp(`^${scope.state_code}-\\d{2}$`).test(decision.district)
      || decisions.has(decision.district) || !clock(decision.source_updated_at)
      || decision.source_round !== 1 || !Array.isArray(decision.candidate_decisions)
      || !/^https:\/\/civicapi\.org\/api\/v2\/race\/\d+$/.test(decision.source_url)
      || !/^[a-f0-9]{64}$/.test(decision.source_sha256)) fail();
    const candidates = decision.candidate_decisions;
    if (new Set(candidates.map(c => c.candidate_id)).size !== candidates.length
      || candidates.filter(c => c.role === "D").length !== 1 || candidates.filter(c => c.role === "R").length !== 1
      || new Set(candidates.map(c => JSON.stringify([c.name, c.party]))).size !== candidates.length) fail();
    let missing = 0;
    for (const c of candidates) {
      if (!integer(c.candidate_id) || !c.name || !integer(c.district_votes)
        || !integer(c.located_county_votes) || !integer(c.unlocated_votes)
        || c.district_votes !== c.located_county_votes + c.unlocated_votes
        || !(c.role === "D" && c.party === "Democratic" && c.unlocated_votes === 0
          || c.role === "R" && c.party === "Republican" && c.unlocated_votes === 0
          || c.role === "unallocated_other" && c.party === "Nonpartisan" && c.name === "Write-in")) fail();
      missing += c.unlocated_votes;
    }
    if (!integer(missing) || decision.complete_vector_qualified !== (missing === 0)) fail();
    decisions.set(decision.district, { ...decision, missing });
    expectedFragments.set(decision.district, new Map(candidates.map(c => [JSON.stringify([c.name, c.party]), 0])));
    unlocated += missing;
  }
  if (unlocated !== data.unlocated_other_votes || !Array.isArray(scope.county_ids)
    || new Set(scope.county_ids).size !== scope.county_ids.length
    || !same([...scope.county_ids].sort(), data.rows.map(row => row.geography).sort())) fail();
  for (const row of data.rows) {
    if (!/^\d{5}$/.test(row.geography) || !row.geography.startsWith(scope.state_fips)
      || row.state_code !== data.state_code || row.year !== data.year || row.level !== "county"
      || !row.geography_name || row.office !== data.office || row.stage !== data.stage || row.source_round !== 1
      || row.freshness !== data.freshness || !Array.isArray(row.district_fragments) || !row.district_fragments.length) fail();
    let dem = 0, rep = 0, other = 0, upper = 0;
    const districts = new Set();
    for (const fragment of row.district_fragments) {
      const decision = decisions.get(fragment.district);
      if (!decision || districts.has(fragment.district) || fragment.geography !== row.geography
        || fragment.source_url !== decision.source_url || fragment.source_sha256 !== decision.source_sha256
        || fragment.source_updated_at !== decision.source_updated_at || fragment.source_round !== 1
        || fragment.unlocated_other_upper_bound !== decision.missing || !Array.isArray(fragment.candidates)
        || fragment.candidates.length !== decision.candidate_decisions.length) fail();
      districts.add(fragment.district);
      const seen = new Set();
      for (const c of fragment.candidates) {
        const key = JSON.stringify([c.name, c.party]);
        const totals = expectedFragments.get(fragment.district);
        if (seen.has(key) || !totals.has(key) || !integer(c.votes)) fail();
        seen.add(key); totals.set(key, totals.get(key) + c.votes);
        if (c.party === "Democratic") dem += c.votes;
        else if (c.party === "Republican") rep += c.votes;
        else other += c.votes;
      }
      upper += decision.missing;
    }
    const total = dem + rep + other;
    if (![dem, rep, other, upper, total + upper].every(integer)
      || row.democratic_votes !== dem || row.republican_votes !== rep || row.located_other_votes !== other
      || row.known_candidate_votes !== total || row.unlocated_other_upper_bound !== upper
      || row.complete_vector_qualified !== (upper === 0)
      || row.other_votes !== (upper ? null : other) || row.contest_votes !== (upper ? null : total)) fail();
    const bounds = total ? [100 * (dem - rep) / total, 100 * (dem - rep) / (total + upper)].sort((a, b) => a - b) : null;
    if (bounds ? !Array.isArray(row.margin_bounds_pp) || row.margin_bounds_pp.length !== 2
      || !bounds.every((value, i) => close(row.margin_bounds_pp[i], value))
      : row.margin_bounds_pp !== null) fail();
    if (upper || !bounds ? row.margin_pp !== null : !close(row.margin_pp, bounds[0])) fail();
  }
  for (const [district, decision] of decisions) {
    for (const c of decision.candidate_decisions)
      if (expectedFragments.get(district).get(JSON.stringify([c.name, c.party])) !== c.located_county_votes) fail();
  }
  if (data.geometry?.type !== "FeatureCollection" || !Array.isArray(data.geometry.features)
    || data.geometry.features.length !== scope.counties
    || !same(data.geometry.features.map(f => f.properties?.key).sort(), [...scope.county_ids].sort())) fail();
  for (const f of data.geometry.features) {
    const p = f.properties, row = data.rows.find(r => r.geography === p.key);
    if (f.type !== "Feature" || p.state_code !== data.state_code || p.boundary_year !== data.year
      || p.name !== row.geography_name || !["Polygon", "MultiPolygon"].includes(f.geometry?.type)) fail();
    const polygons = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    if (!Array.isArray(polygons) || !polygons.length) fail();
    for (const polygon of polygons) {
      if (!Array.isArray(polygon) || !polygon.length) fail();
      for (const ring of polygon) {
        if (!Array.isArray(ring) || ring.length < 4 || ring.some(point =>
          !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)
          || Math.abs(point[0]) > 180 || Math.abs(point[1]) > 90)
          || !same(ring[0], ring.at(-1))) fail();
      }
    }
  }
  return data;
}

export async function loadCountySubsets(descriptor, scope, request = globalThis.fetch) {
  if (!descriptor || !/^https:\/\//.test(descriptor.url || "") || !/^[a-f0-9]{64}$/.test(descriptor.sha256 || "")
    || !integer(descriptor.bytes) || descriptor.bytes > 15000000
    || !/^https:\/\//.test(descriptor.complete_download_url || "")
    || !/^https:\/\//.test(descriptor.csv_url || "")) fail();
  const response = await request(descriptor.url);
  if (!response.ok) throw new Error(`County candidate subset: HTTP ${response.status}`);
  const body = new Uint8Array(await response.arrayBuffer());
  const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))]
    .map(value => value.toString(16).padStart(2, "0")).join("");
  if (body.length !== descriptor.bytes || digest !== descriptor.sha256 || body[0] !== 31 || body[1] !== 139) fail();
  const data = await new Response(new Blob([body]).stream().pipeThrough(new DecompressionStream("gzip"))).json();
  return validateCountySubsets(data, scope);
}

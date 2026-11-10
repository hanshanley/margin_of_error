import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const VERSION = 'data/county-source-reviews/20261110-maine-locality-activity-01';
const key = value => value.normalize('NFKD').toLowerCase().replace(/[^a-z0-9]/g, '');
const sourceKey = value => key(value.replace(/ (?:Twp|Plt)$/, ''));
const digest = value => createHash('sha256').update(value).digest('hex');
const count = value => {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Invalid Maine activity count; missing is not zero');
  return value;
};
const total = categories => {
  if (!categories || typeof categories !== 'object' || Array.isArray(categories) || !Object.keys(categories).length)
    throw new Error('Missing Maine source categories are not zero');
  return Object.values(categories).reduce((sum, row) => count(sum + count(row.votes)), 0);
};
const grouped = (rows, label) => {
  const result = new Map();
  for (const row of rows) {
    const name = label(row);
    if (!result.has(name)) result.set(name, []);
    result.get(name).push(row);
  }
  return result;
};

export function reviewMaineLocalityActivity({ inputs, sources, original, historical }) {
  if (inputs.state_code !== 'ME' || inputs.collector_election_year !== 2026
    || inputs.native_election_id_qualified !== false || inputs.rates_approved !== false
    || inputs.reference.boundary_year !== 2024 || inputs.reference.localities !== 528
    || original.features.length !== 528
    || new Set(original.features.map(f => f.properties.key)).size !== 528
    || original.features.some(f => f.properties.state_code !== 'ME'
      || f.properties.boundary_year !== 2024 || f.properties.level !== 'municipality'))
    throw new Error('Unqualified Maine collector context or full older locality reference');
  const byId = new Map(original.features.map(f => [f.properties.key, f]));
  const byName = grouped(original.features, f => key(f.properties.name));
  const historicalKeys = new Map();
  for (const row of historical.filter(r => r.year === 2024 && r.geography?.level === 'municipality'
    && byId.has(r.geography.key) && !r.statewide_unit && !r.supplemental_unit
    && sourceKey(r.jurisdiction) === key(byId.get(r.geography.key).properties.name))) {
    const name = key(row.jurisdiction);
    if (!historicalKeys.has(name)) historicalKeys.set(name, new Set());
    historicalKeys.get(name).add(row.geography.key);
  }
  const frames = {}, queries = [], referenceQueries = [], frameQueries = [];
  for (const [mode, category] of [['in_person_early', 'inperson'], ['mail_returned', 'returned']]) {
    const source = sources[category], native = source.native;
    if (native.state !== 'ME' || native.category !== category || !/^2026-\d{2}-\d{2}$/.test(native.snapshot_date)
      || typeof native.election_name !== 'string' || source.receipt.http_status !== 200
      || Object.keys(native.regions).length !== 584)
      throw new Error('Changed Maine native source identity, frame or context');
    const regions = Object.keys(native.regions), names = grouped(regions, sourceKey);
    const candidates = new Map();
    for (const name of regions) {
      const qualified = historicalKeys.get(key(name)), matching = byName.get(sourceKey(name)) || [];
      if (qualified?.size === 1) candidates.set(name, {
        reference_key: [...qualified][0], identity_basis: 'held_2024_qualified_identity_reference_only' });
      else if (names.get(sourceKey(name)).length === 1 && matching.length === 1)
        candidates.set(name, { reference_key: matching[0].properties.key,
          identity_basis: 'unambiguous_name_with_literal_Twp_Plt_suffix' });
    }
    const assignments = grouped([...candidates], ([, r]) => r.reference_key);
    for (const [name, candidate] of candidates)
      if (assignments.get(candidate.reference_key).length !== 1) candidates.delete(name);
    const categorySums = {}, parent = total(native.statewide_total);
    const rows = regions.map(name => {
      const categories = native.regions[name], value = total(categories), match = candidates.get(name);
      for (const [category, cell] of Object.entries(categories))
        categorySums[category] = count((categorySums[category] ?? 0) + count(cell.votes));
      return { year: 2026, state_code: 'ME', mode, source_region: name, source_count: value,
        native_categories: categories, native_election_name: native.election_name,
        source_date: native.snapshot_date, source_url: source.receipt.url,
        native_election_id_qualified: false, denominator: null, reported_pct: null,
        cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
        reference_key: match?.reference_key ?? null, identity_basis: match?.identity_basis ?? null,
        disposition: match ? 'matched_older_contextual_locality_activity_only' : 'held_unmatched_or_ambiguous_locality',
        complete_download_url: inputs.complete_download_url };
    });
    if (rows.reduce((sum, row) => sum + row.source_count, 0) !== parent
      || Object.keys(categorySums).length !== Object.keys(native.statewide_total).length
      || Object.entries(native.statewide_total).some(([name, bucket]) => categorySums[name] !== count(bucket.votes)))
      throw new Error('Maine complete native region/category tallies disagree with source parent');
    queries.push(...rows);
    frames[mode] = rows.filter(row => row.reference_key !== null);
    frameQueries.push({ state_code: 'ME', mode, source_date: native.snapshot_date,
      source_regions: 584, mapped_locality_observations: frames[mode].length,
      native_category_parents: native.statewide_total, source_category_sum: parent,
      native_category_parent_sums_agree: true, source_clock: null, source_timezone: null,
      native_election_name: native.election_name, native_election_id_qualified: false,
      analysis_rates_approved: false, source_url: source.receipt.url });
    const observed = new Set(frames[mode].map(row => row.reference_key));
    referenceQueries.push(...original.features.map(({ properties: p }) => ({
      state_code: 'ME', mode, reference_key: p.key, reference_name: p.name, boundary_year: 2024,
      source_region: frames[mode].find(row => row.reference_key === p.key)?.source_region ?? null,
      disposition: observed.has(p.key) ? 'source_activity_name_match' : 'held_no_unique_source_region',
    })));
  }
  return { locality_frames: frames, reference_geometry: inputs.reference,
    complete_source_region_queries: queries, complete_frame_queries: frameQueries,
    complete_reference_queries: referenceQueries,
    summary: { complete_source_region_queries: queries.length, complete_reference_queries: referenceQueries.length,
      mapped_per_mode: Object.fromEntries(Object.entries(frames).map(([m, rows]) => [m, rows.length])),
      held_native_per_mode: Object.fromEntries(Object.entries(frames).map(([m, rows]) => [m, 584 - rows.length])),
      held_reference_per_mode: Object.fromEntries(Object.entries(frames).map(([m, rows]) => [m, 528 - rows.length])),
      contextual_boundary_year: 2024, native_election_id_qualified: false, analysis_rates_approved: false,
      county_totals_inferred: false, precinct_records_inferred: false, modes_added: false } };
}

let cached;
export function loadMaineLocalityActivity() {
  if (cached) return cached;
  const inputs = JSON.parse(readFileSync(`${VERSION}/inputs.json`, 'utf8'));
  const verified = path => {
    const body = readFileSync(path), receipt = inputs.files[path];
    if (!receipt || body.length !== receipt.bytes || digest(body) !== receipt.sha256)
      throw new Error(`Changed sufficient Maine locality input: ${path}`);
    return body;
  };
  for (const path of Object.keys(inputs.files)) verified(path);
  const sources = Object.fromEntries(Object.entries(inputs.responses).map(([category, row]) =>
    [category, { native: JSON.parse(verified(row.path)), receipt: row.receipt }]));
  return cached = reviewMaineLocalityActivity({ inputs, sources,
    original: JSON.parse(gunzipSync(verified(inputs.reference.path))),
    historical: JSON.parse(gunzipSync(verified(inputs.historical_identity_path))) });
}

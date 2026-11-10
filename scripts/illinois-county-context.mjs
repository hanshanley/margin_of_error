import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const version = 'data/county-source-reviews/20261110-illinois-county-context-01';
const modes = { inperson: 'in_person_early', returned: 'mail_returned' };
const cities = ['City of Bloomington', 'City of Chicago', 'City of Danville',
  'City of East St Louis', 'City of Galesburg', 'City of Rockford'];
const nameKey = name => name.replace(/ County$/, '').toLowerCase().replace(/[^a-z0-9]/g, '');
const sum = categories => {
  if (!categories || typeof categories !== 'object' || Array.isArray(categories)
    || !Object.keys(categories).length
    || Object.values(categories).some(row => !Number.isSafeInteger(row?.votes) || row.votes < 0))
    throw new Error('Missing or invalid native category count; not zero');
  return Object.values(categories).reduce((total, row) => total + row.votes, 0);
};

export function reviewIllinoisCountyContext({ inputs, sources, reference }) {
  if (inputs.reference.boundary_year !== 2026 || inputs.reference.counties !== 102
    || inputs.whole_county_counts_qualified !== false || inputs.authority_territories_qualified !== false
    || inputs.native_election_id_qualified !== false
    || inputs.rates_approved !== false || reference.features.length !== 102)
    throw new Error('Unqualified Illinois source-region context');
  const byName = new Map(), byId = new Map();
  for (const feature of reference.features) {
    const p = feature.properties, key = nameKey(p.name);
    if (!/^17\d{3}$/.test(p.key) || p.state_code !== 'IL' || p.boundary_year !== 2026
      || !feature.geometry || byName.has(key) || byId.has(p.key))
      throw new Error('Ambiguous or incompatible county contextual identity');
    byName.set(key, p);
    byId.set(p.key, p);
  }
  const sourceQueries = [], referenceQueries = [], frameQueries = [], frames = {}, cityRows = {};
  for (const [category, mode] of Object.entries(modes)) {
    const source = sources[category], native = source.native;
    if (native.state !== 'IL' || native.category !== category
      || native.snapshot_date !== '2026-11-04'
      || native.election_name !== (category === 'inperson' ? 'Illinois In-Person Early Voting' : 'Illinois Ballots Returned')
      || Object.keys(native.regions).length !== 108
      || source.receipt.url !== `https://civicapi.org/api/v2/early-vote/IL/${category}`)
      throw new Error('Changed native Illinois source frame');
    const parents = Object.fromEntries(Object.keys(native.statewide_total).map(key => [key, 0]));
    const mapped = [], held = [], seen = new Set();
    for (const [name, categories] of Object.entries(native.regions)) {
      const count = sum(categories);
      if (Object.keys(categories).sort().join('|') !== Object.keys(parents).sort().join('|'))
        throw new Error('Native category inventory differs from its source parent');
      for (const [key, row] of Object.entries(categories)) parents[key] += row.votes;
      const city = cities.includes(name);
      const match = city ? null : byName.get(nameKey(name));
      if (!city && (!match || seen.has(match.key)))
        throw new Error('Unknown or duplicate source-region contextual identity');
      if (match) seen.add(match.key);
      const query = { state_code: 'IL', mode, source_region: name, source_count: count,
        native_categories: categories, contextual_county_fips: match?.key ?? null,
        native_geography_id_qualified: false, whole_county_count_qualified: false,
        source_authority_territory_qualified: false, native_election_id_qualified: false,
        cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
        denominator: null, reported_pct: null, source_date: native.snapshot_date,
        source_clock: null, source_timezone: null, source_url: source.receipt.url,
        disposition: city ? 'held_city_named_region_not_assigned_to_county'
          : 'county_named_source_region_on_context_only_not_whole_county_total' };
      sourceQueries.push(query);
      if (city) {
        held.push(query);
        continue;
      }
      mapped.push({ year: 2026, state_code: 'IL', county: name,
        county_fips: match.key, contextual_county_fips: match.key,
        county_id: `additional:IL:source-region:${match.key}`,
        geography_level: 'provider_county_named_region_context',
        ballots: count, denominator: null, reported_pct: null,
        source_mode: mode, source_provider: 'civicAPI early activity',
        source_date: native.snapshot_date, source_url: source.receipt.url,
        count_scope: 'literal_county_named_source_region_not_whole_county',
        native_geography_id_qualified: false, whole_county_count_qualified: false,
        source_authority_territory_qualified: false, native_election_id_qualified: false,
        cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
        reference_geometry: { boundary_year: 2026, counties: 102,
          geography_scope: 'county_context_not_source_authority_territory' },
        native_record: { state: native.state, category, source_region: name,
          snapshot_date: native.snapshot_date, election_name: native.election_name,
          literal_count_field: 'votes', categories } });
    }
    if (seen.size !== 102 || held.length !== 6 || new Set(held.map(r => r.source_region)).size !== 6)
      throw new Error('Incomplete source-region context or city holds');
    for (const [key, value] of Object.entries(parents))
      if (value !== native.statewide_total[key].votes)
        throw new Error('Native source-category parent disagreement');
    const parent = sum(native.statewide_total);
    if (parent !== (category === 'inperson' ? 1162828 : 892086))
      throw new Error('Changed held Illinois parent snapshot');
    mapped.sort((a, b) => a.contextual_county_fips.localeCompare(b.contextual_county_fips));
    for (const row of mapped) referenceQueries.push({ state_code: 'IL', mode,
      contextual_county_fips: row.contextual_county_fips, source_region: row.county,
      source_count: row.ballots, disposition: 'source_count_on_county_context_not_county_total',
      whole_county_count_qualified: false, native_geography_id_qualified: false });
    frameQueries.push({ state_code: 'IL', mode, source_regions: 108, contextual_regions: 102,
      city_regions_held: 6, source_category_parents: native.statewide_total,
      native_parent_source_count: parent, contextual_region_count_sum: mapped.reduce((s, r) => s + r.ballots, 0),
      held_city_count_sum: held.reduce((s, r) => s + r.source_count, 0),
      county_totals_inferred: false, city_counts_allocated: false, rates_approved: false });
    frames[mode] = mapped;
    cityRows[mode] = held;
  }
  return { summary: { complete_source_queries: 216, complete_reference_queries: 204,
    complete_frame_queries: 2, contextual_regions_per_mode: 102, city_holds_per_mode: 6,
    whole_county_counts_qualified: false, authority_territories_qualified: false,
    native_election_id_qualified: false, rates_approved: false },
  source_queries: sourceQueries, reference_queries: referenceQueries, frame_queries: frameQueries,
  county_context_frames: frames, held_city_regions: cityRows,
  complete_download_url: inputs.complete_download_url,
  reference_geometry: { ...inputs.reference, url: inputs.reference.url,
    bytes: inputs.files[inputs.reference.path].bytes, identity_field: 'key',
    geography_scope: 'county_context_not_source_authority_territory',
    source_authority_territories_qualified: false, whole_county_counts_qualified: false,
    review_id: 'illinois-county-name-context-20261110-01' } };
}

export function loadIllinoisCountyContext() {
  const inputs = JSON.parse(readFileSync(`${version}/inputs.json`, 'utf8'));
  for (const [path, receipt] of Object.entries(inputs.files)) {
    const body = readFileSync(path);
    if (body.length !== receipt.bytes || createHash('sha256').update(body).digest('hex') !== receipt.sha256)
      throw new Error(`Changed sufficient Illinois input: ${path}`);
  }
  return reviewIllinoisCountyContext({ inputs,
    reference: JSON.parse(gunzipSync(readFileSync(inputs.reference.path))),
    sources: Object.fromEntries(Object.entries(inputs.responses).map(([category, row]) =>
      [category, { native: JSON.parse(readFileSync(row.path, 'utf8')), receipt: row.receipt }])) });
}

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const VERSION = 'data/county-source-reviews/20261109-provider-county-frames-01';
const modes = { in_person_early: 'inperson', mail_returned: 'returned' };
const digest = value => createHash('sha256').update(value).digest('hex');
const nameKey = value => value.normalize('NFKD').toLowerCase()
  .replace(/^st\.?\s+/, 'saint ').replace(/ (?:county|parish|municipality)$/, '').replace(/[^a-z0-9]/g, '');
const count = value => {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Invalid provider native votes count; missing is not zero');
  return value;
};
const total = categories => {
  if (!categories || typeof categories !== 'object' || Array.isArray(categories) || !Object.keys(categories).length)
    throw new Error('Missing provider source categories are not zero');
  return Object.values(categories).reduce((sum, row) => count(sum + count(row.votes)), 0);
};

export function reviewProviderCountyFrames({ context, sources, catalogue, completeDownloadUrl }) {
  if (context.collector_election_date !== '2026-11-03'
    || context.dataset_directory_id !== '20261104T220424Z'
    || context.source_snapshot_id !== '20261104T220425Z'
    || context.native_election_id_qualified !== false || context.rates_approved !== false
    || context.states.length !== 51 || new Set(context.states.map(r => r.state_code)).size !== 51)
    throw new Error('Changed provider snapshot, collector context or complete state query');
  const frames = {}, frameQueries = [], regionQueries = [];
  for (const state of context.states) {
    const code = state.state_code, reference = catalogue[code];
    if (reference && (reference.boundary_year !== 2026
      || reference.identities.length !== reference.counties
      || new Set(reference.identities.map(r => r.county_fips)).size !== reference.counties
      || reference.identities.some(r => r.state_code !== code || r.boundary_year !== 2026)))
      throw new Error('Unqualified full provider county-identity reference');
    const identities = new Map((reference?.identities || []).map(r => [nameKey(r.county), r]));
    if (reference && identities.size !== reference.counties)
      throw new Error('Ambiguous normalized county identities');
    for (const [mode, category] of Object.entries(modes)) {
      const source = sources[`${code}-${category}`];
      if (!source) {
        frameQueries.push({ state_code: code, mode, disposition: 'no_captured_provider_response',
          source_count: null, county_frame_approved: false, counties: 0 });
        continue;
      }
      const { native, receipt } = source;
      if (native.state !== code || native.category !== category
        || typeof native.election_name !== 'string' || !native.election_name
        || !/^2026-\d{2}-\d{2}$/.test(native.snapshot_date)
        || !native.regions || typeof native.regions !== 'object' || Array.isArray(native.regions)
        || receipt.http_status !== 200 || receipt.source_snapshot_id !== context.source_snapshot_id)
        throw new Error('Changed provider source identity, native date, mode or successful receipt');
      const parent = total(native.statewide_total);
      const regions = Object.entries(native.regions).map(([name, categories]) => ({
        state_code: code, mode, source_region: name, source_count: total(categories),
        native_categories: categories, county_fips: identities.get(nameKey(name))?.county_fips ?? null,
        source_date: native.snapshot_date, source_url: receipt.url,
        native_election_name: native.election_name, native_election_id_qualified: false,
        denominator: null, reported_pct: null,
      }));
      const names = regions.map(r => nameKey(r.source_region));
      const complete = Boolean(reference && regions.length === reference.counties
        && new Set(names).size === reference.counties && names.every(name => identities.has(name)));
      const sum = regions.reduce((s, row) => count(s + row.source_count), 0);
      const categorySums = {};
      for (const row of regions) for (const [name, bucket] of Object.entries(row.native_categories))
        categorySums[name] = count((categorySums[name] ?? 0) + count(bucket.votes));
      const categoryParentsAgree = Object.keys(native.statewide_total).length === Object.keys(categorySums).length
        && Object.entries(native.statewide_total).every(([name, bucket]) => categorySums[name] === count(bucket.votes));
      const approved = complete && sum === parent && categoryParentsAgree;
      const disposition = !regions.length ? 'state_only_no_region_counts'
        : !reference ? 'no_complete_county_reference'
          : !complete ? 'noncounty_mixed_partial_or_unmatched_regions'
            : !approved ? 'native_region_or_category_parent_disagreement'
              : 'complete_county_identity_frame_source_activity_only';
      frameQueries.push({ state_code: code, mode, disposition, county_frame_approved: approved,
        counties: regions.length, source_count: parent, native_region_sum: sum,
        source_count_basis: 'sum_native_statewide_total_category_votes',
        native_category_parents: native.statewide_total, category_parent_sums_agree: categoryParentsAgree,
        source_date: native.snapshot_date, source_url: receipt.url, source_clock: null, source_timezone: null,
        native_election_name: native.election_name, native_election_id_qualified: false });
      regionQueries.push(...regions.map(row => ({ ...row, candidate_county_fips: row.county_fips,
        county_fips: approved ? row.county_fips : null, frame_disposition: disposition,
        county_frame_approved: approved })));
      if (!approved) continue;
      const geometry = { ...reference };
      delete geometry.identities;
      frames[code] ||= {};
      frames[code][mode] = regions.map(row => ({
        ...row, year: 2026, county: identities.get(nameKey(row.source_region)).county,
        reference_geometry: geometry, source_provider: 'civicAPI early activity',
        source_count_qualified: true, cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
        participation_measure_label: mode === 'in_person_early'
          ? 'Provider in-person early activity (native votes counts)'
          : 'Provider returned activity (native votes counts; not cast ballots)',
        native_record: { source_region: row.source_region, categories: row.native_categories,
          state: native.state, category: native.category, election_name: native.election_name,
          snapshot_date: native.snapshot_date, literal_count_field: 'votes' },
        source_update_label: `${native.snapshot_date} provider snapshot date; native clock/timezone not supplied. `
          + 'Collected for the 2026 project; native election identifier is not independently qualified.',
        source_status_literal: 'Provider-reported early activity; not a certified government turnout series',
        source_reporting_label: 'Sum of native source-category votes counts in this one reported activity frame. '
          + 'Source party/bucket categories are not candidate choices; operational affiliation definition is unqualified. '
          + 'Do not add early and returned frames, treat them as full-election turnout, or infer unique people. '
          + 'County identity is separately matched to the complete 2026 Census reference, not a native FIPS or precinct claim. '
          + 'All analysis denominators/rates withheld.',
        complete_download_url: completeDownloadUrl,
      }));
    }
  }
  return { county_frames: frames, frame_queries: frameQueries, region_queries: regionQueries,
    summary: { complete_state_mode_queries: frameQueries.length,
      approved_county_frames: frameQueries.filter(r => r.county_frame_approved).length,
      approved_states: Object.keys(frames).length,
      approved_county_observations: Object.values(frames).flatMap(r => Object.values(r)).flat().length,
      all_source_region_queries: regionQueries.length, analysis_rates_approved: false,
      native_election_context_qualified: false, modes_added: false } };
}

let cached;
export function loadProviderCountyFrames() {
  if (cached) return cached;
  const inputs = JSON.parse(readFileSync(`${VERSION}/inputs.json`, 'utf8'));
  const verified = path => {
    const body = readFileSync(path), receipt = inputs.files[path];
    if (!receipt || body.length !== receipt.bytes || digest(body) !== receipt.sha256)
      throw new Error(`Changed sufficient provider source input: ${path}`);
    return body;
  };
  for (const path of Object.keys(inputs.files)) verified(path);
  const sources = {};
  for (const [key, record] of Object.entries(inputs.responses))
    sources[key] = { native: JSON.parse(verified(record.path)), receipt: record.receipt };
  const catalogue = {};
  for (const [code, reference] of Object.entries(inputs.references)) {
    const raw = gunzipSync(verified(reference.path));
    if (digest(raw) !== reference.uncompressed_sha256)
      throw new Error('Changed provider county-reference decoded bytes');
    const geometry = JSON.parse(raw);
    catalogue[code] = { ...reference, identities: geometry.features.map(({ properties: p }) => ({
      county_fips: p.key, county: p.name, state_code: p.state_code, boundary_year: p.boundary_year,
    })) };
  }
  cached = reviewProviderCountyFrames({
    context: JSON.parse(verified(`${VERSION}/source-context.json`)),
    sources, catalogue, completeDownloadUrl: inputs.complete_download_url,
  });
  return cached;
}

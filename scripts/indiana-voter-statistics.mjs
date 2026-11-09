import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const VERSION = 'data/county-source-reviews/20261109-indiana-voter-statistics-01';
const digest = value => createHash('sha256').update(value).digest('hex');
const nameKey = value => value.toLowerCase().replace(/ county$/, '').replace(/[.\s]/g, '');
const fields = ['REGISTERED_VOTERS', 'VotersVoting', 'InPerson', 'Absentee'];
const count = value => {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0)
    throw new Error('Invalid Indiana native count; missing and boolean values are not zero');
  return value;
};

export function reviewIndianaVoterStatistics({ settings, turnout, roster, geometry, reference, countyParents = [] }) {
  const meta = settings.Root, source = turnout.root;
  if (meta.StateFP !== '18' || meta.CurrentElection !== '11/03/2026'
    || meta.ElectionType !== 'G' || meta.Certified !== 'F' || meta.VersionType !== 'B'
    || roster.year !== 2026 || roster.state_code !== 'IN' || roster.office_category_id !== '1041'
    || roster.office_category_name !== 'Secretary of State'
    || !/^2026-11-09T/.test(source.WriteTime) || !/^2026-11-09T/.test(roster.source_write_time))
    throw new Error('Changed Indiana election, unofficial source or source-clock identity');
  const nativeRows = source.CountyTurnout;
  if (nativeRows.length !== 93 || new Set(nativeRows.map(row => nameKey(row.County))).size !== 93
    || nativeRows.at(-1).County !== 'Total'
    || nativeRows.some(row => row.ElectionDateName !== 'Tuesday, November 3, 2026'))
    throw new Error('Incomplete Indiana 92-county plus separate state-parent query');
  for (const native of nativeRows) {
    if (JSON.stringify(Object.keys(native).sort()) !== JSON.stringify(
      ['County', 'ElectionDateName', ...fields].sort()))
      throw new Error('Changed Indiana native field inventory');
    fields.forEach(field => count(native[field]));
    if (native.VotersVoting !== native.InPerson + native.Absentee)
      throw new Error('Indiana native voting modes disagree; never repair the original');
  }
  const parent = nativeRows.at(-1), counties = nativeRows.slice(0, -1);
  if (fields.some(field => counties.reduce((total, row) => total + row[field], 0) !== parent[field]))
    throw new Error('Indiana original county counts disagree with the separate native state subtotal');
  if (reference.boundary_year !== 2026 || reference.counties !== 92
    || geometry.features.length !== 92 || roster.rows.length !== 92
    || new Set(geometry.features.map(row => row.properties.key)).size !== 92
    || new Set(roster.rows.map(row => row.county_fips)).size !== 92
    || new Set(roster.rows.map(row => nameKey(row.native_county_name))).size !== 92
    || geometry.features.some(({ properties: p }) =>
      p.state_code !== 'IN' || p.boundary_year !== 2026 || !/^18\d{3}$/.test(p.key)))
    throw new Error('Incomplete Indiana native identity or 2026 Census county reference');
  const shapes = new Map(geometry.features.map(row => [row.properties.key, row.properties]));
  const identities = new Map(roster.rows.map(row => [nameKey(row.native_county_name), row]));
  const replacements = new Map();
  for (const item of countyParents) {
    if (item.state_code !== 'IN' || item.election_date !== '2026-11-03'
      || item.whole_county_scope_reviewed !== true || item.unique_voters_certified !== false
      || item.analysis_rate_approved !== false || replacements.has(item.county_fips)
      || !['native_ballots_cast', 'native_voters_cast', 'native_cards_cast',
        'native_turnout_numerator'].includes(item.measure_kind)
      || typeof item.measure_literal !== 'string' || !item.measure_literal
      || !/^https:\/\//.test(item.source_url) || !/^[a-f0-9]{64}$/.test(item.original_sha256)
      || !item.native_record || typeof item.native_record !== 'object' || Array.isArray(item.native_record)
      || !Number.isSafeInteger(item.original_bytes) || item.original_bytes <= 0
      || item.count === 0)
      throw new Error('Unqualified or duplicate Indiana independent county parent');
    const literal = item.measure_kind === 'native_ballots_cast' ? /ballots?\s*cast|total\s*ballots?/i
      : item.measure_kind === 'native_voters_cast' ? /voters?\s*(?:cast|voting)/i
        : item.measure_kind === 'native_turnout_numerator' ? /registered voters|turnout/i : /cards?\s*cast/i;
    if (!literal.test(item.measure_literal))
      throw new Error('Indiana county-parent label does not establish its literal count measure');
    count(item.count);
    replacements.set(item.county_fips, item);
  }
  const result = counties.map(native => {
    const identity = identities.get(nameKey(native.County));
    const shape = shapes.get(identity?.county_fips);
    if (!shape || nameKey(shape.name) !== nameKey(native.County)
      || nameKey(identity.native_county_name) !== nameKey(native.County)
      || identity.number_of_seats !== '1' || !identity.candidate_counts.length)
      throw new Error('Unmatched Indiana county or single-office contradiction control');
    const contestVotes = identity.candidate_counts.reduce((total, value) => total + count(value), 0);
    const inconsistent = native.VotersVoting < contestVotes;
    const replacement = replacements.get(identity.county_fips);
    if (replacement && (!inconsistent || nameKey(replacement.county) !== nameKey(native.County)))
      throw new Error('Independent Indiana parents may replace only a matching held source record');
    const selected = replacement ? replacement.count : inconsistent ? null : native.VotersVoting;
    const note = replacement
      ? 'Selected the independent whole-county source snapshot; the original state-statistics value and conflict remain unchanged. '
        + (replacement.scope_note || '')
      : inconsistent
        ? `Native VotersVoting=${native.VotersVoting}; the separate native Secretary of State contest has `
          + `${contestVotes} candidate votes. This is inconsistent reporting coverage, not zero turnout. `
          + 'The selected participation count is withheld; candidate votes are never substituted.'
        : 'Native Voters Voting, not a candidate-vote sum or certified unique-voter count. '
          + 'InPerson and Absentee retain their native definitions; Absentee is not relabelled mail received.';
    return {
      year: 2026, state_code: 'IN', county: shape.name, county_fips: identity.county_fips,
      source_count: selected, denominator: null, reported_pct: null,
      native_record: replacement ? replacement.native_record : native,
      statewide_statistics_native_record: native,
      selected_source_kind: replacement ? replacement.measure_kind : inconsistent
        ? 'withheld_inconsistent_native_statistics' : 'native_voters_voting',
      participation_measure_label: replacement
        ? replacement.display_label || replacement.measure_literal : 'Native Voters Voting',
      cast_ballot_count_qualified: replacement?.measure_kind === 'native_ballots_cast',
      unique_voter_count_qualified: false,
      source_count_qualified: selected !== null,
      source_url: replacement?.source_url
        || 'https://enr.indianavoters.in.gov/site/data/statewideTurnout_B.json',
      source_update_label: replacement
        ? replacement.source_clock_literal || 'Native county report clock not supplied'
        : `Voter statistics WriteTime: ${source.WriteTime}; timezone not supplied. `
          + `Separate candidate control WriteTime: ${roster.source_write_time}; settings WriteTime: ${meta.WriteTime}. `
          + 'These are separate native clocks, not one common cutoff.',
      source_status_literal: replacement ? replacement.source_status_literal : 'Native Certified=F (unofficial)',
      source_reporting_label: note,
      source_candidate_votes_not_participation: contestVotes,
      reference_geometry: reference,
      quality: [note,
        'All 92 source county identities match the separately checksum-verified 2026 Census reference; not precinct boundaries.',
        'Native registrations are retained, not qualified as analysis denominators. Every analysis rate stays withheld.',
        'The original state subtotal is partial statistics, not a full-election statewide turnout reference.'],
    };
  });
  if (replacements.size !== result.filter(row => replacements.has(row.county_fips)).length)
    throw new Error('Unmatched Indiana county-parent replacement');
  return {
    counties: result, original_state_subtotal: parent,
    summary: {
      original_queries: 93, county_queries: 92,
      selected_counts: result.filter(row => row.source_count !== null).length,
      held_counts: result.filter(row => row.source_count === null).length,
      independent_county_parents: countyParents.length,
      original_source_state_voters_voting: parent.VotersVoting,
      full_election_state_count_qualified: false, analysis_rates_approved: false,
    },
  };
}

export function loadIndianaVoterStatistics() {
  const inputs = JSON.parse(readFileSync(`${VERSION}/inputs.json`, 'utf8'));
  if (inputs.state_full_election_participation_qualified !== false
    || inputs.analysis_rates_approved !== false || inputs.precincts_approved !== false)
    throw new Error('Do not promote partial Indiana statistics to state, rate or precinct coverage');
  const verified = path => {
    const body = readFileSync(path), receipt = inputs.files[path];
    if (!receipt || body.length !== receipt.bytes || digest(body) !== receipt.sha256)
      throw new Error(`Changed Indiana sufficient input: ${path}`);
    return body;
  };
  const json = name => JSON.parse(verified(`${VERSION}/${name}`));
  const compressed = name => JSON.parse(gunzipSync(verified(`${VERSION}/${name}`)));
  const raw = verified(inputs.reference.path), decoded = gunzipSync(raw);
  if (digest(raw) !== inputs.reference.sha256 || digest(decoded) !== inputs.reference.uncompressed_sha256)
    throw new Error('Changed Indiana county-reference bytes');
  const countyParents = json('independent-county-parents.json');
  for (const item of countyParents) {
    const original = verified(item.original_path);
    if (original.length !== item.original_bytes || digest(original) !== item.original_sha256)
      throw new Error('Changed independent Indiana county original');
  }
  const result = reviewIndianaVoterStatistics({
    settings: compressed('original-settings.json.gz'),
    turnout: compressed('original-statewide-turnout.json.gz'),
    roster: compressed('native-county-identity-control.json.gz'),
    geometry: JSON.parse(decoded), reference: inputs.reference, countyParents,
  });
  result.precincts = [];
  if (inputs.monroe) {
    const data = inputs.monroe;
    verified(data.selected_reference_file);
    const units = JSON.parse(gunzipSync(verified(data.participation_file)));
    const source = JSON.parse(verified(data.source_count_file));
    const geometry = JSON.parse(gunzipSync(verified(data.normalized_reference_file)));
    const audit = JSON.parse(verified(data.audit_file));
    result.precincts = reviewIndianaMonroe({ units, source, geometry, audit });
    result.summary.monroe_source_units = units.length;
    result.summary.monroe_mapped_units = geometry.features.length;
    result.summary.monroe_geometry_withheld_units = units.length - geometry.features.length;
  }
  for (const row of result.counties) row.complete_download_url = inputs.complete_download_url;
  for (const row of result.precincts) row.complete_download_url = inputs.complete_download_url;
  return result;
}

export function reviewIndianaMonroe({ units, source, geometry, audit }) {
  const originals = new Map(source.features.map(row => [row.attributes.Precinct_ID, row.attributes]));
  if (units.length !== 103 || originals.size !== 103
    || new Set(units.map(row => row.native_precinct_id)).size !== 103
    || geometry.features.length !== audit.mapped_polygons || audit.geometry_repaired !== false
    || audit.counts_allocated_to_clips !== false || audit.publisher_count_indicator_reproduced !== 42766)
    throw new Error('Incomplete or unqualified Indiana Monroe reporting-unit review');
  for (const row of units) {
    const native = originals.get(row.native_precinct_id);
    if (!native || JSON.stringify(row.native_record) !== JSON.stringify(native)
      || row.year !== 2026 || row.state_code !== 'IN' || row.county_fips !== '18105'
      || row.county_id !== 'additional:IN:18105' || row.unit_key !== String(native.Precinct_ID)
      || row.key !== `IN|18105|${native.Precinct_ID}` || row.unit !== native.Precinct
      || row.ballots !== count(native.Ballots_Cast) || row.denominator !== null || row.reported_pct !== null
      || native.Precinct_Reporting !== 'Partially Reporting'
      || row.source_snapshot !== 'indiana-monroe-native-20261109-01'
      || !['matched', 'withheld_source_geometry'].includes(row.match_status)
      || (row.match_status === 'matched') !== (row.geometry_withheld_reason === null))
      throw new Error('Changed Indiana Monroe native count, identity, rate or source qualification');
  }
  const byId = new Map(units.map(row => [row.key, row]));
  if (new Set(geometry.features.map(row => row.properties.key)).size !== geometry.features.length
    || geometry.features.some(row => !row.geometry || row.properties.match_status !== 'matched'
      || JSON.stringify(row.properties) !== JSON.stringify(byId.get(row.properties.key))))
    throw new Error('Unmatched Indiana Monroe mapped reporting unit');
  if (units.reduce((total, row) => total + row.ballots, 0) !== 42766)
    throw new Error('Changed Indiana Monroe publisher-defined Total Ballots Cast indicator');
  return units;
}

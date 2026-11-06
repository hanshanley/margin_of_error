import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { pathToFileURL } from 'node:url';
import { gzipSync, gunzipSync } from 'node:zlib';
import { canonicalJson } from '../public/scripts/participation-county-context.js';

const digest = value => createHash('sha256').update(value).digest('hex');
const jsonDigest = value => digest(canonicalJson(value));
const nameKey = value => value.normalize('NFKD').toUpperCase().replace(/[^A-Z0-9]/g, '');
const fullCounty = row => row.ballots !== null
  && ['county', 'county_equivalent', 'independent_city'].includes(row.geography_level);
const json = path => JSON.parse(readFileSync(path, 'utf8'));

export function createCountyContextReview(records, inventories, collections, investigation) {
  const current = new Map(inventories['2026'].map(row => [row.GEOID, row]));
  const previous = new Map(inventories['2024'].map(row => [row.GEOID, row]));
  if (current.size !== inventories['2026'].length || previous.size !== inventories['2024'].length
    || current.size !== previous.size || [...current].some(([key, row]) =>
      previous.get(key)?.USPS !== row.USPS || previous.get(key)?.NAME !== row.NAME))
    throw new Error('Current and contextual-vintage county identities disagree');
  const candidates = records.filter(fullCounty), observations = [], geometry = {};
  const nativeKeys = new Set(), joinedKeys = new Set();
  for (const row of candidates) {
    if (row.year !== 2026 || !Number.isSafeInteger(row.ballots) || row.ballots < 0
      || (row.reported_pct !== null && (!Number.isFinite(row.reported_pct) || row.denominator <= 0))
      || nativeKeys.has(`${row.state_code}|${row.county_id}`))
      throw new Error('Invalid or duplicate whole-county participation observation');
    nativeKeys.add(`${row.state_code}|${row.county_id}`);
    const collection = collections[row.state_code];
    const check = investigation.geometry_checks.find(item => item.state_code === row.state_code);
    if (!collection || !check || check.invalid.length || !check.live_complete_bytes_equal
      || !check.current_and_2024_identity_inventory_equal)
      throw new Error('Missing complete geometry or independent geometry review');
    const matches = collection.features.filter(feature => {
      const props = feature.properties, official = current.get(props.key);
      if (!official || official.USPS !== row.state_code || props.state_code !== row.state_code
        || props.boundary_year !== 2024 || props.name !== official.NAME)
        throw new Error('Contextual geometry disagrees with official county identity');
      return [props.name, ...props.aliases].some(alias => nameKey(alias) === nameKey(row.county))
        && (row.state_code !== 'VA' || props.name.endsWith(' city') === (row.geography_level === 'independent_city'));
    });
    if (matches.length !== 1) throw new Error(`Missing or ambiguous county join: ${row.state_code} ${row.county}`);
    const props = matches[0].properties;
    if (joinedKeys.has(props.key) || (/^\d{5}$/.test(row.county_id) && row.county_id !== props.key))
      throw new Error('Duplicate geographic join or conflicting native geographic identifier');
    joinedKeys.add(props.key);
    observations.push({
      state_code: row.state_code, county_id: row.county_id, county: row.county,
      geography_level: row.geography_level, review_id: row.review_id,
      contextual_geoid: props.key, contextual_name: props.name, boundary_year: 2024,
      ballots: row.ballots, denominator: row.denominator, reported_pct: row.reported_pct,
      participation_measure_kind: row.participation_measure_kind ?? 'source_defined_participation_count',
      participation_measure_label: row.participation_measure_label ?? row.participation_measure_literal ?? 'Ballots reported',
      source_record_sha256: jsonDigest(row), source_url: row.source_url,
      complete_download_url: row.complete_download_url,
      contextual_map_approved: true, source_map_approval_unchanged: row.maps_approved,
    });
    geometry[row.state_code] = {
      file: `geometry/county-${row.state_code}.geojson`, boundary_year: 2024,
      sha256: check.contextual_geometry_sha256, canonical_sha256: jsonDigest(collection),
      features: collection.features.length,
      simplification_overlap_pairs: check.overlap_pairs,
    };
  }
  return {
    schema_version: 1, year: 2026, context_base_url: '/participation-context/20261104T183601Z/',
    scope: 'Separately reviewed contextual county identity joins, not source-native FIPS, certified 2026 election boundaries or precinct geography.',
    limitations: [
      'Original source records, map-approval flags, timestamps, counting qualifications, missing denominators and missing rates are unchanged.',
      'Only source-scoped whole-county or county-equivalent participation observations are joined. Municipalities and reporting-unit containers are not aggregated into counties.',
      '2026 and 2024 Census Gazetteer county identities are independently compared. Identity agreement does not establish unchanged election geography or completed counting.',
      'Existing generalized 2024 Census contextual shapes are retained exactly, including documented small simplification overlaps. They are not certified election boundaries or suitable for analytical area measurements.',
      'Native ballots, source-defined Voters Cast and derived mode subtotals retain their distinct labels. Missing rates remain gray; counts do not measure turnout propensity.',
    ],
    counts: {
      complete_source_records: records.length, contextual_joins: observations.length,
      jurisdictions: Object.keys(geometry).length,
      reviewed_rates: observations.filter(row => row.reported_pct !== null).length,
      missing_rates: observations.filter(row => row.reported_pct === null).length,
      excluded_municipalities: records.filter(row => row.geography_level === 'municipality').length,
      excluded_missing_county_totals: records.filter(row => row.ballots === null).length,
    },
    geometry, observations,
    excluded: records.filter(row => !fullCounty(row)).map(row => ({
      state_code: row.state_code, county_id: row.county_id, county: row.county,
      geography_level: row.geography_level, source_record_sha256: jsonDigest(row),
      reason: row.geography_level === 'municipality' ? 'Native municipality, not a county'
        : 'Native reporting-unit container; county total not supplied',
    })),
  };
}

export function loadCountyContextReview(records) {
  const pointer = json(resolve('public/participation-county-context.json'));
  const path = resolve('public', pointer.base_url.slice(1), 'review.json');
  const body = readFileSync(path);
  if (body.length !== pointer.review_bytes || digest(body) !== pointer.review_sha256)
    throw new Error('Changed frozen contextual county review');
  const review = JSON.parse(body);
  const byKey = new Map(records.map(row => [`${row.state_code}|${row.county_id}`, row]));
  if (records.length !== review.counts.complete_source_records
    || byKey.size !== records.length
    || [...review.observations, ...review.excluded].some(row =>
      jsonDigest(byKey.get(`${row.state_code}|${row.county_id}`)) !== row.source_record_sha256))
    throw new Error('Contextual county review does not preserve the complete current source records');
  return { ...pointer, counts: review.counts, coverage: Object.fromEntries(Object.keys(review.geometry).map(code =>
    [code, { counties: review.observations.filter(row => row.state_code === code).length,
      rates: review.observations.filter(row => row.state_code === code && row.reported_pct !== null).length }])) };
}

function joinCsv(review) {
  const fields = Object.keys(review.observations[0]);
  const cell = value => '"' + (value === null ? '' : String(value)).replaceAll('"', '""') + '"';
  return [fields.map(cell).join(','),
    ...review.observations.map(row => fields.map(field => cell(row[field])).join(','))].join('\n') + '\n';
}

export function verifyCountyContextPackage(directory) {
  const compressed = file => JSON.parse(gunzipSync(readFileSync(resolve(directory, file))));
  const review = json(resolve(directory, 'review.json'));
  const records = compressed('complete-source-records.json.gz');
  const inventories = Object.fromEntries(['2024', '2026'].map(year =>
    [year, compressed(`complete-${year}-county-identities.json.gz`)]));
  const collections = Object.fromEntries(Object.keys(review.geometry).map(code =>
    [code, json(resolve(directory, review.geometry[code].file))]));
  const reproduced = createCountyContextReview(records, inventories, collections, {
    geometry_checks: json(resolve(directory, 'geometry-verification.json')),
  });
  if (JSON.stringify(reproduced, null, 2) + '\n' !== readFileSync(resolve(directory, 'review.json'), 'utf8')
    || joinCsv(reproduced) !== readFileSync(resolve(directory, 'county-participation-joins.csv'), 'utf8'))
    throw new Error('Complete county review does not reproduce');
  const checksums = json(resolve(directory, 'checksums.json'));
  for (const [file, expected] of Object.entries(checksums)) {
    const body = readFileSync(resolve(directory, file));
    if (body.length !== expected.bytes || digest(body) !== expected.sha256)
      throw new Error(`Changed complete package member: ${file}`);
  }
  return review.counts;
}

function build(sourceDirectory, destination) {
  if (existsSync(destination)) throw new Error('Never overwrite a contextual county review');
  const records = json(resolve(sourceDirectory, 'complete-current-normalized-records.json'));
  const inventories = Object.fromEntries(['2024', '2026'].map(year =>
    [year, json(resolve(sourceDirectory, `complete-${year}-county-identities.json`))]));
  const investigation = json(resolve(sourceDirectory, 'complete-context-join-investigation.json'));
  const pointer = json(resolve('public/participation-context/latest.json'));
  const contextRoot = resolve('public/participation-context', pointer.snapshot_id);
  const index = json(resolve(contextRoot, 'index.json'));
  if (pointer.snapshot_id !== '20261104T183601Z' || index.boundary_year !== 2024)
    throw new Error('Unexpected contextual county vintage');
  const collections = {}, geometryBodies = {};
  for (const code of new Set(records.filter(fullCounty).map(row => row.state_code))) {
    const file = index.geometry.county[code], body = readFileSync(resolve(contextRoot, file));
    const declared = pointer.files.find(row => row.path === file);
    const reviewed = investigation.geometry_checks.find(row => row.state_code === code);
    if (body.length !== declared.bytes || digest(body) !== declared.sha256
      || declared.sha256 !== reviewed.contextual_geometry_sha256)
      throw new Error('Changed contextual county geometry');
    collections[code] = JSON.parse(body); geometryBodies[file] = body;
  }
  const review = createCountyContextReview(records, inventories, collections, investigation);
  mkdirSync(destination, { recursive: true });
  const save = (file, body) => {
    const path = resolve(destination, file); mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, body, { flag: 'wx' });
  };
  save('review.json', JSON.stringify(review, null, 2) + '\n');
  save('complete-source-records.json.gz', gzipSync(JSON.stringify(records) + '\n', { level: 9 }));
  save('county-participation-joins.csv', joinCsv(review));
  for (const [file, body] of Object.entries(geometryBodies)) save(file, body);
  for (const year of ['2024', '2026']) {
    save(`complete-${year}-county-identities.json.gz`, gzipSync(JSON.stringify(inventories[year]) + '\n', { level: 9 }));
    save(`gazetteer-${year}-national-counties.zip`, readFileSync(resolve(sourceDirectory, `gazetteer-${year}-national-counties.zip`)));
  }
  const receiptFiles = ['2024', '2026'].flatMap(year => [
    `gazetteer-${year}-declaration.html.receipt.json`,
    `gazetteer-${year}-national-counties.zip.receipt.json`,
  ]);
  save('source-receipts.json', JSON.stringify(receiptFiles.map(file => json(resolve(sourceDirectory, file))), null, 2) + '\n');
  save('geometry-verification.json', JSON.stringify(investigation.geometry_checks, null, 2) + '\n');
  if (gunzipSync(readFileSync(resolve(destination, 'complete-source-records.json.gz'))).toString() !== JSON.stringify(records) + '\n')
    throw new Error('Complete source records were not preserved');
  console.log(JSON.stringify({ destination, counts: review.counts, review_sha256: digest(readFileSync(resolve(destination, 'review.json'))) }, null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const [, , sourceDirectory, destination] = process.argv;
  if (sourceDirectory === '--verify' && destination) console.log(JSON.stringify(verifyCountyContextPackage(resolve(destination)), null, 2));
  else {
    if (!sourceDirectory || !destination) throw new Error('Usage: node scripts/build-county-participation-context.mjs SOURCE_DIRECTORY NEW_OUTPUT_DIRECTORY | --verify PACKAGE_DIRECTORY');
    build(resolve(sourceDirectory), resolve(destination));
  }
}

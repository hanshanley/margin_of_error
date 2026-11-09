import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const digest = value => createHash('sha256').update(value).digest('hex');
const read = path => JSON.parse(readFileSync(path, 'utf8'));
const count = value => {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Invalid native county count');
  return value;
};
const nameKey = value => value.trim().replace(/\s+county$/i, '').toLowerCase();
const english = values => {
  const names = values.filter(value => value.languageId === 'en');
  if (names.length !== 1 || !names[0].text) throw new Error('Ambiguous native county name');
  return names[0].text;
};
const unique = (rows, key) => {
  const result = new Map(rows.map(row => [key(row), row]));
  if (result.size !== rows.length) throw new Error('Duplicate native county identity');
  return result;
};
const allBallots = node => {
  const bucket = node.BallotsCast;
  if (!Array.isArray(bucket) || bucket.length !== 1 || bucket[0].VoteTypeID !== '1')
    throw new Error('Missing explicit All ballot bucket');
  const value = count(bucket[0].BallotsCast);
  if (Object.hasOwn(node, 'TotalBallotsCast')
    ? count(node.TotalBallotsCast) !== value : value !== 0)
    throw new Error('Native ballot total disagrees with explicit All bucket');
  return value;
};

export function reviewCountyParents(code, source, units, geometry, reference) {
  const expected = code === 'ID' ? 44 : code === 'ND' ? 53 : 0;
  if (!expected || geometry.features.length !== expected)
    throw new Error('Incomplete native county reference inventory');
  const shapes = unique(geometry.features, feature => feature.properties.key);
  const shapeNames = unique(geometry.features, feature => nameKey(feature.properties.name));
  if ([...shapes].some(([key, feature]) => !new RegExp(`^${code === 'ID' ? '16' : '38'}\\d{3}$`).test(key)
    || feature.properties.state_code !== code || feature.properties.boundary_year !== 2026))
    throw new Error('Incorrect county reference state or vintage');
  unique(units, row => row.key);
  if (units.some(row => row.year !== 2026 || row.state_code !== code))
    throw new Error('Incorrect native reporting-unit election');
  const grouped = new Map();
  for (const row of units) {
    const key = row.county;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(row);
  }
  const output = [];
  if (code === 'ID') {
    if (source.election.electionDate !== '2026-11-03' || source.election.isPrimary !== false
      || source.election.isProduction !== true || source.localityElections.length !== expected)
      throw new Error('Incorrect Idaho county-parent election');
    const registrations = unique(source.voterRegistration, row => row.id);
    unique(source.localityElections, row => row.jurisdictionId);
    const seen = new Set();
    for (const native of source.localityElections) {
      const registration = registrations.get(native.jurisdictionId);
      if (!registration || native.electionDate !== '2026-11-03' || native.isPrimary !== false
        || native.isProduction !== true || typeof native.isOfficialResults !== 'boolean')
        throw new Error('Incorrect Idaho locality parent');
      const county = english(registration.localityName), shape = shapeNames.get(nameKey(county));
      const rows = grouped.get(county);
      if (!shape || seen.has(shape.properties.key) || !rows?.length)
        throw new Error('Unmatched Idaho whole-county identity');
      seen.add(shape.properties.key);
      const ballots = count(native.ballotsCast), denominator = count(native.totalVoters);
      if (count(registration.total) !== denominator
        || rows.reduce((sum, row) => sum + count(row.ballots), 0) !== ballots)
        throw new Error('Idaho county parent disagrees with independent ballot report or API');
      const reportedRegistration = rows.reduce((sum, row) => sum + count(row.registered), 0);
      const flags = [];
      if (reportedRegistration !== denominator) flags.push('county_registration_does_not_reconcile_to_ballot_report');
      if (denominator < 25) flags.push('small_or_missing_registration_denominator');
      if (ballots > denominator) flags.push('ballots_exceed_registration');
      output.push({
        code, county, identity: county, fips: shape.properties.key,
        native: { locality_election: native, voter_registration: registration },
        ballots, denominator, reported_pct: flags.length ? null : 100 * ballots / denominator,
        denominator_basis: 'native_total_registered_voters',
        source_update_label: `County as-of: ${native.asOf}; last updated: ${native.lastUpdated}; publish date: ${native.publishDate ?? 'not supplied'}`,
        source_status_literal: `isOfficialResults=${native.isOfficialResults}`,
        reported_units: null, total_units: rows.length, flags,
        source_reporting_label: 'Explicit native whole-county ballotsCast, independently equal to all separate ballot-report rows. '
          + 'The county totalVoters equals the separate county registration API. Pooled absentee/early units are not assigned to precincts. '
          + (flags.length ? `Analysis rate withheld: ${flags.join('; ')}. ` : 'County registered-voter fraction, not population or demographic turnout. ')
          + 'Reporting completeness and certification are not inferred.',
        reference,
      });
    }
    if (seen.size !== expected || grouped.size !== expected || registrations.size !== expected)
      throw new Error('Incomplete Idaho county-parent scope');
  } else {
    const { election, full, turnout } = source;
    if (String(election.electionID) !== '348' || !election.response.date.startsWith('2026-11-03T')
      || String(full.ElectionData.ElectionID) !== '348' || String(turnout.electionID) !== '348'
      || election.versionID !== turnout.versionID || election.lastUpdated !== turnout.lastUpdated
      || typeof election.isOfficial !== 'boolean'
      || election.isOfficial !== full.ElectionData.IsOfficial || election.isOfficial !== turnout.isOfficial)
      throw new Error('Incorrect or mixed North Dakota election versions');
    const parents = full.TurnoutData.Locations, independent = turnout.response.locations;
    const house = full.ContestData.filter(row => row.ContestName === 'Representative in Congress');
    if (house.length !== 1 || Object.keys(parents).length !== expected
      || Object.keys(independent).length !== expected || grouped.size !== expected)
      throw new Error('Incomplete North Dakota county-parent scope');
    let total = 0;
    for (const [fips, native] of Object.entries(parents)) {
      const shape = shapes.get(fips), other = independent[fips], named = house[0].Locations[fips];
      const rows = grouped.get(fips);
      if (!shape || !other || !named || native.LocationID !== fips || other.locationID !== fips
        || named.LocationID !== fips || nameKey(named.LocationName) !== nameKey(shape.properties.name)
        || !rows?.length || Object.keys(native.Locations).length !== rows.length)
        throw new Error('Unmatched North Dakota county/precinct identity');
      const ballots = allBallots(native);
      if (count(other.totalBallotsCast) !== ballots || rows.reduce((sum, row) => sum + count(row.ballots), 0) !== ballots
        || rows.some(row => native.Locations[row.precinct]?.LocationID !== row.precinct
          || allBallots(native.Locations[row.precinct]) !== row.ballots))
        throw new Error('North Dakota county parent disagrees with independent ballot sources');
      total += ballots;
      output.push({
        code, county: named.LocationName, identity: fips, fips, native,
        ballots, denominator: null, reported_pct: null, denominator_basis: 'electorate_not_qualified',
        native_printed_pct: `${native.VotePercent}% (native printed field; analysis rate withheld)`,
        source_update_label: `${election.lastUpdated}; native version ${election.versionID}`,
        source_status_literal: `IsOfficial=${full.ElectionData.IsOfficial}`,
        reported_units: native.PrecinctsReporting, total_units: native.TotalPrecincts,
        flags: ['native_registeredVoters_field_not_qualified_as_registration'],
        source_reporting_label: 'Explicit TotalBallotsCast county parent, equal to the independent turnout API and all native precinct ballots. '
          + 'The API RegisteredVoters field is retained literally in native_record but is not treated as a registration count. '
          + 'No county or precinct analysis rate is enabled. Reporting completeness is not certification.',
        reference,
      });
    }
    if (total !== count(full.TurnoutData.TotalBallotsCast) || total !== count(election.turnout.totalBallotsCast)
      || total !== count(turnout.turnout.totalBallotsCast))
      throw new Error('North Dakota county/state ballot parents disagree');
  }
  return output;
}

export function loadNativeCountyParents(pointer = read('public/precinct-results.json')) {
  const countyPointer = read('public/county-results.json');
  const countyIndex = read(`${countyPointer.data_directory}/index.json`);
  if (countyIndex.year !== 2026 || countyIndex.boundary_reference_year !== 2026)
    throw new Error('Incorrect native county reference year');
  const output = [];
  for (const [code, suffix] of [['ID', '20261105-idaho-01'], ['ND', '20261105-north-dakota-02']]) {
    const snapshot = pointer.additional_snapshots.find(row => row.data_directory.endsWith(suffix));
    if (!snapshot) throw new Error(`Missing native county-parent source: ${code}`);
    const checksums = read(`${snapshot.data_directory}/checksums.json`);
    const original = name => {
      const raw = readFileSync(`${snapshot.data_directory}/${name}`), expected = checksums[name];
      if (!expected || expected.bytes !== raw.length || expected.sha256 !== digest(raw))
        throw new Error(`Changed native county-parent input: ${name}`);
      return JSON.parse(gunzipSync(raw));
    };
    const coverage = countyIndex.coverage[code], url = new URL(coverage.file);
    if (url.hostname !== 'raw.githubusercontent.com'
      || !/^\/hanshanley\/margin_of_error\/[0-9a-f]{40}\/data\/county-results\//.test(url.pathname))
      throw new Error('Unpinned native county reference URL');
    const path = url.pathname.split('/').slice(4).join('/');
    const raw = readFileSync(path), decoded = gunzipSync(raw);
    if (coverage.sha256 !== digest(raw) || coverage.uncompressed_sha256 !== digest(decoded))
      throw new Error('Changed native county reference geometry');
    const sourceFile = code === 'ID' ? 'count-review/originals/public-response-02.json.gz'
      : 'originals/full-results.json.gz';
    const source = code === 'ID' ? original(sourceFile) : {
      full: original(sourceFile), election: original('originals/election.json.gz'),
      turnout: original('originals/turnout.json.gz'),
    };
    const reference = { path, url: url.href, sha256: digest(raw),
      uncompressed_sha256: digest(decoded), boundary_year: 2026, counties: coverage.counties };
    for (const parent of reviewCountyParents(code, source, original('participation.json.gz'), JSON.parse(decoded), reference))
      output.push({ ...parent, snapshot, sourceFile });
  }
  return output;
}

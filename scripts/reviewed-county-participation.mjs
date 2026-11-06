import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { parse } from 'csv-parse/sync';

const profiles = [
  ['pennsylvania-centre-20261106-01', 'ballots', 'registered_voters', 'registered_voter_rate_literal', 'PA', ['Centre']],
  ['pennsylvania-berks-20261105-01', 'ballots_cast', 'registered_voters', null, 'PA', ['Berks']],
  ['pennsylvania-northampton-20261105-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Northampton']],
  ['pennsylvania-lancaster-20261105-01', 'ballots', 'registrations', 'native_pdf_turnout_percent', 'PA', ['Lancaster']],
  ['pennsylvania-three-county-20261105-01', 'ballots_counted', 'registered_voters', 'native_printed_turnout', 'PA', ['Chester', 'Franklin', 'Lehigh']],
  ['pennsylvania-montgomery-20261105-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout_pct', 'PA', ['Montgomery']],
  ['pennsylvania-bucks-20261105-01', 'ballots_counted', 'registered_voters', 'native_printed_turnout', 'PA', ['Bucks']],
  ['pennsylvania-monroe-20261105-01', 'total_ballots_tabulated', 'eligible_registered_voters', 'native_printed_turnout_pct', 'PA', ['Monroe']],
  ['pennsylvania-fulton-20261106-01', 'accounted_ballots', 'registered_voters', 'native_printed_turnout', 'PA', ['Fulton']],
  ['pennsylvania-cumberland-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Cumberland']],
  ['pennsylvania-adams-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Adams']],
  ['pennsylvania-lebanon-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Lebanon']],
  ['pennsylvania-blair-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Blair']],
  ['pennsylvania-armstrong-20261106-01', 'reported_voters_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Armstrong']],
  ['pennsylvania-wayne-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Wayne']],
  ['pennsylvania-jefferson-20261106-01', 'reported_voters_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Jefferson']],
  ['pennsylvania-clarion-20261106-01', 'reported_voters_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Clarion']],
  ['pennsylvania-cameron-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Cameron']],
  ['pennsylvania-carbon-20261106-01', 'reported_voters_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Carbon']],
  ['pennsylvania-elk-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Elk']],
  ['pennsylvania-forest-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Forest']],
  ['pennsylvania-potter-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Potter']],
  ['pennsylvania-mifflin-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Mifflin']],
  ['pennsylvania-perry-20261106-01', 'ballots_cast', 'registered_voters', 'native_printed_turnout', 'PA', ['Perry']],
  ['dc-delegate-county-20261105-01', 'ballots_cast', 'registered_voters', null, 'DC', ['District of Columbia']],
];
/** @returns {Record<string, string>[]} */
const csv = path => parse(readFileSync(path, 'utf8'), { columns: true, bom: true, skip_empty_lines: true });

function loadNewJerseyParticipation(reviews) {
  const id = 'new-jersey-periodic-participation-20261106-02';
  const matches = reviews.filter(review => review.id === id);
  if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
  const review = matches[0], directory = resolve(review.data_directory);
  const required = {
    'county-participation.csv': 'a9e1e664ee56675219dbe69355947121b9b6e08fc81b355e899278fbddce172d',
    'native-source-pages.csv': '36699e8025c42379ad5e7d1297777609a75dd593d88b8a63cb0bda534e22a7fe',
    'native-counting-qualifications.csv': '342cb5983e5fbf52f3f6f9aa3d5bc2018a2ade518d8ca230bc42eb7ce849e2ce',
    'audit.json': 'bf47bfe6b959e57123eec0ab0342b235354ac56e91d63e7b4c4dc0897ae48bd0',
  };
  for (const [file, digest] of Object.entries(required)) {
    if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
      throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
  }
  const rows = csv(resolve(directory, 'county-participation.csv'));
  const pages = csv(resolve(directory, 'native-source-pages.csv'));
  const notes = csv(resolve(directory, 'native-counting-qualifications.csv'));
  const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
  if (id === 'pennsylvania-perry-20261106-01') {
    for (const [file, digest] of Object.entries({
      'county-participation.csv': '710a64c3da639a698014f2e0766c5a40c7a9cdf7e7ee4832ad3b4442d8bb5499',
      'native-source-pages.csv': '74624adcd3146bb4527e883f4ac178b3c68cec1a89478b56a978d40be09103d3',
      'audit.json': 'dd9cf208f356d4bab5b69971eab10feb020960331b89d38b5edf33bfe6f8f1bb',
    })) {
      if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
        throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
    }
  }
  if (rows.length !== 21 || audit.usable_counties.length !== 19
    || audit.withheld_counties.map(row => row.county).join('|') !== 'Essex|Hudson')
    throw new Error(`Incomplete reviewed county source: ${id}`);
  return rows.filter(native => audit.usable_counties.includes(native.county)).map(native => {
    const ballots = Number(native.reported_participation_subtotal);
    const denominator = native.registered_voters === '' ? null : Number(native.registered_voters);
    const nativeSummary = native.county === 'Cape May';
    const modes = ['early_voting_votes_cast', 'election_day_votes_cast', 'mail_ballots_tallied'];
    if (native.year !== '2026' || native.state_code !== 'NJ' || native.withheld_reason !== ''
      || !Number.isSafeInteger(ballots) || ballots <= 0
      || modes.some(field => !/^\d+$/.test(native[field]))
      || modes.reduce((total, field) => total + Number(native[field]), 0) !== ballots
      || (nativeSummary ? denominator !== 76899 || native.source_page !== '2'
        || native.registration_source_page !== '2' || native.periodic_source_page !== '1'
        || native.native_participation_measure_literal !== 'Ballots Cast - Total'
        : denominator !== null || native.native_participation_measure_literal !== ''))
      throw new Error(`Invalid reviewed county participation: ${id} / ${native.county}`);
    const nativeSourceUpdates = pages.filter(row => row.county === native.county).map(row => ({
      source: `${row.source_role} page ${row.source_page}`, native_update_literal: row.source_update_literal,
      other_update_literals: JSON.parse(row.other_update_literals_json), declared_timezone: row.declared_timezone,
    }));
    return {
      year: 2026, state_code: 'NJ', county_id: `reviewed:NJ:${native.county}`, county: native.county,
      geography_level: 'county', ballots, denominator, denominator_basis: 'native_registered_voters',
      participation_measure_kind: nativeSummary ? 'native_ballot_total' : 'derived_reported_mode_subtotal',
      ...(nativeSummary ? { participation_measure_literal: native.native_participation_measure_literal } : {
        participation_measure_label: 'Derived EV + ED + mail-tallied subtotal; no provisional-issued counts added',
      }),
      reported_pct: denominator === null ? null : 100 * ballots / denominator,
      native_printed_pct: native.native_printed_turnout || null, source_status_literal: native.native_status_literal,
      reported_units: null, total_units: null, source_rows: 0, maps_approved: false,
      review_id: id, native_record: native, native_source_updates: nativeSourceUpdates,
      source_update_label: nativeSourceUpdates.map(row =>
        `${row.source}: ${row.native_update_literal || 'not supplied'}`
        + `${row.other_update_literals.length ? `; other native timestamps: ${row.other_update_literals.join('; ')}` : ''}`
        + ` (${row.declared_timezone || 'timezone not declared'})`).join('; '),
      source_reporting_label: [
        `Periodic participation modes: PDF page ${native.periodic_source_page}.`,
        ...(nativeSummary ? ['Native ballot total and registrations: attached summary, PDF page 2.'] : []),
        ...notes.filter(row => row.county === native.county).map(row => `Native note (page ${row.source_page}): ${row.literal}`),
        ...JSON.parse(native.counting_qualifications_json),
      ].join('; '),
      source_url: `${review.base_url}county-participation.csv`,
      complete_download_url: review.complete_download_url,
      quality: [
        'Reviewed unofficial participation snapshot, not certification, completed statewide counting or demographic turnout.',
        'Issued, received and pending ballots are separate processing measures, not additions to the counted modes.',
        nativeSummary ? 'Native Ballots Cast - Total and registrations are separately verified on PDF page 2.'
          : 'Derived reported mode subtotal, not a native all-mode ballot total or a unique-voter estimate. Registrations and turnout rate are not supplied.',
        'Essex and Hudson remain withheld in the complete 21-county query. County mapping is not approved; undeclared timezones are not inferred.',
      ],
    };
  });
}

export function loadReviewedCountyParticipation(reviews) {
  const observations = [], seen = new Set();
  for (const [id, ballotField, denominatorField, printedField, code, names] of profiles) {
    const matches = reviews.filter(review => review.id === id);
    if (matches.length !== 1) throw new Error(`Missing or duplicated reviewed county source: ${id}`);
    const review = matches[0], directory = resolve(review.data_directory);
    if (id === 'pennsylvania-jefferson-20261106-01') {
      for (const [file, digest] of Object.entries({
        'county-participation.csv': 'd9674bfaa0beaf1e2e0b1174a444e6f408dc4e95eb9e1544119f825f8b7cbb2e',
        'native-source-pages.csv': 'd010adc9bcf8508d761dbda77d99ce89431f07714e9d9d02032756a4a2dfe44f',
        'audit.json': '9eedaeba9c068df9e3258ca6bb3e5b2f553f3b956c531f2aa51eaf045d66d375',
      })) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    if (id === 'pennsylvania-clarion-20261106-01') {
      for (const [file, digest] of Object.entries({
        'county-participation.csv': '2ffea414bf7f6469e4f341efde85d6627079dbbdda02ab7f24db0e518a5bb76c',
        'native-source-pages.csv': '1d2a89ba763b4e9c0f987673c50d286926cf5d2f2ae599f56385b6ae49529c12',
        'audit.json': 'f4b13e48e86bae053332529e2a200c3d93cba6b489f9591bcf5be12186edc308',
      })) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    if (['pennsylvania-cameron-20261106-01', 'pennsylvania-carbon-20261106-01'].includes(id)) {
      const hashes = id === 'pennsylvania-cameron-20261106-01' ? {
        'county-participation.csv': 'b2cb38ef8cd0738ac69b53911c0f59ff2bd09f6c82b8c5163455bdfd3059d06e',
        'native-source-pages.csv': '04c094ab73e1bf1b13a51de3971e2ffb957aa26c240b5df1afe4a4996a6cb425',
        'audit.json': '4900f852c745f0f514fc0879fd55d781344b634178ea001f4b1512cc9bd471a0',
      } : {
        'county-participation.csv': '68ec38689b3af14ae221a3c577aa3aa3e08d05313d6cb0af39480a212642b607',
        'native-source-pages.csv': '5cc7fc5a94e644830836ce5f75aa187c10975f621741d030919211d6bd131a2b',
        'audit.json': '056db770be0a8c4cdc50f3986b0fecf9f8a87331b999b0df0f37482d64aef1c7',
      };
      for (const [file, digest] of Object.entries(hashes)) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    const audit = JSON.parse(readFileSync(resolve(directory, 'audit.json'), 'utf8'));
    if (id === 'pennsylvania-mifflin-20261106-01') {
      for (const [file, digest] of Object.entries({
        'county-participation.csv': 'fc44988e299256ae5fccb9e33a9f0eb049a37f184c2e7f9c3fb64d8b61f95eec',
        'native-source-pages.csv': 'a07daeade5b5a5537ee2fbe6d859e5f8b8d9c15e3d0415888d8ba85cd47ef834',
        'audit.json': '002cca74c5cb18d58c566bd591acc8b81f6fae463f28989e06a63565ac714436',
      })) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    if (id === 'pennsylvania-potter-20261106-01') {
      for (const [file, digest] of Object.entries({
        'county-participation.csv': '32e83977ce7b6679afbccaca04b775dad071abdb26a86497fbeebd66d132bac1',
        'native-source-pages.csv': 'ddd87ae40fef5ecb84f6412fe34b973efe83741823891f696c386de168bd8b00',
        'audit.json': '9a3290b08c635d69d1ead5b2fc68e59cfaa73fb77efe8e49ff53c4cf7a27647d',
      })) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    if (['pennsylvania-elk-20261106-01', 'pennsylvania-forest-20261106-01'].includes(id)) {
      const hashes = id === 'pennsylvania-elk-20261106-01' ? {
        'county-participation.csv': '9f3623d46f0df591b03a21fe759d9705228db9de0ab51e74230cd09a1fc34c65',
        'native-source-pages.csv': 'a0e7ac0ce6e5c364896d148ee9cf131315dfd4787f01cbc04ce435ace179176f',
        'audit.json': 'b3aa21eff714afb9084fb24974aa9b761b3d64ff5c5ebd4fc414001f3b9fd076',
      } : {
        'county-participation.csv': 'db9870d10c5f72159ee759a3c725d98635a89a96f7854638556791cee182a8dd',
        'native-source-pages.csv': 'cb36428e38f0ccac450b83f2b3b4622d79fa4193fa36937c99b4184278ce7604',
        'audit.json': 'fbcfe94d957be9ec41f35c459c0fb35c55629dcf89c8bc85bafff849bdc5b021',
      };
      for (const [file, digest] of Object.entries(hashes)) {
        if (createHash('sha256').update(readFileSync(resolve(directory, file))).digest('hex') !== digest)
          throw new Error(`Invalid reviewed county participation: ${id} / ${file}`);
      }
    }
    const rows = csv(resolve(directory, 'county-participation.csv'));
    if (rows.length !== names.length) throw new Error(`Incomplete reviewed county source: ${id}`);
    for (const native of rows) {
      const county = native.county ?? native.geography, identity = `${code}|${county}`;
      const nativeMifflinSummary = id === 'pennsylvania-mifflin-20261106-01';
      const unusableNativeZero = id === 'pennsylvania-lebanon-20261106-01' || nativeMifflinSummary;
      const excludesProvisionals = id === 'pennsylvania-armstrong-20261106-01';
      const nativeClarionSummary = id === 'pennsylvania-clarion-20261106-01';
      const nativeCameronSummary = id === 'pennsylvania-cameron-20261106-01';
      const nativeCarbonSummary = id === 'pennsylvania-carbon-20261106-01';
      const nativeElkSummary = id === 'pennsylvania-elk-20261106-01';
      const nativeForestSummary = id === 'pennsylvania-forest-20261106-01';
      const nativePotterSummary = id === 'pennsylvania-potter-20261106-01';
      const nativePerrySummary = id === 'pennsylvania-perry-20261106-01';
      const nativeVotersCast = excludesProvisionals || id === 'pennsylvania-jefferson-20261106-01'
        || nativeClarionSummary || nativeCarbonSummary;
      const nativeCountyHeader = id === 'pennsylvania-wayne-20261106-01';
      const ballots = Number(native[ballotField]);
      const denominator = unusableNativeZero ? null : Number(native[denominatorField]);
      const invalidDenominator = unusableNativeZero
        ? nativeMifflinSummary
          ? native[denominatorField] !== '0' || native.registered_turnout_pct !== ''
            || native.native_printed_turnout !== '0.00%'
          : native[denominatorField] !== '' || native.native_registered_voters !== '0'
            || native.registered_turnout_percent !== '' || native.native_printed_turnout !== '0.00%'
        : !/^\d+$/.test(native[denominatorField]) || !Number.isSafeInteger(denominator)
          || denominator <= 0 || ballots > denominator;
      if (native.year !== '2026' || native.state_code !== code || !names.includes(county) || seen.has(identity)
        || !/^\d+$/.test(native[ballotField]) || !Number.isSafeInteger(ballots)
        || (unusableNativeZero && ballots <= 0) || invalidDenominator
        || (excludesProvisionals && (native.native_participation_measure_literal !== 'Voters Cast'
          || native.provisional_voters_cast !== ''
          || native.native_status_literal !== '2026 General Election Unofficial Results w/o PROV'))
        || (nativePerrySummary && (native.native_participation_measure_literal !== 'Total Ballots Cast'
          || native.source_status_literal !== '' || native.parent_status_literal !== 'Unofficial'
          || native.election_day_ballots !== '' || native.mail_ballots !== '' || native.provisional_ballots !== ''
          || native.native_fips !== '' || native.maps_approved !== 'False' || native.counting_complete !== 'False'
          || ballots !== audit.native_ballots_cast || denominator !== audit.native_registered_voters))
        || (nativeCountyHeader && (native.native_participation_measure_literal !== 'Total Ballots Cast'
          || native.native_status_literal !== ''
          || native.native_parent_status_literal !== '2026 General Election Unofficial Results'
          || native.election_day_ballots !== '' || native.mail_ballots !== '' || native.provisional_ballots !== ''
          || ballots !== audit.county_participation.ballots_cast
          || denominator !== audit.county_participation.registered_voters)))
        throw new Error(`Invalid reviewed county participation: ${id} / ${county}`);
      seen.add(identity);
      const sourceAudit = audit.counties?.find(row => row.county === county) ?? audit;
      const printed = printedField ? native[printedField] : null;
      const printedPct = printed ? printed.endsWith('%') ? printed : `${printed}%` : null;
      const reporting = [
        ...(sourceAudit.native_reporting_qualifications ?? []),
        ...JSON.parse(native.counting_qualifications_json || '[]'),
        ...[native.mail_counting_status, native.in_person_counting_status,
          native.reporting_basis && `Native reporting basis: ${native.reporting_basis}`].filter(Boolean),
      ];
      if (nativeClarionSummary) reporting.push(
        '40 of 40 reported precincts does not establish completed ballot counting.',
        'Election Day, mail and provisional participation are not separately reported; missing mode counts are not zero.',
        'Foxburg referendum Times Cast 82/116 is a separate electorate, not additional county participation.',
        'Native Total Votes excludes Unresolved Write-In; contest participation-minus-choice residuals remain unclassified.');
      if (nativeCameronSummary) reporting.push(
        'Native Ballots Cast - Total 1,624 = 1,305 Election Day + 319 Mail; provisional participation is absent, not zero.',
        '10 of 10 Election Day and Absentee/Early precincts reported; zero complete and ten partially reported does not establish completed ballot counting.',
        'Separate Act88 returned 324 / recorded 320 are not counted Mail 319; differences remain unexplained and unallocated.',
        'The Act88 Federal Voter filter is preserved; its source supplies no report clock or timezone, and the 12:01 link label does not supply one.',
        'Not Assigned is nested within Write-In Totals, not additional votes; one blank ballot is already within Ballots Cast.');
      if (nativeCarbonSummary) reporting.push(
        'Native Voters Cast 24,840 = 20,375 Election Day + 4,465 Mail-In + explicit zero Provisional.',
        '51 of 51 reported precincts does not establish completed ballot counting; the earlier Official Zero Report is a separate observation, not current participation.',
        'All 51 statement units reconcile to the county; both county footers and both Cumulative zero/N/A containers remain separate and are not added.',
        'Kidder referendum Times Cast 807/1,457 is a separate electorate, not additional county participation.',
        'Mode-specific registrations and native overvotes/undervotes are absent; 350/381/288/30 participation-minus-choice residuals remain unclassified.');
      if (nativeElkSummary) reporting.push(
        'Native Ballots Cast - Total 11,742 = 9,725 Election Day + 2,017 Absentee/Mail-In + explicit zero Provisional; five blank ballots are already included.',
        'All 29 units are partially reported and zero complete; reported precincts do not establish completed ballot counting.',
        'All 29 unit headers and 87 contests reconcile; ST MARYS 4TH prints 55.10% while its 319/579 fraction rounds to 55.09%, and both remain distinct.',
        'Separate filtered Act88 returned 2,035 / recorded 2,018 are not counted mail 2,017; differences 18/1 remain unexplained. Its election date and filename do not supply a report clock.',
        'The index calls links Official while the reports say UNOFFICIAL RESULTS; the contradictory 11/03/2026 22:08 PM clock is preserved without repair.',
        'Native summary overvotes/undervotes are absent; derived unit sums remain separate. The Act88 scan is visually reviewed, not a two-engine transcription.');
      if (nativeForestSummary) reporting.push(
        'Native Ballots Cast - Total 1,877 / 3,275 registrations is on physical summary page 2, which prints Page 1 of 2; physical page 1 prints Page 2 of 2.',
        'All nine units are partially reported and zero complete; reported precincts do not establish completed ballot counting.',
        'Election Day, mail and provisional participation are absent, not zero; separate 311 mail-in absentee receipts by 8 p.m. are not counted mail ballots.',
        'All eleven scanned pages and magnified choice panels were visually reviewed; both full text engines are empty, not independent transcriptions.',
        'Native county summary has overvotes/undervotes but lacks Total Votes Cast/Contest Totals; units lack all four rows and their derived residuals remain unclassified.',
        'The contradictory 11/03/2026 20:56 PM clock is preserved without repair or inferred timezone.');
      if (nativePotterSummary) reporting.push(
        'Native Ballots Cast - Total 6,244 = 5,389 Election Day + 855 Mail + explicit zero Provisional; two blank ballots are already included.',
        'All 32 units are partially reported and zero complete; the native Election Day complete column nevertheless says 32. This contradiction is preserved, not repaired or interpreted as completed ballot counting.',
        'All 32 unit participation headers and 96 contests reconcile in every reported counting mode.',
        'Separate 871 mail-in/absentee receipts by 8 p.m. are not counted mail 855; the difference 16 remains unexplained and unallocated. The receipt notice supplies no report clock or timezone.',
        'County named write-ins are breakdowns within Write-In Totals, not additional votes; unit named breakdowns are absent, not zero or county names allocated to units.',
        'Native unit Total Votes Cast and Contest Totals rows are absent; derived totals remain separate. Summary and statement clocks remain distinct without an inferred timezone.');
      if (nativeMifflinSummary) reporting.push(
        'Native Ballots Cast - Total 14,439 = 12,017 Election Day + 2,422 Mail + explicit zero Provisional; six blank ballots are already included.',
        'Native registrations zero and printed 0.00% do not establish zero participation; the calculated registration-based rate is unavailable.',
        'All 26 units are partially reported and zero complete; all 104 unit contests and five county contests reconcile without establishing completed ballot counting.',
        'The 85th and 171st Assembly electorates are separate 4,409/10,030-ballot subsets, not the whole county assigned to either contest.',
        'The parent receipt notice literally says Primary Election Day, November 3, 2026 despite the General section; 2,435 receipts are not counted mail 2,422, and the difference 13 remains unexplained.',
        'Not Assigned is nested within Write-In Totals, not additional votes; summary and statement clocks remain distinct without an inferred timezone.');
      if (nativePerrySummary) reporting.push(
        'Native Total Ballots Cast 18,064 / 31,391 registered voters, printed 57.55%; candidate votes are not ballots.',
        'All 31 actual unit participation rows reconcile across 124 unit-contest headers; four All Precincts aggregate headers are separate, not additional units.',
        '31 of 31 reported precincts does not establish completed ballot counting.',
        'Election Day, mail and provisional ballot participation are absent, not zero; ED/MI/PR are candidate-vote columns, and explicit zero PR votes do not establish zero provisional ballots.',
        'The complete scoped query includes both county candidate summaries and all unit participation rows; unresolved unit candidate cells are explicitly outside this query, not imputed or called absent.',
        'Native party labels are absent and not inferred from candidate names; county choice/overvote/undervote accounting reconciles separately.',
        'All 24 entire scanned pages were independently OCRed locally; both PDF text engines are empty. All 31 first participation headers, reporting lines and both whole county summaries were directly visually reviewed.',
        'Unofficial status comes from the declaring county page, not a separate PDF status literal; summary and statement clocks remain distinct without an inferred timezone.');
      for (const field of ['native_group_reporting_status_json', 'native_precinct_reporting_status_json']) {
        for (const row of JSON.parse(native[field] || '[]'))
          reporting.push(`${row.groupName.map(label => label.text).join(' / ')}: `
            + `${row.reportingStatusClientTextKey}; value ${row.value === null ? 'not supplied' : row.value}`);
      }
      const updates = ['source_update_literal', 'source_pdf_update_literal', 'source_json_exported_utc',
        'source_json_generated_utc', 'as_of_utc', 'publish_date_utc']
        .filter(field => native[field]).map(field => `${field}: ${native[field]}`);
      if (audit.native_status_and_update) updates.push(audit.native_status_and_update);
      if (audit.participation_record_edit_ms)
        updates.push(`Native participation edit (UTC milliseconds): ${audit.participation_record_edit_ms.join(', ')}`);
      let nativeSourceUpdates = [];
      if (id === 'pennsylvania-centre-20261106-01') {
        nativeSourceUpdates = csv(resolve(directory, 'native-source-updates.csv'));
      } else if (['pennsylvania-cumberland-20261106-01', 'pennsylvania-adams-20261106-01',
        'pennsylvania-lebanon-20261106-01', 'pennsylvania-blair-20261106-01',
        'pennsylvania-armstrong-20261106-01', 'pennsylvania-wayne-20261106-01',
        'pennsylvania-jefferson-20261106-01', 'pennsylvania-clarion-20261106-01',
        'pennsylvania-cameron-20261106-01', 'pennsylvania-carbon-20261106-01',
        'pennsylvania-elk-20261106-01', 'pennsylvania-forest-20261106-01',
        'pennsylvania-potter-20261106-01', 'pennsylvania-mifflin-20261106-01',
        'pennsylvania-perry-20261106-01'].includes(id)) {
        nativeSourceUpdates = [...new Map(csv(resolve(directory, 'native-source-pages.csv')).map(row =>
          [row.source_report ?? 'county_report', { source: row.source_report ?? 'county_report', native_update_literal: row.source_update_literal,
            declared_timezone: row.declared_timezone }])).values()];
      }
      updates.push(...nativeSourceUpdates.map(row =>
        `${row.source}: ${row.native_update_literal} (${row.declared_timezone || 'timezone not declared'})`));
      const quality = [
        'Reviewed local snapshot, not final certification, statewide coverage, eligible-population or demographic turnout.',
        'Source timestamps retain their native labels; unprovided timezones are not inferred. County mapping is not approved.',
      ];
      if (id === 'pennsylvania-berks-20261105-01') quality.push(...audit.qualifications.slice(2, 4));
      if (native.ballot_receipt_notice_literal || native.act88_mail_ballots_received_by_election_day_deadline)
        quality.push('Received mail ballots are a separate processing count, not the reported ballot total.');
      if (sourceAudit.native_csv_ballot_count_conflicts?.length)
        quality.push('Native contest-ballot zeroes conflict with positive unit ballots; those zeroes are not used as county ballots.');
      if (native.native_status_literal === '' && !native.native_parent_status_literal)
        quality.push('No native result-status literal was supplied; no native status is inferred.');
      if (nativeCountyHeader || nativePerrySummary)
        quality.push('Result status comes from the declaring county page; the PDF supplies no separate status literal.');
      if (id === 'pennsylvania-montgomery-20261105-01') quality.push(audit.limitations[0], audit.limitations[2]);
      if (id === 'dc-delegate-county-20261105-01') quality.push(
        'Citywide county-equivalent participation, separate from the 435 voting House districts.',
        `${native.unresolved_ballot_accounting_difference} ballots remain unresolved in the separate delegate accounting; not filled or allocated.`,
        audit.limitations[1], audit.limitations[4]);
      observations.push({
        year: 2026, state_code: code, county_id: native.county_fips || `reviewed:${code}:${county}`,
        county, geography_level: native.geography_level || 'county', ballots, denominator,
        ...(nativeVotersCast || nativeCameronSummary || nativeElkSummary || nativeForestSummary || nativePotterSummary || nativeMifflinSummary || nativePerrySummary
          ? { participation_measure_literal: native.native_participation_measure_literal } : {}),
        denominator_basis: 'native_registered_voters', reported_pct: denominator === null ? null : 100 * ballots / denominator,
        native_printed_pct: printedPct, source_status_literal: nativePerrySummary
          ? native.parent_status_literal : nativeCountyHeader
            ? native.native_parent_status_literal : nativeClarionSummary || nativeCameronSummary || nativeCarbonSummary
            || nativeElkSummary || nativeForestSummary || nativePotterSummary || nativeMifflinSummary
            ? native.source_status_literal : native.native_status_literal ?? native.result_status ?? null,
        reported_units: null, total_units: null, source_rows: 0, maps_approved: false,
        review_id: id, native_record: native, native_source_updates: nativeSourceUpdates,
        source_update_label: updates.join('; ') || 'Not supplied',
        source_reporting_label: reporting.join('; ') || 'Counting completion not established by this participation table.',
        source_url: `${review.base_url}county-participation.csv`, complete_download_url: review.complete_download_url, quality,
      });
    }
  }
  return [...observations, ...loadNewJerseyParticipation(reviews)];
}

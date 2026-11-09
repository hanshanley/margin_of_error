import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';

const VERSION = 'data/county-source-reviews/20261109-colorado-returned-01';
const digest = value => createHash('sha256').update(value).digest('hex');
const key = value => value.toLowerCase().replace(/ county$/, '').replace(/\s/g, '');
const count = value => {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Invalid Colorado native count; missing is not zero');
  return value;
};
const frames = [
  ['All_Returned_Ballots_By_County', 'ALL RETURNED BALLOTS - MAIL AND IN PERSON COMBINED', 2761449],
  ['Returned_Mail_Ballots_By_County', 'RETURNED MAIL BALLOTS', 2618985],
  ['In_Person_Ballots_By_County', 'IN PERSON BALLOTS', 142464],
];

export function reviewColoradoCountyReturns({ inputs, sheets, geometry }) {
  if (inputs.year !== 2026 || inputs.state_code !== 'CO' || inputs.rates_approved !== false
    || inputs.cast_ballot_count_qualified !== false || inputs.unique_voter_count_qualified !== false
    || inputs.precincts_approved !== false || inputs.source_period_end !== '11:59 PM November 5, 2026'
    || inputs.publication_date !== '2026-11-06' || inputs.source_timezone !== null
    || inputs.reference.boundary_year !== 2026 || geometry.features.length !== 64
    || new Set(geometry.features.map(f => f.properties.key)).size !== 64
    || geometry.features.some(({ properties: p }) =>
      p.state_code !== 'CO' || p.boundary_year !== 2026 || !/^08\d{3}$/.test(p.key)))
    throw new Error('Unqualified Colorado measure, clock, rate or full county reference');
  const identities = new Map(geometry.features.map(f => [key(f.properties.name), f.properties]));
  if (identities.size !== 64 || sheets.length !== 7 || new Set(sheets.map(s => s.name)).size !== 7)
    throw new Error('Incomplete Colorado county identities or original worksheets');
  const reviewed = {}, parents = {};
  for (const [name, title, expected] of frames) {
    const sheet = sheets.find(s => s.name === name);
    if (!sheet) throw new Error('Missing Colorado native mode worksheet');
    const cells = Object.fromEntries(sheet.native_cells.map(c => [c.address, c.value]));
    const headers = [...'BCDEFGHIJKLM'].map(c => cells[`${c}2`]);
    if (cells.A1 !== title || headers.at(-1) !== 'Grand Total' || new Set(headers).size !== 12)
      throw new Error('Changed Colorado native mode or party fields');
    const rows = new Map();
    let parent;
    for (let n = 3; n <= 67; n++) {
      const county = cells[`A${n}`];
      const record = Object.fromEntries([...'BCDEFGHIJKLM'].map((c, i) =>
        [headers[i], count(cells[`${c}${n}`])]));
      if (headers.slice(0, -1).reduce((sum, h) => sum + record[h], 0) !== record['Grand Total'])
        throw new Error('Colorado native party cells disagree with their explicit total');
      if (county === 'Grand Total') {
        parent = record;
        if (n !== 67) throw new Error('Incomplete Colorado county mode query');
        break;
      }
      if (typeof county !== 'string' || !identities.has(key(county)) || rows.has(key(county)))
        throw new Error('Unmatched or duplicate Colorado native county');
      rows.set(key(county), { county, native_excel_row: n, native_record: record });
    }
    if (rows.size !== 64 || parent?.['Grand Total'] !== expected
      || headers.some(h => [...rows.values()].reduce((sum, r) => sum + r.native_record[h], 0) !== parent[h]))
      throw new Error('Colorado counties disagree with the separate native state parent');
    reviewed[name] = rows;
    parents[name] = parent;
  }
  const counties = [...reviewed.All_Returned_Ballots_By_County].map(([identity, original]) => {
    const native = Object.fromEntries(frames.map(([name]) => [name, reviewed[name].get(identity)]));
    const all = native.All_Returned_Ballots_By_County.native_record;
    if (Object.keys(all).some(p => all[p] !== native.Returned_Mail_Ballots_By_County.native_record[p]
      + native.In_Person_Ballots_By_County.native_record[p]))
      throw new Error('Colorado native mode cells disagree; do not repair or allocate');
    const shape = identities.get(identity);
    return {
      year: 2026, state_code: 'CO', county: shape.name, county_fips: shape.key,
      source_count: all['Grand Total'], denominator: null, reported_pct: null,
      native_record: native, reference_geometry: inputs.reference,
      participation_measure_label: 'Returned and processed ballots (native all-returned total)',
      source_count_qualified: true, cast_ballot_count_qualified: false, unique_voter_count_qualified: false,
      source_url: inputs.source_url, complete_download_url: inputs.complete_download_url,
      source_update_label: `${inputs.source_period_end}; timezone not supplied. Published November 6, 2026.`,
      source_status_literal: 'Preliminary returned-and-processed ballot activity; not final or certified',
      source_reporting_label: 'Native ALL RETURNED BALLOTS - MAIL AND IN PERSON COMBINED, not researcher-added modes. '
        + 'Returned/processed is not cast, accepted, counted, certified, final or unique people. '
        + 'Native party categories are registration affiliation, not candidate choice. County denominators and rates withheld.',
    };
  });
  return { counties, original_state_mode_parents: parents,
    summary: { county_queries: 64, county_counts: 64, native_mode_frames: 3, analysis_rates_approved: false } };
}

export function loadColoradoCountyReturns() {
  const inputs = JSON.parse(readFileSync(`${VERSION}/inputs.json`, 'utf8'));
  const verified = path => {
    const body = readFileSync(path), receipt = inputs.files[path];
    if (!receipt || body.length !== receipt.bytes || digest(body) !== receipt.sha256)
      throw new Error(`Changed sufficient Colorado source input: ${path}`);
    return body;
  };
  for (const path of Object.keys(inputs.files)) verified(path);
  const geometry = gunzipSync(verified(inputs.reference.path));
  if (digest(geometry) !== inputs.reference.uncompressed_sha256)
    throw new Error('Changed Colorado full county reference');
  return reviewColoradoCountyReturns({ inputs,
    sheets: JSON.parse(gunzipSync(verified(`${VERSION}/workbook-cells.json.gz`))),
    geometry: JSON.parse(geometry) });
}

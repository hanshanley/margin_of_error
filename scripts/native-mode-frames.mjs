import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { gunzipSync } from 'node:zlib';
import { hasCountySourceMode, selectCountySourceFrame } from '../public/scripts/participation-geography.js';

export const nativeModeVersion = 'data/county-source-reviews/20261110-native-mode-frames-01';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const codes = 'AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split(' ');
const modes = ['available', 'official', 'in_person_early', 'mail_returned'];
const digest = body => createHash('sha256').update(body).digest('hex');
const countyName = value => value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
  .toUpperCase().replace(/\s*\(VOTE CENTER\)/g, '').replace(/\b(COUNTY|PARISH)\b/g, '').replace(/[^A-Z0-9]/g, '');
const observation = row => ({
  county_id: row.county_id, county: row.county, state_code: row.state_code,
  ballots: row.ballots, denominator: row.denominator, reported_pct: row.reported_pct,
  source_mode: row.source_mode ?? null, source_snapshot: row.source_snapshot ?? null,
  source_provider: row.source_provider ?? null,
  native_measure: row.participation_measure_literal ?? null,
  source_reporting_label: row.source_reporting_label ?? null,
  source_url: row.source_url ?? null, complete_download_url: row.complete_download_url ?? null,
});

export async function loadNativeModeInputs(project = root) {
  const directory = join(project, nativeModeVersion);
  const inputs = JSON.parse(readFileSync(join(directory, 'inputs.json')));
  assert.equal(inputs.version, nativeModeVersion);
  assert.equal(Object.keys(inputs.files).length, 58);
  const bodies = {};
  for (const [name, pin] of Object.entries(inputs.files)) {
    assert.ok(!name.startsWith('/') && !name.split('/').includes('..'));
    const body = readFileSync(join(directory, name));
    assert.equal(body.length, pin.bytes);
    assert.equal(digest(body), pin.sha256);
    bodies[name] = body;
  }
  const shared = JSON.parse(bodies['source-data/shared-native-local.json']);
  const reviewed = JSON.parse(bodies['source-data/all-reviewed-counties.json']);
  const counties = [...shared.counties, ...reviewed.filter(row =>
    !shared.counties.some(other => other.state_code === row.state_code
      && (other.county_id === row.county_id || countyName(other.county) === countyName(row.county))))];
  const byState = {};
  for (const code of codes) {
    const file = inputs.state_local_files[code];
    const additional = file ? JSON.parse(gunzipSync(bodies[file])) : null;
    byState[code] = additional ? { ...additional, counties: [...counties, ...additional.counties.filter(row =>
      !counties.some(other => other.state_code === row.state_code && countyName(other.county) === countyName(row.county)))] }
      : { ...shared, counties };
  }
  const baseline = await import(pathToFileURL(join(directory, 'source-code/participation-geography.js')).href);
  return { inputs, byState, baseline };
}

export async function reviewNativeModeFrames(project = root) {
  const { inputs, byState, baseline } = await loadNativeModeInputs(project);
  const decisions = [];
  for (const code of codes) {
    const data = byState[code], unchanged = JSON.stringify(data);
    for (const mode of modes) {
      const before = baseline.selectCountySourceFrame(data, code, mode).filter(row => row.state_code === code);
      const after = selectCountySourceFrame(data, code, mode).filter(row => row.state_code === code);
      const explicitMode = ['in_person_early', 'mail_returned'].includes(mode);
      const supported = hasCountySourceMode(code, mode);
      if (!explicitMode || supported) assert.deepEqual(after, before);
      else assert.equal(after.length, 0);
      assert.equal(JSON.stringify(data), unchanged);
      const changed = JSON.stringify(after) !== JSON.stringify(before);
      decisions.push({
        state_code: code, mode, explicit_requested_mode: explicitMode,
        qualified_requested_frame_available: explicitMode ? supported : null,
        separate_local_export_present: Boolean(inputs.state_local_files[code]),
        before_selected_rows: before.length, after_selected_rows: after.length,
        changed, native_input_records_modified: false,
        before_observations: before.map(observation), after_observations: after.map(observation),
        disposition: changed ? 'unsupported_mode_no_longer_uses_unqualified_other_frame'
          : explicitMode && !supported ? 'no_qualified_mode_local_observations'
            : 'existing_source_frame_preserved',
      });
    }
  }
  const changed = decisions.filter(row => row.changed);
  assert.equal(decisions.length, 204);
  assert.equal(changed.length, 23);
  assert.ok(changed.every(row => row.explicit_requested_mode && !row.qualified_requested_frame_available));
  const summary = {
    jurisdictions: 51, complete_state_mode_decisions: 204, changed_unsupported_mode_decisions: changed.length,
    changed_states: [...new Set(changed.map(row => row.state_code))],
    available_official_decisions_preserved: decisions.filter(row => !row.explicit_requested_mode).length,
    qualified_mode_decisions_preserved: decisions.filter(row => row.explicit_requested_mode
      && row.qualified_requested_frame_available).length,
    residual_non_mode_specific_selections: decisions.filter(row => row.explicit_requested_mode
      && !row.qualified_requested_frame_available && row.after_selected_rows > 0).length,
    source_observations_or_counts_modified: false, new_normalized_mode_or_population_qualification: false,
    missing_separate_export_not_used_to_infer_source_absence: true,
    DC_existing_reviewed_county_observation_preserved: decisions.filter(row =>
      row.state_code === 'DC' && !row.explicit_requested_mode).every(row => row.after_selected_rows === 1),
    source_absence_not_zero: true, statewide_survey_or_return_allocation: false,
  };
  return { summary, complete204_state_mode_decisions: decisions };
}

export const encodeNativeModeReview = value => Buffer.from(JSON.stringify(value, null, 2) + '\n');

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  process.stdout.write(encodeNativeModeReview(await reviewNativeModeFrames()));

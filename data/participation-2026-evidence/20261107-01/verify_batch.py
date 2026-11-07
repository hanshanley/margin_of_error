#!/usr/bin/env python3
import csv
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED_TOP = {'schema_version', 'as_of_label', 'observations', 'butler', 'colorado_composition', 'complete_download_filename'}
EXPECTED_OBS = {'id', 'jurisdiction', 'scope', 'measure', 'numerator', 'denominator', 'denominator_label', 'source_time_label', 'source_url', 'status', 'coverage_note', 'history_note', 'previous_numerator', 'numeric_change', 'comparison_note'}
FORBIDDEN_PATH_PARTS = ('voter-record', 'voter_stats', 'history_stats', 'absentee_spoiled')
FORBIDDEN_SUFFIXES = ('.html', '.xlsx', '.pdf')
FORBIDDEN_CONTENT = (b'/' + b'Users/', b'State Voter ID,', b'First Name,', b'Last Name,', b'Date of Birth,', b'Residential Address,')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package(name):
    return ROOT / 'packages' / name


def rows(name, member):
    with zipfile.ZipFile(package(name)) as z:
        return list(csv.DictReader(io.TextIOWrapper(z.open(member), encoding='utf-8-sig')))


def nested_json(name, member):
    with zipfile.ZipFile(package(name)) as z:
        return json.loads(z.read(member))


def verify_sha_lines(text, getter):
    for line in text.splitlines():
        expected, rel = line.split('  ', 1)
        assert digest(getter(rel)) == expected, rel


def verify_checksums():
    verify_sha_lines((ROOT / 'SHA256SUMS').read_text(), lambda rel: (ROOT / rel).read_bytes())
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    for item in manifest['files']:
        data = (ROOT / item['path']).read_bytes()
        assert len(data) == item['bytes']
        assert digest(data) == item['sha256']
    for path in sorted((ROOT / 'packages').glob('*.zip')):
        with zipfile.ZipFile(path) as z:
            if path.name == 'california-2026-public-query.zip':
                assert digest(path.read_bytes()) == 'd3255beab418cefe4f9bc8b8ed3dd5a93fec8096617c187ffdc3eaad33e36bf5'
                pm = list(csv.DictReader(io.StringIO(z.read('package-manifest.csv').decode())))
                for item in pm:
                    data = z.read(item['file'])
                    assert len(data) == int(item['bytes'])
                    assert digest(data) == item['sha256']
            else:
                verify_sha_lines(z.read('SHA256SUMS').decode(), z.read)
                pm = json.loads(z.read('PACKAGE-MANIFEST.json'))
                for item in pm['files']:
                    data = z.read(item['path'])
                    assert len(data) == item['bytes']
                    assert digest(data) == item['sha256']


def intsum(items, field):
    return sum(int(float(r[field])) for r in items if r[field] != '')


def verify_summary_sources(summary):
    obs = {r['id']: r for r in summary['observations']}
    assert len(obs) == 8

    ncj = nested_json('north-carolina-2026-public-query.zip', 'statewide-observations.json')
    nc = next(r for r in ncj if r['selected_current_proposal'])
    assert obs['nc-2026-reported-ballots-20261106']['numerator'] == nc['ballots']
    assert obs['nc-2026-reported-ballots-20261106']['denominator'] == nc['denominator']
    nc_counties = rows('north-carolina-2026-public-query.zip', 'pipeline-counties.csv')
    assert len(nc_counties) == 100
    assert intsum(nc_counties, 'ballots') == nc['ballots']
    assert intsum(nc_counties, 'denominator') == nc['denominator']

    ga_state = rows('georgia-2026-public-query.zip', 'statewide-participation.csv')[0]
    ga_obs = obs['ga-2026-reported-ballots-20261107']
    assert ga_obs['numerator'] == int(ga_state['ballots'])
    assert ga_obs['denominator'] is None
    ga_counties = rows('georgia-2026-public-query.zip', 'county-participation.csv')
    assert len(ga_counties) == 159
    assert intsum(ga_counties, 'native_ballots_cast') == ga_obs['numerator']

    co_state = rows('colorado-2026-public-query.zip', 'query/statewide-participation.csv')[0]
    co_obs = obs['co-2026-returned-processed-20261105']
    assert co_obs['numerator'] == int(co_state['returned_ballots'])
    assert co_obs['denominator'] == int(co_state['eligible_registered_voters'])
    co_counties = rows('colorado-2026-public-query.zip', 'query/county-participation.csv')
    assert len(co_counties) == 64
    for field in ('returned_ballots', 'returned_mail_ballots', 'in_person_ballots'):
        assert intsum(co_counties, field) == int(co_state[field])
    for member in ('query/state-party-mode-marginals.csv', 'query/county-party-mode-marginals.csv'):
        mode_rows = rows('colorado-2026-public-query.zip', member)
        sums = {mode: sum(int(r['returned_ballots']) for r in mode_rows if r['mode'] == mode) for mode in ('all_returned', 'returned_mail', 'in_person')}
        assert sums == {'all_returned': 2761449, 'returned_mail': 2618985, 'in_person': 142464}

    comp = summary['colorado_composition']
    age = rows('colorado-2026-public-query.zip', 'query/age-composition.csv')
    gender = rows('colorado-2026-public-query.zip', 'query/gender-composition.csv')
    assert len(age) == 8 and len(gender) == 4
    assert comp['age'] == [{'group': r['age_range'], 'returned_ballots': int(r['returned_ballots'])} for r in age]
    assert comp['gender'] == [{'group': r['gender_recorded'], 'returned_ballots': int(r['returned_ballots'])} for r in gender]
    assert sum(r['returned_ballots'] for r in comp['age']) == 2761449
    assert sum(r['returned_ballots'] for r in comp['gender']) == 2761449
    native_cells = rows('colorado-2026-public-query.zip', 'query/source-native-cells.csv')
    inventory = rows('colorado-2026-public-query.zip', 'query/source-sheet-inventory.csv')
    assert len(native_cells) == 4982
    assert sum(int(r['nonempty_cells']) for r in inventory) == 4982
    assert len(inventory) == 7

    duval = rows('florida-duval-2026-public-query.zip', 'county-participation.csv')[0]
    duval_obs = obs['fl-duval-2026-reported-ballots-20261107']
    assert duval_obs['numerator'] == int(duval['reported_participants'])
    assert duval_obs['denominator'] == int(duval['registered_voters'])

    clark = rows('nevada-clark-2026-public-query.zip', 'integration-proposal/data/county-source-reviews/20261107-clark-participation-01/county-participation.csv')[0]
    clark_obs = obs['nv-clark-2026-reported-ballots-20261106']
    assert clark_obs['numerator'] == int(clark['ballots_cast'])
    assert clark_obs['denominator'] == int(clark['registered_voters'])
    clark_modes = rows('nevada-clark-2026-public-query.zip', 'integration-proposal/data/county-source-reviews/20261107-clark-participation-01/counting-group-participation.csv')
    assert intsum(clark_modes, 'ballots') == clark_obs['numerator']

    butler_diag = nested_json('ohio-butler-2026-public-diagnostic.zip', 'public/current-registrant-diagnostic.json')
    butler_obs = obs['oh-butler-2026-recorded-credit-20261107']
    assert butler_obs['numerator'] == butler_diag['marginals']['2026_credit_present']
    assert butler_obs['denominator'] == butler_diag['frame']['records']
    matrix = rows('ohio-butler-2026-public-diagnostic.zip', 'public/credit-presence-matrix.csv')
    prior = sum(int(r['current_registration_records']) for r in matrix if r['credit_2024_general'] == 'present')
    current = sum(int(r['current_registration_records']) for r in matrix if r['credit_2026_general'] == 'present')
    assert prior == summary['butler']['current_2024_credits'] == 176535
    assert current == summary['butler']['current_2026_credits'] == 148569
    assert sum(int(r['current_registration_records']) for r in matrix) == 249106

    tx_rows = rows('texas-harris-2026-public-query.zip', 'output/county-participation.csv')
    assert len(tx_rows) == 13
    tx = {r['native_label']: int(r['count']) for r in tx_rows}
    tx_obs = obs['tx-harris-2026-counted-ballots-20261104']
    assert tx_obs['numerator'] == tx['I. Total ballots counted (G+H)'] == 1392280
    assert tx_obs['denominator'] == tx['Registered Voters'] == 2761770
    assert tx['C. Total Voters (A+B)'] == 1393495
    assert tx['A. In Person Voters'] + tx['B. By mail voters'] == tx['C. Total Voters (A+B)']
    assert tx['D. Provisional Ballots Rejects or pending'] + tx['E. Mail Ballots rejected or pending'] == tx['F. Total Ballots rejected or pending (D+E)']
    assert tx['G. In person ballots counted'] + tx['H. Mail ballot counted'] == tx['I. Total ballots counted (G+H)']
    assert tx['C. Total Voters (A+B)'] - tx['F. Total Ballots rejected or pending (D+E)'] - tx['I. Total ballots counted (G+H)'] == tx['J. Difference between voters and ballot (C-F-I)']

    ca_state = rows('california-2026-public-query.zip', 'statewide-participation.csv')[0]
    ca_obs = obs['ca-2026-native-voter-turnout-20261106']
    assert ca_obs['numerator'] == int(ca_state['reported_participation']) == 10098551
    assert ca_obs['denominator'] == int(ca_state['registered_voters']) == 23273590
    assert ca_state['native_participation_measure_literal'] == 'voterTurnout'
    assert ca_state['native_printed_turnout'] == '43.4'
    assert ca_state['counting_complete'] == 'false' and ca_state['certified'] == 'false'
    assert ca_state['all_mode_unique_ballot_count_proven'] == 'false'
    ca_counties = rows('california-2026-public-query.zip', 'county-participation.csv')
    assert len(ca_counties) == 58
    assert intsum(ca_counties, 'reported_participation') == ca_obs['numerator']
    assert intsum(ca_counties, 'registered_voters') == ca_obs['denominator']
    ca_compare = rows('california-2026-public-query.zip', 'statewide-comparison.csv')[0]
    assert int(ca_compare['old_value']) == ca_obs['previous_numerator'] == 8928966
    assert int(ca_compare['absolute_change']) == ca_obs['numeric_change'] == 1169585
    ca_mode_state = rows('california-2026-public-query.zip', 'statewide-mode-snapshot-2026-11-03.csv')[0]
    ca_mode_counties = rows('california-2026-public-query.zip', 'county-mode-snapshot-2026-11-03.csv')
    assert len(ca_mode_counties) == 58
    mode_fields = ('vbm_issued_distinct_voters', 'vbm_returned_drop_box', 'vbm_returned_drop_off_location', 'vbm_returned_vote_center_drop_off', 'vbm_returned_mail', 'vbm_returned_fax', 'vbm_returned_other', 'vbm_returned_total', 'vbm_accepted_total', 'in_person_regular', 'in_person_provisional_non_cvr', 'in_person_conditional_cvr', 'in_person_instant_cvr', 'in_person_cast_total', 'in_person_accepted_total', 'native_total_ballots_cast', 'accepted_components_sum', 'native_total_minus_accepted_components')
    for field in mode_fields:
        assert intsum(ca_mode_counties, field) == int(ca_mode_state[field])
    assert ca_mode_state['native_total_definition_conflict'] == 'true'
    assert int(ca_mode_state['native_total_minus_accepted_components']) == 110212
    assert ca_mode_state['counting_complete'] == 'false'


def verify_privacy():
    for path in sorted((ROOT / 'packages').glob('*.zip')):
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                low = info.filename.lower()
                assert not any(part in low for part in FORBIDDEN_PATH_PARTS), (path.name, info.filename)
                assert not low.endswith(FORBIDDEN_SUFFIXES), (path.name, info.filename)
                data = z.read(info)
                assert not any(marker in data for marker in FORBIDDEN_CONTENT), (path.name, info.filename)


def verify_complete_zip(summary):
    archive = ROOT / summary['complete_download_filename']
    if archive.exists():
        meta = json.loads((ROOT / 'download.json').read_text())
        data = archive.read_bytes()
        assert meta['bytes'] == len(data)
        assert meta['sha256'] == digest(data)
        sidecar = (ROOT / (archive.name + '.sha256')).read_text().strip().split()[0]
        assert sidecar == meta['sha256']


def main():
    verify_checksums()
    summary = json.loads((ROOT / 'summary.json').read_text())
    assert set(summary) == EXPECTED_TOP
    assert summary['schema_version'] == 1
    assert len(summary['observations']) == 8
    assert all(set(r) == EXPECTED_OBS for r in summary['observations'])
    assert all('comparison_note' in r for r in summary['observations'])
    assert next(r for r in summary['observations'] if r['jurisdiction'] == 'Georgia')['denominator'] is None
    csv_rows = list(csv.DictReader((ROOT / 'summary.csv').open(newline='')))
    assert len(csv_rows) == 8
    assert [r['id'] for r in csv_rows] == [r['id'] for r in summary['observations']]
    verify_summary_sources(summary)
    proof = json.loads((ROOT / 'release-proof.json').read_text())
    assert proof['prior_unpublished_draft_preserved']['sha256'] == '9c61b10cce8892f33c8fa3e2eb850f9139f3f425bd93eff61ed512cbba098bc7'
    assert proof['privacy_and_redistribution']['qualified_colorado_age_gender_composition_counts_included'] is True
    assert proof['privacy_and_redistribution']['unqualified_group_denominators_or_turnout_rates_included'] is False
    assert proof['privacy_and_redistribution']['raw_person_files_included'] is False
    verify_privacy()
    verify_complete_zip(summary)
    print('PASS: 8 observations, source denominators, county/mode sums, Butler marginals, CO 8+4 composition and 4,982 native cells, TX 13 rows, CA 58 county + 58 mode rows, nested/root checksums, privacy, and complete ZIP verified')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise

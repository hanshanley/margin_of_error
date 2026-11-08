import assert from 'node:assert/strict';
import test from 'node:test';
import { chooseAPView } from '../public/scripts/participation-ap-history.js';

const row = (changes = {}) => ({ year: '2024', weight_field: 'FINALVOTE_NATIONAL_WEIGHT',
	scope: 'US50_SOURCE', dimension: 'overall', group: 'all', ...changes });

test('keeps state/national and final/poll-close source frames separate', () => {
	const rows = [row(), row({ weight_field: 'POLLCLOSE_NATIONAL_WEIGHT' }),
		row({ scope: 'AL', weight_field: 'FINALVOTE_STATE_WEIGHT' })];
	assert.deepEqual(chooseAPView(rows, '2024', 'FINALVOTE', 'US50_SOURCE').rows, [rows[0]]);
	assert.deepEqual(chooseAPView(rows, '2024', 'POLLCLOSE', 'US50_SOURCE').rows, [rows[1]]);
	assert.deepEqual(chooseAPView(rows, '2024', 'FINALVOTE', 'AL').rows, [rows[2]]);
});

test('withholds both 2022 publisher national-only states even if a stray row appears', () => {
	for (const scope of ['DE', 'WV']) {
		const view = chooseAPView([row({ year: '2022', scope, weight_field: 'FINALVOTE_STATE_WEIGHT' })],
			'2022', 'FINALVOTE', scope);
		assert.equal(view.held, true);
		assert.equal(view.rows.length, 0);
		assert.match(view.message, /withheld.*Not zero/);
	}
});

test('preserves the unresolved 2018 state inference qualification', () => {
	const view = chooseAPView([], '2018', 'POLLCLOSE', 'AL');
	assert.match(view.message, /47 inference states despite sampling all 50/);
	assert.equal(view.rows.length, 0);
});

test('does not expose state demographics or disclosure/nonresponse rows', () => {
	const rows = [row({ scope: 'AL', weight_field: 'FINALVOTE_STATE_WEIGHT' }),
		row({ scope: 'AL', weight_field: 'FINALVOTE_STATE_WEIGHT', dimension: 'AGE65', group: '1' }),
		row({ dimension: 'RACETH', group: '88' }), row({ dimension: 'EDUC', group: '99' })];
	assert.equal(chooseAPView(rows, '2024', 'FINALVOTE', 'AL').rows.length, 1);
	assert.equal(chooseAPView(rows, '2024', 'FINALVOTE', 'US50_SOURCE').rows.length, 0);
});

test('missing support remains unavailable rather than a zero rate', () => {
	const view = chooseAPView([], '2024', 'FINALVOTE', 'AL');
	assert.equal(view.rows.length, 0);
	assert.match(view.message, /missing is not zero/);
});

test('rejects invalid frames and ambiguous source overall rows', () => {
	assert.throws(() => chooseAPView([], '2026', 'FINALVOTE', 'US50_SOURCE'));
	assert.throws(() => chooseAPView([], '2024', 'COMBINED', 'US50_SOURCE'));
	assert.throws(() => chooseAPView([row(), row()], '2024', 'FINALVOTE', 'US50_SOURCE'));
});

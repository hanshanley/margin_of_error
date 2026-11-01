import assert from 'node:assert/strict';
import test from 'node:test';
import { attentionComparison, densityComparisons, densityContrast, densityGroups } from '../src/lib/platform-density-comparison.mjs';

const groups = ['democratic', 'republican', 'dsa'];

test('attention ratios use explicit directions and an equal-weight share average', () => {
	const shares = { democratic: 0.03, republican: 0.01, dsa: 0.06 };
	for (const [id, numerator, denominator, ratio] of [
		['democratic_vs_republican', 'democratic', 'republican', 3],
		['democratic_vs_dsa', 'dsa', 'democratic', 2],
		['republican_vs_dsa', 'dsa', 'republican', 6],
		['dsa_vs_democratic_republican', 'dsa', 'democratic_republican', 3],
	]) {
		const result = attentionComparison(shares, id);
		assert.equal(result.numerator, numerator);
		assert.equal(result.denominator, denominator);
		assert.equal(result.ratio, ratio);
	}
	const lower = attentionComparison({ democratic: 0.1, republican: 0.3, dsa: 0.01 },
		'dsa_vs_democratic_republican');
	assert.equal(lower.denominatorShare, 0.2);
	assert.equal(lower.ratio, 0.01 / 0.2);
	const precise = attentionComparison({ democratic: 0.012345, republican: 0.034567, dsa: 0.056789 },
		'dsa_vs_democratic_republican');
	assert.equal(precise.ratio, 0.056789 / ((0.012345 + 0.034567) / 2));
});

test('zero and unobserved baselines do not invent ratios or partial averages', () => {
	for (const pair of densityComparisons) {
		assert.equal(attentionComparison({ democratic: 0, republican: 0, dsa: 0.1 }, pair.id).ratio, null);
	}
	const missing = attentionComparison({ democratic: 0.1, republican: null, dsa: 0.2 },
		'dsa_vs_democratic_republican');
	assert.equal(missing.denominatorShare, null);
	assert.equal(missing.ratio, null);
	assert.equal(attentionComparison({ republican: 0.1 }, 'democratic_vs_republican').ratio, null);
	assert.equal(attentionComparison({ democratic: 0.1, republican: 0.2, dsa: 0 },
		'republican_vs_dsa').ratio, 0);
});

test('invalid shares and unknown comparisons are rejected', () => {
	for (const value of [NaN, Infinity, -0.1, 1.1, '0.1', '']) {
		assert.throws(() => attentionComparison({ democratic: value, republican: 0.1 },
			'democratic_vs_republican'), /Invalid attention share/);
	}
	assert.throws(() => attentionComparison({}, 'unknown'), /Unknown attention comparison/);
});

test('combined comparison includes all parties and averages densities, not log densities', () => {
	assert.ok(densityComparisons.some(pair => pair.id === 'dsa_vs_democratic_republican'));
	assert.deepEqual(densityGroups('democratic_republican'), ['democratic', 'republican']);
	assert.ok(Math.abs(densityContrast([Math.log(2), Math.log(8), Math.log(5)],
		groups, 'dsa', 'democratic_republican')) < 1e-12);
});

test('mixture remains stable at extreme log densities and gives both parties equal weight', () => {
	const contrast = densityContrast([-1000, -2000, -1000], groups, 'dsa', 'democratic_republican');
	assert.ok(Math.abs(contrast - Math.log(2)) < 1e-12);
	assert.equal(contrast, densityContrast([-2000, -1000, -1000],
		groups, 'dsa', 'democratic_republican'));
	assert.ok(Math.abs(densityContrast([1000, 1000, 1000],
		groups, 'dsa', 'democratic_republican')) < 1e-12);
});

test('existing pairwise contrasts and reordered density columns are preserved', () => {
	assert.equal(densityContrast([2, 7, 4], groups, 'democratic', 'republican'), -5);
	assert.equal(densityContrast([2, 7, 4], groups, 'democratic', 'dsa'), -2);
	assert.equal(densityContrast([2, 7, 4], groups, 'republican', 'dsa'), 3);
	assert.equal(densityContrast([4, 7, 2], ['dsa', 'republican', 'democratic'],
		'dsa', 'democratic_republican'),
	densityContrast([2, 7, 4], groups, 'dsa', 'democratic_republican'));
});

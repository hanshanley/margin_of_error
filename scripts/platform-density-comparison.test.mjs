import assert from 'node:assert/strict';
import test from 'node:test';
import { densityComparisons, densityContrast, densityGroups } from '../src/lib/platform-density-comparison.mjs';

const groups = ['democratic', 'republican', 'dsa'];

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

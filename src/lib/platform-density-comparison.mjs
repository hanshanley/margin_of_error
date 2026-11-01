export const densityComparisons = [
	{ id: 'democratic_vs_republican', title: 'Democratic and Republican',
		attentionNumerator: 'democratic', attentionDenominator: 'republican' },
	{ id: 'democratic_vs_dsa', title: 'Democratic and DSA',
		attentionNumerator: 'dsa', attentionDenominator: 'democratic' },
	{ id: 'republican_vs_dsa', title: 'Republican and DSA',
		attentionNumerator: 'dsa', attentionDenominator: 'republican' },
	{ id: 'dsa_vs_democratic_republican', title: 'DSA vs. Democrats + Republicans',
		attentionNumerator: 'dsa', attentionDenominator: 'democratic_republican' },
];

export const densityGroups = side => side === 'democratic_republican'
	? ['democratic', 'republican'] : [side];

export function attentionComparison(shares, comparison) {
	const pair = densityComparisons.find(pair => pair.id === comparison);
	if (!pair) throw new Error(`Unknown attention comparison: ${comparison}`);
	const share = side => {
		const values = densityGroups(side).map(group => shares[group]);
		if (values.some(value => value != null &&
			(typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1))) {
			throw new Error(`Invalid attention share: ${side}`);
		}
		if (values.some(value => value == null)) return null;
		return values.reduce((sum, value) => sum + value, 0) / values.length;
	};
	const numeratorShare = share(pair.attentionNumerator);
	const denominatorShare = share(pair.attentionDenominator);
	return {
		numerator: pair.attentionNumerator, denominator: pair.attentionDenominator,
		numeratorShare, denominatorShare,
		ratio: numeratorShare !== null && denominatorShare !== null && denominatorShare > 0
			? numeratorShare / denominatorShare : null,
	};
}

export function densityContrast(logDensities, groups, first, second) {
	const density = side => {
		const values = densityGroups(side).map(group => logDensities[groups.indexOf(group)]);
		if (values.length === 1) return values[0];
		const maximum = Math.max(...values);
		return maximum + Math.log(values.reduce((sum, value) =>
			sum + Math.exp(value - maximum), 0)) - Math.log(values.length);
	};
	return density(first) - density(second);
}

export const densityComparisons = [
	{ id: 'democratic_vs_republican', title: 'Democratic and Republican' },
	{ id: 'democratic_vs_dsa', title: 'Democratic and DSA' },
	{ id: 'republican_vs_dsa', title: 'Republican and DSA' },
	{ id: 'dsa_vs_democratic_republican', title: 'DSA vs. Democrats + Republicans' },
];

export const densityGroups = side => side === 'democratic_republican'
	? ['democratic', 'republican'] : [side];

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

const DAY_IN_MILLISECONDS = 86_400_000;
const REPUBLICAN_EPOCH = Date.UTC(1792, 8, 22);

const months = [
	'Vendémiaire',
	'Brumaire',
	'Frimaire',
	'Nivôse',
	'Pluviôse',
	'Ventôse',
	'Germinal',
	'Floréal',
	'Prairial',
	'Messidor',
	'Thermidor',
	'Fructidor',
];

const complementaryDays = [
	'Jour de la Vertu',
	'Jour du Génie',
	'Jour du Travail',
	'Jour de l’Opinion',
	'Jour des Récompenses',
	'Jour de la Révolution',
];

function isSextileYear(year: number) {
	const followingYear = year + 1;
	return (
		followingYear % 400 === 0 ||
		(followingYear % 4 === 0 && followingYear % 100 !== 0)
	);
}

function toRomanNumeral(value: number) {
	const numerals: Array<[number, string]> = [
		[1000, 'M'],
		[900, 'CM'],
		[500, 'D'],
		[400, 'CD'],
		[100, 'C'],
		[90, 'XC'],
		[50, 'L'],
		[40, 'XL'],
		[10, 'X'],
		[9, 'IX'],
		[5, 'V'],
		[4, 'IV'],
		[1, 'I'],
	];
	let remainder = value;
	let result = '';

	for (const [amount, numeral] of numerals) {
		while (remainder >= amount) {
			result += numeral;
			remainder -= amount;
		}
	}

	return result;
}

export function formatFrenchRepublicanDate(date: Date) {
	const utcDate = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
	if (!Number.isFinite(utcDate) || utcDate < REPUBLICAN_EPOCH) {
		throw new RangeError('French Republican dates require a valid date on or after 22 September 1792.');
	}

	let remainingDays = Math.floor((utcDate - REPUBLICAN_EPOCH) / DAY_IN_MILLISECONDS);
	let year = 1;
	let yearLength = isSextileYear(year) ? 366 : 365;

	while (remainingDays >= yearLength) {
		remainingDays -= yearLength;
		year += 1;
		yearLength = isSextileYear(year) ? 366 : 365;
	}

	const yearLabel = `An ${toRomanNumeral(year)}`;
	if (remainingDays >= 360) {
		return `${complementaryDays[remainingDays - 360]}, ${yearLabel}`;
	}

	const month = months[Math.floor(remainingDays / 30)];
	const day = (remainingDays % 30) + 1;
	return `${day} ${month}, ${yearLabel}`;
}

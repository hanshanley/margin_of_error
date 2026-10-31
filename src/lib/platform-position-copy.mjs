const parties = {
	democratic: 'The Democratic Party',
	republican: 'The Republican Party',
	dsa: 'DSA',
};
const singularVerbs = {
	support: 'supports', affirm: 'affirms', assert: 'asserts', portray: 'portrays',
	attribute: 'attributes', describe: 'describes', criticize: 'criticizes',
	combine: 'combines', welcome: 'welcomes', praise: 'praises', oppose: 'opposes',
	reject: 'rejects', seek: 'seeks', advocate: 'advocates', connect: 'connects',
	move: 'moves', call: 'calls', prioritize: 'prioritizes',
	commit: 'commits', critique: 'critiques', emphasize: 'emphasizes',
	link: 'links', pair: 'pairs',
};
const parallelClauses = [
	['and link sustainable prosperity', 'and links sustainable prosperity'],
	[', criticize Obama-era', ', criticizes Obama-era'],
	[', and portray Biden-era', ', and portrays Biden-era'],
	[', support constitutional', ', supports constitutional'],
	[', and endorse informed', ', and endorses informed'],
	[', support defeating', ', supports defeating'],
	[", criticize Iraq's", ", criticizes Iraq's"],
	[', favor ending', ', favors ending'],
	[', and note burdens', ', and notes burdens'],
	[', advocate its abolition', ', advocates its abolition'],
	[', and propose working-class', ', and proposes working-class'],
	[', demand releases', ', demands releases'],
	[', and later advocate demilitarization', ', and later advocates demilitarization'],
	[', depict nationalist', ', depicts nationalist'],
	[', and later fault Democrats', ', and later faults Democrats'],
	['; they favor', '; it favors'],
	['; they support', '; it supports'],
	['and promise continuation;', 'and promises continuation;'],
];

export function partyPositionSummary(group, summary) {
	const party = parties[group];
	if (!party) throw new Error(`Unknown position organization: ${group}`);
	if (/^Sampled (documents|platforms)\b/.test(summary)) {
		return summary.replace(/^Sampled/, `${party}'s sampled`);
	}
	if (/^Samples(?:\s|,)/.test(summary)) {
		return summary.replace(/^Samples/, `${party}'s sampled documents`);
	}
	if (/^Platforms\s/.test(summary)) {
		return summary.replace(/^Platforms/, `${party}'s platforms`);
	}
	let copy = summary.replace(/^Documents (repeatedly )?(\w+)/, (_, adverb, verb) => {
		if (!singularVerbs[verb]) throw new Error(`Unrecognized summary verb: ${verb}`);
		return `${party} ${adverb ?? ''}${singularVerbs[verb]}`;
	});
	copy = copy
		.replace(/^Across years, documents oppose/, `${party}, across years, opposes`)
		.replace(/^A small, mixed set criticizes/, `${party}, in a small, mixed set of statements, criticizes`)
		.replace(/^From 2016 through 2024, documents criticize/, `${party}, in documents from 2016 through 2024, criticizes`)
		.replace(/^The 2024 examples praise/, `${party}, in its 2024 examples, praises`);
	if (!copy.startsWith(party)) throw new Error(`Unrecognized position summary opening: ${group}`);
	for (const [original, revised] of parallelClauses) copy = copy.replace(original, revised);
	return copy;
}

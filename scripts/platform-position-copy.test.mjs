import assert from 'node:assert/strict';
import { test } from 'node:test';
import { partyPositionSummary } from '../src/lib/platform-position-copy.mjs';

test('names the party without changing the supported policy list', () => {
	const policies = 'targeted federal investment, Medicaid and community-based services, affordable housing, mental-health and substance-use treatment, and assistance for veterans, disabled people, low-income communities, and returning citizens.';
	assert.equal(partyPositionSummary('democratic', `Documents support ${policies}`),
		`The Democratic Party supports ${policies}`);
	assert.equal(partyPositionSummary('dsa', 'Documents repeatedly seek affordable coverage.'),
		'DSA repeatedly seeks affordable coverage.');
});

test('conjugates coordinated clauses without changing historical actors', () => {
	assert.equal(partyPositionSummary('republican',
		'Documents oppose abortion, support constitutional protections, and endorse informed-consent rules; 2024 examples also support birth control.'),
		'The Republican Party opposes abortion, supports constitutional protections, and endorses informed-consent rules; 2024 examples also support birth control.');
	assert.equal(partyPositionSummary('dsa',
		'Documents support diplomacy; they favor military cuts.'),
		'DSA supports diplomacy; it favors military cuts.');
	assert.equal(partyPositionSummary('dsa',
		'Documents portray growth as unequally distributed and link sustainable prosperity to public infrastructure.'),
		'DSA portrays growth as unequally distributed and links sustainable prosperity to public infrastructure.');
	assert.equal(partyPositionSummary('republican',
		'Documents praise Bush-era defense, criticize Obama-era defense, and portray Biden-era borders negatively.'),
		'The Republican Party praises Bush-era defense, criticizes Obama-era defense, and portrays Biden-era borders negatively.');
});

test('retains limited evidence and explicit historical scope', () => {
	assert.equal(partyPositionSummary('democratic',
		'A small, mixed set criticizes corporate power, while generally seeking fairer markets rather than capitalism\'s abolition.'),
		'The Democratic Party, in a small, mixed set of statements, criticizes corporate power, while generally seeking fairer markets rather than capitalism\'s abolition.');
	assert.equal(partyPositionSummary('democratic',
		'From 2016 through 2024, documents criticize Trump on alliances.'),
		'The Democratic Party, in documents from 2016 through 2024, criticizes Trump on alliances.');
	assert.equal(partyPositionSummary('republican',
		'The 2024 examples praise Trump and promise continuation; one 2016 example attacks Obama.'),
		'The Republican Party, in its 2024 examples, praises Trump and promises continuation; one 2016 example attacks Obama.');
});

test('rejects unknown organizations and unsupported opening formats', () => {
	assert.throws(() => partyPositionSummary('unknown', 'Documents support investment.'), /Unknown position organization/);
	assert.throws(() => partyPositionSummary('dsa', 'Unreviewed text.'), /Unrecognized position summary opening/);
	assert.throws(() => partyPositionSummary('dsa', 'Documents invent a policy.'), /Unrecognized summary verb/);
});

test('names parties in current summaries without losing sampled or historical scope', () => {
	assert.equal(partyPositionSummary('democratic', 'Documents pair infrastructure investment with jobs.'),
		'The Democratic Party pairs infrastructure investment with jobs.');
	assert.equal(partyPositionSummary('dsa', 'Sampled documents treat healthcare as a right.'),
		"DSA's sampled documents treat healthcare as a right.");
	assert.equal(partyPositionSummary('republican', 'Sampled platforms support affordable access.'),
		"The Republican Party's sampled platforms support affordable access.");
	assert.equal(partyPositionSummary('republican',
		"Samples, chiefly from 2024, praise Trump's record while promising renewed implementation."),
		"The Republican Party's sampled documents, chiefly from 2024, praise Trump's record while promising renewed implementation.");
	assert.equal(partyPositionSummary('democratic', 'Platforms combine diplomacy and, by 2024, ceasefire language.'),
		"The Democratic Party's platforms combine diplomacy and, by 2024, ceasefire language.");
	assert.equal(partyPositionSummary('dsa', 'Samples support diplomacy; they favor military cuts.'),
		"DSA's sampled documents support diplomacy; they favor military cuts.");
});

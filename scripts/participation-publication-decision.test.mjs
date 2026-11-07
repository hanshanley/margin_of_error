import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
	failClosedPublicationDecision, loadPublicationDecision, publicationAllows,
	publicationDecisionPath, validatePublicationDecision,
} from '../src/lib/participation-publication-decision.mjs';

test('preserves qualified source classes but withholds population-scaled historical inferences', () => {
	const decision = loadPublicationDecision();
	assert.notEqual(decision.status, 'fail_closed');
	for (const metric of [
		'source_backed_turnout_observations', 'provider_initial_estimates', 'unscaled_qualified_survey_shares',
	]) assert.equal(publicationAllows(decision, metric), true, metric);
	for (const metric of [
		'original_coalition_returning_counts', 'original_coalition_switching_counts_rates',
		'signed_apparent_absence_counts_rates', 'population_scaled_prior_composition_counts',
		'age_scaled_original_coalition_counts_rates',
	]) {
		assert.equal(publicationAllows(decision, metric), false, metric);
		assert.equal(publicationAllows(decision, metric, 'NC'), false, metric);
	}
	assert.equal(publicationAllows(decision, 'unrecognized_metric'), false);
	assert.equal(publicationAllows(decision, 'source_backed_turnout_observations', 'XX'), false);
});

test('missing or promoted decisions fail closed without hiding source observations', () => {
	const missing = loadPublicationDecision('scripts/does-not-exist-publication-decision.json');
	assert.equal(missing, failClosedPublicationDecision);
	assert.equal(publicationAllows(missing, 'provider_initial_estimates'), true);
	assert.equal(publicationAllows(missing, 'original_coalition_returning_counts'), false);
	const promoted = JSON.parse(readFileSync(publicationDecisionPath, 'utf8'));
	promoted.metrics.original_coalition_returning_counts = true;
	assert.throws(() => validatePublicationDecision(promoted), /preserve safe classes and suppress scalars/);
});

test('rejects missing, duplicate or unrecognized jurisdictions and unaudited sources', () => {
	const original = JSON.parse(readFileSync(publicationDecisionPath, 'utf8'));
	for (const mutate of [
		value => value.jurisdictions.pop(),
		value => value.jurisdictions.push(value.jurisdictions[0]),
		value => { value.jurisdictions[0][0] = 'XX'; },
		value => { value.source_bindings = []; },
		value => { value.source_bindings[0].sha256 = 'invalid'; },
	]) {
		const value = structuredClone(original);
		mutate(value);
		assert.throws(() => validatePublicationDecision(value));
	}
});

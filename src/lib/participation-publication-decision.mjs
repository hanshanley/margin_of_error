import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export const publicationDecisionPath = resolve(
	'public/participation-publication-decision/20261107-01/decision.json');
const stateCodes = new Set(
	'AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC'.split(' '));
const safeMetrics = new Set([
	'source_backed_turnout_observations',
	'provider_initial_estimates',
	'unscaled_qualified_survey_shares',
]);
const blockedMetrics = new Set([
	'original_coalition_returning_counts',
	'original_coalition_switching_counts_rates',
	'signed_apparent_absence_counts_rates',
	'population_scaled_prior_composition_counts',
	'age_scaled_original_coalition_counts_rates',
]);
const metricNames = [...safeMetrics, ...blockedMetrics];
export const failClosedPublicationDecision = Object.freeze({
	schema_version: 1,
	decision_id: 'fail-closed-missing-or-invalid-publication-decision',
	status: 'fail_closed',
	metrics: Object.freeze(Object.fromEntries(metricNames.map(name => [name, safeMetrics.has(name)]))),
	jurisdictions: Object.freeze([...stateCodes].sort().map(code => [code, false, true, 0, false, false])),
});
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const hash = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);

export function validatePublicationDecision(value) {
	if (!object(value) || value.schema_version !== 1
		|| value.status !== 'public_safe_metric_specific_historical_evidence_decision'
		|| !object(value.metrics) || !Array.isArray(value.jurisdictions)
		|| !Array.isArray(value.source_bindings) || !value.source_bindings.length
		|| !Array.isArray(value.jurisdiction_fields))
		throw new TypeError('Invalid publication-decision envelope');
	if ([...blockedMetrics].some(name => value.metrics[name] !== false)
		|| [...safeMetrics].some(name => value.metrics[name] !== true))
		throw new TypeError('Current historical decision must preserve safe classes and suppress scalars');
	const codes = new Set();
	for (const row of value.jurisdictions) {
		if (!Array.isArray(row) || row.length !== 6 || !stateCodes.has(row[0]) || codes.has(row[0])
			|| typeof row[1] !== 'boolean' || typeof row[2] !== 'boolean'
			|| !Number.isSafeInteger(row[3]) || row[3] < 0 || typeof row[4] !== 'boolean'
			|| row[5] !== false)
			throw new TypeError('Invalid jurisdiction publication decision');
		codes.add(row[0]);
	}
	if (codes.size !== stateCodes.size)
		throw new TypeError('Publication decision must cover the 50 states and D.C.');
	for (const binding of value.source_bindings) {
		if (!object(binding) || typeof binding.role !== 'string'
			|| typeof binding.public_role !== 'string' || !hash(binding.sha256)
			|| !Number.isSafeInteger(binding.bytes) || binding.bytes <= 0)
			throw new TypeError('Invalid publication-decision source binding');
	}
	return value;
}

export function loadPublicationDecision(path = publicationDecisionPath) {
	try {
		return validatePublicationDecision(JSON.parse(readFileSync(path, 'utf8')));
	} catch {
		return failClosedPublicationDecision;
	}
}

export function publicationAllows(decision, metric, stateCode) {
	if (!metricNames.includes(metric) || decision.metrics?.[metric] !== true) return false;
	if (stateCode === undefined) return true;
	const row = decision.jurisdictions?.find(value => value[0] === stateCode);
	if (!row) return false;
	if (metric === 'provider_initial_estimates') return row[2] === true;
	if (metric === 'unscaled_qualified_survey_shares') return row[3] > 0;
	return metric === 'source_backed_turnout_observations';
}

export const publicationDecision = loadPublicationDecision();

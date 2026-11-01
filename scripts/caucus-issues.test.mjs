import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { load } from 'cheerio';

const data = JSON.parse(readFileSync('public/party-platforms/caucuses/analysis.json', 'utf8'));
const $ = load(readFileSync('dist/party-platforms/index.html', 'utf8'));

test('caucus comparisons follow the existing national analysis and work without scripts', () => {
	assert.equal($('#density').next().attr('id'), 'caucuses');
	assert.equal($('.section-links a[href="#caucuses"]').length, 1);
	assert.equal($('#caucuses details.caucus-issue').length, data.topics.length);
	assert.equal($('#caucuses details.caucus-issue[open]').length, 1);
	assert.equal($('#caucuses .caucus-index a').length, data.topics.length);
	assert.equal($('#caucuses canvas, #caucuses .issue-timeline').length, 0);
	assert.match($('#caucuses').text(), /Zero attention does not mean opposition/);
});

test('every theme contains all thirteen caucuses, exact shares and unsmoothed ratios', () => {
	assert.equal(data.groups.length, 13);
	for (const topic of data.topics) {
		const panel = $(`[data-caucus-topic="${topic.id}"]`);
		assert.equal(panel.find('.caucus-row').length, data.groups.length);
		assert.deepEqual(topic.groups.map(group => group.id), data.groups.map(group => group.id));
		for (const group of topic.groups) {
			const row = panel.find(`[data-caucus="${group.id}"]`);
			assert.equal(Number(row.attr('data-share')), group.share);
			assert.equal(row.find('.caucus-percent').text(), `${(100 * group.share).toFixed(1)}%`);
			const baseline = topic.groups.filter(other => other.id !== group.id)
				.reduce((sum, other) => sum + other.share, 0) / 12;
			assert.ok(Math.abs(group.baseline - baseline) < 1e-12);
			if (baseline > 0) {
				assert.ok(Math.abs(group.ratio - group.share / baseline) < 1e-10);
				assert.equal(Number(row.attr('data-ratio')), group.ratio);
			} else {
				assert.equal(group.ratio, null);
				assert.equal(row.attr('data-ratio'), undefined);
			}
		}
	}
});

test('displayed claims retain their actual source excerpts; zero shares do not invent positions', () => {
	for (const topic of data.topics) {
		for (const group of topic.groups) {
			const row = $(`[data-caucus-topic="${topic.id}"] [data-caucus="${group.id}"]`);
			if (group.claims === 0) {
				assert.equal(group.examples.length, 0);
				assert.match(row.find('.caucus-empty').text(), /No eligible claims assigned/);
				assert.equal(row.find('.caucus-evidence').length, 0);
				continue;
			}
			assert.equal(row.find('.caucus-statement > p').text(), group.examples[0].claim_text);
			assert.equal(row.find('.caucus-evidence[open]').length, 0);
			for (const example of group.examples) {
				const evidence = row.find(`[data-claim="${example.claim_id}"]`);
				assert.equal(evidence.find('blockquote').text(), example.evidence);
				assert.equal(evidence.find('a').attr('href'), example.source_url);
			}
		}
	}
});

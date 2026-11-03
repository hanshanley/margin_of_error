import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { load } from 'cheerio';

const data = JSON.parse(readFileSync('public/party-platforms/caucuses/analysis.json', 'utf8'));
const $ = load(readFileSync('dist/party-platforms/index.html', 'utf8'));

test('share links have unique real targets and the DSA title remains on the existing route', () => {
	const ids = $('[id]').toArray().map(element => $(element).attr('id'));
	assert.equal(new Set(ids).size, ids.length);
	for (const link of $('[data-share-link]').toArray()) {
		const target = $(link).attr('href').slice(1);
		assert.ok(ids.includes(target), `Missing share target: ${target}`);
	}
	for (const topic of $('.mobile-topic').toArray()) {
		const id = $(topic).attr('data-topic');
		assert.equal($(`#issue-${id} [data-share-link][href="#issue-${id}"]`).length, 1);
		assert.equal($(`#ratios-${id}[data-share-link]`).length, 1);
		assert.equal($(`#timeline-${id}[data-share-link]`).length, 1);
		assert.equal($(`#ratios-${id}`).closest('details').hasClass('attention-table'), true);
		assert.equal($(`#timeline-${id}`).closest('details').hasClass('timeline-values'), true);
	}
	for (const panel of $('.density-topic').toArray()) {
		for (const comparison of $(panel).find('.attention-comparison').toArray()) {
			assert.equal($(comparison).find('[data-share-link]').attr('href'), `#${$(comparison).attr('id')}`);
		}
	}
	assert.match($('h1').text(), /^DSA in Context: Party Platforms and Caucuses$/);
	assert.equal($('.analysis-heading .scope').length, 0);
	assert.match($('title').text(), /DSA in Context: Party Platforms and Caucuses/);
	assert.match($('meta[property="og:title"]').attr('content'), /DSA in Context/);
	assert.equal(new URL($('link[rel="canonical"]').attr('href')).pathname, '/party-platforms/');
	const listing = load(readFileSync('dist/interactive-analysis/index.html', 'utf8'));
	assert.equal(listing('h2 a[href="/party-platforms/"]').text(), 'DSA in Context: Party Platforms and Caucuses');
	const actions = listing('h2 a[href="/party-platforms/"]').closest('li').find('.lead-actions a');
	assert.deepEqual(actions.toArray().map(link => listing(link).attr('href')), [
		'/party-platforms/',
		'/what-matters-most-to-americas-democratic-socialists/',
	]);
});

test('caucus comparisons follow the existing national analysis and work without scripts', () => {
	assert.equal($('#density').next().attr('id'), 'caucuses');
	assert.equal($('.section-links a[href="#caucuses"]').length, 1);
	assert.equal($('#caucuses details.caucus-issue').length, data.topics.length);
	assert.equal($('#caucuses details.caucus-issue[open]').length, 1);
	assert.equal($('#caucus-topic-select option').length, data.topics.length);
	assert.equal($('#caucuses [data-caucus-step]').length, 2);
	assert.equal($('#caucuses canvas, #caucuses .issue-timeline').length, 0);
	assert.match($('#caucuses').text(), /Zero attention does not mean opposition/);
});

test('every theme contains all thirteen caucuses, exact shares and unsmoothed ratios', () => {
	assert.equal(data.groups.length, 13);
	for (const topic of data.topics) {
		const panel = $(`[data-caucus-topic="${topic.id}"]`);
		assert.equal(panel.find('.caucus-row').length, data.groups.length);
		assert.deepEqual(topic.groups.map(group => group.id), data.groups.map(group => group.id));
		const ranked = panel.find('.caucus-row').toArray().map(row => Number($(row).attr('data-share')));
		assert.deepEqual(ranked, [...ranked].sort((a, b) => b - a));
		const ceiling = Math.max(0.1, Math.ceil(Math.max(...ranked) * 10) / 10);
		assert.equal(panel.find('.caucus-axis').text(), `0%${Math.round(100 * ceiling)}%`);
		for (const group of topic.groups) {
			const row = panel.find(`[data-caucus="${group.id}"]`);
			assert.equal(panel.find(row.attr('href')).attr('data-caucus-position'), group.id);
			const barWidth = Number(row.find('.caucus-track > span').attr('style').match(/width:([\d.]+)%/)[1]);
			assert.ok(Math.abs(barWidth - group.share / ceiling * 100) < 1e-10);
			assert.equal(Number(row.attr('data-share')), group.share);
			assert.equal(row.find('.caucus-percent').text(), `${(100 * group.share).toFixed(1)}%`);
			const baseline = topic.groups.filter(other => other.id !== group.id)
				.reduce((sum, other) => sum + other.share, 0) / 12;
			assert.ok(Math.abs(group.baseline - baseline) < 1e-12);
			if (baseline > 0) {
				assert.ok(Math.abs(group.ratio - group.share / baseline) < 1e-10);
				assert.equal(Number(row.attr('data-ratio')), group.ratio);
				assert.equal(row.find('.caucus-ratio').text(), `${group.ratio.toFixed(1)}×`);
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
			const row = $(`[data-caucus-topic="${topic.id}"] [data-caucus-position="${group.id}"]`);
			if (group.claims === 0) {
				assert.equal(group.examples.length, 0);
				assert.match(row.find('.caucus-empty').text(), /No eligible claims assigned/);
				assert.equal(row.find('.caucus-evidence').length, 0);
				continue;
			}
			assert.equal(row.find('.caucus-statement').text(), group.examples[0].claim_text
				.replace(/^Commitment to /, 'Commits to ')
				.replace(/^Support for /, 'Supports ')
				.replace(/^Opposition to /, 'Opposes '));
			assert.equal(row.find('.caucus-evidence[open]').length, 0);
			for (const example of group.examples) {
				const evidence = row.find(`[data-claim="${example.claim_id}"]`);
				assert.equal(evidence.find('blockquote').text(), example.evidence);
				assert.equal(evidence.find('.caucus-original').text(), example.claim_text);
				assert.equal(evidence.find('a').attr('href'), example.source_url);
			}
		}
	}
});

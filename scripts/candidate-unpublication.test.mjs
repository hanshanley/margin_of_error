import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import test from 'node:test';
import { load } from 'cheerio';

const dist = resolve('dist');

test('withdrawn candidate gallery and publication copies are not built', async () => {
	for (const path of ['which-candidate/index.html', 'artifacts/which-candidate']) {
		await assert.rejects(access(resolve(dist, path)), { code: 'ENOENT' });
	}
	for (const path of ['index.html', 'interactive-analysis/index.html', 'sitemap-0.xml', 'rss.xml']) {
		assert.doesNotMatch(await readFile(resolve(dist, path), 'utf8'), /which-candidate/);
	}
});

test('interactive analysis restores participation first with only one eager preview', async () => {
	const $ = load(await readFile(resolve(dist, 'interactive-analysis/index.html'), 'utf8'));
	const previews = $('.analysis-list .analysis-preview');
	assert.equal(previews.first().attr('href'), '/voter-participation/');
	assert.equal(previews.first().find('img').attr('loading'), 'eager');
	assert.equal(previews.find('img[loading="eager"]').length, 1);
	assert.ok(previews.length > 1);
	for (const image of previews.slice(1).find('img')) {
		assert.equal($(image).attr('loading'), 'lazy');
	}
});

import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import test from 'node:test';
import { load } from 'cheerio';

const root = new URL('../', import.meta.url);
const dist = resolve(process.env.WHICH_CANDIDATE_DIST ?? new URL('dist/', root).pathname);
const prefix = '/artifacts/which-candidate/2026-v2/';
const manifest = JSON.parse(await readFile(new URL(`public${prefix}manifest.json`, root), 'utf8'));

test('all candidate publication assets retain their complete released bytes', async () => {
	assert.equal(manifest.target_year, 2026);
	assert.equal(manifest.provisional, true);
	assert.equal(manifest.charts.length, 9);
	assert.deepEqual(manifest.comparison_years, [2016, 2018, 2020, 2022, 2024, 2026]);
	const css = await readFile(new URL('src/styles/global.css', root), 'utf8');
	const paper = css.match(/--paper:\s*(#[0-9a-f]{6})\s*;/i)[1];
	for (const chart of manifest.charts) {
		assert.equal(chart.files.marginoferror.background.toLowerCase(), paper.toLowerCase());
	}
	for (const [path, expected] of Object.entries(manifest.files)) {
		const source = await readFile(new URL(`public${prefix}${path}`, root));
		const built = await readFile(resolve(dist, `.${prefix}${path}`));
		assert.deepEqual(built, source, path);
		assert.equal(built.length, expected.bytes, path);
		assert.equal(createHash('sha256').update(built).digest('hex'), expected.sha256, path);
	}
});

test('candidate gallery exposes every figure and complete download without JavaScript', async () => {
	const html = await readFile(resolve(dist, 'which-candidate/index.html'), 'utf8');
	const $ = load(html);
	assert.equal($('iframe').length, 0);
	assert.equal($('.candidate-figure').length, 9);
	assert.equal($('.candidate-figure img[loading="eager"]').length, 1);
	assert.equal($('.candidate-figure img[loading="lazy"]').length, 8);
	assert.match($('.snapshot-note').text(), /November 7–8, 2026/);
	assert.match($('.snapshot-note').text(), /not live/);
	for (const chart of manifest.charts) {
		const figure = $(`#${chart.id}`);
		const image = figure.find('img');
		assert.equal(image.attr('src'), `${prefix}${chart.files.marginoferror.png}`);
		assert.equal(image.attr('alt'), chart.alt);
		assert.equal(Number(image.attr('width')), chart.files.marginoferror.width);
		assert.equal(Number(image.attr('height')), chart.files.marginoferror.height);
		assert.equal(figure.find('figcaption').text(), chart.caption);
		assert.equal(figure.find(`a[href="${prefix}${chart.data}"][download]`).length, 1);
		assert.equal(figure.find(`a[href="${prefix}${chart.files.substack.png}"][download]`).length, 1);
	}
	for (const path of Object.values(manifest.downloads)) {
		assert.equal($(`a[href="${prefix}${path}"][download]`).length, 1);
	}
});

test('interactive analysis leads with the new gallery and eagerly loads only its first preview', async () => {
	const html = await readFile(resolve(dist, 'interactive-analysis/index.html'), 'utf8');
	const $ = load(html);
	const previews = $('.analysis-list .analysis-preview');
	assert.equal(previews.first().attr('href'), '/which-candidate/');
	assert.equal(previews.first().find('img').attr('loading'), 'eager');
	assert.equal(previews.find('img[loading="eager"]').length, 1);
	for (const image of previews.slice(1).find('img')) {
		assert.equal($(image).attr('loading'), 'lazy');
	}
});

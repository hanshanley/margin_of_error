import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import test from 'node:test';
import { load } from 'cheerio';
import { candidateDownload, candidateImage, prepareCandidatePages } from './prepare-which-candidate-pages.mjs';

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
		assert.equal(image.attr('src'), candidateImage(chart.files.marginoferror.png));
		assert.equal(image.attr('alt'), chart.alt);
		assert.equal(Number(image.attr('width')), chart.files.marginoferror.width);
		assert.equal(Number(image.attr('height')), chart.files.marginoferror.height);
		assert.equal(figure.find('figcaption').text(), chart.caption);
		assert.equal(figure.find(`a[href="${candidateDownload(chart.data)}"][download]`).length, 1);
		assert.equal(figure.find(`a[href="${candidateDownload(chart.files.substack.png)}"][download]`).length, 1);
	}
	for (const path of Object.values(manifest.downloads)) {
		assert.equal($(`a[href="${candidateDownload(path)}"][download]`).length, 1);
	}
});

test('Pages offloading verifies every remote and local byte before removing any complete download', async () => {
	const output = await mkdtemp(resolve(tmpdir(), 'candidate-pages-'));
	const files = Object.fromEntries(Object.entries(manifest.files).filter(([path]) =>
		path === 'complete-query-set.zip' || path === 'substack/house-history.png'));
	const release = {
		tag_name: '2026-v2',
		target_commitish: 'b4a0668e1b1069f8113ca5f9eb90ee6d9081c79b',
		draft: false,
		assets: Object.entries(files).map(([path, expected]) => ({
			name: path.replaceAll('/', '--'), size: expected.bytes,
			digest: `sha256:${expected.sha256}`, browser_download_url: candidateDownload(path),
		})),
	};
	try {
		for (const path of Object.keys(files)) {
			const target = resolve(output, `.${prefix}${path}`);
			await mkdir(resolve(target, '..'), { recursive: true });
			await writeFile(target, await readFile(new URL(`public${prefix}${path}`, root)));
		}
		const retained = resolve(output, 'unrelated-website-figure.png');
		await mkdir(resolve(retained, '..'), { recursive: true });
		await writeFile(retained, 'retained local website figure');
		const invalid = structuredClone(release);
		invalid.assets[1].digest = 'sha256:incorrect';
		await assert.rejects(prepareCandidatePages(output, { files }, invalid));
		for (const path of Object.keys(files)) await readFile(resolve(output, `.${prefix}${path}`));
		const corrupt = resolve(output, `.${prefix}substack/house-history.png`);
		await writeFile(corrupt, 'corrupt image');
		await assert.rejects(prepareCandidatePages(output, { files }, release));
		await readFile(resolve(output, `.${prefix}complete-query-set.zip`));
		await writeFile(corrupt, await readFile(new URL(`public${prefix}substack/house-history.png`, root)));
		assert.equal(await prepareCandidatePages(output, { files }, release), 2);
		for (const path of Object.keys(files)) {
			await assert.rejects(readFile(resolve(output, `.${prefix}${path}`)), { code: 'ENOENT' });
		}
		assert.equal(await readFile(retained, 'utf8'), 'retained local website figure');
	} finally {
		await rm(output, { recursive: true, force: true });
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

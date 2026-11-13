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
const prefix = '/artifacts/which-candidate/2026-v3/';
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
	assert.match($('.snapshot-note').text(), /Acquired November 13, 2026/);
	assert.match($('.snapshot-note').text(), /November 12–13/);
	assert.match($('.snapshot-note').text(), /405 House and 28 Senate/);
	assert.match($('.snapshot-note').text(), /not live/);
	assert.match($('.correction-note').text(), /v3 supersedes v2/);
	assert.equal($('.correction-note a[href$="/releases/tag/2026-v2"]').length, 1);
	assert.match($('.methods').text(), /only eight Blue Dogs/);
	assert.match($('.methods').text(), /nor that it shrank in 2026/);
	for (const chart of manifest.charts) {
		const figure = $(`#${chart.id}`);
		assert.ok(figure.find('h2').text().trim(), chart.id);
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

async function checkPagesOffload(version, commit, imagePath) {
	const output = await mkdtemp(resolve(tmpdir(), 'candidate-pages-'));
	const localPrefix = `/artifacts/which-candidate/${version}/`;
	const localManifest = JSON.parse(await readFile(new URL(`public${localPrefix}manifest.json`, root), 'utf8'));
	const files = Object.fromEntries(Object.entries(localManifest.files).filter(([path]) =>
		path === 'complete-query-set.zip' || path === imagePath));
	assert.equal(Object.keys(files).length, 2);
	const release = {
		tag_name: version,
		target_commitish: commit,
		draft: false,
		immutable: version === '2026-v3',
		assets: Object.entries(files).map(([path, expected]) => ({
			name: path.replaceAll('/', '--'), size: expected.bytes,
			digest: `sha256:${expected.sha256}`, browser_download_url: candidateDownload(path, version),
		})),
	};
	try {
		for (const path of Object.keys(files)) {
			const target = resolve(output, `.${localPrefix}${path}`);
			await mkdir(resolve(target, '..'), { recursive: true });
			await writeFile(target, await readFile(new URL(`public${localPrefix}${path}`, root)));
		}
		const retained = resolve(output, 'unrelated-website-figure.png');
		await mkdir(resolve(retained, '..'), { recursive: true });
		await writeFile(retained, 'retained local website figure');
		const invalid = structuredClone(release);
		invalid.assets[1].digest = 'sha256:incorrect';
		await assert.rejects(prepareCandidatePages(output, { files }, invalid, version));
		await assert.rejects(prepareCandidatePages(output, { files }, { ...release, draft: true }, version));
		await assert.rejects(prepareCandidatePages(output, { files }, { ...release, target_commitish: 'main' }, version));
		if (version === '2026-v3') {
			await assert.rejects(prepareCandidatePages(output, { files }, { ...release, immutable: false }, version));
		}
		for (const path of Object.keys(files)) await readFile(resolve(output, `.${localPrefix}${path}`));
		const corrupt = resolve(output, `.${localPrefix}${imagePath}`);
		await writeFile(corrupt, 'corrupt image');
		await assert.rejects(prepareCandidatePages(output, { files }, release, version));
		await readFile(resolve(output, `.${localPrefix}complete-query-set.zip`));
		await writeFile(corrupt, await readFile(new URL(`public${localPrefix}${imagePath}`, root)));
		assert.equal(await prepareCandidatePages(output, { files }, release, version), 2);
		for (const path of Object.keys(files)) {
			await assert.rejects(readFile(resolve(output, `.${localPrefix}${path}`)), { code: 'ENOENT' });
		}
		assert.equal(await readFile(retained, 'utf8'), 'retained local website figure');
	} finally {
		await rm(output, { recursive: true, force: true });
	}
}

for (const [version, commit, imagePath] of [
	['2026-v3', 'e36e39819f7e11a606634951124557e1cf346922', 'substack/moderation-history.png'],
	['2026-v2', 'b4a0668e1b1069f8113ca5f9eb90ee6d9081c79b', 'substack/house-history.png'],
]) {
	test(`Pages offloading verifies every ${version} remote and local byte before removing downloads`,
		() => checkPagesOffload(version, commit, imagePath));
}

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

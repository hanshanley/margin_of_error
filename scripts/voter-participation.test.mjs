import assert from 'node:assert/strict';
import test from 'node:test';
import { createHash } from 'node:crypto';
import { previewSvg, publicationScript } from './stage-voter-participation.mjs';
import { participationDownload } from '../public/scripts/participation-downloads.js';
import { rewriteDownloadHtml, verifyReleaseAssets, verifyRemoteFiles } from './prepare-participation-pages.mjs';
import { appendPrecinctHistory } from './build-precinct-histories.mjs';

test('precinct histories retain source counts, missing rates and groups without merging county IDs', () => {
	const histories = new Map();
	const row = { county: 'WAKE', precinct: '01-01', dimension: 'overall', group: 'All',
		participants: 75, registered: 100, turnout_pct: 75, quality: [] };
	appendPrecinctHistory(histories, 2020, [row, { ...row, county: 'DURHAM', participants: 60, turnout_pct: 60 },
		{ ...row, dimension: 'race', group: 'Example', participants: 12, registered: 20, turnout_pct: 60 }]);
	appendPrecinctHistory(histories, 2024, [{ ...row, registered: 50, turnout_pct: null, quality: ['inconsistent_counts'] }]);
	const wake = histories.get('WAKE');
	assert.deepEqual(wake.groups, [['overall', 'All'], ['race', 'Example']]);
	assert.deepEqual(wake.precincts['01-01'], [
		[2020, 0, 75, 100, 75, []], [2020, 1, 12, 20, 60, []],
		[2024, 0, 75, 50, null, ['inconsistent_counts']],
	]);
	assert.deepEqual(histories.get('DURHAM').precincts['01-01'], [[2020, 0, 60, 100, 60, []]]);
	assert.ok(!wake.precincts['01-01'].some(row => row[0] === 2022));
});

test('bulk download routing preserves full snapshots and leaves interactive JSON local', () => {
	const path = '/participation-methods/20261104T183000Z/complete-methods.zip';
	const url = participationDownload(path);
	assert.ok(url.endsWith('/participation-methods__20261104T183000Z__complete-methods.zip'));
	assert.equal(participationDownload(url), url);
	assert.equal(participationDownload('/participation-methods/20261104T183000Z/states.json'),
		'/participation-methods/20261104T183000Z/states.json');
	assert.equal(participationDownload('/party-platforms/complete-analysis.zip'), '/party-platforms/complete-analysis.zip');
	const current = participationDownload('/participation-current/20261104T220424Z/local.json');
	assert.ok(current.startsWith('https://raw.githubusercontent.com/hanshanley/margin_of_error/dc81c095cec959910c6dfb82da8c9184d7a993f9/'));
	assert.ok(current.endsWith('/20261104T220424Z/local.json'));
	assert.equal(participationDownload('/participation-current/latest.json'), '/participation-current/latest.json');
	assert.equal(rewriteDownloadHtml(`<a href="${path}" download>Full data</a><script>fetch("${path}")</script>`,
		[{ path, url }]), `<a href="${url}" download>Full data</a><script>fetch("${path}")</script>`);
});

test('pinned current data must be complete and byte-identical before removing site copies', async () => {
	const bytes = Buffer.from('{"complete":[1,2,3]}');
	const file = { path: '/current.json', url: 'source', bytes: bytes.length,
		sha256: createHash('sha256').update(bytes).digest('hex') };
	await verifyRemoteFiles([file], async () => new Response(bytes));
	await assert.rejects(verifyRemoteFiles([file], async () => new Response('', { status: 404 })), /Missing pinned complete data/);
	await assert.rejects(verifyRemoteFiles([file], async () => new Response('short')), /size changed/);
	await assert.rejects(verifyRemoteFiles([{ ...file, sha256: 'changed' }], async () => new Response(bytes)), /checksum changed/);
});
test('missing, truncated or changed release downloads stop Pages publication', () => {
	const file = { name: 'full.zip', bytes: 42, sha256: 'abc', url: 'https://example.org/full.zip' };
	const asset = { name: file.name, size: file.bytes, digest: 'sha256:abc', browser_download_url: file.url };
	verifyReleaseAssets([file], [asset]);
	assert.throws(() => verifyReleaseAssets([file], []), /Missing complete download/);
	assert.throws(() => verifyReleaseAssets([file], [{ ...asset, size: 2 }]), /size changed/);
	assert.throws(() => verifyReleaseAssets([file], [{ ...asset, digest: 'sha256:changed' }]), /checksum changed/);
});

const renderer = [
	'fetch("data/" + path)',
	'document.querySelectorAll("nav button")',
	'const chart = svg(1100, 480), x = year => 60 + (year - 1964) / 60 * 1010, y = rate => 410 - rate * 3.6;',
	'x2: 1070,', 'year += 8)', 'y: 440,', 'y1: 45, y2: 410,',
].join('\n');

test('publication renderer uses the nested data route and responsive chart without touching source', () => {
	const published = publicationScript(renderer);
	assert.ok(published.includes('fetch("/voter-participation/data/" + path)'));
	assert.ok(published.includes('document.querySelectorAll(".participation-explorer nav button")'));
	assert.ok(published.includes('$("visualization").clientWidth'));
	assert.ok(published.includes('window.addEventListener("resize"'));
	assert.ok(renderer.includes('fetch("data/" + path)'));
	assert.ok(published.startsWith('(() => {'));
});

test('changed upstream renderer cannot silently bypass the publication adaptation', () => {
	assert.throws(() => publicationScript(renderer.replace('x2: 1070,', 'x2: 1080,')),
		/renderer changed upstream/);
});

test('preview plots citizen turnout, excluding incompatible series and pre-1996 observations', () => {
	const row = { year: 1996, dimension: 'overall', age_group: 'All ages',
		denominator: 'cvap', turnout_pct: 60, election_type: 'presidential' };
	const preview = previewSvg([
		row,
		{ ...row, year: 1998, election_type: 'midterm', turnout_pct: 40 },
		{ ...row, dimension: 'race', turnout_pct: 99 },
		{ ...row, denominator: 'vap', turnout_pct: 90 },
		{ ...row, year: 1992, turnout_pct: 80 },
	]);
	assert.equal((preview.match(/<circle /g) ?? []).length, 2);
	assert.ok(preview.includes('cx="100" cy="335"'));
	assert.ok(preview.includes('Presidential elections'));
	assert.ok(preview.includes('Midterms'));
});

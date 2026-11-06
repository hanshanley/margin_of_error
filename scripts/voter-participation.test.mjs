import assert from 'node:assert/strict';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import { createHash } from 'node:crypto';
import { previewSvg, publicationScript, sourceRevision } from './stage-voter-participation.mjs';
import { participationDownload, participationHistoricalRoot } from '../public/scripts/participation-downloads.js';
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

test('historical NC year tables use the pinned complete originals without moving geometry or other data', () => {
	assert.ok(participationHistoricalRoot.includes(`/${sourceRevision}/public/data/nc/`));
	for (const year of [2002, 2004, 2022, 2024]) {
		const path = `/voter-participation/data/nc/${year}.json`;
		const url = participationDownload(path);
		assert.equal(url, participationHistoricalRoot + `${year}.json`);
		assert.equal(participationDownload(url), url);
		assert.equal(rewriteDownloadHtml(`<a href="${path}" download>Full table</a>`, [{ path, url }]),
			`<a href="${url}" download>Full table</a>`);
	}
	for (const path of ['/voter-participation/data/nc/geometry-2024.geojson',
		'/voter-participation/data/nc/summary.json', '/voter-participation/data/states.json',
		'/participation-local/AL.json.gz'])
		assert.equal(participationDownload(path), path);
});

test('only reviewed county context archives move to their complete release assets', () => {
	for (const version of ['01', '05', '10', '11', '12', '13', '14', '15', '16', '17']) {
		const path = `/participation-county-context/20261106-${version}/complete-county-participation-context-${version}.zip`;
		const url = participationDownload(path);
		assert.equal(url, `https://github.com/hanshanley/margin_of_error/releases/download/voter-county-participation-context-20261106-${version}/complete-county-participation-context-${version}.zip`);
		assert.equal(participationDownload(url), url);
		assert.equal(rewriteDownloadHtml(`<a href="${path}" download>Full context</a>`, [{ path, url }]),
			`<a href="${url}" download>Full context</a>`);
	}
	for (const path of [
		'/participation-county-context/20261106-11/review.json',
		'/participation-county-context/20261106-11/complete-source-records.json.gz',
		'/participation-county-context/20261106-11/complete-county-participation-context-10.zip',
		'/participation-county-context/20261106-18/complete-county-participation-context-18.zip',
		'/participation-county-context/20261107-01/complete-county-participation-context-01.zip',
		'/participation-county-context/20261106-11/counties-PA.geojson.gz',
	]) assert.equal(participationDownload(path), path);
});

test('only redundant context13 geometry copies move to fixed complete originals, not interactive or historical geometry', () => {
	for (const code of ['AL', 'AR', 'AZ', 'CA', 'DC', 'FL', 'GA', 'IA', 'KY', 'MO', 'NJ', 'NV', 'OR', 'PA', 'VA', 'WA', 'WY']) {
		const path = `/participation-county-context/20261106-13/geometry/county-${code}.geojson`;
		const url = participationDownload(path);
		assert.equal(url, `https://raw.githubusercontent.com/hanshanley/margin_of_error/70c141f45dae29980f2871a300934688035a2177/public${path}`);
		assert.equal(participationDownload(url), url);
	}
	for (const path of [
		'/participation-county-context/20261106-12/geometry/county-GA.geojson',
		'/participation-county-context/20261106-18/geometry/county-GA.geojson',
		'/participation-county-context/20261106-13/geometry/county-TX.geojson',
		'/participation-county-context/20261106-13/review.json',
		'/participation-context/20261104T183601Z/geometry/county-GA.geojson',
	]) assert.equal(participationDownload(path), path);
});

test('context10/11 redundant copies and context17 use only their exact verified geometry inventories', () => {
	for (const [version, revision, codes] of [
		['10', '47a0efe3e75e9498d89340a7c50e3b311f55c5dc', ['AL', 'AR', 'AZ', 'CA', 'DC', 'FL', 'IA', 'KY', 'MO', 'NJ', 'NV', 'OR', 'PA', 'VA', 'WA', 'WY']],
		['11', '784d261600f349073d3cf74ba8d168595cf6a46e', ['AL', 'AR', 'AZ', 'CA', 'DC', 'FL', 'IA', 'KY', 'MO', 'NJ', 'NV', 'OR', 'PA', 'VA', 'WA', 'WY']],
		['17', '62f1665b3cfec842e89682537ee288ee6cf1dce6', ['AL', 'AR', 'AZ', 'CA', 'DC', 'FL', 'GA', 'IA', 'KY', 'MN', 'MO', 'NJ', 'NV', 'OR', 'PA', 'VA', 'WA', 'WY']],
	]) {
		for (const code of codes) {
			const path = `/participation-county-context/20261106-${version}/geometry/county-${code}.geojson`;
			assert.equal(participationDownload(path),
				`https://raw.githubusercontent.com/hanshanley/margin_of_error/${revision}/public${path}`);
		}
		for (const file of ['review.json', 'complete-source-records.json.gz', 'geometry/county-TX.geojson']) {
			const path = `/participation-county-context/20261106-${version}/${file}`;
			assert.equal(participationDownload(path), path);
		}
	}
	for (const version of ['10', '11']) {
		for (const code of ['GA', 'MN']) {
			const path = `/participation-county-context/20261106-${version}/geometry/county-${code}.geojson`;
			assert.equal(participationDownload(path), path);
		}
	}
});

test('context14 relocates only its verified complete archive and redundant geometry, preserving older URLs', () => {
	const root = 'https://raw.githubusercontent.com/hanshanley/margin_of_error/5d2e25f80be9f9361cc37a4131eb274323c42e75/public';
	for (const code of ['AL', 'AR', 'AZ', 'CA', 'DC', 'FL', 'GA', 'IA', 'KY', 'MO', 'NJ', 'NV', 'OR', 'PA', 'VA', 'WA', 'WY']) {
		const path = `/participation-county-context/20261106-14/geometry/county-${code}.geojson`;
		assert.equal(participationDownload(path), root + path);
	}
	assert.equal(participationDownload('/participation-county-context/20261106-14/complete-county-participation-context-14.zip'),
		'https://github.com/hanshanley/margin_of_error/releases/download/voter-county-participation-context-20261106-14/complete-county-participation-context-14.zip');
	for (const path of ['/participation-county-context/20261106-14/review.json',
		'/participation-county-context/20261106-14/complete-source-records.json.gz',
		'/participation-county-context/20261106-14/geometry/county-TX.geojson'])
		assert.equal(participationDownload(path), path);
});

test('contexts15/16 and historical context12 relocate only their independently published redundant geometry', () => {
	for (const [version, revision, codes] of [
		['12', 'efd750acd9aa1b021b7de9c24b42b8aeecc32e1a',
			['AL', 'AR', 'AZ', 'CA', 'DC', 'FL', 'IA', 'KY', 'MO', 'NJ', 'NV', 'OR', 'PA', 'VA', 'WA', 'WY']],
		['15', '635697084ec43e996662eb5efe55d154fe187405',
			['AL', 'AR', 'AZ', 'CA', 'DC', 'FL', 'GA', 'IA', 'KY', 'MN', 'MO', 'NJ', 'NV', 'OR', 'PA', 'VA', 'WA', 'WY']],
		['16', '833c309f83efa6280eb9a5cfee7a17b2faff4211',
			['AL', 'AR', 'AZ', 'CA', 'DC', 'FL', 'GA', 'IA', 'KY', 'MN', 'MO', 'NJ', 'NV', 'OR', 'PA', 'VA', 'WA', 'WY']],
	]) {
		for (const code of codes) {
			const path = `/participation-county-context/20261106-${version}/geometry/county-${code}.geojson`;
			assert.equal(participationDownload(path),
				`https://raw.githubusercontent.com/hanshanley/margin_of_error/${revision}/public${path}`);
		}
		for (const file of ['review.json', 'complete-source-records.json.gz', 'geometry/county-TX.geojson']) {
			const path = `/participation-county-context/20261106-${version}/${file}`;
			assert.equal(participationDownload(path), path);
		}
	}
	for (const path of ['/participation-county-context/20261106-12/geometry/county-MN.geojson',
		'/participation-county-context/20261106-14/geometry/county-MN.geojson',
		'/participation-context/20261104T183601Z/geometry/county-MN.geojson',
		'/participation-county-context/20261106-09/geometry/county-PA.geojson'])
		assert.equal(participationDownload(path), path);
});

test('different pinned paths may share filenames but every entire original must still match', async () => {
	const files = ['13', '14'].map(version => {
		const bytes = Buffer.from(`complete-context-${version}`);
		return { name: 'county-PA.geojson', path: `/context${version}/county-PA.geojson`,
			url: `source${version}`, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') };
	});
	await verifyRemoteFiles(files, async url => new Response(`complete-context-${url.slice(-2)}`));
	await assert.rejects(verifyRemoteFiles(files, async () => new Response('complete-context-13')), /checksum changed/);
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
	assert.throws(() => verifyReleaseAssets([file, file], [asset]), /Release asset names must be unique/);
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
	assert.ok(published.includes('fetch(participationDownload("/voter-participation/data/" + path))'));
	assert.ok(published.includes(participationDownload.toString()));
	assert.ok(published.includes(JSON.stringify(participationHistoricalRoot)));
	assert.ok(published.includes('document.querySelectorAll(".participation-explorer nav button")'));
	assert.ok(published.includes('$("visualization").clientWidth'));
	assert.ok(published.includes('window.addEventListener("resize"'));
	assert.ok(renderer.includes('fetch("data/" + path)'));
	assert.ok(published.startsWith('(() => {'));
});

test('standalone compatibility renderer includes every dependency of the shared download router', () => {
	const window = { addEventListener() {} };
	runInNewContext(publicationScript(`/*${renderer}*/\nwindow.download = participationDownload;`), { window });
	for (const path of [
		'/participation-county-context/20261106-13/geometry/county-GA.geojson',
		'/participation-county-context/20261106-13/complete-county-participation-context-13.zip',
		'/voter-participation/data/nc/2024.json',
		'/participation-methods/20261104T183000Z/complete-methods.zip',
		'/participation-current/20261104T220424Z/local.json',
	]) assert.equal(window.download(path), participationDownload(path));
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

import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile, unlink } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const releaseRoot = 'https://github.com/hanshanley/which-candidate/releases/download/2026-v2/';
const sourceCommit = 'b4a0668e1b1069f8113ca5f9eb90ee6d9081c79b';
const external = path => path.endsWith('.zip') || path.startsWith('substack/');
const assetName = path => path.replaceAll('/', '--');
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

export function candidateDownload(path) {
	return external(path) ? releaseRoot + assetName(path) : `/artifacts/which-candidate/2026-v2/${path}`;
}

export async function prepareCandidatePages(output, manifest, release) {
	assert.equal(release.tag_name, '2026-v2');
	assert.equal(release.target_commitish, sourceCommit);
	assert.equal(release.draft, false);
	const assets = new Map(release.assets.map(asset => [asset.name, asset]));
	const removable = [];
	for (const [path, expected] of Object.entries(manifest.files).filter(([path]) => external(path))) {
		assert.ok(!path.split('/').includes('..') && !path.startsWith('/'), `Unsafe publication path: ${path}`);
		const asset = assets.get(assetName(path));
		assert.ok(asset, `Missing complete candidate download: ${path}`);
		assert.equal(asset.size, expected.bytes, path);
		assert.equal(asset.digest, `sha256:${expected.sha256}`, path);
		assert.equal(asset.browser_download_url, candidateDownload(path), path);
		const local = resolve(output, 'artifacts/which-candidate/2026-v2', path);
		const bytes = await readFile(local);
		assert.equal(bytes.length, expected.bytes, path);
		assert.equal(sha256(bytes), expected.sha256, path);
		removable.push(local);
	}
	assert.ok(removable.length, 'No candidate downloads were verified');
	for (const path of removable) await unlink(path);
	return removable.length;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	const manifest = JSON.parse(await readFile(new URL('../public/artifacts/which-candidate/2026-v2/manifest.json', import.meta.url)));
	const release = JSON.parse(execFileSync('gh', ['api', 'repos/hanshanley/which-candidate/releases/tags/2026-v2'], { encoding: 'utf8' }));
	const count = await prepareCandidatePages(resolve('dist'), manifest, release);
	console.log(`Verified ${count} complete candidate downloads on the pinned release; website figures remain local.`);
}

import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile, unlink } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const releases = {
	'2026-v3': { commit: 'e36e39819f7e11a606634951124557e1cf346922', immutable: true },
	'2026-v2': { commit: 'b4a0668e1b1069f8113ca5f9eb90ee6d9081c79b', immutable: false },
};
const assetName = path => path.replaceAll('/', '--');
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

export function candidateDownload(path, version = '2026-v3') {
	assert.ok(Object.hasOwn(releases, version), `Unknown candidate release: ${version}`);
	return `https://github.com/hanshanley/which-candidate/releases/download/${version}/${assetName(path)}`;
}

export function candidateImage(path, version = '2026-v3') {
	assert.ok(Object.hasOwn(releases, version), `Unknown candidate release: ${version}`);
	return `https://raw.githubusercontent.com/hanshanley/which-candidate/${releases[version].commit}/publication/${version}/${path}`;
}

export async function prepareCandidatePages(output, manifest, release, version = '2026-v3') {
	assert.ok(Object.hasOwn(releases, version), `Unknown candidate release: ${version}`);
	assert.equal(release.tag_name, version);
	assert.equal(release.target_commitish, releases[version].commit);
	assert.equal(release.draft, false);
	if (releases[version].immutable) assert.equal(release.immutable, true);
	const assets = new Map(release.assets.map(asset => [asset.name, asset]));
	const removable = [];
	for (const [path, expected] of Object.entries(manifest.files)) {
		assert.ok(!path.split('/').includes('..') && !path.startsWith('/'), `Unsafe publication path: ${path}`);
		const asset = assets.get(assetName(path));
		assert.ok(asset, `Missing complete candidate download: ${path}`);
		assert.equal(asset.size, expected.bytes, path);
		assert.equal(asset.digest, `sha256:${expected.sha256}`, path);
		assert.equal(asset.browser_download_url, candidateDownload(path, version), path);
		const local = resolve(output, 'artifacts/which-candidate', version, path);
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
	for (const version of Object.keys(releases)) {
		const bytes = await readFile(new URL(`../public/artifacts/which-candidate/${version}/manifest.json`, import.meta.url));
		const manifest = JSON.parse(bytes);
		const release = JSON.parse(execFileSync('gh', ['api', `repos/hanshanley/which-candidate/releases/tags/${version}`], { encoding: 'utf8' }));
		const files = { ...manifest.files, 'manifest.json': { bytes: bytes.length, sha256: sha256(bytes) } };
		const count = await prepareCandidatePages(resolve('dist'), { files }, release, version);
		console.log(`Verified ${count} complete ${version} downloads before offloading build copies; source and archived downloads remain intact.`);
	}
}

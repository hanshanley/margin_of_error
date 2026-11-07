import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { once } from 'node:events';
import { copyFile, mkdtemp, readdir, readFile, rmdir, stat, unlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { participationCurrentRoot, participationHistoricalRoot, participationCountyContextRoots, participationDownload, participationRelease } from '../public/scripts/participation-downloads.js';

const repository = 'hanshanley/margin_of_error';
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const gh = args => execFileSync('gh', args, { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 });

async function filesUnder(directory) {
	const paths = [];
	for (const entry of await readdir(directory, { withFileTypes: true })) {
		const path = join(directory, entry.name);
		if (entry.isDirectory()) paths.push(...await filesUnder(path));
		else if (entry.isFile()) paths.push(path);
	}
	return paths.sort();
}

export function rewriteDownloadHtml(html, files) {
	for (const file of files) {
		html = html.replaceAll(`href="${file.path}"`, `href="${file.url}"`);
	}
	return html;
}

export function verifyReleaseAssets(files, assets) {
	assert.equal(new Set(files.map(file => file.name)).size, files.length, 'Release asset names must be unique');
	const byName = new Map(assets.map(asset => [asset.name, asset]));
	for (const file of files) {
		const asset = byName.get(file.name);
		assert.ok(asset, `Missing complete download: ${file.name}`);
		assert.equal(asset.size, file.bytes, `Download size changed: ${file.name}`);
		assert.equal(asset.digest, `sha256:${file.sha256}`, `Download checksum changed: ${file.name}`);
		assert.equal(asset.browser_download_url, file.url);
	}
}

export async function verifyRemoteFiles(files, fetcher = fetch) {
	for (const file of files) {
		const response = await fetcher(file.url);
		assert.ok(response.ok, `Missing pinned complete data: ${file.path}`);
		const bytes = Buffer.from(await response.arrayBuffer());
		assert.equal(bytes.length, file.bytes, `Pinned data size changed: ${file.path}`);
		assert.equal(sha256(bytes), file.sha256, `Pinned data checksum changed: ${file.path}`);
	}
}

export function verifyPagesByteCounts(bytes, archiveBytes) {
	assert.ok(bytes < 1_000_000_000, `Published site exceeds the 1 GB Pages limit: ${bytes} bytes`);
	assert.ok(archiveBytes < 1_000_000_000,
		`Pages tar artifact exceeds the 1 GB limit including headers/padding: ${archiveBytes} bytes`);
}

export async function verifyPagesSize(output) {
	const bytes = (await Promise.all((await filesUnder(output)).map(async path => (await stat(path)).size)))
		.reduce((total, size) => total + size, 0);
	assert.ok(bytes < 1_000_000_000, `Published site exceeds the 1 GB Pages limit: ${bytes} bytes`);
	const archive = spawn('tar', [
		'--dereference', ...(process.platform === 'darwin' ? [] : ['--hard-dereference']),
		`--format=${process.platform === 'darwin' ? 'gnutar' : 'gnu'}`,
		'--directory', output, '-cf', '-', '--exclude=.git', '--exclude=.github',
		...(process.platform === 'darwin' ? ['--exclude=*/.[!.]*'] : ['--exclude=.[^/]*']), '.',
	], { stdio: ['ignore', 'pipe', 'inherit'] });
	let archiveBytes = 0;
	const [[code]] = await Promise.all([
		once(archive, 'close'),
		(async () => { for await (const chunk of archive.stdout) archiveBytes += chunk.length; })(),
	]);
	assert.equal(code, 0, 'Could not measure the Pages tar artifact');
	assert.ok(archiveBytes >= bytes + 1024, 'Pages tar measurement omitted site file contents');
	verifyPagesByteCounts(bytes, archiveBytes);
	return { bytes, archiveBytes };
}

export async function preparePages(output, upload = false) {
	const paths = await filesUnder(output);
	const files = [];
	for (const path of paths) {
		const name = '/' + relative(output, path).split('\\').join('/');
		const url = participationDownload(name);
		if (url === name) continue;
		const bytes = await readFile(path);
		files.push({ path: name, name: url.split('/').at(-1), url, bytes: bytes.length, sha256: sha256(bytes) });
	}
	assert.ok(files.length, 'Prepare a fresh, complete build before publishing');
	const pinnedFiles = files.filter(file => [participationCurrentRoot, participationHistoricalRoot, ...Object.values(participationCountyContextRoots),
		'https://github.com/hanshanley/margin_of_error/releases/download/voter-participation-swing-20261106-02/',
		'https://github.com/hanshanley/margin_of_error/releases/download/voter-county-participation-context-']
		.some(root => file.url.startsWith(root)));
	const releaseFiles = files.filter(file => !pinnedFiles.includes(file));
	let release = JSON.parse(gh(['api', `repos/${repository}/releases/tags/${participationRelease}`]));
	if (upload) {
		const existing = new Set(release.assets.map(asset => asset.name));
		const temporary = await mkdtemp(join(tmpdir(), 'participation-downloads-'));
		const staged = [];
		try {
			for (const file of releaseFiles.filter(file => !existing.has(file.name))) {
				const path = join(temporary, file.name);
				await copyFile(join(output, file.path.slice(1)), path);
				staged.push(path);
			}
			if (staged.length) gh(['release', 'upload', participationRelease, '--repo', repository, ...staged]);
		} finally {
			for (const path of staged) await unlink(path);
			await rmdir(temporary);
		}
		release = JSON.parse(gh(['api', `repos/${repository}/releases/tags/${participationRelease}`]));
	}
	verifyReleaseAssets(releaseFiles, release.assets);
	await verifyRemoteFiles(pinnedFiles);
	for (const path of paths.filter(path => path.endsWith('.html'))) {
		const html = await readFile(path, 'utf8');
		const rewritten = rewriteDownloadHtml(html, files);
		if (rewritten !== html) await writeFile(path, rewritten);
	}
	await writeFile(join(output, 'participation-downloads.json'), JSON.stringify({
		release: participationRelease, files,
	}, null, 2) + '\n');
	for (const file of files) await unlink(join(output, file.path.slice(1)));
	const { bytes, archiveBytes } = await verifyPagesSize(output);
	console.log(`Verified ${files.length} byte-identical bulk downloads; Pages site is ${bytes} bytes`);
	console.log(`Verified Pages tar artifact is ${archiveBytes} bytes including headers/padding`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	await preparePages(resolve('dist'), process.argv.includes('--upload'));
}

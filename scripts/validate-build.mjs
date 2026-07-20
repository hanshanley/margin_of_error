import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = new URL('../dist/', import.meta.url);
const projectRoot = new URL('../', import.meta.url);

async function text(path) {
	return readFile(new URL(path, root), 'utf8');
}

async function collectTextFiles(directory) {
	const files = [];
	for (const entry of await readdir(directory, { withFileTypes: true })) {
		const path = join(directory, entry.name);
		if (entry.isDirectory()) {
			files.push(...(await collectTextFiles(path)));
		} else if (/\.(?:html|xml|css|js|txt)$/.test(entry.name)) {
			files.push(path);
		}
	}
	return files;
}

const requiredFiles = [
	'index.html',
	'404.html',
	'about/index.html',
	'archive/index.html',
	'home/index.html',
	'my-first-blog-post/index.html',
	'rss.xml',
	'robots.txt',
	'sitemap-index.xml',
	'CNAME',
];

for (const file of requiredFiles) {
	await assert.doesNotReject(() => text(file), `Missing production file: ${file}`);
}

assert.equal((await text('CNAME')).trim(), 'www.themarginoferror.com');

const sitemapIndex = await text('sitemap-index.xml');
assert.match(sitemapIndex, /https:\/\/www\.themarginoferror\.com\/sitemap-0\.xml/);

const sitemap = await text('sitemap-0.xml');
assert.match(sitemap, /https:\/\/www\.themarginoferror\.com\/my-first-blog-post\//);
assert.doesNotMatch(sitemap, /https:\/\/www\.themarginoferror\.com\/home\//);

const manifest = JSON.parse(
	await readFile(new URL('src/data/migration-manifest.json', projectRoot), 'utf8'),
);
for (const entry of manifest) {
	const sourceFile =
		entry.sourcePath === '/home'
			? 'home/index.html'
			: `${entry.sourcePath.replace(/^\//, '')}/index.html`;
	await assert.doesNotReject(() => text(sourceFile), `Legacy route is missing: ${entry.sourcePath}`);

	if (entry.status === 'migrated') {
		const canonicalUrl = `https://www.themarginoferror.com${entry.targetPath}`;
		assert.match(sitemap, new RegExp(canonicalUrl.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
	}
}

const narrativePost = await text('my-first-blog-post/index.html');
assert.match(narrativePost, /id="tab-article"/);
assert.doesNotMatch(narrativePost, /id="tab-code"/);
assert.doesNotMatch(narrativePost, /id="tab-data"/);
assert.doesNotMatch(narrativePost, /id="tab-outputs"/);
assert.doesNotMatch(narrativePost, /id="tab-explore"/);

const homeRedirect = await text('home/index.html');
assert.match(homeRedirect, /http-equiv="refresh"/);
assert.match(homeRedirect, /rel="canonical" href="https:\/\/www\.themarginoferror\.com\/"/);

const archive = await text('archive/index.html');
const expectedArchiveOrder = [
	'the-influx-of-russian-misinfo-on-the-rrussia-subreddit',
	'timeline-of-events-in-the-build-up-to-the-russo-ukrainian-war',
	'echo-chambers-embedded-in-the-structure-of-news-media-websites',
	'us-summit-for-democracy',
	'oh-q-where-art-thou',
	'oh-q-what-art-thou',
	'my-first-blog-post',
];
const archivePositions = expectedArchiveOrder.map((slug) => archive.indexOf(`href="/${slug}"`));
assert.ok(archivePositions.every((position) => position >= 0), 'Archive is missing a legacy post');
assert.ok(
	archivePositions.every((position, index) => index === 0 || position > archivePositions[index - 1]),
	'Archive posts are not newest-first',
);
assert.equal([...archive.matchAll(/class="archive-thumb"/g)].length, expectedArchiveOrder.length);
assert.match(archive, /class="archive-thumb"[^>]*>[\s\S]*?<img /);

const outputDirectory = fileURLToPath(root);
for (const file of await collectTextFiles(outputDirectory)) {
	const contents = await readFile(file, 'utf8');
	assert.doesNotMatch(
		contents,
		/hanshanley\.github\.io/,
		`github.io leaked into ${relative(outputDirectory, file)}`,
	);
	assert.doesNotMatch(
		contents,
		/googleusercontent\.com/,
		`Google-hosted asset leaked into ${relative(outputDirectory, file)}`,
	);

	for (const match of contents.matchAll(/(?:src|href)="(\/artifacts\/legacy\/[^"]+)"/g)) {
		await assert.doesNotReject(
			() => text(match[1].slice(1)),
			`Missing migrated artifact referenced by ${relative(outputDirectory, file)}: ${match[1]}`,
		);
	}
}

console.log('Production artifact checks passed.');

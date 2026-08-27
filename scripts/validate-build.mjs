import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { load } from 'cheerio';

const root = new URL('../dist/', import.meta.url);
const projectRoot = new URL('../', import.meta.url);

async function text(path) {
	return readFile(new URL(path, root), 'utf8');
}

async function collectFiles(directory) {
	const files = [];
	for (const entry of await readdir(directory, { withFileTypes: true })) {
		const path = join(directory, entry.name);
		if (entry.isDirectory()) {
			files.push(...(await collectFiles(path)));
		} else {
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
	'logo.png',
	'favicon-32.png',
	'apple-touch-icon.png',
	'social-card.png',
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
	if (entry.sourcePath) {
		const sourceFile =
			entry.sourcePath === '/home'
				? 'home/index.html'
				: `${entry.sourcePath.replace(/^\//, '')}/index.html`;
		await assert.doesNotReject(() => text(sourceFile), `Legacy route is missing: ${entry.sourcePath}`);
	}

	if (entry.status === 'migrated') {
		const targetFile =
			entry.targetPath === '/'
				? 'index.html'
				: `${entry.targetPath.replace(/^\/|\/$/g, '')}/index.html`;
		await assert.doesNotReject(() => text(targetFile), `Migrated route is missing: ${entry.targetPath}`);
		const canonicalUrl = `https://www.themarginoferror.com${entry.targetPath}`;
		assert.match(sitemap, new RegExp(canonicalUrl.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
	}
}

const narrativePost = await text('my-first-blog-post/index.html');
assert.doesNotMatch(narrativePost, /class="post-materials"/);

const heritagePost = await text('who-are-the-real-americans-heritage/index.html');
assert.match(heritagePost, /June 29, 2026 · 11 Messidor, An CCXXXIV/);
assert.match(heritagePost, /<h1>Who are the &quot;Real&quot; Americans\?<\/h1>/);
assert.match(
	heritagePost,
	/class="post-subtitle">Heritage, Culture, and the Striving to Define An American Identity on the New Right/,
);
assert.match(heritagePost, /class="post-materials"/);
assert.match(heritagePost, />Code \+ data</);
assert.match(heritagePost, /https:\/\/github\.com\/hanshanley\/pre1870_pop/);

const about = await text('about/index.html');
assert.doesNotMatch(about, /tools I know best|Google Sites and/);

const homeRedirect = await text('home/index.html');
assert.match(homeRedirect, /http-equiv="refresh"/);
assert.match(homeRedirect, /rel="canonical" href="https:\/\/www\.themarginoferror\.com\/"/);

const qAnonHosting = await text('oh-q-where-art-thou/index.html');
assert.doesNotMatch(qAnonHosting, /description" content="&lt;img|description" content="<img/);
assert.match(qAnonHosting, /web hosts, platforms, and news sites/);

const archive = await text('archive/index.html');
const homepage = await text('index.html');
assert.doesNotMatch(homepage, /Vol\. I/i);
assert.doesNotMatch(homepage, /field notes?/i);
assert.match(
	homepage,
	/<p class="kicker">Latest essay<\/p>/,
);
assert.match(homepage, /<h1 id="lead-story-title"><a href="\/who-are-the-real-americans-heritage\/">/);
assert.match(homepage, />Read article<\/a>/);
assert.match(homepage, />Subscribe<\/a>/);
assert.match(homepage, /June 29, 2026[\s\S]{0,120}11 Messidor, An CCXXXIV/);
assert.equal([...homepage.matchAll(/class="post-row"/g)].length, 4);
for (const slug of [
	'who-are-the-real-americans-heritage',
	'a-continent-at-a-crossroads-natos',
	'the-republican-party-after-trump',
	'media-coverage-of-kamala-harris-and',
	'the-shrinking-swing-state-map',
]) {
	assert.match(homepage, new RegExp(`/artifacts/substack/${slug}/cover\\.jpg`));
}
const expectedArchiveOrder = [
	'who-are-the-real-americans-heritage',
	'a-continent-at-a-crossroads-natos',
	'the-republican-party-after-trump',
	'media-coverage-of-kamala-harris-and',
	'the-shrinking-swing-state-map',
	'the-influx-of-russian-misinfo-on-the-rrussia-subreddit',
	'timeline-of-events-in-the-build-up-to-the-russo-ukrainian-war',
	'echo-chambers-embedded-in-the-structure-of-news-media-websites',
	'us-summit-for-democracy',
	'oh-q-where-art-thou',
	'oh-q-what-art-thou',
	'my-first-blog-post',
];
const archivePositions = expectedArchiveOrder.map((slug) => archive.indexOf(`href="/${slug}/"`));
const externalArticles = JSON.parse(
	await readFile(new URL('src/data/external-articles.json', projectRoot), 'utf8'),
);
assert.ok(archivePositions.every((position) => position >= 0), 'Archive is missing a legacy post');
assert.ok(
	archivePositions.every((position, index) => index === 0 || position > archivePositions[index - 1]),
	'Archive posts are not newest-first',
);
assert.equal(
	[...archive.matchAll(/class="archive-thumb"/g)].length,
	expectedArchiveOrder.length + externalArticles.length,
);
assert.match(archive, /class="archive-thumb"[^>]*>[\s\S]*?<img /);
assert.doesNotMatch(archive, /class="archive-thumb"[^>]*aria-hidden="(?!true)"/);

const mediaCoverage = await text('media-coverage-of-kamala-harris-and/index.html');
assert.doesNotMatch(mediaCoverage, /class="post-resources"/);
assert.match(mediaCoverage, /class="post-materials"/);
assert.match(mediaCoverage, />Code</);

const natoSpending = await text('a-continent-at-a-crossroads-natos/index.html');
assert.match(natoSpending, />Code</);
assert.match(natoSpending, />Data</);

const swingStates = await text('the-shrinking-swing-state-map/index.html');
assert.match(swingStates, />Data</);

for (const article of externalArticles) {
	assert.match(archive, new RegExp(article.url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
	assert.match(archive, new RegExp(`/fieldwork/${article.slug}/`));
	const preview = await text(`fieldwork/${article.slug}/index.html`);
	assert.match(preview, new RegExp(article.url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
	assert.match(preview, /Read on DFRLab/);
	assert.match(preview, new RegExp(article.thumbnail.src.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
	assert.match(archive, new RegExp(article.thumbnail.src.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
	assert.match(
		sitemap,
		new RegExp(
			`https://www.themarginoferror.com/fieldwork/${article.slug}/`.replace(
				/[.*+?^${}()|[\]\\]/g,
				'\\$&',
			),
		),
	);
}
assert.equal([...archive.matchAll(/class="external-list"/g)].length, 1);

const outputDirectory = fileURLToPath(root);
const outputFiles = await collectFiles(outputDirectory);
const outputFileNames = new Set(outputFiles.map((file) => relative(outputDirectory, file)));

for (const file of outputFiles.filter((file) => file.endsWith('.html'))) {
	const fileName = relative(outputDirectory, file);
	const $ = load(await readFile(file, 'utf8'));
	assert.ok($('title').text().trim(), `Page title missing in ${fileName}`);
	assert.ok(
		$('meta[name="description"]').attr('content')?.trim(),
		`Meta description missing in ${fileName}`,
	);
	assert.ok($('link[rel="canonical"]').attr('href'), `Canonical URL missing in ${fileName}`);
	if (fileName !== 'home/index.html') {
		assert.equal($('h1').length, 1, `Expected one page heading in ${fileName}`);
	}

	const ids = new Set();
	$('[id]').each((_, element) => {
		const id = $(element).attr('id');
		assert.ok(!ids.has(id), `Duplicate id "${id}" in ${fileName}`);
		ids.add(id);
	});

	$('[href], [src]').each((_, element) => {
		const reference = $(element).attr('href') ?? $(element).attr('src');
		if (!reference?.startsWith('/') || reference.startsWith('//')) return;
		const path = reference.split(/[?#]/)[0];
		const target =
			path === '/' ? 'index.html' : path.endsWith('/') ? `${path.slice(1)}index.html` : path.slice(1);
		assert.ok(outputFileNames.has(target), `Missing internal target "${reference}" in ${fileName}`);
	});
}

for (const file of outputFiles.filter((file) => /\.(?:html|xml|css|js|txt)$/.test(file))) {
	const contents = await readFile(file, 'utf8');
	assert.doesNotMatch(
		contents,
		/hanshanley\.github\.io/,
		`github.io leaked into ${relative(outputDirectory, file)}`,
	);
	assert.doesNotMatch(contents, /written by<a/i, `Missing footer space in ${relative(outputDirectory, file)}`);
	assert.doesNotMatch(
		contents,
		/Thanks for reading The Margin of Error!/i,
		`Substack promotion leaked into ${relative(outputDirectory, file)}`,
	);
	assert.doesNotMatch(
		contents,
		/substackcdn\.com/,
		`Substack CDN dependency leaked into ${relative(outputDirectory, file)}`,
	);

	for (const match of contents.matchAll(/<img\b[^>]*src="\/artifacts\/[^"]+"[^>]*>/g)) {
		assert.match(match[0], /\bwidth="\d+"/, `Image width missing in ${relative(outputDirectory, file)}`);
		assert.match(match[0], /\bheight="\d+"/, `Image height missing in ${relative(outputDirectory, file)}`);
		assert.match(
			match[0],
			/\bloading="(?:lazy|eager)"/,
			`Image loading strategy missing in ${relative(outputDirectory, file)}`,
		);
		assert.match(match[0], /\bdecoding="async"/, `Async decoding missing in ${relative(outputDirectory, file)}`);
	}

	for (const match of contents.matchAll(/<iframe\b[^>]*>/g)) {
		assert.match(
			match[0],
			/src="https:\/\/datawrapper\.dwcdn\.net\//,
			`Unapproved iframe host in ${relative(outputDirectory, file)}`,
		);
		assert.match(
			match[0],
			/sandbox="allow-scripts allow-same-origin"/,
			`Iframe sandbox missing in ${relative(outputDirectory, file)}`,
		);
	}
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

import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { load } from 'cheerio';
import sharp from 'sharp';
import chartImageGroups from '../src/data/website-chart-images.json' with { type: 'json' };

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
	'are-you-an-ai/index.html',
	'archive/index.html',
	'interactive-analysis/index.html',
	'party-platforms/index.html',
	'party-platforms/sources/index.html',
	'party-platforms/publication-manifest.json',
	'home/index.html',
	'my-first-blog-post/index.html',
	'floor-letter-words-the-rise-of-congressional-profanity/index.html',
	'broken-britain-the-headwinds-battering-the-island-nation/index.html',
	'china-is-trending-understanding-china/index.html',
	'rss.xml',
	'robots.txt',
	'sitemap-index.xml',
	'CNAME',
	'logo.png',
	'favicon-32.png',
	'apple-touch-icon.png',
	'social-card.png',
	'website-chart-theme.css',
	'china-us-relations/index.html',
	'china-us-relations/publication-manifest.json',
	'china-us-relations/downloads/business-presence.json',
];

for (const file of requiredFiles) {
	await assert.doesNotReject(() => text(file), `Missing production file: ${file}`);
}

assert.equal((await text('CNAME')).trim(), 'www.themarginoferror.com');
const sourceCss = await readFile(new URL('src/styles/global.css', projectRoot), 'utf8');
const paperHex = sourceCss.match(/--paper:\s*(#[0-9a-f]{6})\s*;/i)?.[1];
assert.ok(paperHex, 'Publication paper colour is missing');
assert.ok((await text('website-chart-theme.css')).includes(`--paper: ${paperHex};`));
const paperRgb = [1, 3, 5].map((offset) => Number.parseInt(paperHex.slice(offset, offset + 2), 16));
const publicRoot = new URL('public/', projectRoot);
const publicFiles = await collectFiles(fileURLToPath(publicRoot));
for (const group of chartImageGroups.filter((group) => group.directory.startsWith('artifacts/'))) {
	const sources = group.files
		? group.files.map((file) => `${group.directory}/${file}`)
		: publicFiles.map((file) => relative(fileURLToPath(publicRoot), file))
			.filter((file) => file.startsWith(`${group.directory}/`) && file.endsWith('.png'));
	const background = [1, 3, 5].map((offset) => Number.parseInt(group.background.slice(offset, offset + 2), 16));
	for (const source of sources) {
		const destination = source.replace(/\.(?:png|jpe?g)$/i, '.website.png');
		const original = await sharp(fileURLToPath(new URL(source, publicRoot))).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
		const website = await sharp(fileURLToPath(new URL(destination, root))).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
		assert.equal(website.info.width, original.info.width, `Chart width changed: ${source}`);
		assert.equal(website.info.height, original.info.height, `Chart height changed: ${source}`);
		const expected = Buffer.from(original.data);
		const alreadyThemed = expected[3] === 255 && paperRgb.every((value, channel) => expected[channel] === value);
		for (let offset = 0; !alreadyThemed && offset < expected.length; offset += 4) {
			if (expected[offset + 3] === 255 && background.every((value, channel) => expected[offset + channel] === value)) {
				paperRgb.forEach((value, channel) => { expected[offset + channel] = value; });
			}
		}
		assert.ok(website.data.equals(expected), `Non-background chart pixels changed: ${source}`);
		assert.ok((await readFile(new URL(source, publicRoot))).equals(await readFile(new URL(source, root))), `Original image changed: ${source}`);
	}
}

const sitemapIndex = await text('sitemap-index.xml');
assert.match(sitemapIndex, /https:\/\/www\.themarginoferror\.com\/sitemap-0\.xml/);

const sitemap = await text('sitemap-0.xml');
assert.match(sitemap, /https:\/\/www\.themarginoferror\.com\/my-first-blog-post\//);
assert.match(sitemap, /https:\/\/www\.themarginoferror\.com\/are-you-an-ai\//);
assert.match(sitemap, /https:\/\/www\.themarginoferror\.com\/interactive-analysis\//);
assert.doesNotMatch(sitemap, /https:\/\/www\.themarginoferror\.com\/home\//);
assert.match(sitemap, /https:\/\/www\.themarginoferror\.com\/congressional_profanity\/activity\//);
assert.doesNotMatch(sitemap, /professional_profanity/);
assert.match(sitemap, /https:\/\/www\.themarginoferror\.com\/uk_decline\//);
assert.match(sitemap, /https:\/\/www\.themarginoferror\.com\/china-us-relations\//);

for (const [legacy, target] of [
	['professional_profanity/index.html', 'congressional_profanity/'],
	['professional_profanity/activity/index.html', 'congressional_profanity/activity/'],
	['professional_profanity/activity.html', 'congressional_profanity/activity/'],
]) {
	const redirect = await text(legacy);
	const escaped = `https://www.themarginoferror.com/${target}`.replace(/[./]/g, '\\$&');
	assert.match(redirect, new RegExp(`http-equiv="refresh" content="0; url=${escaped}"`), legacy);
	assert.match(redirect, new RegExp(`rel="canonical" href="${escaped}"`), legacy);
}

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

const aiIndex = await text('are-you-an-ai/index.html');
assert.match(aiIndex, /Are you an AI\?/);
assert.match(aiIndex, /0000-0002-4291-5896/);
assert.match(aiIndex, /Every article, in one parseable block/);
assert.match(aiIndex, /https:\/\/www\.themarginoferror\.com\/who-are-the-real-americans-heritage\//);
assert.match(aiIndex, /https:\/\/dfrlab\.org\/2021\/08\/11\/new-covid-19-conspiracy-theories/);

const homeRedirect = await text('home/index.html');
assert.match(homeRedirect, /http-equiv="refresh"/);
assert.match(homeRedirect, /rel="canonical" href="https:\/\/www\.themarginoferror\.com\/"/);

const qAnonHosting = await text('oh-q-where-art-thou/index.html');
assert.doesNotMatch(qAnonHosting, /description" content="&lt;img|description" content="<img/);
assert.match(qAnonHosting, /web hosts, platforms, and news sites/);

const archive = await text('archive/index.html');
const analysis = load(await text('interactive-analysis/index.html'));
assert.equal(analysis('h1').text(), 'Interactive analysis');
assert.equal(
	analysis('link[rel="canonical"]').attr('href'),
	'https://www.themarginoferror.com/interactive-analysis/',
);
const congressionalAnalysis = analysis('.analysis-list > li').eq(3);
assert.equal(congressionalAnalysis.find('h2 a').text(), 'The language of Congress');
assert.equal(
	congressionalAnalysis.find('h2 a').attr('href'),
	'https://www.themarginoferror.com/congressional_profanity/',
);
assert.equal(
	congressionalAnalysis.find('.primary-action').attr('href'),
	'https://www.themarginoferror.com/congressional_profanity/',
);
assert.equal(congressionalAnalysis.find('.primary-action').text(), 'Open analysis');
assert.equal(
	congressionalAnalysis.find('a:contains("Read the essay")').attr('href'),
	'/floor-letter-words-the-rise-of-congressional-profanity/',
);
assert.equal(
	congressionalAnalysis.find('img').attr('src'),
	'/artifacts/congressional-record/profanity_per_1k_last50.website.png',
);
assert.equal(analysis('.analysis-list > li').length, 4);
assert.doesNotMatch(analysis.html(), /political-ads|The language of political ads/);
assert.doesNotMatch(sitemap, /political-ads/);
await assert.rejects(readdir(new URL('political-ads/', root)), { code: 'ENOENT' });
const platformAnalysis = analysis('.analysis-list > li').eq(0);
assert.equal(platformAnalysis.find('h2 a').text(), 'National party platforms');
assert.equal(platformAnalysis.find('.primary-action').attr('href'), '/party-platforms/');
assert.equal(platformAnalysis.find('img').attr('loading'), 'eager');
const platforms = load(await text('party-platforms/index.html'));
const platformSources = load(await text('party-platforms/sources/index.html'));
const platformPages = [platforms, platformSources];
const platformData = JSON.parse(await text('party-platforms/analysis.json'));
const platformManifest = JSON.parse(await text('party-platforms/publication-manifest.json'));
assert.ok(!platformManifest.preview_only && !platformData.preview_only, 'A draft preview cannot be published');
const platformCoverPath = '/artifacts/party-platforms/three-platform-booklets-one-conversation.png';
const platformCoverBytes = await readFile(new URL(platformCoverPath.slice(1), root));
assert.deepEqual(platformCoverBytes,
	await readFile(new URL(`public${platformCoverPath}`, projectRoot)),
	'The supplied platform illustration must not be recolored');
const platformCoverSize = await sharp(platformCoverBytes).metadata();
const platformPreview = platformAnalysis.find('img');
assert.equal(platformPreview.attr('src'), platformCoverPath);
assert.equal(Number(platformPreview.attr('width')), platformCoverSize.width);
assert.equal(Number(platformPreview.attr('height')), platformCoverSize.height);
assert.equal(platformPreview.attr('loading'), 'eager');
assert.equal(platformPreview.attr('decoding'), 'async');
assert.equal(platformPreview.attr('alt'), '');
for (const selector of ['meta[property="og:image"]', 'meta[name="twitter:image"]']) {
	assert.equal(platforms(selector).attr('content'),
		`https://www.themarginoferror.com${platformCoverPath}`);
}
assert.equal(platforms('h1').text(), 'National party platforms');
assert.equal(platforms('link[rel=canonical]').attr('href'),
	'https://www.themarginoferror.com/party-platforms/');
for (const [index, page] of platformPages.entries()) {
	assert.equal(page(`img[src="${platformCoverPath}"]`).length, 0,
		'The key illustration belongs on the listing and social cards, not inside analysis pages');
	assert.equal(page('#methods, #downloads, #period-topics, .analysis-tabs, .figure-downloads').length, 0,
		'Analysis pages must not contain technical/download inventories or period discovery');
	assert.equal(page('link[rel=canonical]').attr('href'),
		`https://www.themarginoferror.com/party-platforms/${index === 0 ? '' : 'sources/'}`);
	assert.equal(page('#platform-repository').length, 1);
	assert.equal(page('#platform-repository').attr('href'),
		`https://github.com/hanshanley/dsa/tree/${platformData.source_revision}`);
}
assert.equal(platforms('#topic-list, #methods, #downloads, #period-topics').length, 0,
	'Evidence, diagnostics and period fits must not clutter the issue comparison page');
assert.equal(platformSources('#topic-list > .topic').length, platformData.topics.length);
assert.equal(platforms('#issue-topic option').length, platformData.topics.length);
assert.equal(platforms('.issue-panel').length, platformData.topics.length);
assert.equal(platforms('.issue-chart').length, 4 * platformData.topics.length);
for (const topic of platformData.topics) {
	const issue = platforms(`#issue-${topic.topic_id}`);
	assert.equal(issue.children('summary').text(), topic.title);
	for (const view of ['expanded', 'strict']) {
		for (const kind of ['overall', 'time']) {
			assert.equal(issue.find(`.issue-chart[data-view="${view}"][data-kind="${kind}"] img`).length, 1);
		}
	}
}
assert.equal(platforms('.platform-figure').length, 4 * platformData.topics.length);
assert.equal(platformSources('.platform-figure').length, 0);
assert.ok(platformPages.every(page => page('iframe').length === 0));
assert.equal(platformSources('#topic-query[type=search]').length, 1);
assert.equal(platformData.summary.claims, 26483);
assert.equal(platformData.source_revision, platformManifest.source_revision);
assert.equal(platformManifest.source_repository, 'hanshanley/dsa');
assert.match(platformManifest.source_revision, /^[0-9a-f]{40}$/);
assert.match(platforms('#issues').text(), /Missing periods remain gaps/);
assert.equal(platformAnalysis.find('a:contains("Code and data on GitHub")').attr('href'),
	`https://github.com/hanshanley/dsa/tree/${platformData.source_revision}`);
assert.ok(platformData.topics.every(topic => topic.representatives.length > 0));
for (const topic of platformData.topics) {
	assert.equal(platformSources(`#${topic.topic_id} > summary`).text(), topic.title);
	assert.equal(platformSources(`#${topic.topic_id} .claim`).length, topic.representatives.length);
	assert.equal(platforms(`#issue-${topic.topic_id} > p a`).attr('href'),
		`/party-platforms/sources/#${topic.topic_id}`);
}
for (const [path, checksum] of Object.entries(platformManifest.files)) {
	assert.equal(
		createHash('sha256').update(await readFile(new URL(`party-platforms/${path}`, root))).digest('hex'),
		checksum,
		`Platform source asset changed: ${path}`,
	);
}
for (const page of platformPages) {
	for (const anchor of page('a[data-original-chart]').toArray()) {
		assert.doesNotMatch(page(anchor).attr('href'), /\.website\.png$/);
	}
	for (const image of page('.platform-figure img').toArray()) {
		const node = page(image);
		assert.equal(node.attr('loading'), 'lazy');
		assert.equal(node.attr('decoding'), 'async');
		assert.match(node.attr('src'), /(?:\/website-figures\/.*\.png|\.website\.png)$/);
		assert.ok(node.attr('alt').length > 20);
		if (node.attr('src').includes('/website-figures/')) {
			const path = new URL(node.attr('src').slice(1), root);
			const metadata = await sharp(fileURLToPath(path)).metadata();
			assert.equal(metadata.width, Number(node.attr('width')));
			assert.equal(metadata.height, Number(node.attr('height')));
			const pixel = await sharp(fileURLToPath(path))
				.extract({ left: 0, top: 0, width: 1, height: 1 }).removeAlpha().raw().toBuffer();
			assert.deepEqual([...pixel], paperRgb, 'Platform website variant must match publication paper');
		}
	}
}
assert.ok(sitemap.includes('https://www.themarginoferror.com/party-platforms/'));
assert.ok(sitemap.includes('https://www.themarginoferror.com/party-platforms/sources/'));
const chinaAnalysis = analysis('.analysis-list > li').eq(1);
assert.equal(chinaAnalysis.find('h2 a').text(), 'U.S.–China Exchange');
assert.equal(chinaAnalysis.find('img').attr('loading'), 'lazy');
assert.equal(analysis('.analysis-list img[loading=eager]').length, 1);
for (const link of chinaAnalysis.find('h2 a, .analysis-preview, .primary-action').toArray()) {
	assert.equal(analysis(link).attr('href'), 'https://www.themarginoferror.com/china-us-relations/');
}
assert.equal(chinaAnalysis.find('img').attr('src'),
	'/artifacts/china-us-relations/us-china-fractured-network.webp');
assert.equal(chinaAnalysis.find('img').attr('width'), '1672');
assert.equal(chinaAnalysis.find('img').attr('height'), '941');
const china = load(await text('china-us-relations/index.html'));
assert.equal(china('link[rel="canonical"]').attr('href'), 'https://www.themarginoferror.com/china-us-relations/');
assert.equal(china('.publication-header nav a').length, 5);
assert.equal(china('h1').text(), 'Student exchanges');
assert.equal(china('#exchange-data').length, 1);
assert.equal(china('#chart svg[role=img]').length, 1);
assert.equal(china('.analysis-tabs a').length, 10);
assert.equal(china('.analysis-scope').text(), 'Academic ending years through 2025');
assert.equal(china('#geography option[value=TWN]').length, 0);
assert.equal(china('form.controls[hidden]').length, 1);
assert.equal(china('iframe').length, 0);
assert.equal(china('link[href="/website-chart-theme.css"]').length, 1);
const chinaManifest = JSON.parse(await text('china-us-relations/publication-manifest.json'));
assert.match(chinaManifest.source_revision, /^[0-9a-f]{40}$/);
assert.equal(chinaManifest.source_repository, 'hanshanley/china-us-relation-change');
const businessData = JSON.parse(await text('china-us-relations/downloads/business-presence.json'));
assert.equal(chinaManifest.version, 2);
assert.equal(businessData.observations.length, 468);
const exchangeData = JSON.parse(await text('china-us-relations/downloads/exchange.json'));
assert.equal(exchangeData.observations.length, chinaManifest.observations);
assert.ok(exchangeData.observations.some(r => r.frequency === 'annual' && r.year === 2025 && r.value !== null));
assert.ok(exchangeData.observations.some(r => r.frequency === 'ytd' && r.year === 2026 && r.value !== null));
for (const [name, hash] of Object.entries(chinaManifest.datasets)) {
	assert.equal(createHash('sha256').update(await readFile(new URL(`china-us-relations/downloads/${name}.json`, root))).digest('hex'), hash);
}
for (const name of ['travel.html', 'immigration.html', 'language-learning.html', 'business-presence.html', 'weibo.html']) {
	const page = load(await text(`china-us-relations/${name}`));
	assert.equal(page('.analysis-tabs a[aria-current=page]').length, 1);
	assert.equal(page('iframe').length, 0);
	for (const link of page('a[href^="figures/"]').toArray()) assert.ok(page(link).is('[data-original-chart]'));
}
const comparisonDirectory = load(await text('china-us-relations/comparisons.html'));
assert.equal(comparisonDirectory('.comparison-directory').length, 3);
assert.equal(comparisonDirectory('#regional-topic-routes').length, 1);
const travel = load(await text('china-us-relations/travel.html'));
assert.equal(travel('#measure option[selected]').attr('value'), 'visitors');
assert.match(travel('.travel-definition').text(), /not just tourism/);
const immigration = load(await text('china-us-relations/immigration.html'));
assert.equal(immigration('#green-card-grants').length, 1);
assert.equal(immigration('#new-permanent-resident-arrivals').length, 1);
assert.equal(immigration('#latest-admissions').length, 0);
const migrationData = JSON.parse(await text('china-us-relations/downloads/immigration.json'));
assert.equal(migrationData.observations.length, 206);
assert.equal(migrationData.observations.find(r => r.series_id === 'un_stock:USA:CHN' && r.year === 2024).value, 60434);
assert.equal(migrationData.observations.find(r => r.series_id === 'ohss_nationality:total' && r.year === 2025).value, 65670);
for (const [path, checksum] of Object.entries(chinaManifest.files)) {
	const bytes = await readFile(new URL(`china-us-relations/${path}`, root));
	assert.equal(createHash('sha256').update(bytes).digest('hex'), checksum, `China source asset changed: ${path}`);
}
for (const link of china('a[href^="figures/"]').toArray()) {
	const node = china(link);
	assert.ok(node.is('[data-original-chart]'));
	assert.doesNotMatch(node.attr('href'), /\.website\.png$/);
}
const ukAnalysis = analysis('.analysis-list > li').eq(2);
assert.equal(ukAnalysis.find('h2 a').text(), 'The UK, in context');
for (const link of ukAnalysis.find('h2 a, .analysis-preview, .primary-action').toArray()) {
	assert.equal(analysis(link).attr('href'), 'https://www.themarginoferror.com/uk_decline/');
}
assert.equal(
	ukAnalysis.find('.lead-actions a:contains("Read the essay")').attr('href'),
	'/broken-britain-the-headwinds-battering-the-island-nation/',
);
assert.equal(
	new URL(ukAnalysis.find('img').attr('src'), 'https://www.themarginoferror.com').href.replace(/\.website\.png$/, '.png'),
	'https://www.themarginoferror.com/uk_decline/outputs/uk_decline_scorecard.png',
);
const homepage = await text('index.html');
assert.doesNotMatch(homepage, /Vol\. I/i);
assert.doesNotMatch(homepage, /field notes?/i);
assert.match(
	homepage,
	/<p class="kicker">Latest essay<\/p>/,
);
const britainSlug = 'broken-britain-the-headwinds-battering-the-island-nation';
const chinaSlug = 'china-is-trending-understanding-china';
const chinaSubtitle = 'Chinese culture is having its moment in the sun. So why are fewer Americans visiting, studying, and learning about China?';
assert.match(homepage, new RegExp(`<h1 id="lead-story-title"><a href="/${chinaSlug}/">`));
assert.match(homepage, />Read article<\/a>/);
assert.match(homepage, />Subscribe<\/a>/);
assert.match(homepage, /October 26, 2026/);
const leadPreview = load(homepage);
assert.equal(leadPreview('.dispatches > .section-heading').text().trim(), 'Recent dispatches');
assert.equal(leadPreview('.dispatches > .section-heading > h2#dispatches-title').length, 1);
assert.equal(leadPreview('.home-deck .dek').length, 0);
assert.equal(
	leadPreview('.home-deck .lead-subtitle').text(),
	chinaSubtitle,
);
assert.equal(
	leadPreview('.home-lede .lead-image img').attr('src'),
	`/artifacts/china-us-relations/${chinaSlug}/cover.png`,
);
assert.equal(leadPreview('.home-lede .lead-image img').attr('width'), '1672');
assert.equal(leadPreview('.home-lede .lead-image img').attr('height'), '941');
assert.doesNotMatch(leadPreview('.home-deck').text(), /A look at profanity, slurs, and formal courtesy/);
assert.equal([...homepage.matchAll(/class="post-row"/g)].length, 4);
const archiveAction = leadPreview('.dispatches > .dispatches-footer > .archive-action');
assert.equal(archiveAction.length, 1);
assert.equal(archiveAction.attr('href'), '/archive/');
assert.equal(archiveAction.text(), 'View archive');
assert.equal(archiveAction.parent().prev().attr('class'), 'post-list');
for (const slug of [
	'who-are-the-real-americans-heritage',
	'a-continent-at-a-crossroads-natos',
]) {
	assert.match(homepage, new RegExp(`/artifacts/substack/${slug}/cover\\.jpg`));
}
assert.match(homepage, /\/artifacts\/congressional-record\/profanity_per_1k_last50\.website\.png/);
const expectedArchiveOrder = [
	chinaSlug,
	britainSlug,
	'floor-letter-words-the-rise-of-congressional-profanity',
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

const congressSlug = 'floor-letter-words-the-rise-of-congressional-profanity';
const congressionalPost = load(await text(`${congressSlug}/index.html`));
assert.equal(congressionalPost('h1').text(), 'Floor-Letter Words: The Rise of Congressional Profanity');
assert.equal(
	congressionalPost('.post-header a:contains("Original edition")').attr('href'),
	'https://themarginoferror.substack.com/p/floor-letter-words-the-rise-of-congressional',
);
assert.match(congressionalPost('.post-subtitle').text(), /continued decline in courtesy/);
assert.equal(congressionalPost('.post-description').length, 0);
assert.doesNotMatch(congressionalPost.html(), /A look at profanity, slurs, and formal courtesy/);
assert.equal(congressionalPost('meta[name="description"]').attr('content'), congressionalPost('.post-subtitle').text());
assert.doesNotMatch(archive, /A look at profanity, slurs, and formal courtesy/);
const congressionalArchiveEntry = load(archive)(`h2 a[href="/${congressSlug}/"]`).closest('li');
assert.equal(congressionalArchiveEntry.find('.archive-subtitle').length, 1);
assert.equal(congressionalArchiveEntry.find('.archive-subtitle').parent().find('p').length, 1);
assert.match(congressionalPost('.prose').text(), /Unfortunately, it seems I may have to find another podcast/);
assert.match(congressionalPost('.prose').text(), /Explore and see which members of Congress use the most profanity in interactive graphs or browse the analysis code on GitHub\./);
assert.equal(congressionalPost('.prose img').length, 3);
for (const file of [
	'profanity_per_1k_last50.png',
	'slurs_per_1k.png',
	'formal_courtesy_per_1k_last50.png',
]) {
	assert.equal(congressionalPost(`.prose img[src="/artifacts/congressional-record/${file.replace(/\.png$/, '.website.png')}"]`).length, 1);
	await assert.doesNotReject(() => readFile(new URL(`artifacts/congressional-record/${file}`, root)));
}
assert.equal(congressionalPost('#footnote-anchor-1').attr('href'), '#footnote-1');
assert.equal(congressionalPost('#footnote-1 a[href="#footnote-anchor-1"]').length, 1);
assert.match(congressionalPost('.post-materials').text(), /Interactive congressional language graphs/);
assert.equal(congressionalPost('a[href="https://www.themarginoferror.com/congressional_profanity/"]').length, 2);
assert.match(aiIndex, new RegExp(`https://www\\.themarginoferror\\.com/${congressSlug}/`));
const feed = load(await text('rss.xml'), { xml: true });
assert.equal(feed('item').first().find('link').text(), `https://www.themarginoferror.com/${chinaSlug}/`);
assert.equal(feed('item').eq(1).find('link').text(), `https://www.themarginoferror.com/${britainSlug}/`);
assert.equal(feed('item').eq(2).find('link').text(), `https://www.themarginoferror.com/${congressSlug}/`);

const chinaPost = load(await text(`${chinaSlug}/index.html`));
assert.equal(chinaPost('h1').text(), "China Is Trending. Understanding China Isn't");
assert.equal(chinaPost('.post-subtitle').text(), chinaSubtitle);
assert.equal(chinaPost('.post-description').length, 0);
assert.equal(chinaPost('meta[name="description"]').attr('content'), chinaSubtitle);
assert.match(chinaPost('.byline').text(), /October 26, 2026/);
assert.equal(chinaPost('.post-header a:contains("Original edition")').attr('href'),
	'https://themarginoferror.substack.com/p/5d87f9d4-239d-4733-a54a-ca1b14fcca51');
const chinaFigures = [
	'us-china-favorability.website.png',
	'hongya-cave-chongqing.jpeg',
	'chn-from_us-air_visitors-levels.website.png',
	'chn-to_us-visitors-levels.website.png',
	'chn-from_us-study_abroad-levels.website.png',
	'chinese-bachelors.website.png',
	'chn-to_us-international_students-levels.website.png',
	'new-permanent-resident-arrivals.website.png',
	'bea-USA-CHN-goods.website.png',
	'bea-CHN-USA-goods.website.png',
];
assert.deepEqual(chinaPost('.prose img').toArray().map(image => chinaPost(image).attr('src')),
	chinaFigures.map(file => `/artifacts/china-us-relations/${chinaSlug}/${file}`));
for (const image of chinaPost('.prose img').toArray()) {
	const node = chinaPost(image);
	assert.ok(node.attr('alt')?.trim());
	assert.equal(node.attr('loading'), 'lazy');
	assert.equal(node.attr('decoding'), 'async');
	assert.ok(Number(node.attr('width')) > 0 && Number(node.attr('height')) > 0);
}
assert.doesNotMatch(chinaPost('.prose').html(), /substackcdn\.com|subscription-widget|reader-supported publication/);
for (const number of [1, 2]) {
	assert.equal(chinaPost(`#footnote-anchor-${number}`).attr('href'), `#footnote-${number}`);
	assert.equal(chinaPost(`#footnote-${number} a[href="#footnote-anchor-${number}"]`).length, 1);
}
assert.equal(chinaPost('.prose h6').length, 2);
assert.match(chinaPost('.prose h6').last().text(), /Hongya Cave \(洪崖洞, Hóngyádòng\)/);
assert.match(chinaPost('.prose').text(), /will inspire a few members of Gen Z and Gen Alpha to learn some 汉字 and visit China for themselves/);
assert.equal(chinaPost('.post-materials a[href="https://www.themarginoferror.com/china-us-relations/"]').length, 1);
assert.equal(chinaPost('.post-materials a[href="https://github.com/hanshanley/china-us-relation-change"]').length, 1);
assert.equal(chinaAnalysis.find('a:contains("Read the essay")').attr('href'), `/${chinaSlug}/`);
assert.equal(chinaAnalysis.find('.lead-actions a[href="https://github.com/hanshanley/china-us-relation-change"]').length, 0);
assert.match(aiIndex, new RegExp(`https://www\\.themarginoferror\\.com/${chinaSlug}/`));
assert.match(sitemap, new RegExp(`https://www\\.themarginoferror\\.com/${chinaSlug}/`));

const britainPost = load(await text(`${britainSlug}/index.html`));
assert.equal(britainPost('h1').text(), 'Broken Britain: The Headwinds Battering the Island Nation');
assert.equal(britainPost('.post-subtitle').text(), 'Stagnant incomes, strained public services, and fractured politics are bringing Britain to a standstill');
assert.equal(britainPost('.post-description').length, 0);
assert.equal(britainPost('meta[name="description"]').attr('content'), britainPost('.post-subtitle').text());
assert.match(britainPost('.byline').text(), /October 19, 2026/);
assert.equal(
	britainPost('.post-header a:contains("Original edition")').attr('href'),
	'https://themarginoferror.substack.com/p/broken-britain-the-headwinds-battering',
);
assert.match(britainPost('.prose').text(), /“This is not Winston Churchill we’re dealing with,”/);
assert.match(britainPost('.prose').text(), /the U.K.’s problems may be too complicated to solve simply by swapping prime ministers/);
assert.doesNotMatch(britainPost('.prose').text(), /reader-supported publication|consider becoming a free or paid subscriber/);
const britainFigures = [
	'andy-burnham.jpeg',
	'crime_csew_total.website.png',
	'uk_real_gdp_relative_to_peers.website.png',
	'median_disposable_income_oecd_history.website.png',
	'sterling_currency_strength_v2.website.png',
	'household_electricity_prices.website.png',
	'industrial_electricity_prices.website.png',
	'tuition_by_country_to_france.website.png',
	'rtt_waiting_list_per_1000.website.png',
	'ae_4hr_pct.website.png',
	'uk_austerity_spending_investment.website.png',
	'rail_london_casl.website.png',
	'public_capital_investment.website.png',
	'government_borrowing_costs.website.png',
	'tommy-robinson-post.png',
	'net_migration_by_origin.website.png',
	'gb_voting_intention_average.website.png',
];
assert.deepEqual(
	britainPost('.prose img').toArray().map((image) => britainPost(image).attr('src')),
	britainFigures.map((file) => `/artifacts/uk-decline/${file}`),
);
for (const image of britainPost('.prose img').toArray()) {
	assert.ok(britainPost(image).attr('alt')?.trim(), 'UK article figure needs meaningful alt text');
}
assert.deepEqual(
	britainPost('.prose h6').toArray().map((heading) => britainPost(heading).text()).filter(Boolean),
	[
		'Prime Minister Andrew “Andy” Burnham holds a press conference in his office.',
		'Tommy Robinson’s tweets about Afghan “invaders” and about a “two-tiered” justice system.',
	],
);
const burnhamPhoto = britainPost('.prose img[src="/artifacts/uk-decline/andy-burnham.jpeg"]');
assert.equal(burnhamPhoto.length, 1);
assert.equal(burnhamPhoto.next().prop('tagName'), 'H6');
assert.match(burnhamPhoto.next().attr('style'), /text-align:\s*center/);
const twitterScreenshot = britainPost('.prose img[src="/artifacts/uk-decline/tommy-robinson-post.png"]');
assert.equal(twitterScreenshot.length, 1);
assert.match(twitterScreenshot.attr('style'), /margin-inline:\s*auto/);
assert.equal(twitterScreenshot.next().prop('tagName'), 'H6');
assert.match(twitterScreenshot.next().attr('style'), /text-align:\s*center/);
assert.equal(britainPost('#footnote-anchor-1').attr('href'), '#footnote-1');
assert.equal(britainPost('#footnote-1 a[href="#footnote-anchor-1"]').length, 1);
assert.equal(
	britainPost('#footnote-1 a[href^="https://www.oecd.org/"]').attr('href'),
	'https://www.oecd.org/content/dam/oecd/en/about/programmes/oecd-data-collection-programme/society/income-distribution-database/income-distribution-guidelines.pdf',
);
assert.equal(britainPost('.prose a[href="https://www.themarginoferror.com/uk_decline/"]').length, 1);
assert.equal(britainPost('.post-materials a[href="https://www.themarginoferror.com/uk_decline/"]').length, 1);
assert.equal(britainPost('.post-materials a[href="https://github.com/hanshanley/uk_decline"]').length, 1);
assert.match(aiIndex, new RegExp(`https://www\\.themarginoferror\\.com/${britainSlug}/`));
const britainArchiveEntry = load(archive)(`h2 a[href="/${britainSlug}/"]`).closest('li');
assert.equal(britainArchiveEntry.find('.archive-subtitle').length, 1);
assert.equal(
	britainArchiveEntry.find('img').attr('src'),
	'/artifacts/uk-decline/uk_decline_scorecard.website.png',
);
assert.match(britainArchiveEntry.find('img').attr('style'), /object-fit:\s*contain/);
assert.match(sitemap, new RegExp(`https://www\\.themarginoferror\\.com/${britainSlug}/`));

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

if (outputFileNames.has('uk_decline/index.html')) {
	const ukHome = load(await text('uk_decline/index.html'));
	assert.equal(ukHome('.topic-card').length, 16);
	assert.equal(ukHome('iframe').length, 0);
	for (const link of ukHome('.topic-card > a').toArray()) {
		const page = `uk_decline/${ukHome(link).attr('href')}`;
		const topic = load(await text(page));
		assert.ok(topic('.chart-gallery figure img').length > 0, `No embedded charts in ${page}`);
		assert.equal(topic('iframe').length, 0);
	}
}

for (const file of outputFiles.filter((file) => file.endsWith('.html'))) {
	const fileName = relative(outputDirectory, file);
	const $ = load(await readFile(file, 'utf8'));
	if ($('.site-header').length) {
		const analysisNav = $('.site-header nav[aria-label="Primary navigation"] a').filter((_, element) =>
			new URL($(element).attr('href'), 'https://www.themarginoferror.com').pathname === '/interactive-analysis/',
		);
		assert.equal(analysisNav.length, 1, `Interactive analysis navigation missing in ${fileName}`);
		assert.equal(analysisNav.text(), 'Interactive analysis');
		assert.equal(
			analysisNav.attr('aria-current'),
			fileName === 'interactive-analysis/index.html' ? 'page' : undefined,
			`Incorrect interactive analysis navigation state in ${fileName}`,
		);
	}
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

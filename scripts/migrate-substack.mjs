import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { load } from 'cheerio';
import sharp from 'sharp';
import TurndownService from 'turndown';

const projectRoot = fileURLToPath(new URL('../', import.meta.url));
const manifestPath = join(projectRoot, 'src/data/migration-manifest.json');
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));

const articles = [
	{
		slug: 'who-are-the-real-americans-heritage',
		title: 'Who are the "Real" Americans?',
		subtitle: 'Heritage, Culture, and the Striving to Define An American Identity on the New Right',
		tags: ['American identity', 'Immigration', 'Politics'],
		artifacts: {
			data: [
				{
					label: 'Code + data',
					title: 'Pre-1870 U.S. population repository',
					description: 'Data and analysis used to examine ancestry and the U.S. population before 1870.',
					url: 'https://github.com/hanshanley/pre1870_pop',
					source: 'Hans W. A. Hanley',
					format: 'GitHub repository',
				},
			],
		},
	},
	{
		slug: 'a-continent-at-a-crossroads-natos',
		tags: ['NATO', 'Defense', 'Europe'],
		artifacts: {
			code: {
				description: 'Source code and analysis for the NATO military-spending figures.',
				repository: 'https://github.com/hanshanley/nato-and-adversaries-spending',
			},
			data: [
				{
					title: 'SIPRI Military Expenditure Database',
					description: 'Military-spending estimates used throughout the analysis.',
					url: 'https://www.sipri.org/databases/milex',
					source: 'Stockholm International Peace Research Institute',
					format: 'Database',
				},
				{
					title: 'OECD Social Expenditure Database',
					description: 'Comparative public social-spending data for NATO countries.',
					url: 'https://www.oecd.org/en/data/datasets/social-expenditure-database-socx.html',
					source: 'Organisation for Economic Co-operation and Development',
					format: 'Database',
				},
			],
		},
	},
	{
		slug: 'the-republican-party-after-trump',
		tags: ['Politics', 'National conservatism'],
	},
	{
		slug: 'media-coverage-of-kamala-harris-and',
		tags: ['Media', 'Elections', 'Data'],
		artifacts: {
			code: {
				description: 'Website list and analysis materials for the candidate-coverage comparison.',
				repository: 'https://github.com/hanshanley/harris-trump-coverage',
			},
		},
	},
	{
		slug: 'the-shrinking-swing-state-map',
		tags: ['Elections', 'Data'],
		artifacts: {
			data: [
				{
					title: 'U.S. Presidential Election Returns, 1976–2020',
					description: 'State-level presidential vote tallies used to identify changing swing states.',
					url: 'https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/42MVDX',
					source: 'MIT Election Data and Science Lab',
					format: 'CSV',
				},
			],
		},
	},
];
const localSlugs = new Set(articles.map((article) => article.slug));

function extensionFor(contentType) {
	if (contentType.includes('png')) return 'png';
	if (contentType.includes('webp')) return 'webp';
	if (contentType.includes('svg')) return 'svg';
	return 'jpg';
}

function cleanUrl(value) {
	try {
		const url = new URL(value);
		const slug = url.pathname.match(/\/p\/([^/]+)/)?.[1];
		if (slug && localSlugs.has(slug)) return `/${slug}/`;
		for (const parameter of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'r']) {
			url.searchParams.delete(parameter);
		}
		return url.href;
	} catch {
		return value;
	}
}

for (const article of articles) {
	const sourceUrl = `https://themarginoferror.substack.com/p/${article.slug}`;
	const response = await fetch(sourceUrl);
	if (!response.ok) throw new Error(`Could not fetch ${sourceUrl}: ${response.status}`);

	const html = await response.text();
	const $ = load(html);
	const body = $('.body.markup').first();
	if (!body.length) throw new Error(`Could not find article body for ${sourceUrl}`);

	const title = $('meta[property="og:title"]').attr('content')?.trim();
	const description = $('meta[property="og:description"]').attr('content')?.trim();
	const coverSource = $('meta[property="og:image"]').attr('content');
	const publishedAt = html.match(/"datePublished"\s*:\s*"([^"]+)"/)?.[1];
	if (!title || !description || !coverSource || !publishedAt) {
		throw new Error(`Missing metadata for ${sourceUrl}`);
	}

	body.find('.subscribe-widget, .button-wrapper, button, form, script, style').remove();
	body.find('p, div').each((_, element) => {
		const text = $(element).text().replace(/\s+/g, ' ').trim();
		if (
			/^Thanks for reading The Margin of Error!/i.test(text) ||
			/^This post is public so feel free to share/i.test(text)
		) {
			$(element).remove();
		}
	});
	body.find('a').each((_, anchor) => {
		const link = $(anchor);
		const text = link.text().replace(/\s+/g, ' ').trim();
		const href = link.attr('href');
		if (/^(Share|Subscribe|Thanks for reading)/i.test(text)) {
			link.remove();
		} else if (href) {
			link.attr('href', cleanUrl(href));
		}
	});

	const assetDirectory = join(projectRoot, 'public/artifacts/substack', article.slug);
	const coverResponse = await fetch(coverSource);
	if (!coverResponse.ok) throw new Error(`Could not fetch cover image for ${sourceUrl}`);
	const coverBuffer = Buffer.from(await coverResponse.arrayBuffer());
	const coverMetadata = await sharp(coverBuffer).metadata();
	const coverFileName = `cover.${extensionFor(coverResponse.headers.get('content-type') ?? '')}`;
	const coverPath = `/artifacts/substack/${article.slug}/${coverFileName}`;
	await mkdir(assetDirectory, { recursive: true });
	await writeFile(join(assetDirectory, coverFileName), coverBuffer);

	let imageNumber = 0;
	const thumbnail = {
		src: coverPath,
		alt: `${title} cover image`,
		width: coverMetadata.width,
		height: coverMetadata.height,
	};

	for (const image of body.find('img').toArray()) {
		const source = $(image).attr('src') ?? $(image).attr('data-src');
		if (!source?.startsWith('http')) continue;

		const imageResponse = await fetch(source);
		if (!imageResponse.ok) throw new Error(`Could not fetch image for ${sourceUrl}`);
		imageNumber += 1;
		const extension = extensionFor(imageResponse.headers.get('content-type') ?? '');
		const fileName = `figure-${String(imageNumber).padStart(2, '0')}.${extension}`;
		const localPath = `/artifacts/substack/${article.slug}/${fileName}`;
		const alt =
			$(image).attr('alt')?.trim() ||
			$(image).closest('figure').find('figcaption').text().replace(/\s+/g, ' ').trim() ||
			`${title}, figure ${String(imageNumber).padStart(2, '0')}`;

		const imageBuffer = Buffer.from(await imageResponse.arrayBuffer());
		const metadata = await sharp(imageBuffer).metadata();
		await mkdir(assetDirectory, { recursive: true });
		await writeFile(join(assetDirectory, fileName), imageBuffer);
		$(image).attr('src', localPath).attr('alt', alt).removeAttr('srcset').removeAttr('data-src');
		if (metadata.width && metadata.height) {
			$(image).attr('width', String(metadata.width)).attr('height', String(metadata.height));
		}
	}
	body.find('a').each((_, anchor) => {
		const link = $(anchor);
		if (link.find('img[src^="/artifacts/substack/"]').length) link.replaceWith(link.contents());
	});

	const turndown = new TurndownService({
		headingStyle: 'atx',
		bulletListMarker: '-',
		codeBlockStyle: 'fenced',
		emDelimiter: '_',
	});
	turndown.addRule('local-image', {
		filter: (node) =>
			node.nodeName === 'IMG' && node.getAttribute('src')?.startsWith('/artifacts/substack/'),
		replacement: (_content, node) => {
			const source = node.getAttribute('src');
			const alt = node.getAttribute('alt') ?? '';
			const width = node.getAttribute('width');
			const height = node.getAttribute('height');
			return `\n\n<img src="${source}" alt={${JSON.stringify(alt)}} width="${width}" height="${height}" loading="lazy" decoding="async" />\n\n`;
		},
	});
	turndown.addRule('datawrapper', {
		filter: 'iframe',
		replacement: (_content, node) => {
			const source = node.getAttribute('src');
			if (!source) return '';
			const url = new URL(source);
			if (url.protocol !== 'https:' || url.hostname !== 'datawrapper.dwcdn.net') {
				throw new Error(`Refusing unapproved iframe source: ${source}`);
			}
			return `\n\n<iframe src="${url.href}" title="Interactive chart" loading="lazy" sandbox="allow-scripts allow-same-origin"></iframe>\n\n`;
		},
	});

	const markdown = turndown
		.turndown(body.html() ?? '')
		.replace(/([\p{L}\p{N}”’")])(?=\[[^\]]+\]\(https?:)/gu, '$1 ')
		.replace(/\n{3,}/g, '\n\n')
		.trim();
	const frontmatter = [
		'---',
		`title: ${JSON.stringify(article.title ?? title)}`,
		...(article.subtitle ? [`subtitle: ${JSON.stringify(article.subtitle)}`] : []),
		`description: ${JSON.stringify(description)}`,
		`publishedAt: ${JSON.stringify(publishedAt)}`,
		`sortOrder: ${Math.floor(new Date(publishedAt).valueOf() / 1000)}`,
		'author: "Hans W. A. Hanley"',
		`tags: ${JSON.stringify(article.tags)}`,
		`legacyPath: ${JSON.stringify(`/${article.slug}`)}`,
		`originalUrl: ${JSON.stringify(sourceUrl)}`,
		...(thumbnail
			? [
					'thumbnail:',
					`  src: ${JSON.stringify(thumbnail.src)}`,
					`  alt: ${JSON.stringify(thumbnail.alt)}`,
					...(thumbnail.width ? [`  width: ${thumbnail.width}`] : []),
					...(thumbnail.height ? [`  height: ${thumbnail.height}`] : []),
				]
			: []),
		...(article.artifacts
			? [
					'artifacts:',
					...(article.artifacts.code
						? [
								'  code:',
								`    description: ${JSON.stringify(article.artifacts.code.description)}`,
								`    repository: ${JSON.stringify(article.artifacts.code.repository)}`,
							]
						: []),
					...(article.artifacts.data
						? [
								'  data:',
								...article.artifacts.data.flatMap((item) => [
									...(item.label ? [`    - label: ${JSON.stringify(item.label)}`] : []),
									`${item.label ? '      ' : '    - '}title: ${JSON.stringify(item.title)}`,
									`      description: ${JSON.stringify(item.description)}`,
									`      url: ${JSON.stringify(item.url)}`,
									`      source: ${JSON.stringify(item.source)}`,
									`      format: ${JSON.stringify(item.format)}`,
								]),
							]
						: []),
					...(article.artifacts.explore
						? [
								'  explore:',
								'    kind: "external"',
								`    url: ${JSON.stringify(article.artifacts.explore.url)}`,
								`    title: ${JSON.stringify(article.artifacts.explore.title)}`,
								`    description: ${JSON.stringify(article.artifacts.explore.description)}`,
								`    fallback: ${JSON.stringify(article.artifacts.explore.fallback)}`,
							]
						: []),
				]
			: []),
		'featured: false',
		'draft: false',
		'---',
		'',
	].join('\n');
	const outputPath = join(projectRoot, 'src/content/posts', `${article.slug}.mdx`);
	await mkdir(dirname(outputPath), { recursive: true });
	await writeFile(outputPath, `${frontmatter}${markdown}\n`);

	const manifestEntry = {
		sourceUrl,
		sourcePlatform: 'Substack',
		targetPath: `/${article.slug}/`,
		title,
		status: 'migrated',
		notes: `${imageNumber} inline image${imageNumber === 1 ? '' : 's'} copied locally.`,
	};
	const existingIndex = manifest.findIndex((item) => item.sourceUrl === sourceUrl);
	if (existingIndex >= 0) manifest[existingIndex] = manifestEntry;
	else manifest.push(manifestEntry);
	console.log(`Migrated ${title} (${imageNumber} images)`);
}

await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

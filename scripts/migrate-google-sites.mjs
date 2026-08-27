import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { load } from 'cheerio';
import sharp from 'sharp';
import TurndownService from 'turndown';

const projectRoot = fileURLToPath(new URL('../', import.meta.url));
const manifestPath = join(projectRoot, 'src/data/migration-manifest.json');
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
const origin = process.env.GOOGLE_SITES_ORIGIN?.replace(/\/$/, '');
if (!origin) {
	throw new Error('Set GOOGLE_SITES_ORIGIN to the published Google Sites source URL.');
}

const tagsByPath = {
	'/echo-chambers-embedded-in-the-structure-of-news-media-websites': ['News media', 'Networks'],
	'/oh-q-what-art-thou': ['QAnon', 'Disinformation'],
	'/oh-q-where-art-thou': ['QAnon', 'Disinformation'],
	'/the-influx-of-russian-misinfo-on-the-rrussia-subreddit': ['Disinformation', 'Russia', 'Reddit'],
	'/timeline-of-events-in-the-build-up-to-the-russo-ukrainian-war': ['Russia', 'Ukraine', 'World events'],
	'/us-summit-for-democracy': ['Democracy', 'Data'],
};

const sortOrderByPath = {
	'/the-influx-of-russian-misinfo-on-the-rrussia-subreddit': 70,
	'/timeline-of-events-in-the-build-up-to-the-russo-ukrainian-war': 60,
	'/echo-chambers-embedded-in-the-structure-of-news-media-websites': 50,
	'/us-summit-for-democracy': 40,
	'/oh-q-where-art-thou': 30,
	'/oh-q-what-art-thou': 20,
};

const turndown = new TurndownService({
	headingStyle: 'atx',
	bulletListMarker: '-',
	codeBlockStyle: 'fenced',
	emDelimiter: '_',
});
turndown.addRule('local-image', {
	filter: (node) =>
		node.nodeName === 'IMG' && node.getAttribute('src')?.startsWith('/artifacts/legacy/'),
	replacement: (_content, node) => {
		const source = node.getAttribute('src');
		const alt = node.getAttribute('alt') ?? '';
		const width = node.getAttribute('width');
		const height = node.getAttribute('height');
		return `\n\n<img src="${source}" alt={${JSON.stringify(alt)}} width="${width}" height="${height}" loading="lazy" decoding="async" />\n\n`;
	},
});

function cleanGoogleRedirect(href) {
	try {
		const url = new URL(href, origin);
		if ((url.hostname === 'www.google.com' || url.hostname === 'google.com') && url.pathname === '/url') {
			return url.searchParams.get('q') ?? href;
		}
		return url.href;
	} catch {
		return href;
	}
}

function imageExtension(contentType) {
	if (contentType.includes('png')) return 'png';
	if (contentType.includes('webp')) return 'webp';
	if (contentType.includes('svg')) return 'svg';
	return 'jpg';
}

const remigrateAll = process.argv.includes('--all');
const entries = manifest.filter(
	(item) =>
		item.sourcePath &&
		(item.status === 'pending' ||
			(remigrateAll && !['/home', '/my-first-blog-post'].includes(item.sourcePath))),
);

for (const entry of entries) {
	const response = await fetch(`${origin}${entry.sourcePath}`);
	if (!response.ok) throw new Error(`Could not fetch ${entry.sourcePath}: ${response.status}`);

	const $ = load(await response.text());
	const cells = $('div.JNdkSc-SmKAyb.LkDMRd').toArray();
	const titleIndex = cells.findIndex((cell) => $(cell).text().trim().length > 0);
	const articleCells = cells
		.slice(titleIndex + 1)
		.filter((cell) => !$(cell).text().trim().startsWith('Get in contact'));

	for (const cell of articleCells) {
		$(cell)
			.find('a')
			.each((_, anchor) => {
				const href = $(anchor).attr('href');
				if (href) $(anchor).attr('href', cleanGoogleRedirect(href));
				if (!$(anchor).text().trim() && !$(anchor).find('img').length) $(anchor).remove();
			});
	}

	const slug = entry.sourcePath.slice(1);
	const assetDirectory = join(projectRoot, 'public/artifacts/legacy', slug);
	let imageNumber = 0;
	let thumbnail;

	for (const cell of articleCells) {
		const caption = $(cell).text().replace(/\s+/g, ' ').trim();
		for (const image of $(cell).find('img').toArray()) {
			const source = $(image).attr('src');
			if (!source?.startsWith('http')) continue;

			const imageResponse = await fetch(source);
			if (!imageResponse.ok) throw new Error(`Could not fetch image for ${entry.sourcePath}`);

			imageNumber += 1;
			const extension = imageExtension(imageResponse.headers.get('content-type') ?? '');
			const fileName = `figure-${String(imageNumber).padStart(2, '0')}.${extension}`;
			const imageBuffer = Buffer.from(await imageResponse.arrayBuffer());
			const metadata = await sharp(imageBuffer).metadata();
			await mkdir(assetDirectory, { recursive: true });
			await writeFile(join(assetDirectory, fileName), imageBuffer);
			$(image).attr('src', `/artifacts/legacy/${slug}/${fileName}`);
			$(image).attr(
				'alt',
				caption.slice(0, 220) || `${entry.title}, figure ${String(imageNumber).padStart(2, '0')}`,
			);
			if (metadata.width && metadata.height) {
				$(image).attr('width', String(metadata.width)).attr('height', String(metadata.height));
			}
			thumbnail ??= {
				src: `/artifacts/legacy/${slug}/${fileName}`,
				alt: $(image).attr('alt'),
				width: metadata.width,
				height: metadata.height,
			};
		}
	}

	const markdown = articleCells
		.map((cell) => turndown.turndown($.html(cell)))
		.map((block) => block.trim())
		.filter(Boolean)
		.join('\n\n')
		.replace(/^(#{1,6})\s*\n+([^\n#].*)$/gm, '$1 $2')
		.replace(/([\p{L}\p{N}”’")])(?=\[[^\]]+\]\(https?:)/gu, '$1 ')
		.replace(/^#{1,6}\s*$/gm, '')
		.replace(/\n{3,}/g, '\n\n');
	const firstParagraph =
		markdown
			.split(/\n{2,}/)
			.find((block) => !/^(?:#|!\[)/.test(block) && block.length > 80) ?? '';
	const plainText = firstParagraph
		.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
		.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
		.replace(/[*_`\\]/g, '')
		.replace(/\s+/g, ' ')
		.trim();
	const description = `${plainText.slice(0, 185).trim().replace(/\s+\S*$/, '')}…`;
	const frontmatter = [
		'---',
		`title: ${JSON.stringify(entry.title)}`,
		`description: ${JSON.stringify(description)}`,
		'author: "Hans W. A. Hanley"',
		`tags: ${JSON.stringify(tagsByPath[entry.sourcePath] ?? ['Archive'])}`,
		`legacyPath: ${JSON.stringify(entry.sourcePath)}`,
		`sortOrder: ${sortOrderByPath[entry.sourcePath] ?? 0}`,
		...(thumbnail
			? [
					'thumbnail:',
					`  src: ${JSON.stringify(thumbnail.src)}`,
					`  alt: ${JSON.stringify(thumbnail.alt)}`,
					...(thumbnail.width ? [`  width: ${thumbnail.width}`] : []),
					...(thumbnail.height ? [`  height: ${thumbnail.height}`] : []),
				]
			: []),
		'featured: false',
		'draft: false',
		'---',
		'',
	].join('\n');
	const outputPath = join(projectRoot, 'src/content/posts', `${slug}.mdx`);

	await mkdir(dirname(outputPath), { recursive: true });
	await writeFile(outputPath, `${frontmatter}${markdown}\n`);

	entry.status = 'migrated';
	entry.notes = `${imageNumber} original inline image${imageNumber === 1 ? '' : 's'} copied locally; publication date requires confirmation.`;
	console.log(`Migrated ${entry.sourcePath} (${imageNumber} images)`);
}

await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

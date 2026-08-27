import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { load } from 'cheerio';
import sharp from 'sharp';

const projectRoot = fileURLToPath(new URL('../', import.meta.url));
const dataPath = join(projectRoot, 'src/data/external-articles.json');
const articles = JSON.parse(await readFile(dataPath, 'utf8'));

for (const article of articles) {
	const pageResponse = await fetch(article.url);
	if (!pageResponse.ok) {
		throw new Error(`Could not fetch ${article.url}: ${pageResponse.status}`);
	}

	const $ = load(await pageResponse.text());
	const source =
		$('meta[property="og:image"]').attr('content') ??
		$('meta[name="twitter:image"]').attr('content');
	if (!source) throw new Error(`No social image found for ${article.url}`);

	const imageResponse = await fetch(new URL(source, article.url));
	if (!imageResponse.ok) {
		throw new Error(`Could not fetch image for ${article.slug}: ${imageResponse.status}`);
	}

	const directory = join(projectRoot, 'public/artifacts/external', article.slug);
	const outputPath = join(directory, 'cover.jpg');
	await mkdir(directory, { recursive: true });
	const metadata = await sharp(Buffer.from(await imageResponse.arrayBuffer()))
		.rotate()
		.resize({ width: 1200, withoutEnlargement: true })
		.jpeg({ quality: 84, mozjpeg: true })
		.toFile(outputPath);

	article.thumbnail = {
		src: `/artifacts/external/${article.slug}/cover.jpg`,
		alt: `${article.title} cover image`,
		width: metadata.width,
		height: metadata.height,
	};
	console.log(`Downloaded ${article.slug}`);
}

await writeFile(dataPath, `${JSON.stringify(articles, null, 2)}\n`);

import { readdir, readFile, writeFile } from 'node:fs/promises';
import { relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { load } from 'cheerio';
import sharp from 'sharp';
import imageGroups from '../src/data/website-chart-images.json' with { type: 'json' };

const projectRoot = new URL('../', import.meta.url);
const site = 'https://www.themarginoferror.com';

function rgb(hex) {
	if (!/^#[0-9a-f]{6}$/i.test(hex)) throw new Error(`Invalid chart background: ${hex}`);
	return [1, 3, 5].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16));
}

export async function recolorChart(input, background, paper) {
	const source = rgb(background);
	const target = rgb(paper);
	const { data, info } = await sharp(input).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
	let changedPixels = 0;
	const alreadyThemed = data[3] === 255 && target.every((value, channel) => data[channel] === value);
	for (let offset = 0; !alreadyThemed && offset < data.length; offset += 4) {
		// Exact, opaque background pixels only: retain plotted colours and transparency.
		if (data[offset + 3] !== 255 || !source.every((value, channel) => data[offset + channel] === value)) continue;
		target.forEach((value, channel) => { data[offset + channel] = value; });
		changedPixels += 1;
	}
	return {
		image: await sharp(data, { raw: { width: info.width, height: info.height, channels: 4 } }).png().toBuffer(),
		changedPixels,
	};
}

async function collectFiles(directory) {
	const files = [];
	for (const entry of await readdir(directory, { withFileTypes: true })) {
		const path = resolve(directory, entry.name);
		if (entry.isDirectory()) files.push(...await collectFiles(path));
		else files.push(path);
	}
	return files;
}

export function themeChartPage(html, pagePath, images) {
	const $ = load(html, { scriptingEnabled: false, sourceCodeLocationInfo: true });
	if ($('meta[http-equiv="refresh"]').length) return html;
	const pageUrl = new URL(pagePath, `${site}/`);
	const edits = [];
	let hasCharts = false;
	const setAttribute = (element, name, value) => {
		const location = element.sourceCodeLocation;
		if (!location?.startTag) throw new Error(`Missing chart element location in ${pagePath}`);
		const escaped = value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
		const attribute = location.attrs?.[name];
		if (attribute) {
			edits.push({ start: attribute.startOffset, end: attribute.endOffset, value: `${name}="${escaped}"` });
		} else {
			const end = location.startTag.endOffset;
			const offset = end - (html.slice(end - 2, end) === '/>' ? 2 : 1);
			edits.push({ start: offset, end: offset, value: ` ${name}="${escaped}"` });
		}
	};
	const replacement = (reference) => {
		if (!reference) return undefined;
		const url = new URL(reference, pageUrl);
		if (url.origin !== site) return undefined;
		const output = images.get(url.pathname);
		if (!output) return undefined;
		if (output === url.pathname) return reference;
		url.pathname = output;
		return /^https?:\/\//.test(reference) ? url.href : `${url.pathname}${url.search}${url.hash}`;
	};

	$('img[src]').each((_, element) => {
		const image = $(element);
		const output = replacement(image.attr('src'));
		if (!output) return;
		setAttribute(element, 'src', output);
		const classes = new Set((image.attr('class') ?? '').split(/\s+/).filter(Boolean));
		classes.add('website-chart');
		setAttribute(element, 'class', [...classes].join(' '));
		hasCharts = true;
	});
	$('a[href], meta[property="og:image"], meta[name="twitter:image"]').each((_, element) => {
		const node = $(element);
		const attribute = node.is('a') ? 'href' : 'content';
		const output = replacement(node.attr(attribute));
		if (output) setAttribute(element, attribute, output);
	});
	if (!hasCharts && !/^(?:uk_decline|congressional_profanity)\//.test(pagePath)) return html;
	if (!$('link[href="/website-chart-theme.css"]').length) {
		const offset = $('head')[0]?.sourceCodeLocation?.endTag?.startOffset;
		if (offset === undefined) throw new Error(`Missing chart page head in ${pagePath}`);
		edits.push({ start: offset, end: offset, value: '<link rel="stylesheet" href="/website-chart-theme.css">' });
	}
	for (const edit of edits.sort((a, b) => b.start - a.start)) {
		html = html.slice(0, edit.start) + edit.value + html.slice(edit.end);
	}
	return html;
}

export async function buildWebsiteCharts(directory) {
	const root = resolve(directory);
	const css = await readFile(new URL('src/styles/global.css', projectRoot), 'utf8');
	const paper = css.match(/--paper:\s*(#[0-9a-f]{6})\s*;/i)?.[1];
	if (!paper) throw new Error('The publication paper colour is missing from global.css');
	const files = await collectFiles(root);
	const paths = new Set(files.map((file) => relative(root, file)));
	const images = new Map();
	let exported = 0;

	for (const group of imageGroups) {
		const selected = group.files
			? group.files.map((file) => `${group.directory}/${file}`)
			: [...paths].filter((file) => file.startsWith(`${group.directory}/`) && file.endsWith('.png') && !file.endsWith('.website.png'));
		for (const path of selected) {
			if (!paths.has(path)) throw new Error(`Registered chart is missing: ${path}`);
			const output = path.replace(/\.(?:png|jpe?g)$/i, '.website.png');
			const { image, changedPixels } = await recolorChart(resolve(root, path), group.background, paper);
			await writeFile(resolve(root, output), image);
			if (changedPixels) exported += 1;
			images.set(`/${path}`, `/${output}`);
		}
	}

	await writeFile(resolve(root, 'website-chart-theme.css'), [
		`:root { --paper: ${paper}; }`,
		'.website-chart, .analysis-preview, .mini-chart > svg { background: var(--paper); }',
		'',
	].join('\n'));
	for (const path of files.filter((file) => file.endsWith('.html'))) {
		const html = await readFile(path, 'utf8');
		const themed = themeChartPage(html, relative(root, path), images);
		if (themed !== html) await writeFile(path, themed);
	}
	console.log(`Website chart exports: ${images.size} lossless copies, ${exported} backgrounds updated to ${paper}. Originals unchanged.`);
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
	await buildWebsiteCharts(process.argv[2] ?? fileURLToPath(new URL('dist/', projectRoot)));
}

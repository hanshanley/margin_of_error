import assert from 'node:assert/strict';
import { test } from 'node:test';
import sharp from 'sharp';
import { recolorChart, themeChartPage } from './build-website-charts.mjs';

test('changes only exact opaque background pixels, preserving line colours and alpha', async () => {
	const pixels = Buffer.from([
		247, 245, 240, 255,
		61, 111, 140, 255,
		200, 90, 61, 255,
		246, 245, 240, 255,
		247, 245, 240, 80,
		0, 0, 0, 0,
	]);
	const original = await sharp(pixels, { raw: { width: 6, height: 1, channels: 4 } }).png().toBuffer();
	const before = Buffer.from(original);
	const { image, changedPixels } = await recolorChart(original, '#f7f5f0', '#f2efe7');
	const { data, info } = await sharp(image).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
	assert.equal(changedPixels, 1);
	assert.equal(info.width, 6);
	assert.equal(info.height, 1);
	assert.deepEqual([...data.subarray(0, 4)], [242, 239, 231, 255]);
	assert.deepEqual(data.subarray(4), pixels.subarray(4));
	assert.deepEqual(original, before);
});

test('JPEG website exports are lossless after decoding and leave the original buffer untouched', async () => {
	const input = await sharp({
		create: { width: 40, height: 30, channels: 3, background: '#ffffff' },
	}).composite([{
		input: await sharp({
			create: { width: 10, height: 20, channels: 3, background: '#3d6f8c' },
		}).png().toBuffer(),
		left: 15,
		top: 5,
	}]).jpeg().toBuffer();
	const before = Buffer.from(input);
	const decoded = await sharp(input).ensureAlpha().raw().toBuffer();
	const { image } = await recolorChart(input, '#ffffff', '#f2efe7');
	assert.equal((await sharp(image).metadata()).format, 'png');
	const output = await sharp(image).ensureAlpha().raw().toBuffer();
	for (let offset = 0; offset < decoded.length; offset += 4) {
		const pixel = [...decoded.subarray(offset, offset + 4)];
		assert.deepEqual(
			[...output.subarray(offset, offset + 4)],
			pixel.slice(0, 3).every((value) => value === 255) ? [242, 239, 231, 255] : pixel,
		);
	}
	assert.deepEqual(input, before);
});

test('already matching exports retain every pixel, including incidental colours from the old palette', async () => {
	const pixels = Buffer.from([242, 239, 231, 255, 247, 245, 240, 255]);
	const input = await sharp(pixels, { raw: { width: 2, height: 1, channels: 4 } }).png().toBuffer();
	const { image, changedPixels } = await recolorChart(input, '#f7f5f0', '#f2efe7');
	assert.equal(changedPixels, 0);
	assert.deepEqual(await sharp(image).ensureAlpha().raw().toBuffer(), pixels);
});

test('rewrites chart references and downloads without touching photos or embedded data', () => {
	const data = '<script type="application/json" id="data">{"D":[1,2],"R":[3,4]}</script>';
	const heading = '<h1>Who are the &quot;Real&quot; Americans?</h1>';
	const html = `<!doctype html><html><head></head><body>${heading}
		<img src="/artifacts/chart.jpg"><a href="/artifacts/chart.jpg">Download</a>
		<img src="/photo.jpg"><img src="https://elsewhere.example/artifacts/chart.jpg">
		<noscript><img src="/artifacts/chart.jpg"></noscript>${data}</body></html>`;
	const themed = themeChartPage(html, 'essay/index.html', new Map([
		['/artifacts/chart.jpg', '/artifacts/chart.website.png'],
	]));
	assert.match(themed, /src="\/artifacts\/chart.website.png" class="website-chart"/);
	assert.match(themed, /href="\/artifacts\/chart.website.png"/);
	assert.match(themed, /src="\/photo.jpg"/);
	assert.match(themed, /src="https:\/\/elsewhere.example\/artifacts\/chart.jpg"/);
	assert.ok(themed.includes(data));
	assert.ok(themed.includes(heading));
	assert.equal(themed.match(/href="\/website-chart-theme.css"/g).length, 1);
});

test('interactive dashboards get the publication background even without raster images', () => {
	const html = '<!doctype html><html><head></head><body><svg role="img"></svg></body></html>';
	assert.match(themeChartPage(html, 'congressional_profanity/index.html', new Map()), /website-chart-theme.css/);
	assert.match(themeChartPage(html, 'uk_decline/nhs.html', new Map()), /website-chart-theme.css/);
	assert.match(themeChartPage(html, 'china-us-relations/index.html', new Map()), /website-chart-theme.css/);
	assert.equal(themeChartPage(html, 'about/index.html', new Map()), html);
	const redirect = '<!doctype html><meta http-equiv="refresh" content="0; url=activity/"><h1>Redirecting</h1>';
	assert.equal(themeChartPage(redirect, 'congressional_profanity/activity.html', new Map()), redirect);
});

test('explicit original-background downloads are preserved while previews are themed', () => {
	const html = '<html><head></head><body><img src="figures/a.png">' +
		'<a data-original-chart href="figures/a.png">Margin of Error PNG</a>' +
		'<a data-original-chart href="figures/b.png">Substack PNG</a></body></html>';
	const themed = themeChartPage(html, 'china-us-relations/index.html', new Map([
		['/china-us-relations/figures/a.png', '/china-us-relations/figures/a.website.png'],
		['/china-us-relations/figures/b.png', '/china-us-relations/figures/b.website.png'],
	]));
	assert.match(themed, /src="\/china-us-relations\/figures\/a.website.png"/);
	assert.match(themed, /data-original-chart href="figures\/a.png"/);
	assert.match(themed, /data-original-chart href="figures\/b.png"/);
	assert.match(themed, /website-chart-theme.css/);
});

import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { copyFile, mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { participationCurrentRoot, participationHistoricalRoot, participationArchivedNationwideRoot, participationReleaseRoot, participationCountyContextRoots,
	participationDownload } from '../public/scripts/participation-downloads.js';

export const sourceRevision = '792e3d91609f7ee929c35b5ec15c13710db94be8';
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

function replaceOnce(text, before, after) {
	if (!text.includes(before) || text.indexOf(before) !== text.lastIndexOf(before)) {
		throw new Error(`Participation renderer changed upstream: ${before}`);
	}
	return text.replace(before, after);
}

export function publicationScript(source) {
	let script = replaceOnce(source, 'fetch("data/" + path)', 'fetch(participationDownload("/voter-participation/data/" + path))');
	script = script.replaceAll('document.querySelectorAll("nav button")',
		'document.querySelectorAll(".participation-explorer nav button")');
	script = replaceOnce(script,
		'const chart = svg(1100, 480), x = year => 60 + (year - 1964) / 60 * 1010, y = rate => 410 - rate * 3.6;',
		'const width = Math.max(420, Math.min(1100, $("visualization").clientWidth));\n'
		+ '  const right = width - 25, chart = svg(width, 420);\n'
		+ '  const x = year => 55 + (year - 1964) / 60 * (right - 55), y = rate => 350 - rate * 3;');
	script = replaceOnce(script, 'x2: 1070,', 'x2: right,');
	script = replaceOnce(script, 'year += 8)', 'year += width < 640 ? 12 : 8)');
	script = replaceOnce(script, 'y: 440,', 'y: 385,');
	script = replaceOnce(script, 'y1: 45, y2: 410,', 'y1: 45, y2: 350,');
	return `(() => {\n"use strict";\nconst participationCurrentRoot = ${JSON.stringify(participationCurrentRoot)};\n`
		+ `const participationHistoricalRoot = ${JSON.stringify(participationHistoricalRoot)};\n`
		+ `const participationArchivedNationwideRoot = ${JSON.stringify(participationArchivedNationwideRoot)};\n`
		+ `const participationReleaseRoot = ${JSON.stringify(participationReleaseRoot)};\n`
		+ `const participationCountyContextRoots = ${JSON.stringify(participationCountyContextRoots)};\n`
		+ `${participationDownload.toString()}\n${script}\nlet resizeTimer;\n`
		+ 'window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 150); });\n})();\n';
}

export function previewSvg(national) {
	const points = national.filter(row => row.dimension === 'overall' && row.age_group === 'All ages'
		&& row.denominator === 'cvap' && row.year >= 1996).sort((a, b) => a.year - b.year);
	const x = year => 100 + (year - 1996) / 28 * 980;
	const y = rate => 485 - (rate - 30) * 5;
	const lines = ['presidential', 'midterm'].map((type, index) => {
		const rows = points.filter(row => row.election_type === type);
		const color = ['#256e70', '#9d704b'][index];
		return `<path d="${rows.map((row, i) => `${i ? 'L' : 'M'}${x(row.year)},${y(row.turnout_pct)}`).join(' ')}" fill="none" stroke="${color}" stroke-width="4"/>`
			+ rows.map(row => `<circle cx="${x(row.year)}" cy="${y(row.turnout_pct)}" r="5" fill="${color}"/>`).join('');
	}).join('');
	const grid = [40, 50, 60, 70].map(rate => `<line x1="100" x2="1080" y1="${y(rate)}" y2="${y(rate)}" stroke="#d7d1c5"/>`
		+ `<text x="78" y="${y(rate) + 6}" text-anchor="end">${rate}%</text>`).join('');
	return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
		<rect width="1200" height="675" fill="#f2efe7"/>
		<text x="80" y="85" fill="#655f55" font-family="sans-serif" font-size="17" letter-spacing="3">THE MARGIN OF ERROR · INTERACTIVE ANALYSIS</text>
		<text x="80" y="161" fill="#171713" font-family="Georgia,serif" font-size="64">Who participates?</text>
		<text x="80" y="207" fill="#655f55" font-family="sans-serif" font-size="22">Reported turnout among adult citizens, 1996–2024</text>
		<g font-family="sans-serif" font-size="18" fill="#655f55">${grid}${lines}
		<text x="100" y="539">1996</text><text x="1080" y="539" text-anchor="end">2024</text>
		<line x1="100" x2="133" y1="590" y2="590" stroke="#256e70" stroke-width="4"/>
		<text x="146" y="596">Presidential elections</text>
		<line x1="450" x2="483" y1="590" y2="590" stroke="#9d704b" stroke-width="4"/>
		<text x="496" y="596">Midterms</text></g>
		<text x="100" y="640" fill="#655f55" font-family="sans-serif" font-size="16">Source: U.S. Census Bureau, Current Population Survey. Participation, not candidate choice.</text>
	</svg>`;
}

async function filesUnder(directory) {
	const files = [];
	for (const entry of await readdir(directory, { withFileTypes: true })) {
		const path = join(directory, entry.name);
		if (entry.isDirectory()) files.push(...await filesUnder(path));
		else if (entry.isFile()) files.push(path);
	}
	return files.sort();
}

export async function stage(source, output) {
	const revision = execFileSync('git', ['-C', source, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
	if (revision !== sourceRevision) throw new Error(`Expected verified source ${sourceRevision}, got ${revision}`);
	const dirty = execFileSync('git', ['-C', source, 'status', '--porcelain', '--', 'public/app.js', 'public/current.js', 'public/nationwide.js', 'public/model.js', 'public/cps.js', 'public/data'],
		{ encoding: 'utf8' }).trim();
	if (dirty) throw new Error('Participation source assets have uncommitted changes');
	const input = join(source, 'public/data');
	const analysis = JSON.parse(await readFile(join(input, 'analysis.json'), 'utf8'));
	const national = JSON.parse(await readFile(join(input, 'national.json'), 'utf8'));
	const states = JSON.parse(await readFile(join(input, 'states.json'), 'utf8'));
	if (analysis.national_rows !== national.length || analysis.state_rows !== states.length
		|| analysis.coverage.other_states !== 'not_assessed') throw new Error('Unexpected participation snapshot');
	await mkdir(output, { recursive: true });
	const existing = await readdir(output);
	if (existing.length) throw new Error(`Stage into an empty directory, not an existing export: ${output}`);
	const files = [];
	for (const path of await filesUnder(input)) {
		const name = `data/${relative(input, path)}`;
		const destination = join(output, name);
		await mkdir(dirname(destination), { recursive: true });
		await copyFile(path, destination);
		const bytes = await readFile(destination);
		files.push({ path: name, bytes: bytes.length, sha256: sha256(bytes), original: true });
	}
	for (const name of ['data/complete-analysis.zip', 'data/national.csv', 'data/states.csv',
		'data/nc/2024.csv', 'data/nc/2004.csv', 'data/coverage.csv', 'data/nationwide/latest.json',
		'data/model/validation.json', 'data/model/backtests.csv', 'data/model/complete-validation.zip',
		'data/cps/inputs.json', 'data/cps/joint-cells.csv', 'data/cps/marginals.csv',
		'data/cps/published-comparisons.csv', 'data/cps/complete-inputs.zip']) {
		if (!files.some(file => file.path === name)) throw new Error(`Missing complete dataset: ${name}`);
	}
	const script = await readFile(join(source, 'public/app.js'), 'utf8');
	await writeFile(join(output, 'app.js'), publicationScript(script));
	await copyFile(join(source, 'public/current.js'), join(output, 'current.js'));
	await copyFile(join(source, 'public/nationwide.js'), join(output, 'nationwide.js'));
	await copyFile(join(source, 'public/model.js'), join(output, 'model.js'));
	await copyFile(join(source, 'public/cps.js'), join(output, 'cps.js'));
	await sharp(Buffer.from(previewSvg(national))).png().toFile(join(output, 'preview.png'));
	for (const name of ['app.js', 'current.js', 'nationwide.js', 'model.js', 'cps.js', 'preview.png']) {
		const bytes = await readFile(join(output, name));
		files.push({ path: name, bytes: bytes.length, sha256: sha256(bytes),
			original: name === 'current.js' || name === 'nationwide.js' || name === 'model.js' || name === 'cps.js' });
	}
	await writeFile(join(output, 'publication-manifest.json'), JSON.stringify({
		source_repository: 'https://github.com/hanshanley/voter-participation',
		source_revision: revision,
		source_renderer_sha256: sha256(script),
		transform: 'Publication-relative fetches with verified immutable download routing, scoped navigation, responsive chart, publication preview; data byte-preserved.',
		files,
	}, null, 2) + '\n');
	console.log(`Staged ${files.length} verified participation assets from ${revision}`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	await stage(resolve(process.argv[2] ?? '../voter-participation'),
		resolve(process.argv[3] ?? 'public/voter-participation'));
}

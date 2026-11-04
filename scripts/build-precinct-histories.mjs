import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export function appendPrecinctHistory(histories, year, rows) {
	for (const row of rows) {
		if (!row.precinct) continue;
		if (!histories.has(row.county)) histories.set(row.county, {
			county: row.county, groups: [], precincts: Object.create(null),
		});
		const county = histories.get(row.county);
		let group = county.groups.findIndex(([dimension, group]) => dimension === row.dimension && group === row.group);
		if (group < 0) {
			group = county.groups.length;
			county.groups.push([row.dimension, row.group]);
		}
		(county.precincts[row.precinct] ??= []).push([
			year, group, row.participants, row.registered, row.turnout_pct, row.quality,
		]);
	}
}

export async function buildPrecinctHistories() {
	const root = resolve('public/voter-participation');
	const manifest = JSON.parse(await readFile(resolve(root, 'publication-manifest.json'), 'utf8'));
	const summary = JSON.parse(await readFile(resolve(root, 'data/nc/summary.json'), 'utf8'));
	const histories = new Map();
	for (const { year } of summary.filter(row => row.status === 'aggregated').sort((a, b) => a.year - b.year)) {
		const name = `data/nc/${year}.json`;
		const bytes = await readFile(resolve(root, name));
		const original = manifest.files.find(file => file.path === name);
		assert.ok(original?.original, `Missing verified original: ${name}`);
		assert.equal(createHash('sha256').update(bytes).digest('hex'), original.sha256, `Changed input: ${name}`);
		appendPrecinctHistory(histories, year, JSON.parse(bytes).records);
	}
	const output = resolve('public/participation-precinct-history/nc');
	await mkdir(output, { recursive: true });
	let bytes = 0;
	for (const [county, history] of histories) {
		assert.match(county, /^[A-Z ]+$/);
		const json = JSON.stringify({
			source_revision: manifest.source_revision,
			columns: ['year', 'group_index', 'participants', 'registered', 'turnout_pct', 'quality'],
			...history,
		}) + '\n';
		await writeFile(resolve(output, `${county}.json`), json);
		bytes += Buffer.byteLength(json);
	}
	console.log(`Built ${histories.size} county precinct-history indexes (${bytes} bytes) from verified original observations`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	await buildPrecinctHistories();
}

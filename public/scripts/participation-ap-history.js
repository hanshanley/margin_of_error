export function chooseAPView(rows, year, frame, scope) {
	if (!['2018', '2020', '2022', '2024'].includes(year) ||
		!['FINALVOTE', 'POLLCLOSE'].includes(frame)) throw new Error('Unsupported source view');
	const national = scope === 'US50_SOURCE';
	const weight = `${frame}_${national ? 'NATIONAL' : 'STATE'}_WEIGHT`;
	const held = year === '2022' && ['DE', 'WV'].includes(scope);
	const selected = held ? [] : rows.filter(row => row.year === year &&
		row.weight_field === weight && row.scope === scope &&
		!['88', '99', 'MISSING'].includes(row.group) && (national || row.dimension === 'overall'));
	const overall = selected.filter(row => row.dimension === 'overall');
	if (overall.length > 1) throw new Error('Nonunique source overall row');
	return {
		weight, rows: selected, held,
		message: held ? '2022 state inference withheld by the publisher for Delaware and West Virginia. Not zero.'
			: year === '2018' && !national
				? '2018 state-source descriptives only; the publisher reports 47 inference states despite sampling all 50.' +
					(overall.length ? '' : ' No permitted broad estimate for this view; missing is not zero.')
				: overall.length === 0
					? 'No permitted broad estimate for this view. See the complete selection-dispositions CSV; missing is not zero.'
					: 'Source-weighted modeled participation, not administratively observed turnout or population people.',
	};
}

export async function initializeAPHistory(root) {
	const controls = root.querySelector('[data-ap-controls]');
	const status = root.querySelector('[data-ap-status]');
	let rows;
	let pending;
	function render() {
		const year = root.querySelector('[data-ap-year]').value;
		const frame = root.querySelector('[data-ap-frame]').value;
		const scope = root.querySelector('[data-ap-scope]').value;
		const view = chooseAPView(rows, year, frame, scope);
		root.querySelector('[data-ap-qualification]').textContent = view.message;
		root.querySelector('[data-ap-weight]').textContent = view.weight;
		root.querySelector('[data-ap-caption]').textContent =
			`${year}: ${scope === 'US50_SOURCE' ? 'national source groups' : 'whole-state overall only'}. Native definitions retained.`;
		const body = root.querySelector('[data-ap-rows]');
		body.replaceChildren();
		for (const row of view.rows) {
			const tr = document.createElement('tr');
			tr.dataset.apViewRow = `${row.dimension}:${row.group}`;
			const values = [
				`${row.dimension}: ${row.native_labels}`,
				`${Number(row.modeled_voter_pct).toFixed(2)}%`,
				`${Number(row.modeled_nonvoter_pct).toFixed(2)}%`,
				`${Number(row.already_voted_self_report_pct).toFixed(2)}%`,
				Number(row.n).toLocaleString('en-US'),
			];
			values.forEach((value, index) => {
				const cell = document.createElement(index === 0 ? 'th' : 'td');
				if (index === 0) cell.scope = 'row';
				cell.textContent = value;
				tr.append(cell);
			});
			body.append(tr);
		}
		root.querySelector('[data-ap-dynamic]').hidden = false;
	}
	async function load() {
		if (pending) return pending;
		pending = (async () => {
			status.textContent = 'Loading the pinned public historical aggregates...';
			try {
				const response = await fetch(root.dataset.apSource, {
					credentials: 'omit', mode: 'cors', signal: AbortSignal.timeout(20000),
				});
				if (!response.ok) throw new Error('Historical source unavailable');
				const buffer = await response.arrayBuffer();
				const digest = await crypto.subtle.digest('SHA-256', buffer);
				const hash = [...new Uint8Array(digest)].map(n => n.toString(16).padStart(2, '0')).join('');
				if (hash !== root.dataset.apSha256) throw new Error('Historical source changed');
				const data = JSON.parse(new TextDecoder().decode(buffer));
				if (data.schema !== 'ap-public-participation-v1' || !Array.isArray(data.rows) ||
					data.rows.length !== 602) throw new Error('Historical source schema changed');
				rows = data.rows;
				controls.disabled = false;
				render();
				status.textContent = '602 permitted public source rows loaded and checksum-verified. State demographics are not exported.';
			} catch {
				status.textContent = 'State/group data unavailable or changed. The national table and complete downloads remain available; missing is not zero.';
			}
		})();
		return pending;
	}
	for (const control of controls.querySelectorAll('select')) control.addEventListener('change', render);
	const drawer = root.closest('#participation-research');
	if (!drawer || drawer.open) await load();
	else {
		const onToggle = () => {
			if (!drawer.open) return;
			drawer.removeEventListener('toggle', onToggle);
			void load();
		};
		drawer.addEventListener('toggle', onToggle);
	}
}

if (typeof document !== 'undefined') {
	const root = document.querySelector('#participation-ap-history');
	if (root) void initializeAPHistory(root);
}

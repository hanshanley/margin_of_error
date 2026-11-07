export function cohortSelection(records, county, method, dimension) {
  const selected = records.filter(row => row.county === county && row.dimension === dimension
    && (method === 'All included methods' || row.method_literal === method));
  const grouped = new Map();
  for (const row of selected) {
    if (!grouped.has(row.group)) grouped.set(row.group, { group: row.group, accepted_records: 0,
      positive_2024_history_matches: county === 'DURHAM' ? 0 : null,
      history_unresolved: county === 'DURHAM' ? 0 : null });
    const group = grouped.get(row.group);
    group.accepted_records += row.accepted_records;
    if (group.positive_2024_history_matches !== null) {
      group.positive_2024_history_matches += row.positive_2024_history_matches;
      group.history_unresolved += row.history_unresolved;
    }
  }
  return [...grouped.values()].sort((a, b) => a.group.localeCompare(b.group));
}

export function renderCohortRows(body, records) {
  body.replaceChildren();
  const format = value => value === null ? 'Not reviewed' : value.toLocaleString('en-US');
  for (const row of records) {
    const tr = document.createElement('tr');
    for (const [index, value] of [row.group, format(row.accepted_records),
      format(row.positive_2024_history_matches), format(row.history_unresolved)].entries()) {
      const cell = document.createElement(index ? 'td' : 'th');
      if (!index) cell.scope = 'row';
      else cell.className = 'numeric';
      cell.textContent = value;
      tr.append(cell);
    }
    body.append(tr);
  }
}

export async function initializeSwing() {
  const panel = document.querySelector('#participation-swing');
  if (!panel) return;
  const status = panel.querySelector('[data-swing-status]');
  try {
    const base = panel.dataset.base;
    const responses = await Promise.all(['aggregate-cohort.json', 'observed-comparisons.json']
      .map(file => fetch(`${base}${file}`)));
    if (responses.some(response => !response.ok)) throw new Error('Analysis inputs could not be loaded');
    const [records, observed] = await Promise.all(responses.map(response => response.json()));
    const county = panel.querySelector('[data-swing-county]');
    const method = panel.querySelector('[data-swing-method]');
    const dimension = panel.querySelector('[data-swing-dimension]');
    const contest = panel.querySelector('[data-swing-contest]');
    const body = panel.querySelector('[data-swing-rows]');
    function render() {
      const groups = cohortSelection(records, county.value, method.value, dimension.value);
      renderCohortRows(body, groups);
      const capability = panel.querySelector(`[data-dimension-note="${dimension.value}"]`);
      status.textContent = groups.length
        ? `${county.value} · ${method.value} · accepted records, not unique voters, turnout rates or vote choices.`
        : capability?.textContent ?? 'This dimension is not supplied by the reviewed cohort source.';
      for (const note of panel.querySelectorAll('[data-dimension-note]')) {
        note.hidden = note !== capability;
      }
      const comparison = observed.find(row => row.county === county.value && row.contest === contest.value);
      const target = panel.querySelector('[data-observed-swing]');
      if (!comparison || comparison.swing_margin_pp === null) {
        target.textContent = comparison?.exclusion_reasons.join('; ') || 'No comparable county result reviewed.';
      } else {
        const signed = value => `${value >= 0 ? '+' : ''}${value.toFixed(2)}`;
        target.textContent = `${signed(comparison.swing_margin_pp)} pp Democratic-minus-Republican margin change; `
          + `${signed(comparison.democratic_share_change_pp)} pp Democratic two-party share change. `
          + '2024 President vs. selected 2026 race, all reported methods and different electorates; not demographic persuasion.';
      }
    }
    function updateContests() {
      const previous = contest.value;
      contest.replaceChildren();
      for (const row of observed.filter(row => row.county === county.value)) {
        contest.add(new Option(row.contest, row.contest));
      }
      contest.value = [...contest.options].some(option => option.value === previous) ? previous : 'US SENATE';
    }
    for (const control of [county, method, dimension, contest]) {
      control.disabled = false;
      control.addEventListener('change', () => {
        if (control === county) updateContests();
        render();
      });
    }
    updateContests();
    render();
  } catch {
    status.textContent = 'Interactive inputs could not be loaded. The saved Durham table and complete downloadable analysis remain available.';
  }
}

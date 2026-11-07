import assert from 'node:assert/strict';

const states = ['D', 'R', 'O', 'B', 'N', 'X'];
const margin = { D: 1, R: -1, O: 0, B: 0, N: 0, X: 0 };
const components = ['switching', 'dropoff', 'returning', 'other_and_contest', 'eligibility_residence'];

function count(value) {
  assert.ok(Number.isSafeInteger(value) && value >= 0, 'Expected a nonnegative safe integer count');
  return value;
}

function vector(values) {
  assert.deepEqual(Object.keys(values).sort(), [...states].sort(), 'Supply every outcome, including explicit zero');
  const result = states.map(state => count(values[state]));
  count(result.reduce((sum, value) => sum + value, 0));
  return result;
}

export function twoPartyResult(democratic, republican) {
  count(democratic); count(republican);
  const total = count(democratic + republican);
  return {
    democratic, republican, two_party_votes: total,
    margin_votes: democratic - republican,
    democratic_share_pct: total ? 100 * democratic / total : null,
    margin_pp: total ? 100 * (democratic - republican) / total : null,
  };
}

export function componentFor(from, to) {
  assert.ok(states.includes(from) && states.includes(to), 'Unknown outcome state');
  if (from === 'X' || to === 'X') return 'eligibility_residence';
  if (from !== to && ['D', 'R'].includes(from) && ['D', 'R'].includes(to)) return 'switching';
  if (['D', 'R'].includes(from) && to === 'N') return 'dropoff';
  if (from === 'N' && ['D', 'R'].includes(to)) return 'returning';
  return 'other_and_contest';
}

export function transitionAccounting(flows) {
  const before = Object.fromEntries(states.map(state => [state, 0]));
  const after = { ...before };
  const contribution = Object.fromEntries(components.map(key => [key, 0]));
  const seen = new Set();
  for (const { from, to, voters } of flows) {
    const key = `${from}:${to}`;
    assert.ok(!seen.has(key), 'Duplicate transition');
    seen.add(key);
    const component = componentFor(from, to);
    count(voters);
    before[from] = count(before[from] + voters);
    after[to] = count(after[to] + voters);
    contribution[component] += (margin[to] - margin[from]) * voters;
  }
  vector(before); vector(after);
  const start = twoPartyResult(before.D, before.R);
  const end = twoPartyResult(after.D, after.R);
  const change = end.margin_votes - start.margin_votes;
  assert.equal(Object.values(contribution).reduce((sum, value) => sum + value, 0), change);
  const share = Object.fromEntries(components.map(key => [
    key, Math.abs(change) >= 1 ? 100 * contribution[key] / change : null,
  ]));
  let normalized = null;
  if (start.two_party_votes && end.two_party_votes) {
    const scale = 50 * (1 / start.two_party_votes + 1 / end.two_party_votes);
    normalized = Object.fromEntries(components.map(key => [key, scale * contribution[key]]));
    normalized.denominator_scaling = 50 * (start.margin_votes + end.margin_votes)
      * (1 / end.two_party_votes - 1 / start.two_party_votes);
    assert.ok(Math.abs(Object.values(normalized).reduce((sum, value) => sum + value, 0)
      - (end.margin_pp - start.margin_pp)) < 1e-8, 'Normalization does not reconcile');
  }
  return {
    before, after, margin_vote_change: change,
    margin_pp_change: start.margin_pp === null || end.margin_pp === null ? null : end.margin_pp - start.margin_pp,
    margin_vote_contributions: contribution, signed_share_of_margin_vote_change_pct: share,
    margin_pp_contributions: normalized,
    gross_major_party_switchers: flows.filter(row => row.from !== row.to
      && ['D', 'R'].includes(row.from) && ['D', 'R'].includes(row.to))
      .reduce((sum, row) => sum + row.voters, 0),
  };
}

function transportCost(rows, columns, weights, allowed) {
  const size = rows.length, source = size * 2, sink = source + 1;
  const graph = Array.from({ length: sink + 1 }, () => []);
  function edge(from, to, capacity, cost) {
    const forward = { to, capacity, cost, reverse: graph[to].length };
    const reverse = { to: from, capacity: 0, cost: -cost, reverse: graph[from].length };
    graph[from].push(forward); graph[to].push(reverse);
  }
  const total = rows.reduce((sum, value) => sum + value, 0);
  for (let i = 0; i < size; i++) {
    edge(source, i, rows[i], 0);
    edge(size + i, sink, columns[i], 0);
    for (let j = 0; j < size; j++) if (allowed[i][j]) edge(i, size + j, total, weights[i][j]);
  }
  let sent = 0, cost = 0;
  while (sent < total) {
    const distance = Array(graph.length).fill(Infinity), previous = Array(graph.length).fill(null);
    distance[source] = 0;
    for (let iteration = 0; iteration < graph.length - 1; iteration++) {
      let changed = false;
      for (let from = 0; from < graph.length; from++) {
        for (let index = 0; index < graph[from].length; index++) {
          const item = graph[from][index];
          if (item.capacity && distance[from] + item.cost < distance[item.to]) {
            distance[item.to] = distance[from] + item.cost;
            previous[item.to] = [from, index];
            changed = true;
          }
        }
      }
      if (!changed) break;
    }
    assert.ok(previous[sink], 'Infeasible transition margins or restrictions');
    let amount = total - sent;
    for (let to = sink; to !== source;) {
      const [from, index] = previous[to];
      amount = Math.min(amount, graph[from][index].capacity); to = from;
    }
    for (let to = sink; to !== source;) {
      const [from, index] = previous[to], item = graph[from][index];
      item.capacity -= amount; graph[to][item.reverse].capacity += amount; to = from;
    }
    sent += amount; cost += amount * distance[sink];
  }
  assert.ok(Number.isSafeInteger(cost), 'Transition objective exceeds safe integer precision');
  return cost;
}

export function transitionBounds({ before, after, common_population_verified, forbidden = [] }) {
  assert.equal(common_population_verified, true, 'A verified common population is required; registrations are not a panel');
  const rows = vector(before), columns = vector(after);
  assert.equal(rows.reduce((a, b) => a + b, 0), columns.reduce((a, b) => a + b, 0), 'Population totals disagree');
  for (const [from, to] of forbidden) componentFor(from, to);
  const blocked = new Set(forbidden.map(([from, to]) => `${from}:${to}`));
  const allowed = states.map(from => states.map(to => !blocked.has(`${from}:${to}`)));
  const result = {};
  for (const component of components) {
    const weights = states.map(from => states.map(to =>
      componentFor(from, to) === component ? margin[to] - margin[from] : 0));
    result[component] = {
      lower: transportCost(rows, columns, weights, allowed),
      upper: -transportCost(rows, columns, weights.map(row => row.map(value => -value)), allowed) || 0,
    };
  }
  return {
    units: 'net Democratic margin votes', evidence: 'conditional_identification_bounds',
    assumptions: ['Supplied marginals describe a verified common population.',
      'All transitions are allowed except the explicitly supplied forbidden cells.',
      'Component extrema are separate feasible histories; their extrema cannot be summed.'],
    components: result,
  };
}

export function geographicAccounting(before, after) {
  assert.ok(before.length > 0 && before.length === after.length, 'Comparable units required');
  const baseline = new Map(before.map(row => [row.id, twoPartyResult(row.democratic, row.republican)]));
  assert.equal(baseline.size, before.length, 'Duplicate geography');
  assert.equal(new Set(after.map(row => row.id)).size, after.length, 'Duplicate geography');
  const totalBefore = [...baseline.values()].reduce((sum, row) => sum + row.two_party_votes, 0);
  const totalAfter = after.reduce((sum, row) => sum + count(row.democratic) + count(row.republican), 0);
  count(totalBefore); count(totalAfter);
  assert.ok(totalBefore > 0 && totalAfter > 0, 'Nonzero parent electorate required');
  let within = 0, composition = 0;
  for (const row of after) {
    const start = baseline.get(row.id), end = twoPartyResult(row.democratic, row.republican);
    assert.ok(start && start.two_party_votes > 0 && end.two_party_votes > 0, 'Missing or empty comparable unit');
    const w0 = start.two_party_votes / totalBefore, w1 = end.two_party_votes / totalAfter;
    const s0 = start.democratic / start.two_party_votes, s1 = end.democratic / end.two_party_votes;
    within += 100 * (w0 + w1) * (s1 - s0);
    composition += 100 * (s0 + s1) * (w1 - w0);
  }
  return { within_unit_margin_pp: within, geographic_weight_margin_pp: composition,
    swing_margin_pp: within + composition,
    interpretation: 'Geographic accounting, not individual persuasion or partisan drop-off.' };
}

export function qualifyCohort(evidence, { demographic = false } = {}) {
  const required = ['membership_verified', 'same_people', 'methods_matched', 'geography_matched',
    'cutoff_matched', 'valid_vote_universe_matched', 'prior_turnout_verified', 'prior_preference_validated'];
  if (demographic) required.push('demographic_choice_validated');
  const missing = required.filter(key => evidence[key] !== true);
  return { qualified: missing.length === 0, missing_evidence: missing,
    status: missing.length ? 'withheld' : 'model_estimated' };
}

export function cohortShift(evidence, baseline, outcome, options) {
  const qualification = qualifyCohort(evidence, options);
  if (!qualification.qualified) return { ...qualification, shift_margin_pp: null, shift_share_pp: null };
  for (const value of [baseline, outcome]) {
    assert.ok(Number.isFinite(value) && value >= -100 && value <= 100, 'Expected a two-party margin in percentage points');
  }
  return { ...qualification, shift_margin_pp: outcome - baseline, shift_share_pp: (outcome - baseline) / 2,
    interpretation: 'Fixed-cohort performance versus modeled prior preference; not gross switching or causal persuasion.' };
}

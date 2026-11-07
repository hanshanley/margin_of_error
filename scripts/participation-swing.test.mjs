import test from 'node:test';
import assert from 'node:assert/strict';
import {
  twoPartyResult, transitionAccounting, transitionBounds, geographicAccounting, cohortShift,
} from './participation-swing.mjs';

const population = values => ({ D: 0, R: 0, O: 0, B: 0, N: 0, X: 0, ...values });
const evidence = {
  membership_verified: true, same_people: true, methods_matched: true, geography_matched: true,
  cutoff_matched: true, valid_vote_universe_matched: true, prior_turnout_verified: true,
  prior_preference_validated: true, demographic_choice_validated: true,
};

test('switches contribute twice their count with the correct sign', () => {
  const result = transitionAccounting([{ from: 'R', to: 'D', voters: 8 }, { from: 'D', to: 'R', voters: 3 }]);
  assert.equal(result.margin_vote_contributions.switching, 10);
  assert.equal(result.gross_major_party_switchers, 11);
});

test('identical observed elections allow different switching and drop-off histories', () => {
  const first = transitionAccounting([
    { from: 'D', to: 'D', voters: 50 }, { from: 'R', to: 'R', voters: 40 }, { from: 'R', to: 'N', voters: 10 },
  ]);
  const second = transitionAccounting([
    { from: 'D', to: 'D', voters: 40 }, { from: 'D', to: 'N', voters: 10 },
    { from: 'R', to: 'R', voters: 40 }, { from: 'R', to: 'D', voters: 10 },
  ]);
  assert.deepEqual(first.before, second.before); assert.deepEqual(first.after, second.after);
  assert.equal(first.margin_vote_contributions.switching, 0);
  assert.equal(second.signed_share_of_margin_vote_change_pct.switching, 200);
  assert.equal(second.signed_share_of_margin_vote_change_pct.dropoff, -100);
  const bounds = transitionBounds({ before: first.before, after: first.after, common_population_verified: true });
  assert.deepEqual(bounds.components.switching, { lower: 0, upper: 20 });
  assert.deepEqual(bounds.components.dropoff, { lower: -10, upper: 10 });
});

test('participation, contest abstention, other choices, and eligibility remain separate', () => {
  const result = transitionAccounting([
    { from: 'D', to: 'N', voters: 3 }, { from: 'N', to: 'D', voters: 5 },
    { from: 'R', to: 'B', voters: 2 }, { from: 'O', to: 'D', voters: 4 },
    { from: 'X', to: 'R', voters: 6 },
  ]);
  assert.deepEqual(result.margin_vote_contributions,
    { switching: 0, dropoff: -3, returning: 5, other_and_contest: 6, eligibility_residence: -6 });
  assert.equal(result.margin_vote_change, 2);
});

test('normalization accounts for denominator changes and zero swing has no percentages', () => {
  const result = transitionAccounting([
    { from: 'D', to: 'D', voters: 20 }, { from: 'R', to: 'R', voters: 10 },
    { from: 'D', to: 'N', voters: 20 }, { from: 'R', to: 'N', voters: 10 },
  ]);
  assert.ok(Math.abs(result.margin_pp_change) < 1e-9);
  assert.ok(Math.abs(Object.values(result.margin_pp_contributions).reduce((a, b) => a + b)) < 1e-9);
  const zero = transitionAccounting([{ from: 'D', to: 'D', voters: 2 }]);
  assert.equal(zero.signed_share_of_margin_vote_change_pct.switching, null);
  assert.equal(twoPartyResult(0, 0).margin_pp, null);
});

test('rejects unknown counts, duplicate flows, and fabricated population universes', () => {
  assert.throws(() => twoPartyResult(null, 2));
  assert.throws(() => twoPartyResult(1.5, 2));
  assert.throws(() => transitionAccounting([{ from: 'D', to: 'R', voters: 2 }, { from: 'D', to: 'R', voters: 3 }]));
  assert.throws(() => transitionBounds({ before: population({ D: 3 }), after: population({ D: 3 }) }), /common population/);
  assert.throws(() => transitionBounds({
    before: population({ D: 3 }), after: population({ D: 2 }), common_population_verified: true,
  }), /totals disagree/);
  assert.throws(() => transitionBounds({
    before: population({ D: 3 }), after: population({ R: 3 }), common_population_verified: true, forbidden: [['D', 'R']],
  }), /Infeasible/);
});

test('bounds match exhaustive small-population histories, not just fitted totals', () => {
  for (let d0 = 0; d0 <= 3; d0++) for (let r0 = 0; r0 <= 3 - d0; r0++)
    for (let d1 = 0; d1 <= 3; d1++) for (let r1 = 0; r1 <= 3 - d1; r1++) {
      const before = population({ D: d0, R: r0, N: 3 - d0 - r0 });
      const after = population({ D: d1, R: r1, N: 3 - d1 - r1 });
      const all = [];
      function enumerate(index, remaining, flows) {
        if (index === 3) {
          if (remaining.every(value => value === 0)) all.push(transitionAccounting(flows).margin_vote_contributions);
          return;
        }
        const from = ['D', 'R', 'N'][index], n = before[from];
        for (let a = 0; a <= Math.min(n, remaining[0]); a++)
          for (let b = 0; b <= Math.min(n - a, remaining[1]); b++) {
            const c = n - a - b;
            if (c <= remaining[2]) enumerate(index + 1, [remaining[0] - a, remaining[1] - b, remaining[2] - c],
              [...flows, ...['D', 'R', 'N'].map((to, i) => ({ from, to, voters: [a, b, c][i] }))]);
          }
      }
      enumerate(0, [after.D, after.R, after.N], []);
      const actual = transitionBounds({ before, after, common_population_verified: true }).components;
      for (const key of ['switching', 'dropoff', 'returning']) {
        assert.equal(actual[key].lower, Math.min(...all.map(row => row[key])));
        assert.equal(actual[key].upper, Math.max(...all.map(row => row[key])));
      }
    }
});

test('geographic composition change with fixed local preference is not persuasion', () => {
  const result = geographicAccounting([
    { id: 'a', democratic: 80, republican: 20 }, { id: 'b', democratic: 20, republican: 80 },
  ], [{ id: 'a', democratic: 40, republican: 10 }, { id: 'b', democratic: 20, republican: 80 }]);
  assert.equal(result.within_unit_margin_pp, 0);
  assert.ok(Math.abs(result.geographic_weight_margin_pp + 20) < 1e-9);
  assert.throws(() => geographicAccounting([{ id: 'a', democratic: 2, republican: 1 }],
    [{ id: 'b', democratic: 2, republican: 1 }]), /Missing/);
});

test('fixed-cohort illustration is an 18-point margin shift, not 18% switchers', () => {
  const result = cohortShift(evidence, -6, 12, { demographic: true });
  assert.equal(result.shift_margin_pp, 18);
  assert.equal(result.shift_share_pp, 9);
});

test('missing evidence, different cohorts, method shifts, and demographic choice gaps withhold estimates', () => {
  for (const key of Object.keys(evidence)) {
    const result = cohortShift({ ...evidence, [key]: false }, -6, 12, { demographic: true });
    assert.equal(result.shift_margin_pp, null);
    assert.deepEqual(result.missing_evidence, [key]);
  }
  assert.equal(cohortShift({ ...evidence, demographic_choice_validated: false }, -6, 12).shift_margin_pp, 18);
  assert.throws(() => cohortShift(evidence, NaN, 12));
});

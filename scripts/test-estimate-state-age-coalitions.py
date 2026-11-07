import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "state_scenarios", Path(__file__).with_name("estimate-state-age-coalitions.py"))
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)


def inputs():
    historical = {
        "state_code": "NC", "prior_choice": "R", "native_current_survey_subset": 53,
        "minimum_age": 18, "maximum_age": 29,
        "certain_age_support": {"fraction_within_reported_2024_coalition": .2},
        "possible_age_support_including_unknown_birth_year": {"fraction_within_reported_2024_coalition": .3},
    }
    current = {
        "state_code": "NC", "contest_code": "SG", "subset": {"sub": 53, "longName": "18-29"},
        "population_scope": "state", "status": "conditional_matched_demographic_count",
        "population_match": {"status": "matched_published_population", "group_share_pct_of_current_electorate": 50},
        "joint_source_url": "selected-state-source", "joint_source_sha256": "frozen-hash",
        "joint_source_timestamp": "frozen-revision", "estimated_electorate_total": 100,
        "estimated_current_group_count": 50,
        "composition": {
            "R": {"share_pct_of_current_group": 60, "estimated_current_group_count": 30,
                  "reported_current_choice_counts": {"D": 3}},
            "D": {"share_pct_of_current_group": 30, "estimated_current_group_count": 15,
                  "reported_current_choice_counts": {"R": 3}},
            "O": {"share_pct_of_current_group": 5}, "N": {"share_pct_of_current_group": 5},
        },
    }
    joint = {
        "status": "published_joint_question_reviewed", "state_code": "NC", "contest_code": "SG",
        "subset": copy.deepcopy(current["subset"]), "source_url": current["joint_source_url"],
        "source_sha256": current["joint_source_sha256"], "source_timestamp": current["joint_source_timestamp"],
        "joint_question_rows": {
            key: {"prior_choice_share_pct": row["share_pct_of_current_group"],
                  "current_choice_pct_within_prior_choice": {"D": 10, "R": 20}}
            for key, row in current["composition"].items()
        },
    }
    return historical, current, joint


class StateScenarioTests(unittest.TestCase):
    def test_exact_state_reference_sensitivity_and_negative_diagnostics(self):
        result = state.calculate(*inputs(), 100)
        self.assertEqual(result["birth_year_only_hypothetical_original_cohort"], {"lower": 20, "upper": 30})
        self.assertEqual(result["birth_year_only_apparent_absence"], {"lower": -10, "upper": 0})
        self.assertEqual(result["birth_year_only_original_coalition_scaled_switching_pct"],
                         {"lower": 10, "upper": 15})
        self.assertEqual(len(result["sensitivity_scenarios"]), 486)
        for scenario in result["sensitivity_scenarios"]:
            self.assertAlmostEqual(scenario["hypothetical_original_cohort_count"]
                                   - scenario["current_reported_prior_count"], scenario["apparent_absence_count"])
            self.assertAlmostEqual(scenario["reported_opposite_choice_count"],
                                   scenario["current_reported_prior_count"] * .1)
        self.assertTrue(result["negative_birth_year_residual_endpoint"])
        self.assertIsNone(result["measured_staying_home_count"])
        self.assertIsNone(result["design_confidence_interval"])

    def test_no_national_dc_different_state_or_wrong_office_substitution(self):
        for target, key, value in (
            (0, "state_code", "US"), (0, "state_code", "DC"), (1, "state_code", "VA"),
            (1, "contest_code", "HG"), (1, "contest_code", "SP"), (1, "population_scope", "50_states_excluding_DC"),
            (0, "maximum_age", 44), (1, "status", "withheld"),
        ):
            data = list(inputs())
            data[target][key] = value
            with self.assertRaises(ValueError):
                state.calculate(*data, 100)

    def test_source_revision_population_counts_and_joint_cells_must_match(self):
        for key in ("source_sha256", "source_timestamp", "contest_code"):
            historical, current, joint = inputs()
            joint[key] = "changed"
            with self.assertRaises(ValueError):
                state.calculate(historical, current, joint, 100)
        historical, current, joint = inputs()
        current["estimated_current_group_count"] += 1
        with self.assertRaises(ValueError):
            state.calculate(historical, current, joint, 100)
        current["estimated_current_group_count"] -= 1
        joint["joint_question_rows"]["R"]["current_choice_pct_within_prior_choice"]["D"] = 20
        with self.assertRaises(ValueError):
            state.calculate(historical, current, joint, 100)

    def test_suppression_is_not_reconstructed_and_rounded_zero_is_not_exact(self):
        historical, current, joint = inputs()
        current["composition"]["R"]["reported_current_choice_counts"]["D"] = None
        joint["joint_question_rows"]["R"]["current_choice_pct_within_prior_choice"]["D"] = None
        result = state.calculate(historical, current, joint, 100)
        self.assertIsNone(result["reported_opposite_choice_count"])
        self.assertIsNone(result["birth_year_only_original_coalition_scaled_switching_pct"])
        self.assertTrue(all(row["reported_opposite_choice_count"] is None
                            for row in result["sensitivity_scenarios"]))
        historical, current, joint = inputs()
        current["composition"]["R"].update(share_pct_of_current_group=0, estimated_current_group_count=0)
        current["composition"]["R"]["reported_current_choice_counts"]["D"] = 0
        current["composition"]["D"]["share_pct_of_current_group"] = 90
        joint["joint_question_rows"]["R"]["prior_choice_share_pct"] = 0
        joint["joint_question_rows"]["D"]["prior_choice_share_pct"] = 90
        result = state.calculate(historical, current, joint, 100)
        self.assertEqual(result["reported_opposite_choice_count"], 0)
        self.assertGreater(result["current_switcher_rounding_only_envelope"]["upper"], 0)

    def test_invalid_fractions_counts_and_unexplained_composition_fail(self):
        for value in (.4, float("nan"), True):
            historical, current, joint = inputs()
            historical["certain_age_support"]["fraction_within_reported_2024_coalition"] = value
            with self.assertRaises(ValueError):
                state.calculate(historical, current, joint, 100)
        historical, current, joint = inputs()
        current["composition"]["R"]["share_pct_of_current_group"] = 55
        joint["joint_question_rows"]["R"]["prior_choice_share_pct"] = 55
        with self.assertRaises(ValueError):
            state.calculate(historical, current, joint, 100)

    def test_original_zero_support_does_not_create_rate(self):
        historical, current, joint = inputs()
        historical["certain_age_support"]["fraction_within_reported_2024_coalition"] = 0
        result = state.calculate(historical, current, joint, 100)
        self.assertIsNone(result["birth_year_only_original_coalition_scaled_switching_pct"])

    def test_state_baselines_are_not_national_totals_and_coverage_stays_explicit(self):
        historical, current, joint = inputs()
        other = copy.deepcopy(historical)
        other["prior_choice"] = "D"
        support = {"status": "private_state_birth_year_support_not_qualified_population_estimates",
                   "historical_controls_checked": True, "cohorts": [historical, other]}
        baselines = {code: {"D": 500, "R": 500, "all_presidential_votes": 1000}
                     for code in state.model.age.historical.STATE_CODES.values()}
        baselines["NC"] = {"D": 100, "R": 200, "all_presidential_votes": 300}
        result = state.estimate(support, {"estimates": [current]}, baselines, {"tables": [joint]})
        self.assertEqual(len(result["jurisdiction_coverage"]), 51)
        self.assertEqual([row["official_state_prior_coalition"] for row in result["estimates"]], [100, 200])
        self.assertEqual(next(row for row in result["estimates"] if row["prior_choice"] == "R")
                         ["birth_year_only_hypothetical_original_cohort"], {"lower": 40, "upper": 60})
        for changed in (
            {**support, "cohorts": [historical, other, historical]},
            {**support, "cohorts": [historical]},
            {**support, "historical_controls_checked": False},
        ):
            with self.assertRaises(ValueError):
                state.estimate(changed, {"estimates": [current]}, baselines, {"tables": [joint]})
        for currents, joints in (([current, current], [joint]), ([current], []), ([current], [joint, joint])):
            with self.assertRaises(ValueError):
                state.estimate(support, {"estimates": currents}, baselines, {"tables": joints})


if __name__ == "__main__":
    unittest.main()

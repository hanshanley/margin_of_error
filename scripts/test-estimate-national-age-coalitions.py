import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "age_scenarios", Path(__file__).with_name("estimate-national-age-coalitions.py"))
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def inputs():
    historical = {
        "scope": "50_states_excluding_DC", "prior_choice": "R",
        "native_current_survey_subset": 53, "minimum_age": 18, "maximum_age": 29,
        "certain_age_support": {"fraction_within_reported_2024_coalition": .2},
        "possible_age_support_including_unknown_birth_year": {"fraction_within_reported_2024_coalition": .3},
    }
    current = {
        "state_code": "US", "contest_code": "HG", "subset": {"sub": 53, "longName": "18-29"},
        "population_scope": "50_states_excluding_DC", "status": "conditional_matched_demographic_count",
        "population_match": {"status": "matched_published_population", "group_share_pct_of_current_electorate": 50},
        "joint_source_url": "selected-source", "joint_source_sha256": "frozen-hash",
        "joint_source_timestamp": "frozen-revision",
        "estimated_electorate_total": 100,
        "composition": {
            "R": {"share_pct_of_current_group": 60, "estimated_current_group_count": 30,
                  "reported_current_choice_counts": {"D": 3}},
            "D": {"share_pct_of_current_group": 30},
            "O": {"share_pct_of_current_group": 5}, "N": {"share_pct_of_current_group": 5},
        },
    }
    joint = {
        "status": "published_joint_question_reviewed", "state_code": "US", "contest_code": "HG",
        "subset": current["subset"], "source_url": current["joint_source_url"],
        "source_sha256": current["joint_source_sha256"], "source_timestamp": current["joint_source_timestamp"],
        "joint_question_rows": {
            key: {"prior_choice_share_pct": row["share_pct_of_current_group"],
                  "current_choice_pct_within_prior_choice": {"D": 10}}
            for key, row in current["composition"].items()
        },
    }
    return historical, current, joint


class AgeScenarioTests(unittest.TestCase):
    def test_signed_residual_and_original_denominator_are_preserved(self):
        result = model.calculate(*inputs(), 100)
        self.assertEqual(result["birth_year_only_hypothetical_original_cohort"], {"lower": 20, "upper": 30})
        self.assertEqual(result["birth_year_only_apparent_absence"], {"lower": -10, "upper": 0})
        self.assertEqual(result["birth_year_only_original_coalition_scaled_switching_pct"],
                         {"lower": 10, "upper": 15})
        self.assertTrue(result["negative_birth_year_residual_endpoint"])
        self.assertIsNone(result["measured_staying_home_count"])
        self.assertIsNone(result["design_confidence_interval"])

    def test_birthday_and_sensitivity_ranges_are_separate(self):
        result = model.calculate(*inputs(), 100)
        self.assertEqual(len(result["sensitivity_scenarios"]), 486)
        self.assertLess(result["marginal_sensitivity_apparent_absence"]["lower"], -10)
        self.assertGreater(result["marginal_sensitivity_apparent_absence"]["upper"], 0)
        for scenario in result["sensitivity_scenarios"]:
            if scenario["status"] == "conditional_sensitivity_scenario":
                self.assertAlmostEqual(scenario["hypothetical_original_cohort_count"]
                                       - scenario["current_reported_prior_count"],
                                       scenario["apparent_absence_count"])

    def test_suppressed_choices_are_not_recovered(self):
        historical, current, joint = inputs()
        current["composition"]["R"]["reported_current_choice_counts"]["D"] = None
        joint["joint_question_rows"]["R"]["current_choice_pct_within_prior_choice"]["D"] = None
        result = model.calculate(historical, current, joint, 100)
        self.assertIsNone(result["reported_opposite_choice_count"])
        self.assertIsNone(result["birth_year_only_original_coalition_scaled_switching_pct"])
        self.assertTrue(all(row["reported_opposite_choice_count"] is None
                            for row in result["sensitivity_scenarios"]
                            if row["status"] == "conditional_sensitivity_scenario"))

    def test_scope_and_cohort_redefinition_fail_closed(self):
        for key, value in (("scope", "US51"), ("maximum_age", 44)):
            historical, current, joint = inputs()
            historical[key] = value
            with self.assertRaises(ValueError):
                model.calculate(historical, current, joint, 100)
        historical, current, joint = inputs()
        current["contest_code"] = "SG"
        with self.assertRaises(ValueError):
            model.calculate(historical, current, joint, 100)

    def test_stale_counts_and_nonfinite_or_inverted_support_are_rejected(self):
        historical, current, joint = inputs()
        current["composition"]["R"]["estimated_current_group_count"] += 1
        with self.assertRaises(ValueError):
            model.calculate(historical, current, joint, 100)
        for value in (.4, float("nan"), True):
            historical, current, joint = inputs()
            historical["certain_age_support"]["fraction_within_reported_2024_coalition"] = value
            with self.assertRaises(ValueError):
                model.calculate(historical, current, joint, 100)

    def test_zero_original_group_does_not_create_a_rate(self):
        historical, current, joint = inputs()
        historical["certain_age_support"]["fraction_within_reported_2024_coalition"] = 0
        result = model.calculate(historical, current, joint, 100)
        self.assertIsNone(result["birth_year_only_original_coalition_scaled_switching_pct"])
        self.assertTrue(result["negative_birth_year_residual_endpoint"])

    def test_dc_is_excluded_from_both_prior_coalitions(self):
        baselines = {state: {"D": 0, "R": 0, "all_presidential_votes": 0}
                     for state in model.age.historical.STATE_CODES.values()}
        baselines["NC"] = {"D": 10, "R": 20, "all_presidential_votes": 35}
        baselines["DC"] = {"D": 999, "R": 999, "all_presidential_votes": 1998}
        self.assertEqual(model.national_baselines(baselines), {"D": 10, "R": 20})
        del baselines["NC"]
        with self.assertRaises(ValueError):
            model.national_baselines(baselines)

    def test_explicit_native_percentage_survives_rounded_zero_prior_count(self):
        historical, current, joint = inputs()
        current["composition"]["R"].update(share_pct_of_current_group=0, estimated_current_group_count=0)
        current["composition"]["R"]["reported_current_choice_counts"]["D"] = 0
        current["composition"]["D"]["share_pct_of_current_group"] = 90
        joint["joint_question_rows"]["R"]["prior_choice_share_pct"] = 0
        joint["joint_question_rows"]["D"]["prior_choice_share_pct"] = 90
        result = model.calculate(historical, current, joint, 100)
        self.assertEqual(result["reported_opposite_choice_count"], 0)
        self.assertGreater(result["current_switcher_rounding_only_envelope"]["upper"], 0)
        valid = [row for row in result["sensitivity_scenarios"]
                 if row["status"] == "conditional_sensitivity_scenario"]
        self.assertTrue(any(row["reported_opposite_choice_count"] > 0 for row in valid))
        self.assertTrue(any(row["status"] == "withheld_invalid_recall_or_rounding_scenario"
                            for row in result["sensitivity_scenarios"]))

    def test_changed_native_choice_or_revision_is_rejected(self):
        for key in ("source_timestamp", "source_sha256"):
            historical, current, joint = inputs()
            joint[key] = "changed"
            with self.assertRaises(ValueError):
                model.calculate(historical, current, joint, 100)
        historical, current, joint = inputs()
        joint["joint_question_rows"]["R"]["current_choice_pct_within_prior_choice"]["D"] = 20
        with self.assertRaises(ValueError):
            model.calculate(historical, current, joint, 100)


if __name__ == "__main__":
    unittest.main()

import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "race_matching", Path(__file__).with_name("review-national-race-matching.py"))
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def inputs():
    historical = {"group": "Hispanic", "respondents": 10, "sum_weight": 20,
                  "sum_squared_weight": 40, "fraction_within_reported_2024_coalition": .2}
    current = {
        "state_code": "US", "contest_code": "HG", "subset": {"sub": 7, "longName": "Latino Voters"},
        "population_scope": "50_states_excluding_DC", "status": "conditional_matched_demographic_count",
        "population_match": {"status": "matched_published_population", "question_id": 260,
                             "answer": "Latino", "group_share_pct_of_current_electorate": 50},
        "joint_source_url": "selected-source", "joint_source_sha256": "frozen-hash",
        "joint_source_timestamp": "frozen-revision", "estimated_electorate_total": 100,
        "composition": {
            "R": {"share_pct_of_current_group": 60, "estimated_current_group_count": 30,
                  "reported_current_choice_counts": {"D": 3}},
            "D": {"share_pct_of_current_group": 30},
            "O": {"share_pct_of_current_group": 5}, "N": {"share_pct_of_current_group": 5},
        },
    }
    joint = {
        "status": "published_joint_question_reviewed", "state_code": "US", "contest_code": "HG",
        "subset": copy.deepcopy(current["subset"]), "source_url": current["joint_source_url"],
        "source_sha256": current["joint_source_sha256"], "source_timestamp": current["joint_source_timestamp"],
        "joint_question_rows": {
            p: {"prior_choice_share_pct": row["share_pct_of_current_group"],
                "current_choice_pct_within_prior_choice": {"D": 10}}
            for p, row in current["composition"].items()
        },
    }
    return historical, current, joint


def calculate(historical, current, joint):
    return model.calculate(historical, current, joint, "R", 100, "source_race_2024", "Hispanic")


class RaceMatchingTests(unittest.TestCase):
    def test_signed_residual_is_not_nonvoting_or_qualification(self):
        result = calculate(*inputs())
        self.assertEqual(result["hypothetical_original_group_if_labels_matched"], 20)
        self.assertEqual(result["apparent_absence_if_labels_matched"], -10)
        self.assertEqual(result["original_group_scaled_opposite_choice_pct_if_labels_matched"], 15)
        self.assertTrue(result["negative_residual_diagnostic"])
        self.assertFalse(result["cross_source_matching_qualified"])
        self.assertFalse(result["public_release_qualified"])
        for key in ("measured_staying_home_count", "demographic_turnout_rate", "design_confidence_interval"):
            self.assertIsNone(result[key])

    def test_distinct_historical_definitions_remain_distinct(self):
        historical, current, joint = inputs()
        source = calculate(historical, current, joint)
        historical["fraction_within_reported_2024_coalition"] = .3
        combined = model.calculate(historical, current, joint, "R", 100, "race_ethnicity_2024", "Hispanic")
        self.assertEqual(source["historical_dimension"], "source_race_2024")
        self.assertEqual(combined["historical_dimension"], "race_ethnicity_2024")
        self.assertEqual(combined["apparent_absence_if_labels_matched"], 0)
        self.assertEqual(combined["reported_opposite_choice_count"], source["reported_opposite_choice_count"])

    def test_wrong_geography_contest_native_label_and_revision_fail(self):
        for key, value in (("population_scope", "US51"), ("contest_code", "SG"), ("state_code", "CA")):
            historical, current, joint = inputs()
            current[key] = value
            with self.assertRaises(ValueError):
                calculate(historical, current, joint)
        historical, current, joint = inputs()
        current["population_match"]["answer"] = "Hispanic"
        with self.assertRaises(ValueError):
            calculate(historical, current, joint)
        for key in ("source_sha256", "source_timestamp"):
            historical, current, joint = inputs()
            joint[key] = "changed"
            with self.assertRaises(ValueError):
                calculate(historical, current, joint)

    def test_changed_native_prior_choice_flow_and_nonfinite_counts_fail(self):
        historical, current, joint = inputs()
        joint["joint_question_rows"]["R"]["prior_choice_share_pct"] = 61
        with self.assertRaises(ValueError):
            calculate(historical, current, joint)
        historical, current, joint = inputs()
        joint["joint_question_rows"]["R"]["current_choice_pct_within_prior_choice"]["D"] = 20
        with self.assertRaises(ValueError):
            calculate(historical, current, joint)
        for value in (31, float("nan"), True):
            historical, current, joint = inputs()
            current["composition"]["R"]["estimated_current_group_count"] = value
            with self.assertRaises(ValueError):
                calculate(historical, current, joint)

    def test_suppression_and_explicit_choice_with_rounded_zero_are_preserved(self):
        historical, current, joint = inputs()
        current["composition"]["R"]["reported_current_choice_counts"]["D"] = None
        joint["joint_question_rows"]["R"]["current_choice_pct_within_prior_choice"]["D"] = None
        self.assertIsNone(calculate(historical, current, joint)["reported_opposite_choice_count"])
        historical, current, joint = inputs()
        current["composition"]["R"].update(share_pct_of_current_group=0, estimated_current_group_count=0)
        current["composition"]["R"]["reported_current_choice_counts"]["D"] = 0
        current["composition"]["D"]["share_pct_of_current_group"] = 90
        joint["joint_question_rows"]["R"]["prior_choice_share_pct"] = 0
        joint["joint_question_rows"]["D"]["prior_choice_share_pct"] = 90
        result = calculate(historical, current, joint)
        self.assertEqual(result["reported_opposite_choice_count"], 0)
        self.assertEqual(result["native_opposite_choice_pct_within_current_prior"], 10)

    def test_unknowns_stay_in_full_historical_denominator(self):
        historical, _, _ = inputs()
        other = {"group": "Unknown race", "respondents": 40, "sum_weight": 80,
                 "sum_squared_weight": 160, "fraction_within_reported_2024_coalition": .8}
        coalition = {"respondents": 50, "sum_weight": 100, "sum_squared_weight": 200,
                     "partitions": {"source_race_2024": [historical, other]}}
        self.assertEqual(model.historical_groups(coalition, "source_race_2024")["Hispanic"]
                         ["fraction_within_reported_2024_coalition"], .2)
        coalition["partitions"]["source_race_2024"] = [historical]
        with self.assertRaises(ValueError):
            model.historical_groups(coalition, "source_race_2024")

    def test_duplicate_groups_and_inconsistent_sufficient_statistics_fail(self):
        historical, _, _ = inputs()
        coalition = {"respondents": 20, "sum_weight": 40, "sum_squared_weight": 80,
                     "partitions": {"source_race_2024": [historical, copy.deepcopy(historical)]}}
        with self.assertRaises(ValueError):
            model.historical_groups(coalition, "source_race_2024")
        historical["fraction_within_reported_2024_coalition"] = .5
        historical["sum_weight"] = float("nan")
        coalition["partitions"]["source_race_2024"] = [historical]
        with self.assertRaises(ValueError):
            model.historical_groups(coalition, "source_race_2024")


if __name__ == "__main__":
    unittest.main()

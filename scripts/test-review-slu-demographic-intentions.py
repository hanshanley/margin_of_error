import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "demographic", Path(__file__).with_name("review-slu-demographic-intentions.py"))
demographic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demographic)


def row(prior="2", house="1", weight="1", **fields):
    return {
        "presvote24post": prior, "POLS025": house, "weight": weight,
        "QB": "1", "votereg": "1", "gender": "1", "agegroup": "1",
        "race": "1", "educ": "2", "incgroup": "1", "USR_Classification": "3",
        "employ": "1", "marstat": "1", "child18": "2", **fields,
    }


def group(result, field, code):
    dimension = next(item for item in result["dimensions"] if item["native_variable"] == field)
    return next(item for item in dimension["groups"] if item["native_code"] == code)


def prior(group_result, code):
    return next(item for item in group_result["comparisons"] if item["native_prior_code"] == code)


class DemographicIntentionsTests(unittest.TestCase):
    def test_actual_joint_weighting_retains_other_and_unsure(self):
        result = demographic.review([
            row(weight="2"), row(house="2"), row(house="3"), row(house="4", QB="2"),
            row(house="2", weight="9", gender="2")])
        male = prior(group(result, "gender", "1"), "2")
        self.assertEqual(male["support"]["respondents"], 4)
        self.assertAlmostEqual(male["support"]["kish_effective_base_not_design_n"], 25 / 7)
        self.assertEqual([item["weighted_within_prior_share"]
                          for item in male["intended_house_choices"]], [.4, .2, .2, .2])
        self.assertAlmostEqual(male["turnout_intentions"][1]["weighted_within_prior_share"], .2)
        self.assertEqual(prior(group(result, "gender", "2"), "2")
                         ["intended_house_choices"][0]["weighted_within_prior_share"], 0)

    def test_partitions_retain_nonmajor_priors_and_original_overall_review(self):
        rows = [row(prior="1", weight="2"), row(prior="2", gender="2"),
                row(prior="6", house="3"), row(prior="9", house="4", incgroup="-1")]
        result = demographic.review(rows)
        self.assertEqual(result["overall_review"], demographic.slu.review(rows))
        for dimension in result["dimensions"]:
            self.assertTrue(dimension["all_partition_support_controls_reconciled"])
            self.assertEqual(sum(item["support"]["respondents"] for item in dimension["groups"]), 4)
        male = group(result, "gender", "1")
        self.assertEqual(prior(male, "6")["reported_2024_choice"], "Oliver")
        self.assertEqual(prior(male, "9")["support"]["respondents"], 1)

    def test_native_missing_income_category_is_not_dropped_or_zero_imputed(self):
        result = demographic.review([row(incgroup="-1", weight="3"), row(weight="2")])
        missing = group(result, "incgroup", "-1")
        self.assertEqual(missing["native_label"], "No Data")
        self.assertEqual(missing["support"]["sum_weight"], 3)
        self.assertEqual(prior(missing, "2")["intended_house_choices"][0]
                         ["weighted_within_prior_share"], 1)

    def test_zero_joint_denominator_is_unavailable_not_zero(self):
        result = demographic.review([row(prior="1")])
        trump = prior(group(result, "gender", "1"), "2")
        self.assertEqual(trump["support"]["respondents"], 0)
        self.assertTrue(all(item["weighted_within_prior_share"] is None
                            for item in trump["intended_house_choices"]))
        self.assertTrue(all(item["weighted_within_prior_share"] is None
                            for item in trump["turnout_intentions"]))

    def test_missing_and_unrecognized_demographics_fail_closed(self):
        for field in demographic.DIMENSIONS:
            missing = row()
            del missing[field]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Missing"):
                demographic.review([missing])
            for value in ("", "99", None):
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "Unknown"):
                    demographic.review([row(**{field: value})])

    def test_partition_controls_detect_lost_counts_weights_and_squared_weights(self):
        support = demographic.slu.support([2, 1])
        for field in ("respondents", "sum_weight", "sum_squared_weight"):
            altered = copy.deepcopy(support)
            altered[field] += 1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "control"):
                demographic.check_support([altered], support)

    def test_changed_native_demographic_marginals_fail_qualification(self):
        with self.assertRaisesRegex(ValueError, "demographic marginals"):
            demographic.qualify_native(demographic.review([row()]))

    def test_population_completed_turnout_and_public_release_are_not_inferred(self):
        result = demographic.review([row()])
        self.assertFalse(result["public_release_qualified"])
        for name in ("population_switchers", "apparent_absence", "measured_staying_home",
                     "new_or_returning_voter_identity", "demographic_turnout",
                     "total_swing_shares", "design_confidence_intervals", "district_or_county_estimates"):
            self.assertIsNone(result[name])
        for dimension in result["dimensions"]:
            self.assertIsNone(dimension["demographic_measurement_date"])
            self.assertFalse(dimension["category_operationalization_independently_verified"])


if __name__ == "__main__":
    unittest.main()

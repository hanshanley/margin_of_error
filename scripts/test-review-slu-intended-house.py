import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "slu", Path(__file__).with_name("review-slu-intended-house.py"))
slu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slu)


def row(prior="2", house="1", weight="1", likelihood="1"):
    return {"presvote24post": prior, "POLS025": house, "weight": weight,
            "QB": likelihood, "votereg": "1"}


class IntendedHouseTests(unittest.TestCase):
    def test_joint_weighting_keeps_undecided_and_other_denominators(self):
        result = slu.review([row(weight="2"), row(house="2"),
                             row(house="3"), row(house="4", likelihood="2"),
                             row(prior="1", house="2", weight="3")])
        trump = next(item for item in result["comparisons"] if item["reported_2024_choice"] == "Trump")
        choices = {item["party_or_response"]: item for item in trump["intended_house_choices"]}
        self.assertAlmostEqual(choices["D"]["weighted_within_prior_share"], 2 / 5)
        self.assertAlmostEqual(choices["R"]["weighted_within_prior_share"], 1 / 5)
        self.assertEqual(trump["support"]["respondents"], 4)
        self.assertAlmostEqual(trump["support"]["kish_effective_base_not_design_n"], 25 / 7)
        self.assertAlmostEqual(sum(item["weighted_within_prior_share"] for item in choices.values()), 1)
        self.assertAlmostEqual(trump["turnout_intentions"][1]["weighted_within_prior_share"], 1 / 5)

    def test_native_presidential_nonvote_is_nine_not_six(self):
        result = slu.review([row(prior="9"), row(prior="6", house="2")])
        present = {item["reported_2024_choice"] for item in result["comparisons"]
                   if item["support"]["respondents"]}
        self.assertEqual(present, {"Presidential nonvote", "Oliver"})
        for item in result["comparisons"]:
            if not item["support"]["respondents"]:
                self.assertIsNone(item["intended_house_choices"][0]["weighted_within_prior_share"])

    def test_no_completed_turnout_population_or_design_inference(self):
        result = slu.review([row()])
        for name in ("population_switchers", "apparent_absence", "measured_staying_home",
                     "new_or_returning_voter_identity", "demographic_turnout",
                     "total_swing_shares", "design_confidence_intervals", "district_or_county_estimates"):
            self.assertIsNone(result[name])
        self.assertIn("pre_election_intentions", result["status"])

    def test_changed_universe_missing_or_invalid_codes_fail_closed(self):
        for field, value in [("presvote24post", "7"), ("presvote24post", ""),
                             ("POLS025", "8"), ("QB", "3"), ("votereg", "2")]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                slu.review([{**row(), field: value}])
        missing = row()
        del missing["weight"]
        with self.assertRaisesRegex(ValueError, "columns"):
            slu.review([missing])
        with self.assertRaisesRegex(ValueError, "Empty"):
            slu.review([])

    def test_invalid_or_nonfinite_weights_fail_closed(self):
        for weight in ("0", "-1", "nan", "inf", "1e308", "bad", None):
            with self.subTest(weight=weight), self.assertRaisesRegex(ValueError, "weight"):
                slu.review([row(weight=weight)])

    def test_native_qualification_requires_both_marginals_and_weighted_topline(self):
        result = slu.review([row()])
        with self.assertRaisesRegex(ValueError, "marginals"):
            slu.qualify_native(result)
        result["native_variable_counts"] = copy.deepcopy(slu.NATIVE_COUNTS)
        with self.assertRaisesRegex(ValueError, "topline"):
            slu.qualify_native(result)
        result["intended_house_topline"] = [
            {"party_or_response": label, "weighted_sample_share": fraction}
            for label, fraction in (("D", .44), ("R", .48), ("Other", .02), ("Not sure", .06))]
        self.assertTrue(slu.qualify_native(result)["native_marginals_and_rounded_topline_checked"])


if __name__ == "__main__":
    unittest.main()

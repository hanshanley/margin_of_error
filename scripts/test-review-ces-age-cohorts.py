import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "ces_age", Path(__file__).with_name("review-ces-age-cohorts.py"))
age = importlib.util.module_from_spec(spec)
spec.loader.exec_module(age)


def row(birth="1997", weight="1", **changes):
    return {"birthyr": birth, "vvweight_post": weight, "TS_g2024": "1", "CC24_410": "1",
            "inputstate": "37", "TS_state": "NC", **changes}


class AgeCohortTests(unittest.TestCase):
    def test_young_boundary_is_not_aged_2024_group(self):
        self.assertEqual(age.memberships(row("1996"))["53"], "birthday_boundary")
        self.assertEqual(age.memberships(row("1997"))["53"], "certain")
        self.assertEqual(age.memberships(row("1995"))["53"], "outside")

    def test_middle_and_older_boundary_directions(self):
        self.assertEqual(age.memberships(row("1981"))["54"], "birthday_boundary")
        self.assertEqual(age.memberships(row("1982"))["54"], "certain")
        self.assertEqual(age.memberships(row("1961"))["55"], "birthday_boundary")
        self.assertEqual(age.memberships(row("1960"))["55"], "certain")
        self.assertEqual(age.memberships(row("1962"))["55"], "outside")

    def test_unknown_births_expand_possible_not_certain(self):
        result = age.review([row(), row("NA", weight="2"), row("1980")])
        cohort = next(item for item in result["cohorts"] if item["native_current_survey_subset"] == 53)
        self.assertEqual(cohort["certain_age_support"]["fraction_within_reported_2024_coalition"], .25)
        self.assertEqual(cohort["possible_age_support_including_unknown_birth_year"]
                         ["fraction_within_reported_2024_coalition"], .75)
        self.assertEqual(cohort["unknown_birth_year_respondents"], 1)

    def test_unknown_and_incompatible_birth_years_remain_unknown(self):
        for birth in ("", "NA", "1997.0", "2007", "1903"):
            self.assertEqual(set(age.memberships(row(birth)).values()), {"unknown"})

    def test_dc_and_ineligible_source_rows_do_not_enter_coalition(self):
        result = age.review([row(), row(weight="100", inputstate="11", TS_state="DC"),
                             row(weight="100", TS_g2024="7"), row(weight="100", TS_state="VA")])
        self.assertTrue(all(item["coalition"]["respondents"] == 1 for item in result["cohorts"]))
        self.assertEqual(result["source_audit"]["retained_respondents"], 2)

    def test_empty_certain_support_stays_zero_not_false_effective_sample(self):
        result = age.review([row("1960")])
        cohort = next(item for item in result["cohorts"] if item["native_current_survey_subset"] == 53)
        self.assertIsNone(cohort["certain_age_support"]["effective_sample_size"])
        self.assertEqual(cohort["certain_age_support"]["fraction_within_reported_2024_coalition"], 0)
        self.assertIsNone(result["group_dropoff_estimates"])
        self.assertIsNone(result["design_confidence_intervals"])

    def test_historical_control_mismatch_fails_closed(self):
        data = [row()]
        control = age.historical.review(data, demographics_fn=age.memberships)
        self.assertTrue(age.review(data, control)["historical_controls_checked"])
        next(item for item in control["coalitions"] if item["scope"] == "US50")["sum_weight"] += 1
        with self.assertRaisesRegex(ValueError, "controls differ"):
            age.review(data, control)
        control["source_audit"]["retained_respondents"] += 1
        with self.assertRaisesRegex(ValueError, "dispositions differ"):
            age.review(data, control)

    def test_both_prior_coalitions_keep_different_weighted_ranges(self):
        result = age.review([row(), row("1996", weight="3"), row("1980", CC24_410="2")])
        cohorts = [item for item in result["cohorts"] if item["native_current_survey_subset"] == 53]
        self.assertEqual(len(cohorts), 2)
        dem = next(item for item in cohorts if item["prior_choice"] == "D")
        self.assertEqual(dem["certain_age_support"]["fraction_within_reported_2024_coalition"], .25)
        self.assertEqual(dem["possible_age_support_including_unknown_birth_year"]
                         ["fraction_within_reported_2024_coalition"], 1)
        rep = next(item for item in cohorts if item["prior_choice"] == "R")
        self.assertEqual(rep["possible_age_support_including_unknown_birth_year"]
                         ["fraction_within_reported_2024_coalition"], 0)


if __name__ == "__main__":
    unittest.main()

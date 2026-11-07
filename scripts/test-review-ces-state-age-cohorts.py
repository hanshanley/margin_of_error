import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "state_age", Path(__file__).with_name("review-ces-state-age-cohorts.py"))
state_age = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state_age)


def row(birth="1997", weight="1", **changes):
    return {"birthyr": birth, "vvweight_post": weight, "TS_g2024": "1", "CC24_410": "1",
            "inputstate": "37", "TS_state": "NC", **changes}


def control(rows):
    return state_age.age.historical.review(rows, demographics_fn=state_age.age.memberships)


def cohort(result, state="NC", prior="D", subset=53):
    return next(item for item in result["cohorts"] if (
        item["state_code"], item["prior_choice"], item["native_current_survey_subset"]
    ) == (state, prior, subset))


class StateAgeTests(unittest.TestCase):
    def test_state_support_is_not_the_national_fraction(self):
        data = [row(), row("1980", weight="3"), row(weight="9", inputstate="48", TS_state="TX")]
        result = state_age.review(data, control(data))
        nc, tx = cohort(result), cohort(result, state="TX")
        self.assertEqual(nc["certain_age_support"]["fraction_within_reported_2024_coalition"], .25)
        self.assertEqual(tx["certain_age_support"]["fraction_within_reported_2024_coalition"], 1)
        self.assertEqual({item["state_code"] for item in result["cohorts"]}, {"NC", "TX"})

    def test_dc_keeps_its_own_coalition_denominator(self):
        data = [row(), row("1980", weight="100", inputstate="11", TS_state="DC")]
        result = state_age.review(data, control(data))
        self.assertEqual(cohort(result)["coalition"]["sum_weight"], 1)
        self.assertEqual(cohort(result, state="DC")["coalition"]["sum_weight"], 100)
        self.assertEqual(cohort(result, state="DC")["certain_age_support"]
                         ["fraction_within_reported_2024_coalition"], 0)

    def test_state_controls_fail_even_when_national_totals_are_unchanged(self):
        data = [row(), row("1980", inputstate="48", TS_state="TX")]
        changed = control(data)
        for item in changed["coalitions"]:
            if item["scope"] in ("NC", "TX"):
                item["sum_weight"] += .25 if item["scope"] == "NC" else -.25
        with self.assertRaisesRegex(ValueError, "coalition controls differ"):
            state_age.review(data, changed)

    def test_missing_duplicate_and_wrong_prior_controls_fail(self):
        data = [row(), row(CC24_410="2")]
        original = control(data)
        for mutation in ("missing", "duplicate", "prior"):
            changed = copy.deepcopy(original)
            if mutation == "missing":
                changed["coalitions"].pop()
            elif mutation == "duplicate":
                changed["coalitions"].append(copy.deepcopy(changed["coalitions"][0]))
            else:
                changed["coalitions"][0]["prior_choice"] = "invalid"
            with self.assertRaisesRegex(ValueError, "coalition controls differ"):
                state_age.review(data, changed)

    def test_source_dispositions_and_state_matching_are_preserved(self):
        data = [row(), row(weight="50", TS_state="VA"), row(weight="50", TS_g2024="7")]
        original = control(data)
        result = state_age.review(data, original)
        self.assertEqual(cohort(result)["coalition"]["respondents"], 1)
        original["source_audit"]["retained_respondents"] += 1
        with self.assertRaisesRegex(ValueError, "dispositions differ"):
            state_age.review(data, original)

    def test_boundaries_unknowns_and_parties_use_separate_full_denominators(self):
        data = [row(), row("1996", weight="2"), row("NA", weight="3"),
                row("1960", weight="4", CC24_410="2")]
        result = state_age.review(data, control(data))
        dem = cohort(result)
        self.assertEqual(dem["certain_age_support"]["fraction_within_reported_2024_coalition"], 1 / 6)
        self.assertEqual(dem["possible_age_support_including_unknown_birth_year"]
                         ["fraction_within_reported_2024_coalition"], 1)
        self.assertEqual(dem["birthday_boundary_respondents"], 1)
        self.assertEqual(dem["unknown_birth_year_respondents"], 1)
        self.assertEqual(cohort(result, prior="R", subset=55)["certain_age_support"]
                         ["fraction_within_reported_2024_coalition"], 1)
        self.assertIsNone(cohort(result, prior="R")["certain_age_support"]["effective_sample_size"])
        self.assertIsNone(result["group_dropoff_estimates"])
        self.assertIsNone(result["design_confidence_intervals"])

    def test_other_choice_is_controlled_but_not_reassigned(self):
        data = [row(), row(weight="100", CC24_410="3")]
        original = control(data)
        result = state_age.review(data, original)
        self.assertEqual({item["prior_choice"] for item in result["cohorts"]}, {"D"})
        self.assertEqual(cohort(result)["coalition"]["sum_weight"], 1)
        next(item for item in original["coalitions"] if item["prior_choice"] == "O")["respondents"] += 1
        with self.assertRaisesRegex(ValueError, "coalition controls differ"):
            state_age.review(data, original)

    def test_no_major_party_support_fails_closed(self):
        data = [row(CC24_410="3")]
        with self.assertRaisesRegex(ValueError, "No state major-party"):
            state_age.review(data, control(data))


if __name__ == "__main__":
    unittest.main()

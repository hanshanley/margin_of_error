import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "baseline", Path(__file__).with_name("review-ces-demographic-baselines.py"))
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def respondent(**changes):
    return {
        "TS_g2024": "2", "CC24_410": "2", "vvweight_post": "1",
        "inputstate": "37", "TS_state": "NC", "gender4": "1",
        "race": "1", "hispanic": "2", "educ": "5", "birthyr": "1996",
    } | changes


class HistoricalDemographicBaselineTests(unittest.TestCase):
    def coalition(self, output, scope="NC", prior="R"):
        return next(r for r in output["coalitions"] if (r["scope"], r["prior_choice"]) == (scope, prior))

    def test_coalition_conditioning_and_full_unknown_denominator(self):
        output = baseline.review([
            respondent(vvweight_post="2"), respondent(gender4="9"),
            respondent(CC24_410="1", vvweight_post="10", gender4="2"),
        ])
        row = self.coalition(output)
        groups = {r["group"]: r for r in row["partitions"]["gender_2024"]}
        self.assertAlmostEqual(groups["Man"]["fraction_within_reported_2024_coalition"], 2 / 3)
        self.assertAlmostEqual(groups["Unknown gender"]["fraction_within_reported_2024_coalition"], 1 / 3)
        self.assertAlmostEqual(row["effective_sample_size"], 9 / 5)
        self.assertIsNone(output["original_group_population_estimates"])
        self.assertIsNone(output["group_dropoff_estimates"])

    def test_dc_is_not_in_fifty_state_national_scope(self):
        output = baseline.review([respondent(), respondent(inputstate="11", TS_state="DC", vvweight_post="3")])
        self.assertEqual(self.coalition(output, "US50")["sum_weight"], 1)
        self.assertEqual(self.coalition(output, "US51")["sum_weight"], 4)
        self.assertEqual(self.coalition(output, "DC")["sum_weight"], 3)

    def test_native_gender_and_education_do_not_collapse_other_categories(self):
        groups = baseline.demographics(respondent(gender4="3", educ="4"))
        self.assertEqual(groups["gender_2024"], "Non-binary")
        self.assertEqual(groups["education_2024"], "2-year")
        self.assertEqual(groups["race_education_2024"], "Non-Hispanic White; No college degree")
        self.assertEqual(baseline.demographics(respondent(educ="9"))["education_2024"], "Unknown education")

    def test_race_and_ethnicity_definitions_stay_distinct(self):
        groups = baseline.demographics(respondent(hispanic="1"))
        self.assertEqual(groups["source_race_2024"], "White")
        self.assertEqual(groups["race_ethnicity_2024"], "Hispanic")
        self.assertEqual(groups["race_education_2024"], "Not non-Hispanic White; College degree")
        self.assertEqual(baseline.demographics(respondent(hispanic="9"))["race_ethnicity_2024"], "Unknown ethnicity")
        self.assertEqual(baseline.demographics(respondent(race="6"))["race_ethnicity_2024"], "Non-Hispanic Two or more races")

    def test_age_groups_are_not_a_frozen_current_demographic_cohort(self):
        groups = baseline.demographics(respondent(birthyr="1995"))
        self.assertEqual(groups["age_2024_by_birth_year"], "18-29")
        self.assertEqual(groups["age_2026_by_birth_year_if_alive"], "30-44")
        self.assertEqual(baseline.demographics(respondent(birthyr="1961"))["age_2026_by_birth_year_if_alive"], "65+")

    def test_source_dispositions_and_invalid_weights(self):
        output = baseline.review([
            respondent(TS_g2024="7"), respondent(CC24_410="9"),
            respondent(vvweight_post="NA"), respondent(TS_state="SC"), respondent(),
        ])
        self.assertEqual(output["source_audit"]["native_respondents"], 5)
        self.assertEqual(output["source_audit"]["retained_respondents"], 1)
        self.assertEqual(len(output["source_audit"]), 6)
        for weight in ("nan", "inf", "0", "-1"):
            with self.assertRaisesRegex(ValueError, "Invalid documented survey weight"):
                baseline.review([respondent(vvweight_post=weight)])
        with self.assertRaisesRegex(ValueError, "Unrecognized survey state"):
            baseline.review([respondent(inputstate="99")])

    def test_partition_weights_and_weighted_ratio_variance(self):
        output = baseline.review([respondent(), respondent(gender4="2")])
        row = self.coalition(output)
        for groups in row["partitions"].values():
            self.assertEqual(sum(r["respondents"] for r in groups), 2)
            self.assertEqual(sum(r["sum_weight"] for r in groups), 2)
            self.assertAlmostEqual(sum(r["fraction_within_reported_2024_coalition"] for r in groups), 1)
        group = row["partitions"]["gender_2024"][0]
        self.assertAlmostEqual(group["independent_row_ratio_standard_error_not_design"], (0.25 / 2) ** 0.5)
        self.assertTrue(group["low_effective_base_diagnostic"])

    def test_native_label_changes_rejected(self):
        audit = {"dataverse_file_id": 12050327, "respondent_data_transferred": False,
                 "selected_variables": {name: {"codes": codes} for name, codes in baseline.LABELS.items()}}
        baseline.verify_labels(audit)
        changed = copy.deepcopy(audit)
        changed["selected_variables"]["race"]["codes"]["6"] = "Middle Eastern"
        with self.assertRaisesRegex(ValueError, "Native numeric labels differ"):
            baseline.verify_labels(changed)


if __name__ == "__main__":
    unittest.main()

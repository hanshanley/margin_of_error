from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "entry", Path(__file__).with_name("review-historical-entry-compatibility.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def survey():
    return {
        "current_query_weight": "100",
        "prior": {"NO_PRESIDENT": {"weight": "3"}, "UNKNOWN": {"weight": "2"}},
        "prior_by_age": {prior: {"UNDER_18_IN_2020": {"weight": "1"}} for prior in ("D", "R", "O")},
        "prior_composition": {prior: {"conditional_scaled_current_people": str(value)}
                              for prior, value in (("D", 50), ("R", 40), ("O", 5), ("UNKNOWN", 2))},
        "control": {"presidential_2020": {"total": 145}},
    }


def vendor(first=4):
    return {"total_voter_turnout": {"2022": 100},
            "first_time_voters_vendor_definition": {"2022": first}}


def admin():
    return {"year_controls": [{"year": 2020, "official_ballots_cast": 150}],
            "comparisons": [{"prior_year": 2020, "current_year": 2022,
                             "missing_record_only_sensitivity_not_ci":
                                 {"overlap_count_lower": 90, "overlap_count_upper": 92}}]}


class EntryTests(unittest.TestCase):
    def test_unknown_choices_allowed_before_flagging_proxy_gap(self):
        result = module.entry_check(survey(), vendor())
        self.assertFalse(result["proxy_exceeds_unknown_compatible_maximum"])
        self.assertEqual(result["maximum_no_presidential_vote_if_all_unknown_choices_were_nonvoters"], Decimal(".05"))
        self.assertEqual(result["signed_proxy_minus_unknown_compatible_maximum_pp"], -1)

    def test_age_conflicts_are_additional_uncertainty_not_silent_reclassification(self):
        result = module.entry_check(survey(), vendor(6))
        self.assertTrue(result["proxy_exceeds_unknown_compatible_maximum"])
        self.assertFalse(result["proxy_exceeds_age_conflict_relaxed_maximum"])
        self.assertFalse(result["matched_population_rejection_or_significance"])
        self.assertEqual(survey()["prior"]["NO_PRESIDENT"]["weight"], "3")

    def test_missing_current_electorate_is_not_zero_entry(self):
        item = survey()
        item["current_query_weight"] = "0"
        item["prior"] = {p: {"weight": "0"} for p in ("NO_PRESIDENT", "UNKNOWN")}
        item["prior_by_age"] = {p: {"UNDER_18_IN_2020": {"weight": "0"}} for p in ("D", "R", "O")}
        self.assertIsNone(module.entry_check(item, vendor())["proxy_exceeds_unknown_compatible_maximum"])

    def test_nc_contest_gap_and_incoming_requirements_are_not_measured_error(self):
        result = module.nc_check(survey(), admin())
        self.assertEqual(result["conditional_nc2020_presidential_return_count_lower"], 85)
        self.assertEqual(result["conditional_nc2020_presidential_return_count_upper"], 92)
        self.assertEqual(result["minimum_nonNC2020_presidential_participants_needed_if_all_measurements_correct"], 3)
        self.assertIsNone(result["matched_population_error"])

    def test_nc_unknown_prior_history_can_bridge_low_known_count(self):
        item = survey()
        item["prior_composition"]["D"]["conditional_scaled_current_people"] = "38"
        result = module.nc_check(item, admin())
        self.assertFalse(result["known_plus_unknown_below_NC_minimum_under_stated_assumptions"])
        item["prior_composition"]["UNKNOWN"]["conditional_scaled_current_people"] = "0"
        self.assertTrue(module.nc_check(item, admin())["known_plus_unknown_below_NC_minimum_under_stated_assumptions"])

    def test_invalid_proxy_counts_and_overlapping_categories_rejected(self):
        for count in (-1, 101, True):
            with self.subTest(count=count), self.assertRaises(ValueError):
                module.entry_check(survey(), vendor(count))
        item = survey()
        item["prior"]["UNKNOWN"]["weight"] = "99"
        with self.assertRaises(ValueError):
            module.entry_check(item, vendor())


if __name__ == "__main__":
    unittest.main()

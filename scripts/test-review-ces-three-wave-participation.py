import copy
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "panel", Path(__file__).with_name("review-ces-three-wave-participation.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(**changes):
    result = dict(TS_g2022="4", TS_g2024="3", TS_state_22="NC", TS_state_24="NC",
                  CL_2020gvm="1", commonpostweight_24="1", commonpostweight_22="2",
                  vvweight_post_22="3")
    result.update(changes)
    return result


def scope(rows, name="ALL_SOURCE"):
    return next(s for s in module.review(rows)["scopes"] if s["scope"] == name)


class PanelParticipationTests(unittest.TestCase):
    def test_all_nine_status_cells_retain_unknowns_on_both_axes(self):
        result = scope([row(TS_g2022=a, TS_g2024=b) for a in ("4", "7", "NA") for b in ("3", "7", "NA")])
        self.assertEqual(result["source_rows"], 9)
        self.assertEqual([n for r in result["raw_matrix"].values() for n in r.values()], [1] * 9)

    def test_previous_nonvoters_include_proven_older_participants_and_unresolved(self):
        result = scope([row(TS_g2022="7"), row(TS_g2022="7", CL_2020gvm="NA")])
        weighted = result["weight_frames"]["commonpostweight_24"]
        self.assertEqual(weighted["current_only_known_2020_participants"]["n"], 1)
        self.assertEqual(weighted["current_only_first_ever_status_unresolved"]["n"], 1)
        self.assertIsNone(weighted["first_ever_voter_count"])

    def test_unknown_compatible_return_range_uses_full_prior_positive_row(self):
        result = scope([row(commonpostweight_24="2"), row(TS_g2024="7"), row(TS_g2024="NA")])
        weighted = result["weight_frames"]["commonpostweight_24"]
        self.assertEqual(weighted["return_pct_unknown_compatible_lower_not_ci"], 50)
        self.assertEqual(weighted["return_pct_unknown_compatible_upper_not_ci"], 75)
        self.assertIsNone(weighted["design_ci"])

    def test_missing_weights_do_not_drop_raw_source_cases(self):
        result = scope([row(commonpostweight_24="NA"), row(commonpostweight_24="0")])
        weighted = result["weight_frames"]["commonpostweight_24"]
        self.assertEqual(result["source_rows"], 2)
        self.assertEqual(weighted["missing_or_zero_weight_rows"], 2)
        self.assertIsNone(weighted["return_pct_unknown_compatible_lower_not_ci"])

    def test_literal_matched_states_and_unlocated_cases_are_not_survey_fips(self):
        result = module.review([row(), row(TS_state_24="DC"), row(TS_state_24="NA")])
        scopes = {s["scope"]: s for s in result["scopes"]}
        self.assertEqual((scopes["NC"]["source_rows"], scopes["DC"]["source_rows"],
                          scopes["UNLOCATED"]["source_rows"], scopes["ALL_SOURCE"]["source_rows"]),
                         (1, 1, 1, 3))
        with self.assertRaises(ValueError):
            scope([row(TS_state_24="28")])

    def test_movers_are_flagged_without_dropping_or_inventing_unknown_state(self):
        source = [row(TS_state_22="SC"), row(TS_state_22="-1")]
        before = copy.deepcopy(source)
        result = scope(source, "NC")
        self.assertEqual(result["source_rows"], 2)
        self.assertEqual(result["known_matched_state_changed_rows"], 1)
        self.assertEqual(source, before)

    def test_unknown_voting_method_is_positive_but_invalid_codes_fail(self):
        self.assertEqual(module.history("6", 2024), "POSITIVE")
        self.assertEqual(module.history("NA", 2024), "UNKNOWN")
        for changes in ({"TS_g2024": "0"}, {"CL_2020gvm": "7"},
                        {"commonpostweight_24": "-1"}, {"commonpostweight_24": "NaN"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                scope([row(**changes)])


if __name__ == "__main__":
    unittest.main()

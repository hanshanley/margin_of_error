import copy
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest


spec = importlib.util.spec_from_file_location(
    "hybrid", Path(__file__).with_name("review-ces-hybrid-participation.py"))
hybrid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hybrid)


def respondent(**changes):
    return {
        "TS_g2024": "2", "TS_voterstatus": "1", "vvweight": "1", "commonweight": "100",
        "commonpostweight": "1", "votereg_post": "1", "CC24_401": "5",
        "inputstate": "37", "TS_state": "NC", "gender4": "1",
        "race": "1", "hispanic": "2", "educ": "5", "birthyr": "1996",
    } | changes


def unmatched(**changes):
    return respondent(TS_g2024="NA", TS_voterstatus="NA", vvweight="NA", TS_state="NA", **changes)


def scope(result, name="US51"):
    return next(row for row in result["scopes"] if row["survey_scope"] == name)


class HybridParticipationTests(unittest.TestCase):
    def test_selfreported_nonvote_reduces_unknown_only_under_named_assumption(self):
        result = hybrid.review([
            respondent(commonpostweight="2"), respondent(TS_g2024="7"),
            unmatched(CC24_401="1", commonpostweight="3"),
            unmatched(votereg_post="2", CC24_401="NA", commonpostweight="4"),
            unmatched(commonpostweight="5"),
        ])
        total = scope(result)["overall"]
        self.assertEqual(total["record_only_compatible_fraction_same_post_frame"], [2 / 15, 14 / 15])
        self.assertEqual(total["guide_hybrid_compatible_fraction"], [2 / 15, 7 / 15])
        self.assertEqual(total["guide_classifiable_participation_fraction"], 0.2)
        self.assertEqual(total["guide_unknown_weight_fraction"], 1 / 3)
        self.assertEqual(total["respondents"], 5)
        self.assertIsNone(total["adult_population_turnout_rate"])
        self.assertIsNone(total["eligible_population_turnout_rate"])

    def test_all_four_reported_nonvote_codes_and_unsure_registration(self):
        result = hybrid.review([unmatched(votereg_post="3", CC24_401=str(code)) for code in range(1, 5)])
        total = scope(result)["overall"]
        self.assertEqual(total["record_and_selfreport_categories"]["selfreported_nonvote"]["respondents"], 4)
        self.assertEqual(total["guide_hybrid_compatible_fraction"], [0, 0])

    def test_contradictory_unmatched_report_has_explicit_conservative_variant(self):
        total = scope(hybrid.review([respondent(), unmatched(votereg_post="2")]))["overall"]
        self.assertEqual(total["guide_classifiable_participation_fraction"], 0.5)
        self.assertEqual(total["guide_hybrid_compatible_fraction"], [0.5, 0.5])
        self.assertEqual(total["conflict_as_unknown_compatible_fraction"], [0.5, 1])
        self.assertEqual(total["conflict_as_unknown_classifiable_participation_fraction"], 1)
        self.assertEqual(total["record_and_selfreport_categories"][hybrid.CONFLICT]["respondents"], 1)

    def test_known_records_precede_conflicting_selfreports(self):
        total = scope(hybrid.review([
            respondent(CC24_401="1"), respondent(TS_g2024="7"),
        ]))["overall"]
        self.assertEqual(total["guide_classifiable_participation_fraction"], 0.5)
        self.assertEqual(total["record_selfreport_disagreement_respondents"], 2)

    def test_unknowns_and_empty_classifiable_denominator_remain_unavailable(self):
        total = scope(hybrid.review([
            unmatched(votereg_post="3", CC24_401="NA"),
            respondent(TS_g2024="NA"), unmatched(),
        ]))["overall"]
        self.assertEqual(total["guide_hybrid_compatible_fraction"], [0, 1])
        self.assertIsNone(total["guide_classifiable_participation_fraction"])
        self.assertIsNone(total["conflict_as_unknown_classifiable_participation_fraction"])
        self.assertEqual(len(total["record_and_selfreport_categories"]), 3)

    def test_missing_postwave_weight_is_nonresponse_not_zero_turnout(self):
        result = hybrid.review([
            respondent(), unmatched(commonpostweight="NA", votereg_post="NA", CC24_401="NA"),
        ])
        self.assertEqual(result["source_audit"]["native_respondents"], 2)
        self.assertEqual(result["source_audit"]["no_postwave_weight"], 1)
        self.assertEqual(scope(result)["overall"]["respondents"], 1)
        self.assertEqual(scope(result)["overall"]["guide_classifiable_participation_fraction"], 1)

    def test_native_partitions_state_missingness_and_dc_scope(self):
        result = hybrid.review([
            respondent(TS_state="NA"), respondent(TS_state="SC", gender4="NA"),
            respondent(inputstate="11", TS_state="DC", commonpostweight="3"),
        ])
        total = scope(result, "NC")["overall"]
        self.assertEqual(total["validation_state_missing_respondents"], 1)
        self.assertEqual(total["validation_state_mismatch_respondents"], 1)
        for rows in scope(result, "NC")["partitions"].values():
            self.assertEqual(sum(r["sum_weight"] for r in rows), 2)
        self.assertEqual(scope(result, "US50")["overall"]["sum_weight"], 2)
        self.assertEqual(scope(result)["overall"]["sum_weight"], 5)
        self.assertFalse(scope(result, "UT")["available"])
        self.assertIsNone(scope(result, "UT")["overall"])
        self.assertEqual(len(result["scopes"]), 53)

    def test_candidate_choice_and_pre_or_registered_weights_do_not_select_population(self):
        rows = [respondent(), unmatched(CC24_401="1")]
        changed = copy.deepcopy(rows)
        for row in changed:
            row.update(CC24_410="invalid", TS_partyreg="invalid", commonweight="nan", vvweight_post="nan")
        self.assertEqual(hybrid.review(rows), hybrid.review(changed))

    def test_invalid_post_codes_weights_and_unweighted_responses_fail(self):
        for changes in (
            {"CC24_401": "6"}, {"votereg_post": "4"},
            {"commonpostweight": "0"}, {"commonpostweight": "-1"},
            {"commonpostweight": "nan"}, {"commonpostweight": "inf"},
            {"commonpostweight": "NA"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                hybrid.review([respondent(**changes)])

    def test_serialized_review_is_reproducible_across_hash_seeds(self):
        worker = (
            "import json,runpy; n=runpy.run_path(" + repr(str(Path(__file__).resolve())) + "); "
            "rows=[n['respondent'](TS_g2024='7',commonpostweight='10000000000000000'),"
            "n['unmatched'](CC24_401='1'),n['unmatched'](votereg_post='2',CC24_401='NA'),"
            "n['unmatched'](votereg_post='2'),n['respondent']()]; "
            "print(json.dumps(n['hybrid'].review(rows)))")
        outputs = [subprocess.check_output(
            [sys.executable, "-c", worker], env={**os.environ, "PYTHONHASHSEED": str(seed)})
            for seed in range(1, 4)]
        self.assertEqual(len(set(outputs)), 1)


if __name__ == "__main__":
    unittest.main()

import copy
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "profile", Path(__file__).with_name("review-ces-2024-current-profile.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(**changes):
    value = dict(inputstate="37", TS_state="NC", TS_g2024="4",
                 presvote20post="1", birthyr="1980")
    value.update({name: "1" for name in module.WEIGHTS})
    value.update(changes)
    return value


def control():
    return {state: {"ballots_2024": 100, "presidential_2020": {"D": 60, "R": 30, "O": 10, "total": 100}}
            for state in list(module.FIPS.values()) + ["US50", "US51"]}


def scope(rows, state="NC", index=0):
    result = module.review(iter(rows), control())
    return next(s for s in result["states"] if s["state_code"] == state)["specifications"][index]


class CurrentProfileTests(unittest.TestCase):
    def test_native_postal_geography_and_agreement_sensitivity(self):
        self.assertEqual(scope([row()])["current_query_n"], 1)
        self.assertEqual(scope([row(TS_state="OK")])["current_query_n"], 0)
        self.assertEqual(scope([row(TS_state="OK")], index=1)["current_query_n"], 1)
        with self.assertRaises(ValueError):
            scope([row(TS_state="28")])

    def test_full_denominator_keeps_nonpresidential_and_unknown_profiles(self):
        result = scope([row(), row(presvote20post="6"), row(presvote20post="NA")])
        self.assertEqual(result["current_query_n"], 3)
        self.assertAlmostEqual(result["prior_composition"]["D"]["share_full_current_query_denominator"],
                               Decimal(1) / 3, places=27)
        self.assertEqual(result["prior"]["NO_PRESIDENT"]["n"], 1)
        self.assertEqual(result["prior"]["UNKNOWN"]["n"], 1)
        self.assertIsNone(result["prior_composition"]["NO_PRESIDENT"]["signed_apparent_absence"])

    def test_new2024_adults_and_prior_profile_conflicts_preserved(self):
        result = scope([row(birthyr=str(year)) for year in (2001, 2002, 2003, 2004, 2005, 2006, 2007)])
        self.assertEqual(result["current_query_n"], 7)
        self.assertEqual([result["prior_by_age"]["D"][age]["n"] for age in module.AGE], [1, 1, 2, 2, 1])

    def test_no_current_choice_or_post_interview_answer_needed(self):
        value = row(vvweight_post="NA", commonpostweight="NA")
        self.assertNotIn("CC24_410", value)
        self.assertNotIn("CC24_401", value)
        self.assertEqual(scope([value])["current_query_n"], 1)
        self.assertEqual(scope([value], index=2)["current_query_n"], 0)

    def test_weighted_scaling_preserves_signed_negative_absence(self):
        result = scope([row(vvweight="3"), row(presvote20post="6")])
        prior = result["prior_composition"]["D"]
        self.assertEqual(prior["conditional_scaled_current_people"], 75)
        self.assertEqual(prior["signed_apparent_absence"], -15)
        self.assertEqual(prior["return_pct_original_coalition"], 125)

    def test_explicit_nonvote_missing_record_and_missing_weights_are_not_voters(self):
        result = scope([row(TS_g2024="7"), row(TS_g2024="NA"), row(TS_state="NA"), row(vvweight="NA")])
        self.assertEqual(result["current_query_n"], 0)
        self.assertEqual(result["dispositions"]["not_record_positive"]["n"], 2)
        self.assertEqual(result["dispositions"]["matched_state_missing"]["n"], 1)
        self.assertEqual(result["dispositions"]["missing_or_zero_weight"]["n"], 1)
        for changes in ({"TS_g2024": "0"}, {"presvote20post": "7"},
                        {"vvweight": "-1"}, {"vvweight": "NaN"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                scope([row(**changes)])

    def test_dc_separate_us50_and_us51_without_modifying_input(self):
        values = [row(), row(inputstate="11", TS_state="DC")]
        before = copy.deepcopy(values)
        result = module.review(iter(values), control())
        counts = {s["state_code"]: s["specifications"][0]["current_query_n"] for s in result["states"]}
        self.assertEqual([counts[s] for s in ("NC", "DC", "US50", "US51")], [1, 1, 1, 2])
        self.assertEqual(values, before)
        self.assertFalse(result["population_method_validated"])

    def test_controls_require_complete_frames_and_separate_us_reconciliation(self):
        original = {s: {"D": 60, "R": 30, "O": 10, "total": 100} for s in module.FIPS.values()}
        selected = {"official_2020": {"states": original}, "turnout_2024": {
            "states": {s: {"ballots": 100, "status": "source_reported_unverified"} for s in original},
            "separate_us_ballots": 5100}}
        result = module.controls(selected)
        self.assertEqual((result["US50"]["ballots_2024"], result["US51"]["ballots_2024"]), (5000, 5100))
        selected["turnout_2024"]["separate_us_ballots"] = 5101
        with self.assertRaises(ValueError):
            module.controls(selected)
        del selected["turnout_2024"]["states"]["NC"]
        with self.assertRaises(ValueError):
            module.controls(selected)


if __name__ == "__main__":
    unittest.main()

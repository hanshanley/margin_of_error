import copy
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "reporting", Path(__file__).with_name("review-ces-three-wave-reporting.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(**changes):
    value = {name: "NA" for name in module.REQUIRED}
    value.update(CC20_410="1", presvote20post_24="1", presvote20post_22="1",
                 CL_2020gvm="1", TS_g2024="4", CC24_401="5", CC24_412="1",
                 inputstate_20="37", inputstate_24="37", commonpostweight_24="2",
                 commonpostweight_22="3", vvweight_post_22="4",
                 HouseCand1Party_post_24="Republican")
    value.update(changes)
    return value


def bridge():
    return {
        "status": "cross_wave_common_item_bridge_conditional_not_panel_native_labels",
        "panel_numeric_labels_directly_qualified": False,
        "panel_code_transport_assumption_required": True,
        "same_case_2020_choice_and_state_matches": 6175,
        "baseline_codes": {"1": "Joe Biden (Democrat)", "2": "Donald J. Trump (Republican)",
                           "4": "Other", "5": "I did not vote in this race",
                           "6": "I did not vote", "7": "Not sure"},
        "profile_2020_codes_in_2024_common": {"1": "Joe Biden", "2": "Donald Trump",
                                           "6": "Did not vote for President"},
        "current_house_codes_in_2024_common": {**{code: "" for code in module.HOUSE_CODES},
                                               "10": "Other", "11": "I did not vote in this race",
                                               "13": "Not sure"},
    }


class ThreeWaveReportingTests(unittest.TestCase):
    def test_native2024_fields_and_actual_weights_replace_only_explicit_helper_roles(self):
        source = [row()]
        before = copy.deepcopy(source)
        results = module.scope_review(source, True)
        self.assertEqual([results[i]["current_validated_voter_weight"] for i in (0, 4, 8)],
                         [Decimal(2), Decimal(3), Decimal(4)])
        self.assertEqual([results[i]["weight"] for i in (0, 4, 8)], list(module.WEIGHTS))
        self.assertEqual(source, before)
        self.assertNotIn("recalled", str(results))
        self.assertNotIn("unmatched_2022", str(results))

    def test_changed_profile_reports_preserve_signed_difference_and_negative_absence(self):
        result = module.scope_review([row(presvote20post_24="2")], True)[0]
        democratic, republican = result["comparisons"]
        self.assertEqual(democratic["return_difference_weight_units"], -2)
        self.assertEqual(republican["estimated_apparent_absence_weight_units"], -2)
        self.assertIsNone(republican["estimated_return_pct"])

    def test_known_reference_frame_retains_presidential_nonvote_but_excludes_unknown_reports(self):
        results = module.scope_review([row(CC20_410="5", presvote20post_24="6"),
                                       row(CC20_410="NA", presvote20post_24="6")], True)
        self.assertEqual(results[0]["dispositions"]["retained"]["n"], 1)
        self.assertEqual(results[0]["unknown_reference_choice_rows_excluded_from_paired_frame"], 1)
        self.assertEqual(results[2]["dispositions"]["retained"]["n"], 2)

    def test_unknown_current_history_stays_in_coverage_and_compatible_ranges(self):
        result = module.scope_review([row(TS_g2024="NA")], True)[0]
        self.assertEqual(result["dispositions"]["unmatched_current_history"]["n"], 1)
        democratic = result["comparisons"][0]
        self.assertEqual(democratic["compatible_return_pct_lower_with_unmatched_current"], 0)
        self.assertEqual(democratic["compatible_return_pct_upper_with_unmatched_current"], 100)

    def test_2024_does_not_inherit_unsupported2022_house_response_codes(self):
        for code in ("6", "7", "8", "12"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                module.scope_review([row(CC24_412=code)], True)
        result = module.scope_review([row(HouseCand1Party_post_24="Independent")], True)[0]
        self.assertEqual(result["current_house_by_contemporaneous_prior_validated_voters"]["D"]["O"]["n"], 1)

    def test_state_stability_and_dc_exclusion_are_not_national_mover_exclusion(self):
        result = module.review([row(), row(inputstate_20="11", inputstate_24="11"),
                                row(inputstate_20="37", inputstate_24="6")])
        scopes = {scope["scope"]: scope for scope in result["scopes"]}
        self.assertEqual(scopes["CA"]["current_survey_state_rows"], 1)
        self.assertEqual(scopes["CA"]["stable_survey_state_rows"], 0)
        self.assertEqual(scopes["US50"]["specifications"][0]["dispositions"]["retained"]["n"], 2)
        self.assertEqual(scopes["US51"]["specifications"][0]["dispositions"]["retained"]["n"], 3)
        self.assertFalse(result["population_method_validated"])
        self.assertTrue(result["panel_code_transport_assumption_required"])

    def test_conditional_codebook_transport_cannot_be_presented_as_native_numeric_qualification(self):
        module.checked_bridge(bridge())
        for key, value in (("panel_code_transport_assumption_required", False),
                           ("panel_numeric_labels_directly_qualified", True)):
            item = bridge()
            item[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.checked_bridge(item)
        item = bridge()
        item["current_house_codes_in_2024_common"]["12"] = "I did not vote"
        with self.assertRaises(ValueError):
            module.checked_bridge(item)


if __name__ == "__main__":
    unittest.main()

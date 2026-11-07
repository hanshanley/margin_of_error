import copy
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "recall", Path(__file__).with_name("review-ces-historical-recall.py"))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def row(old="1", recall="1", turnout="4", house="1", party="Democratic"):
    result = {field: "NA" for field in module.REQUIRED}
    result.update({
        "CC20_410": old, "presvote20post": recall, "CL_2020gvm": "4",
        "TS_g2022": turnout, "CC22_401": "5" if turnout != "7" else "1",
        "CC22_412": house, "inputstate_20": "6", "inputstate_22": "6",
        "commonpostweight_22": "1", "vvweight_post_22": "1",
        "HouseCand1Party_post_22": party, "HouseCand2Party_post_22": "Republican",
    })
    return result


class RecallTests(unittest.TestCase):
    def primary(self, rows):
        return module.review(rows)["specifications"][0]

    def test_correct_recall_identity_is_control_not_validation(self):
        result = module.review([row(), row(turnout="7"), row("2", "2", house="2")])
        for comparison in result["specifications"][0]["comparisons"]:
            self.assertEqual(Decimal(comparison["return_error_pp"]), 0)
            self.assertEqual(Decimal(comparison["switch_error_pp_original_coalition"]), 0)
        self.assertFalse(result["population_method_validated"])

    def test_prior_reclassification_changes_return_and_directional_switching(self):
        rows = [row(), row("2", "1"), row("2", "2", turnout="7")]
        d, r = self.primary(rows)["comparisons"]
        self.assertEqual(Decimal(d["return_error_pp"]), 100)
        self.assertEqual(Decimal(d["estimated_apparent_absence_weight_units"]), -1)
        self.assertEqual(Decimal(r["return_error_pp"]), -50)
        self.assertEqual(Decimal(r["switch_error_pp_original_coalition"]), -50)

    def test_unmatched_turnout_preserved_in_bounds_not_assigned_nonvote(self):
        result = self.primary([row(), row(turnout="7"), row(turnout="NA")])
        d = result["comparisons"][0]
        self.assertEqual(result["dispositions"]["unmatched_2022_history"]["n"], 1)
        self.assertEqual(d["benchmark_explicit_nonvote"]["n"], 1)
        self.assertEqual(d["all_2020_positive_validation_prior_coalition"]["unknown"]["n"], 1)
        self.assertLess(Decimal(d["compatible_return_pct_lower_with_unmatched_2022"]), 34)
        self.assertGreater(Decimal(d["compatible_return_pct_upper_with_unmatched_2022"]), 66)

    def test_party_is_selected_literal_post_candidate_not_position(self):
        self.assertEqual(module.house_choice(row(party="Republican")), "R")
        self.assertEqual(module.house_choice(row(party="Conservative")), "O")
        self.assertEqual(module.house_choice(row(party="-1")), "UNKNOWN")
        self.assertEqual(module.house_choice(row(house="11")), "CONTEST_NONVOTE")

    def test_unknown_house_and_prior_responses_keep_denominators(self):
        result = self.primary([row("2", "2"), row("2", "2", house="NA"),
                               row("4", "5"), row("NA", "6")])
        r = result["comparisons"][1]
        self.assertEqual(Decimal(r["p_reported_opposite_house_full_query_coalition"]), Decimal(".5"))
        self.assertEqual(Decimal(result["current_validated_voter_weight"]), 4)
        self.assertEqual(result["current_house_by_recalled_prior_query_voters"]["NO_PRESIDENT"]["D"]["n"], 1)

    def test_missing_2020_validation_and_either_wave_dc_are_explicit(self):
        missing, dc = row(), row()
        missing["CL_2020gvm"] = "NA"
        dc["inputstate_20"] = "11"
        result = self.primary([row(), missing, dc])
        self.assertEqual(result["dispositions"]["no_positive_2020_validation"]["n"], 1)
        self.assertEqual(result["dispositions"]["dc_excluded"]["n"], 1)
        self.assertEqual(result["dispositions"]["retained"]["n"], 1)

    def test_self_report_rule_does_not_change_administrative_total(self):
        false_positive = row(turnout="7")
        false_positive["CC22_401"] = "5"
        result = module.review([row(), false_positive])
        a, b = result["specifications"][:2]
        self.assertEqual(a["current_validated_voter_weight"], b["current_validated_voter_weight"])
        self.assertEqual(Decimal(a["query_voter_weight"]), 1)
        self.assertEqual(Decimal(b["query_voter_weight"]), 2)

    def test_postweight_nonresponse_is_not_replaced_by_another_weight(self):
        nonresponse = row()
        nonresponse["commonpostweight_22"] = "NA"
        result = module.review([row(), nonresponse])
        self.assertEqual(result["specifications"][0]["dispositions"]["retained"]["n"], 1)
        self.assertEqual(result["specifications"][4]["dispositions"]["retained"]["n"], 2)

    def test_empty_query_and_empty_coalition_rates_are_unavailable(self):
        d, r = self.primary([row(turnout="7")])["comparisons"]
        self.assertIsNone(d["estimated_returned_weight_units"])
        self.assertIsNone(r["benchmark_return_pct"])
        self.assertIsNone(r["estimated_return_pct"])

    def test_invalid_native_codes_and_weights_fail_closed(self):
        for field, value in (("TS_g2022", "9"), ("CC20_410", "3"),
                             ("CC22_412", "9"), ("commonpostweight_22", "-1"),
                             ("commonpostweight_22", "NaN")):
            with self.subTest(field=field, value=value):
                bad = row()
                bad[field] = value
                with self.assertRaises((ValueError, ArithmeticError)):
                    self.primary([bad])
        bad = copy.deepcopy(row())
        del bad["TS_g2022"]
        with self.assertRaises(ValueError):
            self.primary([bad])


if __name__ == "__main__":
    unittest.main()

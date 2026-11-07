from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "all_state", Path(__file__).with_name("review-all-state-historical-recall.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(state="6", prior="1", recalled="1", turnout="4", **extra):
    result = {key: "NA" for key in module.recall.REQUIRED}
    result.update({
        "inputstate_20": state, "inputstate_22": state,
        "CC20_410": prior, "presvote20post": recalled, "CL_2020gvm": "4",
        "TS_g2022": turnout, "CC22_401": "1" if turnout == "7" else "5",
        "CC22_412": "1", "HouseCand1Party_post_22": "Democratic",
        "commonpostweight_22": "1", "vvweight_post_22": "1",
        **extra,
    })
    return result


class AllStateTests(unittest.TestCase):
    def test_all_states_present_including_empty_without_false_validation(self):
        result = module.review([row()])
        self.assertEqual(len(result["states"]), 50)
        self.assertEqual(len({s["state_code"] for s in result["states"]}), 50)
        self.assertNotIn("DC", {s["state_code"] for s in result["states"]})
        self.assertEqual(sum(s["current_survey_state_rows"] for s in result["states"]), 1)
        self.assertEqual(sum(len(s["specifications"]) for s in result["states"]), 200)
        self.assertEqual(result["states_population_validated"], 0)
        empty = next(s for s in result["states"] if s["state_code"] == "AK")
        self.assertEqual(empty["historical_test_status"], "no_primary_known_history_frame")
        self.assertIsNone(empty["specifications"][0]["comparisons"][0]["return_error_pp"])

    def test_movers_unresolved_states_and_dc_partition_without_reassignment(self):
        rows = [row(), row(inputstate_20="37"), row(inputstate_20="NA"),
                row("11"), row(inputstate_22="NA")]
        result = module.review(rows)
        ca = next(s for s in result["states"] if s["state_code"] == "CA")
        self.assertEqual(ca["current_survey_state_rows"], 3)
        self.assertEqual(ca["same_survey_state_both_waves"], 1)
        self.assertEqual(ca["different_prior_survey_state_excluded"], 1)
        self.assertEqual(ca["unresolved_prior_survey_state_excluded"], 1)
        self.assertEqual(result["dc_rows_separate_not_discarded"], 1)
        self.assertEqual(result["unresolved_current_state_rows"], 1)
        self.assertEqual(ca["specifications"][0]["dispositions"]["retained"]["n"], 1)

    def test_changed_recall_has_actual_signed_errors_not_a_tautology(self):
        result = module.review([row(), row(prior="2"), row(prior="2", recalled="2", turnout="7")])
        ca = next(s for s in result["states"] if s["state_code"] == "CA")
        d, r = ca["specifications"][0]["comparisons"]
        self.assertEqual(Decimal(d["return_error_pp"]), 100)
        self.assertEqual(Decimal(r["return_error_pp"]), -50)
        self.assertFalse(ca["population_method_validated"])

    def test_unknown_history_stays_unknown_and_effective_n_uses_retained_frame(self):
        rows = [row(commonpostweight_22="2"), row(turnout="7"),
                row(turnout="NA", commonpostweight_22="100")]
        result = module.review(rows)
        ca = next(s for s in result["states"] if s["state_code"] == "CA")
        primary = ca["specifications"][0]
        self.assertEqual(primary["dispositions"]["unmatched_2022_history"]["n"], 1)
        sample = primary["baseline_effective_samples"]["D"]
        self.assertEqual(sample["raw_n"], 2)
        self.assertEqual(Decimal(sample["weight_sum"]), 3)
        self.assertEqual(Decimal(sample["kish_effective_n_descriptive_not_design_precision"]), Decimal("1.8"))

    def test_self_report_changes_query_not_administrative_total(self):
        result = module.review([row(), row(turnout="7", CC22_401="5")])
        ca = next(s for s in result["states"] if s["state_code"] == "CA")
        a, b = ca["specifications"][:2]
        self.assertEqual(a["current_validated_voter_weight"], b["current_validated_voter_weight"])
        self.assertEqual(Decimal(a["query_voter_weight"]), 1)
        self.assertEqual(Decimal(b["query_voter_weight"]), 2)

    def test_each_weight_keeps_its_own_frame(self):
        result = module.review([row(), row(commonpostweight_22="NA")])
        ca = next(s for s in result["states"] if s["state_code"] == "CA")
        self.assertEqual(ca["specifications"][0]["dispositions"]["retained"]["n"], 1)
        self.assertEqual(ca["specifications"][2]["dispositions"]["retained"]["n"], 2)

    def test_invalid_native_codes_and_missing_columns_fail(self):
        for extra in ({"TS_g2022": "9"}, {"commonpostweight_22": "NaN"},
                      {"CL_2020gvm": "9"}):
            with self.subTest(extra=extra), self.assertRaises((ValueError, ArithmeticError)):
                module.review([row(**extra)])
        bad = row()
        del bad["TS_g2022"]
        with self.assertRaises(ValueError):
            module.review([bad])


if __name__ == "__main__":
    unittest.main()

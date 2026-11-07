import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "gates", Path(__file__).with_name("review-all-state-2026-validation-gates.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def historical():
    primary = {
        "dispositions": {"retained": {"n": 2}},
        "comparisons": [{"prior_coalition": p, "return_error_pp": "1"} for p in ("D", "R")],
        "baseline_effective_samples": {"D": {"raw_n": 1}, "R": {"raw_n": 1}},
    }
    return {
        "status": "all_50_state_historical_recall_diagnostics_not_population_validation",
        "population_method_validated": False,
        "states": [{"state_code": code, "population_method_validated": False,
                    "specifications": [copy.deepcopy(primary) for _ in range(4)],
                    "different_prior_survey_state_excluded": 0} for code in sorted(module.STATES)],
    }


def preliminary():
    return {
        "status": "preliminary_estimated_total_scenarios_not_validated_participation",
        "state_comparisons": [
            {"state_code": "NC", "contest_code": "SG", "reference": {"R": {"apparent_absence_count": -1}},
             "current_electorate_composition": {"N": {"reported_current_choice_counts": {"D": None}}}}],
        "jurisdictions": [{"state_code": code, "conditional_contests": ["SG"] if code == "NC" else [],
                           "preliminary_turnout": {"ballots": 1000, "native_record": {
                               "STATE_ABV": code, "SOURCE": "Initial Estimate"}}}
                          for code in sorted(module.STATES | {"DC"})],
        "national_house_comparison": {"state_code": "US", "contest_code": "HG", "value": 123},
        "assumptions_and_limits": ["original limitation"],
    }


class GateTests(unittest.TestCase):
    def test_all_states_present_without_inventing_missing_2026_estimates(self):
        result = module.review(historical(), preliminary())
        self.assertEqual(len(result["states"]), 50)
        self.assertEqual(result["states_with_conditional_2026_comparisons"], 1)
        self.assertEqual(result["conditional_state_contests"], 1)
        missing = next(s for s in result["states"] if s["state_code"] == "AK")
        self.assertEqual(missing["conditional_2026_comparisons_unchanged"], [])
        self.assertEqual(missing["current_estimate_status"], "no_qualified_state_joint_table_no_transition_estimate")
        self.assertEqual(result["dc_disposition_separate"]["state_code"], "DC")
        self.assertEqual(result["estimated_ballots_50_state_sum_excluding_dc"], 50000)
        self.assertTrue(all(s["estimated_2026_total_ballots"] == 1000 for s in result["states"]))

    def test_negative_counts_suppression_and_original_values_are_not_modified(self):
        h, p = historical(), preliminary()
        before = copy.deepcopy((h, p))
        result = module.review(h, p)
        current = next(s for s in result["states"] if s["state_code"] == "NC")
        self.assertEqual(current["conditional_2026_comparisons_unchanged"], p["state_comparisons"])
        self.assertEqual((h, p), before)
        self.assertEqual(result["national_house_comparison_unchanged_not_state_allocated"], p["national_house_comparison"])

    def test_historical_diagnostic_never_becomes_population_validation(self):
        result = module.review(historical(), preliminary())
        self.assertFalse(result["population_method_validated"])
        self.assertEqual(result["states_population_validated"], 0)
        for state in result["states"]:
            self.assertFalse(state["population_validation_gate"]["certified_2026_transition_counts_allowed"])

    def test_invalid_or_promoted_turnout_cannot_be_used(self):
        for value in (True, 0, -1, None):
            p = preliminary()
            p["jurisdictions"][0]["preliminary_turnout"]["ballots"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.review(historical(), p)
        p = preliminary()
        p["jurisdictions"][0]["preliminary_turnout"]["native_record"]["SOURCE"] = "Certified"
        with self.assertRaises(ValueError):
            module.review(historical(), p)

    def test_incomplete_duplicate_or_falsely_validated_historical_states_fail(self):
        for edit in ("missing", "duplicate", "claimed_validated", "partial_specs"):
            h = historical()
            if edit == "missing":
                h["states"].pop()
            elif edit == "duplicate":
                h["states"][-1] = copy.deepcopy(h["states"][0])
            elif edit == "claimed_validated":
                h["states"][0]["population_method_validated"] = True
            else:
                h["states"][0]["specifications"].pop()
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.review(h, preliminary())

    def test_duplicate_contests_unknown_states_or_missing_dispositions_fail(self):
        for edit in ("duplicate", "unknown", "missing_dc"):
            p = preliminary()
            if edit == "duplicate":
                p["state_comparisons"].append(copy.deepcopy(p["state_comparisons"][0]))
            elif edit == "unknown":
                p["state_comparisons"][0]["state_code"] = "XX"
            else:
                p["jurisdictions"] = [s for s in p["jurisdictions"] if s["state_code"] != "DC"]
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.review(historical(), p)


if __name__ == "__main__":
    unittest.main()

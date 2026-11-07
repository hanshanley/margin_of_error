import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "state_age_package", Path(__file__).with_name("package-state-age-coalitions.py"))
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def audit():
    return {
        "status": "private_state_birth_year_support_not_qualified_population_estimates",
        "historical_controls_checked": True,
        "cohorts": [{
            "state_code": state, "prior_choice": prior, "native_current_survey_subset": 55,
            "minimum_age": 65, "maximum_age": None,
            "coalition": {"respondents": 400, "effective_sample_size": 300, "sum_weight": 500},
            "certain_age_support": {
                "respondents": 150, "effective_sample_size": 110,
                "fraction_within_reported_2024_coalition": .3 if state == "CA" else .4},
            "possible_age_support_including_unknown_birth_year": {
                "respondents": 151, "fraction_within_reported_2024_coalition": .35},
            "birthday_boundary_respondents": 1, "unknown_birth_year_respondents": 0,
        } for state in ("CA", "TX") for prior in ("D", "R")],
    }


def current():
    return {"estimates": [{"state_code": state, "subset": {"sub": 55}} for state in ("CA", "TX")]}


class StateAgePackageTests(unittest.TestCase):
    def test_selection_retains_own_state_support_and_excludes_small_boundary_fields(self):
        selected = package.select_historical(audit(), current())
        self.assertEqual(len(selected), 4)
        self.assertEqual([r["certain_age_support"]["fraction_within_reported_2024_coalition"]
                          for r in selected], [.3, .3, .4, .4])
        self.assertTrue(all("birthday_boundary_respondents" not in r and
                            "unknown_birth_year_respondents" not in r for r in selected))
        self.assertTrue(all("respondents" not in r["possible_age_support_including_unknown_birth_year"]
                            for r in selected))
        self.assertTrue(all("sum_weight" not in r["coalition"] for r in selected))

    def test_source_support_shortlist_requires_both_prior_coalitions(self):
        for field, value in (("respondents", 99), ("effective_sample_size", 99),
                             ("effective_sample_size", None)):
            historical = audit()
            historical["cohorts"][0]["certain_age_support"][field] = value
            self.assertEqual({r["state_code"] for r in package.select_historical(historical, current())}, {"TX"})

    def test_bad_controls_duplicate_and_missing_state_support_fail(self):
        historical = audit()
        historical["historical_controls_checked"] = False
        with self.assertRaises(ValueError):
            package.select_historical(historical, current())
        historical = audit()
        historical["cohorts"].append(copy.deepcopy(historical["cohorts"][0]))
        with self.assertRaises(ValueError):
            package.select_historical(historical, current())
        historical = audit()
        historical["cohorts"].pop()
        with self.assertRaises(KeyError):
            package.select_historical(historical, current())

    def test_summary_retains_signed_results_and_suppression_without_full_scenario_duplication(self):
        result = {"estimates": [{
            "state_code": "CA", "contest_code": "GG", "subset": 55, "prior_choice": "D",
            "birth_year_only_apparent_absence": {"lower": -10, "upper": 2},
            "design_confidence_interval": None, "sensitivity_scenarios": [{
                "status": "conditional_sensitivity_scenario", "apparent_absence_count": -20,
                "reported_opposite_choice_count": None, "original_coalition_scaled_switching_pct": None,
            }],
        }]}
        row = package.summarize(result, audit())["estimates"][0]
        self.assertNotIn("sensitivity_scenarios", row)
        self.assertEqual(row["marginal_sensitivity_apparent_absence_count"], {"lower": -20, "upper": -20})
        self.assertIsNone(row["marginal_sensitivity_reported_opposite_choice_count"])
        self.assertEqual(row["birth_year_only_apparent_absence"]["lower"], -10)
        self.assertIsNone(row["design_confidence_interval"])
        self.assertIn("sensitivity_scenarios", result["estimates"][0])

    def test_changed_selected_input_requires_new_immutable_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / package.DATA
            path.mkdir(parents=True)
            for name in package.PINS:
                (path / name).write_bytes((package.ROOT / package.DATA / name).read_bytes())
            (path / "selected-historical-support.json").write_text('{"historical_controls_checked":true}')
            with patch.object(package, "ROOT", root), self.assertRaises(ValueError):
                package.selected_inputs()


if __name__ == "__main__":
    unittest.main()

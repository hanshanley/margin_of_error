import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "age_package", Path(__file__).with_name("package-national-age-coalitions.py"))
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class AgePackageTests(unittest.TestCase):
    def support(self):
        return {"cohorts": [{
            "native_current_survey_subset": 53, "prior_choice": "R",
            "certain_age_support": {"respondents": 194, "effective_sample_size": 114},
            "coalition": {"respondents": 13666}, "birthday_boundary_respondents": 1,
        }]}

    def result(self):
        return {"status": "conditional_scenarios", "estimates": [{
            "subset": 53, "prior_choice": "R", "birth_year_only_apparent_absence": {"lower": -10, "upper": 2},
            "design_confidence_interval": None, "sensitivity_scenarios": [{
                "status": "conditional_sensitivity_scenario",
                "reported_opposite_choice_count": 3, "original_coalition_scaled_switching_pct": 5,
            }],
        }]}

    def test_summary_retains_signed_results_without_large_or_small_private_cells(self):
        result = self.result()
        summary = package.summarize(result, self.support())
        row = summary["estimates"][0]
        self.assertNotIn("sensitivity_scenarios", row)
        self.assertNotIn("birthday_boundary_respondents", row)
        self.assertEqual(row["birth_year_only_apparent_absence"]["lower"], -10)
        self.assertIsNone(row["design_confidence_interval"])
        self.assertEqual(row["marginal_sensitivity_reported_opposite_choice_count"], {"lower": 3, "upper": 3})
        self.assertIn("sensitivity_scenarios", result["estimates"][0])

    def test_missing_or_zero_denominator_rate_does_not_create_a_finite_envelope(self):
        result = self.result()
        result["estimates"][0]["sensitivity_scenarios"].append({
            "status": "conditional_sensitivity_scenario",
            "reported_opposite_choice_count": None, "original_coalition_scaled_switching_pct": None,
        })
        row = package.summarize(result, self.support())["estimates"][0]
        self.assertIsNone(row["marginal_sensitivity_reported_opposite_choice_count"])
        self.assertIsNone(row["marginal_sensitivity_original_coalition_scaled_switching_pct"])

    def test_changed_selected_input_requires_a_new_reviewed_version(self):
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

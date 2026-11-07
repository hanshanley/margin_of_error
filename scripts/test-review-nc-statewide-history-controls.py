import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "history_controls", Path(__file__).with_name("review-nc-statewide-history-controls.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CoverageTests(unittest.TestCase):
    def test_missing_only_bounds_allow_either_wave_and_respect_official_marginals(self):
        result = module.missing_only_bounds(90, 60, 50, 100, 65)
        self.assertEqual(result["overlap_count_lower"], 50)
        self.assertEqual(result["overlap_count_upper"], 65)
        self.assertEqual(result["return_pct_lower"], 50)
        self.assertEqual(result["return_pct_upper"], 65)
        self.assertEqual(module.missing_only_bounds(90, 90, 90, 100, 100)["overlap_count_upper"], 100)

    def test_overcoverage_is_incompatible_not_clamped(self):
        self.assertIsNone(module.missing_only_bounds(101, 60, 50, 100, 65))
        self.assertIsNone(module.missing_only_bounds(90, 66, 50, 100, 65))

    def test_empty_denominators_and_invalid_counts_remain_unavailable_or_rejected(self):
        result = module.missing_only_bounds(0, 0, 0, 0, 0)
        self.assertIsNone(result["return_pct_lower"])
        for args in ((True, 1, 0, 1, 1), (1, 1, 2, 2, 2), (-1, 1, 0, 1, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                module.missing_only_bounds(*args)

    def test_official_ballot_column_is_not_eligible_denominator_and_missing_year_fails(self):
        rows = "".join("<tr><td>%d General</td><td>999</td><td>%d</td><td>10%%</td></tr>" % (year, n)
                       for year, n in ((2020, 100), (2022, 60), (2024, 110)))
        self.assertEqual(module.official_ballots("<table>" + rows + "</table>"), {2020: 100, 2022: 60, 2024: 110})
        with self.assertRaises(ValueError):
            module.official_ballots("<table>" + rows.replace("2024 General", "2026 General") + "</table>")


if __name__ == "__main__":
    unittest.main()

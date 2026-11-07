import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "panel", Path(__file__).with_name("review-prolific-panel.py"))
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


def fixture():
    tables = {}
    for name, (base, total, answers) in panel.TABLES.items():
        cells = {(3, 1): base, (7, 2): total,
                 (7, 1): "Unweighted n", (8, 1): "Weighted n", (9, 1): "Effective n"}
        for column, label in enumerate(
            ("Harris", "Trump", "Other candidate", "Did not vote / not eligible", "Rather not say"), 6):
            cells[6, column] = label
        for column in (6, 7):
            for row, value in ((7, 100), (8, 90), (9, 70)):
                cells[row, column] = value
            for index, answer in enumerate(answers):
                row = 10 + 2 * index
                cells[row, 1], cells[row + 1, 1] = answer, "    \u00b1"
                cells[row, column] = 100 if index == 0 else 0
                cells[row + 1, column] = 0 if index == 1 else 4
        tables[name] = cells
    return tables


class ProlificPanelTests(unittest.TestCase):
    def test_retains_zeroes_full_responses_and_actual_conditional_margins(self):
        result = panel.review(fixture())
        self.assertEqual(len(result["tables"]), 3)
        choices = result["tables"][1]["groups"][0]["responses"]
        self.assertEqual(len(choices), 5)
        self.assertEqual(choices[1]["weighted_percentage"], 0)
        self.assertEqual(choices[1]["publisher_bootstrap_margin_pp"], 0)
        self.assertEqual(choices[-1]["native_response"], "I would not vote %")
        self.assertEqual(result["tables"][0]["groups"][0]["responses"][0]
                         ["publisher_bootstrap_margin_pp"], 4)

    def test_wrong_universe_and_ambiguous_prior_columns_fail_closed(self):
        for key, value in (((3, 1), panel.RV_BASE), ((7, 2), 1251), ((6, 6), "Trump")):
            tables = fixture()
            tables["01 LikeVote"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                panel.review(tables)

    def test_missing_reordered_or_nonreconciling_answers_fail(self):
        for key, value in (((10, 1), "Would not vote"), ((11, 1), None), ((10, 6), 99)):
            tables = fixture()
            tables["01 LikeVote"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                panel.review(tables)

    def test_invalid_native_probabilities_margins_and_support_fail(self):
        for key, values in (((10, 6), (None, True, -1, 101, float("nan"))),
                            ((11, 6), (None, True, -1, float("inf"))),
                            ((7, 6), (None, True, 0, 1.5))):
            for value in values:
                tables = fixture()
                tables["01 LikeVote"][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    panel.review(tables)

    def test_differing_same_respondent_support_rejected_not_multiplied(self):
        for row in (7, 8, 9):
            tables = fixture()
            tables["05 GenBallot resp"][row, 6] += 1
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, "support differs"):
                panel.review(tables)

    def test_no_population_turnout_absence_local_allocation_or_public_qualification(self):
        tables = fixture()
        original = copy.deepcopy(tables)
        result = panel.review(tables)
        self.assertEqual(tables, original)
        self.assertFalse(result["public_release_qualified"])
        for field in panel.UNSUPPORTED:
            self.assertIsNone(result[field])
        self.assertNotEqual(result["tables"][0]["native_population"],
                            result["tables"][1]["native_population"])


if __name__ == "__main__":
    unittest.main()

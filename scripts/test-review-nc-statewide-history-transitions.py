import importlib.util
from pathlib import Path
import sqlite3
import unittest


spec = importlib.util.spec_from_file_location(
    "statewide_history", Path(__file__).with_name("review-nc-statewide-history-transitions.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(identity, date="11/03/2020", description="GENERAL"):
    return {"ncid": identity, "election_lbl": date, "election_desc": description}


class StatewideHistoryTests(unittest.TestCase):
    def test_duplicates_and_reentry_are_reduced_without_emitting_identifiers(self):
        source = [row("PRIVATE1"), row("PRIVATE1"), row("PRIVATE1", "11/08/2022"),
                  row("PRIVATE2"), row("PRIVATE2", "11/05/2024"),
                  row("PRIVATE3", "11/06/2018"), row("PRIVATE3", "11/08/2022"),
                  row("", "11/08/2022"), row("PRIVATE4", "03/05/2024", "PRIMARY")]
        with sqlite3.connect(":memory:") as connection:
            masks, audit = module.reduce_rows(source, connection, batch_size=2)
        result = module.summarize_masks(masks)
        self.assertEqual(audit["native_records"], 9)
        self.assertEqual(audit["raw_general_2020_records"], 3)
        self.assertEqual(audit["missing_identifier_2022_records"], 1)
        self.assertEqual(result["available_2016_through_2024_history_union_records"], 3)
        first, second = result["comparisons"]
        self.assertEqual(first["record_presence_matrix"], {
            "recorded_both": 1, "recorded_prior_only": 1,
            "recorded_current_only": 1, "neither_recorded": 0})
        self.assertEqual(first["positive_earlier_history_in_current_only_not_first_ever"], 1)
        self.assertEqual(second["positive_earlier_history_in_current_only_not_first_ever"], 1)
        self.assertNotIn("PRIVATE", str(result))
        self.assertIsNone(first["first_ever_voters"])
        self.assertFalse(result["population_method_validated"])

    def test_no_denominator_or_history_never_becomes_zero_turnout(self):
        result = module.summarize_masks({})
        for comparison in result["comparisons"]:
            self.assertIsNone(comparison["recorded_current_among_recorded_prior_pct"])
            self.assertIsNone(comparison["population_turnout_rate"])

    def test_invalid_masks_and_counts_fail(self):
        for counts in ({0: 1}, {32: 1}, {True: 1}, {1: True}, {1: 0}, {1: -1}):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                module.summarize_masks(counts)

    def test_wrong_election_and_batch_size_fail(self):
        with sqlite3.connect(":memory:") as connection:
            with self.assertRaises(ValueError):
                module.reduce_rows([row("PRIVATE", description="PRIMARY")], connection)
        with sqlite3.connect(":memory:") as connection:
            with self.assertRaises(ValueError):
                module.reduce_rows([], connection, batch_size=0)


if __name__ == "__main__":
    unittest.main()

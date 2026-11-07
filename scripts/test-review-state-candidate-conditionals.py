import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "candidate_conditionals_test", Path(__file__).with_name("review-state-candidate-conditionals.py"))
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
SOURCE = ROOT / "data/participation-candidate-conditionals/20261107-01/selected-source-tables.json"


class CandidateConditionalsTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads(SOURCE.read_text())

    def test_literal_candidates_and_distinct_sullivans_are_not_pooled(self):
        result = model.review(self.snapshot)
        senate = next(row for row in result["contests"]
                      if (row["state_code"], row["contest_code"]) == ("AK", "SG"))
        names = {row["full_name"]: row for row in senate["candidates"]}
        self.assertEqual(names["Dan S. Sullivan"]["literal_party"], "R")
        self.assertEqual(names["Daniel J. Sullivan"]["literal_party"], "I")
        self.assertNotEqual(names["Dan S. Sullivan"]["candidate_id"], names["Daniel J. Sullivan"]["candidate_id"])
        self.assertEqual(len(senate["candidates"]), 4)
        self.assertEqual(set(senate["reported_choices_by_prior"]), {"D", "R", "O", "N"})
        values = {row["candidate_id"]: row["percentage"]
                  for row in senate["reported_choices_by_prior"]["R"]["current_candidate_percentages"]}
        self.assertEqual(values[70718], 5)
        self.assertEqual(values[64262], 90)
        self.assertEqual(values[177716], 1)

    def test_suppressed_cell_remains_unknown(self):
        source = next(row for row in self.snapshot["sources"] if
                      row["configuration_entry"]["stateAbbr"] == "NH"
                      and row["configuration_entry"]["raceTypeCode"] == "SG")
        answer = next(row for row in source["selected_native_data"]["questions"][0]["answers"]
                      if row["answer"] == "Trump")
        answer["candidateAnswers"][0]["percentage"] = -1
        result = next(row for row in model.review(self.snapshot)["contests"]
                      if row["state_code"] == "NH" and row["contest_code"] == "SG")
        self.assertIsNone(result["reported_choices_by_prior"]["R"]["current_candidate_percentages"][0]["percentage"])

    def test_wrong_election_and_unreleased_sources_fail_closed(self):
        for change in ("election", "release"):
            snapshot = copy.deepcopy(self.snapshot)
            data = snapshot["sources"][0]["selected_native_data"]
            if change == "election":
                data["electionDate"] = "2024-11-05"
            else:
                data["exitPollEmbargo"]["exitPollsReleased"] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                model.review(snapshot)

    def test_unexplained_gaps_and_all_population_gates_are_preserved(self):
        result = model.review(self.snapshot)
        for row in result["contests"]:
            self.assertEqual(row["unexplained_gap_from_100_pct"],
                             5 if (row["state_code"], row["contest_code"]) == ("NH", "GG") else 3)
            self.assertEqual(sum(value["reported_prior_share_pct"]
                                 for value in row["reported_choices_by_prior"].values()),
                             row["reported_prior_composition_sum_pct"])
            self.assertIn(row["ordinary_comparison_status"], model.WITHHELD)
            for field in ("estimated_returning_count", "estimated_switcher_count", "apparent_absence_count",
                          "measured_staying_home_count", "original_coalition_switching_rate",
                          "share_of_total_swing", "design_confidence_interval", "inferred_ranked_choice_round"):
                self.assertIsNone(row[field])
        self.assertFalse(result["population_or_original_coalition_scaling_performed"])

    def test_duplicate_or_missing_contest_inventory_is_rejected(self):
        self.snapshot["sources"][0] = copy.deepcopy(self.snapshot["sources"][1])
        with self.assertRaisesRegex(ValueError, "four selected"):
            model.review(self.snapshot)


if __name__ == "__main__":
    unittest.main()

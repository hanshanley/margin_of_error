import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "history_transitions", Path(__file__).with_name("review-registration-history-transitions.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def cell(before=False, middle=False, after=False, count=10, **extra):
    return {
        "records": count,
        "registration_status_2026": "ACTIVE",
        "registration_by_2020": True,
        "historical_search_complete": True,
        "prior_2016_history": False, "prior_2018_history": False,
        "prior_2020_history": before, "prior_2022_history": middle,
        "prior_2024_history": ("Positive 2024 NC history" if after else
                              "No 2024 NC history found; national participation unresolved"),
        **extra,
    }


class HistoryTransitionTests(unittest.TestCase):
    def test_completed_elections_partition_same_frame_without_inventing_new_voters(self):
        rows = [cell(True, True, True, 40), cell(True, False, True, 20),
                cell(False, True, False, 10), cell(False, False, False, 30)]
        result = module.summarize(rows)
        first, second = result["comparisons"]
        self.assertEqual(result["retained_registration_frame"], 100)
        self.assertEqual(first["record_presence_matrix"], {
            "recorded_both": 40, "recorded_prior_only": 20,
            "recorded_current_only": 10, "neither_recorded": 30})
        self.assertAlmostEqual(first["recorded_current_among_recorded_prior_pct"], 100 * 40 / 60)
        self.assertEqual(second["record_presence_matrix"], {
            "recorded_both": 40, "recorded_prior_only": 10,
            "recorded_current_only": 20, "neither_recorded": 30})
        for comparison in result["comparisons"]:
            for key in ("first_ever_voters", "confirmed_previously_eligible_nonparticipants",
                        "population_turnout_rate", "candidate_choice_retention"):
                self.assertIsNone(comparison[key])

    def test_exclusions_are_disjoint_and_unsearched_history_does_not_become_nonvoting(self):
        result = module.summarize([
            cell(count=10, registration_status_2026="REMOVED", historical_search_complete=False),
            cell(count=20, historical_search_complete=False, prior_2020_history=None),
            cell(count=30, registration_by_2020=None),
            cell(count=40, registration_by_2020=False),
            cell(True, True, True, 50),
        ])
        self.assertEqual(result["input_aggregate_population"], 150)
        self.assertEqual(result["retained_registration_frame"], 50)
        self.assertEqual(result["mutually_exclusive_frame_exclusions"], {
            "not_currently_active_or_inactive": 10, "incomplete_history_search": 20,
            "current_registration_not_established_by_2020": 70})
        self.assertEqual(result["comparisons"][0]["record_presence_matrix"]["recorded_both"], 50)

    def test_empty_denominators_are_unavailable_not_zero_rates(self):
        result = module.summarize([cell()])
        for comparison in result["comparisons"]:
            self.assertIsNone(comparison["recorded_current_among_recorded_prior_pct"])
            self.assertIsNone(comparison["recorded_prior_among_recorded_current_pct"])

    def test_older_positive_history_rules_out_first_time_without_promoting_no_match(self):
        source = [
            cell(False, True, False, 10, prior_2018_history=True),
            cell(False, True, False, 20),
            cell(True, False, True, 30),
            cell(False, False, True, 40),
        ]
        first, second = module.summarize(source)["comparisons"]
        self.assertEqual(first["current_only_record_split"], {
            "positive_history_before_prior_election_not_first_ever": 10,
            "no_earlier_record_found_first_ever_unresolved": 20})
        self.assertEqual(second["current_only_record_split"], {
            "positive_history_before_prior_election_not_first_ever": 30,
            "no_earlier_record_found_first_ever_unresolved": 40})
        self.assertIsNone(first["first_ever_voters"])
        source[0]["prior_2018_history"] = None
        with self.assertRaises(ValueError):
            module.summarize(source)

    def test_unknown_flags_invalid_counts_and_unknown_2024_labels_fail(self):
        for edit in ({"records": True}, {"records": 0}, {"records": -1},
                     {"prior_2020_history": None}, {"prior_2022_history": 1},
                     {"prior_2024_history": "unknown"}, {"historical_search_complete": None},
                     {"registration_by_2020": 1}):
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.summarize([cell(**edit)])

    def test_selection_does_not_mutate_input_and_current_2026_history_is_unused(self):
        source = [cell(True, True, True, positive_2026_history=None),
                  cell(False, False, True, positive_2026_history=False)]
        before = copy.deepcopy(source)
        expected = module.summarize(source)
        for row in source:
            row["positive_2026_history"] = "incomplete"
        self.assertEqual(module.summarize(source), expected)
        self.assertEqual([{k: v for k, v in row.items() if k != "positive_2026_history"} for row in source],
                         [{k: v for k, v in row.items() if k != "positive_2026_history"} for row in before])

    def test_private_summary_requires_matching_native_and_independent_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = json.dumps([cell(True, True, True)]).encode()
            digest = hashlib.sha256(raw).hexdigest()
            (root / "joint-cells.json").write_bytes(raw)
            audit = {"state_code": "NC", "county": "EXAMPLE", "joint_cells_sha256": digest,
                     "aggregate_cells": 1, "sources": [],
                     "history": {f"general_{year}_records": 10 for year in (2016, 2018, 2020, 2022, 2024)}}
            controls = {"county": "EXAMPLE", "joint_cells_sha256": digest,
                        "all_linkage_control_signatures_match": True,
                        "controls": {"private_population": 10}}
            (root / "audit.json").write_text(json.dumps(audit))
            proof = root / "controls.json"
            proof.write_text(json.dumps(controls))
            result = module.qualified_summary(root, proof)
            self.assertEqual(result["retained_registration_frame"], 10)
            controls["controls"]["private_population"] = 11
            proof.write_text(json.dumps(controls))
            with self.assertRaises(ValueError):
                module.qualified_summary(root, proof)
            controls["controls"]["private_population"] = 10
            controls["all_linkage_control_signatures_match"] = False
            proof.write_text(json.dumps(controls))
            with self.assertRaises(ValueError):
                module.qualified_summary(root, proof)
            proof.write_text(json.dumps({**controls, "all_linkage_control_signatures_match": True}))
            (root / "joint-cells.json").write_bytes(raw + b"\n")
            with self.assertRaises(ValueError):
                module.qualified_summary(root, proof)

    def test_missing_pairs_cannot_create_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "output"
            with self.assertRaises(ValueError):
                module.review([], [], out)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()

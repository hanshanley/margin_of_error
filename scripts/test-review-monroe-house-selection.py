import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("monroe_selection", HERE / "review-monroe-house-selection.py")
monroe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monroe)
SOURCE = HERE / "selected-source-facts.json"
if not SOURCE.exists():
    SOURCE = HERE.parent / "data/county-source-reviews/20261107-monroe-selected-01/selected-source-facts.json"


class MonroeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.selected = monroe.load(SOURCE)

    def test_literal_vectors_and_separate_participation(self):
        audit, rows, receipts = monroe.review(self.selected)
        self.assertEqual(audit["house_candidate_votes"], 61096)
        self.assertEqual({party: sum(row["votes"] for row in rows if row["party"] == party)
                          for party in ["DEMOCRATIC", "REPUBLICAN", ""]},
                         {"DEMOCRATIC": 35619, "REPUBLICAN": 25343, "": 134})
        self.assertEqual(audit["participation"]["total_ballots_tabulated"], 61587)
        self.assertEqual(len(receipts), 4)
        self.assertFalse(audit["precinct_longitudinal_qualified"])

    def test_changed_factual_input_cannot_replace_the_reviewed_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "changed.json"
            self.selected["participation"]["total_ballots_tabulated"] += 1
            target.write_text(json.dumps(self.selected))
            with self.assertRaisesRegex(ValueError, "Changed selected source"):
                monroe.load(target)

    def test_native_blank_party_is_not_relabelled_from_old_workbook(self):
        self.selected["contests"][1]["candidates"][-1]["party_html"] = "Nonpartisan"
        with self.assertRaisesRegex(ValueError, "literal candidate or party"):
            monroe.review(self.selected)

    def test_unit_and_mode_counts_require_independent_reconciliation(self):
        for kind in ["unit_count", "mode_count", "boolean"]:
            with self.subTest(kind=kind):
                selected = copy.deepcopy(self.selected)
                contest = selected["contests"][1]
                if kind == "unit_count":
                    contest["reporting_units"][0]["candidate_counts"][0] += 1
                elif kind == "mode_count":
                    contest["candidates"][0]["modes"]["Election Day"] += 1
                else:
                    contest["reporting_units"][0]["candidate_counts"][0] = True
                with self.assertRaises(ValueError):
                    monroe.review(selected)

    def test_duplicate_units_or_incomplete_county_partition_are_rejected(self):
        for name in [self.selected["contests"][1]["reporting_units"][1]["name"], "Unmatched unit"]:
            with self.subTest(name=name):
                selected = copy.deepcopy(self.selected)
                selected["contests"][1]["reporting_units"][0]["name"] = name
                with self.assertRaisesRegex(ValueError, "reporting units|county cover"):
                    monroe.review(selected)

    def test_complete_package_reproduces_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = [Path(temporary) / name for name in ["first", "second"]]
            for folder in [first, second]:
                monroe.build(SOURCE, folder)
            self.assertEqual({path.name: path.read_bytes() for path in first.iterdir()},
                             {path.name: path.read_bytes() for path in second.iterdir()})
            inventory = json.loads((first / "checksums.json").read_bytes())
            self.assertEqual(set(inventory) | {"checksums.json"}, {path.name for path in first.iterdir()})
            self.assertTrue(all(monroe.checksum(first / name) == expected
                                for name, expected in inventory.items()))
            with self.assertRaisesRegex(ValueError, "overwrite"):
                monroe.build(SOURCE, first)


if __name__ == "__main__":
    unittest.main()

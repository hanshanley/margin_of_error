import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest


FOLDER = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("reviewer", FOLDER / "review-bradford-native-query.py")
REVIEWER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEWER)


class NativeQueryTests(unittest.TestCase):
    def setUp(self):
        self.records = json.loads(gzip.decompress((FOLDER / "source-records.json.gz").read_bytes()))

    def test_complete_reproduction_and_scope_preservation(self):
        expected = REVIEWER.reproduce(FOLDER)
        for name, body in expected.items():
            self.assertEqual((FOLDER / name).read_bytes(), body, name)
        tables = REVIEWER.tables(self.records)
        self.assertEqual(len(tables["county-candidate-results.csv"]), 26)
        self.assertTrue(all(not row["all_mode_participation_approved"]
                            for row in tables["election-day-participation.csv"]))
        district_rows = [row for row in tables["county-contest-accounting.csv"]
                         if row["geographic_scope"] == "within_county_Assembly_district_subset"]
        self.assertTrue(all(row["native_scope_ballots"] == ""
                            and row["unclassified_ballot_minus_candidate_sum"] == "" for row in district_rows))

    def test_rejects_all_mode_promotion_and_received_mail_addition(self):
        for update in (dict(all_mode_participation=20982), dict(counted_mail_ballots=3346)):
            changed = copy.deepcopy(self.records)
            changed.update(update)
            with self.assertRaises(ValueError):
                REVIEWER.validate(changed, check_pinned=False)
        self.records["snapshots"][0]["snapshot"]["voting_mode_literal"] = "All ballots"
        with self.assertRaisesRegex(ValueError, "all-mode"):
            REVIEWER.validate(self.records, check_pinned=False)

    def test_rejects_lost_earlier_snapshot(self):
        self.records["snapshots"].pop()
        with self.assertRaisesRegex(ValueError, "snapshot"):
            REVIEWER.validate(self.records, check_pinned=False)

    def test_rejects_inferred_write_in_party(self):
        self.records["snapshots"][0]["contests"][0]["choices"][-1]["native_party"] = "OTH"
        with self.assertRaisesRegex(ValueError, "write-in party"):
            REVIEWER.validate(self.records, check_pinned=False)

    def test_rejects_extrapolated_legislative_reporting_scope(self):
        self.records["snapshots"][0]["contests"][2]["total_precincts"] = 61
        with self.assertRaisesRegex(ValueError, "reporting fraction"):
            REVIEWER.validate(self.records, check_pinned=False)

    def test_rejects_changed_native_choice_and_clock(self):
        self.records["snapshots"][0]["contests"][0]["choices"][0]["votes"] += 1
        with self.assertRaisesRegex(ValueError, "choice sum"):
            REVIEWER.validate(self.records, check_pinned=False)
        self.setUp()
        self.records["snapshots"][0]["snapshot"]["source_update_literal"] = ""
        with self.assertRaisesRegex(ValueError, "clock"):
            REVIEWER.validate(self.records, check_pinned=False)


if __name__ == "__main__":
    unittest.main()

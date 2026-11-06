import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("review_tioga", ROOT / "review-tioga.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FACTS = json.loads((ROOT / "native-facts.json").read_text())


class TiogaReviewTests(unittest.TestCase):
    def test_complete_native_query_and_blank_inclusion(self):
        tables, audit = MODULE.review(FACTS)
        county = tables["county-participation.csv"]
        self.assertEqual([row["ballots_cast"] for row in county], [14845, 12683, 2162, 0])
        self.assertEqual(county[0]["registered_voters"], 26874)
        self.assertEqual(county[0]["blank_ballots_already_included"], 2)
        self.assertEqual(len(tables["precinct-participation.csv"]), 164)
        self.assertEqual(len(tables["candidate-results.csv"]), 1680)
        self.assertEqual(audit["map_approvals"], 0)
        self.assertEqual(len(audit["reviewed_candidate_percent_conflicts"]), 3)
        self.assertTrue(all(row["source_clock_precedes_election"] for row in county))
        self.assertTrue(all(row["native_overvotes"] == "" and row["native_undervotes"] == ""
                            for row in tables["contest-accounting.csv"]))

    def test_missing_page_rejected(self):
        with self.assertRaisesRegex(ValueError, "43-page"):
            MODULE.parse_pages(FACTS["native_pages"]["pdfplumber"][:-1])

    def test_repaired_clock_rejected(self):
        pages = copy.deepcopy(FACTS["native_pages"]["pdfplumber"])
        pages[0] = pages[0].replace("08/08/2026", "11/03/2026")
        with self.assertRaisesRegex(ValueError, "clock"):
            MODULE.parse_pages(pages)

    def test_mode_mismatch_rejected(self):
        pages = copy.deepcopy(FACTS["native_pages"]["pdfplumber"])
        pages[0] = pages[0].replace("14,845 12,683 2,162 0", "14,845 12,684 2,162 0")
        with self.assertRaisesRegex(ValueError, "reported modes"):
            MODULE.parse_pages(pages)

    def test_candidate_accounting_mismatch_rejected(self):
        pages = copy.deepcopy(FACTS["native_pages"]["pdfplumber"])
        pages[1] = pages[1].replace("9,861 66.81% 9,032 829 0", "9,862 66.81% 9,033 829 0")
        with self.assertRaisesRegex(ValueError, "accounting"):
            MODULE.parse_pages(pages)

    def test_duplicate_precinct_rejected(self):
        pages = copy.deepcopy(FACTS["native_pages"]["pdfplumber"])
        pages[3] = pages[3].replace("Blossburg Borough", "Bloss Township")
        with self.assertRaisesRegex(ValueError, "duplicate native precinct"):
            MODULE.parse_pages(pages)

    def test_missing_literal_party_rejected(self):
        pages = copy.deepcopy(FACTS["native_pages"]["pdfplumber"])
        pages[1] = pages[1].replace("REP Stacy Garrity", "Stacy Garrity")
        with self.assertRaisesRegex(ValueError, "party"):
            MODULE.parse_pages(pages)

    def test_unreviewed_percentage_conflict_rejected(self):
        pages = copy.deepcopy(FACTS["native_pages"]["pdfplumber"])
        pages[1] = pages[1].replace("9,861 66.81%", "9,861 66.82%")
        with self.assertRaisesRegex(ValueError, "Unreviewed native candidate percentage"):
            MODULE.parse_pages(pages)

    def test_existing_destination_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "already exist"):
                MODULE.build(Path(directory))


if __name__ == "__main__":
    unittest.main()

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("susquehanna", ROOT / "review-susquehanna.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ORIGINAL = copy.deepcopy(module.REPORTS)
COLUMNS = json.loads((ROOT / "summary-columns.json").read_text())


class NativeQueryTests(unittest.TestCase):
    def setUp(self):
        module.REPORTS = copy.deepcopy(ORIGINAL)

    def tearDown(self):
        module.REPORTS = copy.deepcopy(ORIGINAL)

    def change(self, role, page, before, after):
        text = module.REPORTS[role]["native_pages"]["pdfplumber"][page]
        self.assertIn(before, text)
        module.REPORTS[role]["native_pages"]["pdfplumber"][page] = text.replace(before, after, 1)

    def review(self):
        return module.review("pdfplumber", COLUMNS["pdfplumber"])

    def test_complete_independent_parses_reconcile_without_substituting_votes_for_ballots(self):
        left = module.validated()
        self.assertEqual(left, self.review())
        county = left["summary"]
        self.assertEqual(county["total_ballots"], sum(row["total_ballots"] for row in left["precincts"]))
        self.assertTrue(all(c["total_votes"] < county["total_ballots"] for c in county["contests"].values()))
        self.assertTrue(all(row["exact_half_tie"] for row in left["round_half_up_differences"]))

    def test_changed_candidate_vote_fails_instead_of_adjusting_totals(self):
        self.change("precinct", 0, "68 35.79%", "69 35.79%")
        with self.assertRaises(AssertionError):
            self.review()

    def test_changed_ballot_total_fails(self):
        self.change("precinct", 0, "Total Ballots 191", "Total Ballots 192")
        with self.assertRaises(AssertionError):
            self.review()

    def test_repeated_registrations_cannot_be_pooled(self):
        self.change("canvass", 0, "Normal 347 157", "Normal 694 157")
        with self.assertRaises(AssertionError):
            self.review()

    def test_missing_canvass_page_is_not_partial_success(self):
        module.REPORTS["canvass"]["native_pages"]["pdfplumber"].pop()
        with self.assertRaises(AssertionError):
            self.review()

    def test_duplicate_mode_cannot_replace_mail(self):
        self.change("canvass", 0, "Absentee / Mail-In 347 33", "Normal 347 33")
        with self.assertRaises(AssertionError):
            self.review()

    def test_dash_is_not_a_nonzero_vote_percentage(self):
        with self.assertRaises(AssertionError):
            module.check_percentage(1, 33, "-", "mutated zero choice", [])

    def test_half_even_tie_cannot_be_rewritten_half_up(self):
        self.change("precinct", 4, "70.62%", "70.63%")
        with self.assertRaises(AssertionError):
            self.review()

    def test_governor_canvass_affiliations_remain_explicit_cross_report_matches(self):
        tables = module.tables(self.review())
        rows = [r for r in tables["canvass-candidate-results.csv"] if r["native_contest"] == module.SPECS[0][0]]
        self.assertTrue(rows)
        self.assertTrue(all(r["native_literal_party"] == "" for r in rows))
        self.assertTrue(any(r["matched_summary_literal_party"] == "DEM" for r in rows))
        self.assertTrue(any(r["native_choice"] != r["matched_summary_choice"] for r in rows))
        self.assertTrue(all(r["native_ballot_mode_count"] == "" for r in rows))

    def test_missing_accounting_and_unclassified_residuals_are_not_zero_or_undervotes(self):
        tables = module.tables(self.review())
        self.assertTrue(all(r["native_undervotes"] == "" and r["native_overvotes"] == ""
                            for r in tables["contest-accounting.csv"]))
        county = [r for r in tables["contest-accounting.csv"] if r["scope"] == "county"]
        self.assertEqual([r["ballots_less_contest_votes_unclassified"] for r in county], [71, 130, 143, 105])
        self.assertTrue(all(r["blank_ballots"] == "" for r in tables["precinct-participation.csv"]))

    def test_changed_extractor_inventory_is_rejected(self):
        self.change("canvass", 0, "Normal 347 157", "Normal 347 158")
        with self.assertRaises(AssertionError):
            module.validated()


if __name__ == "__main__":
    unittest.main()

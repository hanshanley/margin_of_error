import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest


folder = Path(__file__).parent
spec = importlib.util.spec_from_file_location("georgia_query", folder / "review-georgia-native-query.py")
query = importlib.util.module_from_spec(spec)
spec.loader.exec_module(query)


class GeorgiaQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = json.loads(gzip.decompress((folder / "source-records.json.gz").read_bytes()))

    def test_blank_native_turnout_cards_are_retained_not_dropped(self):
        cards, root = query.parse_voters(self.records["voters"]["text"])
        self.assertEqual(len(cards), 159)
        self.assertEqual(cards["Screven County"], dict(voters=0, ballots=5236, printed_turnout=""))
        self.assertEqual(cards["Jeff Davis County"], dict(voters=0, ballots=4180, printed_turnout=""))
        self.assertEqual(root["ballots"], 4210155)

    def test_county_uuid_join_is_case_insensitive_and_order_independent(self):
        records = dict(self.records, primary=copy.deepcopy(self.records["primary"]))
        rows = records["primary"]["complete_county_native_records"]
        rows.reverse()
        for row in rows:
            row["native_child_locality"]["id"] = row["native_child_locality"]["id"].swapcase()
        observed, _ = query.participation(records)
        self.assertEqual(len(observed), 159)
        self.assertEqual(sum(row["native_ballots_cast"] for row in observed), 4210155)

    def test_changed_ballot_or_invented_zero_turnout_is_rejected(self):
        for old, new in (("Ballots Cast: 6,224", "Ballots Cast: 6,225"),
                         ("Ballots Cast: 4,180\nVoter Turnout:", "Ballots Cast: 4,180\nVoter Turnout: 0.00%")):
            text = self.records["voters"]["text"]
            self.assertIn(old, text)
            records = dict(self.records, voters=dict(self.records["voters"], text=text.replace(old, new, 1)))
            with self.assertRaises(ValueError):
                query.participation(records)

    def test_missing_modes_are_not_zero_or_a_complete_sum(self):
        self.assertEqual(query.mode_summary([dict(voteCount=12), dict(voteCount=None)]),
                         dict(known_sum=12, missing_cells=1, complete=False, complete_sum=None))
        self.assertEqual(query.mode_summary([dict(voteCount=0)])["complete_sum"], 0)
        self.assertIsNone(query.mode_summary([])["complete_sum"])

    def test_conflicting_native_root_is_not_overwritten(self):
        records = dict(self.records, primary=copy.deepcopy(self.records["primary"]))
        records["primary"]["election"]["ballotsCast"] = 4210155
        with self.assertRaisesRegex(ValueError, "overwritten"):
            query.participation(records)

    def test_complete_source_audit_preserves_parties_modes_and_stage_exclusions(self):
        _, _, audit = query.validate(self.records)
        self.assertEqual(audit["missing_mode_cells"], 372)
        self.assertEqual(audit["exception_counts"]["incomplete_modes"], 93)
        self.assertEqual(audit["exception_counts"]["literal_party_differences"], 116)
        self.assertEqual(audit["exception_counts"]["unresolved_contest_scopes"], 2)
        self.assertEqual(audit["exception_counts"]["root_minus_approved_county_residuals"], 4)
        self.assertTrue(any(row["native_county_party"] == "" and row["native_root_party"] == "Rep"
                            for row in audit["exceptions"]["literal_party_differences"]))
        self.assertTrue(any("Special Primary" in row["native_root_contest"] and
                            "Special Primary" not in row["native_county_contest"]
                            for row in audit["exceptions"]["unresolved_contest_scopes"]))

    def test_downloads_keep_full_native_rows_and_missing_party_and_mode_cells(self):
        counties, root = query.participation(self.records)
        tables = query.tables(self.records, counties, root)
        self.assertEqual(len(tables["candidate-results.csv"]), 7524)
        self.assertEqual(len(tables["precinct-choice-results.csv.gz"]), 102214)
        self.assertEqual(sum(row["native_votes"] is None for row in tables["candidate-mode-results.csv"]), 372)
        choice = next(row for row in tables["candidate-results.csv"]
                      if row["native_locality_name"] == "Liberty County"
                      and row["native_choice_id"] == "5")
        self.assertEqual(choice["native_party"], "")
        self.assertEqual(choice["scope"], "county")
        self.assertTrue(all(row["source_fips"] == "" for row in tables["county-participation.csv"]))


if __name__ == "__main__":
    unittest.main()

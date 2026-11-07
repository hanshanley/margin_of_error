import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("scope", Path(__file__).with_name("review-nc-candidate-scope.py"))
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


def row(**overrides):
    values = {"County": "DURHAM", "Election Date": "11/03/2026", "Vote For": "1",
              "Precinct": "EARLY", "Real Precinct": "N", "Contest Name": "US SENATE",
              "Choice": "Example", "Choice Party": "DEM", "Election Day": "0", "Early Voting": "10",
              "Absentee by Mail": "2", "Provisional": "0", "Total Votes": "12"}
    values.update(overrides)
    return values


class ScopeTest(unittest.TestCase):
    def test_retains_administrative_votes_and_literal_parties_by_separate_contest(self):
        records = scope.aggregate_candidates([row(), row(**{
            "Contest Name": "US HOUSE OF REPRESENTATIVES DISTRICT 04", "Choice Party": "UNA",
        })], 2026)
        self.assertEqual(len(records), 10)
        self.assertEqual({record["party_literal"] for record in records}, {"DEM", "UNA"})
        self.assertEqual(sum(record["votes"] for record in records if record["method"] == "Total Votes"), 24)

    def test_rejects_duplicate_wrong_date_unreconciled_and_unknown_counts(self):
        for records in [[row(), row()], [row(**{"Election Date": "11/05/2024"})],
                        [row(**{"Total Votes": "13"})], [row(**{"Early Voting": "*"})],
                        [row(**{"Vote For": "2"})]]:
            with self.assertRaises(ValueError):
                scope.aggregate_candidates(records, 2026)

    def test_separates_presidential_baseline_from_congressional_returns(self):
        record = row(**{"Contest Name": "US PRESIDENT", "Election Date": "11/05/2024"})
        self.assertEqual({item["year"] for item in scope.aggregate_candidates([record], 2024)}, {2024})
        with self.assertRaises(ValueError):
            scope.aggregate_candidates([record], 2026)


if __name__ == "__main__":
    unittest.main()

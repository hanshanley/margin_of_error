import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("alabama_counties", Path(__file__).with_name("alabama-county-counts.py"))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class AlabamaCountyCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = core.frozen()

    def test_all_native_counts_join_by_name_not_ordinal_code(self):
        result = core.qualify(**self.inputs)
        jefferson = next(row for row in result["county_decisions"] if row["native_county_code"] == "01")
        self.assertEqual((jefferson["county_fips"], jefferson["ballots"], jefferson["registered"]),
                         ("01073", 248526, 497469))
        self.assertEqual(len(result["county_decisions"]), 67)
        self.assertEqual(sum(row["ballots"] for row in result["county_decisions"]), 1693621)
        self.assertTrue(all(row["reported_pct"] is None for row in result["county_decisions"]))
        self.assertEqual(jefferson["native_printed_pct"], "49.96%")

    def test_missing_native_statistics_are_not_filled_from_candidates(self):
        values = copy.deepcopy(self.inputs)
        values["sheets"]["Statistics"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete county statistics"):
            core.qualify(**values)

    def test_mixed_election_and_candidate_count_substitution_are_rejected(self):
        for field, value in [("Election Code", "2024"), ("Ballots Cast", "1")]:
            with self.subTest(field=field):
                values = copy.deepcopy(self.inputs)
                values["sheets"]["Statistics"][0][field] = value
                with self.assertRaises(ValueError):
                    core.qualify(**values)

    def test_duplicate_reference_and_incomplete_topology_review_are_rejected(self):
        values = copy.deepcopy(self.inputs)
        values["geometry"]["features"][1] = values["geometry"]["features"][0]
        with self.assertRaisesRegex(ValueError, "Duplicate county reference"):
            core.qualify(**values)
        values = copy.deepcopy(self.inputs)
        values["pairs"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete or positive"):
            core.qualify(**values)


if __name__ == "__main__":
    unittest.main()

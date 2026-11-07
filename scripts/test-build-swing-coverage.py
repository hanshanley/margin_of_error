import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("coverage", Path(__file__).with_name("build-swing-coverage.py"))
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


class CoverageTest(unittest.TestCase):
    def test_all_states_dc_and_split_counties_do_not_become_false_estimates(self):
        model = {"models": [{"group_diagnostics": {"state": [
            {"group": state, "low_effective_sample": state == "DC"} for state in coverage.CODES
        ]}}]}
        candidates = [
            dict(year="2026", office="U.S. House", votes="10", state_code="NC", county_fips="37001",
                 district=district, county_name="Alamance", party=party, source_url="source", source_updated_at="clock")
            for district in ["NC-01", "NC-02"] for party in ["Democratic", "Republican"]
        ]
        result = coverage.build(model, candidates, [], [])
        self.assertEqual(len(result["jurisdictions"]), 51)
        self.assertEqual(result["state_count"], 50)
        self.assertTrue(all(not row["attribution_available"] for row in result["county_contests"]))
        self.assertTrue(all(any("split" in reason for reason in row["exclusions"]) for row in result["county_contests"]))
        dc = next(row for row in result["jurisdictions"] if row["state_code"] == "DC")
        self.assertIn("delegate", dc["house_applicability"])
        self.assertIn("not assumed absent", dc["governor_inventory"])
        lone_party = [dict(candidates[0], party="Independent")]
        uncontested = coverage.build(model, lone_party, [], [])["county_contests"][0]
        self.assertEqual(uncontested["literal_party_totals"], {"Independent": 10})
        self.assertTrue(any("two-major-party" in reason for reason in uncontested["exclusions"]))

    def test_missing_jurisdictions_fail_instead_of_disappearing(self):
        with self.assertRaises(ValueError):
            coverage.build({"models": [{"group_diagnostics": {"state": []}}]}, [], [], [])


if __name__ == "__main__":
    unittest.main()

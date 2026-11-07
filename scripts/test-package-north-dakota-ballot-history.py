import copy
import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "selected_nd", Path(__file__).with_name("package-north-dakota-ballot-history.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DATA = Path(__file__).resolve().parents[1] / module.DATA


class SelectedBallotHistoryTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((DATA / "selected-observations.json").read_bytes())
        self.methods = json.loads((DATA / "methodology-review.json").read_bytes())

    def test_complete_native_counts_and_signed_changes_keep_unknown_transitions(self):
        result = module.review(self.source, self.methods)
        self.assertEqual(len(result["counties"]), 53)
        self.assertEqual(result["statewide"]["ballots_by_year"],
                         {"2022": 242526, "2024": 371975, "2026": 239057})
        self.assertEqual(result["statewide"]["reported_ballot_count_change_since_2024"], -132918)
        self.assertEqual(result["statewide"]["reported_ballot_count_change_since_2022"], -3469)
        self.assertFalse(result["current_snapshot_official"])
        self.assertFalse(result["precinct_longitudinal_comparison_qualified"])
        for key in ("measured_prior_voter_dropoff", "new_or_returning_voters",
                    "party_switchers", "demographic_turnout_rate"):
            self.assertIsNone(result["statewide"][key])
            self.assertTrue(all(row[key] is None for row in result["counties"]))

    def test_election_status_version_and_denominator_cannot_be_promoted(self):
        for index, key, value in [
            (2, "official", True), (2, "source_version", "v76"),
            (2, "election_date", "2026-05-01"), (2, "native_eligible_voters", 500000),
            (0, "source_clock_timezone", "UTC"), (0, "official", False),
            (1, "native_denominator_definition", "registered voters"),
        ]:
            source = copy.deepcopy(self.source)
            source["observations"][index][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.review(source, self.methods)

    def test_every_selected_precinct_is_required_and_missing_is_not_zero(self):
        for edit in ("missing", "negative", "boolean", "float", "wrong_sum", "wrong_count"):
            source = copy.deepcopy(self.source)
            observation = source["observations"][0]
            row = observation["counties"][0]
            if edit == "missing":
                row["precincts"].clear()
            elif edit == "wrong_sum":
                row["ballots"] += 1
            elif edit == "wrong_count":
                observation["reported_precincts"] += 1
            else:
                row["precincts"][0]["ballots"] = {"negative": -1, "boolean": True, "float": 932.0}[edit]
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.review(source, self.methods)

    def test_duplicate_county_and_within_county_precinct_identities_fail(self):
        for edit in ("county", "county_code", "precinct", "historical_parent"):
            source = copy.deepcopy(self.source)
            rows = source["observations"][0]["counties"]
            if edit == "county":
                rows[1]["county_name"] = rows[0]["county_name"]
            elif edit == "county_code":
                rows[1]["native_county_id"] = rows[0]["native_county_id"]
            elif edit == "precinct":
                row = next(row for row in rows if len(row["precincts"]) > 1)
                row["precincts"][1]["precinct_id"] = row["precincts"][0]["precinct_id"]
            else:
                rows[0]["precincts"][0]["precinct_id"] = "023901"
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.review(source, self.methods)
        source = copy.deepcopy(self.source)
        source["observations"][2]["counties"][0]["county_name"] = "Unmatched"
        with self.assertRaises(ValueError):
            module.review(source, self.methods)

    def test_current_local_ids_can_repeat_in_different_counties(self):
        current = self.source["observations"][2]
        identities = [row["precinct_id"] for county in current["counties"] for row in county["precincts"]]
        self.assertLess(len(set(identities)), len(identities))
        result = module.review(self.source, self.methods)
        self.assertEqual(result["source_observations"][2]["reported_precincts"], 358)

    def test_population_and_geographic_claims_remain_unqualified(self):
        for key in ("individual_transitions_qualified", "demographic_turnout_rates_qualified",
                    "precinct_longitudinal_comparison_qualified", "geographic_overlay_qualified"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.review(self.source, {**self.methods, key: True})

    def test_unselected_fields_and_missing_native_provenance_fail(self):
        for edit in ("private_field", "receipt", "hash", "url", "secret_field"):
            source = copy.deepcopy(self.source)
            if edit == "private_field":
                source["observations"][0]["counties"][0]["voters"] = ["person"]
            elif edit == "receipt":
                del source["source_receipts"]["terminology_and_archive"]
            else:
                source["source_receipts"]["2022"][{
                    "hash": "sha256", "url": "url", "secret_field": "authorization"}[edit]] = "changed"
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.review(source, self.methods)


if __name__ == "__main__":
    unittest.main()

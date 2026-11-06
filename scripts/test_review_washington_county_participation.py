import copy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data/county-source-reviews/20261106-washington-participation-01"
SPEC = importlib.util.spec_from_file_location(
    "washington", ROOT / "scripts/review-washington-county-participation.py")
washington = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(washington)


class WashingtonCountyParticipationTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def test_native_state_zero_does_not_replace_county_participation(self):
        counties, units, audit = washington.reconcile(self.facts)
        king = next(row for row in counties if row["source_short_name"] == "king-county-wa")
        self.assertEqual(audit["native_state_ballots"], 0)
        self.assertGreater(audit["county_ballots_sum"], 0)
        self.assertEqual(king["unallocated_county_ballots"], king["ballots_cast"])
        self.assertGreater(king["registered_turnout_percent"], 0)
        self.assertTrue(all(row["ballots_cast"] == 0 for row in units
                            if row["county_id"] == king["county_id"]))
        self.assertIn("not zero participation", king["quality_flags"])

    def test_independent_county_state_count_and_identity_mismatches_fail(self):
        for field, value in (("ballotsCast", 1), ("totalVoters", 1), ("id", "other-election")):
            facts = copy.deepcopy(self.facts)
            facts["counties"][0]["election"][field] = value
            with self.assertRaisesRegex(ValueError, "county/state records disagree"):
                washington.reconcile(facts)

    def test_missing_counts_and_unit_accounting_changes_fail(self):
        for field, value in (("ballotsCast", None), ("voterRegistration", True),
                             ("voterTurnout", 1)):
            facts = copy.deepcopy(self.facts)
            facts["counties"][0]["voterTurnout"][0][field] = value
            with self.assertRaisesRegex(ValueError, "invalid native|accounting disagrees"):
                washington.reconcile(facts)

    def test_king_exception_does_not_allow_other_ballot_gaps(self):
        unit = self.facts["counties"][0]["voterTurnout"][0]
        unit["ballotsCast"] += 1
        unit["voterTurnout"] += 1
        with self.assertRaisesRegex(ValueError, "Unreviewed.*discrepancy"):
            washington.reconcile(self.facts)

    def test_duplicate_counties_and_units_are_not_silently_deduplicated(self):
        for kind in ("county", "unit"):
            facts = copy.deepcopy(self.facts)
            if kind == "county":
                facts["counties"][-1] = facts["counties"][0]
            else:
                facts["counties"][0]["voterTurnout"][-1]["id"] = facts[
                    "counties"][0]["voterTurnout"][0]["id"]
            with self.assertRaisesRegex(ValueError, "duplicated"):
                washington.reconcile(facts)

    def test_primary_or_certified_status_cannot_be_substituted(self):
        for field in ("isPrimary", "isOfficialResults"):
            facts = copy.deepcopy(self.facts)
            facts["counties"][0]["election"][field] = True
            with self.assertRaisesRegex(ValueError, "election or native status"):
                washington.reconcile(facts)

    def test_distinct_native_timestamps_survive_without_timezone_invention(self):
        rows, _, _ = washington.reconcile(self.facts)
        for row, native in zip(rows, self.facts["counties"]):
            self.assertEqual(row["source_as_of"], native["election"]["asOf"])
            self.assertEqual(row["source_last_updated"], native["election"]["lastUpdated"])
            self.assertEqual(row["source_publish_date"], native["election"]["publishDate"])
        self.assertTrue(any(row["source_as_of"] != row["state_locality_source_as_of"]
                            for row in rows))

    def test_offline_package_reproduces_every_byte(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "facts"
            washington.build(self.facts, output)
            self.assertEqual({path.name for path in output.iterdir()},
                             {path.name for path in PACKAGE.iterdir()})
            for path in output.iterdir():
                self.assertEqual(path.read_bytes(), (PACKAGE / path.name).read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()

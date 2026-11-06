import copy
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data/county-source-reviews/20261106-oregon-participation-01"
SPEC = importlib.util.spec_from_file_location("oregon_review", ROOT / "scripts/review-oregon-county-participation.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class OregonParticipationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def test_complete_portable_reproduction_matches_every_file_and_zip_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "reproduced"
            subprocess.run([sys.executable, "-S", str(PACKAGE / "review-oregon-county-participation.py"),
                "--facts", str(PACKAGE / "source-records.json.gz"), "--output", str(output)],
                check=True, stdout=subprocess.PIPE)
            self.assertEqual({p.name for p in output.iterdir()}, {p.name for p in PACKAGE.iterdir()})
            for path in PACKAGE.iterdir():
                self.assertEqual((output / path.name).read_bytes(), path.read_bytes(), path.name)
            with zipfile.ZipFile(output / "complete-oregon-county-participation-01.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), {p.name for p in PACKAGE.iterdir() if p.suffix != ".zip"})
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (PACKAGE / name).read_bytes())

    def test_all_native_fields_and_positive_ballots_survive_false_reporting_flags(self):
        rows, headers, audit = REVIEW.reconcile(self.facts)
        originals = json.loads(self.facts["original_county_response"])["d"]
        self.assertEqual((len(rows), audit["ballots_counted"], audit["active_registered_voters"]),
                         (36, 1760007, 3109086))
        with (PACKAGE / "county-participation.csv").open() as source:
            saved = list(csv.DictReader(source))
        self.assertEqual(len(saved), 36)
        for row, record, distributed in zip(rows, originals, saved):
            self.assertEqual(json.loads(row["native_record_json"]), record)
            self.assertEqual(json.loads(distributed["native_record_json"]), record)
            self.assertEqual(int(distributed["ballots_counted"]), record["calcVoterTurnout"])
            self.assertEqual(int(distributed["active_registered_voters"]), record["Voters"])
            self.assertGreater(row["ballots_counted"], 0)
            self.assertFalse(record["IsReported"])
            self.assertEqual(record["CountyPercent"], 0)
        self.assertEqual(audit["false_native_reporting_flags"], 36)
        self.assertTrue(all(header["source_updated_at"] == "11/5/2026 | 8:30 PM PT" for header in headers))
        self.assertFalse(audit["maps_approved"])
        self.assertFalse(audit["demographic_rates_approved"])

    def test_rejects_missing_duplicate_or_misidentified_counties(self):
        for mutate in (
                lambda rows: rows.pop(),
                lambda rows: rows.__setitem__(1, rows[0].copy()),
                lambda rows: rows[0].update(CountyName="Wrong county"),
                lambda rows: rows[0].update(PrecinctName="One precinct")):
            facts = copy.deepcopy(self.facts)
            records = json.loads(facts["original_county_response"])
            mutate(records["d"])
            facts["original_county_response"] = json.dumps(records)
            with self.assertRaises(ValueError):
                REVIEW.reconcile(facts)
        facts = copy.deepcopy(self.facts)
        facts["county_cards"][1] = facts["county_cards"][0].copy()
        with self.assertRaises(ValueError):
            REVIEW.reconcile(facts)

    def test_rejects_invalid_counts_and_independent_fraction_disagreement(self):
        for field, value in (("calcVoterTurnout", True), ("calcVoterTurnout", -1),
                ("Voters", "12852"), ("Voters", 0), ("calcVoterTurnout", 8318)):
            facts = copy.deepcopy(self.facts)
            records = json.loads(facts["original_county_response"])
            records["d"][0][field] = value
            facts["original_county_response"] = json.dumps(records)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                REVIEW.reconcile(facts)

    def test_rejects_wrong_election_status_rollup_or_chart_remainder(self):
        for field, value in (("election_date", "11/5/2024"), ("election_type", "Primary"),
                ("source_status_literal", "Official"), ("ballots_counted", 1760008),
                ("active_registered_voters", 3109087), ("native_hidden_remainder", 1349080),
                ("native_reported_percent", "0.00%"), ("source_updated_at", "11/5/2026 8:30 PM")):
            facts = copy.deepcopy(self.facts)
            facts["statewide_headers"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                REVIEW.reconcile(facts)

    def test_rejects_changed_complete_original_and_http_provenance(self):
        for mutate in (
                lambda facts: facts.update(original_county_response="{}"),
                lambda facts: facts["source_receipts"][0].update(status=403),
                lambda facts: facts["source_receipts"].pop()):
            facts = copy.deepcopy(self.facts)
            mutate(facts)
            with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ValueError):
                REVIEW.build(facts, Path(temporary) / "invalid")

    def test_refuses_overwrite_and_retains_both_independent_headers(self):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ValueError):
            REVIEW.build(self.facts, Path(temporary))
        with (PACKAGE / "statewide-observations.csv").open() as source:
            rows = list(csv.DictReader(source))
        self.assertEqual({row["source_file"] for row in rows},
                         {"official-index.html", "official-turnout.html"})
        self.assertTrue(all(int(row["native_hidden_remainder"]) + int(row["ballots_counted"])
                            == int(row["active_registered_voters"]) for row in rows))


if __name__ == "__main__":
    unittest.main()

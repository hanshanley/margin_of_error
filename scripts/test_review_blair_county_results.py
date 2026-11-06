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
PACKAGE = ROOT / "data/county-source-reviews/20261106-blair-facts-01"
SPEC = importlib.util.spec_from_file_location("blair", ROOT / "scripts/review-blair-county-results.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class BlairReviewTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def test_complete_native_scopes_and_count_vectors(self):
        REVIEW.validate(self.facts)
        current, zero = self.facts["reports"]
        self.assertEqual(REVIEW.counts(current["pages"][0]["participation"]["ballot_count_literals"]),
                         [43898, 35560, 8338, 0])
        self.assertEqual(REVIEW.counts(zero["pages"][0]["participation"]["ballot_count_literals"]), [0] * 4)
        self.assertEqual(sum(len(c["rows"]) for r in self.facts["reports"]
                             for p in r["pages"] for c in p["contests"]), 32)

    def test_complete_tables_keep_zero_report_and_candidate_results_separate(self):
        def table(name):
            with (PACKAGE / name).open() as source:
                return list(csv.DictReader(source))
        current, zero = table("county-participation.csv"), table("pre-election-zero-participation.csv")
        self.assertEqual(len(current), 1)
        self.assertEqual(len(zero), 1)
        self.assertEqual(current[0]["ballots_cast"], "43898")
        self.assertEqual(zero[0]["ballots_cast"], "0")
        self.assertEqual(current[0]["registered_voters"], "81846")
        self.assertEqual(current[0]["native_printed_turnout"], "53.63%")
        candidates = table("county-candidate-results.csv")
        house = [row for row in candidates if row["office_literal"] == "REPRESENTATIVE IN CONGRESS"]
        self.assertEqual(sum(int(row["Total"]) for row in house), 43749)
        self.assertEqual([row["party_literal"] for row in house], ["DEM", "REP", ""])
        self.assertEqual(len(candidates), 16)
        self.assertEqual(len(table("pre-election-zero-candidate-results.csv")), 16)
        accounting = table("county-contest-accounting.csv")
        self.assertEqual(len(accounting), 40)
        for row in accounting:
            self.assertEqual(row["native_under_or_overvote_classification"], "")
            self.assertEqual(row["native_contest_ballot_denominator"], "")
            if row["office_literal"] in REVIEW.OFFICES[3:]:
                self.assertEqual(row["unclassified_ballot_minus_selection_residual"], "")
                self.assertEqual(row["reviewed_county_ballots_for_whole_county_contest_only"], "")
        residual = next(row for row in accounting if row["office_literal"] == REVIEW.OFFICES[1]
                        and row["mode_literal"] == "Total" and row["source_report"] == "current")
        self.assertEqual(residual["unclassified_ballot_minus_selection_residual"], "149")

    def test_rejects_missing_or_merged_native_scope(self):
        for reports in (self.facts["reports"][:1], self.facts["reports"][::-1],
                        [self.facts["reports"][0]] * 2):
            facts = copy.deepcopy(self.facts)
            facts["reports"] = reports
            with self.assertRaisesRegex(ValueError, "report scope"):
                REVIEW.validate(facts)

    def test_rejects_arithmetic_and_consistent_but_changed_native_counts(self):
        for values in (["14,518", "9,755", "4,762", "0"], ["14,518", "9,756", "4,762", "0"]):
            facts = copy.deepcopy(self.facts)
            facts["reports"][0]["pages"][1]["contests"][1]["rows"][0]["count_literals"] = values
            with self.assertRaises(ValueError):
                REVIEW.validate(facts)

    def test_rejects_changed_reporting_time_or_zero_snapshot(self):
        for mutate in (
            lambda facts: facts["reports"][0]["pages"][0].update(source_update_literal="11/04/2026 10:45 PM"),
            lambda facts: facts["reports"][0]["pages"][0]["reporting"][0].update(reported_literal="92"),
            lambda facts: facts["reports"][1]["pages"][0]["participation"].update(
                ballot_count_literals=["1", "1", "0", "0"]),
        ):
            facts = copy.deepcopy(self.facts)
            mutate(facts)
            with self.assertRaises(ValueError):
                REVIEW.validate(facts)

    def test_rejects_changed_source_provenance(self):
        for field, value in (("sha256", "0" * 64), ("status", 403), ("bytes", 1),
                             ("url", REVIEW.INDEX), ("final_url", REVIEW.INDEX)):
            facts = copy.deepcopy(self.facts)
            facts["source_receipts"]["county-summary.pdf"][field] = value
            with self.assertRaisesRegex(ValueError, "source provenance"):
                REVIEW.validate(facts)

    def test_portable_offline_reproduction_matches_every_file_and_zip_member(self):
        with tempfile.TemporaryDirectory(prefix="blair-facts-") as directory:
            output = Path(directory) / "reproduced"
            subprocess.run([sys.executable, "-S", str(PACKAGE / "review-blair-county-results.py"),
                            "--facts", str(PACKAGE / "source-records.json.gz"), "--output", str(output)],
                           check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({p.name for p in output.iterdir()}, {p.name for p in PACKAGE.iterdir()})
            for path in PACKAGE.iterdir():
                self.assertEqual((output / path.name).read_bytes(), path.read_bytes(), path.name)
            with zipfile.ZipFile(output / "complete-blair-2026-numerical-facts-01.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(len(archive.namelist()), 13)
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (output / name).read_bytes())


if __name__ == "__main__":
    unittest.main()

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
PACKAGE = ROOT / "data/county-source-reviews/20261106-wayne-facts-01"
SPEC = importlib.util.spec_from_file_location("wayne", ROOT / "scripts/review-wayne-county-results.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class WayneReviewTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def table(self, name):
        with (PACKAGE / name).open() as source:
            return list(csv.DictReader(source))

    def test_county_header_is_not_a_contest_or_selection_count(self):
        REVIEW.validate(self.facts)
        county, = self.table("county-participation.csv")
        self.assertEqual(county["ballots_cast"], "21707")
        self.assertEqual(county["registered_voters"], "36885")
        self.assertEqual(county["native_printed_turnout"], "58.85%")
        self.assertEqual(county["native_participation_measure_literal"], "Total Ballots Cast")
        self.assertEqual(county["native_status_literal"], "")
        self.assertEqual(county["native_parent_status_literal"], REVIEW.PARENT_STATUS)
        self.assertEqual(county["precincts_reported"], county["precincts_total"])
        self.assertEqual(county["declared_timezone"], "")
        contests = self.table("native-contest-participation.csv")
        self.assertEqual(len(contests), 6)
        self.assertEqual(contests[0]["ballots_literal"], "21689")
        self.assertEqual(contests[1]["ballots_literal"], "21707")
        self.assertEqual(sum(int(row["ballots_literal"]) for row in contests[2:4]), 21689)
        self.assertEqual(sum(int(row["ballots_literal"]) for row in contests[4:]), 21689)

    def test_complete_choices_include_write_ins_once_without_invented_parties(self):
        choices = self.table("county-candidate-results.csv")
        self.assertEqual(len(choices), 19)
        self.assertEqual(sum(row["row_kind"] == "write_in" for row in choices), 6)
        self.assertTrue(all(row["party_literal"] == "" for row in choices))
        totals = self.table("native-contest-subtotals.csv")
        self.assertEqual(len(totals), 6)
        self.assertEqual(totals[0]["Total"], "21556")
        for subtotal in totals:
            selected = [row for row in choices if row["office_literal"] == subtotal["office_literal"]]
            for mode in REVIEW.MODES:
                self.assertEqual(sum(int(row[mode]) for row in selected), int(subtotal[mode]))
        self.assertEqual(choices[6]["PR"], "0")

    def test_native_accounting_preserves_header_gap_and_missing_mode_denominators(self):
        county, = self.table("county-participation.csv")
        for name in ("election_day_ballots", "mail_ballots", "provisional_ballots"):
            self.assertEqual(county[name], "")
        rows = self.table("county-contest-accounting.csv")
        self.assertEqual(len(rows), 24)
        totals = [row for row in rows if row["mode_literal"] == "Total"]
        self.assertEqual(totals[0]["unclassified_header_minus_contest_ballots"], "18")
        self.assertEqual(totals[1]["unclassified_header_minus_contest_ballots"], "0")
        self.assertEqual(totals[0]["native_overvotes"], "57")
        for row in totals:
            self.assertEqual(row["unclassified_contest_accounting_residual"], "0")
            self.assertEqual(int(row["native_contest_ballots"]),
                int(row["candidate_selections_including_write_in"])
                + int(row["native_overvotes"]) + int(row["native_undervotes"]))
        for row in rows:
            if row["mode_literal"] != "Total":
                for name in ("native_contest_ballots", "native_overvotes", "native_undervotes",
                             "unclassified_contest_accounting_residual"):
                    self.assertEqual(row[name], "")
            if row["office_literal"] in REVIEW.OFFICES[2:]:
                self.assertEqual(row["county_header_ballots_for_whole_county_scope_only"], "")
                self.assertEqual(row["unclassified_header_minus_contest_ballots"], "")

    def test_rejects_replaced_header_inferred_parties_and_missing_scope(self):
        for mutate in (
            lambda report: report.update(ballots_literal="21689"),
            lambda report: report.update(native_status_literal="Official"),
            lambda report: report.update(declared_timezone="Eastern"),
            lambda report: report["contests"][0]["rows"][0].update(party_literal="DEM"),
            lambda report: report["contests"].pop(),
        ):
            facts = copy.deepcopy(self.facts)
            mutate(facts["report"])
            with self.assertRaises(ValueError):
                REVIEW.validate(facts)

    def test_rejects_corrupted_or_incompletely_extracted_native_accounting(self):
        for mutate in (
            lambda report: report["contests"][0]["rows"][0].update(count_literals=["8975", "5608"]),
            lambda report: report["contests"][0]["rows"][0].update(count_literals=["8976", "5608", "3337", "30"]),
            lambda report: report["contests"][0].update(overvotes_literal="114"),
            lambda report: report["contests"][0].update(ballots_literal="21707"),
            lambda report: report.update(source_update_literal="2026-11-06 15:08:51"),
            lambda report: report["contests"][0]["rows"][0].update(printed_vote_percent_literal="41.65%"),
        ):
            facts = copy.deepcopy(self.facts)
            mutate(facts["report"])
            with self.assertRaises(ValueError):
                REVIEW.validate(facts)

    def test_rejects_changed_source_provenance(self):
        for field, value in (("sha256", "0" * 64), ("status", 404), ("bytes", 0),
                             ("url", REVIEW.INDEX), ("final_url", REVIEW.INDEX)):
            facts = copy.deepcopy(self.facts)
            facts["source_receipts"]["county-statement.pdf"][field] = value
            with self.assertRaisesRegex(ValueError, "source provenance"):
                REVIEW.validate(facts)

    def test_portable_offline_reproduction_matches_every_file_and_zip_member(self):
        with tempfile.TemporaryDirectory(prefix="wayne-facts-") as directory:
            output = Path(directory) / "reproduced"
            subprocess.run([sys.executable, "-S", str(PACKAGE / "review-wayne-county-results.py"),
                            "--facts", str(PACKAGE / "source-records.json.gz"), "--output", str(output)],
                           check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({path.name for path in output.iterdir()}, {path.name for path in PACKAGE.iterdir()})
            for path in PACKAGE.iterdir():
                self.assertEqual((output / path.name).read_bytes(), path.read_bytes(), path.name)
            with zipfile.ZipFile(output / "complete-wayne-2026-numerical-facts-01.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(len(archive.namelist()), 12)
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (output / name).read_bytes())


if __name__ == "__main__":
    unittest.main()

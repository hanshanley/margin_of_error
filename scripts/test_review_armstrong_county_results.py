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
PACKAGE = ROOT / "data/county-source-reviews/20261106-armstrong-facts-01"
SPEC = importlib.util.spec_from_file_location("armstrong", ROOT / "scripts/review-armstrong-county-results.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class ArmstrongReviewTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def table(self, name):
        with (PACKAGE / name).open() as source:
            return list(csv.DictReader(source))

    def test_native_participation_is_not_party_groups_or_candidate_votes(self):
        REVIEW.validate(self.facts)
        county, = self.table("county-participation.csv")
        self.assertEqual(county["native_participation_measure_literal"], "Voters Cast")
        self.assertEqual(county["reported_voters_cast"], "24039")
        self.assertEqual(county["registered_voters"], "43750")
        self.assertEqual(county["native_printed_turnout"], "54.95%")
        self.assertEqual(county["provisional_voters_cast"], "")
        self.assertEqual(county["election_day_voters_cast"], "20853")
        self.assertEqual(county["mail_voters_cast"], "3186")
        groups = self.table("native-elector-group-participation.csv")
        self.assertEqual(len(groups), 9)
        for row in groups[:6]:
            self.assertEqual(row["voters_cast_literal"], "0")
            self.assertEqual(row["printed_turnout_literal"], "N/A")
            self.assertEqual(row["registered_voters_literal"],
                             "0" if row["counting_group_literal"] == "Total" else "")
        house = [row for row in self.table("county-candidate-results.csv")
                 if row["office_literal"] == REVIEW.OFFICES[1]]
        self.assertEqual(sum(int(row["Total"]) for row in house), 23935)
        self.assertEqual([row["party_literal"] for row in house], ["REP", "DEM", ""])

    def test_complete_native_rows_subtotals_and_party_vectors_stay_separate(self):
        candidates = self.table("county-candidate-results.csv")
        self.assertEqual(len(candidates), 13)
        self.assertEqual(sum(row["row_kind"] == "candidate" for row in candidates), 9)
        self.assertEqual(sum(row["row_kind"] == "unresolved_write_in" for row in candidates), 4)
        self.assertEqual(len(self.table("county-literal-party-totals.csv")), 36)
        subtotals = self.table("native-contest-subtotals.csv")
        self.assertEqual(len(subtotals), 4)
        governor = next(row for row in subtotals if row["office_literal"] == REVIEW.OFFICES[0])
        self.assertEqual(governor["Total"], "23951")
        self.assertEqual(sum(int(row["Total"]) for row in candidates
                             if row["office_literal"] == REVIEW.OFFICES[0]), 23978)

    def test_missing_provisional_and_district_denominators_remain_missing(self):
        accounting = self.table("county-contest-accounting.csv")
        self.assertEqual(len(accounting), 16)
        for row in accounting:
            self.assertEqual(row["native_contest_participation_denominator"], "")
            self.assertEqual(row["native_under_or_overvote_classification"], "")
            if row["mode_literal"] == "Provisional" or row["office_literal"] in REVIEW.OFFICES[2:]:
                self.assertEqual(row["reviewed_county_voters_cast_for_whole_county_scope_only"], "")
                self.assertEqual(row["unclassified_participation_minus_selection_residual"], "")
        residuals = {row["office_literal"]: row["unclassified_participation_minus_selection_residual"]
                     for row in accounting if row["mode_literal"] == "Total"}
        self.assertEqual(residuals[REVIEW.OFFICES[0]], "61")
        self.assertEqual(residuals[REVIEW.OFFICES[1]], "104")

    def test_rejects_missing_or_changed_native_participation_scope(self):
        for mutate in (
            lambda report: report.update(native_status_literal="Official Results"),
            lambda report: report.update(native_summary_scope_literal=REVIEW.SUMMARY + ", Provisional"),
            lambda report: report["pages"][0]["elector_group_participation"][0].update(
                registered_voters_literal="0"),
            lambda report: report["pages"][0]["elector_group_participation"][2].update(
                printed_turnout_literal="0.00%"),
            lambda report: report["pages"][0]["elector_group_participation"].pop(),
        ):
            facts = copy.deepcopy(self.facts)
            mutate(facts["report"])
            with self.assertRaises(ValueError):
                REVIEW.validate(facts)

    def test_rejects_incomplete_vectors_or_consistently_changed_native_data(self):
        for mutate in (
            lambda report: report["pages"][0]["contests"][0]["rows"][0].update(
                count_literals=["14,483", "918", "0"]),
            lambda report: report["pages"][0]["contests"][0]["rows"][0].update(
                count_literals=["14,483", "918", "0", "15,402"]),
            lambda report: report["pages"][0]["contests"][0]["rows"][-1].update(
                count_literals=["23", "5", "0", "28"]),
            lambda report: report["pages"][1].update(source_update_literal="11/4/2026 10:26:30 PM"),
            lambda report: report["pages"][1]["contests"].pop(),
        ):
            facts = copy.deepcopy(self.facts)
            mutate(facts["report"])
            with self.assertRaises(ValueError):
                REVIEW.validate(facts)

    def test_rejects_changed_source_provenance(self):
        for field, value in (("sha256", "0" * 64), ("status", 403), ("bytes", 1),
                             ("url", REVIEW.INDEX), ("final_url", REVIEW.INDEX)):
            facts = copy.deepcopy(self.facts)
            facts["source_receipts"]["county-totals.pdf"][field] = value
            with self.assertRaisesRegex(ValueError, "source provenance"):
                REVIEW.validate(facts)

    def test_portable_offline_reproduction_matches_every_file_and_zip_member(self):
        with tempfile.TemporaryDirectory(prefix="armstrong-facts-") as directory:
            output = Path(directory) / "reproduced"
            subprocess.run([sys.executable, "-S", str(PACKAGE / "review-armstrong-county-results.py"),
                            "--facts", str(PACKAGE / "source-records.json.gz"), "--output", str(output)],
                           check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({path.name for path in output.iterdir()}, {path.name for path in PACKAGE.iterdir()})
            for path in PACKAGE.iterdir():
                self.assertEqual((output / path.name).read_bytes(), path.read_bytes(), path.name)
            with zipfile.ZipFile(output / "complete-armstrong-2026-numerical-facts-01.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(len(archive.namelist()), 12)
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (output / name).read_bytes())


if __name__ == "__main__":
    unittest.main()

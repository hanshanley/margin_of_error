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
PACKAGE = ROOT / "data/county-source-reviews/20261106-lebanon-facts-01"
SCRIPT = ROOT / "scripts/review-lebanon-county-results.py"
SPEC = importlib.util.spec_from_file_location("lebanon", SCRIPT)
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


class LebanonReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def rejected(self, mutate):
        facts = copy.deepcopy(self.facts)
        mutate(facts)
        with self.assertRaises((ValueError, KeyError)):
            review.validate(facts)

    def test_complete_native_rows_are_preserved_without_double_counting_writeins(self):
        review.validate(self.facts)
        for kind, filename in [("county", "county-candidate-results.csv"),
                               ("unit", "native-unit-candidate-results.csv")]:
            expected = []
            report = next(row for row in self.facts["reports"] if row["kind"] == kind)
            for page in report["pages"]:
                for contest in page["contests"]:
                    for row in contest["rows"]:
                        if row["label_literal"] != "Contest Totals":
                            expected.append((page["unit"], contest["office_literal"],
                                row["label_literal"], row["count_literals"]))
            with (PACKAGE / filename).open() as source:
                actual = [(row["native_unit"], row["office_literal"], row["label_literal"],
                           json.loads(row["native_count_literals_json"])) for row in csv.DictReader(source)]
            self.assertEqual(actual, expected)
        with (PACKAGE / "county-contest-accounting.csv").open() as source:
            house = next(row for row in csv.DictReader(source) if row["office_literal"] == review.OFFICES[1]
                         and row["mode_literal"] == "Total")
        self.assertEqual(int(house["candidate_selections_including_write_in_total"]), 51061)
        self.assertEqual(int(house["unclassified_ballot_minus_selection_residual"]), 207)
        self.assertEqual(house["native_under_or_overvote_classification"], "")

    def test_positive_ballots_do_not_make_native_zero_registration_or_printed_rate_usable(self):
        for filename, size in [("county-participation.csv", 1), ("native-unit-participation.csv", 60)]:
            with (PACKAGE / filename).open() as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(len(rows), size)
            for row in rows:
                self.assertGreater(int(row["ballots_cast"]), 0)
                self.assertEqual(row["native_registered_voters"], "0")
                self.assertEqual(row["native_printed_turnout"], "0.00%")
                self.assertEqual(row["registered_voters"], "")
                self.assertEqual(row["registered_turnout_percent"], "")
                self.assertEqual(row["provisional_ballots"], "0")
                self.assertEqual(row["declared_timezone"], "")
                self.assertEqual(row["native_status_literal"], "UNOFFICIAL RESULTS")
        self.assertEqual(self.facts["index_observation"]["pending_provisionals_literal"], "268")

    def test_missing_duplicate_reordered_and_changed_election_pages_fail_closed(self):
        self.rejected(lambda f: f["reports"][1]["pages"].pop())
        self.rejected(lambda f: f["reports"][1]["pages"].__setitem__(1, f["reports"][1]["pages"][0]))
        for field, value in [("native_status_literal", "OFFICIAL RESULTS"),
                             ("source_update_literal", "11/05/2026 12:16 PM"),
                             ("native_county_label", "Lebanon County")]:
            self.rejected(lambda f, k=field, v=value: f["reports"][1]["pages"][0].__setitem__(k, v))

    def test_missing_zero_or_inconsistent_ballot_counts_and_denominators_are_rejected(self):
        for value in ["", "1", None, 0]:
            self.rejected(lambda f, v=value: f["reports"][0]["pages"][0]["participation"].__setitem__(
                "registered_voters_literal", v))
        for value in ["", None, -1, "1.5"]:
            self.rejected(lambda f, v=value: f["reports"][1]["pages"][0]["participation"][
                "ballot_count_literals"].__setitem__(0, v))
        def inconsistent(facts):
            values = facts["reports"][1]["pages"][0]["participation"]["ballot_count_literals"]
            values[0], values[1] = "317", "271"
        self.rejected(inconsistent)

    def test_candidate_or_writein_changes_and_duplicate_offices_are_rejected(self):
        def changed(facts):
            row = facts["reports"][1]["pages"][0]["contests"][0]["rows"][0]["count_literals"]
            row[0], row[1] = str(review.integer(row[0]) + 1), str(review.integer(row[1]) + 1)
        self.rejected(changed)
        self.rejected(lambda f: f["reports"][1]["pages"][0]["contests"].append(
            copy.deepcopy(f["reports"][1]["pages"][0]["contests"][0])))
        self.rejected(lambda f: f["reports"][0]["pages"][1]["contests"][0]["rows"].pop())

    def test_reporting_pending_provisional_and_complete_primary_provenance_are_required(self):
        self.rejected(lambda f: f["reports"][0]["pages"][0]["reporting"][1].__setitem__("reported_literal", "60"))
        self.rejected(lambda f: f["index_observation"].__setitem__("pending_provisionals_literal", "0"))
        self.rejected(lambda f: f["source_receipts"].pop("official-index.html"))
        self.rejected(lambda f: f["source_receipts"]["county-summary.pdf"].__setitem__("sha256", "0"*64))

    def test_portable_offline_reproduction_matches_all_files_and_complete_zip_members(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "rebuilt"
            subprocess.run([sys.executable, "-S", str(SCRIPT), "--facts",
                str(PACKAGE / "source-records.json.gz"), "--output", str(target)],
                check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({p.name for p in target.iterdir()}, {p.name for p in PACKAGE.iterdir()})
            for original in PACKAGE.iterdir():
                self.assertEqual((target / original.name).read_bytes(), original.read_bytes(), original.name)
            archive_path = target / "complete-lebanon-2026-numerical-facts-01.zip"
            with zipfile.ZipFile(archive_path) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), {p.name for p in PACKAGE.iterdir() if p.suffix != ".zip"})
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (PACKAGE / name).read_bytes())
            with self.assertRaises(FileExistsError):
                review.build(self.facts, target)


if __name__ == "__main__":
    unittest.main()

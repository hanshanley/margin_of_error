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
PACKAGE = ROOT / "data/county-source-reviews/20261106-lawrence-facts-01"
SCRIPT = ROOT / "scripts/review-lawrence-county-results.py"
SPEC = importlib.util.spec_from_file_location("lawrence", SCRIPT)
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


class LawrenceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def rows(self, name):
        with (PACKAGE / name).open() as source:
            return list(csv.DictReader(source))

    def rejected(self, mutate):
        facts = copy.deepcopy(self.facts)
        mutate(facts)
        with self.assertRaises((ValueError, KeyError)):
            review.validate(facts)

    def test_mail_only_is_not_added_to_county_or_promoted_to_all_mode_participation(self):
        county, = self.rows("county-participation.csv")
        mail, = self.rows("mail-only-participation.csv")
        units = self.rows("native-unit-participation.csv")
        self.assertEqual(len(units), 74)
        self.assertEqual(sum(int(r["ballots_cast"]) for r in units), int(county["ballots_cast"]))
        self.assertEqual(sum(int(r["registered_voters"]) for r in units), int(county["registered_voters"]))
        self.assertEqual(int(mail["ballots_cast"]), int(county["mail_ballots"]))
        self.assertNotEqual(mail["source_update_literal"], county["source_update_literal"])
        self.assertTrue(all(r["declared_timezone"] == "" for r in [county, mail, *units]))
        self.assertAlmostEqual(float(county["registered_turnout_percent"]), 100 * 31401 / 57470)
        reporting = self.rows("native-reporting-statements.csv")
        complete = next(r for r in reporting if r["source_report"] == "county"
                        and r["label_literal"] == "Precincts Complete")
        self.assertEqual(complete["reported_literal"], "0")

    def test_unit_rounding_conflicts_keep_native_counts_but_withhold_usable_rates(self):
        units = self.rows("native-unit-participation.csv")
        missing = {r["native_unit"] for r in units if r["registered_turnout_percent"] == ""}
        self.assertEqual(missing, {"New Castle 1-2", "Neshannock Twp 8"})
        for row in units:
            self.assertGreater(int(row["registered_voters"]), 0)
        checks = self.rows("native-turnout-checks.csv")
        self.assertEqual({r["native_unit"] for r in checks
                          if r["within_half_final_printed_decimal_point"] == "False"}, missing)

    def test_writein_details_and_accounting_do_not_inflate_candidate_votes(self):
        candidates = self.rows("native-candidate-results.csv")
        rows = [r for r in candidates if r["source_report"] == "county"
                and r["office_literal"] == review.OFFICES[0]]
        selected = sum(int(r["Total"]) for r in rows if r["row_kind"] != "write_in_detail")
        total = next(r for r in self.rows("native-contest-accounting.csv")
                     if r["source_report"] == "county" and r["office_literal"] == review.OFFICES[0])
        self.assertEqual(selected, int(total["Total"]))
        self.assertEqual(selected, 31247)
        self.assertLess(selected, 31401)
        self.assertTrue(any(r["row_kind"] == "write_in_detail" for r in rows))

    def test_partial_senate_district_is_not_given_the_whole_county_electorate(self):
        report = self.facts["reports"][2]
        units = {p["unit"]: review.counts(p["participation"]["ballot_count_literals"])[0]
                 for p in report["pages"] if p["participation"]}
        scopes = {}
        for page in report["pages"]:
            for contest in page["contests"]:
                scopes.setdefault(contest["office_literal"], set()).add(page["unit"])
        senate = scopes[review.OFFICES[2]]
        self.assertEqual(len(senate), 58)
        self.assertLess(sum(units[u] for u in senate), 31401)
        house_a, house_b = scopes[review.OFFICES[3]], scopes[review.OFFICES[4]]
        self.assertFalse(house_a & house_b)
        self.assertEqual(house_a | house_b, set(units))

    def test_missing_duplicate_changed_and_reordered_pages_fail_closed(self):
        self.rejected(lambda f: f["reports"][2]["pages"].pop())
        self.rejected(lambda f: f["reports"][2]["pages"].__setitem__(1, f["reports"][2]["pages"][0]))
        self.rejected(lambda f: f["reports"][1]["pages"][0].__setitem__(
            "source_update_literal", "11/03/2026 9:27 PM"))
        self.rejected(lambda f: f["reports"][0]["pages"][0].__setitem__("native_status_literal", "OFFICIAL RESULTS"))
        self.rejected(lambda f: f["source_receipts"]["lawrence-summary.pdf"].__setitem__("sha256", "0" * 64))

    def test_changed_ballots_candidate_vectors_or_overlapping_writeins_are_rejected(self):
        self.rejected(lambda f: f["reports"][0]["pages"][0]["participation"][
            "ballot_count_literals"].__setitem__(0, "37,509"))
        self.rejected(lambda f: f["reports"][2]["pages"][0]["participation"].__setitem__(
            "registered_voters_literal", "0"))
        self.rejected(lambda f: f["reports"][2]["pages"][0]["contests"][0]["rows"][0][
            "count_literals"].__setitem__(0, "113"))
        self.rejected(lambda f: f["reports"][0]["pages"][1]["contests"][0]["rows"].pop())
        self.rejected(lambda f: f["reports"][2]["pages"][0]["contests"].append(
            copy.deepcopy(f["reports"][2]["pages"][0]["contests"][0])))

    def test_portable_offline_reproduction_matches_all_files_and_archive_members(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "rebuilt"
            subprocess.run([sys.executable, "-S", str(SCRIPT), "--facts",
                str(PACKAGE / "source-records.json.gz"), "--output", str(target)],
                check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({p.name for p in target.iterdir()}, {p.name for p in PACKAGE.iterdir()})
            for original in PACKAGE.iterdir():
                self.assertEqual((target / original.name).read_bytes(), original.read_bytes(), original.name)
            with zipfile.ZipFile(target / "complete-lawrence-2026-numerical-facts-01.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), {p.name for p in PACKAGE.iterdir() if p.suffix != ".zip"})
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (PACKAGE / name).read_bytes())
            with self.assertRaises(FileExistsError):
                review.build(self.facts, target)


if __name__ == "__main__":
    unittest.main()

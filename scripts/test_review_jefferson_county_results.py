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
PACKAGE = ROOT / "data/county-source-reviews/20261106-jefferson-facts-01"
SPEC = importlib.util.spec_from_file_location("jefferson", ROOT / "scripts/review-jefferson-county-results.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class JeffersonReviewTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def table(self, name):
        with (PACKAGE / name).open() as source:
            return list(csv.DictReader(source))

    def test_participation_reconciles_without_substituting_votes_or_receipts(self):
        REVIEW.validate(self.facts)
        county, = self.table("county-participation.csv")
        self.assertEqual(county["native_participation_measure_literal"], "Voters Cast")
        self.assertEqual(county["reported_voters_cast"], "15205")
        self.assertEqual(county["registered_voters"], "28226")
        self.assertEqual(county["native_printed_turnout"], "53.87%")
        self.assertEqual(county["provisional_voters_cast"], "39")
        summary = self.table("native-summary-participation.csv")
        self.assertEqual([r["registered_voters_literal"] for r in summary], ["", "", "", "28,226"])
        receipt, = self.table("native-mail-ballot-receipts.csv")
        self.assertEqual(receipt["measure_kind"], "received_absentee_and_mail_in_ballots")
        self.assertEqual(receipt["count_literal"], "2114")
        self.assertEqual(receipt["counting_measure"], "False")
        candidates = self.table("county-candidate-results.csv")
        self.assertEqual(len(candidates), 13)
        self.assertEqual(len(self.table("county-literal-party-totals.csv")), 36)
        congress = [r for r in candidates if r["office_literal"] == REVIEW.OFFICES[1]]
        self.assertEqual(sum(int(r["Total"]) for r in congress), 15132)
        self.assertEqual([r["party_literal"] for r in congress], ["DEM", "REP", ""])

    def test_unit_scopes_and_cumulative_container_preserve_native_zeroes(self):
        rows = self.table("native-unit-participation.csv")
        self.assertEqual(len(rows), 156)
        actual = [r for r in rows if r["scope_kind"] == "native_reporting_unit" and r["mode_literal"] == "Total"]
        self.assertEqual(len(actual), 38)
        self.assertEqual(sum(int(r["voters_cast_literal"].replace(",", "")) for r in actual), 15205)
        self.assertEqual(sum(int(r["registered_voters_literal"].replace(",", "")) for r in actual), 28226)
        cumulative = [r for r in rows if r["scope_kind"] == "nongeographical_container"]
        self.assertEqual(len(cumulative), 4)
        self.assertTrue(all(r["unit_literal"] == "Cumulative" and r["voters_cast_literal"] == "0"
            and r["registered_voters_literal"] == "0" and r["printed_turnout_literal"] == "N/A" for r in cumulative))
        self.assertNotIn("unit_candidate_results", self.facts["query"]["statement"])
        self.assertTrue(self.facts["query"]["statement"]["pages"][7]["native_privacy_notice_present"])

    def test_contest_electorates_and_unclassified_residuals_stay_separate(self):
        rows = self.table("county-contest-accounting.csv")
        totals = {r["office_literal"]: r for r in rows if r["mode_literal"] == "Total"}
        self.assertEqual([totals[o]["native_times_cast"] for o in REVIEW.OFFICES],
                         ["15205", "15205", "15192", "13"])
        self.assertEqual([totals[o]["native_registered_voters"] for o in REVIEW.OFFICES],
                         ["28226", "28226", "28187", "39"])
        self.assertEqual([totals[o]["unclassified_participation_minus_selection_residual"]
                          for o in REVIEW.OFFICES], ["115", "73", "80", "0"])
        self.assertTrue(all(r["native_under_or_overvote_classification"] == "" for r in rows))
        footers = self.table("native-county-candidate-footers.csv")
        self.assertEqual(len(footers), 75)
        self.assertEqual(sum(r["scope_kind"] == "county" for r in footers), 50)
        pages = self.table("native-source-pages.csv")
        self.assertEqual(len(pages), 53)
        self.assertEqual({r["source_update_literal"] for r in pages},
                         {"11/4/2026 3:47:13 PM", "11/4/2026 3:47:52 PM"})
        self.assertTrue(all(r["declared_timezone"] == "" for r in pages))

    def test_rejects_missing_duplicate_invented_and_consistently_changed_facts(self):
        for mutate in (
            lambda q: q["statement"]["units"].pop(),
            lambda q: q["statement"]["units"].append(copy.deepcopy(q["statement"]["units"][0])),
            lambda q: q["statement"]["units"][-1]["participation"][0].update(printed_turnout_literal="0.00%"),
            lambda q: q["summary_pages"][0]["participation"][0].update(registered_voters_literal="28,226"),
            lambda q: q["summary_pages"][1]["contests"][-1]["rows"][-1].update(count_literals=["", "0", "0", "0"]),
            lambda q: q["summary_pages"][0]["contests"][0]["rows"][0].update(party_literal="DEMOCRATIC"),
            lambda q: q["statement"]["county_candidate_footers"].pop(),
            lambda q: q["summary_pages"][1]["contests"][-1].update(registered_voters_literal="28,226"),
            lambda q: q["statement"]["pages"][0].update(declared_timezone="Eastern"),
            lambda q: q["act88"].update(counting_measure=True),
        ):
            facts = copy.deepcopy(self.facts)
            mutate(facts["query"])
            with self.assertRaises(ValueError):
                REVIEW.validate(facts)
        facts = copy.deepcopy(self.facts)
        facts["source_receipts"][REVIEW.SUMMARY_FILE]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source provenance"):
            REVIEW.validate(facts)

    def test_offline_standard_library_reproduction_matches_every_file_and_member(self):
        with tempfile.TemporaryDirectory(prefix="jefferson-facts-") as directory:
            output = Path(directory) / "reproduced"
            subprocess.run([sys.executable, "-S", str(PACKAGE / "review-jefferson-county-results.py"),
                "--facts", str(PACKAGE / "source-records.json.gz"), "--output", str(output)],
                check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({p.name for p in output.iterdir()}, {p.name for p in PACKAGE.iterdir()})
            for path in PACKAGE.iterdir():
                self.assertEqual((output / path.name).read_bytes(), path.read_bytes(), path.name)
            with zipfile.ZipFile(output / "complete-jefferson-2026-county-query-01.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(len(archive.namelist()), 16)
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (output / name).read_bytes())


if __name__ == "__main__":
    unittest.main()

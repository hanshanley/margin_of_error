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
PACKAGE = ROOT / "data/county-source-reviews/20261106-huntingdon-facts-01"
SPEC = importlib.util.spec_from_file_location("huntingdon", ROOT / "scripts/review-huntingdon-county-results.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class HuntingdonReviewTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def table(self, name):
        with (PACKAGE / name).open() as source:
            return list(csv.DictReader(source))

    def test_participation_keeps_native_ballots_denominator_and_explicit_modes(self):
        REVIEW.validate(self.facts)
        county, = self.table("county-participation.csv")
        self.assertEqual([county[k] for k in ("ballots_cast", "registered_voters",
            "election_day_ballots", "mail_ballots", "provisional_ballots", "blank_ballots")],
            ["16024", "27917", "13855", "2169", "0", "0"])
        self.assertEqual(county["native_printed_turnout"], "57.40%")
        self.assertAlmostEqual(float(county["registered_turnout_percent"]), 100 * 16024 / 27917)
        self.assertEqual(county["source_fips"], "")
        self.assertIn("Primary-Election", county["source_url"])
        self.assertEqual(county["election_date"], "2026-11-03")

    def test_complete_candidates_and_literal_parties_do_not_become_participation(self):
        candidates = self.table("native-candidate-results.csv")
        self.assertEqual(len(candidates), 16)
        self.assertEqual(len(self.table("native-contest-accounting.csv")), 10)
        self.assertEqual(len(self.table("county-literal-party-totals.csv")), 44)
        congress = [r for r in candidates if r["office_literal"] == REVIEW.OFFICES[1]]
        self.assertEqual(sum(int(r["Total"]) for r in congress), 15948)
        self.assertEqual([r["party_literal"] for r in congress], ["DEM", "REP", ""])
        self.assertTrue(all(r["party_literal"] == "" for r in candidates if r["row_kind"] == "write_in_total"))
        scopes = self.table("county-contest-accounting.csv")
        totals = [r for r in scopes if r["mode_literal"] == "Total"]
        self.assertEqual([r["derived_contest_ballots"] for r in totals],
            ["16024", "16024", "16024", "1141", "14883"])
        self.assertEqual([r["matches_county_ballot_vector"] for r in totals],
            ["True", "True", "True", "False", "False"])
        self.assertTrue(all(r["district_registered_voters"] == ""
            and r["geographic_partition_verified"] == "False" for r in scopes))

    def test_native_clock_and_complete_reporting_do_not_imply_certification(self):
        pages = self.table("native-source-pages.csv")
        self.assertEqual(len(pages), 2)
        self.assertTrue(all(p["source_update_literal"] == "11/03/2026 9:56 PM"
            and p["declared_timezone"] == "" and p["native_status_literal"] == "UNOFFICIAL RESULTS"
            for p in pages))
        rows = self.table("native-reporting-statements.csv")
        self.assertEqual([r["reported_literal"] for r in rows], ["58", "58", "0", "58"])
        audit = json.loads((PACKAGE / "audit.json").read_text())
        self.assertFalse(audit["maps_approved"])
        self.assertFalse(audit["demographic_turnout_approved"])

    def test_missing_duplicate_invented_and_consistently_changed_facts_are_rejected(self):
        for mutate in (
            lambda f: f["pages"].pop(),
            lambda f: f["pages"][1]["contests"].pop(),
            lambda f: f["pages"][1]["contests"][0]["rows"].pop(),
            lambda f: f["pages"][1]["contests"][0]["rows"].append(
                copy.deepcopy(f["pages"][1]["contests"][0]["rows"][0])),
            lambda f: f["pages"][0]["participation"]["ballot_count_literals"].pop(),
            lambda f: f["pages"][0].update(declared_timezone="Eastern"),
            lambda f: f["pages"][0].update(native_status_literal="CERTIFIED"),
            lambda f: f["source_receipts"]["summary.pdf"].update(chain_verified=False),
            lambda f: f["source_receipts"]["summary.pdf"].update(sha256="0" * 64),
        ):
            facts = copy.deepcopy(self.facts)
            mutate(facts)
            with self.assertRaises(ValueError):
                REVIEW.validate(facts)
        facts = copy.deepcopy(self.facts)
        rows = facts["pages"][1]["contests"][0]["rows"]
        rows[0]["count_literals"][:2] = ["5,087", "3,659"]
        rows[1]["count_literals"][:2] = ["10,612", "9,905"]
        with self.assertRaisesRegex(ValueError, "reviewed two-engine"):
            REVIEW.validate(facts)

    def test_entire_extracted_query_reproduces_offline_byte_for_byte(self):
        with tempfile.TemporaryDirectory(prefix="huntingdon-facts-") as directory:
            extracted = Path(directory) / "extracted"
            with zipfile.ZipFile(PACKAGE / "complete-huntingdon-2026-numerical-facts-01.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(len(archive.namelist()), 12)
                archive.extractall(extracted)
            output = Path(directory) / "reproduced"
            subprocess.run([sys.executable, "-S", str(extracted / "review-huntingdon-county-results.py"),
                "--facts", str(extracted / "source-records.json.gz"), "--output", str(output)],
                check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({p.name for p in output.iterdir()}, {p.name for p in PACKAGE.iterdir()})
            for path in PACKAGE.iterdir():
                self.assertEqual((output / path.name).read_bytes(), path.read_bytes(), path.name)

    def test_existing_output_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="huntingdon-existing-") as directory:
            output = Path(directory) / "existing"
            output.mkdir()
            sentinel = output / "retained"
            sentinel.write_bytes(b"untouched")
            with self.assertRaises(FileExistsError):
                REVIEW.build(self.facts, output)
            self.assertEqual(sentinel.read_bytes(), b"untouched")
            self.assertEqual(list(output.iterdir()), [sentinel])


if __name__ == "__main__":
    unittest.main()

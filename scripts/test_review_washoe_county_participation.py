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
PACKAGE = ROOT / "data/county-source-reviews/20261106-washoe-participation-01"
SPEC = importlib.util.spec_from_file_location("washoe_review", ROOT / "scripts/review-washoe-county-participation.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class WashoeParticipationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def test_complete_portable_reproduction_matches_every_distributed_byte(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "reproduced"
            subprocess.run([sys.executable, "-S", str(PACKAGE / "review-washoe-county-participation.py"),
                "--facts", str(PACKAGE / "source-records.json.gz"), "--output", str(output)],
                check=True, stdout=subprocess.PIPE)
            self.assertEqual({path.name for path in output.iterdir()}, {path.name for path in PACKAGE.iterdir()})
            for path in PACKAGE.iterdir():
                self.assertEqual((output / path.name).read_bytes(), path.read_bytes(), path.name)
            with zipfile.ZipFile(output / "complete-washoe-county-participation-01.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), {path.name for path in PACKAGE.iterdir() if path.suffix != ".zip"})
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (PACKAGE / name).read_bytes())

    def test_native_participation_and_zero_modes_are_not_candidate_votes(self):
        rows, modes, candidates, audit = REVIEW.parse_pages(self.facts["page_texts"])
        self.assertEqual((rows[0]["ballots_cast"], rows[0]["registered_voters"]), (191830, 329777))
        self.assertEqual([row["ballots"] for row in modes], [54762, 35133, 101935, 0, 0, 0])
        self.assertTrue(all(row["denominator_scope"] == "entire_county_not_mode_registration" for row in modes))
        self.assertEqual(sum(row["candidate_votes"] for row in candidates), 189752)
        self.assertEqual(audit["house_party_votes"], {"DEM": 111162, "IAP": 8325, "REP": 70265})
        self.assertEqual(audit["house_candidate_votes"] + audit["house_undervotes"] + audit["house_overvotes"],
                         audit["ballots"])
        self.assertEqual(rows[0]["source_generated_at"], "11/4/2026 6:13:35 PM")
        self.assertEqual(rows[0]["source_status_literal"], "REPORT 6 - UNOFFICIAL RESULTS")
        self.assertEqual(rows[0]["native_reported_percent"], "58.17%")
        self.assertFalse(audit["maps_approved"])
        self.assertFalse(audit["statewide_completion_approved"])

    def test_rejects_missing_pages_and_wrong_election_or_scope(self):
        with self.assertRaises(ValueError):
            REVIEW.parse_pages(self.facts["page_texts"][:-1])
        for original, replacement in (("WASHOE COUNTY", "CLARK COUNTY"),
                ("General Election", "Primary Election"), ("November 03, 2026", "November 05, 2024"),
                ("REPORT 6 - UNOFFICIAL RESULTS", "REPORT 6 - OFFICIAL RESULTS"),
                ("All Districts", "One District"), ("6:13:35 PM", "6:20:00 PM")):
            pages = self.facts["page_texts"].copy()
            pages[0] = pages[0].replace(original, replacement)
            with self.subTest(original=original), self.assertRaises(ValueError):
                REVIEW.parse_pages(pages)

    def test_rejects_independent_mode_and_times_cast_discrepancies(self):
        for page, original, replacement in (
                (0, "Early Vote\n54,762\n16.61%", "Early Vote\n54,763\n16.61%"),
                (22, "191,830 / 329,777", "191,829 / 329,777")):
            pages = self.facts["page_texts"].copy()
            self.assertIn(original, pages[page])
            pages[page] = pages[page].replace(original, replacement, 1)
            with self.subTest(page=page), self.assertRaises(ValueError):
                REVIEW.parse_pages(pages)

    def test_rejects_candidate_identity_and_under_over_discrepancies(self):
        for original, replacement in (
                ("269\n350\n1,335", "270\n350\n1,335"),
                ("Chapman, Lynn", "Missing native candidate"),
                ("111,162\n58.58%", "111,163\n58.58%")):
            pages = self.facts["page_texts"].copy()
            self.assertIn(original, pages[0])
            pages[0] = pages[0].replace(original, replacement, 1)
            with self.subTest(original=original), self.assertRaises(ValueError):
                REVIEW.parse_pages(pages)

    def test_rejects_changed_original_receipt_and_numerical_text(self):
        mutations = (
            lambda facts: facts.update(input_pdf_sha256="not the complete original PDF digest"),
            lambda facts: facts["source_receipt"].update(status=404),
            lambda facts: facts["page_texts"].__setitem__(22, "changed source text"),
        )
        for mutate in mutations:
            facts = copy.deepcopy(self.facts)
            mutate(facts)
            with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ValueError):
                REVIEW.build(facts, Path(temporary) / "invalid")

    def test_refuses_overwrite_and_retains_complete_native_tables(self):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ValueError):
            REVIEW.build(self.facts, Path(temporary))
        with (PACKAGE / "counting-group-participation.csv").open() as source:
            self.assertEqual(len(list(csv.DictReader(source))), 6)
        with (PACKAGE / "house-candidate-votes.csv").open() as source:
            self.assertEqual(len(list(csv.DictReader(source))), 3)


if __name__ == "__main__":
    unittest.main()

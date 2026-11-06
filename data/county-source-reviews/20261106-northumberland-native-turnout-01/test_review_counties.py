import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("county_query", HERE / "review-counties.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
INPUTS = json.loads((HERE / "source-inputs.json").read_text())


def signed(inputs):
    inputs["numeric_pages_sha256"] = hashlib.sha256(
        json.dumps(inputs["extractions"], ensure_ascii=True, sort_keys=True).encode()).hexdigest()
    return inputs


class NorthumberlandQueryTest(unittest.TestCase):
    def test_native_participation_modes_blank_ballots_and_missing_cells(self):
        parsed = module.review(INPUTS)
        county = parsed["county"][0]
        self.assertEqual((county["ballots_cast"], county["registered_voters"],
                          county["native_turnout_pct"], county["blank_ballots"]),
                         (28341, 55540, "51.03", 28))
        self.assertEqual([row["ballots_cast"] for row in parsed["modes"]], [28341, 24393, 3948, 0])
        self.assertEqual([row["blank_ballots"] for row in parsed["modes"]], [28, 28, 0, 0])
        self.assertTrue(all(row["registered_voters"] is None and row["native_turnout_pct"] is None
                            for row in parsed["modes"][1:]))

    def test_all_candidates_options_and_literal_parties(self):
        candidates = module.review(INPUTS)["candidates"]
        self.assertEqual(len(candidates), 23)
        self.assertEqual([row["native_party"] for row in candidates[:4]], ["DEM", "REP", "LIB", None])
        self.assertEqual([row["total"] for row in candidates[:4]], [11648, 15953, 521, 32])
        self.assertEqual(sum(row["native_party"] is None for row in candidates), 14)
        self.assertEqual(sum(row["is_write_in"] for row in candidates), 5)
        self.assertEqual([row["candidate_or_option"] for row in candidates if row["is_referendum_option"]],
                         ["Yes", "No"])
        self.assertTrue(all(row["native_pct"] is None for row in candidates))

    def test_vote_for_seven_and_unclassified_residuals_are_not_ballots(self):
        parsed = module.review(INPUTS)
        self.assertEqual([row["unclassified_residual"] for row in parsed["contests"]],
                         [187, 235, 178, 126, 41, 3862])
        commission = parsed["contests"][-1]
        self.assertEqual((commission["vote_for"], commission["native_contest_totals"],
                          commission["native_total_votes_cast"]), (7, 9450, 5588))
        self.assertTrue(all(row["native_undervotes"] is None and row["native_overvotes"] is None
                            for row in parsed["accounting"]))
        self.assertTrue(all(row["native_ballots_cast"] is None and row["native_registered_voters"] is None
                            for row in parsed["scopes"]))
        self.assertEqual(parsed["county"][0]["ballots_cast"], 28341)

    def test_native_clock_reporting_scope_and_approval_missingness(self):
        parsed = module.review(INPUTS)
        self.assertEqual([row["native_report_clock"] for row in parsed["pages"]],
                         ["11/03/2026 22:18 PM"] * 3)
        self.assertTrue(all(row["native_timezone"] is None for row in parsed["pages"]))
        self.assertEqual([(row["reported"], row["total"]) for row in parsed["reporting"]],
                         [(74, 74), (74, 74), (0, 74), (74, 74)])
        self.assertEqual(parsed["reporting"][-1]["mail_absentee"], 74)
        county = parsed["county"][0]
        self.assertIsNone(county["native_fips"])
        self.assertFalse(county["map_approved"])
        self.assertFalse(county["analysis_rate_approved"])

    def test_missing_page_header_or_different_native_clock_is_rejected(self):
        for operation in ("missing", "year", "clock", "page"):
            altered = copy.deepcopy(INPUTS)
            if operation == "missing":
                altered["extractions"]["pymupdf"].pop()
            else:
                before, after = {"year": ("2026 General Election", "2024 General Election"),
                    "clock": ("22:18 PM", "22:19 PM"), "page": ("Page 2 of 3", "Page 3 of 3")}[operation]
                altered["extractions"]["pymupdf"][1] = altered["extractions"]["pymupdf"][1].replace(before, after)
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                module.review(signed(altered))

    def test_complete_extraction_hash_and_native_vector_changes_are_rejected(self):
        altered = copy.deepcopy(INPUTS)
        altered["extractions"]["pymupdf"][0] += "\nchanged"
        with self.assertRaises(ValueError):
            module.review(altered)
        for before, after in (("24,393", "24,394"), ("55,540", "55,541")):
            altered = copy.deepcopy(INPUTS)
            altered["extractions"]["pdfplumber"][0] = altered["extractions"]["pdfplumber"][0].replace(before, after)
            with self.subTest(before=before), self.assertRaises(ValueError):
                module.review(signed(altered))

    def test_candidate_duplicate_invented_party_and_multi_vote_changes_rejected(self):
        for page, before, after in ((1, "STACY GARRITY", "JOSH SHAPIRO"),
                (2, "DANIELLE HINKLE", "DEM DANIELLE HINKLE"), (2, "Vote For 7", "Vote For 1"),
                (1, "15,953", "15,954")):
            altered = copy.deepcopy(INPUTS)
            if before == "STACY GARRITY":
                before, after = "STACY GARRITY, Governor", "JOSH SHAPIRO, Governor"
            altered["extractions"]["pdfplumber"][page] = altered["extractions"]["pdfplumber"][page].replace(before, after)
            with self.subTest(before=before), self.assertRaises(ValueError):
                module.review(signed(altered))

    def test_exact_original_receipt_and_source_declaration(self):
        provenance = json.loads((HERE / "source-provenance.json").read_text())
        receipt = provenance["pdf_receipt"]
        self.assertEqual((receipt["status"], receipt["bytes"]), (200, 38693))
        self.assertEqual(receipt["sha256"], INPUTS["source_pdf_sha256"])
        self.assertTrue(receipt["verified_tls"])
        self.assertEqual(receipt["redirects"][0]["status"], 301)
        self.assertTrue(provenance["declaration"]["literal_href"].endswith("/2026_1103_unofficial/overall7.pdf"))
        self.assertEqual(provenance["visually_reviewed_physical_pages"], [1, 2, 3])

    def test_actual_complete_archive_and_isolated_full_reproduction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, extracted, output = root / "original", root / "extracted", root / "output"
            module.build(original)
            with zipfile.ZipFile(original / "complete-query.zip") as archive:
                self.assertEqual(len(archive.namelist()), 15)
                self.assertNotIn("complete-query.zip", archive.namelist())
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (HERE / name).read_bytes(), name)
                archive.extractall(extracted)
            manifest = json.loads((extracted / "checksums.json").read_text())
            self.assertEqual(len(manifest), 14)
            for name, receipt in manifest.items():
                body = (extracted / name).read_bytes()
                self.assertEqual(len(body), receipt["bytes"])
                self.assertEqual(hashlib.sha256(body).hexdigest(), receipt["sha256"])
            subprocess.run(["python3", "-B", "-I", str(extracted / "review-counties.py"),
                            "--output", str(output)], check=True, capture_output=True)
            expected = {path.name for path in extracted.iterdir()} | {"complete-query.zip"}
            self.assertEqual({path.name for path in output.iterdir()}, expected)
            self.assertEqual(len(expected), 16)
            for name in expected:
                self.assertEqual((output / name).read_bytes(), (original / name).read_bytes(), name)

    def test_refuses_to_mutate_existing_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                module.build(Path(temporary))


if __name__ == "__main__":
    unittest.main()

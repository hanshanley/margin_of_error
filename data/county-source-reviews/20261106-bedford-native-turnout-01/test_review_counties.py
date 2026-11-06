import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bedford_query", HERE / "review-counties.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
INPUTS = json.loads((HERE / "source-inputs.json").read_text())


def resign(inputs):
    inputs["numeric_pages_sha256"] = hashlib.sha256(
        json.dumps(inputs["extractions"], ensure_ascii=True, sort_keys=True).encode()).hexdigest()
    return inputs


class BedfordQueryTest(unittest.TestCase):
    def test_native_participation_and_all_modes(self):
        result = module.review(INPUTS)
        self.assertEqual([(r["voters_cast"], r["registered_voters"], r["native_turnout_pct"])
                          for r in result["county"]], [(19041, 33079, "57.56")])
        self.assertEqual([r["voters_cast"] for r in result["ballot_modes"]], [16138, 2903, 0, 19041])
        self.assertEqual([r["registered_voters"] for r in result["ballot_modes"]], [None, None, None, 33079])
        self.assertEqual([r["native_turnout_pct"] for r in result["ballot_modes"]], ["48.79", "8.78", "0.00", "57.56"])

    def test_complete_native_candidates_and_parties(self):
        result = module.review(INPUTS)
        self.assertEqual(len(result["candidates"]), 12)
        self.assertEqual([r["native_total_votes"] for r in result["contests"]], [18865, 18853, 18626, 16856])
        self.assertEqual([(r["candidate"], r["native_party"], r["total"])
                          for r in result["candidates"] if r["native_party"] == "LIB"],
                         [("Ken Krawchuk/John Thomas", "LIB", 264)])
        self.assertEqual(len([r for r in result["candidates"] if r["native_party"] is None]), 4)

    def test_unresolved_writeins_stay_separate_and_nonadditive(self):
        result = module.review(INPUTS)
        self.assertEqual([r["total"] for r in result["unresolved"]], [8, 23, 34, 339])
        for row in result["accounting"]:
            self.assertEqual(row["native_total_votes"] + row["native_undervotes"] + row["native_overvotes"],
                             row["times_cast"])
            self.assertTrue(row["unresolved_not_added_again"])
        self.assertTrue(all(row["allocation_to_undervotes_or_overvotes"] is None for row in result["unresolved"]))

    def test_status_clock_missingness_and_reporting_scope(self):
        result = module.review(INPUTS)
        self.assertEqual([r["native_report_clock"] for r in result["pages"]], ["11/3/2026 9:53:30 PM"] * 2)
        self.assertEqual(len(result["reporting"]), 5)
        self.assertTrue(all((r["reported"], r["total"]) == (40, 40) for r in result["reporting"]))
        county = result["county"][0]
        self.assertEqual(county["native_status"], "Unofficial")
        self.assertIsNone(county["native_timezone"])
        self.assertIsNone(county["native_fips"])
        self.assertFalse(county["analysis_rate_approved"])
        self.assertFalse(county["map_approved"])

    def test_complete_page_and_independent_extraction_tampering(self):
        for replacement in ("19,042", "19,040"):
            inputs = copy.deepcopy(INPUTS)
            inputs["extractions"]["pdfplumber"][0] = inputs["extractions"]["pdfplumber"][0].replace("19,041", replacement)
            with self.assertRaises((ValueError, AssertionError)):
                module.review(resign(inputs))
        inputs = copy.deepcopy(INPUTS)
        inputs["extractions"]["pymupdf"] = inputs["extractions"]["pymupdf"][:1]
        with self.assertRaises(ValueError):
            module.review(resign(inputs))

    def test_candidate_vector_percent_and_duplicate_rejection(self):
        for old, new in (("4,556", "4,557"), ("24.15%", "24.16%"),
                         ("Write-in 5 3 0 8 0.04%", "Write-in 5 3 0 8 0.04% Write-in 5 3 0 8 0.04%")):
            inputs = copy.deepcopy(INPUTS)
            inputs["extractions"]["pdfplumber"][0] = inputs["extractions"]["pdfplumber"][0].replace(old, new)
            self.assertNotEqual(inputs["extractions"]["pdfplumber"], INPUTS["extractions"]["pdfplumber"])
            with self.assertRaises(ValueError):
                module.review(resign(inputs))

    def test_clock_reporting_and_scope_rejection(self):
        for index, old, new in ((1, "9:53:30 PM", "9:54:30 PM"),
                                (1, "40 of 40", "39 of 40")):
            inputs = copy.deepcopy(INPUTS)
            inputs["extractions"]["pdfplumber"][index] = inputs["extractions"]["pdfplumber"][index].replace(old, new)
            with self.assertRaises(ValueError):
                module.review(resign(inputs))
        inputs = copy.deepcopy(INPUTS)
        inputs["election_scope_origin"] = "2026 Primary"
        with self.assertRaises(ValueError):
            module.review(inputs)

    def test_original_pdf_and_declaring_base_receipts(self):
        self.assertEqual(INPUTS["source_pdf_sha256"], "590d5d9e2b717289a9979aea5f8beeffd0598432035011706dde74044d792b24")
        provenance = json.loads((HERE / "source-provenance.json").read_text())
        self.assertEqual(provenance["pdf_receipt"]["bytes"], 174249)
        self.assertEqual(provenance["pdf_receipt"]["status"], 200)
        self.assertEqual(provenance["pdf_receipt"]["resolved_using_actual_html_base"], "https://www.bedfordcountypa.org/")
        self.assertNotIn("/departments/elections/Elections/", provenance["pdf_receipt"]["final_url"])

    def test_archive_has_all_facts_and_reproduces_without_self_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "original"
            module.build(original)
            with zipfile.ZipFile(original / "complete-query.zip") as archive:
                self.assertEqual(len(archive.namelist()), 15)
                self.assertNotIn("complete-query.zip", archive.namelist())
                archive.extractall(root / "extracted")
            manifest = json.loads((root / "extracted/checksums.json").read_text())
            self.assertEqual(len(manifest["files"]), 14)
            for entry in manifest["files"]:
                body = (root / "extracted" / entry["path"]).read_bytes()
                self.assertEqual(len(body), entry["bytes"])
                self.assertEqual(hashlib.sha256(body).hexdigest(), entry["sha256"])
            subprocess.run([sys.executable, "-I", str(root / "extracted/review-counties.py"),
                            "--output", str(root / "reproduced")], check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({p.name for p in original.iterdir()}, {p.name for p in (root / "reproduced").iterdir()})
            for path in original.iterdir():
                self.assertEqual(path.read_bytes(), (root / "reproduced" / path.name).read_bytes(), path.name)

    def test_refuses_to_mutate_existing_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                module.build(Path(temporary))


if __name__ == "__main__":
    unittest.main()

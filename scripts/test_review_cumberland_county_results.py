import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cumberland_review", ROOT / "scripts/review-cumberland-county-results.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
SOURCE = ROOT / "data/county-source-reviews/20261106-cumberland-facts-01"


class CumberlandFactsTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads((SOURCE / "source-records.json").read_text())

    def test_complete_native_participation_is_not_candidate_votes(self):
        REVIEW.validate(self.facts)
        county = self.facts["reports"][0]["pages"][0]["participation"]
        self.assertEqual(REVIEW.counts(county["ballot_count_literals"]), [117334, 89435, 27899])
        self.assertEqual(REVIEW.integer(county["registered_voters_literal"]), 185538)
        governor = self.facts["reports"][0]["pages"][1]["contests"][0]
        self.assertEqual(sum(REVIEW.counts(row["count_literals"])[0] for row in governor["rows"]), 114712)
        self.assertEqual(governor["rows"][-1]["party_literal"], "")
        self.assertNotEqual(self.facts["reports"][0]["pages"][0]["source_update_literal"],
                            self.facts["reports"][1]["pages"][0]["source_update_literal"])

    def test_missing_pages_and_unknown_timezones_fail_closed(self):
        for mutation in ("page", "timezone"):
            facts = copy.deepcopy(self.facts)
            if mutation == "page":
                facts["reports"][1]["pages"].pop()
            else:
                facts["reports"][1]["pages"][0]["declared_timezone"] = "Eastern"
            with self.assertRaises(ValueError):
                REVIEW.validate(facts)

    def test_incomplete_candidates_and_modes_are_rejected(self):
        for mutation in ("candidate", "mode"):
            facts = copy.deepcopy(self.facts)
            rows = facts["reports"][1]["pages"][0]["contests"][0]["rows"]
            if mutation == "candidate":
                rows.pop(0)
            else:
                rows[0]["count_literals"].pop()
            with self.assertRaises(ValueError):
                REVIEW.validate(facts)

    def test_candidate_vectors_must_reconcile_even_with_valid_mode_sums(self):
        row = self.facts["reports"][1]["pages"][0]["contests"][0]["rows"][0]
        row["count_literals"] = ["532", "414", "118"]
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            REVIEW.validate(self.facts)

    def test_unit_participation_must_reconcile_to_county(self):
        self.facts["reports"][1]["pages"][0]["participation"]["registered_voters_literal"] = "1,033"
        with self.assertRaises(ValueError):
            REVIEW.validate(self.facts)

    def test_printed_fraction_discrepancy_is_retained_not_corrected(self):
        page = next(page for page in self.facts["reports"][1]["pages"]
                    if page["unit"] == "UPPER ALLEN 6" and page["participation"] is not None)
        self.assertEqual(page["participation"]["printed_turnout_literal"], "65.36%")
        page["participation"]["printed_turnout_literal"] = "65.37%"
        with self.assertRaisesRegex(ValueError, "Changed source-specific"):
            REVIEW.validate(self.facts)

    def test_complete_package_reproduces_offline_and_keeps_accounting_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "facts"
            audit = REVIEW.build(self.facts, output)
            self.assertFalse(audit["maps_approved"])
            self.assertEqual(audit["table_rows"]["native-unit-participation.csv"], 118)
            self.assertEqual(audit["table_rows"]["native-unit-candidate-option-results.csv"], 1461)
            self.assertIn("absent, not zero", " ".join(audit["qualifications"]))
            for path in SOURCE.iterdir():
                if path.suffix in (".csv", ".json"):
                    self.assertEqual(path.read_bytes(), (output / path.name).read_bytes(), path.name)
            with zipfile.ZipFile(output / "complete-cumberland-2026-numerical-facts-01.zip") as archive:
                self.assertEqual(len(archive.namelist()), 12)
                self.assertEqual(len(set(archive.namelist())), 12)
                self.assertFalse(any(name.endswith((".pdf", ".html")) for name in archive.namelist()))


if __name__ == "__main__":
    unittest.main()

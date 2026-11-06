import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("maryland", ROOT / "review-maryland.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MarylandReviewTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads((ROOT / "native-facts.json").read_text())

    def replace_both(self, old, new):
        for pages in self.facts["extractors"].values():
            pages[0] = pages[0].replace(old, new)

    def test_preserves_every_native_field_and_withholds_unestablished_interpretations(self):
        rows = module.review(self.facts)
        self.assertEqual(len(rows), 25)
        self.assertEqual(sum(row["cards_cast"] for row in rows[:-1]), 1944170)
        self.assertEqual(rows[-1]["eligible_voters"], 4293322)
        self.assertEqual(rows[-1]["native_printed_percentage"], "45.28%")
        self.assertEqual(rows[0]["native_update_literal"], "11/5/2026 7:36 pm")
        for row in rows:
            self.assertEqual(row["native_measure_literal"], "Cards Cast")
            for field in ("source_fips", "declared_timezone", "provisional_count", "unique_voters"):
                self.assertEqual(row[field], "")
            for field in ("analysis_ballots_approved", "analysis_rates_approved", "maps_approved"):
                self.assertIs(row[field], False)

    def test_rejects_mixed_numerical_snapshots_and_clocks(self):
        self.facts["extractors"]["pdfplumber"][0] = self.facts["extractors"]["pdfplumber"][0].replace(
            "7:36 pm", "6:15 pm")
        with self.assertRaisesRegex(ValueError, "extractions disagree"):
            module.review(self.facts)

    def test_rejects_duplicate_or_unknown_county(self):
        self.replace_both("Anne Arundel County", "Allegany County")
        with self.assertRaisesRegex(ValueError, "county"):
            module.review(self.facts)

    def test_rejects_unreconciled_total(self):
        self.replace_both("1,944,170", "1,944,171")
        with self.assertRaisesRegex(ValueError, "numerical disagreement"):
            module.review(self.facts)

    def test_rejects_incorrect_native_percentages(self):
        self.replace_both("47.40%", "47.41%")
        with self.assertRaisesRegex(ValueError, "percentage"):
            module.review(self.facts)

    def test_rejects_missing_or_extra_report_rows(self):
        for pages in self.facts["extractors"].values():
            pages[0] += "\nAdditional County 1 1 100.00%\n"
        with self.assertRaisesRegex(ValueError, "layout"):
            module.review(self.facts)

    def test_rejects_a_guessed_or_primary_source(self):
        self.facts["declaration"]["url"] += "?guessed=1"
        with self.assertRaisesRegex(ValueError, "actually declared"):
            module.review(self.facts)

    def test_complete_archive_reproduces_offline_and_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "complete"
            module.build(ROOT / "native-facts.json", output)
            with zipfile.ZipFile(output / "complete-query.zip") as archive:
                self.assertEqual(len(archive.namelist()), 9)
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (output / name).read_bytes())
            repeated = Path(temporary) / "repeated"
            module.build(output / "native-facts.json", repeated)
            self.assertEqual(sorted(path.name for path in output.iterdir()),
                             sorted(path.name for path in repeated.iterdir()))
            for path in output.iterdir():
                self.assertEqual(path.read_bytes(), (repeated / path.name).read_bytes())
            with self.assertRaisesRegex(ValueError, "overwrite"):
                module.build(ROOT / "native-facts.json", output)


if __name__ == "__main__":
    unittest.main()

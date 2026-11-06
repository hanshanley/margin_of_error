import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("county_review", ROOT / "review-counties.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CountyReviewTests(unittest.TestCase):
    def setUp(self):
        self.inputs = json.loads((ROOT / "source-inputs.json").read_text())

    def test_native_participation_is_not_candidate_votes(self):
        tables = module.review(self.inputs)
        self.assertEqual([r["total_ballots"] for r in tables["county-participation.csv"]], [2712, 10542])
        self.assertEqual([r["unclassified_residual"] for r in tables["contest-accounting.csv"]],
                         [41, 32, 396, 0, 0, 0, 0])
        self.assertTrue(all(r["native_mode_ballots"] is None for r in tables["contest-accounting.csv"]))

    def test_rejects_candidate_mode_and_contest_sum_corruption(self):
        for column in (1, 3, 4, 5):
            changed = copy.deepcopy(self.inputs)
            changed["reports"][0]["contests"][0]["choices"][0][column] += 1
            with self.assertRaises(AssertionError):
                module.review(changed)

    def test_rejects_repeated_denominator_or_percentage_corruption(self):
        for key, value in (("header_registered_voters", 4502), ("header_printed_percentage", "60.26%")):
            changed = copy.deepcopy(self.inputs)
            changed["reports"][0]["contests"][0][key] = value
            with self.assertRaises(AssertionError):
                module.review(changed)

    def test_rejects_native_accounting_mismatch(self):
        for key in ("header_ballots", "overvoted_ballots", "footer_overvotes", "footer_undervotes"):
            changed = copy.deepcopy(self.inputs)
            changed["reports"][1]["contests"][0][key] += 1
            with self.assertRaises(AssertionError):
                module.review(changed)

    def test_missing_party_timezone_reporting_and_native_pages(self):
        tables = module.review(self.inputs)
        self.assertTrue(all(r["native_literal_party"] is None for r in tables["candidate-results.csv"]))
        self.assertTrue(all(r["native_timezone"] is None for r in tables["source-pages.csv"]))
        self.assertIsNone(tables["reporting.csv"][0]["reported_precincts"])
        self.assertEqual([r["native_page"] for r in tables["source-pages.csv"]], ["1 of 1", None, None, "1 of 1"])
        self.assertIsNone(tables["source-pages.csv"][2]["native_clock"])

    def test_complete_write_in_listing_keeps_shortfalls_and_blanks(self):
        tables = module.review(self.inputs)
        matrix = tables["write-in-matrix.csv"]
        self.assertEqual(len(matrix), 59)
        self.assertEqual([r["summary_less_listing_unallocated"] for r in
                          tables["write-in-reconciliation.csv"]], [0, 4, 25])
        columns = self.inputs["sullivan_write_in_matrix"]["columns"] + ["TOTALS"]
        values = [r[c] for r in matrix for c in columns]
        self.assertEqual((len(values), values.count(None), values.count(0)), (944, 841, 16))
        hedgcock = next(r for r in matrix if r["native_choice"] == "Michael Hedgcock")
        self.assertEqual((hedgcock["Hillsgrove Town"], hedgcock["Laporte Boro"], hedgcock["TOTALS"]), (1, 1, 2))
        self.assertIsNone(hedgcock["Laporte Twp"])

    def test_rejects_missing_to_zero_conversion_and_invalid_locality(self):
        for key in ("Forks Township", "Invented Township"):
            changed = copy.deepcopy(self.inputs)
            changed["sullivan_write_in_matrix"]["sections"][0]["rows"][0][1][key] = 0
            with self.assertRaises(AssertionError):
                module.review(changed)

    def test_rejects_dropped_continuation_and_false_named_totals(self):
        for section_index, row_index in ((3, 34), (2, 0)):
            changed = copy.deepcopy(self.inputs)
            changed["sullivan_write_in_matrix"]["sections"][section_index]["rows"].pop(row_index)
            with self.assertRaises(AssertionError):
                module.review(changed)

    def test_rejects_stale_wyoming_snapshot(self):
        changed = copy.deepcopy(self.inputs)
        changed["reports"][1]["total_ballots"] = 10531
        with self.assertRaises(AssertionError):
            module.review(changed)

    def test_complete_archive_rebuild_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "query"
            module.build(output)
            expected = json.loads((ROOT / "checksums.json").read_text())
            self.assertEqual(set(p.name for p in output.iterdir()),
                             set(expected) | {"checksums.json", "complete-query.zip"})
            for path in output.iterdir():
                self.assertEqual(path.read_bytes(), (ROOT / path.name).read_bytes(), path.name)
            with zipfile.ZipFile(output / "complete-query.zip") as archive:
                self.assertEqual(set(archive.namelist()), set(expected) | {"checksums.json"})


if __name__ == "__main__":
    unittest.main()

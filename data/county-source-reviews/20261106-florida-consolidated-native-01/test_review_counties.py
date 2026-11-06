import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("county_review", HERE / "review-counties.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE = json.loads((HERE / "source-qualification.json").read_text())


class NativeCountyReviewTests(unittest.TestCase):
    def test_complete_table_and_separate_total(self):
        parsed = module.review(copy.deepcopy(SOURCE))
        self.assertEqual(len(parsed["counties"]), 67)
        self.assertEqual(len(parsed["cells"]), 680)
        self.assertEqual(parsed["statewide"][0]["reported_participants"], 8335497)
        self.assertEqual(parsed["statewide"][0]["eligible_active_registered_voters"], 13704495)
        monroe = next(row for row in parsed["counties"] if row["native_county"] == "Monroe")
        self.assertEqual((monroe["reported_participants"], monroe["eligible_active_registered_voters"]),
                         (32506, 54704))

    def test_missing_and_duplicate_counties_rejected(self):
        missing = copy.deepcopy(SOURCE)
        missing["county_rows"].pop()
        duplicate = copy.deepcopy(SOURCE)
        duplicate["county_rows"][1] = duplicate["county_rows"][0]
        for source in (missing, duplicate):
            with self.subTest(source=source["county_rows"][0][0]["text"]):
                with self.assertRaises(ValueError):
                    module.review(source)

    def test_count_percentage_and_aggregate_tampering_rejected(self):
        for row_type, column, value in (
            ("county_rows", 1, "-1"), ("county_rows", 3, "0%"),
            ("statewide_row", 1, "8,335,498"), ("county_rows", 2, "0"),
        ):
            source = copy.deepcopy(SOURCE)
            row = source[row_type][0] if row_type == "county_rows" else source[row_type]
            row[column]["text"] = value
            with self.subTest(row_type=row_type, column=column, value=value):
                with self.assertRaises(ValueError):
                    module.review(source)

    def test_missing_or_unrecognized_county_flags_rejected(self):
        for classes in ([], [[]], [["Z"]], [["Y", "N"]]):
            source = copy.deepcopy(SOURCE)
            source["county_rows"][0][8]["span_classes"] = classes
            with self.subTest(classes=classes):
                with self.assertRaises(ValueError):
                    module.review(source)

    def test_unfinished_flags_missing_clock_and_no_approval_preserved(self):
        parsed = module.review(copy.deepcopy(SOURCE))
        alachua = next(row for row in parsed["counties"] if row["native_county"] == "Alachua")
        self.assertEqual(alachua["native_provisional_completed"], "N")
        self.assertEqual(alachua["native_10_day_overseas_completed"], "N")
        for row in parsed["counties"]:
            self.assertIsNone(row["source_as_of"])
            self.assertIsNone(row["source_timezone"])
            self.assertIsNone(row["native_fips"])
            self.assertIs(row["map_approved"], False)
            self.assertIs(row["analysis_rate_approved"], False)
        self.assertIsNone(parsed["statewide"][0]["native_provisional_completed"])

    def test_approval_and_clock_invention_rejected(self):
        for key, value in (("map_approved", True), ("county_fips_join_approved", True),
                           ("generic_turnout_approved", True), ("certified", True),
                           ("source_as_of", "2026-11-06T00:00:00Z"),
                           ("source_timezone", "Eastern")):
            source = copy.deepcopy(SOURCE)
            source[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    module.review(source)

    def test_native_code_is_not_fips(self):
        source = copy.deepcopy(SOURCE)
        source["native_county_catalog"][0]["native_fips"] = "12001"
        with self.assertRaises(ValueError):
            module.review(source)

    def test_complete_reproducible_zip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            audit = module.build(first)
            module.build(second)
            self.assertEqual((first / "complete-query.zip").read_bytes(),
                             (second / "complete-query.zip").read_bytes())
            with zipfile.ZipFile(first / "complete-query.zip") as archive:
                self.assertEqual(set(archive.namelist()),
                                 {path.name for path in first.iterdir()} - {"complete-query.zip"})
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (first / name).read_bytes())
            self.assertEqual(audit["row_counts"]["source-native-cells.csv"], 680)
            with self.assertRaises(ValueError):
                module.build(first)


if __name__ == "__main__":
    unittest.main()

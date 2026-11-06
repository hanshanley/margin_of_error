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
    def test_complete_table_and_separate_statewide_total(self):
        parsed = module.review(copy.deepcopy(SOURCE))
        self.assertEqual([(row["native_geography_literal"], row["reported_voter_count"])
                          for row in parsed["counties"]],
                         [("Kent County", 51462), ("New Castle County", 159774), ("Sussex County", 103559)])
        self.assertEqual(parsed["statewide"][0]["reported_voter_count"], 314795)
        self.assertEqual((len(parsed["modes"]), len(parsed["cells"])), (16, 25))

    def test_missing_and_duplicate_counties_rejected(self):
        for kind in ("missing", "duplicate", "statewide"):
            source = copy.deepcopy(SOURCE)
            if kind == "missing":
                source["headers"].pop(1)
            elif kind == "duplicate":
                source["headers"][2] = source["headers"][1]
            else:
                source["headers"][-1] = "Kent County"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                module.review(source)

    def test_missing_or_repeated_methods_rejected(self):
        for kind in ("missing", "duplicate"):
            source = copy.deepcopy(SOURCE)
            if kind == "missing":
                source["rows"].pop()
            else:
                source["rows"][1] = source["rows"][0]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                module.review(source)

    def test_bad_counts_and_both_aggregate_directions_rejected(self):
        for row, column, value in ((0, 1, "-1"), (0, 1, ""), (0, 1, "2,97"),
                                    (0, 4, "20,394"), (3, 1, "51,463")):
            source = copy.deepcopy(SOURCE)
            source["rows"][row][column] = value
            with self.subTest(row=row, column=column, value=value), self.assertRaises(ValueError):
                module.review(source)

    def test_clocks_registrations_and_approvals_not_invented(self):
        for key, value in (("native_update_literal", "2026-11-06T00:00:00Z"),
                           ("source_timezone", "Eastern"), ("registration_denominators", [1, 2, 3]),
                           ("native_fips", "10001"), ("all_mode_completion_approved", True),
                           ("analysis_rate_approved", True), ("map_approved", True), ("certified", True)):
            source = copy.deepcopy(SOURCE)
            source[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.review(source)

    def test_afternoon_snapshot_missingness_and_aggregate_scope_retained(self):
        parsed = module.review(copy.deepcopy(SOURCE))
        for row in parsed["counties"] + parsed["statewide"]:
            self.assertTrue(row["partial_election_day_snapshot"])
            for key in ("native_registered_voters", "source_timezone", "native_fips"):
                self.assertIsNone(row[key])
            for key in ("all_mode_completion_approved", "analysis_rate_approved", "map_approved", "certified"):
                self.assertIs(row[key], False)
        self.assertEqual(sum(row["reported_voter_count"] for row in parsed["modes"]
                             if row["geography_level"] == "county" and not row["is_aggregate"]), 314795)

    def test_complete_reproducible_zip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = [Path(temporary) / name for name in ("first", "second")]
            module.build(first)
            module.build(second)
            self.assertEqual((first / "complete-query.zip").read_bytes(),
                             (second / "complete-query.zip").read_bytes())
            with zipfile.ZipFile(first / "complete-query.zip") as archive:
                self.assertEqual(set(archive.namelist()),
                                 {path.name for path in first.iterdir()} - {"complete-query.zip"})
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (first / name).read_bytes())
            with self.assertRaises(ValueError):
                module.build(first)


if __name__ == "__main__":
    unittest.main()

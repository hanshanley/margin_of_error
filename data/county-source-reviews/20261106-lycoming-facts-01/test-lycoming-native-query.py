import copy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


FOLDER = Path(__file__).parent
spec = importlib.util.spec_from_file_location("lycoming", FOLDER / "review-lycoming-native-query.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class LycomingNativeQueryTests(unittest.TestCase):
    def setUp(self):
        self.records = json.loads(gzip.decompress((FOLDER / "source-records.json.gz").read_bytes()))

    def test_complete_reproduction_and_extracted_archive(self):
        result = review.reproduce(FOLDER)
        for name, data in result.items():
            self.assertEqual((FOLDER / name).read_bytes(), data, name)
        with tempfile.TemporaryDirectory() as temporary:
            with zipfile.ZipFile(FOLDER / review.ARCHIVE) as archive:
                self.assertEqual(set(archive.namelist()), set(result) - {review.ARCHIVE})
                self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))
                archive.extractall(temporary)
            self.assertEqual(review.reproduce(Path(temporary)), result)

    def test_receipts_and_candidate_modes_are_not_ballot_modes(self):
        tables = review.tables(self.records)
        row = tables["county-participation.csv"][0]
        self.assertEqual((row["ballots_cast"], row["registered_voters"]), (40596, 73009))
        self.assertEqual(row["county_ballot_modes"], "")
        self.assertEqual(row["blank_ballots"], "")
        self.assertEqual(tables["native-mail-ballot-receipts.csv"][0]["count"], 5770)
        self.assertIs(tables["native-mail-ballot-receipts.csv"][0]["added_to_ballots"], False)
        self.assertEqual(len(tables["native-candidate-mode-results.csv"]), 48)
        self.assertEqual({row["party_literal"] for row in tables["native-candidate-results.csv"]}, {""})

    def test_district_electorates_and_native_turnout_are_not_county_ballots(self):
        tables = review.tables(self.records)
        self.assertEqual([row["registered_voters"] for row in tables["native-contests.csv"]],
                         [73009, 45774, 27235, 33076, 39933, 2187])
        self.assertEqual([row["votes"] for row in tables["native-contest-totals.csv"]],
                         [40412, 24549, 15864, 14019, 20584, 1198])
        self.assertEqual([row["unclassified_county_ballot_minus_choice_total"]
                          for row in tables["native-contest-totals.csv"]], [184, "", "", "", "", ""])
        self.assertEqual(tables["native-contests.csv"][0]["native_turnout_pct"], "55.58")
        self.assertEqual(tables["county-participation.csv"][0]["native_printed_turnout_pct"], "55.60")

    def test_native_clock_missing_fields_and_unofficial_qualifications_survive(self):
        tables = review.tables(self.records)
        row = tables["county-participation.csv"][0]
        self.assertEqual(row["source_update_literal"], "2026-11-05 10:37:43")
        for field in ("declared_timezone", "source_fips"):
            self.assertEqual(row[field], "")
        self.assertIs(row["counting_complete"], False)
        self.assertIs(row["maps_approved"], False)
        self.assertIn("native_calendar_label_conflict",
                      {row["kind"] for row in tables["native-counting-qualifications.csv"]})

    def test_semantic_scope_corruptions_fail_beyond_hash_and_independent_copy_guards(self):
        cases = [
            ("ballots_cast", 46366), ("registered_voters", 0), ("blank_ballots", 0),
            ("county_ballot_modes", {"ED": 34684, "MI": 5728, "PR": 0}),
            ("declared_timezone", "EST"), ("source_fips", "42081"),
            ("counting_complete", True), ("maps_approved", True),
            ("native_overall_turnout_pct", "55.58"), ("reported_precincts", 79),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.records)
                for report in ("native_report", "independent_native_report"):
                    changed[report][field] = value
                with self.assertRaises(ValueError):
                    review.validate(changed, check_pinned=False)

    def test_semantic_choice_and_source_corruptions_fail_beyond_hash_guard(self):
        for field, value in (("votes", 15325), ("votes", True), ("MI", 0),
                             ("party_literal", "DEM"), ("choice_literal", "Shapiro"),
                             ("printed_pct", "37.93")):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.records)
                for report in ("native_report", "independent_native_report"):
                    changed[report]["contests"][0]["choices"][0][field] = value
                with self.assertRaises(ValueError):
                    review.validate(changed, check_pinned=False)
        for field in ("source_receipts", "source_declarations", "source_pages", "counting_qualifications"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.records)
                changed[field].pop()
                with self.assertRaises(ValueError):
                    review.validate(changed, check_pinned=False)
        changed = copy.deepcopy(self.records)
        changed["mail_receipt"]["added_to_ballots"] = True
        with self.assertRaises(ValueError):
            review.validate(changed, check_pinned=False)
        for field in ("registered_voters", "native_turnout_pct"):
            changed = copy.deepcopy(self.records)
            for report in ("native_report", "independent_native_report"):
                changed[report]["contests"][1][field] = 73009
            with self.assertRaises(ValueError):
                review.validate(changed, check_pinned=False)


if __name__ == "__main__":
    unittest.main()

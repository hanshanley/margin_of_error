import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest


FOLDER = Path(__file__).parent
spec = importlib.util.spec_from_file_location("greene", FOLDER / "review-greene-county-native-query.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class GreeneNativeQueryTests(unittest.TestCase):
    def setUp(self):
        self.records = json.loads(gzip.decompress((FOLDER / "source-records.json.gz").read_bytes()))

    def test_complete_reproduction_and_extracted_archive(self):
        import tempfile
        import zipfile
        result = review.reproduce(FOLDER)
        for name, data in result.items():
            self.assertEqual((FOLDER / name).read_bytes(), data, name)
        with tempfile.TemporaryDirectory() as temporary:
            with zipfile.ZipFile(FOLDER / review.ARCHIVE) as archive:
                self.assertEqual(set(archive.namelist()), set(result) - {review.ARCHIVE})
                archive.extractall(temporary)
            rebuilt = review.reproduce(Path(temporary))
            self.assertEqual(rebuilt, result)

    def test_missing_denominator_and_clock_stay_missing(self):
        rows = review.tables(self.records)["county-participation.csv"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ballots_cast"], 11105)
        self.assertEqual(rows[0]["blank_ballots"], 5)
        for field in ("registered_voters", "registered_turnout_pct", "native_printed_turnout",
                      "source_update_literal", "declared_timezone", "source_fips"):
            self.assertEqual(rows[0][field], "")
        self.assertIs(rows[0]["counting_complete"], False)
        self.assertIs(rows[0]["maps_approved"], False)

    def test_candidate_accounting_never_invents_party_participation(self):
        tables = review.tables(self.records)
        totals = tables["county-contest-accounting.csv"]
        self.assertEqual([row["derived_candidate_sum"] for row in totals], [10990, 10897, 10548, 10918])
        self.assertEqual([row["unclassified_ballot_minus_candidate_sum"] for row in totals], [115, 208, 557, 187])
        parties = tables["county-literal-party-totals.csv"]
        self.assertNotIn("Ballots Cast Total", {row["party_literal"] for row in parties})
        self.assertEqual(sum(row["votes"] for row in parties), sum(row["derived_candidate_sum"] for row in totals))

    def test_semantic_corruptions_fail_beyond_input_hash_guard(self):
        cases = [
            ("registered_voters", 0), ("registered_voters", 20000),
            ("native_printed_turnout", "55.5"), ("source_update_literal", "11/3/2026 10:00 PM"),
            ("declared_timezone", "EST"), ("source_fips", "42059"),
            ("counting_complete", True), ("maps_approved", True),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(self.records)
                changed[field] = value
                with self.assertRaises(ValueError):
                    review.validate(changed, check_pinned=False)
        for field, value in (("votes", 4567), ("party_literal", "DEMOCRAT"),
                             ("candidate_or_measure_literal", "Josh Shapiro"),
                             ("printed_pct", "41.6%"), ("votes", True)):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(self.records)
                changed["native_rows"][2][field] = value
                with self.assertRaises(ValueError):
                    review.validate(changed, check_pinned=False)
        for key in ("native_rows", "source_receipts", "native_header"):
            with self.subTest(removed=key):
                changed = copy.deepcopy(self.records)
                changed[key].pop()
                with self.assertRaises(ValueError):
                    review.validate(changed, check_pinned=False)


if __name__ == "__main__":
    unittest.main()

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("county_review", HERE / "review-county.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE = json.loads((HERE / "source-qualification.json").read_text())


class NativeCountyReviewTests(unittest.TestCase):
    def test_complete_participation_candidate_and_native_input(self):
        parsed = module.review(copy.deepcopy(SOURCE))
        self.assertEqual(len(parsed["unit_participation"]), 106)
        self.assertEqual(len(parsed["candidates"]), 65)
        self.assertEqual(len(parsed["reporting"]), 26)
        county = parsed["participation"][0]
        self.assertEqual((county["reported_ballots_cast"], county["reported_registered_voters"],
                          county["native_registered_percentage"]), (67812, 97950, "69.23%"))
        governor = [row for row in parsed["candidates"]
                    if row["native_contest"] == "Governor / Lieutenant Governor"]
        self.assertEqual(sum(row["votes"] for row in governor), 67418)
        self.assertNotEqual(sum(row["votes"] for row in governor), county["reported_ballots_cast"])
        self.assertTrue(all(not row["selections_are_participants"] for row in governor))
        self.assertEqual(len(parsed["cells"]), sum(len(r) for t in SOURCE["tables"] for r in t))

    def test_missing_tables_duplicate_units_and_truncated_vectors_rejected(self):
        missing = copy.deepcopy(SOURCE)
        missing["tables"].pop()
        duplicate = copy.deepcopy(SOURCE)
        duplicate["tables"][2][2][1] = duplicate["tables"][2][1][1]
        truncated = copy.deepcopy(SOURCE)
        truncated["tables"][4][1].pop()
        for source in (missing, duplicate, truncated):
            with self.subTest():
                with self.assertRaises(ValueError):
                    module.review(source)

    def test_native_counts_percentages_and_candidate_identity_tampering_rejected(self):
        for table, row, column, value in (
            (2, 1, 3, "265"), (1, 2, 2, "69.24%"),
            (3, 1, 3, "27,725"), (3, 1, 2, "41.13%"),
            (4, 0, 2, "Different candidate"), (2, 1, 2, "-1"),
        ):
            source = copy.deepcopy(SOURCE)
            source["tables"][table][row][column] = value
            with self.subTest(table=table, row=row, column=column):
                with self.assertRaises(ValueError):
                    module.review(source)

    def test_reporting_scope_and_unit_identity_tampering_rejected(self):
        reporting = copy.deepcopy(SOURCE)
        reporting["reporting_statements"][0] = "Precincts Reporting: 105 of 106 for 99%"
        wrong_unit = copy.deepcopy(SOURCE)
        wrong_unit["tables"][4][1][1] = "Another County"
        for source in (reporting, wrong_unit):
            with self.subTest():
                with self.assertRaises(ValueError):
                    module.review(source)

    def test_native_zeros_missing_unit_rates_and_nonpartisan_write_ins_preserved(self):
        parsed = module.review(copy.deepcopy(SOURCE))
        units = {row["native_unit"]: row for row in parsed["unit_participation"]}
        self.assertEqual((units["City of Janesville Ward 40"]["registered_voters"],
                          units["City of Janesville Ward 40"]["ballots_cast"]), (3538, 0))
        self.assertEqual((units["City of Beloit Ward 26"]["registered_voters"],
                          units["City of Beloit Ward 26"]["ballots_cast"]), (0, 0))
        self.assertIn("City of Beliot Ward 11", units)
        for row in parsed["unit_participation"]:
            self.assertIsNone(row["native_turnout_percentage"])
            self.assertIs(row["map_approved"], False)
        write_ins = [row for row in parsed["parties"] if row["native_write_in"]]
        self.assertTrue(write_ins)
        self.assertTrue(all(row["native_party"] == "NONPARTISAN"
                            and row["write_in_party_not_inferred"] for row in write_ins))
        referenda = [row for row in parsed["candidates"] if row["native_option"] in ("Yes", "No")]
        self.assertEqual(len(referenda), 18)
        self.assertTrue(all(row["native_party"] == "NONPARTISAN"
                            and row["native_label"] == row["native_option"] + " (NONPARTISAN)"
                            for row in referenda))

    def test_clock_geography_approval_and_election_invention_rejected(self):
        for key, value in (
            ("source_timezone", "Central"), ("native_fips", "55105"),
            ("native_update_literal", "2026-11-06T00:00:00Z"),
            ("election_date", "2024-11-05"), ("map_approved", True),
            ("county_fips_join_approved", True), ("generic_turnout_approved", True),
            ("all_mode_definition_approved", True), ("certified", True),
        ):
            source = copy.deepcopy(SOURCE)
            source[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    module.review(source)

    def test_complete_reproducible_zip_checksums_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / "first", Path(temporary) / "second"
            audit = module.build(first)
            module.build(second)
            self.assertEqual((first / "complete-query.zip").read_bytes(),
                             (second / "complete-query.zip").read_bytes())
            checksums = json.loads((first / "checksums.json").read_text())
            for entry in checksums["files"]:
                body = (first / entry["path"]).read_bytes()
                self.assertEqual((len(body), hashlib.sha256(body).hexdigest()),
                                 (entry["bytes"], entry["sha256"]))
            with zipfile.ZipFile(first / "complete-query.zip") as archive:
                self.assertEqual(set(archive.namelist()),
                                 {path.name for path in first.iterdir()} - {"complete-query.zip"})
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (first / name).read_bytes())
            self.assertEqual(audit["row_counts"]["native-unit-participation.csv"], 106)
            with self.assertRaises(ValueError):
                module.build(first)


if __name__ == "__main__":
    unittest.main()

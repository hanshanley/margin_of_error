import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("state_review", HERE / "review-state.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE = json.loads((HERE / "source-qualification.json").read_text())
NATIVE = [json.loads((HERE / name).read_bytes()) for name in module.NATIVE]


class NativeStateReviewTests(unittest.TestCase):
    def test_complete_statewide_and_separate_district_query(self):
        parsed = module.review(copy.deepcopy(SOURCE), *copy.deepcopy(NATIVE))
        state = parsed["statewide"][0]
        self.assertEqual((state["ballots_cast"], state["registered_voters"], state["native_printed_percent"]),
                         (384862, 810407, "47.49"))
        self.assertEqual((len(parsed["districts"]), len(parsed["statewide"])), (41, 1))
        self.assertEqual((len(parsed["candidates"]), len(parsed["county_candidates"]), len(parsed["parties"])),
                         (124, 124, 124))

    def test_missing_repeated_or_wrong_districts_rejected(self):
        for kind in ("missing", "duplicate", "county"):
            native = copy.deepcopy(NATIVE)
            if kind == "missing":
                native[0].pop()
            elif kind == "duplicate":
                native[0][1] = native[0][0]
            else:
                native[0][0]["Representative District"] = "Kent County"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                module.review(copy.deepcopy(SOURCE), *native)

    def test_bad_counts_rates_and_statewide_aggregates_rejected(self):
        for index, field, value in ((0, "Ballots Cast", "-1"), (0, "Reg Voters", "0"),
                                    (0, "Percentage", 0), (41, "Ballots Cast", "384,863")):
            native = copy.deepcopy(NATIVE)
            native[0][index][field] = value
            with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                module.review(copy.deepcopy(SOURCE), *native)

    def test_candidate_modes_county_components_and_inventory_rejected(self):
        for source_index, field, value in ((1, "Total Votes", "1"), (2, "State", 1),
                                            (2, "Wilmington", 1)):
            native = copy.deepcopy(NATIVE)
            native[source_index][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.review(copy.deepcopy(SOURCE), *native)
        native = copy.deepcopy(NATIVE)
        native[2].pop()
        with self.assertRaises(ValueError):
            module.review(copy.deepcopy(SOURCE), *native)

    def test_source_clocks_geography_and_approvals_not_invented(self):
        for key, value in (("native_turnout_update_clock", "2026-11-04T03:03:18.364-05:00"),
                           ("native_turnout_timezone", "-05:00"), ("native_fips", "10"),
                           ("analysis_rate_approved", True), ("maps_approved", True),
                           ("all_mode_complete", True), ("certified", True)):
            source = copy.deepcopy(SOURCE)
            source[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.review(source, *copy.deepcopy(NATIVE))
        native = copy.deepcopy(NATIVE)
        native[0][0]["ReportTime"] = native[1][0]["ReportTime"]
        with self.assertRaises(ValueError):
            module.review(copy.deepcopy(SOURCE), *native)

    def test_candidates_not_participation_and_missing_clocks_retained(self):
        parsed = module.review(copy.deepcopy(SOURCE), *copy.deepcopy(NATIVE))
        senate = sum(module.integer(row["Total Votes"]) for row in parsed["candidates"]
                     if row["Contest Title"] == "U.S. Senator")
        self.assertNotEqual(senate, parsed["statewide"][0]["ballots_cast"])
        for row in parsed["districts"] + parsed["statewide"]:
            for field in ("native_update_clock", "declared_timezone", "native_fips"):
                self.assertIsNone(row[field])
            for field in ("analysis_rate_approved", "maps_approved", "all_mode_complete", "certified"):
                self.assertIs(row[field], False)

    def test_candidate_reporting_units_keep_per_contest_scope(self):
        parsed = module.review(copy.deepcopy(SOURCE), *copy.deepcopy(NATIVE))
        senate = next(row for row in parsed["candidates"] if row["Contest Title"] == "U.S. Senator")
        attorney = next(row for row in parsed["candidates"] if row["Contest Title"] == "Attorney General")
        self.assertEqual((senate["Precincts Reported"], senate["Total Precincts"]), (530, 530))
        self.assertEqual((attorney["Precincts Reported"], attorney["Total Precincts"]), (527, 527))
        native = copy.deepcopy(NATIVE)
        native[1][0]["Precincts Reported"] = 531
        with self.assertRaises(ValueError):
            module.review(copy.deepcopy(SOURCE), *native)

    def test_complete_reproducible_zip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = [Path(temporary) / name for name in ("first", "second")]
            module.build(first)
            module.build(second)
            self.assertEqual((first / "complete-query.zip").read_bytes(),
                             (second / "complete-query.zip").read_bytes())
            with zipfile.ZipFile(first / "complete-query.zip") as archive:
                self.assertEqual(set(archive.namelist()), {path.name for path in first.iterdir()} - {"complete-query.zip"})
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (first / name).read_bytes())
            with self.assertRaises(ValueError):
                module.build(first)


if __name__ == "__main__":
    unittest.main()

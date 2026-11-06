import copy
import contextlib
import csv
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


spec = importlib.util.spec_from_file_location(
    "mn_review", Path(__file__).with_name("review-minnesota-bulk-participation.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    choice = ["MN", "01", "", "0102", "U.S. Senator", "", "0403", "Candidate", "", "",
              "DFL", "2", "2", "9", "100.00", "9"]
    return {
        "counties": [["01", "County", "2"]],
        "parties": [["DFL", "Democratic-Farmer-Labor", "04"]],
        "precincts": [["01", "0001", "One", "", "", "", "", "", "", ""],
                      ["01", "0002", "Two", "", "", "", "", "", "", ""]],
        "pctstats": [["MN", "01", "0001", "One", "1", "10", "0", "9", "0", "0", "0", "9"],
                     ["MN", "01", "0002", "Two", "1", "10", "0", "0", "0", "0", "0", "0"]],
        "county-results": [choice],
        "precinct-results": [choice[:2] + ["0001"] + choice[3:]],
    }


def records(body):
    return list(csv.DictReader(io.StringIO(body.decode())))


class NativeParticipationReview(unittest.TestCase):
    def test_extracted_download_rebuilds_every_file_and_complete_archive_without_originals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "original"
            with mock.patch.object(module, "original_tables", return_value=(fixture(), b"[]\n")):
                with contextlib.redirect_stdout(io.StringIO()):
                    module.reproduce(root / "unused", None, original)
            name = "complete-minnesota-native-query.zip"
            extracted = root / "extracted"
            with zipfile.ZipFile(original / name) as archive:
                archive.extractall(extracted)
            rebuilt = root / "rebuilt"
            subprocess.run([
                sys.executable, str(extracted / "review-minnesota-bulk-participation.py"),
                "--snapshot", str(extracted), "--output", str(rebuilt),
            ], check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({path.name for path in original.iterdir()},
                             {path.name for path in rebuilt.iterdir()})
            for path in original.iterdir():
                self.assertEqual(path.read_bytes(), (rebuilt / path.name).read_bytes(), path.name)

    def test_flag_one_zero_is_actual_and_candidate_votes_never_replace_participation(self):
        tables = fixture()
        tables["county-results"][0][13] = "7"
        row = records(module.review(tables)["county-participation.csv"])[0]
        self.assertEqual(row["complete_total_number_voted"], "9")
        self.assertEqual(row["reported_statistics"], "2")
        self.assertEqual(row["eligible_for_registration_fraction_review"], "true")
        self.assertEqual(row["native_fips"], "")
        self.assertEqual(row["native_update_clock"], "")
        self.assertEqual(row["maps_approved"], "false")

    def test_unreported_zero_and_nonzero_never_complete_county_or_electorate(self):
        for native_voted in ("0", "200"):
            tables = fixture()
            tables["pctstats"][1][4] = "0"
            tables["pctstats"][1][11] = native_voted
            row = records(module.review(tables)["county-participation.csv"])[0]
            self.assertEqual(row["reported_total_number_voted_subtotal"], "9")
            self.assertEqual(row["complete_total_number_voted"], "")
            self.assertEqual(row["derived_complete_7am_plus_election_day_registrations"], "")
            self.assertEqual(row["eligible_for_registration_fraction_review"], "false")

    def test_conflicts_and_electorate_excesses_preserve_native_totals_and_block_rate_review(self):
        tables = fixture()
        tables["pctstats"][0][11] = "11"
        result = module.review(tables)
        row = records(result["county-participation.csv"])[0]
        self.assertEqual(row["complete_total_number_voted"], "11")
        self.assertEqual(row["eligible_for_registration_fraction_review"], "false")
        self.assertEqual(records(result["statistic-component-residuals.csv"])[0]
                         ["total_minus_roster_and_three_absentee_fields"], "2")
        self.assertEqual(records(result["statistic-electorate-excesses.csv"])[0]
                         ["voted_minus_7am_and_election_day_registrations"], "1")

    def test_precinct_identity_is_county_scoped_and_reference_complete(self):
        tables = fixture()
        tables["counties"].append(["02", "Other county", "1"])
        tables["precincts"].append(["02"] + tables["precincts"][0][1:])
        tables["pctstats"].append(["MN", "02"] + tables["pctstats"][0][2:])
        self.assertEqual(len(records(module.review(tables)["county-participation.csv"])), 2)
        for mutate in ("duplicate", "missing", "unknown_flag"):
            changed = copy.deepcopy(tables)
            if mutate == "duplicate":
                changed["pctstats"].append(changed["pctstats"][0])
            elif mutate == "missing":
                changed["precincts"].pop()
            else:
                changed["pctstats"][0][4] = "2"
            with self.assertRaises(ValueError):
                module.review(changed)

    def test_estimated_question_blanks_remain_literal_choice_residual_not_actual_blanks(self):
        tables = fixture()
        tables["county-results"][0][3:11] = [
            "0351", "Constitutional Amendment", "", "9003", "ESTIMATED BLANKS", "", "", "NP"]
        result = module.review(tables)
        residuals = records(result["county-choice-reconciliation.csv"])
        blank = next(row for row in residuals if row["candidate_name"] == "ESTIMATED BLANKS")
        self.assertEqual(blank["party_abbreviation"], "NP")
        self.assertEqual(blank["county_minus_precinct_sum"], "9")
        self.assertEqual(records(result["county-participation.csv"])[0]
                         ["complete_total_number_voted"], "9")


if __name__ == "__main__":
    unittest.main()

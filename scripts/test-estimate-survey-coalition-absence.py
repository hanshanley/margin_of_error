import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile


spec = importlib.util.spec_from_file_location(
    "absence", Path(__file__).with_name("estimate-survey-coalition-absence.py"))
absence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(absence)


def workbook(path, *, missing=False, duplicate=False, wrong_candidate=False, wrong_total=False):
    uri = absence.NS["s"]
    q = lambda name: f"{{{uri}}}{name}"
    book = ET.Element(q("workbook"))
    ET.SubElement(ET.SubElement(book, q("sheets")), q("sheet"), name="OFFICIAL 2024 PRES GE RESULTS")
    strings = ["STATE", "HARRIS", "TRUMP", "TOTAL VOTES", "Total:"] + absence.CODES
    ss = ET.Element(q("sst"))
    for text in strings:
        ET.SubElement(ET.SubElement(ss, q("si")), q("t")).text = text
    sheet = ET.Element(q("worksheet"))
    data = ET.SubElement(sheet, q("sheetData"))
    rows = [{"A": "STATE", "M": "TRUMP" if wrong_candidate else "HARRIS",
             "Y": "TRUMP", "AE": "TOTAL VOTES"}]
    states = absence.CODES[:-1] if missing else absence.CODES
    rows += [{"A": code, "M": 100, "Y": 200, "AE": 350} for code in states]
    if duplicate:
        rows.append(rows[1])
    n = len(states)
    rows.append({"A": "Total:", "M": n * 100 + int(wrong_total), "Y": n * 200, "AE": n * 350})
    for number, cells in enumerate(rows, 1):
        row = ET.SubElement(data, q("row"), r=str(number))
        for column, value in cells.items():
            cell = ET.SubElement(row, q("c"), r=f"{column}{number}")
            if isinstance(value, str):
                cell.set("t", "s")
                value = strings.index(value)
            ET.SubElement(cell, q("v")).text = str(value)
    with zipfile.ZipFile(path, "w") as archive:
        for name, element in [("xl/workbook.xml", book), ("xl/sharedStrings.xml", ss),
                              ("xl/worksheets/sheet1.xml", sheet)]:
            archive.writestr(name, ET.tostring(element))


class AbsenceTests(unittest.TestCase):
    def test_user_hypothetical_uses_original_coalition_denominators(self):
        row = absence.coalition(1000000, 1000000, 60, 10)
        self.assertEqual(row["returning_count"], 600000)
        self.assertEqual(row["reported_switcher_count"], 60000)
        self.assertEqual(row["apparent_absence_count"], 400000)
        self.assertEqual(row["reported_switchers_pct_of_original_coalition"], 6)
        self.assertEqual(row["apparent_absence_pct_of_original_coalition"], 40)

    def test_presidential_headers_coverage_duplicates_and_national_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "official.xlsx"
            workbook(path)
            self.assertEqual(len(absence.fec_baselines(path)), 51)
            self.assertEqual(absence.fec_baselines(path)["NC"]["R"], 200)
            for keyword in ["missing", "duplicate", "wrong_candidate", "wrong_total"]:
                workbook(path, **{keyword: True})
                with self.assertRaises(ValueError):
                    absence.fec_baselines(path)

    def test_negative_residual_is_not_clamped_or_treated_as_negative_people(self):
        row = absence.coalition(100, 1000, 20, 10)
        self.assertEqual(row["apparent_absence_count"], -100)
        self.assertTrue(row["infeasible_as_closed_original_coalition"])

    def test_unknown_and_invalid_inputs_do_not_become_zero(self):
        for values in [(100, None, 60, 10), (100, 100, -1, 10),
                       (100, 100, 60, -1), (100, 100, math.nan, 10),
                       (True, 100, 60, 10), (0, 100, 60, 10)]:
            with self.assertRaises(ValueError):
                absence.coalition(*values)

    def test_joint_scope_and_balanced_sensitivity_remain_separate_from_dropoff(self):
        table = {
            "state_code": "NC", "contest_code": "SG", "subset": {"sub": 0},
            "status": "published_joint_question_reviewed",
            "source_url": "source", "source_sha256": "digest",
            "source_timestamp": "2026-11-04T00:00:00Z", "source_reported_respondents": 4000,
            "reported_composition_sum_pct": 100,
            "joint_question_rows": {
                "R": {"prior_choice_share_pct": 40, "current_choice_pct_within_prior_choice": {"D": 10}},
                "D": {"prior_choice_share_pct": 50, "current_choice_pct_within_prior_choice": {"R": 2}},
            },
        }
        reporting = {"state_code": "NC", "status": "reported", "quality": [], "ballots": 1000}
        result = absence.estimate(table, {"D": 900, "R": 1000}, reporting)
        self.assertEqual(len(result["sensitivity_scenarios"]), 9)
        self.assertIn("not_validated_dropoff", result["status"])
        self.assertEqual(result["reference"]["R"]["reported_switcher_count"], 40)
        self.assertIsNone(result["reference"]["R"]["reported_same_party_count"])
        scope = result["response_scope_sensitivity"][-1]
        self.assertEqual(scope["marginal_coalition_envelopes"]["R"]["returning_count"], [380, 430])
        self.assertEqual(scope["marginal_coalition_envelopes"]["R"]["reported_switcher_count"], [38, 88])
        self.assertEqual(scope["marginal_coalition_envelopes"]["R"]["apparent_absence_count"], [570, 620])
        for scenario in result["sensitivity_scenarios"]:
            coalitions = scenario["coalitions"]
            n = 1000 * scenario["current_ballot_count_scale"]
            self.assertAlmostEqual(sum(c["returning_count"] for c in coalitions.values()), n * .9)
        wrong = copy.deepcopy(table)
        wrong["subset"]["sub"] = 53
        with self.assertRaises(ValueError):
            absence.estimate(wrong, {"D": 900, "R": 1000}, reporting)
        reporting["quality"] = ["partial_scope"]
        with self.assertRaises(ValueError):
            absence.estimate(table, {"D": 900, "R": 1000}, reporting)

    def test_zero_reported_switching_has_positive_rounding_upper_bound(self):
        result = absence.rounding_envelope(1000, 1000, 40, 0)
        self.assertEqual(result["reported_switcher_count"], [0, 2.025])
        self.assertEqual(result["apparent_absence_count"], [595, 605])
        self.assertIsNone(absence.rounding_envelope(1000, 1000, 40.2, 1))

    def test_nonvote_other_and_missing_choice_accounting_does_not_invent_first_voters(self):
        root = Path(__file__).resolve().parents[1]
        tables = json.loads((root / "public/participation-survey/20261107-02/joint-table-review.json").read_text())["tables"]
        table = next(row for row in tables if row["state_code"] == "DE"
                     and row["contest_code"] == "SG" and row["subset"]["sub"] == 0)
        reporting = {"state_code": "DE", "status": "reported", "quality": [], "ballots": 1000}
        result = absence.estimate(table, {"D": 900, "R": 1000}, reporting)
        composition = result["current_electorate_composition"]
        self.assertEqual(composition["N"]["conditional_current_electorate_count"], 30)
        self.assertEqual(composition["N"]["reported_current_choice_counts"], {"D": None, "R": None})
        self.assertEqual(result["signed_composition_rounding_difference_pct"], 1)
        self.assertEqual(sum(row["conditional_current_electorate_count"] for row in composition.values()), 990)
        identification = result["participation_entry_identification"]
        self.assertTrue(identification["all_four_prior_choice_categories_present"])
        self.assertFalse(identification["complete_participation_entry_exit_decomposition"])
        for key in ("first_ever_voters", "newly_registered_current_voters",
                    "newly_eligible_current_voters", "previously_eligible_nonparticipants",
                    "current_voters_without_prior_ballot"):
            self.assertIsNone(identification[key])
        self.assertNotIn("N", result["reference"])

    def test_partial_categories_and_overfull_composition_are_not_zero_filled_or_normalized(self):
        rows = {
            "D": {"prior_choice_share_pct": 50, "current_choice_pct_within_prior_choice": {"D": 97, "R": 4}},
            "R": {"prior_choice_share_pct": 51, "current_choice_pct_within_prior_choice": {"R": 90}},
        }
        original = copy.deepcopy(rows)
        result = absence.electorate_accounting(rows, 1000)
        self.assertEqual(result["signed_composition_rounding_difference_pct"], -1)
        self.assertEqual(set(result["current_electorate_composition"]), {"D", "R"})
        self.assertFalse(result["participation_entry_identification"]["all_four_prior_choice_categories_present"])
        self.assertEqual(result["current_electorate_composition"]["D"]["reported_current_choice_counts"],
                         {"D": 485, "R": 20})
        self.assertEqual(rows, original)
        for category, field, value in (("D", "prior_choice_share_pct", True),
                                       ("R", "prior_choice_share_pct", math.nan)):
            changed = copy.deepcopy(rows)
            changed[category][field] = value
            with self.assertRaises(ValueError):
                absence.electorate_accounting(changed, 1000)
        changed = copy.deepcopy(rows)
        changed["R"]["current_choice_pct_within_prior_choice"]["D"] = 101
        with self.assertRaises(ValueError):
            absence.electorate_accounting(changed, 1000)
        with self.assertRaises(ValueError):
            absence.electorate_accounting({**rows, "unknown_code": {}}, 1000)

    def test_reviewed_native_snapshots_keep_every_warning_and_false_approval(self):
        root = Path(__file__).resolve().parents[1]
        inputs = json.loads((root / "data/participation-coalition-scenarios/20261107-02/participation-input.json").read_text())
        tables = json.loads((root / "public/participation-survey/20261107-02/joint-table-review.json").read_text())["tables"]
        for native in inputs["reviewed_scaling_observations"]:
            original = copy.deepcopy(native)
            table = next(row for row in tables if row["state_code"] == native["state_code"]
                         and row["contest_code"] == "SG" and row["subset"]["sub"] == 0)
            with self.assertRaises(ValueError):
                absence.estimate(table, {"D": 9000000, "R": 9000000}, native)
            result = absence.estimate_reviewed_snapshot(table, {"D": 9000000, "R": 9000000}, native)
            self.assertEqual(native, original)
            self.assertEqual(result["turnout_source"], original)
            self.assertTrue(result["turnout_source"]["quality"])
            self.assertFalse(result["turnout_input_qualification"]["all_ballot_population_scope_confirmed"])
            self.assertFalse(result["turnout_input_qualification"]["native_source_approval_flags_changed"])
            if native["state_code"] == "DE":
                self.assertEqual(result["turnout_source"]["native_record"]["all_mode_complete"], "False")
                self.assertEqual(result["turnout_source"]["native_source_updates"], [])
                self.assertEqual(result["turnout_source"]["native_record"]["native_update_clock"], "")

    def test_changed_reviewed_records_and_unsupported_voter_turnout_fail_closed(self):
        root = Path(__file__).resolve().parents[1]
        inputs = json.loads((root / "data/participation-coalition-scenarios/20261107-02/participation-input.json").read_text())
        native = inputs["reviewed_scaling_observations"][0]
        for field, value in [("quality", []), ("ballots", native["ballots"] + 1),
                             ("source_date", "invented clock"), ("state_code", "CA")]:
            changed = copy.deepcopy(native)
            changed[field] = value
            with self.assertRaises(ValueError):
                absence.validate_reviewed_snapshot(changed)
        with self.assertRaises(ValueError):
            absence.validate_reviewed_snapshot(inputs["scope_withholdings"][0]["native_observation"])


if __name__ == "__main__":
    unittest.main()

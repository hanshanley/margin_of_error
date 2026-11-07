import copy
import importlib.util
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


if __name__ == "__main__":
    unittest.main()

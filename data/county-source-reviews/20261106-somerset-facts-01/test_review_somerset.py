import copy
import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("somerset", HERE / "review-somerset.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FACTS = json.loads((HERE / "native-facts.json").read_text())


class SomersetTests(unittest.TestCase):
    def test_partial_modes_cannot_be_filled_with_zero(self):
        with self.assertRaisesRegex(ValueError, "Missing native participation"):
            module.participation(
                "Registered Voters - Total 127 Ballots Cast - Total 71 57 14 "
                "Ballots Cast - Blank 0 0 0 0 Voter Turnout - Total 55.91%")

    def test_unknown_column_content_is_not_discarded(self):
        with self.assertRaisesRegex(ValueError, "column inventory"):
            module.columns("TOTAL Election Day Absentee/Mail-In Provisional 123")

    def test_primary_election_cannot_pass_general_identity(self):
        with self.assertRaisesRegex(ValueError, "election/report identity"):
            module.page_body(
                "Summary Results Report 2026 General Primary May 19, 2026 "
                "Somerset County UNOFFICIAL RESULTS EMS Report "
                "- 11/03/2026 11:03 PM Page 1 of 3 "
                "Report generated with Electionware Copyright \u00a9 2007-2020",
                "summary", 1)

    def test_statistics_must_match_each_native_unit(self):
        changed = copy.deepcopy(FACTS)
        changed["reports"]["statistics"][0]["rows"][0]["ballots_literal"] = "72"
        with self.assertRaisesRegex(ValueError, "Statistics and precinct reports disagree"):
            module.validate(changed)

    def test_equal_percentages_keep_distinct_native_precision(self):
        tables = module.tables(FACTS)
        custom = next(row for row in tables["statistics-crosscheck.csv"]
                      if row["unit_literal"] == "Jefferson Township")
        statement = next(row for row in tables["native-unit-participation.csv"]
                         if row["unit_literal"] == "Jefferson Township"
                         and row["counting_mode_literal"] == "TOTAL")
        self.assertNotEqual(custom["native_printed_turnout"], statement["native_printed_turnout"])
        self.assertEqual(float(custom["native_printed_turnout"][:-1]),
                         float(statement["native_printed_turnout"][:-1]))

    def test_candidate_rollup_cannot_hide_a_reconciling_mode_change(self):
        changed = copy.deepcopy(FACTS)
        row = changed["reports"]["statement"][0]["contests"][0]["rows"][0]
        row["count_literals"] = ["31", "22", "9", "0"]
        with self.assertRaisesRegex(ValueError, "Unit and county candidate counts disagree"):
            module.validate(changed)

    def test_extra_unit_choice_cannot_escape_county_rollup(self):
        changed = copy.deepcopy(FACTS)
        contest = changed["reports"]["statement"][0]["contests"][0]
        extra = copy.deepcopy(contest["rows"][0])
        extra["label_literal"] = "DEM Unreported Choice"
        extra["choice_literal"] = "Unreported Choice"
        contest["rows"].append(extra)
        with self.assertRaisesRegex(ValueError, "Unknown, duplicate or missing unit choice"):
            module.validate(changed)

    def test_report_clocks_do_not_acquire_an_inferred_timezone(self):
        changed = copy.deepcopy(FACTS)
        changed["reports"]["statement"][0]["declared_timezone"] = "Eastern"
        with self.assertRaisesRegex(ValueError, "source qualifications"):
            module.validate(changed)

    def test_candidate_votes_and_absent_accounting_do_not_replace_ballots(self):
        tables = module.tables(FACTS)
        governor = next(row for row in tables["county-contest-accounting.csv"]
                        if row["contest_literal"] == module.TITLES[0]
                        and row["counting_mode_literal"] == "TOTAL")
        self.assertNotEqual(governor["derived_choice_sum"],
                            tables["county-participation.csv"][0]["ballots_cast"])
        for row in tables["county-contest-accounting.csv"]:
            for field in ("native_total_votes_cast", "native_contest_totals",
                          "native_overvotes", "native_undervotes", "registered_voters"):
                self.assertEqual(row[field], "")

    def test_native_reporting_counter_conflicts_are_retained(self):
        rows = module.tables(FACTS)["native-reporting-statistics.csv"]
        mail = next(row for row in rows if row["label_literal"] == module.REPORTING[3])
        self.assertNotEqual(mail["reported"], mail["native_mail_column"])
        complete = next(row for row in rows if row["label_literal"] == module.REPORTING[1])
        self.assertEqual(complete["reported"], 0)
        self.assertGreater(complete["total"], 0)

    def test_write_ins_never_acquire_literal_parties(self):
        changed = copy.deepcopy(FACTS)
        changed["reports"]["summary"][1]["contests"][0]["rows"][-1]["literal_party"] = "DEM"
        with self.assertRaisesRegex(ValueError, "Write-ins cannot acquire a party"):
            module.validate(changed)
        parties = module.tables(FACTS)["county-literal-party-totals.csv"]
        self.assertFalse(any(row["choice_literal"] == "Write-In Totals" for row in parties))

    def test_registrations_are_not_mode_denominators(self):
        rows = module.tables(FACTS)["native-participation-modes.csv"]
        self.assertTrue(all(row["registered_voters"] == "" for row in rows
                            if row["counting_mode_literal"] != "TOTAL"))


if __name__ == "__main__":
    unittest.main()

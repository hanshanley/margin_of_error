import copy
import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("county_summary", HERE / "review-three-additional-pa-summaries.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
fixture = HERE / "native-facts.json"
if not fixture.exists():
    fixture = HERE.parent / "data/county-source-reviews/20261106-three-pa-summary-facts-01/native-facts.json"
FACTS = json.loads(fixture.read_text())


class CountySummaryTests(unittest.TestCase):
    def test_pdf_percentage_before_label_keeps_same_native_participation(self):
        prefix = ("Registered Voters - Total 803 Ballots Cast - Total 354 286 68 0 "
                  "Ballots Cast - Blank 0 0 0 0 ")
        first, _ = module.statistics(prefix + "Voter Turnout - Total 44.08%", "Schuylkill")
        second, _ = module.statistics(prefix + "44.08%Voter Turnout - Total", "Schuylkill")
        self.assertEqual(first, second)

    def test_partial_modes_cannot_be_filled_with_zero(self):
        with self.assertRaises(ValueError):
            module.statistics("Registered Voters - Total 803 Ballots Cast - Total 354 286 68 "
                              "Ballots Cast - Blank 0 0 0 Voter Turnout - Total 44.08%", "Schuylkill")

    def test_native_mode_totals_must_reconcile(self):
        with self.assertRaises(ValueError):
            module.integers(["354", "286", "69", "0"])

    def test_total_only_source_does_not_acquire_invented_modes(self):
        facts, tail = module.statistics(
            "Registered Voters - Total 51 Ballots Cast - Total 31 "
            "Ballots Cast - Blank 0 Voter Turnout - Total 60.78%", "Indiana")
        self.assertEqual(facts["ballot_literals"], ["31"])
        self.assertEqual(tail, "")
        with self.assertRaises(ValueError):
            module.integers(["31", "31"])

    def test_unrecognized_column_content_is_not_silently_discarded(self):
        with self.assertRaises(ValueError):
            module.header_columns("TOTAL Election Day Mail Votes Provisional 123")

    def test_primary_or_wrong_year_cannot_pass_general_identity(self):
        text = ("Summary Results Report UNOFFICIAL RESULTS 2026 General Election "
                "November 3, 2024 Indiana County "
                "Election Summary - 11/03/2026 10:03 PM 1 of 2")
        with self.assertRaises(ValueError):
            module.page_body(text, "Indiana", "summary", 1)

    def test_precinct_report_cannot_be_presented_as_county_summary(self):
        text = ("Summary Results Report UNOFFICIAL RESULTS 2026 General Election "
                "November 3, 2026 Indiana County "
                "Precinct Summary - 11/03/2026 10:03 PM 1 of 2")
        with self.assertRaises(ValueError):
            module.page_body(text, "Indiana", "summary", 1)

    def test_native_mode_and_accounting_absence_survives_csv_conversion(self):
        tables = module.tables(FACTS)
        indiana = [row for row in tables["native-participation-modes.csv"] if row["county"] == "Indiana"]
        self.assertEqual(len(indiana), 1)
        for row in tables["county-contest-accounting.csv"]:
            if row["county"] in ("Indiana", "Schuylkill"):
                self.assertEqual(row["native_overvotes"], "")
                self.assertEqual(row["native_undervotes"], "")
            if row["county"] == "Schuylkill":
                self.assertEqual(row["native_contest_totals"], "")
                self.assertEqual(row["native_total_votes_cast"], "")

    def test_ballot_questions_and_write_ins_do_not_acquire_parties(self):
        tables = module.tables(FACTS)
        excluded = [row for row in tables["county-candidate-results.csv"]
                    if row["choice_kind"] != "candidate"]
        self.assertTrue(excluded)
        self.assertTrue(all(row["literal_party"] == "" for row in excluded))
        party = tables["county-literal-party-totals.csv"]
        self.assertTrue(all(row["choice_kind"] == "candidate" for row in party))
        self.assertTrue(all(row["literal_party"] in ("DEM", "REP", "LIB") for row in party))

    def test_native_reporting_contradictions_are_preserved(self):
        reports = module.tables(FACTS)["native-reporting-statistics.csv"]
        row = next(row for row in reports if row["county"] == "Lackawanna"
                   and row["label_literal"] == "Election Day Precincts Reporting")
        self.assertGreater(row["native_election_day_column"] + row["native_provisional_column"],
                           row["reported"])
        absent = next(row for row in reports if row["county"] == "Indiana")
        self.assertEqual(absent["native_election_day_column"], "")

    def test_native_unit_and_county_changes_break_frozen_review(self):
        changed = copy.deepcopy(FACTS)
        changed["counties"]["Indiana"]["unit_participation"][0]["ballot_literals"][0] = "30"
        with self.assertRaises(ValueError):
            module.validate(changed)

    def test_restricted_contests_have_no_borrowed_registration_denominator(self):
        rows = module.tables(FACTS)["county-contest-accounting.csv"]
        self.assertTrue(any("CITY OF CARBONDALE" in row["contest_literal"] for row in rows))
        self.assertTrue(all("registered_voters" not in row for row in rows))

    def test_native_rounding_conflict_is_flagged_without_correcting_source(self):
        rows = module.tables(FACTS)["native-unit-participation.csv"]
        conflicts = [row for row in rows if row["printed_turnout_rounding_conflict"] is True]
        self.assertEqual(len(conflicts), 1)
        row = conflicts[0]
        self.assertEqual(row["native_printed_turnout"], "55.42%")
        self.assertGreater(100 * row["ballots_cast"] / row["registered_voters"], 55.425)


if __name__ == "__main__":
    unittest.main()

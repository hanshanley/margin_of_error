import copy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/participation-estimated-coalitions/20261107-01"
spec = importlib.util.spec_from_file_location(
    "preliminary", Path(__file__).with_name("estimate-preliminary-coalitions.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PreliminaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.totals = module.read_turnout(
            DATA / "Turnout_2026G_v0.2.csv", DATA / "Turnout_2026G_v0.1_doc.txt")
        cls.tables = json.loads((ROOT / "public/participation-survey/20261107-02/joint-table-review.json").read_text())["tables"]
        cls.baselines = module.math.fec_baselines(
            ROOT / "data/participation-coalition-scenarios/20261107-02/official-2024.xlsx")

    def table(self, code, contest="SG"):
        return next(copy.deepcopy(row) for row in self.tables if row["state_code"] == code
                    and row["contest_code"] == contest and row["subset"]["sub"] == 0)

    def test_native_coverage_reconciliation_mixed_commas_and_unknowns(self):
        self.assertEqual(self.totals["US"]["ballots"],
                         sum(self.totals[code]["ballots"] for code in module.math.CODES))
        self.assertEqual(self.totals["AR"]["native_record"]["TOTAL_BALLOTS_COUNTED"], "895,000")
        self.assertEqual(self.totals["AR"]["ballots"], 895000)
        with (DATA / "Turnout_2026G_v0.2.csv").open() as stream:
            original = list(csv.DictReader(stream))
        for field, value in [("STATE_ABV", "XX"), ("TOTAL_BALLOTS_COUNTED", ""),
                             ("TOTAL_BALLOTS_COUNTED", "0"), ("TOTAL_BALLOTS_COUNTED", "-1"),
                             ("TOTAL_BALLOTS_COUNTED", "8,95,000"), ("SOURCE", "Certified")]:
            rows = copy.deepcopy(original)
            rows[1][field] = value
            with self.assertRaises(ValueError):
                module.parse_rows(rows)
        for rows in [original[:-1], original + [original[1]]]:
            with self.assertRaises(ValueError):
                module.parse_rows(rows)
        rows = copy.deepcopy(original)
        rows[0]["TOTAL_BALLOTS_COUNTED"] = str(int(rows[0]["TOTAL_BALLOTS_COUNTED"]) + 1)
        with self.assertRaises(ValueError):
            module.parse_rows(rows)

    def test_unreviewed_native_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "changed.csv"
            path.write_bytes((DATA / "Turnout_2026G_v0.2.csv").read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                module.read_turnout(path, DATA / "Turnout_2026G_v0.1_doc.txt")

    def test_refreshed_source_requires_explicit_reviewed_version_and_exact_bytes(self):
        refreshed = ROOT / "data/participation-estimated-coalitions/20261107-03"
        csv_path = refreshed / "Turnout_2026G_v0.2.csv"
        doc_path = refreshed / "Turnout_2026G_v0.1_doc.txt"
        for version in ("20261107-01", "unreviewed"):
            with self.assertRaises(ValueError):
                module.read_turnout(csv_path, doc_path, version)
        with self.assertRaises(ValueError):
            module.read_turnout(DATA / "Turnout_2026G_v0.2.csv", doc_path, "20261107T055406Z")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "changed.csv"
            path.write_bytes(csv_path.read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                module.read_turnout(path, doc_path, "20261107T055406Z")
            path.write_bytes(doc_path.read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                module.read_turnout(csv_path, path, "20261107T055406Z")

    def test_refreshed_national_scope_and_unchanged_supported_states(self):
        refreshed = ROOT / "data/participation-estimated-coalitions/20261107-03"
        totals = module.read_turnout(refreshed / "Turnout_2026G_v0.2.csv",
                                    refreshed / "Turnout_2026G_v0.1_doc.txt", "20261107T055406Z")
        baseline, turnout = module.national_inputs(totals, self.baselines)
        result = module.calculate(self.table("US", "HG"), baseline, turnout)
        self.assertEqual(turnout["ballots"], 123317000)
        self.assertEqual(turnout["native_national_ballots"] - turnout["excluded_dc_ballots"], 123317000)
        self.assertEqual(totals["WA"]["ballots"], 3250000)
        old_baseline, old_turnout = module.national_inputs(self.totals, self.baselines)
        previous = module.calculate(self.table("US", "HG"), old_baseline, old_turnout)
        for prior, returning, switched in (("R", 22000, 1540), ("D", 24500, 490)):
            self.assertAlmostEqual(result["reference"][prior]["returning_count"]
                                   - previous["reference"][prior]["returning_count"], returning)
            self.assertAlmostEqual(result["reference"][prior]["reported_switcher_count"]
                                   - previous["reference"][prior]["reported_switcher_count"], switched)
        for table in self.tables:
            if (table["subset"]["sub"] == 0 and table["state_code"] != "US"
                    and table["status"] == "published_joint_question_reviewed"):
                code = table["state_code"]
                self.assertEqual(module.calculate(table, self.baselines[code], totals[code]),
                                 module.calculate(table, self.baselines[code], self.totals[code]))

    def test_source_denominators_and_symmetric_stress_without_mutation(self):
        table, turnout = self.table("NC"), copy.deepcopy(self.totals["NC"])
        original = copy.deepcopy((table, turnout))
        result = module.calculate(table, self.baselines["NC"], turnout)
        expected = 4245000 * .43
        self.assertAlmostEqual(result["reference"]["R"]["returning_count"], expected)
        self.assertAlmostEqual(result["reference"]["R"]["reported_switcher_count"], expected * .10)
        self.assertAlmostEqual(result["reference"]["R"]["apparent_absence_count"], 2898423 - expected)
        self.assertEqual({row["estimated_total_scale"] for row in result["sensitivity_scenarios"]}, {.95, 1, 1.05})
        for row in result["sensitivity_scenarios"]:
            self.assertAlmostEqual(sum(c["returning_count"] for c in row["coalitions"].values()),
                                   4245000 * row["estimated_total_scale"] * .92)
        self.assertEqual((table, turnout), original)

    def test_prior_nonvote_is_current_composition_not_first_time_or_imputed_choice(self):
        result = module.calculate(self.table("DE"), self.baselines["DE"], self.totals["DE"])
        nonvote = result["current_electorate_composition"]["N"]
        self.assertAlmostEqual(nonvote["conditional_current_electorate_count"], 383000 * .03)
        self.assertEqual(nonvote["reported_current_choice_counts"], {"D": None, "R": None})
        self.assertNotIn("first_time_voter_count", result)
        self.assertEqual(result["signed_composition_rounding_difference_pct"], 1)
        identification = result["participation_entry_identification"]
        self.assertTrue(identification["all_four_prior_choice_categories_present"])
        self.assertIsNone(identification["first_ever_voters"])
        self.assertIsNone(identification["previously_eligible_nonparticipants"])
        self.assertFalse(identification["complete_participation_entry_exit_decomposition"])

    def test_negative_absence_and_overfull_rounding_are_diagnostics_not_clamped(self):
        table = self.table("NC")
        table["joint_question_rows"]["N"]["prior_choice_share_pct"] = 7
        table["reported_composition_sum_pct"] = 101
        result = module.calculate(table, {"D": 1, "R": 1}, self.totals["NC"])
        self.assertLess(result["reference"]["R"]["apparent_absence_count"], 0)
        self.assertTrue(result["reference"]["R"]["infeasible_as_closed_original_coalition"])
        self.assertEqual(result["signed_composition_rounding_difference_pct"], -1)
        self.assertEqual(result["current_electorate_composition"]["N"]["reported_share_pct_of_current_electorate"], 7)

    def test_wrong_state_subgroup_composition_or_status_never_released(self):
        table = self.table("NC")
        for field, value in [("status", "withheld_joint_composition_incomplete"),
                             ("subset", {"sub": 1}), ("state_code", "GA"),
                             ("reported_composition_sum_pct", 90)]:
            changed = copy.deepcopy(table)
            changed[field] = value
            with self.assertRaises(ValueError):
                module.calculate(changed, self.baselines["NC"], self.totals["NC"])
        for rows in ({key: value for key, value in table["joint_question_rows"].items() if key != "N"},
                     {**table["joint_question_rows"], "unknown_code": {}}):
            changed = copy.deepcopy(table)
            changed["joint_question_rows"] = rows
            with self.assertRaises(ValueError):
                module.calculate(changed, self.baselines["NC"], self.totals["NC"])

    def test_national_house_uses_actual_national_population_not_a_state_allocation(self):
        baseline, turnout = module.national_inputs(self.totals, self.baselines)
        result = module.calculate(self.table("US", "HG"), baseline, turnout)
        self.assertEqual(result["preliminary_turnout"]["native_record"]["STATE_ABV"], "US")
        self.assertEqual(result["official_2024_baseline"]["R"], 77302580 - self.baselines["DC"]["R"])
        self.assertEqual(result["official_2024_baseline"]["D"], 75017613 - self.baselines["DC"]["D"])
        self.assertEqual(result["preliminary_turnout"]["ballots"], 123490000 - 223000)
        self.assertEqual(result["preliminary_turnout"]["native_record"], self.totals["US"]["native_record"])
        self.assertAlmostEqual(result["reference"]["R"]["reported_switcher_count"], 123267000 * .0308)
        with self.assertRaises(ValueError):
            module.calculate(self.table("US", "HG"), baseline, self.totals["US"])
        table = self.table("US", "HG")
        table["contest_code"] = "SG"
        with self.assertRaises(ValueError):
            module.calculate(table, baseline, turnout)


if __name__ == "__main__":
    unittest.main()

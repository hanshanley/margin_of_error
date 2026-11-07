import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "counts", Path(__file__).with_name("estimate-demographic-current-counts.py"))
counts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(counts)


class DemographicCountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((ROOT / counts.DATA / "selected-source-tables.json").read_text())
        cls.items = {
            (x["configuration_entry"]["stateAbbr"], x["configuration_entry"]["raceTypeCode"],
             x["configuration_entry"]["subsetNumber"]): x for x in cls.snapshot["sources"]}
        cls.totals = counts.turnout.read_turnout(
            ROOT / counts.UF / "Turnout_2026G_v0.2.csv",
            ROOT / counts.UF / "Turnout_2026G_v0.1_doc.txt")
        cls.output = counts.estimate(cls.snapshot, cls.totals)

    def row(self, code, contest, sub):
        return next(r for r in self.output["estimates"]
                    if (r["state_code"], r["contest_code"], r["subset"]["sub"]) == (code, contest, sub))

    def test_matched_joint_factorization_and_no_historical_denominator(self):
        row = self.row("NC", "SG", 20)
        self.assertEqual(row["estimated_current_group_count"], 1910250)
        self.assertAlmostEqual(row["composition"]["R"]["reported_current_choice_counts"]["D"], 74881.8)
        self.assertAlmostEqual(row["composition"]["D"]["reported_current_choice_counts"]["R"], 8214.075)
        for field in ("original_2024_group_coalition_baseline", "group_dropoff_estimate",
                      "demographic_turnout_rate", "share_of_total_swing", "design_confidence_interval"):
            self.assertIsNone(row[field])

    def test_exact_overlapping_age_definition_not_summed_rounded_marginals(self):
        row = self.row("US", "HG", 54)
        self.assertEqual(row["population_match"]["question_id"], 1949)
        self.assertEqual(row["population_match"]["group_share_pct_of_current_electorate"], 30)
        self.assertEqual(row["estimated_current_group_count"], 36980100)
        native = self.items[("US", "HG", 0)]
        q = counts.question(native, 159, "Age")
        self.assertEqual(counts.answer(q, "18-29") + counts.answer(q, "30-44"), 31)

    def test_national_excludes_dc_and_unsupported_modes_stay_withheld(self):
        national = [r for r in self.output["estimates"] if r["state_code"] == "US"]
        self.assertTrue(national)
        self.assertTrue(all(r["estimated_electorate_total"] == 123267000 for r in national))
        self.assertEqual(self.output["native_national_turnout"]["ballots"], 123490000)
        self.assertEqual(self.totals["DC"]["ballots"], 223000)
        mode = [r for r in self.output["source_group_dispositions"] if r["subset"]["sub"] in (51, 52)]
        self.assertTrue(mode)
        self.assertTrue(all(r["status"] == "withheld_no_matched_population_question" for r in mode))
        self.assertEqual(len(self.output["jurisdictions"]), 51)

    def test_suppressed_conditional_choices_remain_null(self):
        row = self.row("NC", "SG", 54)
        self.assertEqual(row["composition"]["O"]["estimated_current_group_count"], 38205)
        self.assertEqual(row["composition"]["O"]["reported_current_choice_counts"], {"D": None, "R": None})

    def test_population_suppression_and_subgroup_identity_fail_closed(self):
        main, group = self.items[("NC", "SG", 0)], self.items[("NC", "SG", 20)]
        changed = copy.deepcopy(main)
        counts.question(changed, 11001, "Gender")["answers"][0]["totalPercentage"] = -1
        self.assertEqual(counts.population_match(changed, group)["status"], "withheld_suppressed_population_share")
        changed = copy.deepcopy(group)
        counts.question(changed, 11001, "Gender")["answers"][0]["totalPercentage"] = 99
        self.assertEqual(counts.population_match(main, changed)["status"], "withheld_subgroup_identity_mismatch")
        changed = copy.deepcopy(main)
        changed["selected_demographic_questions"] = []
        self.assertEqual(counts.population_match(changed, group)["status"], "withheld_missing_population_question")

    def test_different_contest_or_revision_cannot_be_combined(self):
        main, group = self.items[("NC", "SG", 0)], self.items[("NC", "SG", 20)]
        for change in ("contest", "timestamp"):
            changed = copy.deepcopy(main)
            if change == "contest":
                changed["configuration_entry"]["raceTypeCode"] = "GG"
            else:
                changed["selected_native_data"]["timestamp"] = "2026-11-03T00:00:00.000Z"
            with self.assertRaisesRegex(ValueError, "scopes or revisions"):
                counts.population_match(changed, group)

    def test_rounding_is_not_renormalized_and_stress_is_symmetric(self):
        row = self.row("US", "HG", 20)
        self.assertEqual(row["population_match"]["population_partition_signed_rounding_difference_pct"], -1)
        self.assertEqual(row["estimated_current_group_count"], 123267000 * .47)
        self.assertEqual(row["signed_prior_composition_rounding_difference_pct"], -1)
        scenarios = [x for x in row["sensitivity_scenarios"] if x["harris_to_trump_transfer_pp"] == 0]
        reference = row["composition"]["R"]["reported_current_choice_counts"]["D"]
        self.assertAlmostEqual(scenarios[0]["reported_opposite_party_counts"]["R"], reference * .95)
        self.assertAlmostEqual(scenarios[-1]["reported_opposite_party_counts"]["R"], reference * 1.05)
        lower = row["rounding_only_opposite_choice_envelopes"]["R"]["lower"]
        self.assertAlmostEqual(lower, 123267000 * .465 * .485 * .065)

    def test_unreconciled_group_partition_is_not_repaired(self):
        main = copy.deepcopy(self.items[("NC", "SG", 0)])
        group = self.items[("NC", "SG", 20)]
        counts.question(main, 11001, "Gender")["answers"][0]["totalPercentage"] = 40
        self.assertEqual(counts.population_match(main, group)["status"], "withheld_unreconciled_population_partition")


if __name__ == "__main__":
    unittest.main()

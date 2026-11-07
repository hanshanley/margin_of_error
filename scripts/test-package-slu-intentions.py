import copy
import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "selected_slu", Path(__file__).with_name("package-slu-intentions.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DATA = Path(__file__).resolve().parents[1] / module.DATA


class SelectedIntentionTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((DATA / "selected-aggregates.json").read_text())
        self.methods = json.loads((DATA / "methodology-review.json").read_text())

    def test_selected_reference_preserves_unsure_and_full_prior_denominator(self):
        result = module.review(self.source, self.methods)
        trump = next(row for row in result["rows"] if row["prior_party"] == "R")
        self.assertAlmostEqual(trump["intended_house_pct"]["D"], 4.222814434078959)
        self.assertAlmostEqual(trump["intended_house_pct"]["Not sure"], 6.24207424515223)
        self.assertAlmostEqual(sum(trump["intended_house_pct"].values()), 100)
        for key in ("population_switchers", "apparent_absence", "measured_staying_home",
                    "new_or_returning_identity", "demographic_turnout", "overall_swing_share",
                    "design_confidence_intervals", "district_or_county_estimates"):
            self.assertIsNone(result[key])

    def test_changed_election_universe_and_observation_status_fail(self):
        for field, value in (("completed_voting", True), ("geography", "WA"),
                             ("universe", "all_voters"), ("contest_scope", "Missouri_statewide_House"),
                             ("field_period", {"start": "2026-11-03", "end": "2026-11-03"})):
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.review({**self.source, field: value}, self.methods)

    def test_selected_rows_cannot_omit_responses_or_renormalize(self):
        for edit in ("missing", "sum", "nan", "label", "duplicate"):
            source = copy.deepcopy(self.source)
            row = source["rows"][0]
            if edit == "missing":
                del row["weighted_house_shares"]["Not sure"]
            elif edit == "sum":
                row["weighted_house_shares"]["D"] += .001
            elif edit == "nan":
                row["weighted_house_shares"]["D"] = float("nan")
            elif edit == "label":
                row["reported_2024_choice"] = "Harris"
            else:
                source["rows"][1] = copy.deepcopy(row)
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.review(source, self.methods)

    def test_private_cells_and_population_promotion_are_rejected(self):
        for level in ("root", "row"):
            source = copy.deepcopy(self.source)
            target = source if level == "root" else source["rows"][0]
            target["raw_joint_counts"] = [1, 2, 3, 4]
            with self.subTest(level=level), self.assertRaises(ValueError):
                module.review(source, self.methods)
        for key in ("population_scaling_permitted", "completed_participation_permitted",
                    "district_or_county_allocation_permitted", "design_confidence_intervals_permitted"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.review(self.source, {**self.methods, key: True})


if __name__ == "__main__":
    unittest.main()

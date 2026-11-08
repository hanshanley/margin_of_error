import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("civic_package", ROOT / "scripts/package-civic-estimates.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((ROOT / module.DATA / "selected-aggregates.json").read_text())

    def test_complete_scopes_and_queries(self):
        result = module.review(self.source)
        self.assertEqual(len(result["participation"]), 79)
        self.assertEqual(len(result["conditional_flows"]), 112)
        self.assertEqual(len(result["conditional_flow_dispositions"]), 118)
        self.assertEqual(len(result["margin_components"]), 2)

    def test_model_and_self_report_not_conflated(self):
        result = module.review(self.source)
        overall = next(r for r in result["participation"] if r["scope"] == "POOLED_SOURCE" and r["dimension"] == "overall")
        self.assertNotEqual(overall["modeled_voter_pct"], overall["already_voted_self_report_pct"])
        self.assertIsNone(result["measured_staying_home"])

    def test_no_population_or_weight_target_promotion(self):
        for key in ("administrative_turnout_validation", "source_weight_units_are_people",
                    "original_coalition_population_validation"):
            altered = copy.deepcopy(self.source)
            altered[key] = True
            with self.assertRaises(ValueError):
                module.review(altered)

    def test_incomplete_model_frame_rejected(self):
        altered = copy.deepcopy(self.source)
        altered["participation"][0]["modeled_nonvoter_weight"] = "0"
        with self.assertRaises(ValueError):
            module.review(altered)

    def test_removed_demographic_not_recovered(self):
        altered = copy.deepcopy(self.source)
        altered["participation"][0]["group"] = "88"
        with self.assertRaises(ValueError):
            module.review(altered)

    def test_sparse_flow_disposition_not_bypassed(self):
        altered = copy.deepcopy(self.source)
        selected = altered["conditional_flows"][0]
        for row in altered["conditional_flow_dispositions"]:
            if all(row[k] == selected[k] for k in ("prior_election", "dimension", "group", "prior_choice")):
                row["status"] = "withheld_sparse_source_joint_support"
        with self.assertRaises(ValueError):
            module.review(altered)

    def test_signed_components_and_denominator_reconcile(self):
        result = module.review(self.source)
        for row in result["margin_components"]:
            total = sum(module.number(row[key]) for key in (
                "switching_pp", "modeled_nonparticipation_pp", "no_prior_contest_vote_entry_pp",
                "other_or_unresolved_pp", "denominator_pp"))
            self.assertLess(abs(total - module.number(row["total_within_source_margin_change_pp"])),
                            module.Decimal("1e-20"))

    def test_unreconciled_margin_not_fitted_away(self):
        altered = copy.deepcopy(self.source)
        altered["pooled_margin_primitives"][0]["switching"] = "0"
        with self.assertRaises(ValueError):
            module.review(altered)


if __name__ == "__main__":
    unittest.main()

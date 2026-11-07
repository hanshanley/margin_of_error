import copy
import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "selected_slu_demographics", Path(__file__).with_name("package-slu-demographic-intentions.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DATA = Path(__file__).resolve().parents[1] / module.DATA


class SelectedDemographicIntentionTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((DATA / "selected-aggregates.json").read_text())
        self.methods = json.loads((DATA / "methodology-review.json").read_text())

    def test_selected_reference_preserves_joint_choices_and_full_denominators(self):
        result = module.review(self.source, self.methods)
        female = next(group for group in result["groups"] if group["native_variable"] == "gender")
        trump = next(row for row in female["rows"] if row["prior_party"] == "R")
        self.assertAlmostEqual(trump["intended_house_pct"]["D"], 4.278433518682422)
        self.assertAlmostEqual(trump["intended_house_pct"]["Not sure"], 6.940568929366908)
        self.assertAlmostEqual(sum(trump["intended_house_pct"].values()), 100)
        white = next(group for group in result["groups"] if group["native_variable"] == "race")
        harris = next(row for row in white["rows"] if row["prior_party"] == "D")
        self.assertEqual(harris["intended_house_pct"]["R"], 0)
        self.assertFalse(result["groups_additive"])
        for key in ("population_switchers", "apparent_absence", "measured_staying_home",
                    "new_or_returning_identity", "demographic_turnout", "overall_swing_share",
                    "design_confidence_intervals", "district_or_county_estimates",
                    "demographic_measurement_date"):
            self.assertIsNone(result[key])

    def test_changed_election_universe_and_observation_status_fail(self):
        for key, value in (("completed_voting", True), ("geography", "WA"),
                           ("universe", "all_voters"), ("contest_scope", "statewide_House"),
                           ("field_period", {"start": "2026-11-03", "end": "2026-11-03"})):
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.review({**self.source, key: value}, self.methods)
        changed = copy.deepcopy(self.source)
        changed["source_files"]["survey"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            module.review(changed, self.methods)

    def test_missing_duplicate_unqualified_and_relabelled_groups_fail(self):
        for edit in ("missing", "duplicate", "unqualified", "harmonized", "context", "base"):
            source = copy.deepcopy(self.source)
            group = source["groups"][0]
            if edit == "missing":
                source["groups"].pop()
            elif edit == "duplicate":
                source["groups"][-1] = copy.deepcopy(group)
            elif edit == "unqualified":
                group["native_code"] = "1"
            elif edit == "harmonized":
                group["native_description"] = "gender identity"
            elif edit == "context":
                source["groups"][2]["display_label"] = "Self-reported suburban residents"
            else:
                group["rows"][0]["raw_prior_base"] += 1
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.review(source, self.methods)

    def test_other_unsure_zero_and_invalid_numeric_denominators(self):
        for edit in ("missing", "sum", "nan", "bool", "negative", "kish"):
            source = copy.deepcopy(self.source)
            row = source["groups"][0]["rows"][0]
            if edit == "missing":
                del row["weighted_house_shares"]["Not sure"]
            elif edit == "sum":
                row["weighted_house_shares"]["D"] += .001
            elif edit == "kish":
                row["kish_weight_concentration_base"] = 99
            else:
                row["weighted_house_shares"]["R"] = {
                    "nan": float("nan"), "bool": False, "negative": -.01}[edit]
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.review(source, self.methods)

    def test_private_fields_and_population_promotions_fail(self):
        for level in ("root", "group", "row"):
            source = copy.deepcopy(self.source)
            target = {"root": source, "group": source["groups"][0],
                      "row": source["groups"][0]["rows"][0]}[level]
            target["raw_joint_counts"] = [1, 2, 3, 4]
            with self.subTest(level=level), self.assertRaises(ValueError):
                module.review(source, self.methods)
        for key in module.PERMISSIONS:
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.review(self.source, {**self.methods, key: True})


if __name__ == "__main__":
    unittest.main()

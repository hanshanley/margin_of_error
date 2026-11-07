import copy
import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "pew_intentions", Path(__file__).with_name("package-pew-intentions.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DATA = Path(__file__).resolve().parents[1] / module.DATA


class PanelIntentionTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((DATA / "selected-aggregates.json").read_text())
        self.methods = json.loads((DATA / "methodology-review.json").read_text())

    def test_native_choice_labels_and_unknown_nonresponse_are_preserved(self):
        result = module.review(self.source, self.methods)
        trump, harris = result["rows"]
        self.assertEqual(trump["intended_house_pct"], {"D": 5, "R": 77, "Other": 5, "Not sure": 13})
        self.assertEqual(harris["intended_house_pct"], {"D": 87, "R": 3, "Other": 3, "Not sure": 7})
        self.assertIsNone(trump["no_answer_pct"])
        for key in ("completed_2026_transitions", "population_switchers", "original_coalition_rates",
                    "returning_population", "apparent_absence", "measured_staying_home",
                    "demographic_by_prior_choice_estimates", "state_or_local_estimates"):
            self.assertIsNone(result[key])

    def test_source_rounding_is_not_renormalized_or_used_to_reconstruct_nonresponse(self):
        source = copy.deepcopy(self.source)
        source["rows"][0]["intended_house_pct"]["R"] -= 1
        source["rows"][0]["published_sum_minus_100_pp"] = -1
        result = module.review(source, self.methods)
        self.assertEqual(sum(result["rows"][0]["intended_house_pct"].values()), 99)
        self.assertEqual(result["rows"][0]["intended_house_pct"]["D"], 5)
        self.assertIsNone(result["rows"][0]["no_answer_pct"])

    def test_completed_voting_or_wrong_population_cannot_be_promoted(self):
        for key, value in (
            ("geography", "MO"), ("universe", "2026_voters"),
            ("prior_choice_administratively_observed", True),
            ("field_period", {"start": "2026-11-03", "end": "2026-11-03",
                              "completed_november_2026_votes": True})):
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.review({**self.source, key: value}, self.methods)
        for key in module.PERMISSIONS:
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.review(self.source, {**self.methods, key: True})

    def test_missing_other_unsure_duplicate_groups_or_fabricated_zero_nonresponse_fail(self):
        for edit in ("other", "unsure", "duplicate", "nonresponse", "boolean", "sum"):
            source = copy.deepcopy(self.source)
            row = source["rows"][0]
            if edit == "other":
                del row["intended_house_pct"]["Other"]
            elif edit == "unsure":
                del row["intended_house_pct"]["Not sure"]
            elif edit == "duplicate":
                source["rows"][1] = copy.deepcopy(row)
            elif edit == "nonresponse":
                row["no_answer_pct"] = 0
            elif edit == "boolean":
                row["intended_house_pct"]["D"] = True
            else:
                row["published_sum_minus_100_pp"] = 1
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.review(source, self.methods)

    def test_private_fields_and_missing_native_provenance_fail(self):
        for level in ("root", "row", "methods", "receipt"):
            source, methods = copy.deepcopy(self.source), copy.deepcopy(self.methods)
            target = {
                "root": source, "row": source["rows"][0],
                "methods": methods, "receipt": source["source_files"][0]}[level]
            target["respondent_records"] = []
            with self.subTest(level=level), self.assertRaises(ValueError):
                module.review(source, methods)
        source = copy.deepcopy(self.source)
        source["source_files"].pop()
        with self.assertRaises(ValueError):
            module.review(source, self.methods)


if __name__ == "__main__":
    unittest.main()

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("county", Path(__file__).with_name("package-county-scenarios.py"))
county = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(county)
DATA = county.ROOT / county.DATA


class CountySelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((DATA / "selected-scenarios.json").read_text())
        cls.methods = json.loads((DATA / "methodology-review.json").read_text())
        cls.proof = json.loads((DATA / "accounting-proof.json").read_text())

    def rejected(self, snapshot=None, methods=None, proof=None):
        with self.assertRaises((ValueError, KeyError)):
            county.review(snapshot if snapshot is not None else self.snapshot,
                          methods if methods is not None else self.methods,
                          proof if proof is not None else self.proof)

    def test_complete_real_selected_grid_and_summary(self):
        summary = county.review(self.snapshot, self.methods, self.proof)
        self.assertNotIn("scenarios", summary)
        self.assertEqual(summary["default_conditional_scenario"], self.snapshot["default_conditional_scenario"])
        self.assertFalse(summary["demographic_partitions_exhaustive"])
        self.assertEqual(summary["demographic_sensitivity_range_margin_pp"],
                         self.snapshot["demographic_sensitivity_range_margin_pp"])

    def test_missing_scenarios_or_missing_broad_groups_rejected(self):
        value = copy.deepcopy(self.snapshot)
        value["scenarios"].pop()
        self.rejected(snapshot=value)
        value = copy.deepcopy(self.snapshot)
        value["scenarios"][0]["demographics"].pop()
        self.rejected(snapshot=value)

    def test_unqualified_category_or_private_fields_rejected(self):
        value = copy.deepcopy(self.snapshot)
        value["scenarios"][0]["demographics"][1]["group"] = "NATIVE HAWAIIAN or PACIFIC ISLANDER"
        self.rejected(snapshot=value)
        for target in ("root", "group", "flow", "diagnostic"):
            value = copy.deepcopy(self.snapshot)
            node = {"root": value, "group": value["scenarios"][0]["demographics"][1],
                    "flow": value["scenarios"][0]["demographics"][1]["modeled_prior_choice_transitions"]["D"],
                    "diagnostic": value["turnout_temporal_diagnostics"]}[target]
            node["individual_scores"] = [0.5]
            self.rejected(snapshot=value)

    def test_arithmetic_and_sensitivity_mutations_rejected(self):
        for target in ("activity", "flow", "range"):
            value = copy.deepcopy(self.snapshot)
            if target == "activity":
                value["scenarios"][0]["demographics"][1]["modeled_cohort_counts"][
                    "prior_county_participants_now_nonvoting"] += 1
            elif target == "flow":
                value["scenarios"][0]["demographics"][1]["modeled_prior_choice_transitions"]["D"]["X"] += 1
            else:
                value["demographic_sensitivity_range_margin_pp"][1]["modeled_cohort_counts"][
                    "prior_county_participants_now_nonvoting"]["minimum"] += 1
            self.rejected(snapshot=value)

    def test_scope_measurement_or_evidence_promotion_rejected(self):
        for field in ("group_turnout_rate_pct", "measured_staying_home_count"):
            value = copy.deepcopy(self.snapshot)
            value["scenarios"][0]["demographics"][1][field] = 0
            self.rejected(snapshot=value)
        value = copy.deepcopy(self.snapshot)
        value["county"] = "DURHAM"
        self.rejected(snapshot=value)
        value = copy.deepcopy(self.methods)
        value["validated_individual_attribution"] = True
        self.rejected(methods=value)
        value = copy.deepcopy(self.proof)
        value["individual_attribution_independently_validated"] = True
        self.rejected(proof=value)

    def test_changed_frozen_input_refused_before_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / county.DATA
            target.mkdir(parents=True)
            for name in county.PINS:
                (target / name).write_bytes((DATA / name).read_bytes())
            (target / "accounting-proof.json").write_text("{}\n")
            with patch.object(county, "ROOT", root), self.assertRaisesRegex(ValueError, "Frozen county selection"):
                county.package()


if __name__ == "__main__":
    unittest.main()

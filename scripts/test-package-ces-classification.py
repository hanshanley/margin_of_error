"""Exercise estimand, disclosure, completeness and immutable package boundaries."""

import contextlib
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile


SPEC = importlib.util.spec_from_file_location(
    "ces_classification", Path(__file__).with_name("package-ces-classification.py"))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
INPUT = json.loads((module.ROOT / module.DATA / "selected-aggregates.json").read_bytes())
METHODS = json.loads((module.ROOT / module.DATA / "methodology-review.json").read_bytes())


class ClassificationTests(unittest.TestCase):
    def test_unknowns_stay_in_denominator_not_classifiable_only(self):
        row = {
            "dimension": "overall", "group": "overall", "respondents": 300,
            "sum_weight": 300, "sum_squared_weight": 300,
            "categories": {name: {"respondents": 100, "sum_weight": 100, "sum_squared_weight": 100}
                           for name in module.CATEGORIES},
        }
        result = module.summarize(row)
        self.assertEqual(result["conditional_compatible_fraction"], [1 / 3, 2 / 3])
        self.assertEqual(result["unresolved_weight_fraction"], 1 / 3)
        self.assertIsNone(result["adult_population_turnout_rate"])

    def test_complete_real_evidence_keeps_withholdings_and_same_frame_comparator(self):
        result = module.review(INPUT, METHODS)
        overall = next(row for row in INPUT["rows"] if row["dimension"] == "overall")
        lower, upper = result["record_only_compatible_fraction_same_post_frame_overall_only"]
        self.assertEqual(lower, result["rows"][0]["conditional_compatible_fraction"][0])
        self.assertAlmostEqual(
            upper, 1 - INPUT["record_only_overall_nonvote_sum_weight"] / overall["sum_weight"],
            places=14)
        self.assertGreater(upper, result["rows"][0]["conditional_compatible_fraction"][1])
        self.assertTrue(all(row["public_estimate"] is None for row in result["jurisdictions"]))
        self.assertIsNone(result["completed_2026_participation_or_choice"])

    def test_wrong_weight_scope_variant_and_promoted_permissions_fail(self):
        for field, value in (("weight_frame", "adult_commonweight"),
                             ("survey_scope", "US51"), ("classification", "guide")):
            snapshot = deepcopy(INPUT)
            snapshot[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.review(snapshot, METHODS)
        for permission in module.PERMISSIONS:
            methods = deepcopy(METHODS)
            methods[permission] = True
            with self.subTest(permission=permission), self.assertRaises(ValueError):
                module.review(INPUT, methods)

    def test_fine_or_private_fields_and_alternative_variant_fail(self):
        for mutation in ("fine_category", "raw_conflict", "group_comparator"):
            snapshot = deepcopy(INPUT)
            if mutation == "fine_category":
                snapshot["rows"][0]["categories"]["explicit_recorded_nonvote"] = {
                    "respondents": 100, "sum_weight": 100, "sum_squared_weight": 100}
            elif mutation == "raw_conflict":
                snapshot["rows"][0]["rare_conflict_count"] = 1
            else:
                snapshot["rows"][1]["explicit_recorded_nonvote_sum_weight"] = 100
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                module.review(snapshot, METHODS)

    def test_missing_duplicate_or_new_group_and_state_estimates_fail(self):
        for mutation in ("missing", "duplicate", "omitted_group", "state_estimate", "missing_state"):
            snapshot = deepcopy(INPUT)
            if mutation == "missing":
                snapshot["rows"].pop()
            elif mutation == "duplicate":
                snapshot["rows"][-1] = deepcopy(snapshot["rows"][-2])
            elif mutation == "omitted_group":
                snapshot["rows"][-1]["group"] = "Other"
            elif mutation == "state_estimate":
                snapshot["jurisdictions"][0]["public_estimate"] = 0
            else:
                snapshot["jurisdictions"].pop()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                module.review(snapshot, METHODS)

    def test_invalid_small_or_nonreconciling_statistics_fail(self):
        for field, value in (("respondents", True), ("respondents", 29),
                             ("sum_weight", -1), ("sum_weight", float("nan")),
                             ("sum_squared_weight", 0)):
            snapshot = deepcopy(INPUT)
            snapshot["rows"][1]["categories"]["recorded_vote"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                module.review(snapshot, METHODS)
        snapshot = deepcopy(INPUT)
        snapshot["rows"][1]["sum_weight"] += 1
        with self.assertRaises(ValueError):
            module.review(snapshot, METHODS)

    def test_small_complement_and_broken_exhaustive_partition_fail(self):
        for dimension, increase in (("gender_2024", 30), ("education_2024", 1)):
            snapshot = deepcopy(INPUT)
            row = next(row for row in snapshot["rows"] if row["dimension"] == dimension)
            for field in module.FIELDS:
                row[field] += increase
                row["categories"]["classified_nonvote"][field] += increase
            with self.subTest(dimension=dimension), self.assertRaises(ValueError):
                module.review(snapshot, METHODS)

    def test_wrong_native_controls_labels_or_receipts_fail(self):
        for mutation in ("guide", "controls", "labels", "source_accounting"):
            snapshot = deepcopy(INPUT)
            if mutation == "guide":
                snapshot["source_files"][1]["sha256"] = "0" * 64
            elif mutation == "controls":
                snapshot["native_response_controls"]["CC24_401"]["5"] -= 1
            elif mutation == "labels":
                snapshot["native_label_metadata_selection"]["respondent_data_transferred"] = True
            else:
                snapshot["source_accounting"]["postwave_respondents"] -= 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                module.review(snapshot, METHODS)

    def test_deterministic_complete_package_and_fail_closed_frozen_bytes(self):
        original_root = module.ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for path in (module.DATA, "scripts"):
                    (root / path).mkdir(parents=True)
                for name in module.PINS:
                    shutil.copyfile(original_root / module.DATA / name, root / module.DATA / name)
                for name in ("package-ces-classification.py", "test-package-ces-classification.py",
                             *module.NATIVE_HELPERS):
                    shutil.copyfile(original_root / "scripts" / name, root / "scripts" / name)
                module.ROOT = root
                with contextlib.redirect_stdout(io.StringIO()):
                    module.package()
                out = root / module.PUBLIC
                first = {path.name: path.read_bytes() for path in out.iterdir()}
                with contextlib.redirect_stdout(io.StringIO()):
                    module.package()
                self.assertEqual(first, {path.name: path.read_bytes() for path in out.iterdir()})
                with zipfile.ZipFile(io.BytesIO(first["complete-analysis.zip"])) as archive:
                    inventory = json.loads(archive.read("checksums.json"))
                    self.assertEqual(set(archive.namelist()), set(inventory) | {"checksums.json"})
                    for name, meta in inventory.items():
                        raw = archive.read(name)
                        self.assertEqual(meta, {"bytes": len(raw), "sha256": module.digest(raw)})
                    for name in module.PINS:
                        self.assertIn(f"{module.DATA}/{name}", inventory)
                (out / "classification-evidence.json").write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "Frozen CES"):
                    module.package()
                self.assertEqual((out / "complete-analysis.zip").read_bytes(), first["complete-analysis.zip"])
                (out / "classification-evidence.json").write_bytes(first["classification-evidence.json"])
                (root / module.DATA / "selected-aggregates.json").write_bytes(b"{}")
                with self.assertRaisesRegex(ValueError, "Reviewed CES inputs"):
                    module.package()
                self.assertEqual((out / "classification-evidence.json").read_bytes(),
                                 first["classification-evidence.json"])
        finally:
            module.ROOT = original_root


if __name__ == "__main__":
    unittest.main()

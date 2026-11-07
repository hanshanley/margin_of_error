import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "integration", Path(__file__).with_name("integrate-state-participation-evidence.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def evidence(period=(2020, 2022), kind="administrative_joint_history"):
    return {
        "prior_year": period[0], "current_year": period[1], "evidence_kind": kind,
        "source_population": "Synthetic source-record universe, not eligible population",
        "counts": {"prior_positive": 100, "current_positive": 80, "both": 60,
                   "prior_only": 40, "current_only": 20, "neither": None},
        "source_paths": ["synthetic-input.json"], "proof_paths": ["synthetic-proof.json"],
        "checked_arithmetic": True, "population_match": False, "public_release_qualified": False,
        "source_cohort_compatible": True,
    }


def state(code):
    return {"state_code": code, "status": "source_not_acquired",
            "evidence": [], "access_dispositions": [{"status": "synthetic_access_fixture"}],
            "limits": ["Synthetic fixture, not real source evidence"], "next_action": "Qualify original source"}


def fixtures():
    batches = [{"batch": name, "states": [state(code) for code in sorted(codes)]}
               for name, codes in module.BATCHES.items()]
    nc = state("NC")
    nc["evidence"] = [evidence()]
    historical = {"states": [{"state_code": code, "specifications": [
        {"dispositions": {"retained": {"n": 10}}}]} for code in sorted(module.STATES)]}
    return batches, nc, historical


class IntegrationTests(unittest.TestCase):
    def test_all_50_states_present_but_coverage_is_not_model_validation(self):
        batches, nc, historical = fixtures()
        original = copy.deepcopy((batches, nc, historical))
        result = module.integrate(batches, nc, historical)
        self.assertEqual(len(result["states"]), 50)
        self.assertEqual(result["states_with_primary_period_joint_evidence"], 1)
        self.assertFalse(result["all_states_have_primary_period_joint_evidence"])
        self.assertFalse(result["population_method_validated"])
        self.assertEqual((batches, nc, historical), original)

    def test_supplementary_presidential_period_does_not_satisfy_midterm_coverage(self):
        batches, nc, historical = fixtures()
        az = next(s for s in batches[0]["states"] if s["state_code"] == "AZ")
        az["evidence"] = [evidence((2020, 2024), "published_vendor_aggregate_joint")]
        result = module.integrate(batches, nc, historical)
        self.assertEqual(result["states_with_primary_period_joint_evidence"], 1)
        self.assertEqual(result["states_with_supplementary_joint_evidence"], 1)

    def test_marginals_partial_counts_and_unchecked_sources_are_not_joint_benchmarks(self):
        for change in ("marginals", "unknown_overlap", "unchecked"):
            item = evidence()
            if change == "marginals":
                item["evidence_kind"] = "marginals_only"
            elif change == "unknown_overlap":
                item["counts"]["both"] = None
            else:
                item["checked_arithmetic"] = False
            with self.subTest(change=change):
                self.assertFalse(module.checked_evidence(item)["joint_benchmark_available_not_model_validation"])

    def test_unknown_neither_remains_unknown_not_zero_or_eligible_denominator(self):
        item = module.checked_evidence(evidence())
        self.assertIsNone(item["counts"]["neither"])
        self.assertEqual(item["record_union_n_not_eligible_population"], 120)
        self.assertFalse(item["population_match"])

    def test_invalid_or_inconsistent_counts_fail_closed(self):
        for key, value in (("both", 101), ("prior_only", 41), ("current_only", -1),
                           ("prior_positive", True), ("current_positive", 1.5)):
            item = evidence()
            item["counts"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                module.checked_evidence(item)
        item = evidence()
        del item["counts"]["neither"]
        with self.assertRaises(ValueError):
            module.checked_evidence(item)

    def test_missing_duplicate_or_reassigned_states_cannot_be_silently_dropped(self):
        for change in ("missing", "duplicate_state", "wrong_batch", "duplicate_batch", "missing_history"):
            batches, nc, historical = fixtures()
            if change == "missing":
                batches[0]["states"].pop()
            elif change == "duplicate_state":
                batches[0]["states"][-1] = copy.deepcopy(batches[0]["states"][0])
            elif change == "wrong_batch":
                batches[0]["states"][0] = state("NC")
            elif change == "duplicate_batch":
                batches[-1] = copy.deepcopy(batches[0])
            else:
                historical["states"].pop()
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.integrate(batches, nc, historical)

    def test_claimed_checks_require_explicit_source_and_proof_artifacts(self):
        for field in ("source_paths", "proof_paths"):
            item = evidence()
            item[field] = []
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.checked_evidence(item)
        item = evidence()
        item["evidence_kind"] = "validated_everywhere"
        with self.assertRaises(ValueError):
            module.checked_evidence(item)

    def test_explicit_research_alias_preserves_source_class_and_qualification(self):
        source_kind = "published_original_research_county_tooltips_aggregated_to_statewide_joint_transition"
        item = module.checked_evidence(evidence((2020, 2024), source_kind))
        self.assertEqual(item["evidence_kind"], "published_original_research_joint")
        self.assertEqual(item["source_evidence_kind"], source_kind)
        self.assertTrue(item["supplementary_presidential_period"])
        self.assertFalse(item["primary_midterm_period"])
        self.assertFalse(item["population_match"])

    def test_incompatible_or_unknown_published_cohorts_cannot_be_promoted_by_arithmetic(self):
        for value in (False, None):
            item = evidence(kind="published_vendor_aggregate_joint")
            item["source_cohort_compatible"] = value
            checked = module.checked_evidence(item)
            self.assertTrue(checked["integration_joint_count_identities_checked"])
            self.assertFalse(checked["joint_benchmark_available_not_model_validation"])
            self.assertIsNone(checked["record_union_n_not_eligible_population"])
        for kind in ("published_vendor_partial_transition_prior_only",
                     "published_voter_file_aggregate_incompatible_joint_reconstruction"):
            self.assertFalse(module.checked_evidence(evidence(kind=kind))[
                "joint_benchmark_available_not_model_validation"])

    def test_artifacts_resolve_against_explicit_root_not_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "batch" / "proof.json"
            source.parent.mkdir()
            source.write_text("{}")
            for path in ("batch/proof.json", str(source)):
                self.assertEqual(module.resolve_artifact(path, root), source.resolve())
            for path in ("missing.json", "../outside.json", str(Path(__file__).resolve())):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    module.resolve_artifact(path, root)


if __name__ == "__main__":
    unittest.main()

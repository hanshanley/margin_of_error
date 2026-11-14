"""Verify the model35 website overlay and strict external publication proof."""

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/participation-registered-controls/20261113-34/display-model.json"
PROJECTION = ROOT / "data/participation-registered-controls/20261114-35/display-model.json"
MODEL_SDK = Path(os.environ["MODEL35_MODEL_SDK"]) if os.environ.get("MODEL35_MODEL_SDK") else None
COUNT_SDK = Path(os.environ["MODEL35_COUNT_SDK"]) if os.environ.get("MODEL35_COUNT_SDK") else None
MODEL_RECEIPT = (Path(os.environ["MODEL35_MODEL_RECEIPT"])
                 if os.environ.get("MODEL35_MODEL_RECEIPT") else None)
COUNT_RECEIPT = (Path(os.environ["MODEL35_COUNT_RECEIPT"])
                 if os.environ.get("MODEL35_COUNT_RECEIPT") else None)
COMPONENT = ROOT / "src/components/ParticipationCivicEstimates.astro"
BUILDER = ROOT / "scripts/build-registered-control-private-preview.py"
BUILD = runpy.run_path(str(BUILDER))
WORK = ROOT / ".test-model35-publication-status-work"


def pin(path):
    body = path.read_bytes()
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


class Model35PrivateProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(BASE.read_bytes())
        cls.projection = json.loads(PROJECTION.read_bytes())

    def test_only_nc_or_rows_overlay_current_website_projection(self):
        codes = {"NC", "OR"}
        self.assertEqual(
            [row for row in self.projection["states"] if row["state_code"] not in codes],
            [row for row in self.base["states"] if row["state_code"] not in codes],
        )
        self.assertEqual(
            [row for row in self.projection["scenarios"] if row["state_code"] not in codes],
            [row for row in self.base["scenarios"] if row["state_code"] not in codes],
        )
        self.assertEqual(self.projection["source_projection"][
            "preserved_other_state_codes"], 49)
        self.assertEqual(self.projection["source_projection"][
            "preserved_other_scenarios"], 32)
        self.assertTrue(self.projection["source_projection"][
            "retained_current_nm_revision"])
        self.assertEqual(
            next(row for row in self.projection["states"] if row["state_code"] == "NM"),
            next(row for row in self.base["states"] if row["state_code"] == "NM"),
        )

    def test_nc_or_rows_equal_full_model35_public_outputs(self):
        if MODEL_SDK is None:
            self.skipTest("Set MODEL35_MODEL_SDK for full SDK integration")
        with zipfile.ZipFile(MODEL_SDK) as archive:
            prefix = "queries/reference-model35/"
            model_states = list(csv.DictReader(io.StringIO(
                archive.read(prefix + "complete-state-control-query.csv").decode())))
            model_scenarios = list(csv.DictReader(io.StringIO(
                archive.read(prefix + "complete-conditional-registered-scenarios.csv").decode())))
        state_fields = tuple(self.projection["states"][0])
        scenario_fields = tuple(self.projection["scenarios"][0])
        expected_states = {
            row["state_code"]: {name: row[name] for name in state_fields}
            for row in model_states if row["state_code"] in ("NC", "OR")
        }
        expected_scenarios = {
            (row["state_code"], row["control_id"]): {name: row[name] for name in scenario_fields}
            for row in model_scenarios
            if (row["state_code"], row["control_id"])
            in {("NC", "reporting-NC"), ("OR", "reporting-OR")}
        }
        actual_states = {
            row["state_code"]: row for row in self.projection["states"]
            if row["state_code"] in ("NC", "OR")
        }
        actual_scenarios = {
            (row["state_code"], row["control_id"]): row
            for row in self.projection["scenarios"]
            if (row["state_code"], row["control_id"]) in expected_scenarios
        }
        self.assertEqual(actual_states, expected_states)
        self.assertEqual(actual_scenarios, expected_scenarios)

    def test_source_reference_changes_have_exact_meaningful_values(self):
        changes = {row["state_code"]: row for row in
                   self.projection["native_reference_changes"]}
        self.assertEqual(changes["NC"]["native_numerator_difference"], -518)
        self.assertEqual(changes["NC"]["registered_denominator_difference"], 0)
        self.assertEqual(changes["NC"]["conditional_modeled_voter_unit_difference"], "0")
        self.assertEqual(changes["OR"]["native_numerator_difference"], -26981)
        self.assertEqual(changes["OR"]["registered_denominator_difference"], -22)
        self.assertEqual(
            changes["OR"]["conditional_modeled_voter_unit_difference"],
            "-14.7416565894603554070505860949628091008651443279001558242930301316261507203",
        )
        self.assertEqual(
            changes["OR"]["conditional_modeled_nonvoter_unit_difference"],
            "-7.2583434105396445929494139050371908991348556720998441757069698683738492797",
        )
        self.assertTrue(all(row["diagnostic_is_not_validated_model_error"]
                            for row in changes.values()))

    def test_sdk_pins_and_verified_flags_are_honest(self):
        if MODEL_SDK is None or COUNT_SDK is None:
            self.skipTest("Set MODEL35_MODEL_SDK and MODEL35_COUNT_SDK for pin integration")
        self.assertEqual(self.projection["complete_download"], {
            "url": ("https://github.com/hanshanley/margin_of_error/releases/download/"
                    "participation-nc-or-native-controls-r35-20261114-01/complete-analysis.zip"),
            **pin(MODEL_SDK),
        })
        self.assertEqual(self.projection["count_download"]["bytes"], pin(COUNT_SDK)["bytes"])
        self.assertEqual(self.projection["count_download"]["sha256"], pin(COUNT_SDK)["sha256"])
        self.assertEqual(self.projection["publication_status"], {
            "status": "verified_immutable", "immutable": True,
            "verified_anonymously": True})
        self.assertEqual(self.projection["count_publication_status"], {
            "status": "verified_immutable", "immutable": True,
            "verified_anonymously": True})
        self.assertEqual(self.projection["source_projection"][
            "model35_public_outputs_verified"], 25)

    def test_component_uses_verified_projection_without_embedding_bulk(self):
        body = COMPONENT.read_text()
        self.assertIn("20261114-35/display-model.json", body)
        self.assertIn('data-native-publication-status="planned_immutable"', body)
        self.assertIn('data-native-publication-status="verified_immutable"', body)
        self.assertIn('data-native-registered-download="model-zip"', body)
        self.assertIn('data-native-registered-download="count-zip"', body)
        self.assertNotIn("data-native-group-download", body)
        self.assertIn("no bulk SDK or query body is embedded in this page", body)
        self.assertLess(PROJECTION.stat().st_size, 60_000)

    def test_publication_schema_rejects_nonimmutable_and_incomplete_proof(self):
        try:
            WORK.mkdir()
            body = b"fixture-sdk-body"
            url = "https://example.invalid/complete-analysis.zip"
            base = {
                "passed": True,
                "immutable": True,
                "all_assets_authenticated_draft_and_anonymous_public_full_body_verified": True,
                "assets": [{
                    "name": "complete-analysis.zip",
                    "id": 1,
                    "url": url,
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }],
            }
            for index, mutation in enumerate((
                    {"immutable": False},
                    {"all_assets_authenticated_draft_and_anonymous_public_full_body_verified": False},
                    {"passed": False},
            )):
                proof = {**base, **mutation}
                path = WORK / f"invalid-{index}.json"
                path.write_text(json.dumps(proof))
                with self.assertRaisesRegex(ValueError, "publication proof differs"):
                    BUILD["publication_status"](path, body, url)
            mismatch = json.loads(json.dumps(base))
            mismatch["assets"][0]["url"] = "https://example.invalid/wrong.zip"
            path = WORK / "mismatch.json"
            path.write_text(json.dumps(mismatch))
            with self.assertRaisesRegex(ValueError, "publication proof differs"):
                BUILD["publication_status"](path, body, url)
        finally:
            shutil.rmtree(WORK, ignore_errors=True)

    def test_actual_receipts_build_verified_dual_sdk_projection(self):
        if any(path is None for path in (
                MODEL_SDK, COUNT_SDK, MODEL_RECEIPT, COUNT_RECEIPT)):
            self.skipTest("Set MODEL35_*_SDK and MODEL35_*_RECEIPT for publication integration")
        rebuilt = BUILD["build"](
            BASE, MODEL_SDK, COUNT_SDK, MODEL_RECEIPT, COUNT_RECEIPT)
        self.assertEqual(rebuilt, self.projection)
        self.assertEqual(rebuilt["publication_status"]["status"], "verified_immutable")
        self.assertEqual(rebuilt["count_publication_status"]["status"], "verified_immutable")
        planned = BUILD["build"](BASE, MODEL_SDK, COUNT_SDK)
        self.assertEqual(planned["publication_status"]["status"], "planned_immutable")
        self.assertEqual(planned["count_publication_status"]["status"], "planned_immutable")
        planned.pop("publication_status")
        planned.pop("count_publication_status")
        verified = json.loads(json.dumps(rebuilt))
        verified.pop("publication_status")
        verified.pop("count_publication_status")
        self.assertEqual(planned, verified)
        with self.assertRaisesRegex(ValueError, "must advance together"):
            BUILD["build"](BASE, MODEL_SDK, COUNT_SDK, MODEL_RECEIPT, None)
        try:
            WORK.mkdir()
            invalid_model = json.loads(MODEL_RECEIPT.read_bytes())
            invalid_model["immutable"] = False
            invalid_model_path = WORK / "model-not-immutable.json"
            invalid_model_path.write_text(json.dumps(invalid_model))
            with self.assertRaisesRegex(ValueError, "publication proof differs"):
                BUILD["build"](
                    BASE, MODEL_SDK, COUNT_SDK, invalid_model_path, COUNT_RECEIPT)
            invalid_count = json.loads(COUNT_RECEIPT.read_bytes())
            invalid_count["assets"][0]["sha256"] = "0" * 64
            invalid_count_path = WORK / "count-pin-mismatch.json"
            invalid_count_path.write_text(json.dumps(invalid_count))
            with self.assertRaisesRegex(ValueError, "publication proof differs"):
                BUILD["build"](
                    BASE, MODEL_SDK, COUNT_SDK, MODEL_RECEIPT, invalid_count_path)
        finally:
            shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

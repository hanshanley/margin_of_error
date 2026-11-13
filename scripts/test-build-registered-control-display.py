import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("registered_display", ROOT / "scripts/build-registered-control-display.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def csv_bytes(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


class RegisteredDisplayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.publication = self.root / "publication.json"
        codes = ["DC"] + [f"{i:02}" for i in range(50)]
        states = [dict(state_code=code, civic_source_n="100" if code != "DC" else "",
                       control_id="", control_registered_denominator="", control_denominator_basis="",
                       control_native_time="", control_source_url="") for code in codes]
        self.scenario = dict(
            state_code="00", control_id="existing", native_registered_denominator="20",
            native_denominator_basis="native_undefined_status", source_time_label="native date",
            source_url="https://example.gov/frame", civic_source_n="100",
            conditional_modeled_voter_count="12.000000000000000000000001",
            conditional_modeled_nonvoter_count="7.999999999999999999999999",
            assumption_validated="False", survey_weight_target_qualified="False",
            same_frame_and_cutoff_independently_qualified="False",
            bridge_outcome_calibration_applied="False",
            model_nonvoter_is_administratively_observed_staying_home="False")
        self.members = {
            "complete-state-control-query.csv": csv_bytes(states),
            "complete-native-control-dispositions.csv": csv_bytes([dict(state_code="00", numerator="11")]),
            "complete-conditional-registered-scenarios.csv": csv_bytes([self.scenario]),
            "summary.json": json.dumps(dict(
                conditional_scenarios=1, native_control_version=29,
                new_model_variants_or_scenarios_created=0,
                study_fit_weights_or_probabilities_changed=False,
                native_count_used_for_outcome_fitting=False)).encode(),
        }
        self.prepare()

    def prepare(self):
        with zipfile.ZipFile(self.root / "complete-analysis.zip", "w") as archive:
            for name, body in self.members.items():
                archive.writestr(name, body)
        body = (self.root / "complete-analysis.zip").read_bytes()
        assets = []
        for name, content in {"complete-analysis.zip": body, **{
                k: v for k, v in self.members.items() if k.endswith((".csv", ".json.gz"))}}.items():
            assets.append(dict(name=name, anonymous_status=200, bytes=len(content),
                               sha256=hashlib.sha256(content).hexdigest(),
                               url="https://github.com/example/releases/download/immutable/" + name))
        self.proof = dict(passed=True, draft=False, assets=assets)
        self.save()

    def save(self):
        self.publication.write_text(json.dumps(self.proof))

    def test_preserves_unrounded_scenarios_and_unsampled_missing_state(self):
        model = module.build(self.root, self.publication)
        self.assertEqual(model["scenarios"][0]["conditional_modeled_voter_count"],
                         self.scenario["conditional_modeled_voter_count"])
        self.assertEqual(model["states"][0]["civic_source_n"], "")
        self.assertEqual(model["states"][0]["control_registered_denominator"], "")
        self.assertEqual(len(model["query_downloads"]), 3)
        self.assertFalse(model["frame_exchangeability_or_observed_staying_home_qualified"])

    def test_rejects_draft_headers_only_or_changed_full_download(self):
        self.proof["draft"] = True
        self.save()
        with self.assertRaisesRegex(ValueError, "published full-body"):
            module.build(self.root, self.publication)
        self.proof["draft"] = False
        self.proof["assets"][0].pop("anonymous_status")
        self.save()
        with self.assertRaisesRegex(ValueError, "anonymously verified"):
            module.build(self.root, self.publication)
        self.prepare()
        (self.root / "complete-analysis.zip").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "differs from its verified full download"):
            module.build(self.root, self.publication)

    def test_rejects_inconsistent_csv_or_promoted_validation(self):
        self.proof["assets"][1]["sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "CSV differs"):
            module.build(self.root, self.publication)
        self.scenario["assumption_validated"] = "True"
        self.members["complete-conditional-registered-scenarios.csv"] = csv_bytes([self.scenario])
        self.prepare()
        with self.assertRaisesRegex(ValueError, "validated population"):
            module.build(self.root, self.publication)

    def test_native_group_downloads_require_both_full_verified_archive_members(self):
        names = ("complete-native-participation-group-controls.csv",
            "complete-current-native-source-queries.json.gz")
        self.members[names[0]] = b"state_code,reported_source_ballots\n00,0\n"
        self.members[names[1]] = b"complete-query-input-fixture"
        self.prepare()
        model = module.build(self.root, self.publication)
        self.assertEqual(set(model["source_group_downloads"]), set(names))
        next(asset for asset in self.proof["assets"] if asset["name"] == names[1])["sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "native group download differs"):
            module.build(self.root, self.publication)
        self.members.pop(names[1])
        self.prepare()
        with self.assertRaisesRegex(ValueError, "Both complete native group"):
            module.build(self.root, self.publication)


if __name__ == "__main__":
    unittest.main()

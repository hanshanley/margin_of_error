"""Project a fully verified native-control release into build-time display data."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile


def build(analysis, publication):
    proof = json.loads(publication.read_bytes())
    if proof.get("passed") is not True or proof.get("draft") is not False:
        raise ValueError("A published full-body-verified release is required")
    assets = [a for a in proof["assets"] if a["name"] == "complete-analysis.zip"]
    if len(assets) != 1 or assets[0].get("anonymous_status") != 200:
        raise ValueError("The complete numerical archive must be anonymously verified")
    asset = assets[0]
    archive_path = analysis / "complete-analysis.zip"
    body = archive_path.read_bytes()
    if len(body) != asset["bytes"] or hashlib.sha256(body).hexdigest() != asset["sha256"]:
        raise ValueError("The displayed model differs from its verified full download")
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = lambda name: list(csv.DictReader(io.StringIO(archive.read(name).decode())))
        states = rows("complete-state-control-query.csv")
        scenarios = rows("complete-conditional-registered-scenarios.csv")
        summary = json.loads(archive.read("summary.json"))
        query_downloads = {}
        for name in ("complete-state-control-query.csv", "complete-native-control-dispositions.csv",
                     "complete-conditional-registered-scenarios.csv"):
            matches = [a for a in proof["assets"] if a["name"] == name]
            original = archive.read(name)
            if (len(matches) != 1 or matches[0].get("anonymous_status") != 200
                    or matches[0]["bytes"] != len(original)
                    or matches[0]["sha256"] != hashlib.sha256(original).hexdigest()):
                raise ValueError("A full numerical CSV differs from its verified archive member")
            query_downloads[name] = {key: matches[0][key] for key in ("url", "bytes", "sha256")}
    if (len(states) != 51 or len({r["state_code"] for r in states}) != 51
            or "DC" not in {r["state_code"] for r in states}
            or len(scenarios) != summary["conditional_scenarios"]
            or summary["new_model_variants_or_scenarios_created"] != 0
            or summary["study_fit_weights_or_probabilities_changed"] is not False
            or summary["native_count_used_for_outcome_fitting"] is not False):
        raise ValueError("Native scenario coverage, prior or calibration contract changed")
    flags = ("assumption_validated", "survey_weight_target_qualified",
             "same_frame_and_cutoff_independently_qualified", "bridge_outcome_calibration_applied",
             "model_nonvoter_is_administratively_observed_staying_home")
    if any(row[field] != "False" for row in scenarios for field in flags):
        raise ValueError("Do not display conditional source units as validated population counts")
    state_fields = (
        "state_code", "civic_source_n", "control_id", "control_registered_denominator",
        "control_denominator_basis", "control_native_time", "control_source_url")
    scenario_fields = (
        "state_code", "control_id", "native_registered_denominator", "native_denominator_basis",
        "source_time_label", "source_url", "civic_source_n",
        "conditional_modeled_voter_count", "conditional_modeled_nonvoter_count")
    return dict(
        contract="participation.registered_control_display.v1", year=2026,
        native_control_version=summary["native_control_version"],
        states=[{key: row[key] for key in state_fields} for row in states],
        scenarios=[{key: row[key] for key in scenario_fields} for row in scenarios],
        model_variant_or_study_probabilities_changed=False,
        frame_exchangeability_or_observed_staying_home_qualified=False,
        native_outcome_fitting_applied=False,
        complete_download={key: asset[key] for key in ("url", "bytes", "sha256")},
        query_downloads=query_downloads,
        release_base=asset["url"].rsplit("/", 1)[0] + "/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--publication", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new display-data version")
    result = build(args.analysis, args.publication)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

"""Build a model35 website projection from frozen SDKs and optional strict receipts."""

import argparse
import csv
from decimal import Decimal, localcontext
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile


MODEL_URL = (
    "https://github.com/hanshanley/margin_of_error/releases/download/"
    "participation-nc-or-native-controls-r35-20261114-01/complete-analysis.zip"
)
COUNT_URL = (
    "https://github.com/hanshanley/margin_of_error/releases/download/"
    "participation-nc-or-native-counts-20261114-01/complete-analysis.zip"
)
MODEL_PREFIX = "queries/reference-model35/"
COUNT_PREFIX = "queries/reference-counts/"


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def verify_sdk(path, expected_url):
    body = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError("Duplicate or corrupt SDK member")
        checksums = json.loads(archive.read("checksums.json"))
        if set(checksums) != set(names) - {"checksums.json", "REPRODUCE.txt"}:
            raise ValueError("SDK checksum inventory changed")
        for name, metadata in checksums.items():
            if pin(archive.read(name)) != metadata:
                raise ValueError("SDK member checksum changed: " + name)
        plan = json.loads(archive.read("publication-plan.json"))
        if (plan["url"] != expected_url or plan["status"] != "planned_immutable"
                or plan["immutable"] is not False
                or plan["verified_anonymously"] is not False):
            raise ValueError("Expected a private planned SDK")
        members = {name: archive.read(name) for name in names}
    return body, members


def publication_status(proof_path, sdk_body, expected_url):
    if proof_path is None:
        return {
            "status": "planned_immutable",
            "immutable": False,
            "verified_anonymously": False,
        }
    proof = json.loads(proof_path.read_bytes())
    assets = proof.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Actual immutable publication proof differs from the private SDK")
    matches = [item for item in assets
               if item.get("name") == "complete-analysis.zip"]
    if (proof.get("passed") is not True
            or proof.get("immutable") is not True
            or proof.get(
                "all_assets_authenticated_draft_and_anonymous_public_full_body_verified") is not True
            or len(assets) != 1 or len(matches) != 1
            or type(matches[0].get("id")) is not int or matches[0]["id"] <= 0
            or matches[0]["url"] != expected_url
            or matches[0]["bytes"] != len(sdk_body)
            or matches[0]["sha256"] != hashlib.sha256(sdk_body).hexdigest()):
        raise ValueError("Actual immutable publication proof differs from the private SDK")
    return {
        "status": "verified_immutable",
        "immutable": True,
        "verified_anonymously": True,
    }


def csv_rows(members, name):
    return list(csv.DictReader(io.StringIO(members[MODEL_PREFIX + name].decode())))


def member_descriptor(members, prefix, name, url):
    body = members[prefix + name]
    return {
        "member": prefix + name,
        "url": url + "#member=" + prefix + name,
        **pin(body),
    }


def replace(rows, updates, key):
    output = [dict(row) for row in rows]
    positions = {key(row): index for index, row in enumerate(output)}
    for row in updates:
        identity = key(row)
        if identity not in positions:
            raise ValueError("Overlay identity is absent from the accepted website projection")
        output[positions[identity]] = row
    return output


def build(base_display, model_sdk, count_sdk, model_publication=None, count_publication=None):
    base_body = base_display.read_bytes()
    base = json.loads(base_body)
    if (base["contract"] != "participation.registered_control_display.v1"
            or base["native_control_version"] != 34
            or len(base["states"]) != 51 or len(base["scenarios"]) != 34):
        raise ValueError("Accepted website model34 projection changed")
    model_body, model_members = verify_sdk(model_sdk, MODEL_URL)
    count_body, count_members = verify_sdk(count_sdk, COUNT_URL)
    if (model_publication is None) != (count_publication is None):
        raise ValueError("Model and count SDK publication proofs must advance together")
    model_status = publication_status(model_publication, model_body, MODEL_URL)
    count_status = publication_status(count_publication, count_body, COUNT_URL)
    if model_status != count_status:
        raise ValueError("Model and count SDK publication states differ")

    states = csv_rows(model_members, "complete-state-control-query.csv")
    scenarios = csv_rows(model_members, "complete-conditional-registered-scenarios.csv")
    summary = json.loads(model_members[MODEL_PREFIX + "summary.json"])
    nc_change = json.loads(
        model_members[MODEL_PREFIX + "reported-registered-reference-change.json"])
    or_change = json.loads(model_members[MODEL_PREFIX + "state-reference-change.json"])
    if (summary["native_control_version"] != 35 or len(states) != 51
            or len(scenarios) != 34 or nc_change["state_code"] != "NC"
            or or_change["state_code"] != "OR"
            or summary["study_fit_weights_or_probabilities_changed"] is not False
            or summary["native_count_used_for_outcome_fitting"] is not False):
        raise ValueError("Model35 source/control scope changed")

    state_fields = (
        "state_code", "civic_source_n", "control_id", "control_registered_denominator",
        "control_denominator_basis", "control_native_time", "control_source_url")
    scenario_fields = (
        "state_code", "control_id", "native_registered_denominator", "native_denominator_basis",
        "source_time_label", "source_url", "civic_source_n",
        "conditional_modeled_voter_count", "conditional_modeled_nonvoter_count")
    model_states = [{name: row[name] for name in state_fields} for row in states]
    model_scenarios = [{name: row[name] for name in scenario_fields} for row in scenarios]
    overlay_codes = {"NC", "OR"}
    overlay_states = [row for row in model_states if row["state_code"] in overlay_codes]
    overlay_scenarios = [
        row for row in model_scenarios
        if (row["state_code"], row["control_id"])
        in {("NC", "reporting-NC"), ("OR", "reporting-OR")}
    ]
    merged_states = replace(
        base["states"], overlay_states, lambda row: row["state_code"])
    merged_scenarios = replace(
        base["scenarios"], overlay_scenarios,
        lambda row: (row["state_code"], row["control_id"]))
    if ([row for row in merged_states if row["state_code"] not in overlay_codes]
            != [row for row in base["states"] if row["state_code"] not in overlay_codes]):
        raise ValueError("An unrelated state projection changed")
    if ([row for row in merged_scenarios if row["state_code"] not in overlay_codes]
            != [row for row in base["scenarios"] if row["state_code"] not in overlay_codes]):
        raise ValueError("An unrelated conditional scenario changed")

    count_dataset = json.loads(count_members[COUNT_PREFIX + "dataset.json"])
    count_index = json.loads(count_members[COUNT_PREFIX + "index.json"])
    current = json.loads(gzip.decompress(
        count_members[COUNT_PREFIX + count_index["current_snapshot"]["file"]]))
    current_rows = {
        row["state_code"]: row for row in current["snapshot"]["reporting"]
        if row["state_code"] in overlay_codes
    }
    if (count_dataset["version"]
            != "7afe2ba0db377e8d5a81c8b82c0b124834f3b8b6c3cf1c48181c9e5e3a4bb8c7"
            or current_rows["NC"]["ballots"] != nc_change["current_selected_reference"]
            or current_rows["NC"]["denominator"] != nc_change["registered_source_units"]
            or current_rows["OR"]["ballots"] != or_change["current_native_count"]
            or current_rows["OR"]["denominator"] != or_change["current_registered"]):
        raise ValueError("Count SDK and model35 controls are incoherent")

    nc_reference = {
        "kind": "reported_reference_fixed_register",
        "state_code": "NC",
        "control_id": nc_change["control_id"],
        "previous_native_numerator": nc_change["previous_selected_reference"],
        "current_native_numerator": nc_change["current_selected_reference"],
        "native_numerator_difference": nc_change["selected_reference_difference"],
        "previous_registered_denominator": nc_change["registered_source_units"],
        "current_registered_denominator": nc_change["registered_source_units"],
        "registered_denominator_difference": 0,
        "previous_native_clock": nc_change["previous_control"]["source_time_label"],
        "current_native_clock": current_rows["NC"]["source_update_label"],
        "previous_native_minus_model_diagnostic": (
            nc_change["previous_scenario"]["reported_cast_minus_conditional_modeled_voter_count"]),
        "current_native_minus_model_diagnostic": (
            nc_change["current_reported_minus_modeled_nominal_not_validated_error"]),
        "conditional_modeled_voter_unit_difference": "0",
        "conditional_modeled_nonvoter_unit_difference": "0",
        "source_weights_probabilities_and_fits_unchanged": True,
        "diagnostic_is_not_validated_model_error": True,
    }
    with localcontext() as context:
        context.prec = 80
        or_previous_diagnostic = str(
            Decimal(or_change["previous_model_reference"]["ballots"])
            - Decimal(or_change["previous_conditional_voter_units"]))
    or_reference = {
        "kind": "registered_reference",
        "state_code": "OR",
        "control_id": or_change["control_id"],
        "previous_native_numerator": or_change["previous_model_reference"]["ballots"],
        "current_native_numerator": or_change["current_native_count"],
        "native_numerator_difference": or_change["model_reference_count_difference"],
        "previous_registered_denominator": or_change["previous_model_reference"]["registered"],
        "current_registered_denominator": or_change["current_registered"],
        "registered_denominator_difference": or_change["model_registered_difference"],
        "previous_native_clock": or_change["previous_model_reference"]["clock"],
        "current_native_clock": current_rows["OR"]["source_update_label"],
        "previous_native_minus_model_diagnostic": or_previous_diagnostic,
        "current_native_minus_model_diagnostic": (
            or_change["native_minus_model_nominal_not_validated_error"]),
        "conditional_modeled_voter_unit_difference": (
            or_change["conditional_voter_unit_difference"]),
        "conditional_modeled_nonvoter_unit_difference": (
            or_change["conditional_nonvoter_unit_difference"]),
        "source_weights_probabilities_and_fits_unchanged": True,
        "diagnostic_is_not_validated_model_error": True,
    }

    public_names = sorted(
        name[len(MODEL_PREFIX):] for name in model_members
        if name.startswith(MODEL_PREFIX) and "/" not in name[len(MODEL_PREFIX):])
    if len(public_names) != 25:
        raise ValueError("Full model35 public output inventory changed")
    query_names = (
        "complete-state-control-query.csv",
        "complete-native-control-dispositions.csv",
        "complete-conditional-registered-scenarios.csv",
    )
    group_names = (
        "complete-native-participation-group-controls.csv",
        "complete-current-native-source-queries.json.gz",
    )
    result = {
        "contract": "participation.registered_control_display.v2",
        "year": 2026,
        "native_control_version": 35,
        "states": merged_states,
        "scenarios": merged_scenarios,
        "native_reference_changes": [nc_reference, or_reference],
        "retained_native_reference_changes": [base["native_reference_change"]],
        "model_variant_or_study_probabilities_changed": False,
        "frame_exchangeability_or_observed_staying_home_qualified": False,
        "native_outcome_fitting_applied": False,
        "publication_status": model_status,
        "count_publication_status": count_status,
        "complete_download": {"url": MODEL_URL, **pin(model_body)},
        "count_download": {
            "url": COUNT_URL, "version": count_dataset["version"], **pin(count_body)},
        "query_downloads": {
            name: member_descriptor(model_members, MODEL_PREFIX, name, MODEL_URL)
            for name in query_names
        },
        "source_group_downloads": {
            name: member_descriptor(model_members, MODEL_PREFIX, name, MODEL_URL)
            for name in group_names
        },
        "source_projection": {
            "base_display": pin(base_body),
            "base_native_control_version": 34,
            "model35_sdk": pin(model_body),
            "count_sdk": pin(count_body),
            "model35_public_outputs_verified": 25,
            "overlaid_state_codes": ["NC", "OR"],
            "preserved_other_state_codes": 49,
            "preserved_other_scenarios": 32,
            "retained_current_nm_revision": True,
            "candidate_model35_nm_predecessor_not_applied": True,
            "house_models_families_probabilities_weights_changed": False,
        },
        "prior_current_release": base["complete_download"],
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-display", type=Path, required=True)
    parser.add_argument("--model-sdk", type=Path, required=True)
    parser.add_argument("--count-sdk", type=Path, required=True)
    parser.add_argument("--model-publication", type=Path)
    parser.add_argument("--count-publication", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a fresh display projection path")
    result = build(
        args.base_display, args.model_sdk, args.count_sdk,
        args.model_publication, args.count_publication)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

"""Merge independently processed state evidence without promoting coverage to validation."""

import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path


BATCHES = {
    "agent-a": frozenset("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS".split()),
    "agent-b": frozenset("KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY".split()),
    "agent-c": frozenset("ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()),
}
STATES = frozenset().union(*BATCHES.values(), {"NC"})
COUNT_FIELDS = ("prior_positive", "current_positive", "both", "prior_only", "current_only", "neither")
PRIMARY_PERIODS = {(2020, 2022), (2022, 2024)}
JOINT_KINDS = {
    "administrative_joint_history", "published_vendor_aggregate_joint", "published_original_research_joint",
}
KINDS = JOINT_KINDS | {
    "survey_panel_recall_only", "marginals_only", "discovery_only", "blocked",
    "published_vendor_partial_transition_prior_only",
    "published_voter_file_aggregate_incompatible_joint_reconstruction",
}
KIND_ALIASES = {
    "published_original_research_county_tooltips_aggregated_to_statewide_joint_transition":
        "published_original_research_joint",
}


def checked_evidence(evidence):
    result = copy.deepcopy(evidence)
    a, b = evidence["prior_year"], evidence["current_year"]
    if type(a) is not int or type(b) is not int or a >= b:
        raise ValueError("Invalid historical election period")
    kind = KIND_ALIASES.get(evidence["evidence_kind"], evidence["evidence_kind"])
    if kind not in KINDS:
        raise ValueError("Unknown evidence type must be reviewed, not silently promoted")
    if kind != evidence["evidence_kind"]:
        result["source_evidence_kind"] = evidence["evidence_kind"]
        result["evidence_kind"] = kind
    for key in ("checked_arithmetic", "population_match", "public_release_qualified"):
        if type(evidence[key]) is not bool:
            raise ValueError("Explicit evidence qualification flags required")
    if not isinstance(evidence["source_population"], str) or not evidence["source_population"].strip():
        raise ValueError("Define the source population")
    counts = evidence["counts"]
    if set(counts) != set(COUNT_FIELDS):
        raise ValueError("Keep every count field; unknown counts must be null")
    if any(value is not None and (type(value) is not int or value < 0) for value in counts.values()):
        raise ValueError("History counts must be nonnegative integers or null")
    known = lambda keys: all(counts[key] is not None for key in keys)
    if known(("prior_positive", "both", "prior_only")):
        if counts["prior_positive"] != counts["both"] + counts["prior_only"]:
            raise ValueError("Prior history categories do not reconcile")
    if known(("current_positive", "both", "current_only")):
        if counts["current_positive"] != counts["both"] + counts["current_only"]:
            raise ValueError("Current history categories do not reconcile")
    if known(("prior_positive", "current_positive", "both")):
        if counts["both"] > min(counts["prior_positive"], counts["current_positive"]):
            raise ValueError("Overlap exceeds source marginals")
    complete = known(COUNT_FIELDS[:-1])
    cohort = evidence.get("source_cohort_compatible")
    if cohort is not None and type(cohort) is not bool:
        raise ValueError("Source-cohort compatibility must be explicit boolean or unknown")
    cohort_qualified = (cohort is True or (
        kind == "administrative_joint_history" and cohort is not False))
    for key in ("source_paths", "proof_paths"):
        if (not isinstance(evidence[key], list)
                or any(not isinstance(path, str) or not path.strip() for path in evidence[key])):
            raise ValueError("Source and verification paths must be explicit lists")
        if complete and evidence["checked_arithmetic"] and not evidence[key]:
            raise ValueError("Checked joint counts require source and proof artifacts")
    result["integration_joint_count_identities_checked"] = complete
    result["integration_source_cohort_qualified"] = cohort_qualified
    result["primary_midterm_period"] = (a, b) in PRIMARY_PERIODS
    result["supplementary_presidential_period"] = (a, b) == (2020, 2024)
    result["joint_benchmark_available_not_model_validation"] = (
        complete and evidence["checked_arithmetic"] and kind in JOINT_KINDS and cohort_qualified)
    result["record_union_n_not_eligible_population"] = (
        counts["prior_positive"] + counts["current_positive"] - counts["both"]
        if result["joint_benchmark_available_not_model_validation"] else None)
    return result


def checked_state(state):
    if state["state_code"] not in STATES:
        raise ValueError("Unknown state")
    for key in ("status", "next_action"):
        if not isinstance(state[key], str) or not state[key].strip():
            raise ValueError("Require an explicit state disposition and next action")
    for key in ("evidence", "access_dispositions", "limits"):
        if not isinstance(state[key], list):
            raise ValueError("State evidence, access and limitations must be lists")
    if not state["evidence"] and not state["access_dispositions"]:
        raise ValueError("No evidence or access disposition for state")
    result = copy.deepcopy(state)
    result["evidence"] = [checked_evidence(evidence) for evidence in state["evidence"]]
    result["primary_period_joint_evidence_available"] = any(
        e["primary_midterm_period"] and e["joint_benchmark_available_not_model_validation"]
        for e in result["evidence"])
    result["supplementary_joint_evidence_available"] = any(
        e["supplementary_presidential_period"] and e["joint_benchmark_available_not_model_validation"]
        for e in result["evidence"])
    result["model_population_validation_status"] = "not_established_by_evidence_integration"
    return result


def integrate(batches, nc, historical):
    if len(batches) != len(BATCHES) or {batch["batch"] for batch in batches} != set(BATCHES):
        raise ValueError("Require all three distinct state batches")
    combined = {}
    for batch in batches:
        codes = [state["state_code"] for state in batch["states"]]
        if len(codes) != len(BATCHES[batch["batch"]]) or set(codes) != BATCHES[batch["batch"]]:
            raise ValueError("Missing, duplicated or reassigned state in batch")
        for state in batch["states"]:
            combined[state["state_code"]] = checked_state(state)
    if nc["state_code"] != "NC":
        raise ValueError("Parent administrative evidence must be North Carolina")
    combined["NC"] = checked_state(nc)
    if set(combined) != STATES or len(combined) != 50:
        raise ValueError("Nationwide state inventory does not reconcile")
    prior = historical["states"]
    if len(prior) != 50 or {state["state_code"] for state in prior} != STATES:
        raise ValueError("Require the full 50-state historical diagnostic")
    diagnostics = {state["state_code"]: state for state in prior}
    states = []
    for code in sorted(STATES):
        state = combined[code]
        primary = diagnostics[code]["specifications"][0]
        state["historical_panel_primary_known_history_n"] = primary["dispositions"]["retained"]["n"]
        state["historical_panel_is_population_validation"] = False
        states.append(state)
    return {
        "status": "all_50_state_independent_participation_evidence_inventory",
        "states": states, "state_count": 50,
        "states_with_primary_period_joint_evidence": sum(s["primary_period_joint_evidence_available"] for s in states),
        "states_with_supplementary_joint_evidence": sum(s["supplementary_joint_evidence_available"] for s in states),
        "all_states_have_primary_period_joint_evidence": all(s["primary_period_joint_evidence_available"] for s in states),
        "evidence_coverage_is_not_model_validation": True,
        "population_method_validated": False,
        "public_release_qualified": False,
        "limits": [
            "Source-history counts, vendor-published aggregates and survey diagnostics are distinct evidence classes.",
            "Primary midterm periods are 2020-to-2022 and 2022-to-2024; 2020-to-2024 is supplementary only.",
            "Arithmetic identities and source availability do not independently validate population transport or candidate choices.",
            "Unknown neither, eligibility, first-ever status and missing history are not replaced with zero.",
            "No new 2026 correction, confidence interval or downward geographic allocation is fitted.",
        ],
    }


def resolve_artifact(path, root):
    root = root.resolve()
    candidate = Path(path)
    candidate = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if root not in candidate.parents or not candidate.is_file():
        raise ValueError("Missing evidence artifact or path outside explicit artifact root: " + path)
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", action="append", type=Path, required=True)
    parser.add_argument("--nc-evidence", type=Path, required=True)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--historical-proof", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise ValueError("Output must be new and outside the repository")
    historical_raw = args.historical.read_bytes()
    proof = json.loads(args.historical_proof.read_text())
    if (proof["status"] != "all_50_states_200_specifications_independently_verified"
            or proof["results_sha256"] != hashlib.sha256(historical_raw).hexdigest()):
        raise ValueError("Historical independent proof differs")
    result = integrate(
        [json.loads(path.read_text()) for path in args.batch],
        json.loads(args.nc_evidence.read_text()), json.loads(historical_raw))
    for state in result["states"]:
        for evidence in state["evidence"]:
            for name in ("source_paths", "proof_paths"):
                evidence["resolved_" + name] = [
                    str(resolve_artifact(path, args.artifact_root)) for path in evidence[name]]
    result["input_sha256"] = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in args.batch + [args.nc_evidence, args.historical, args.historical_proof]
    }
    args.output.mkdir(parents=True, mode=0o700)
    descriptor = os.open(args.output / "all-state-evidence.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(result, target, indent=2, allow_nan=False)
        target.write("\n")
    descriptor = os.open(args.output / "all-state-coverage.csv", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(["state", "primary_period_joint_evidence", "supplementary_joint_evidence",
                         "historical_panel_known_history_n", "disposition", "model_validation"])
        for state in result["states"]:
            writer.writerow([
                state["state_code"], state["primary_period_joint_evidence_available"],
                state["supplementary_joint_evidence_available"],
                state["historical_panel_primary_known_history_n"], state["status"],
                state["model_population_validation_status"],
            ])
    print(json.dumps({key: value for key, value in result.items() if key not in ("states", "input_sha256", "limits")}))


if __name__ == "__main__":
    main()

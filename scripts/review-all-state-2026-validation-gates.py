"""Attach historical evidence gates to unchanged provisional 2026 state comparisons."""

import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import zipfile


STATES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
ARCHIVE_SHA256 = "91f99be9779ddec465a96114903fe8afb080ae6adf21f038f057621e219a293a"


def review(historical, preliminary):
    states = historical["states"]
    if (historical["status"] != "all_50_state_historical_recall_diagnostics_not_population_validation"
            or len(states) != 50 or {s["state_code"] for s in states} != STATES
            or historical["population_method_validated"] is not False
            or any(s["population_method_validated"] is not False for s in states)):
        raise ValueError("Require the complete diagnostic, not claimed population validation")
    if preliminary["status"] != "preliminary_estimated_total_scenarios_not_validated_participation":
        raise ValueError("Require the qualified provisional 2026 estimate tier")
    comparisons = preliminary["state_comparisons"]
    keys = [(row["state_code"], row["contest_code"]) for row in comparisons]
    if len(set(keys)) != len(keys) or any(code not in STATES for code, _ in keys):
        raise ValueError("Duplicate or unknown state-contest comparison")
    jurisdictions = preliminary["jurisdictions"]
    if len(jurisdictions) != 51 or {r["state_code"] for r in jurisdictions} != STATES | {"DC"}:
        raise ValueError("Keep all state dispositions and DC separately")
    output = []
    for state in states:
        if len(state["specifications"]) != 4:
            raise ValueError("Incomplete state historical sensitivity analysis")
        primary = state["specifications"][0]
        current = [copy.deepcopy(row) for row in comparisons if row["state_code"] == state["state_code"]]
        native_disposition = next(row for row in jurisdictions if row["state_code"] == state["state_code"])
        turnout = native_disposition["preliminary_turnout"]
        ballots = turnout["ballots"]
        if (type(ballots) is not int or ballots <= 0
                or turnout["native_record"]["STATE_ABV"] != state["state_code"]
                or turnout["native_record"]["SOURCE"] != "Initial Estimate"):
            raise ValueError("Unqualified state provisional turnout")
        output.append({
            "state_code": state["state_code"],
            "estimated_2026_total_ballots": ballots,
            "estimated_2026_total_status": "initial_estimate_not_observed_certified_count",
            "historical_diagnostic_completed": True,
            "primary_known_history_n": primary["dispositions"]["retained"]["n"],
            "historical_survey_state_movers_excluded": state["different_prior_survey_state_excluded"],
            "historical_return_error_pp": {
                row["prior_coalition"]: row["return_error_pp"] for row in primary["comparisons"]},
            "historical_effective_samples_descriptive_not_design_precision": primary["baseline_effective_samples"],
            "population_validation_gate": {
                "status": "not_qualified",
                "state_representative_longitudinal_weights": False,
                "independent_matched_population_transition_benchmark": False,
                "complete_administrative_entry_exit_evidence": False,
                "certified_2026_transition_counts_allowed": False,
                "reason": "A paired retained-panel recall diagnostic does not establish state population transport, entrants or abstention.",
            },
            "conditional_2026_comparisons_unchanged": current,
            "conditional_contests_available": len(current),
            "current_estimate_status": (
                "conditional_only_not_historically_population_validated" if current
                else "no_qualified_state_joint_table_no_transition_estimate"),
            "native_2026_jurisdiction_disposition": copy.deepcopy(native_disposition),
        })
    return {
        "status": "all_state_2026_conditional_counts_with_historical_evidence_gates",
        "states": output,
        "state_count": 50,
        "states_with_conditional_2026_comparisons": len({code for code, _ in keys}),
        "conditional_state_contests": len(comparisons),
        "estimated_ballots_50_state_sum_excluding_dc": sum(s["estimated_2026_total_ballots"] for s in output),
        "states_population_validated": 0,
        "dc_disposition_separate": copy.deepcopy(next(r for r in jurisdictions if r["state_code"] == "DC")),
        "national_house_comparison_unchanged_not_state_allocated": copy.deepcopy(preliminary["national_house_comparison"]),
        "source_assumptions_and_limits_unchanged": copy.deepcopy(preliminary["assumptions_and_limits"]),
        "additional_limits": [
            "The historical test is 2020-to-2022, not a genuine 2022 House-to-2024 panel.",
            "Historical recall errors are not transferred as a fitted correction to 2026.",
            "All original 2026 numbers, suppressed choices, composition residuals, offices and source dispositions remain unchanged.",
            "Prior presidential nonvote composition is not identified first-ever voting or all-ballot nonparticipation.",
            "New registration is not first-time voting; no missing registration/history is reclassified as nonvoting.",
            "State-specific historical precision and population transport remain unqualified; no post-hoc passing threshold is used.",
            "EAVS aggregate registration/turnout controls would not alone identify individual transitions; native EAVS downloads returned HTTP403 and are not acquired evidence.",
            "No new certified count, confidence interval, demographic or local allocation is created.",
        ],
        "population_method_validated": False,
        "public_release_qualified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--independent-proof", type=Path, required=True)
    parser.add_argument("--preliminary-archive", type=Path, required=True)
    parser.add_argument("--eavs-source-disposition", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise ValueError("Output must be new and outside the repository")
    historical_raw = args.historical.read_bytes()
    eavs_raw = args.eavs_source_disposition.read_bytes()
    receipts = json.loads(eavs_raw)["receipts"]
    if len(receipts) != 6 or any(
            r.get("error_type") != "HTTPError" or r.get("error") != "HTTP Error 403: Forbidden"
            for r in receipts):
        raise ValueError("Review any changed EAVS source disposition before using this evidence gate")
    proof_raw = args.independent_proof.read_bytes()
    proof = json.loads(proof_raw)
    if (proof["status"] != "all_50_states_200_specifications_independently_verified"
            or proof["results_sha256"] != hashlib.sha256(historical_raw).hexdigest()):
        raise ValueError("Historical independent proof differs")
    archive_raw = args.preliminary_archive.read_bytes()
    if hashlib.sha256(archive_raw).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Frozen preliminary package differs")
    with zipfile.ZipFile(args.preliminary_archive) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt preliminary package")
        checksums = json.loads(archive.read("checksums.json"))
        for name, receipt in checksums.items():
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != receipt["sha256"] or len(raw) != receipt["bytes"]:
                raise ValueError("Preliminary package input checksum differs")
        candidates = [name for name in archive.namelist() if name.endswith("/estimated-coalition-scenarios.json")]
        if len(candidates) != 1:
            raise ValueError("Ambiguous preliminary analysis")
        preliminary = json.loads(archive.read(candidates[0]))
    result = review(json.loads(historical_raw), preliminary)
    result["source_binding"] = {
        "historical_sha256": hashlib.sha256(historical_raw).hexdigest(),
        "historical_independent_proof_sha256": hashlib.sha256(proof_raw).hexdigest(),
        "preliminary_complete_archive_sha256": ARCHIVE_SHA256,
        "eavs_source_disposition_sha256": hashlib.sha256(eavs_raw).hexdigest(),
        "reviewer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.mkdir(parents=True, mode=0o700)
    raw = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
    descriptor = os.open(args.output / "all-state-2026-gates.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        target.write(raw)
    descriptor = os.open(args.output / "all-50-state-participation-review.csv",
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", newline="") as target:
        fields = ["state", "estimated_2026_ballots_not_certified", "historical_primary_known_history_n",
                  "conditional_contests_available", "population_validation"]
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for state in result["states"]:
            writer.writerow(dict(zip(fields, [
                state["state_code"], state["estimated_2026_total_ballots"],
                state["primary_known_history_n"], state["conditional_contests_available"],
                "not_qualified",
            ])))
    print(json.dumps({"states": 50, "conditional_state_contests": len(preliminary["state_comparisons"]),
                      "population_validated_states": 0, "sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()

"""Calculate private state-specific age scenarios, not measured staying home."""

import argparse
import importlib.util
import itertools
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "state_age_math", Path(__file__).with_name("estimate-national-age-coalitions.py"))
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def calculate(historical, current, joint, prior_total):
    state, prior = historical["state_code"], historical["prior_choice"]
    sub = historical["native_current_survey_subset"]
    if (state not in model.age.historical.STATE_CODES.values() or state == "DC"
            or prior not in ("D", "R") or sub not in model.age.COHORTS
            or (historical["minimum_age"], historical["maximum_age"]) != model.age.COHORTS[sub]
            or current["state_code"] != state or current["subset"]["sub"] != sub
            or current["contest_code"] not in ("GG", "SG")
            or current["population_scope"] != "state"
            or current["status"] != "conditional_matched_demographic_count"
            or current["population_match"]["status"] != "matched_published_population"):
        raise ValueError("Mismatched state age/contest/population scope")
    if (joint["status"] != "published_joint_question_reviewed"
            or any(joint[key] != current[key] for key in ("state_code", "contest_code", "subset"))
            or any(joint[source] != current[target] for source, target in (
                ("source_url", "joint_source_url"), ("source_sha256", "joint_source_sha256"),
                ("source_timestamp", "joint_source_timestamp")))):
        raise ValueError("Joint source does not match the reviewed state count")
    low, high = [model.finite(historical[key]["fraction_within_reported_2024_coalition"])
                 for key in ("certain_age_support", "possible_age_support_including_unknown_birth_year")]
    n = model.finite(current["estimated_electorate_total"])
    g = model.finite(current["population_match"]["group_share_pct_of_current_electorate"])
    if not 0 <= low <= high <= 1 or model.finite(prior_total) < 0 or n <= 0 or not 0 <= g <= 100:
        raise ValueError("Invalid historical support or current population")
    q = {p: model.finite(current["composition"][p]["share_pct_of_current_group"]) for p in ("D", "R", "O", "N")}
    if (any(not 0 <= value <= 100 for value in q.values()) or not 98 <= sum(q.values()) <= 102
            or any(q[p] != joint["joint_question_rows"][p]["prior_choice_share_pct"] for p in q)):
        raise ValueError("Invalid or mismatched native prior composition")
    returning = model.finite(current["composition"][prior]["estimated_current_group_count"])
    if (not math.isclose(model.finite(current["estimated_current_group_count"]), n * g / 100,
                         rel_tol=1e-12, abs_tol=1e-7)
            or not math.isclose(returning, n * g / 100 * q[prior] / 100,
                                rel_tol=1e-12, abs_tol=1e-7)):
        raise ValueError("Current state group counts do not reconcile")
    opposite = {"D": "R", "R": "D"}[prior]
    flow = current["composition"][prior]["reported_current_choice_counts"][opposite]
    native_p = model.survey.percent(
        joint["joint_question_rows"][prior]["current_choice_pct_within_prior_choice"][opposite])
    p = native_p / 100 if native_p is not None else None
    if ((flow is None) != (p is None) or flow is not None and not math.isclose(
            model.finite(flow), returning * p, rel_tol=1e-12, abs_tol=1e-7)):
        raise ValueError("State flow does not reproduce the explicit native choice percentage")
    scenarios = []
    for endpoint, shift, scale, group_rounding, recall, prior_rounding in itertools.product(
        (low, high), (-.02, 0, .02), (.95, 1, 1.05), (-.5, 0, .5), (-2, 0, 2), (-.5, 0, .5)
    ):
        adjusted_q = {key: q[key] + (recall if key == "R" else -recall) for key in ("D", "R")}
        adjusted_q[prior] += prior_rounding
        axes = {
            "historical_birth_year_fraction_endpoint": endpoint,
            "assumed_historical_group_fraction_shift_pp": 100 * shift,
            "estimated_total_scale": scale, "current_group_rounding_pp": group_rounding,
            "harris_to_trump_recall_transfer_pp": recall, "current_prior_rounding_pp": prior_rounding,
        }
        if any(not 0 <= value <= 100 for value in adjusted_q.values()):
            scenarios.append({**axes, "status": "withheld_invalid_recall_or_rounding_scenario"})
            continue
        original = prior_total * min(1, max(0, endpoint + shift))
        count = n * scale * min(100, max(0, g + group_rounding)) / 100 * adjusted_q[prior] / 100
        switching = count * p if p is not None else 0. if count == 0 else None
        scenarios.append({
            **axes, "status": "conditional_sensitivity_scenario",
            "hypothetical_original_cohort_count": original,
            "current_reported_prior_count": count, "reported_opposite_choice_count": switching,
            "apparent_absence_count": original - count,
            "original_coalition_scaled_switching_pct":
                100 * switching / original if original > 0 and switching is not None else None,
        })
    old = [prior_total * fraction for fraction in (low, high)]
    return {
        "state_code": state, "contest_code": current["contest_code"],
        "subset": sub, "group": current["subset"]["longName"], "prior_choice": prior,
        "official_state_prior_coalition": prior_total,
        "birth_year_only_hypothetical_original_cohort": model.bounds(old),
        "estimated_current_reported_prior_count": returning,
        "reported_opposite_choice_count": flow,
        "current_switcher_rounding_only_envelope": None if native_p is None else {
            "lower": n * max(0, g - .5) / 100 * max(0, q[prior] - .5) / 100 * max(0, native_p - .5) / 100,
            "upper": n * min(100, g + .5) / 100 * min(100, q[prior] + .5) / 100 * min(100, native_p + .5) / 100,
        },
        "birth_year_only_apparent_absence": model.bounds([value - returning for value in old]),
        "birth_year_only_original_coalition_scaled_switching_pct":
            model.bounds([100 * flow / value for value in old]) if flow is not None and min(old) > 0 else None,
        "negative_birth_year_residual_endpoint": min(old) < returning,
        "sensitivity_scenarios": scenarios,
        "measured_staying_home_count": None, "identified_new_or_returning_count": None,
        "demographic_turnout_rate": None, "share_of_total_swing": None,
        "design_confidence_interval": None,
    }


def estimate(historical, current, baselines, joint_review):
    if (historical["status"] != "private_state_birth_year_support_not_qualified_population_estimates"
            or historical["historical_controls_checked"] is not True):
        raise ValueError("Unchecked state-specific historical support")
    model.national_baselines(baselines)
    history, joints, seen, estimates = {}, {}, set(), []
    for row in historical["cohorts"]:
        key = row["state_code"], row["native_current_survey_subset"], row["prior_choice"]
        if key in history:
            raise ValueError("Duplicate historical state age cohort")
        history[key] = row
    for row in joint_review["tables"]:
        key = row["state_code"], row["contest_code"], row["subset"]["sub"]
        if key in joints:
            raise ValueError("Duplicate state joint table")
        joints[key] = row
    for row in current["estimates"]:
        state, contest, sub = row["state_code"], row["contest_code"], row["subset"]["sub"]
        if state == "US" or sub not in model.age.COHORTS:
            continue
        key = state, contest, sub
        if key in seen or key not in joints:
            raise ValueError("Duplicate or missing current state joint age table")
        seen.add(key)
        for prior in ("D", "R"):
            if (state, sub, prior) not in history:
                raise ValueError("Missing state-specific historical age cohort")
            estimates.append(calculate(history[state, sub, prior], row, joints[key], baselines[state][prior]))
    if not estimates:
        raise ValueError("No matched state-specific age comparisons")
    return {
        "status": "private_conditional_state_age_scenarios_not_release_qualified",
        "estimates": estimates,
        "jurisdiction_coverage": [{
            "state_code": state, "matched_state_contest_age_tables": sum(key[0] == state for key in seen),
            "status": "private_conditional_scenarios" if any(key[0] == state for key in seen)
            else "no_qualified_current_age_comparison_in_frozen_release",
        } for state in sorted(baselines)],
        "assumptions_and_limits": [
            "State-specific CES coalition support scales that state's official2024coalition, never national shares.",
            "Current counts use the same state's qualified contest/population/joint-source release.",
            "Prospective birth-year support does not observe survival,residence,or2026participation.",
            "Apparent absence includes death,migration,recall,response-population,and historical composition error.",
            "Birthday and assumed historicalmix+-2pp,recall+-2pp,total95/100/105percent ranges are not confidence intervals.",
            "The main grid holds explicit native conditional choice fixed; its rounding envelope is separate.",
            "Retain signed negatives and rates exceeding100percent as diagnostics,not physical nonvoting counts.",
            "Rounded zero does not establish zero switching; suppressed cells are not reconstructed.",
            "Groups18-29and18-44overlap; offices,groups,and marginal endpoints are not additive.",
            "SSRS choices can retain initial pre-election intentions; outcome calibration is not validation.",
            "Small cells and all scenarios stay private pending state-specific precision/disclosure qualification.",
            "No measured stayinghome,new/returning identity,demographic turnout,causal persuasion,or total-swing share.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("historical", "current", "baselines", "joint", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT in args.output.resolve().parents:
        raise ValueError("Use a new private output outside the repository")
    result = estimate(*(json.loads(getattr(args, name).read_text())
                        for name in ("historical", "current", "baselines")),
                      model.survey.review_snapshot(json.loads(args.joint.read_text())))
    result["input_sha256"] = {name: model.age.historical.digest(getattr(args, name), "sha256")
                              for name in ("historical", "current", "baselines", "joint")}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"age_coalition_contests": len(result["estimates"]),
                      "states_with_estimates": len({row["state_code"] for row in result["estimates"]}),
                      "public_release_qualified": False}))

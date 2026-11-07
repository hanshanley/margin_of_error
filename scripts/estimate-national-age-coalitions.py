"""Compute private national prospective-age scenarios, not measured staying home."""

import argparse
import importlib.util
import itertools
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "national_age_support", Path(__file__).with_name("review-ces-age-cohorts.py"))
age = importlib.util.module_from_spec(spec)
spec.loader.exec_module(age)
spec = importlib.util.spec_from_file_location(
    "national_age_joint", Path(__file__).with_name("review-cnn-voter-poll.py"))
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid numeric input")
    return value


def national_baselines(baselines):
    if set(baselines) != set(age.historical.STATE_CODES.values()):
        raise ValueError("Incomplete official state/DC baselines")
    for row in baselines.values():
        if any(type(row[key]) is not int or row[key] < 0 for key in ("D", "R", "all_presidential_votes")):
            raise ValueError("Invalid official coalition count")
        if row["D"] + row["R"] > row["all_presidential_votes"]:
            raise ValueError("Official choices exceed the presidential total")
    return {party: sum(row[party] for state, row in baselines.items() if state != "DC")
            for party in ("D", "R")}


def bounds(values):
    return {"lower": min(values), "upper": max(values)}


def calculate(historical, current, joint, prior_total):
    sub, prior = historical["native_current_survey_subset"], historical["prior_choice"]
    if (historical["scope"] != "50_states_excluding_DC" or prior not in ("D", "R")
            or sub not in age.COHORTS or current["state_code"] != "US"
            or current["contest_code"] != "HG" or current["subset"]["sub"] != sub
            or current["population_scope"] != "50_states_excluding_DC"
            or current["status"] != "conditional_matched_demographic_count"
            or current["population_match"]["status"] != "matched_published_population"):
        raise ValueError("Mismatched national age/contest/population scope")
    if (historical["minimum_age"], historical["maximum_age"]) != age.COHORTS[sub]:
        raise ValueError("Historical age cohort redefined")
    if (joint["status"] != "published_joint_question_reviewed"
            or joint["state_code"] != "US" or joint["contest_code"] != "HG"
            or joint["subset"] != current["subset"]
            or any(joint[source] != current[target] for source, target in (
                ("source_url", "joint_source_url"), ("source_sha256", "joint_source_sha256"),
                ("source_timestamp", "joint_source_timestamp")))):
        raise ValueError("Joint source does not match the reviewed current count")
    low, high = [finite(historical[key]["fraction_within_reported_2024_coalition"]) for key in
                 ("certain_age_support", "possible_age_support_including_unknown_birth_year")]
    if not 0 <= low <= high <= 1 or finite(prior_total) < 0:
        raise ValueError("Invalid historical cohort support")
    n = finite(current["estimated_electorate_total"])
    g = finite(current["population_match"]["group_share_pct_of_current_electorate"])
    if n <= 0 or not 0 <= g <= 100:
        raise ValueError("Invalid current population")
    q = {p: finite(current["composition"][p]["share_pct_of_current_group"]) for p in ("D", "R", "O", "N")}
    if any(not 0 <= value <= 100 for value in q.values()) or not 98 <= sum(q.values()) <= 102:
        raise ValueError("Invalid rounded prior composition")
    if any(q[p] != joint["joint_question_rows"][p]["prior_choice_share_pct"] for p in q):
        raise ValueError("Current and native prior compositions differ")
    returning = finite(current["composition"][prior]["estimated_current_group_count"])
    if not math.isclose(returning, n * g / 100 * q[prior] / 100, rel_tol=1e-12, abs_tol=1e-7):
        raise ValueError("Current group counts do not reconcile")
    other = {"D": "R", "R": "D"}[prior]
    flow = current["composition"][prior]["reported_current_choice_counts"][other]
    if flow is not None and not 0 <= finite(flow) <= returning + 1e-7:
        raise ValueError("Invalid published conditional flow")
    native_p = survey.percent(joint["joint_question_rows"][prior]["current_choice_pct_within_prior_choice"][other])
    p = native_p / 100 if native_p is not None else None
    if ((flow is None) != (p is None) or flow is not None and not math.isclose(
            flow, returning * p, rel_tol=1e-12, abs_tol=1e-7)):
        raise ValueError("Current flow does not reproduce the explicit native choice percentage")
    old = [prior_total * fraction for fraction in (low, high)]
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
        current_count = n * scale * min(100, max(0, g + group_rounding)) / 100 * adjusted_q[prior] / 100
        switching = current_count * p if p is not None else 0. if current_count == 0 else None
        scenarios.append({
            **axes, "status": "conditional_sensitivity_scenario",
            "hypothetical_original_cohort_count": original,
            "current_reported_prior_count": current_count,
            "reported_opposite_choice_count": switching,
            "apparent_absence_count": original - current_count,
            "original_coalition_scaled_switching_pct":
                100 * switching / original if original > 0 and switching is not None else None,
        })
    valid = [item for item in scenarios if item["status"] == "conditional_sensitivity_scenario"]
    return {
        "subset": sub, "group": current["subset"]["longName"], "prior_choice": prior,
        "birth_year_only_hypothetical_original_cohort": bounds(old),
        "estimated_current_reported_prior_count": returning,
        "reported_opposite_choice_count": flow,
        "current_switcher_rounding_only_envelope": None if native_p is None else {
            "lower": n * max(0, g - .5) / 100 * max(0, q[prior] - .5) / 100 * max(0, native_p - .5) / 100,
            "upper": n * min(100, g + .5) / 100 * min(100, q[prior] + .5) / 100 * min(100, native_p + .5) / 100,
        },
        "birth_year_only_apparent_absence": bounds([value - returning for value in old]),
        "birth_year_only_original_coalition_scaled_switching_pct":
            bounds([100 * flow / value for value in old]) if flow is not None and min(old) > 0 else None,
        "negative_birth_year_residual_endpoint": min(old) < returning,
        "marginal_sensitivity_apparent_absence": bounds([item["apparent_absence_count"] for item in valid]),
        "sensitivity_scenarios": scenarios,
        "measured_staying_home_count": None, "identified_new_or_returning_count": None,
        "demographic_turnout_rate": None, "share_of_total_swing": None,
        "design_confidence_interval": None,
    }


def estimate(historical, current, baselines, joint_review):
    if (historical["status"] != "private_national_birth_year_support_not_demographic_dropoff"
            or historical["historical_controls_checked"] is not True):
        raise ValueError("Unchecked historical cohort support")
    totals = national_baselines(baselines)
    groups = {}
    for row in current["estimates"]:
        if row["state_code"] == "US" and row["subset"]["sub"] in age.COHORTS:
            sub = row["subset"]["sub"]
            if sub in groups:
                raise ValueError("Duplicate current national age group")
            groups[sub] = row
    if set(groups) != set(age.COHORTS):
        raise ValueError("Missing current national age group")
    joints = {}
    for row in joint_review["tables"]:
        if row["state_code"] == "US" and row["subset"]["sub"] in age.COHORTS:
            sub = row["subset"]["sub"]
            if sub in joints:
                raise ValueError("Duplicate national joint age table")
            joints[sub] = row
    if set(joints) != set(groups):
        raise ValueError("Missing native national joint age table")
    if any(row["estimated_electorate_total"] != current["national_50_state_estimated_turnout"]
           for row in groups.values()):
        raise ValueError("National current totals differ")
    estimates, seen = [], set()
    for cohort in historical["cohorts"]:
        key = cohort["native_current_survey_subset"], cohort["prior_choice"]
        if key in seen or key[0] not in groups or key[1] not in totals:
            raise ValueError("Duplicate or unknown historical cohort")
        seen.add(key)
        estimates.append(calculate(cohort, groups[key[0]], joints[key[0]], totals[key[1]]))
    if seen != set(itertools.product(age.COHORTS, ("D", "R"))):
        raise ValueError("Missing historical national age cohort")
    return {
        "status": "private_conditional_prospective_age_scenarios_not_release_qualified",
        "population_scope": "50_states_excluding_DC", "national_official_prior_coalitions": totals,
        "estimates": estimates,
        "assumptions_and_limits": [
            "Official2024coalitions are scaled by coalition-conditioned CES weighted birth-year support, not current preference calibration.",
            "The same prospective2026age bands are used; a2024age18-29category is not substituted.",
            "Calendar-year birthday ambiguity is retained without imputing a birthday or survival.",
            "The current total/group/prior counts remain conditional on UF preliminary totals and the SSRS response-population assumption.",
            "Apparent absence includes death,migration,recall,source-population and historical composition error; it is not measured staying home.",
            "Birth-year ranges,rounding envelopes,and prespecified historical-mix/recall/turnout stresses are not confidence intervals.",
            "The main sensitivity grid holds explicit native conditional choice percentages fixed; their rounding is shown separately.",
            "Historical fraction shifts+-2pp and estimated-total scales95/100/105percent are assumptions, not empirically estimated uncertainty bounds.",
            "Negative residuals and rates exceeding100percent remain model/source diagnostics, not physical nonvoter counts.",
            "Rounded zero and absent conditional cells do not establish zero switching; suppressed values are never reconstructed.",
            "Current House choices can retain pre-election intentions; no administrative candidate-choice validation is claimed.",
            "National age groups18-29and18-44overlap; offices,groups and marginal endpoints must not be added.",
            "No state/local allocation,demographic turnout,new/returning identity,causal persuasion or overall-swing share is identified.",
            "Publication still requires disclosure/precision review,complete selected aggregate inputs,and additive UI acceptance.",
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
                      survey.review_snapshot(json.loads(args.joint.read_text())))
    result["input_sha256"] = {name: age.historical.digest(getattr(args, name), "sha256")
                              for name in ("historical", "current", "baselines", "joint")}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"age_coalitions": len(result["estimates"]), "public_release_qualified": False,
                      "negative_reference_endpoints": sum(
                          row["negative_birth_year_residual_endpoint"] for row in result["estimates"])}))

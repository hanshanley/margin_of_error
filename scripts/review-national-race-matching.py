"""Quantify private race-definition diagnostics, not qualified demographic drop-off."""

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "race_matching_controls", Path(__file__).with_name("estimate-national-age-coalitions.py"))
controls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controls)
GROUPS = {5: ("White", "Non-Hispanic White"), 6: ("Black", "Non-Hispanic Black"),
          7: ("Hispanic", "Hispanic")}
DIMENSIONS = ("source_race_2024", "race_ethnicity_2024")
HISTORICAL_SHA256 = "80fff0c5cd3df49d7d6a2a782c339e62f1286041170ddafd73c090495e9cb88a"


def historical_groups(coalition, dimension):
    rows = coalition["partitions"][dimension]
    if len({row["group"] for row in rows}) != len(rows):
        raise ValueError("Duplicate historical demographic group")
    total = controls.finite(coalition["sum_weight"])
    squared = controls.finite(coalition["sum_squared_weight"])
    count = coalition["respondents"]
    if total <= 0 or squared <= 0 or type(count) is not int or count <= 0:
        raise ValueError("Invalid historical coalition controls")
    for row in rows:
        weight = controls.finite(row["sum_weight"])
        square = controls.finite(row["sum_squared_weight"])
        fraction = controls.finite(row["fraction_within_reported_2024_coalition"])
        if (type(row["respondents"]) is not int or row["respondents"] <= 0
                or not 0 < weight <= total or not 0 < square <= squared
                or not 0 < fraction <= 1
                or not math.isclose(fraction, weight / total, rel_tol=1e-12, abs_tol=1e-12)):
            raise ValueError("Invalid historical demographic sufficient statistics")
    for key in ("sum_weight", "sum_squared_weight", "respondents"):
        if not math.isclose(sum(row[key] for row in rows), coalition[key], rel_tol=1e-10, abs_tol=1e-8):
            raise ValueError("Historical partition does not retain the full coalition")
    return {row["group"]: row for row in rows}


def calculate(historical, current, joint, prior, prior_total, dimension, label):
    sub = current["subset"]["sub"]
    if (sub not in GROUPS or label != GROUPS[sub][DIMENSIONS.index(dimension)]
            or current["state_code"] != "US" or current["contest_code"] != "HG"
            or current["population_scope"] != "50_states_excluding_DC"
            or current["status"] != "conditional_matched_demographic_count"
            or current["population_match"]["status"] != "matched_published_population"
            or current["population_match"]["question_id"] != 260
            or current["population_match"]["answer"] != ("Latino" if sub == 7 else GROUPS[sub][0])
            or prior not in ("D", "R") or controls.finite(prior_total) <= 0):
        raise ValueError("Mismatched national race/contest/population scope")
    if (joint["status"] != "published_joint_question_reviewed"
            or joint["state_code"] != "US" or joint["contest_code"] != "HG"
            or joint["subset"] != current["subset"]
            or any(joint[source] != current[target] for source, target in (
                ("source_url", "joint_source_url"), ("source_sha256", "joint_source_sha256"),
                ("source_timestamp", "joint_source_timestamp")))):
        raise ValueError("Joint source does not match the reviewed current count")
    n = controls.finite(current["estimated_electorate_total"])
    g = controls.finite(current["population_match"]["group_share_pct_of_current_electorate"])
    q = {p: controls.finite(current["composition"][p]["share_pct_of_current_group"])
         for p in ("D", "R", "O", "N")}
    if n <= 0 or not 0 <= g <= 100 or any(not 0 <= value <= 100 for value in q.values()):
        raise ValueError("Invalid current population or prior-choice composition")
    if not 98 <= sum(q.values()) <= 102 or any(
            q[p] != joint["joint_question_rows"][p]["prior_choice_share_pct"] for p in q):
        raise ValueError("Incomplete or changed native prior composition")
    returning = controls.finite(current["composition"][prior]["estimated_current_group_count"])
    if not math.isclose(returning, n * g / 100 * q[prior] / 100, rel_tol=1e-12, abs_tol=1e-7):
        raise ValueError("Current group counts do not reconcile")
    opposite = {"D": "R", "R": "D"}[prior]
    native_p = controls.survey.percent(
        joint["joint_question_rows"][prior]["current_choice_pct_within_prior_choice"][opposite])
    flow = current["composition"][prior]["reported_current_choice_counts"][opposite]
    if ((flow is None) != (native_p is None) or flow is not None and (
            not 0 <= controls.finite(flow) <= returning + 1e-7
            or not math.isclose(flow, returning * native_p / 100, rel_tol=1e-12, abs_tol=1e-7))):
        raise ValueError("Current flow does not reproduce the explicit native choice")
    fraction = controls.finite(historical["fraction_within_reported_2024_coalition"])
    if historical["group"] != label or not 0 < fraction <= 1:
        raise ValueError("Historical label or coalition denominator differs")
    original = prior_total * fraction
    return {
        "subset": sub, "current_source_label": current["population_match"]["answer"],
        "prior_choice": prior, "historical_dimension": dimension, "historical_source_label": label,
        "historical_fraction_within_full_prior_coalition": fraction,
        "historical_raw_group_base": historical["respondents"],
        "historical_kish_weight_concentration_diagnostic":
            historical["sum_weight"] ** 2 / historical["sum_squared_weight"],
        "hypothetical_original_group_if_labels_matched": original,
        "estimated_current_reported_prior_count": returning,
        "native_opposite_choice_pct_within_current_prior": native_p,
        "reported_opposite_choice_count": flow,
        "apparent_absence_if_labels_matched": original - returning,
        "original_group_scaled_opposite_choice_pct_if_labels_matched":
            100 * flow / original if flow is not None else None,
        "negative_residual_diagnostic": original < returning,
        "cross_source_matching_qualified": False, "public_release_qualified": False,
        "measured_staying_home_count": None, "identified_new_or_returning_count": None,
        "demographic_turnout_rate": None, "share_of_total_swing": None,
        "design_confidence_interval": None,
    }


def review(historical, current, baselines, joint_review):
    if historical["status"] != "private_historical_demographic_audit_not_qualified_2026_baseline":
        raise ValueError("Wrong historical audit")
    totals = controls.national_baselines(baselines)
    coalitions = [row for row in historical["coalitions"]
                  if row["scope"] == "US50" and row["prior_choice"] in ("D", "R")]
    if len(coalitions) != 2 or {row["prior_choice"] for row in coalitions} != {"D", "R"}:
        raise ValueError("Missing or duplicate historical50state coalition")
    groups, joints = {}, {}
    for source, target in ((current["estimates"], groups), (joint_review["tables"], joints)):
        for row in source:
            if row["state_code"] == "US" and row["subset"]["sub"] in GROUPS:
                sub = row["subset"]["sub"]
                if sub in target:
                    raise ValueError("Duplicate current national race group")
                target[sub] = row
        if set(target) != set(GROUPS):
            raise ValueError("Missing current national race group")
    diagnostics = []
    for coalition in coalitions:
        prior = coalition["prior_choice"]
        for index, dimension in enumerate(DIMENSIONS):
            cells = historical_groups(coalition, dimension)
            for sub, labels in GROUPS.items():
                if groups[sub]["estimated_electorate_total"] != current["national_50_state_estimated_turnout"]:
                    raise ValueError("National current totals differ")
                label = labels[index]
                if label not in cells:
                    raise ValueError("Missing historical demographic support")
                diagnostics.append(calculate(cells[label], groups[sub], joints[sub],
                                             prior, totals[prior], dimension, label))
    return {
        "status": "private_unqualified_national_race_definition_diagnostics",
        "population_scope": "50_states_excluding_DC", "national_official_prior_coalitions": totals,
        "source_audit": historical["source_audit"], "diagnostics": diagnostics,
        "alternative_definitions_are_not_identification_bounds": True,
        "cross_source_matching_qualified": False, "public_release_qualified": False,
        "limits": [
            "Source race and combined race/ethnicity are different CES operationalizations. Their alternatives are not interchangeable groups or uncertainty bounds.",
            "CNN exports White/Black/Latino categories; selected SSRS methods identify self-reported Race/Ethnicity but do not resolve complete category operationalization.",
            "Conditional calculations hold published current-group composition/choices fixed to expose historical-definition sensitivity, not identify true group residuals.",
            "Unknown and unselected categories remain in each historical coalition denominator; no historical group renormalization is applied.",
            "Historical demographic identity can change. Death,migration,recall,response-population and historical composition error remain in any hypothetical residual.",
            "Current counts depend on preliminaryUFtotals and the unvalidated SSRS all-ballot response-population assumption; retained initial intentions are not universally completed choices.",
            "Raw bases and Kish diagnostics are not design precision or automatic publication qualification. No sampling/design CIs are supplied.",
            "Negative residuals and rates exceeding100percent remain diagnostics, never clamped into physical nonvoting.",
            "This private calculation is not qualified for public demographic drop-off, measured staying home,new/returning identity,turnout,total-swing shares or state/local allocation.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("historical", "current", "baselines", "joint", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT in args.output.resolve().parents:
        raise ValueError("Use a new private output outside the repository")
    pins = {name: hashlib.sha256(getattr(args, name).read_bytes()).hexdigest()
            for name in ("historical", "current", "baselines", "joint")}
    if pins["historical"] != HISTORICAL_SHA256:
        raise ValueError("Frozen historical control changed")
    result = review(*(json.loads(getattr(args, name).read_text())
                      for name in ("historical", "current", "baselines")),
                    controls.survey.review_snapshot(json.loads(args.joint.read_text())))
    result["input_sha256"] = pins
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"definition_diagnostics": len(result["diagnostics"]),
                      "cross_source_matching_qualified": False, "public_release_qualified": False}))

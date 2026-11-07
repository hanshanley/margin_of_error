"""Audit private state-specific prospective age support, not demographic drop-off."""

import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "state_age_support", Path(__file__).with_name("review-ces-age-cohorts.py"))
age = importlib.util.module_from_spec(spec)
spec.loader.exec_module(age)


def review(rows, control):
    audit = age.historical.review(rows, demographics_fn=age.memberships)
    if audit["source_audit"] != control["source_audit"]:
        raise ValueError("Historical respondent dispositions differ")
    keys = ("respondents", "sum_weight", "sum_squared_weight")
    expected = {(item["scope"], item["prior_choice"]): item for item in control["coalitions"]}
    actual = {(item["scope"], item["prior_choice"]): item for item in audit["coalitions"]}
    if (len(expected) != len(control["coalitions"]) or set(expected) != set(actual)
            or any(not math.isclose(item[key], expected[identity][key],
                                    rel_tol=1e-12, abs_tol=1e-8)
                   for identity, item in actual.items() for key in keys)):
        raise ValueError("Historical state/national coalition controls differ")
    results = []
    empty = {"respondents": 0, "sum_weight": 0., "sum_squared_weight": 0.}
    for total in audit["coalitions"]:
        if total["scope"] not in age.historical.STATE_CODES.values() or total["prior_choice"] not in ("D", "R"):
            continue
        for sub, (lower, upper) in age.COHORTS.items():
            groups = {item["group"]: item for item in total["partitions"][str(sub)]}
            possible = age.combine([groups.get(key, empty)
                                    for key in ("certain", "birthday_boundary", "unknown")])
            results.append({
                "state_code": total["scope"], "prior_choice": total["prior_choice"],
                "native_current_survey_subset": sub, "minimum_age": lower, "maximum_age": upper,
                "coalition": {**{key: total[key] for key in keys},
                              "effective_sample_size": total["effective_sample_size"]},
                "certain_age_support": age.support(groups.get("certain", empty), total),
                "possible_age_support_including_unknown_birth_year": age.support(possible, total),
                "birthday_boundary_respondents": groups.get("birthday_boundary", empty)["respondents"],
                "unknown_birth_year_respondents": groups.get("unknown", empty)["respondents"],
            })
    if not results:
        raise ValueError("No state major-party coalition support")
    return {
        "status": "private_state_birth_year_support_not_qualified_population_estimates",
        "source_audit": audit["source_audit"], "cohorts": results,
        "historical_controls_checked": True,
        "original_group_population_estimates": None, "group_dropoff_estimates": None,
        "design_confidence_intervals": None,
        "limits": [
            "Each fraction uses only that state's validated2024turnout/reported-choice/weight subset.",
            "Every state and national coalition control is checked; national shares are never allocated to states.",
            "DC is a separate historical scope, not an available2026SSRSstate comparison.",
            "A birth year gives calendar2026ages2025-b..2026-b; birthdays are not imputed.",
            "Unknown birth years remain in the full state coalition denominator and possible support.",
            "These are hypothetically aged2024participants, not observed2026survivors,residents,or voters.",
            "Changing residence and survey-voterfile state agreement do not identify a fixed state cohort.",
            "Effective bases and birthday ranges are diagnostics, not design CIs or publication thresholds.",
            "The18-29and18-44groups overlap; groups,offices,and marginal endpoints are not additive.",
            "Matching current state/contest/population sources and precision/disclosure review remain required.",
            "Small cells remain private; no state population,dropoff,turnout,or total-swing share is released.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("survey", "guide", "labels", "control", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT in args.output.resolve().parents:
        raise ValueError("Use a new private output outside the repository")
    if (age.historical.digest(args.survey, "sha256") != age.historical.CSV_SHA256
            or age.historical.digest(args.guide, "md5") != age.historical.GUIDE_MD5
            or age.historical.digest(args.control, "sha256") != age.CONTROL_SHA256):
        raise ValueError("Frozen historical source, guide or controls changed")
    age.historical.verify_labels(json.loads(args.labels.read_text()))
    with args.survey.open(newline="") as source:
        result = review(csv.DictReader(source), json.loads(args.control.read_text()))
    result["source_pins"] = {
        "survey_sha256": age.historical.CSV_SHA256, "guide_md5": age.historical.GUIDE_MD5,
        "control_sha256": age.CONTROL_SHA256,
        "native_label_audit_sha256": age.historical.digest(args.labels, "sha256"),
        "doi": "10.7910/DVN/X11EP6", "release": "9.0", "license": "CC0 1.0",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"cohorts": len(result["cohorts"]),
                      "jurisdictions": len({item["state_code"] for item in result["cohorts"]}),
                      "historical_controls_checked": True,
                      "population_estimates_released": False, "output": str(args.output)}))

"""Audit prospective national age-cohort support without assuming known birthdays."""

import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ces_age_historical", Path(__file__).with_name("review-ces-demographic-baselines.py"))
historical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(historical)
COHORTS = {53: (18, 29), 54: (18, 44), 55: (65, None)}
CONTROL_SHA256 = "80fff0c5cd3df49d7d6a2a782c339e62f1286041170ddafd73c090495e9cb88a"


def memberships(row):
    birth = row["birthyr"]
    valid = birth.isdigit() and 1904 <= int(birth) <= 2006
    result = {}
    for sub, (lower, upper) in COHORTS.items():
        if not valid:
            status = "unknown"
        else:
            # A birth year alone gives two possible ages during calendar 2026.
            minimum, maximum = 2025 - int(birth), 2026 - int(birth)
            if minimum >= lower and (upper is None or maximum <= upper):
                status = "certain"
            elif maximum >= lower and (upper is None or minimum <= upper):
                status = "birthday_boundary"
            else:
                status = "outside"
        result[str(sub)] = status
    return result


def combine(groups):
    return {key: sum(group[key] for group in groups)
            for key in ("respondents", "sum_weight", "sum_squared_weight")}


def support(group, total):
    squared = group["sum_squared_weight"]
    return {
        **group, "fraction_within_reported_2024_coalition": group["sum_weight"] / total["sum_weight"],
        "effective_sample_size": group["sum_weight"] ** 2 / squared if squared else None,
    }


def review(rows, control=None):
    audit = historical.review(rows, demographics_fn=memberships)
    if control is not None and audit["source_audit"] != control["source_audit"]:
        raise ValueError("Historical respondent dispositions differ")
    results = []
    empty = {"respondents": 0, "sum_weight": 0., "sum_squared_weight": 0.}
    for total in audit["coalitions"]:
        if total["scope"] != "US50" or total["prior_choice"] not in ("D", "R"):
            continue
        if control is not None:
            matches = [row for row in control["coalitions"]
                       if row["scope"] == "US50" and row["prior_choice"] == total["prior_choice"]]
            if len(matches) != 1 or any(
                not math.isclose(total[key], matches[0][key], rel_tol=1e-12, abs_tol=1e-8)
                for key in empty
            ):
                raise ValueError("Historical national coalition controls differ")
        for sub, (lower, upper) in COHORTS.items():
            groups = {group["group"]: group for group in total["partitions"][str(sub)]}
            certain = groups.get("certain", empty)
            possible = combine([groups.get(key, empty)
                                for key in ("certain", "birthday_boundary", "unknown")])
            results.append({
                "scope": "50_states_excluding_DC", "prior_choice": total["prior_choice"],
                "native_current_survey_subset": sub, "minimum_age": lower, "maximum_age": upper,
                "coalition": {**{key: total[key] for key in empty},
                              "effective_sample_size": total["effective_sample_size"]},
                "certain_age_support": support(certain, total),
                "possible_age_support_including_unknown_birth_year": support(possible, total),
                "birthday_boundary_respondents": groups.get("birthday_boundary", empty)["respondents"],
                "unknown_birth_year_respondents": groups.get("unknown", empty)["respondents"],
            })
    if not results:
        raise ValueError("No national major-party coalition support")
    return {
        "status": "private_national_birth_year_support_not_demographic_dropoff",
        "source_audit": audit["source_audit"], "cohorts": results,
        "historical_controls_checked": control is not None,
        "original_group_population_estimates": None, "group_dropoff_estimates": None,
        "design_confidence_intervals": None,
        "limits": [
            "The same validated-turnout/reported-choice/weight/state filters as the historical audit apply.",
            "US50 excludes DC from both the historical denominator and every cohort.",
            "A birth year gives two possible ages during calendar2026; no birthday is imputed.",
            "Certain/possible support retains unknown birth years in the full coalition denominator.",
            "These are hypothetically aged2024participants, not observed2026survivors,residents,or voters.",
            "The18-29and18-44cohorts overlap; do not sum them or infer30-44from rounded current tables.",
            "Birth-year support ranges and effective samples are not design or sampling confidence intervals.",
            "National support does not qualify state/local allocation or any demographic population estimate.",
            "Small cells remain private pending disclosure,precision,and cross-source qualification.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("survey", "guide", "labels", "control", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT in args.output.resolve().parents:
        raise ValueError("Use a new private output outside the repository")
    if (historical.digest(args.survey, "sha256") != historical.CSV_SHA256
            or historical.digest(args.guide, "md5") != historical.GUIDE_MD5
            or historical.digest(args.control, "sha256") != CONTROL_SHA256):
        raise ValueError("Frozen historical source, guide or controls changed")
    historical.verify_labels(json.loads(args.labels.read_text()))
    with args.survey.open(newline="") as source:
        result = review(csv.DictReader(source), json.loads(args.control.read_text()))
    result["source_pins"] = {
        "survey_sha256": historical.CSV_SHA256, "guide_md5": historical.GUIDE_MD5,
        "control_sha256": CONTROL_SHA256,
        "native_label_audit_sha256": historical.digest(args.labels, "sha256"),
        "doi": "10.7910/DVN/X11EP6", "release": "9.0", "license": "CC0 1.0",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"cohorts": len(result["cohorts"]), "historical_controls_checked": True,
                      "population_estimates_released": False, "output": str(args.output)}))

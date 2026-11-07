"""Privately review source-native Missouri demographic House-party intentions."""

import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "slu", Path(__file__).with_name("review-slu-intended-house.py"))
slu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slu)

# Labels and raw marginals are from the pinned native August codebook.
DIMENSIONS = {
    "gender": {
        "description": "Sex",
        "kind": "native_survey_or_profile_category",
        "categories": {"1": ("Male", 402), "2": ("Female", 498)},
    },
    "agegroup": {
        "description": "Age group",
        "kind": "native_survey_or_profile_category",
        "categories": {"1": ("65+", 254), "2": ("45-64", 320),
                       "3": ("30-44", 185), "4": ("18-29", 141)},
    },
    "race": {
        "description": "Race",
        "kind": "native_survey_or_profile_category",
        "categories": {"1": ("White", 731), "2": ("Black", 108),
                       "3": ("Hispanic", 13), "4": ("Asian", 8),
                       "5": ("Native American", 6), "6": ("Two or more races", 27),
                       "7": ("Other", 6), "8": ("Middle Eastern", 1)},
    },
    "educ": {
        "description": "Education",
        "kind": "native_survey_or_profile_category",
        "categories": {"1": ("No HS", 17), "2": ("High school graduate", 216),
                       "3": ("Some college", 220), "4": ("2-year", 105),
                       "5": ("4-year", 210), "6": ("Post-grad", 132)},
    },
    "incgroup": {
        "description": "Income group",
        "kind": "native_derived_income_group",
        "categories": {"-1": ("No Data", 52), "1": ("Under $50k", 344),
                       "2": ("$50k - $100k", 308), "3": ("$100k or more", 196)},
    },
    "USR_Classification": {
        "description": "USR_Classification",
        "kind": "native_geographic_context_not_individual_residence_type",
        "categories": {"1": ("Rural", 183), "2": ("Small Medium Metro", 197),
                       "3": ("Suburban", 344), "4": ("Urban", 176)},
    },
    "employ": {
        "description": "Employment Status",
        "kind": "native_survey_or_profile_category",
        "categories": {"1": ("Full-time", 322), "2": ("Part-time", 89),
                       "3": ("Temporarily laid off", 3), "4": ("Unemployed", 37),
                       "5": ("Retired", 295), "6": ("Permanently disabled", 76),
                       "7": ("Homemaker", 51), "8": ("Student", 12), "9": ("Other", 15)},
    },
    "marstat": {
        "description": "Marital Status",
        "kind": "native_survey_or_profile_category",
        "categories": {"1": ("Married", 451), "2": ("Separated", 11),
                       "3": ("Divorced", 116), "4": ("Widowed", 59),
                       "5": ("Never married", 220),
                       "6": ("Domestic / civil partnership", 43)},
    },
    "child18": {
        "description": "Children under age 18 in household",
        "kind": "native_survey_or_profile_category",
        "categories": {"1": ("Yes", 212), "2": ("No", 688)},
    },
}


def check_support(parts, expected):
    if sum(part["respondents"] for part in parts) != expected["respondents"]:
        raise ValueError("Demographic partition respondent control differs")
    for field in ("sum_weight", "sum_squared_weight"):
        if not math.isclose(math.fsum(part[field] for part in parts), expected[field],
                            rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("Demographic partition weight control differs")


def review(rows):
    rows = list(rows)
    overall = slu.review(rows)
    dimensions = []
    counters = {field: Counter() for field in DIMENSIONS}
    for row in rows:
        for field, definition in DIMENSIONS.items():
            if field not in row:
                raise ValueError(f"Missing native demographic column: {field}")
            if row[field] not in definition["categories"]:
                raise ValueError(f"Unknown native demographic response: {field}")
            counters[field][row[field]] += 1
    for field, definition in DIMENSIONS.items():
        groups = []
        for code, (label, _) in definition["categories"].items():
            selected = [row for row in rows if row[field] == code]
            if not selected:
                continue
            result = slu.review(selected)
            groups.append({
                "native_code": code, "native_label": label,
                "support": result["support"], "comparisons": result["comparisons"],
            })
        check_support([group["support"] for group in groups], overall["support"])
        for index, comparison in enumerate(overall["comparisons"]):
            parts = [group["comparisons"][index] for group in groups]
            check_support([part["support"] for part in parts], comparison["support"])
            for name in ("intended_house_choices", "turnout_intentions"):
                for cell_index, cell in enumerate(comparison[name]):
                    check_support([part[name][cell_index]["support"] for part in parts],
                                  cell["support"])
        dimensions.append({
            "native_variable": field, "native_description": definition["description"],
            "kind": definition["kind"],
            "demographic_measurement_date": None,
            "category_operationalization_independently_verified": False,
            "native_category_labels": {
                code: label for code, (label, _) in definition["categories"].items()},
            "groups": groups, "all_partition_support_controls_reconciled": True,
        })
    return {
        "status": "private_demographic_pre_election_intentions_not_completed_voting",
        "geography": "MO", "public_release_qualified": False,
        "overall_review": overall,
        "native_demographic_counts": {field: dict(count) for field, count in counters.items()},
        "dimensions": dimensions,
        "population_switchers": None, "apparent_absence": None,
        "measured_staying_home": None, "new_or_returning_voter_identity": None,
        "demographic_turnout": None, "total_swing_shares": None,
        "design_confidence_intervals": None, "district_or_county_estimates": None,
        "limits": [
            "All original overall-review limitations apply to every demographic group.",
            "All eight prior responses and every House Other/Not sure response remain in denominators.",
            "Small joint cells and respondent records remain private; no public selection is qualified.",
            "Groups are actual same-respondent joint observations, not multiplied marginal distributions.",
            "Each dimension separately partitions the same sample; dimensions must not be added.",
            "Native gender is described Sex, not an independently established gender-identity measure.",
            "Native age groups are not fixed 2024 or November 2026 birth cohorts.",
            "Native race codes are not independently harmonized to CES or SSRS race/ethnicity definitions.",
            "Income No Data is retained; family-income questions do not establish household income.",
            "USR categories are native geographic context; classification method/vintage remain unverified.",
            "Profile demographic measurement dates are not independently established.",
            "No new weights, population scaling, design CIs or precision/disclosure qualification is supplied.",
        ],
    }


def qualify_native(result):
    expected = {
        field: {code: count for code, (_, count) in definition["categories"].items()}
        for field, definition in DIMENSIONS.items()
    }
    if result["native_demographic_counts"] != expected:
        raise ValueError("Frozen numeric data and native demographic marginals differ")
    slu.qualify_native(result["overall_review"])
    result["native_demographic_marginals_checked"] = True
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (*slu.SOURCE_PINS, "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT in args.output.resolve().parents:
        raise ValueError("Use a new private output outside the repository")
    for name, expected in slu.SOURCE_PINS.items():
        if hashlib.sha256(getattr(args, name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen {name} changed")
    with args.survey.open(newline="", encoding="utf-8-sig") as source:
        result = qualify_native(review(csv.DictReader(source)))
    result["source_pins"] = slu.SOURCE_PINS
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "respondents": result["overall_review"]["support"]["respondents"],
        "dimensions": len(result["dimensions"]),
        "groups": sum(len(item["groups"]) for item in result["dimensions"]),
        "native_demographic_marginals_checked": True,
        "public_release_qualified": False, "output": str(args.output),
    }))

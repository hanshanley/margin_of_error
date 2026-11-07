"""Review private Missouri likely-voter intentions, not completed voting or turnout."""

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PINS = {
    "survey": "ee9ef15692aebaaa35bd97947d26946a3a5e53cdb2ab6aface72ebc0d0d5509e",
    "codebook": "ca771025ba2b2e40448d7cb69374e1d2f5bc0a0c84753fdc7cf04c5248e830aa",
    "topline": "ba90493f673ba7d36b5d608b3d616b9d32dde237bc6b05726a97698bcaaf2f11",
}
PRIOR = {
    "1": "Harris", "2": "Trump", "3": "Kennedy", "4": "Stein",
    "5": "West", "6": "Oliver", "8": "Other", "9": "Presidential nonvote",
}
HOUSE = {"1": "D", "2": "R", "3": "Other", "4": "Not sure"}
LIKELIHOOD = {"1": "Almost certain", "2": "Probably"}
REQUIRED = {"weight", "presvote24post", "POLS025", "QB", "votereg"}
NATIVE_COUNTS = {
    "presvote24post": {"1": 383, "2": 418, "3": 5, "4": 10,
                       "5": 2, "6": 4, "8": 5, "9": 73},
    "POLS025": {"1": 428, "2": 388, "3": 20, "4": 64},
    "QB": {"1": 802, "2": 98},
    "votereg": {"1": 900},
}


def support(weights):
    total = math.fsum(weights)
    squared = math.fsum(weight * weight for weight in weights)
    if not math.isfinite(total) or not math.isfinite(squared):
        raise ValueError("Invalid accumulated survey weights")
    return {
        "respondents": len(weights), "sum_weight": total, "sum_squared_weight": squared,
        "kish_effective_base_not_design_n": total * total / squared if squared else None,
    }


def review(rows):
    weights = []
    cells = {(prior, house): [] for prior in PRIOR for house in HOUSE}
    likelihood = {(prior, code): [] for prior in PRIOR for code in LIKELIHOOD}
    counters = {field: Counter() for field in NATIVE_COUNTS}
    for row in rows:
        if not REQUIRED <= row.keys():
            raise ValueError("Missing selected survey columns")
        prior, house, vote = (row["presvote24post"], row["POLS025"], row["QB"])
        if (prior not in PRIOR or house not in HOUSE or vote not in LIKELIHOOD
                or row["votereg"] != "1"):
            raise ValueError("Unrecognized response or changed likely-registered-voter universe")
        try:
            weight = float(row["weight"])
        except (ValueError, TypeError) as error:
            raise ValueError("Invalid survey weight") from error
        if weight <= 0 or not math.isfinite(weight * weight):
            raise ValueError("Invalid survey weight")
        weights.append(weight)
        cells[prior, house].append(weight)
        likelihood[prior, vote].append(weight)
        for field in counters:
            counters[field][row[field]] += 1
    if not weights:
        raise ValueError("Empty survey")
    total = support(weights)
    comparisons = []
    for prior, label in PRIOR.items():
        base = support([weight for house in HOUSE for weight in cells[prior, house]])
        denominator = base["sum_weight"]
        comparisons.append({
            "native_prior_code": prior, "reported_2024_choice": label, "support": base,
            "weighted_sample_share": denominator / total["sum_weight"],
            "intended_house_choices": [{
                "native_code": house, "party_or_response": response,
                "support": support(cells[prior, house]),
                "weighted_within_prior_share": (
                    math.fsum(cells[prior, house]) / denominator if denominator else None),
            } for house, response in HOUSE.items()],
            "turnout_intentions": [{
                "native_code": code, "response": response,
                "support": support(likelihood[prior, code]),
                "weighted_within_prior_share": (
                    math.fsum(likelihood[prior, code]) / denominator if denominator else None),
            } for code, response in LIKELIHOOD.items()],
        })
    return {
        "status": "private_pre_election_intentions_not_completed_voting",
        "geography": "MO", "contest_scope": "generic_US_House_party_in_respondents_own_district",
        "published_topline_field_dates": {"start": "2026-08-13", "end": "2026-08-24"},
        "native_variable_counts": {field: dict(count) for field, count in counters.items()},
        "support": total,
        "intended_house_topline": [{
            "party_or_response": response,
            "weighted_sample_share": math.fsum(
                weight for prior in PRIOR for weight in cells[prior, house]
            ) / total["sum_weight"],
        } for house, response in HOUSE.items()],
        "comparisons": comparisons,
        "population_switchers": None, "apparent_absence": None,
        "measured_staying_home": None, "new_or_returning_voter_identity": None,
        "demographic_turnout": None, "total_swing_shares": None,
        "design_confidence_intervals": None, "district_or_county_estimates": None,
        "limits": [
            "August intentions are not November completed participation or actual House votes.",
            "The sample contains only registered likely voters; unlikely voters are not observed.",
            "Generic party choice is not a named-candidate or individual-district result.",
            "Keep every other-party and unsure response in each prior-choice denominator.",
            "Presidential nonvote is not all-race nonparticipation, first-ever voting or eligibility entry.",
            "The published methods calibrate 1074 registered voters on recalled2024choice before selecting900likely voters.",
            "Historical RV calibration is not proof that the likely-voter sample was forced to2024vote shares.",
            "No current-voter mass scaling, recall correction or new historical reweighting is applied.",
            "Kish bases describe weight concentration, not subgroup design degrees of freedom or CIs.",
            "The source's overall margin of error is not a joint-cell or conditional-choice interval.",
            "Small cells and all respondent records remain private; selected publication needs separate review.",
            "This is independent SLU/YouGov evidence, not an additional SSRS state table.",
        ],
    }


def qualify_native(result):
    if result["native_variable_counts"] != NATIVE_COUNTS:
        raise ValueError("Frozen numeric data and native codebook marginals differ")
    expected = {"D": 44, "R": 48, "Other": 2, "Not sure": 6}
    for row in result["intended_house_topline"]:
        if math.floor(100 * row["weighted_sample_share"] + .5) != expected[row["party_or_response"]]:
            raise ValueError("Weighted generic House topline differs from the native questionnaire")
    result["native_marginals_and_rounded_topline_checked"] = True
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (*SOURCE_PINS, "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT in args.output.resolve().parents:
        raise ValueError("Use a new private output outside the repository")
    for name, expected in SOURCE_PINS.items():
        if hashlib.sha256(getattr(args, name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen {name} changed")
    with args.survey.open(newline="", encoding="utf-8-sig") as source:
        result = qualify_native(review(csv.DictReader(source)))
    result["source_pins"] = SOURCE_PINS
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "respondents": result["support"]["respondents"],
        "joint_prior_rows": len(result["comparisons"]),
        "native_marginals_and_rounded_topline_checked": True,
        "population_counts_released": False, "output": str(args.output),
    }))

"""Review private nonpartisan CES participation records without coding unmatched as nonvote."""

import argparse
from collections import Counter
import csv
import importlib.util
import json
import math
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ces_demographics", Path(__file__).with_name("review-ces-demographic-baselines.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
MISSING = {"", "NA"}
FRAMES = ("adult_survey_commonweight", "matched_active_registered_vvweight")
TOTAL_FIELDS = (
    "respondents", "sum_weight", "sum_squared_weight",
    "validation_state_mismatch_respondents", "validation_state_mismatch_weight",
    "validation_state_missing_respondents", "validation_state_missing_weight",
)
DIMENSIONS = (
    "gender_2024", "source_race_2024", "race_ethnicity_2024", "education_2024",
    "race_education_2024", "calendar_year_age_2024",
)


def positive_weight(value):
    weight = float(value)
    if not math.isfinite(weight) or weight <= 0:
        raise ValueError("Invalid documented survey weight")
    return weight


def classify(row):
    matched = row["TS_voterstatus"] == "1"
    if not matched and row["TS_voterstatus"] not in MISSING:
        raise ValueError("Unknown validated registration code")
    code = row["TS_g2024"]
    if code not in MISSING | {"1", "2", "3", "4", "5", "6", "7"}:
        raise ValueError("Unknown general participation code")
    if not matched:
        if code not in MISSING or row["vvweight"] not in MISSING or row["TS_state"] not in MISSING:
            raise ValueError("Unmatched respondent has matched-only fields")
        return "unmatched"
    if row["vvweight"] in MISSING or row["TS_state"] not in set(base.STATE_CODES.values()) | MISSING:
        raise ValueError("Missing documented matched registration weight or state")
    return ("matched_missing_history" if code in MISSING else
            "explicit_recorded_nonvote" if code == "7" else "recorded_vote")


def groups(row):
    values = base.demographics(row)
    return {dimension: values["age_2024_by_birth_year" if dimension == "calendar_year_age_2024"
                              else dimension] for dimension in DIMENSIONS}


def add(bucket, category, weight, mismatch, missing_state):
    cell = bucket.setdefault(category, Counter())
    cell["respondents"] += 1
    cell["sum_weight"] += weight
    cell["sum_squared_weight"] += weight * weight
    cell["validation_state_mismatch_respondents"] += int(mismatch)
    cell["validation_state_mismatch_weight"] += weight * int(mismatch)
    cell["validation_state_missing_respondents"] += int(missing_state)
    cell["validation_state_missing_weight"] += weight * int(missing_state)


def summarize(bucket):
    totals = {key: sum(cell.get(key, 0) for cell in bucket.values()) for key in TOTAL_FIELDS}
    weight = totals["sum_weight"]
    positive = bucket.get("recorded_vote", {}).get("sum_weight", 0)
    unknown = sum(bucket.get(category, {}).get("sum_weight", 0)
                  for category in ("unmatched", "matched_missing_history"))
    return {
        **totals, "record_categories": bucket,
        "effective_sample_size_not_design_precision": weight ** 2 / totals["sum_squared_weight"],
        "recorded_vote_weight_fraction": positive / weight,
        "unknown_history_weight_fraction": unknown / weight,
        "record_compatible_participation_fraction": [positive / weight, (positive + unknown) / weight],
        "eligible_population_turnout_rate": None,
    }


def reconcile(overall, partitions):
    for rows in partitions.values():
        for key in TOTAL_FIELDS:
            if not math.isclose(sum(row[key] for row in rows), overall[key], rel_tol=1e-10, abs_tol=1e-8):
                raise ValueError("Demographic partition does not reconcile")
        for category, expected in overall["record_categories"].items():
            for key, value in expected.items():
                actual = sum(row["record_categories"].get(category, {}).get(key, 0) for row in rows)
                if not math.isclose(actual, value, rel_tol=1e-10, abs_tol=1e-8):
                    raise ValueError("Participation-category partition does not reconcile")


def review(rows):
    audit, totals, cells = Counter(), {}, {}
    for row in rows:
        audit["native_respondents"] += 1
        state = base.STATE_CODES.get(row["inputstate"].zfill(2))
        if state is None:
            raise ValueError("Unrecognized survey state")
        category = classify(row)
        audit[category] += 1
        missing_state = category != "unmatched" and row["TS_state"] in MISSING
        mismatch = category != "unmatched" and not missing_state and row["TS_state"] != state
        audit["validation_state_mismatch_respondents"] += int(mismatch)
        audit["validation_state_missing_respondents"] += int(missing_state)
        weights = {FRAMES[0]: positive_weight(row["commonweight"])}
        if category != "unmatched":
            weights[FRAMES[1]] = positive_weight(row["vvweight"])
        demographics = groups(row)
        for scope in (state, "US51") if state == "DC" else (state, "US50", "US51"):
            for frame, weight in weights.items():
                add(totals.setdefault((scope, frame), {}), category, weight, mismatch, missing_state)
                for dimension, group in demographics.items():
                    add(cells.setdefault((scope, frame, dimension, group), {}), category, weight, mismatch, missing_state)
    results = []
    for scope in sorted(set(base.STATE_CODES.values()) | {"US50", "US51"}):
        frames = {}
        for frame in FRAMES:
            if (scope, frame) not in totals:
                frames[frame] = {"available": False, "overall": None, "partitions": {}}
                continue
            overall = summarize(totals[(scope, frame)])
            partitions = {}
            for (cell_scope, cell_frame, dimension, group), bucket in sorted(cells.items()):
                if (cell_scope, cell_frame) == (scope, frame):
                    partitions.setdefault(dimension, []).append({"group": group, **summarize(bucket)})
            reconcile(overall, partitions)
            frames[frame] = {"available": True, "overall": overall, "partitions": partitions}
        results.append({"survey_scope": scope, "frames": frames})
    return {
        "status": "private_participation_record_audit_not_public_qualified_turnout",
        "election": "2024 general", "source_audit": dict(audit), "scopes": results,
        "measured_2026_participation": None, "prior_candidate_choice": None,
        "limits": [
            "No candidate-choice or party field is used; participation methods 1-6 are recorded votes and 7 is explicit recorded nonvote.",
            "Unmatched registration and matched missing history remain separate unknowns, never assumed nonvoters.",
            "commonweight targets adults, not a voting-eligible or citizen-only population. Its record-positive fraction is not an eligible-population turnout rate.",
            "The compatible range allows unknown histories to be either vote or nonvote conditional on recorded classifications. It is not a sampling/design confidence interval or a bound covering validation error.",
            "vvweight targets matched active registered adults, not all adults or an election-day registered electorate. Registered and adult frames have different denominators and are never pooled.",
            "Matching occurred in June-July 2025; registration status is at matching, not necessarily election day. Survey and validation states can differ; missing validation state and actual disagreement are separate diagnostics, and neither is silently deleted.",
            "Utah matching is specifically limited by private/withheld registrations; low matching is not evidence of low turnout.",
            "Demographics are source-defined 2024 attributes, not fixed 2026 cohorts. Calendar-year age uses birth year without an election-day birthday and is not exact election-day age.",
            "Raw race and combined race/ethnicity are separate operationalizations. Unknown groups remain; overlapping dimensions and national/state scopes are not additive.",
            "US50 excludes DC; US51 includes DC. Survey-state groups do not establish where a ballot was cast.",
            "Weights use demographic and election calibration; agreement with targets is not independent validation. Kish effective bases are diagnostics, not design precision or public-release thresholds.",
            "No 2026 participation, individual switching, staying-home, first-time voting, migration or eligible-population demographic turnout is estimated.",
            "Fine aggregates stay private pending source-semantic, precision and disclosure review; do not export this audit wholesale.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("survey", "guide", "labels", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT in args.output.resolve().parents or args.output.resolve() == ROOT:
        raise ValueError("Use a new private output outside the repository")
    if base.digest(args.survey, "sha256") != base.CSV_SHA256 or base.digest(args.guide, "md5") != base.GUIDE_MD5:
        raise ValueError("Frozen CES source or guide changed")
    base.verify_labels(json.loads(args.labels.read_bytes()))
    with args.survey.open(newline="") as source:
        result = review(csv.DictReader(source))
    if result["source_audit"]["native_respondents"] != 60000:
        raise ValueError("Frozen native respondent control differs")
    result["source_pins"] = {
        "survey_sha256": base.CSV_SHA256, "guide_md5": base.GUIDE_MD5,
        "native_label_audit_sha256": base.digest(args.labels, "sha256"),
        "reviewer_sha256": base.digest(Path(__file__), "sha256"),
        "demographic_helper_sha256": base.digest(Path(base.__file__), "sha256"),
        "license": "CC0 1.0", "doi": "10.7910/DVN/X11EP6", "release": "9.0",
    }
    descriptor = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(json.dumps({"source_audit": result["source_audit"], "scopes": len(result["scopes"]),
                      "output_sha256": base.digest(args.output, "sha256")}))

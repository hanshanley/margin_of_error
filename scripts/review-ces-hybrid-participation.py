"""Privately review the CES documented record/self-report turnout specification."""

import argparse
from collections import Counter
import csv
import importlib.util
import json
import math
import os
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "participation_records", Path(__file__).with_name("review-ces-participation-records.py"))
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)
MISSING = records.MISSING
NONVOTE = (
    "explicit_recorded_nonvote", "selfreported_nonvote", "selfreported_not_registered",
    "unmatched_not_registered_but_reports_vote",
)
UNKNOWN = ("matched_missing_history", "unmatched_reported_vote", "unmatched_missing_response")
CONFLICT = "unmatched_not_registered_but_reports_vote"
EXTRA_FIELDS = (
    "record_selfreport_disagreement_respondents", "record_selfreport_disagreement_weight",
)
TOTAL_FIELDS = records.TOTAL_FIELDS + EXTRA_FIELDS
NATIVE_RESPONSE_CONTROLS = {
    "votereg_post": {"1": 46781, "2": 2425, "3": 226, "NA": 10568},
    "CC24_401": {"1": 1654, "2": 579, "3": 482, "4": 505, "5": 43795, "NA": 12985},
}


def classify(row, category):
    registration, vote = row["votereg_post"], row["CC24_401"]
    if registration not in MISSING | {"1", "2", "3"} or vote not in MISSING | set("12345"):
        raise ValueError("Unrecognized post-election response code")
    if category != "unmatched":
        return category
    if registration == "2":
        return CONFLICT if vote == "5" else "selfreported_not_registered"
    if vote in set("1234"):
        return "selfreported_nonvote"
    return "unmatched_reported_vote" if vote == "5" else "unmatched_missing_response"


def add(bucket, category, weight, mismatch, missing_state, disagreement):
    records.add(bucket, category, weight, mismatch, missing_state)
    cell = bucket[category]
    cell["record_selfreport_disagreement_respondents"] += int(disagreement)
    cell["record_selfreport_disagreement_weight"] += weight * int(disagreement)


def summarize(bucket):
    totals = {key: sum(cell.get(key, 0) for cell in bucket.values()) for key in TOTAL_FIELDS}
    weight = totals["sum_weight"]
    positive = bucket.get("recorded_vote", {}).get("sum_weight", 0)
    nonvote = sum(bucket.get(category, {}).get("sum_weight", 0) for category in NONVOTE)
    unknown = sum(bucket.get(category, {}).get("sum_weight", 0) for category in UNKNOWN)
    conflict = bucket.get(CONFLICT, {}).get("sum_weight", 0)
    record_unknown = unknown + nonvote - bucket.get("explicit_recorded_nonvote", {}).get("sum_weight", 0)
    if not math.isclose(positive + nonvote + unknown, weight, rel_tol=1e-10, abs_tol=1e-8):
        raise ValueError("Hybrid classification does not reconcile")
    return {
        **totals, "record_and_selfreport_categories": bucket,
        "effective_sample_size_not_design_precision": weight ** 2 / totals["sum_squared_weight"],
        "record_positive_weight_fraction": positive / weight,
        "guide_nonvote_weight_fraction": nonvote / weight,
        "guide_unknown_weight_fraction": unknown / weight,
        "guide_classifiable_participation_fraction": positive / (positive + nonvote) if positive + nonvote else None,
        "record_only_compatible_fraction_same_post_frame": [positive / weight, (positive + record_unknown) / weight],
        "guide_hybrid_compatible_fraction": [positive / weight, (positive + unknown) / weight],
        "conflict_as_unknown_compatible_fraction": [positive / weight, (positive + unknown + conflict) / weight],
        "conflict_as_unknown_classifiable_participation_fraction": (
            positive / (positive + nonvote - conflict) if positive + nonvote - conflict else None),
        "adult_population_turnout_rate": None,
        "eligible_population_turnout_rate": None,
    }


def reconcile(overall, partitions):
    for rows in partitions.values():
        for key in TOTAL_FIELDS:
            if not math.isclose(sum(row[key] for row in rows), overall[key], rel_tol=1e-10, abs_tol=1e-8):
                raise ValueError("Hybrid demographic partition does not reconcile")
        for category, expected in overall["record_and_selfreport_categories"].items():
            for key, value in expected.items():
                actual = sum(row["record_and_selfreport_categories"].get(category, {}).get(key, 0) for row in rows)
                if not math.isclose(actual, value, rel_tol=1e-10, abs_tol=1e-8):
                    raise ValueError("Hybrid demographic category does not reconcile")


def review(rows):
    audit, controls, totals, cells = Counter(), {key: Counter() for key in NATIVE_RESPONSE_CONTROLS}, {}, {}
    for row in rows:
        audit["native_respondents"] += 1
        state = records.base.STATE_CODES.get(row["inputstate"].zfill(2))
        if state is None:
            raise ValueError("Unrecognized survey state")
        recorded = records.classify(row)
        category = classify(row, recorded)
        for key in controls:
            controls[key][row[key]] += 1
        audit["native_" + recorded] += 1
        if row["commonpostweight"] in MISSING:
            if row["votereg_post"] not in MISSING or row["CC24_401"] not in MISSING:
                raise ValueError("Post-election response without a documented post-wave weight")
            audit["no_postwave_weight"] += 1
            continue
        weight = records.positive_weight(row["commonpostweight"])
        audit["postwave_respondents"] += 1
        audit[category] += 1
        missing_state = recorded != "unmatched" and row["TS_state"] in MISSING
        mismatch = recorded != "unmatched" and not missing_state and row["TS_state"] != state
        disagreement = (
            recorded == "recorded_vote" and (row["votereg_post"] == "2" or row["CC24_401"] in set("1234"))
            or recorded == "explicit_recorded_nonvote" and row["CC24_401"] == "5")
        demographic_groups = records.groups(row)
        for scope in (state, "US51") if state == "DC" else (state, "US50", "US51"):
            add(totals.setdefault(scope, {}), category, weight, mismatch, missing_state, disagreement)
            for dimension, group in demographic_groups.items():
                add(cells.setdefault((scope, dimension, group), {}), category, weight,
                    mismatch, missing_state, disagreement)
    scopes = []
    for scope in sorted(set(records.base.STATE_CODES.values()) | {"US50", "US51"}):
        if scope not in totals:
            scopes.append({"survey_scope": scope, "available": False, "overall": None, "partitions": {}})
            continue
        overall, partitions = summarize(totals[scope]), {}
        for (cell_scope, dimension, group), bucket in sorted(cells.items()):
            if cell_scope == scope:
                partitions.setdefault(dimension, []).append({"group": group, **summarize(bucket)})
        reconcile(overall, partitions)
        scopes.append({"survey_scope": scope, "available": True, "overall": overall, "partitions": partitions})
    return {
        "status": "private_documented_hybrid_classification_not_public_qualified_turnout",
        "election": "2024 general", "frame": "adult_postwave_commonpostweight",
        "source_audit": dict(audit), "native_response_controls": controls, "scopes": scopes,
        "measured_2026_participation": None, "prior_candidate_choice": None,
        "limits": [
            "Uses the guide's third specification with commonpostweight for both-wave adult respondents, not the pre-wave or matched-registered weights.",
            "Numeric codes are bound by unique native response counts in the frozen guide and full CSV, not by guessing PDF display order.",
            "Recorded votes and explicit recorded nonvotes have precedence over self-reports; disagreement remains a separate diagnostic, not silently recoded evidence.",
            "Unmatched self-reported nonregistration or nonvoting is assumed nonvote in the guide specification. Unmatched reported voters, missing responses and matched missing histories remain unknown.",
            "The guide's nonregistration rule includes unmatched people reporting nonregistration AND voting. This conflicting category remains explicit; the separate conflict-as-unknown variant moves it to unknown.",
            "The classifiable fraction excludes unresolved records from its denominator. It is not an unconditional population turnout estimate.",
            "Compatible fractions allow unresolved records to vote or not, conditional on known classifications and truthful reported nonparticipation. They are not design confidence intervals or validation-error bounds.",
            "Record-only comparison uses the SAME post-wave frame and weights, not the previously reviewed all-60000 commonweight frame.",
            "Adults are not an eligible/citizen-only denominator. Post-wave nonresponse and weighting/calibration assumptions remain; Kish bases are not design precision.",
            "Validation matched active registrations in June-July 2025, not a proven election-day registration frame; Utah private/withheld registration limits matching.",
            "Survey state, missing validation state and actual disagreement are distinct; survey state is not established ballot geography.",
            "Source-defined 2024 demographics are not fixed 2026 cohorts. Calendar-year age is not exact election-day age; raw race and combined ethnicity remain separate.",
            "Unknown demographics remain; dimensions and US50/US51/state scopes overlap and are not additive. US50 excludes DC.",
            "No candidate/party field, 2026 result, historical-choice selection, population switching, measured staying-home or first-time-voter identity is used.",
            "Fine aggregates stay private pending source-semantic, precision and disclosure review; no public selection is automatically qualified.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("survey", "guide", "labels", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or records.ROOT in args.output.resolve().parents or args.output.resolve() == records.ROOT:
        raise ValueError("Use a new private output outside the repository")
    base = records.base
    if base.digest(args.survey, "sha256") != base.CSV_SHA256 or base.digest(args.guide, "md5") != base.GUIDE_MD5:
        raise ValueError("Frozen CES source or guide changed")
    base.verify_labels(json.loads(args.labels.read_bytes()))
    with args.survey.open(newline="") as source:
        result = review(csv.DictReader(source))
    if (result["source_audit"]["native_respondents"] != 60000
            or result["source_audit"]["postwave_respondents"] != 49432
            or result["native_response_controls"] != NATIVE_RESPONSE_CONTROLS):
        raise ValueError("Frozen respondent or guide response controls changed")
    result["source_pins"] = {
        "survey_sha256": base.CSV_SHA256, "guide_md5": base.GUIDE_MD5,
        "native_label_audit_sha256": base.digest(args.labels, "sha256"),
        "reviewer_sha256": base.digest(Path(__file__), "sha256"),
        "record_reviewer_sha256": base.digest(Path(records.__file__), "sha256"),
        "demographic_helper_sha256": base.digest(Path(base.__file__), "sha256"),
        "license": "CC0 1.0", "doi": "10.7910/DVN/X11EP6", "release": "9.0",
    }
    descriptor = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(json.dumps({"source_audit": result["source_audit"], "scopes": len(result["scopes"]),
                      "output_sha256": base.digest(args.output, "sha256")}))

"""Privately summarize completed-election history records in a retained registration frame."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path


PERIODS = ((2020, 2022), (2022, 2024))
PRIOR_2024 = {
    "Positive 2024 NC history": True,
    "No 2024 NC history found; national participation unresolved": False,
}


def recorded(cell, year):
    value = (PRIOR_2024.get(cell["prior_2024_history"])
             if year == 2024 else cell[f"prior_{year}_history"])
    if type(value) is not bool:
        raise ValueError("Complete historical search requires known record-presence indicators")
    return value


def summarize(cells):
    matrices = {period: Counter(dict.fromkeys(
        ("recorded_both", "recorded_prior_only", "recorded_current_only", "neither_recorded"), 0))
        for period in PERIODS}
    exclusions = Counter(dict.fromkeys(
        ("not_currently_active_or_inactive", "incomplete_history_search",
         "current_registration_not_established_by_2020"), 0))
    total = retained = 0
    for cell in cells:
        count = cell["records"]
        if type(count) is not int or count <= 0:
            raise ValueError("Invalid aggregate record count")
        total += count
        if cell["registration_status_2026"] not in ("ACTIVE", "INACTIVE"):
            exclusions["not_currently_active_or_inactive"] += count
            continue
        if type(cell["historical_search_complete"]) is not bool:
            raise ValueError("Unknown search-completeness flag")
        if not cell["historical_search_complete"]:
            exclusions["incomplete_history_search"] += count
            continue
        by_2020 = cell["registration_by_2020"]
        if by_2020 is not None and type(by_2020) is not bool:
            raise ValueError("Unknown registration-date flag")
        if by_2020 is not True:
            exclusions["current_registration_not_established_by_2020"] += count
            continue
        retained += count
        for prior, current in PERIODS:
            before, after = recorded(cell, prior), recorded(cell, current)
            category = ("recorded_both" if before and after else
                        "recorded_prior_only" if before else
                        "recorded_current_only" if after else "neither_recorded")
            matrices[(prior, current)][category] += count
    if total != retained + sum(exclusions.values()):
        raise ValueError("Frame exclusions do not reconcile")
    comparisons = []
    for (prior, current), counts in matrices.items():
        if sum(counts.values()) != retained:
            raise ValueError("History matrix does not reconcile to the retained frame")
        prior_positive = counts["recorded_both"] + counts["recorded_prior_only"]
        current_positive = counts["recorded_both"] + counts["recorded_current_only"]
        comparisons.append({
            "prior_year": prior, "current_year": current,
            "record_presence_matrix": dict(counts),
            "prior_positive_history_records": prior_positive,
            "current_positive_history_records": current_positive,
            "recorded_current_among_recorded_prior_pct": (
                100 * counts["recorded_both"] / prior_positive if prior_positive else None),
            "recorded_prior_among_recorded_current_pct": (
                100 * counts["recorded_both"] / current_positive if current_positive else None),
            "first_ever_voters": None,
            "confirmed_previously_eligible_nonparticipants": None,
            "population_turnout_rate": None,
            "candidate_choice_retention": None,
        })
    return {
        "input_aggregate_population": total,
        "retained_registration_frame": retained,
        "mutually_exclusive_frame_exclusions": dict(exclusions),
        "comparisons": comparisons,
    }


def qualified_summary(directory, controls_path):
    audit_raw = (directory / "audit.json").read_bytes()
    cells_raw = (directory / "joint-cells.json").read_bytes()
    control_raw = controls_path.read_bytes()
    audit, controls = json.loads(audit_raw), json.loads(control_raw)
    digest = hashlib.sha256(cells_raw).hexdigest()
    if (audit.get("state_code") != "NC" or not audit.get("county")
            or controls.get("county") != audit["county"]
            or controls.get("all_linkage_control_signatures_match") is not True
            or audit.get("joint_cells_sha256") != digest
            or controls.get("joint_cells_sha256") != digest):
        raise ValueError("Missing or changed independent linkage controls")
    for year in (2020, 2022, 2024):
        if audit["history"].get(f"general_{year}_records", 0) <= 0:
            raise ValueError("Missing completed-election history source coverage")
    cells = json.loads(cells_raw)
    if len(cells) != audit["aggregate_cells"]:
        raise ValueError("Aggregate cell count differs from source audit")
    summary = summarize(cells)
    if summary["input_aggregate_population"] != controls["controls"]["private_population"]:
        raise ValueError("Aggregate population differs from independent source controls")
    return {
        "state_code": "NC", "county": audit["county"],
        "provenance_sha256": {
            "audit": hashlib.sha256(audit_raw).hexdigest(),
            "joint_cells": digest,
            "independent_controls": hashlib.sha256(control_raw).hexdigest(),
        },
        "native_sources": audit["sources"],
        **summary,
    }


def review(directories, controls, output):
    if not directories or len(directories) != len(controls):
        raise ValueError("Pair each private review with its independent controls")
    if output.exists():
        raise ValueError("Refusing to overwrite an existing review")
    rows = [qualified_summary(directory, proof) for directory, proof in zip(directories, controls)]
    if len({row["county"] for row in rows}) != len(rows):
        raise ValueError("Duplicate county selection")
    result = {
        "status": "private_retained_registration_history_diagnostic_not_population_validation",
        "frame": "2026 ACTIVE/INACTIVE current records dated by November 3, 2020, with complete NC history search",
        "counties": rows,
        "limitations": [
            "This is a retained 2026 registration frame, not either historical electorate or all eligible residents.",
            "Current-record registration dates and statuses are not reconstructed election-day registration or eligibility.",
            "No history record found is not proven national nonparticipation or first-ever voting.",
            "The matrices concern recorded all-ballot participation, not presidential contest participation or candidate choice.",
            "Deaths, moves, removals, registration-date changes and unresolved record linkage can select the retained frame.",
            "No 2026 participation or nonparticipation is classified from incomplete current histories.",
            "Record-presence ratios are descriptive, not population turnout rates, design confidence intervals or validation of a correction.",
            "Only broad county matrices are emitted privately; no individuals, fine cells or individual scores are exported.",
        ],
        "population_method_validated": False,
        "public_release_qualified": False,
    }
    output.mkdir(parents=True, mode=0o700)
    raw = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
    descriptor = os.open(output / "history-transitions.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        target.write(raw)
    print(json.dumps({"status": result["status"], "counties": len(rows),
                      "results_sha256": hashlib.sha256(raw).hexdigest()}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-directory", action="append", type=Path, required=True)
    parser.add_argument("--independent-controls", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review(args.review_directory, args.independent_controls, args.output)

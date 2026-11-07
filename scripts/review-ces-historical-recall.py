#!/usr/bin/env python3
"""Private matched-panel recall diagnostics, not population transition certification."""

import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path


ZERO = Decimal(0)
HUNDRED = Decimal(100)
WEIGHTS = ("commonpostweight_22", "vvweight_post_22")
PRIOR = ("D", "R", "O", "NO_PRESIDENT", "UNKNOWN")
HOUSE = ("D", "R", "O", "CONTEST_NONVOTE", "REPORTED_NONVOTE", "UNKNOWN")
STATES = frozenset(
    str(n) for n in (1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 17,
                    18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
                    31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 44,
                    45, 46, 47, 48, 49, 50, 51, 53, 54, 55, 56)
)
MISSING = frozenset(("", "NA"))
REQUIRED = (
    "CC20_410", "presvote20post", "CL_2020gvm", "TS_g2022", "CC22_401",
    "CC22_412", "inputstate_20", "inputstate_22",
) + WEIGHTS + tuple("HouseCand%dParty_post_22" % i for i in range(1, 9))
EXPECTED_LABELS = {
    "CC20_410": {"1": "Joe Biden (Democrat)", "2": "Donald J. Trump (Republican)"},
    "presvote20post": {"1": "Joe Biden", "2": "Donald Trump",
                       "6": "Did not vote for President"},
    "TS_g2022": {"7": "did not vote", "6": "voted by unknown method"},
    "CL_2020gvm": {"5": "unknown"},
    "CC22_401": {"5": "I definitely voted in the November 2022 General Election."},
    "CC22_412": {"1": "$HouseCand1Name ($HouseCand1Party)",
                 "11": "I did not vote in this race", "12": "I did not vote"},
}


def code(value, allowed, field):
    if value in MISSING:
        return None
    if value not in allowed:
        raise ValueError("Unexpected native code in " + field)
    return value


def weight(value):
    if value in MISSING:
        return None
    result = Decimal(value)
    if not result.is_finite() or result < ZERO:
        raise ValueError("Invalid post-election weight")
    return result


def prior_choice(value, recalled=False):
    allowed = {"1", "2", "3", "4", "5", "6", "8", "9"} if recalled else {
        "1", "2", "4", "5", "6", "7", "98", "99"}
    value = code(value, allowed, "presvote20post" if recalled else "CC20_410")
    if value in ("1", "2"):
        return "D" if value == "1" else "R"
    if (recalled and value in ("3", "4", "5")) or (not recalled and value == "4"):
        return "O"
    if (recalled and value == "6") or (not recalled and value in ("5", "6")):
        return "NO_PRESIDENT"
    return "UNKNOWN"


def house_choice(row):
    value = code(row["CC22_412"],
                 {str(i) for i in range(1, 9)} | {"10", "11", "12", "13", "98", "99"},
                 "CC22_412")
    if value in {str(i) for i in range(1, 9)}:
        party = row["HouseCand%sParty_post_22" % value]
        if party in MISSING or party == "-1":
            return "UNKNOWN"
        return {"Democratic": "D", "Republican": "R"}.get(party, "O")
    return {"10": "O", "11": "CONTEST_NONVOTE", "12": "REPORTED_NONVOTE"}.get(
        value, "UNKNOWN")


def percent(numerator, denominator):
    return HUNDRED * numerator / denominator if denominator else None


def empty_cell():
    return {"n": 0, "weight": ZERO}


def add(cell, amount):
    cell["n"] += 1
    cell["weight"] += amount


def serialize(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


def specification(rows, weight_name, include_dc, current_rule):
    if weight_name not in WEIGHTS or current_rule not in (
            "record_positive", "reported_definitely_voted"):
        raise ValueError("Unsupported weight or current-voter selection")
    dispositions = {
        name: empty_cell() for name in (
            "missing_or_zero_postweight", "unresolved_survey_state", "dc_excluded",
            "no_positive_2020_validation", "unmatched_2022_history", "retained")
    }
    all_prior = {
        p: {s: empty_cell() for s in ("positive", "explicit_nonvote", "unknown")}
        for p in PRIOR
    }
    baseline = {p: empty_cell() for p in PRIOR}
    returned = {p: empty_cell() for p in PRIOR}
    nonvote = {p: empty_cell() for p in PRIOR}
    recalled_return = {p: empty_cell() for p in PRIOR}
    recalled_house = {p: {h: empty_cell() for h in HOUSE} for p in PRIOR}
    actual_house = {p: {h: empty_cell() for h in HOUSE} for p in PRIOR}
    recall_matrix = {p: {r: empty_cell() for r in PRIOR} for p in PRIOR}
    current_total = ZERO
    query_total = ZERO
    self_report_conflicts = {"record_positive_reported_not_voted": empty_cell(),
                            "record_nonvote_reported_definitely_voted": empty_cell()}
    for row in rows:
        w = weight(row[weight_name])
        if w is None or w == ZERO:
            add(dispositions["missing_or_zero_postweight"], ZERO)
            continue
        states = (row["inputstate_20"], row["inputstate_22"])
        if any(state not in STATES for state in states):
            add(dispositions["unresolved_survey_state"], w)
            continue
        if not include_dc and "11" in states:
            add(dispositions["dc_excluded"], w)
            continue
        prior_validation = code(row["CL_2020gvm"], {str(i) for i in range(1, 6)},
                                "CL_2020gvm")
        if prior_validation is None:
            add(dispositions["no_positive_2020_validation"], w)
            continue
        old = prior_choice(row["CC20_410"])
        recall = prior_choice(row["presvote20post"], recalled=True)
        history = code(row["TS_g2022"], {str(i) for i in range(1, 8)}, "TS_g2022")
        status = "unknown" if history is None else (
            "explicit_nonvote" if history == "7" else "positive")
        add(all_prior[old][status], w)
        if history is None:
            add(dispositions["unmatched_2022_history"], w)
            continue
        add(dispositions["retained"], w)
        add(baseline[old], w)
        add(recall_matrix[old][recall], w)
        report = code(row["CC22_401"], {"1", "2", "3", "4", "5", "8", "9"}, "CC22_401")
        positive = history != "7"
        if positive:
            current_total += w
            add(returned[old], w)
            add(actual_house[old][house_choice(row)], w)
            if report in ("1", "2", "3", "4"):
                add(self_report_conflicts["record_positive_reported_not_voted"], w)
        else:
            add(nonvote[old], w)
            if report == "5":
                add(self_report_conflicts["record_nonvote_reported_definitely_voted"], w)
        queried = positive if current_rule == "record_positive" else report == "5"
        if queried:
            query_total += w
            add(recalled_return[recall], w)
            add(recalled_house[recall][house_choice(row)], w)
    assert sum(c["n"] for c in dispositions.values()) == len(rows)
    assert sum(c["weight"] for c in returned.values()) == current_total
    assert sum(c["weight"] for c in recalled_return.values()) == query_total
    comparisons = []
    for p, opposite in (("D", "R"), ("R", "D")):
        t = baseline[p]["weight"]
        actual_return = returned[p]["weight"]
        q = recalled_return[p]["weight"] / query_total if query_total else None
        conditional = (recalled_house[p][opposite]["weight"] / recalled_return[p]["weight"]
                       if recalled_return[p]["weight"] else None)
        estimated_return = current_total * q if q is not None else None
        estimated_switch = (estimated_return * conditional
                            if conditional is not None else (
                                ZERO if estimated_return == ZERO else None))
        actual_switch = actual_house[p][opposite]["weight"]
        estimated_absence = t - estimated_return if estimated_return is not None else None
        actual_absence = nonvote[p]["weight"]
        assert actual_return + actual_absence == t
        full = all_prior[p]
        total_full = sum(c["weight"] for c in full.values())
        comparisons.append({
            "prior_coalition": p,
            "baseline": baseline[p],
            "benchmark_returned": returned[p],
            "benchmark_explicit_nonvote": nonvote[p],
            "recalled_current_coalition": recalled_return[p],
            "q_recalled_among_query_voters": q,
            "p_reported_opposite_house_full_query_coalition": conditional,
            "estimated_returned_weight_units": estimated_return,
            "estimated_apparent_absence_weight_units": estimated_absence,
            "return_error_weight_units": estimated_return - actual_return if q is not None else None,
            "absence_error_weight_units": estimated_absence - actual_absence if q is not None else None,
            "benchmark_return_pct": percent(actual_return, t),
            "estimated_return_pct": percent(estimated_return, t) if q is not None else None,
            "return_error_pp": percent(estimated_return - actual_return, t) if q is not None else None,
            "benchmark_reported_opposite_house_weight_units": actual_switch,
            "estimated_reported_opposite_house_weight_units": estimated_switch,
            "switch_error_weight_units": estimated_switch - actual_switch if estimated_switch is not None else None,
            "benchmark_reported_opposite_house_pct_original_coalition": percent(actual_switch, t),
            "estimated_reported_opposite_house_pct_original_coalition": percent(estimated_switch, t) if estimated_switch is not None else None,
            "switch_error_pp_original_coalition": percent(estimated_switch - actual_switch, t) if estimated_switch is not None else None,
            "benchmark_opposite_house_pct_returners": percent(actual_switch, actual_return),
            "estimated_opposite_house_pct_query_returners": HUNDRED * conditional if conditional is not None else None,
            "all_2020_positive_validation_prior_coalition": full,
            "compatible_return_pct_lower_with_unmatched_2022": percent(full["positive"]["weight"], total_full),
            "compatible_return_pct_upper_with_unmatched_2022": percent(full["positive"]["weight"] + full["unknown"]["weight"], total_full),
            "design_ci": None,
        })
    return {
        "weight": weight_name, "include_dc": include_dc, "current_query_rule": current_rule,
        "dispositions": dispositions, "current_validated_voter_weight": current_total,
        "query_voter_weight": query_total, "all_prior_turnout_classifications": all_prior,
        "contemporaneous_to_recalled_prior_matrix_known_history": recall_matrix,
        "current_house_by_contemporaneous_prior_validated_voters": actual_house,
        "current_house_by_recalled_prior_query_voters": recalled_house,
        "self_report_record_conflicts_known_history": self_report_conflicts,
        "comparisons": comparisons,
    }


def review(rows):
    selected = []
    for row in rows:
        if set(REQUIRED) - set(row):
            raise ValueError("Required native columns missing")
        selected.append({name: row[name] for name in REQUIRED})
    rows = selected
    with localcontext() as context:
        context.prec = 50
        specs = [
            specification(rows, w, dc, rule)
            for w in WEIGHTS for dc in (False, True)
            for rule in ("record_positive", "reported_definitely_voted")
        ]
    return serialize({
        "status": "matched_panel_recall_stress_test_not_population_method_validation",
        "source_rows": len(rows),
        "weight_unit_definition": "Relative survey-weight mass; NOT numbers of people in the population.",
        "primary_specification": {"weight": WEIGHTS[0], "include_dc": False,
                                  "current_query_rule": "record_positive"},
        "specifications": specs,
        "interpretation": [
            "The primary comparison isolates changed prior-choice reporting on the same retained panel.",
            "Both years must have known survey state; US50 excludes DC residence in either survey wave.",
            "2020 positive administrative validation is required; missing records are not nonvoting.",
            "2022 unmatched histories remain in coverage/bounds and are excluded only from the known-history matched comparison.",
            "N and baseline T are measured in the SAME matched panel and weight frame, not FEC or national population totals.",
            "Self-report specifications hold administrative N fixed and change q/p respondent selection only.",
            "Candidate choice is surveyed; validated turnout does not validate candidate choice.",
            "House party uses each selected candidate's literal post-wave party; other parties are not reassigned.",
            "Every unknown/contest-nonvote response remains in the full conditional denominator.",
            "Other, presidential nonvote and unresolved prior choices are separate and never normalized away.",
            "Post-wave/administratively matched selection, attrition, calibration, matching errors and missing House choices remain limitations.",
            "These are paired recall/selection diagnostics, not independent full-population error estimates or a new 2026 estimate.",
            "Compatible missing-history ranges do not cover false matches or all survey error.",
            "The original CSV/DDI contain 11009 cases; the guide states 11015. This source discrepancy is unresolved.",
        ],
        "population_method_validated": False,
        "population_counts": None, "design_ci": None,
        "state_or_demographic_transition_certification": False,
        "public_release_qualified": False,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--native-labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.output.exists() or Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise ValueError("Output must be new and outside the repository")
    native = json.loads(args.metadata.read_text())["data"]["latestVersion"]
    if native["versionState"] != "RELEASED" or native["license"]["rightsIdentifier"] != "CC0-1.0":
        raise ValueError("Source release/license mismatch")
    item = next(f for f in native["files"] if f["dataFile"]["id"] == 10231930)
    if item["restricted"] is not False:
        raise ValueError("Source is restricted")
    raw = args.csv.read_bytes()
    file = item["dataFile"]
    if (file["checksum"]["type"] != "MD5" or len(raw) != file["originalFileSize"]
            or hashlib.md5(raw).hexdigest() != file["checksum"]["value"]):
        raise ValueError("Original CSV native checksum mismatch")
    labels = json.loads(args.native_labels.read_text())
    for name, expected in EXPECTED_LABELS.items():
        actual = labels["selected_variables"][name]["codes"]
        if any(actual.get(key) != value for key, value in expected.items()):
            raise ValueError("Native response labels differ: " + name)
    for receipt in labels["metadata_ranges"]:
        section = receipt["content_range"].split()[1].split("/")[0]
        matches = [
            p for p in args.native_labels.parent.glob("stata-metadata-*.bin")
            if hashlib.sha256(p.read_bytes()).hexdigest() == receipt["sha256"]
        ]
        if len(matches) != 1 or len(matches[0].read_bytes()) != receipt["bytes"]:
            raise ValueError("Frozen native metadata section mismatch: " + section)
    with args.csv.open(newline="", encoding="utf-8-sig") as handle:
        result = review(csv.DictReader(handle))
    if result["source_rows"] != 11009:
        raise ValueError("Original CSV/DDI case count differs")
    result["source_binding"] = {
        "doi": "10.7910/DVN/XV7ABM",
        "original_csv_sha256": hashlib.sha256(raw).hexdigest(),
        "original_csv_md5": hashlib.md5(raw).hexdigest(),
        "metadata_sha256": hashlib.sha256(args.metadata.read_bytes()).hexdigest(),
        "native_labels_sha256": hashlib.sha256(args.native_labels.read_bytes()).hexdigest(),
        "full_stata_checksum_verified": False,
        "reviewer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, sort_keys=True, indent=2)
        handle.write("\n")
    print(json.dumps({
        "status": result["status"], "source_rows": result["source_rows"],
        "primary_comparisons": result["specifications"][0]["comparisons"],
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

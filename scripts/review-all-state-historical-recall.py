"""Private all-state paired recall diagnostics; not population transition validation."""

import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import json
import os
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "historical_recall", Path(__file__).with_name("review-ces-historical-recall.py"))
recall = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recall)
FIPS = dict(zip(
    "1 2 4 5 6 8 9 10 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56".split(),
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(),
))
NATIONAL_SHA256 = "c8e66c2f900275a3a1233fa9720eb87447db1054a57d07427a284fb90ad41690"
RULES = ("record_positive", "reported_definitely_voted")


def effective_samples(rows, weight_name):
    accumulators = {p: [0, Decimal(0), Decimal(0)] for p in recall.PRIOR}
    for row in rows:
        w = recall.weight(row[weight_name])
        if not w or row["CL_2020gvm"] in recall.MISSING or row["TS_g2022"] in recall.MISSING:
            continue
        prior = recall.prior_choice(row["CC20_410"])
        acc = accumulators[prior]
        acc[0] += 1
        acc[1] += w
        acc[2] += w * w
    return {
        prior: {"raw_n": n, "weight_sum": total,
                "kish_effective_n_descriptive_not_design_precision": total * total / squares if squares else None}
        for prior, (n, total, squares) in accumulators.items()
    }


def state_diagnostic(rows):
    stable = [r for r in rows if r["inputstate_20"] == r["inputstate_22"]]
    moved = sum(r["inputstate_20"] in recall.STATES and r["inputstate_20"] != r["inputstate_22"]
                for r in rows)
    unresolved = len(rows) - len(stable) - moved
    specs = []
    with localcontext() as context:
        context.prec = 50
        for w in recall.WEIGHTS:
            samples = effective_samples(stable, w)
            for rule in RULES:
                result = recall.specification(stable, w, False, rule)
                result["baseline_effective_samples"] = samples
                specs.append(result)
    return {
        "current_survey_state_rows": len(rows),
        "same_survey_state_both_waves": len(stable),
        "different_prior_survey_state_excluded": moved,
        "unresolved_prior_survey_state_excluded": unresolved,
        "specifications": specs,
        "historical_test_status": (
            "paired_recall_diagnostic_only" if specs[0]["dispositions"]["retained"]["n"]
            else "no_primary_known_history_frame"),
        "population_method_validated": False,
        "state_representative_longitudinal_weights_qualified": False,
        "independent_population_transport_benchmark_available": False,
        "design_ci": None,
    }


def review(rows):
    grouped = {fips: [] for fips in FIPS}
    dc = unresolved = total = 0
    for row in rows:
        if set(recall.REQUIRED) - set(row):
            raise ValueError("Missing native historical fields")
        total += 1
        current = row["inputstate_22"]
        if current == "11":
            dc += 1
        elif current not in grouped:
            unresolved += 1
        else:
            grouped[current].append({k: row[k] for k in recall.REQUIRED})
    states = [{
        "state_code": FIPS[fips], "survey_state_fips": fips,
        **state_diagnostic(grouped[fips]),
    } for fips in FIPS]
    if total != sum(s["current_survey_state_rows"] for s in states) + dc + unresolved:
        raise ValueError("Source row partition does not reconcile")
    return recall.serialize({
        "status": "all_50_state_historical_recall_diagnostics_not_population_validation",
        "source_rows": total, "state_count": len(states),
        "dc_rows_separate_not_discarded": dc,
        "unresolved_current_state_rows": unresolved,
        "states": states,
        "primary_specification": {"weight": recall.WEIGHTS[0], "current_query_rule": RULES[0]},
        "method": {
            "period": "2020_President_to_2022_participation_and_House",
            "state_assignment": "2022 survey state; only same survey state in both waves enters each diagnostic",
            "specifications_per_state": 4,
            "comparison": "Contemporaneous 2020 choice versus 2022-recalled 2020 choice, same retained panel and weights",
            "count_units": "Relative survey-weight mass, not population people",
            "no_correction_fitted": True,
            "passing_threshold_used": False,
        },
        "limitations": [
            "National panel weights are not qualified state-representative longitudinal weights.",
            "Small state/coalition samples and effective-n diagnostics do not provide design confidence intervals.",
            "Paired recall agreement is not validation of official-population T/current-total N scaling.",
            "Survey-state stability is not verified election-day residence stability.",
            "Missing voter history stays unknown and is not assigned nonvoting.",
            "Candidate choice is surveyed; administrative turnout does not validate choice.",
            "All prior-choice, unknown, other and House contest-nonvote categories remain separate.",
            "Attrition, administrative matching and outcome calibration remain limitations.",
            "The state diagnostics condition on positive 2020 administrative participation, so do not identify entrants.",
            "A genuine 2022-to-2024 joint panel remains unacquired; no second-period validation is claimed.",
        ],
        "states_population_validated": 0,
        "population_method_validated": False,
        "public_release_qualified": False,
    })


def qualified_rows(source, national_path):
    raw = national_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != NATIONAL_SHA256:
        raise ValueError("Frozen national qualification differs")
    binding = json.loads(raw)["source_binding"]
    names = {
        "merged_recontact.csv": "original_csv_sha256",
        "dataset-metadata.json": "metadata_sha256",
        "native-labels-proof.json": "native_labels_sha256",
    }
    for name, key in names.items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != binding[key]:
            raise ValueError("Frozen historical input differs: " + name)
    helper = Path(__file__).with_name("review-ces-historical-recall.py")
    if hashlib.sha256(helper.read_bytes()).hexdigest() != binding["reviewer_sha256"]:
        raise ValueError("Qualified native-code helper differs")
    native = json.loads((source / "dataset-metadata.json").read_text())["data"]["latestVersion"]
    item = next(f for f in native["files"] if f["dataFile"]["id"] == 10231930)
    if (item["restricted"] is not False or native["versionState"] != "RELEASED"
            or native["license"]["rightsIdentifier"] != "CC0-1.0"):
        raise ValueError("Historical source access qualification differs")
    data = (source / "merged_recontact.csv").read_bytes()
    if (hashlib.md5(data).hexdigest() != item["dataFile"]["checksum"]["value"]
            or len(data) != item["dataFile"]["originalFileSize"]):
        raise ValueError("Original native CSV checksum differs")
    with (source / "merged_recontact.csv").open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 11009:
        raise ValueError("Native panel row count differs")
    return rows, binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-directory", type=Path, required=True)
    parser.add_argument("--national-diagnostic", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise ValueError("Output must be new and outside the repository")
    rows, binding = qualified_rows(args.source_directory, args.national_diagnostic)
    result = review(rows)
    result["source_binding"] = binding
    result["reviewer_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    raw = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    args.output.mkdir(parents=True, mode=0o700)
    descriptor = os.open(args.output / "all-state-historical.json",
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        target.write(raw)
    print(json.dumps({"states": len(result["states"]), "specifications": 4 * len(result["states"]),
                      "source_rows": result["source_rows"], "population_validated_states": 0,
                      "results_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()

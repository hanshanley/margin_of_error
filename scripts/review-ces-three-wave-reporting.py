"""Conditional 2020 report/profile comparison using the retained 2024 panel."""

import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HELPER = ROOT / "review-ces-historical-recall.py"
HELPER_SHA256 = "3b1e036b5d4de898e3c815135ad575fbb010977c5e930b6d1360f6f20de348e9"
SOURCE_SHA256 = "e9921d391159cf8fcb68a0b69aa76c94a5bf73436f516606bf3fb310125ba5ac"
spec = importlib.util.spec_from_file_location("paired_reporting", HELPER)
paired = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paired)
FIPS = dict(zip(
    "1 2 4 5 6 8 9 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56".split(),
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(),
))
WEIGHTS = ("commonpostweight_24", "commonpostweight_22", "vvweight_post_22")
FRAMES = ("known_reference_choice", "all_reference_categories")
RULES = ("record_positive", "reported_definitely_voted")
HOUSE_CODES = {"1", "2", "3", "4", "5", "10", "11", "13", "98", "99"}
REQUIRED = (
    "CC20_410", "presvote20post_24", "presvote20post_22", "CL_2020gvm",
    "TS_g2024", "CC24_401", "CC24_412", "inputstate_20", "inputstate_24",
) + WEIGHTS + tuple("HouseCand%dParty_post_24" % i for i in range(1, 6))


def checked_bridge(bridge):
    if (bridge["status"] != "cross_wave_common_item_bridge_conditional_not_panel_native_labels"
            or bridge["panel_numeric_labels_directly_qualified"] is not False
            or bridge["panel_code_transport_assumption_required"] is not True
            or bridge["same_case_2020_choice_and_state_matches"] != 6175):
        raise ValueError("Require the explicit conditional common-item bridge, not invented panel labels")
    expected = {"1": "Joe Biden", "2": "Donald Trump", "6": "Did not vote for President"}
    if any(bridge["profile_2020_codes_in_2024_common"].get(k) != v for k, v in expected.items()):
        raise ValueError("Profile codebook differs")
    if set(bridge["current_house_codes_in_2024_common"]) != HOUSE_CODES:
        raise ValueError("Do not inherit unsupported 2022 House slots or nonvote codes")
    for code, label in (("10", "Other"), ("11", "I did not vote in this race"), ("13", "Not sure")):
        if bridge["current_house_codes_in_2024_common"][code] != label:
            raise ValueError("Current House noncandidate responses differ")
    baseline = {"1": "Joe Biden (Democrat)", "2": "Donald J. Trump (Republican)",
                "4": "Other", "5": "I did not vote in this race",
                "6": "I did not vote", "7": "Not sure"}
    if any(bridge["baseline_codes"].get(code) != label for code, label in baseline.items()):
        raise ValueError("Qualified contemporaneous baseline codes differ")


def canonical_rows(rows, weight, frame):
    if weight not in WEIGHTS or frame not in FRAMES:
        raise ValueError("Unknown source weight or reference-choice frame")
    result = []
    excluded = 0
    for row in rows:
        if row["CC24_412"] not in HOUSE_CODES | paired.MISSING:
            raise ValueError("Unsupported 2024 House response")
        known = paired.prior_choice(row["CC20_410"]) != "UNKNOWN"
        if frame == "known_reference_choice" and not known:
            excluded += 1
            continue
        # The frozen arithmetic helper uses role aliases named for its original 2022 wave.
        mapped = {
            "CC20_410": row["CC20_410"], "presvote20post": row["presvote20post_24"],
            "CL_2020gvm": row["CL_2020gvm"], "TS_g2022": row["TS_g2024"],
            "CC22_401": row["CC24_401"], "CC22_412": row["CC24_412"],
            "inputstate_20": row["inputstate_20"], "inputstate_22": row["inputstate_24"],
            "commonpostweight_22": row[weight],
        }
        for i in range(1, 9):
            mapped["HouseCand%dParty_post_22" % i] = (
                row["HouseCand%dParty_post_24" % i] if i <= 5 else "NA")
        result.append(mapped)
    return result, excluded


def renamed(value):
    if isinstance(value, dict):
        return {
            key.replace("unmatched_2022", "unmatched_current").replace("recalled", "profile")
            .replace("benchmark", "contemporaneous_reference").replace("error", "difference"):
                renamed(item) for key, item in value.items()
        }
    if isinstance(value, list):
        return [renamed(item) for item in value]
    return value


def scope_review(rows, include_dc):
    specifications = []
    for weight in WEIGHTS:
        for frame in FRAMES:
            canonical, excluded = canonical_rows(rows, weight, frame)
            for rule in RULES:
                result = paired.specification(canonical, "commonpostweight_22", include_dc, rule)
                result["weight"] = weight
                result["reference_choice_frame"] = frame
                result["unknown_reference_choice_rows_excluded_from_paired_frame"] = excluded
                specifications.append(renamed(result))
    return specifications


def review(rows):
    selected = []
    for row in rows:
        if set(REQUIRED) - set(row):
            raise ValueError("Missing native three-wave reporting fields")
        selected.append({name: row[name] for name in REQUIRED})
    states = []
    with paired.localcontext() as context:
        context.prec = 50
        for fips, code in FIPS.items():
            current = [row for row in selected if row["inputstate_24"] == fips]
            stable = [row for row in current if row["inputstate_20"] == fips]
            states.append({
                "scope": code, "current_survey_state_rows": len(current),
                "stable_survey_state_rows": len(stable),
                "different_or_unknown_2020_survey_state_excluded_rows": len(current) - len(stable),
                "specifications": scope_review(stable, True),
            })
        for name, dc in (("US50", False), ("US51", True)):
            states.append({"scope": name, "source_rows": len(selected),
                           "specifications": scope_review(selected, dc)})
    unresolved = sum(row["inputstate_24"] not in FIPS for row in selected)
    assert sum(state["current_survey_state_rows"] for state in states[:-2]) + unresolved == len(selected)
    return paired.serialize({
        "status": "all_state_conditional_2020_to2024_reporting_selection_diagnostic",
        "source_rows": len(selected), "scopes": states,
        "unresolved_current_survey_state_rows": unresolved,
        "profile2020_different_between2022_and2024_rows": sum(
            row["presvote20post_22"] != row["presvote20post_24"] for row in selected),
        "primary": {"weight": WEIGHTS[0], "reference_choice_frame": FRAMES[0], "current_rule": RULES[0]},
        "panel_code_transport_assumption_required": True,
        "panel_native_numeric_choice_labels_qualified": False,
        "population_method_validated": False, "public_release_qualified": False,
        "limits": [
            "Condition on the documented common-item codebook bridge, not absent panel-native numeric labels.",
            "All6175 original2020choice/state fields match the already qualified two-wave release by private case key.",
            "2024profile andHouse definitions are transported from the same common-item codebooks; direct2024case equivalence is unavailable.",
            "The primary paired frame has known contemporaneous2020choice; all-reference sensitivity preserves missing original choices.",
            "Positive2020administrative history and known current history define the selected matched diagnostic, not the full2024electorate.",
            "Unknown original choice filled by a later profile is not proof of false reporting; missing current history remains in compatible bounds.",
            "State diagnostics require the same survey state in2020/2024; national scopes retain within-scope movers and explicitly exclude DC as specified.",
            "A2020profile carried in2024 is not proven freshly asked in2024; do not interpret differences as four-year memory effects.",
            "Reference candidate choice is survey-reported, not administrative gold. Differences are reporting/selection differences, not population errors.",
            "N and baselineT are relative weights in the same retained panel, not national people or official election totals.",
            "The earlier2022weight frames are sensitivities, not2024validated-voter weights. No2024vvweight is invented.",
            "Self-report sensitivities hold administratively positiveN fixed and change only the queryq/p sample.",
            "Current House choice is supplementary and uses literal source candidate parties, not registered party or inferred party.",
            "Original2020adult selection excludes later first-age-eligible cohorts; this diagnostic does not validate entry or population transport.",
            "No fitted correction, posthoc passing threshold, design confidence interval or changed2026estimate is produced.",
        ],
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "bridge", "prespec", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT.parent in args.output.resolve().parents:
        raise ValueError("Require new private output outside repository")
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    hashes = {
        "source": digest(args.source), "bridge": digest(args.bridge), "helper": digest(HELPER),
        "reviewer": digest(Path(__file__)),
        "tests": digest(ROOT / "test-review-ces-three-wave-reporting.py"),
    }
    if (hashes["source"] != SOURCE_SHA256 or hashes["helper"] != HELPER_SHA256
            or json.loads(args.prespec.read_text())["input_sha256"] != hashes):
        raise ValueError("Native source/code/design binding differs")
    checked_bridge(json.loads(args.bridge.read_text()))
    with args.source.open(newline="", encoding="utf-8-sig") as source:
        result = review(csv.DictReader(source))
    if result["source_rows"] != 6175:
        raise ValueError("Native case count differs")
    result["input_sha256"] = hashes
    result["prespec_sha256"] = digest(args.prespec)
    args.output.mkdir(parents=True, mode=0o700)
    descriptor = os.open(args.output / "reporting-diagnostic.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(result, target, indent=2, allow_nan=False)
        target.write("\n")
    print(json.dumps({"status": result["status"], "cases": result["source_rows"],
                      "scopes": len(result["scopes"]),
                      "specifications": sum(len(scope["specifications"]) for scope in result["scopes"])}))


if __name__ == "__main__":
    main()

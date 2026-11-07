"""Private 2022-to-2024 panel participation, not population transport validation."""

import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path


SOURCE_SHA256 = "e9921d391159cf8fcb68a0b69aa76c94a5bf73436f516606bf3fb310125ba5ac"
STATES = tuple("AK AL AR AZ CA CO CT DC DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY".split())
STATUS = ("POSITIVE", "EXPLICIT_NONVOTE", "UNKNOWN")
WEIGHTS = ("commonweight_24", "commonpostweight_24", "commonpostweight_22", "vvweight_post_22")
SCOPES = STATES + ("UNLOCATED", "ALL_SOURCE")
MISSING = {"", "NA"}
ZERO = Decimal(0)


def history(value, year):
    if value in MISSING:
        return "UNKNOWN"
    if value not in {str(i) for i in range(1, 8)}:
        raise ValueError("Unexpected numbered general-history code for " + str(year))
    return "EXPLICIT_NONVOTE" if value == "7" else "POSITIVE"


def matched_state(value):
    if value in MISSING or value == "-1":
        return None
    if value not in STATES:
        raise ValueError("Expected literal matched-state abbreviation, not numeric state code")
    return value


def weight(value):
    if value in MISSING:
        return None
    value = Decimal(value)
    if not value.is_finite() or value < 0:
        raise ValueError("Invalid panel weight")
    return value


def cell():
    return {"n": 0, "weight": ZERO, "squared_weight": ZERO}


def add(target, value):
    target["n"] += 1
    target["weight"] += value
    target["squared_weight"] += value * value


def frame():
    return {
        "missing_or_zero_weight_rows": 0, "used": cell(),
        "matrix": {prior: {current: cell() for current in STATUS} for prior in STATUS},
        "current_only_known_2020_participants": cell(),
        "current_only_first_ever_status_unresolved": cell(),
    }


def scope():
    return {
        "source_rows": 0, "known_matched_state_changed_rows": 0,
        "raw_matrix": {prior: {current: 0 for current in STATUS} for prior in STATUS},
        "weight_frames": {name: frame() for name in WEIGHTS},
    }


def review(rows, primary_weight="commonpostweight_24"):
    if primary_weight not in ("commonweight_24", "commonpostweight_24"):
        raise ValueError("Earlier registered/adult weights are not current primary weights")
    scopes = {name: scope() for name in SCOPES}
    total = 0
    with localcontext() as context:
        context.prec = 50
        for row in rows:
            total += 1
            prior, current = history(row["TS_g2022"], 2022), history(row["TS_g2024"], 2024)
            old_state, new_state = matched_state(row["TS_state_22"]), matched_state(row["TS_state_24"])
            older = row["CL_2020gvm"]
            if older not in MISSING and older not in {"1", "2", "3", "4", "5"}:
                raise ValueError("Unexpected numbered 2020 positive-history code")
            values = {name: weight(row[name]) for name in WEIGHTS}
            for name in (new_state or "UNLOCATED", "ALL_SOURCE"):
                result = scopes[name]
                result["source_rows"] += 1
                result["raw_matrix"][prior][current] += 1
                result["known_matched_state_changed_rows"] += bool(
                    old_state and new_state and old_state != new_state)
                for key, value in values.items():
                    weighted = result["weight_frames"][key]
                    if not value:
                        weighted["missing_or_zero_weight_rows"] += 1
                        continue
                    add(weighted["used"], value)
                    add(weighted["matrix"][prior][current], value)
                    if (prior, current) == ("EXPLICIT_NONVOTE", "POSITIVE"):
                        field = ("current_only_known_2020_participants" if older not in MISSING
                                 else "current_only_first_ever_status_unresolved")
                        add(weighted[field], value)
        output = []
        for name in SCOPES:
            result = scopes[name]
            assert sum(sum(row.values()) for row in result["raw_matrix"].values()) == result["source_rows"]
            for weighted in result["weight_frames"].values():
                assert weighted["used"]["n"] + weighted["missing_or_zero_weight_rows"] == result["source_rows"]
                assert sum(value["weight"] for row in weighted["matrix"].values() for value in row.values()) == weighted["used"]["weight"]
                entered = weighted["matrix"]["EXPLICIT_NONVOTE"]["POSITIVE"]
                older = weighted["current_only_known_2020_participants"]
                unresolved = weighted["current_only_first_ever_status_unresolved"]
                assert entered["n"] == older["n"] + unresolved["n"]
                assert entered["weight"] == older["weight"] + unresolved["weight"]
                prior = weighted["matrix"]["POSITIVE"]
                denominator = sum(value["weight"] for value in prior.values())
                returned = prior["POSITIVE"]["weight"]
                unknown = prior["UNKNOWN"]["weight"]
                weighted["prior_positive_2022_weight"] = denominator
                weighted["return_pct_unknown_compatible_lower_not_ci"] = (
                    100 * returned / denominator if denominator else None)
                weighted["return_pct_unknown_compatible_upper_not_ci"] = (
                    100 * (returned + unknown) / denominator if denominator else None)
                weighted["first_ever_voter_count"] = None
                weighted["design_ci"] = None
            output.append({"scope": name, **result})
    assert sum(scopes[name]["source_rows"] for name in SCOPES if name != "ALL_SOURCE") == total
    return {
        "status": "all_state_2022_to2024_selected_panel_participation_not_population_validation",
        "source_rows": total, "scopes": output, "primary_weight": primary_weight,
        "population_method_validated": False, "public_release_qualified": False,
        "limits": [
            "The same retained2020adult respondents supply2022 and2024 validated-history classifications.",
            "These are selected-panel raw counts and relative weight units, not statewide population transition totals.",
            "All50states and DC are current matched-record states as ofAugust2025; UNLOCATED and ALL_SOURCE retain every case.",
            "Changed matched states are reported, not silently excluded or treated as national turnout entry or exit.",
            "State grouping is not a historical state-cohort or election-day residence definition.",
            "Only code7 is explicit nonvote in2022/2024; missing histories remain UNKNOWN on both axes.",
            "Unknown-compatible ranges are conditional on correct known records, not design CIs or false-match bounds.",
            "This administrative-history-only analysis consumes no2024post-interview answers; commonweight_24 supports the full retained respondent frame.",
            "Commonpostweight_24 is retained as a post-interview-frame sensitivity; earlier2022weights are not2024voter weights.",
            "Current-only explicit2022nonvoters with positive2020history are known earlier participants, not first-ever voters.",
            "Current-only people without positive2020history remain first-ever-unresolved; earlier elections are unobserved.",
            "Panel recruitment in2020 excludes people first age-eligible in2022/2024; this dataset cannot resolve all population entrants.",
            "This is new joint-history evidence, not an independent replication or a tautological N*q accuracy test.",
            "No new2026 correction, current-choice inference, demographic population rate or source certification is produced.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "qualification", "prespec", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--primary-weight", choices=("commonweight_24", "commonpostweight_24"),
                        default="commonpostweight_24")
    args = parser.parse_args()
    if args.output.exists() or Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise ValueError("Require new private output outside repository")
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    hashes = {
        "source": digest(args.source), "qualification": digest(args.qualification),
        "reviewer": digest(Path(__file__)),
        "tests": digest(Path(__file__).with_name("test-review-ces-three-wave-participation.py")),
    }
    qualification = json.loads(args.qualification.read_text())
    design = json.loads(args.prespec.read_text())
    if (hashes["source"] != SOURCE_SHA256 or qualification["source_sha256"] != SOURCE_SHA256
            or qualification["status"] != "three_wave_participation_codes_qualified_from_explicit_numbered_guide"
            or design["input_sha256"] != hashes or design["primary_weight"] != args.primary_weight
            or (args.primary_weight == "commonweight_24"
                and qualification.get("administrative_only_primary_weight") != "commonweight_24")):
        raise ValueError("Native source/coding/design binding differs")
    with args.source.open(newline="", encoding="utf-8-sig") as source:
        result = review(csv.DictReader(source), args.primary_weight)
    if result["source_rows"] != 6175:
        raise ValueError("Native case count differs")
    result["input_sha256"] = hashes
    result["prespec_sha256"] = digest(args.prespec)
    args.output.mkdir(parents=True, mode=0o700)
    descriptor = os.open(args.output / "panel-participation.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(result, target, indent=2, default=str, allow_nan=False)
        target.write("\n")
    print(json.dumps({"status": result["status"], "cases": result["source_rows"],
                      "scopes": len(result["scopes"]), "weight_frames": len(WEIGHTS)}))


if __name__ == "__main__":
    main()

"""Conditional historical entry checks; not matched-population validation."""

import argparse
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path


def entry_check(specification, vendor):
    turnout = vendor["total_voter_turnout"]["2022"]
    first = vendor["first_time_voters_vendor_definition"]["2022"]
    if type(turnout) is not int or turnout <= 0 or type(first) is not int or not 0 <= first <= turnout:
        raise ValueError("Invalid vendor first-record marginal")
    total = Decimal(specification["current_query_weight"])
    if total < 0:
        raise ValueError("Invalid current-query denominator")
    with localcontext() as context:
        context.prec = 50
        proxy = Decimal(first) / turnout
        known = Decimal(specification["prior"]["NO_PRESIDENT"]["weight"])
        unknown = Decimal(specification["prior"]["UNKNOWN"]["weight"])
        conflicts = sum(
            Decimal(specification["prior_by_age"][prior]["UNDER_18_IN_2020"]["weight"])
            for prior in ("D", "R", "O"))
        if min(known, unknown, conflicts) < 0 or known + unknown + conflicts > total:
            raise ValueError("Overlapping or invalid current-query categories")
        upper = (known + unknown) / total if total else None
        relaxed = (known + unknown + conflicts) / total if total else None
        return {
            "vendor_no_prior_record_share": proxy,
            "reported_no_presidential_vote_share": known / total if total else None,
            "maximum_no_presidential_vote_if_all_unknown_choices_were_nonvoters": upper,
            "maximum_also_allowing_all_underage_prior_choice_conflicts": relaxed,
            "signed_proxy_minus_unknown_compatible_maximum_pp": 100 * (proxy - upper) if upper is not None else None,
            "proxy_exceeds_unknown_compatible_maximum": proxy > upper if upper is not None else None,
            "proxy_exceeds_age_conflict_relaxed_maximum": proxy > relaxed if relaxed is not None else None,
            "matched_population_rejection_or_significance": False,
        }


def nc_check(specification, administrative):
    comparisons = [c for c in administrative["comparisons"]
                   if (c["prior_year"], c["current_year"]) == (2020, 2022)]
    if len(comparisons) != 1:
        raise ValueError("Require one qualified NC2020-to-2022 comparison")
    bounds = comparisons[0]["missing_record_only_sensitivity_not_ci"]
    ballots = next(c["official_ballots_cast"] for c in administrative["year_controls"] if c["year"] == 2020)
    presvotes = specification["control"]["presidential_2020"]["total"]
    if ballots < presvotes:
        raise ValueError("Presidential votes exceed all-ballot control")
    contest_gap = ballots - presvotes
    lower = max(0, bounds["overlap_count_lower"] - contest_gap)
    upper = min(bounds["overlap_count_upper"], presvotes)
    if not 0 <= lower <= upper:
        raise ValueError("Invalid conditional NC presidential overlap bounds")
    values = specification["prior_composition"]
    if any(values[prior]["conditional_scaled_current_people"] is None for prior in ("D", "R", "O", "UNKNOWN")):
        known = possible = signed_gap = minimum_incoming = None
    else:
        with localcontext() as context:
            context.prec = 50
            known = sum(Decimal(values[prior]["conditional_scaled_current_people"]) for prior in ("D", "R", "O"))
            possible = known + Decimal(values["UNKNOWN"]["conditional_scaled_current_people"])
            signed_gap = known - upper
            minimum_incoming = max(Decimal(0), signed_gap)
    return {
        "official_2020_ballots_without_presidential_candidate_vote": contest_gap,
        "conditional_nc2020_presidential_return_count_lower": lower,
        "conditional_nc2020_presidential_return_count_upper": upper,
        "estimated_prior_US_presidential_participants_among_current_NC_voters": known,
        "maximum_prior_US_presidential_participants_if_all_unknowns_participated": possible,
        "signed_known_US_returns_minus_NC_upper": signed_gap,
        "minimum_nonNC2020_presidential_participants_needed_if_all_measurements_correct": minimum_incoming,
        "known_plus_unknown_below_NC_minimum_under_stated_assumptions": (
            possible < lower if possible is not None else None),
        "matched_population_error": None,
        "design_ci": None,
    }


def review(survey, vendor, administrative):
    states = {state["state_code"]: state for state in survey["states"]}
    if set(states) - {"US50"} != set(vendor["states"]) or len(vendor["states"]) != 51:
        raise ValueError("Require all50states and separateDC in both sources")
    results = []
    for code in sorted(vendor["states"]):
        comparisons = []
        for specification in states[code]["specifications"]:
            comparisons.append({
                "weight": specification["weight"],
                "current_rule": specification["current_rule"],
                "geography_rule": specification["geography_rule"],
                "entry_subset_condition": entry_check(specification, vendor["states"][code]),
                "nc_administrative_condition": nc_check(specification, administrative) if code == "NC" else None,
            })
        results.append({"state_code": code, "specifications": comparisons})
    return {
        "status": "all_state_conditional_entry_compatibility_not_matched_validation",
        "states": results, "population_method_validated": False, "public_release_qualified": False,
        "limits": [
            "A true first-ever voter cannot have a prior presidential vote; a vendor first-record proxy need not identify true first-ever voting.",
            "Subset comparisons require common current-electorate frames, correct reports, complete histories and compatible source vintages.",
            "Survey selection, weighting, sampling error, false or missing records, migration and timing can explain differences; no matched-frame claim or significance test is made.",
            "Unknown prior choices are allowed entirely to be prior presidential nonvoters before flagging a subset gap.",
            "An additional sensitivity allows all underage prior-choice conflicts to be nonvoters; the original estimates are never recoded.",
            "NC bounds additionally assume correct positives/stable identifiers/unique ballots and only missing history records.",
            "NC administrative overlap is within NC in both years; surveyed prior US voting can include people whose2020vote was elsewhere.",
            "Subtracting all2020ballots without presidential votes gives a conservative presidential-overlap lower bound, not observed presidential history.",
            "Minimum incoming-prior-participant counts are conditional mathematical requirements, not measured migration or a fitted correction.",
            "Specifications are retained together; no favorable weighting variant is selected after these checks.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("survey", "survey-proof", "vendor", "vendor-proof", "nc-controls", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise ValueError("Require a new private output outside repository")
    survey, vendor, nc = (json.loads(path.read_text()) for path in (args.survey, args.vendor, args.nc_controls))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    for path, proof, key in ((args.survey, args.survey_proof, "results_sha256"),
                             (args.vendor, args.vendor_proof, "result_sha256")):
        if json.loads(proof.read_text())[key] != digest(path):
            raise ValueError("Independent source-result proof differs")
    if nc["status"] != "statewide_administrative_coverage_checked_not_population_transition_certification":
        raise ValueError("Unqualified NC administrative coverage artifact")
    result = review(survey, vendor, nc)
    result["input_sha256"] = {name: digest(getattr(args, name)) for name in
                              ("survey", "survey_proof", "vendor", "vendor_proof", "nc_controls")}
    args.output.mkdir(parents=True, mode=0o700)
    descriptor = os.open(args.output / "entry-compatibility.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(result, target, indent=2, default=str, allow_nan=False)
        target.write("\n")
    print(json.dumps({"status": result["status"], "scopes": len(result["states"]),
                      "specifications": sum(len(state["specifications"]) for state in result["states"])}))


if __name__ == "__main__":
    main()

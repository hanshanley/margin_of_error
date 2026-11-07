"""Expose native candidate conditionals without qualifying population arithmetic."""

import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "candidate_conditionals_native", Path(__file__).with_name("review-cnn-voter-poll.py"))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
EXPECTED = {("AK", "GG"), ("AK", "SG"), ("NH", "GG"), ("NH", "SG")}
WITHHELD = {"withheld_nonunique_literal_dem_rep_comparison",
            "withheld_unreconciled_prior_composition"}


def review(snapshot):
    sources = snapshot["sources"]
    inventory = {(source["configuration_entry"]["stateAbbr"], source["configuration_entry"]["raceTypeCode"])
                 for source in sources}
    if len(sources) != 4 or inventory != EXPECTED:
        raise ValueError("Expected four selected Alaska/New Hampshire state sources")
    results = []
    for source in sources:
        checked = native.review_source(source)
        if checked["status"] not in WITHHELD or source["configuration_entry"]["subsetNumber"] != 0:
            raise ValueError("Source is not qualified for this unscaled selected view")
        data = source["selected_native_data"]
        candidates = [{
            "candidate_id": candidate["candidateId"], "full_name": candidate["fullName"],
            "literal_party": candidate["partyAbbreviation"], "literal_party_name": candidate["partyName"],
        } for candidate in data["candidates"]]
        if any(not candidate["full_name"] for candidate in candidates):
            raise ValueError("Full candidate identity is required")
        priors = {}
        for answer in data["questions"][0]["answers"]:
            priors[native.PRIOR[answer["answer"]]] = {
                "reported_prior_share_pct": native.percent(answer["totalPercentage"]),
                "current_candidate_percentages": [
                    {"candidate_id": cell["candidateId"], "percentage": native.percent(cell["percentage"])}
                    for cell in answer["candidateAnswers"]],
            }
        results.append({
            "state_code": checked["state_code"], "contest_code": checked["contest_code"],
            "contest_title": checked["contest_title"], "source_url": source["source_url"],
            "source_sha256": source["source_sha256"], "source_timestamp": checked["source_timestamp"],
            "native_stage": data["stage"], "inferred_ranked_choice_round": None,
            "ordinary_comparison_status": checked["status"],
            "reported_prior_composition_sum_pct": checked["reported_composition_sum_pct"],
            "unexplained_gap_from_100_pct": checked["reported_composition_difference_from_100_pct"],
            "candidates": candidates, "reported_choices_by_prior": priors,
            "estimated_returning_count": None, "estimated_switcher_count": None,
            "apparent_absence_count": None, "measured_staying_home_count": None,
            "original_coalition_switching_rate": None, "share_of_total_swing": None,
            "design_confidence_interval": None,
        })
    return {
        "status": "published_candidate_specific_conditionals_unscaled",
        "states": ["AK", "NH"], "ordinary_population_comparisons_still_withheld": True,
        "population_or_original_coalition_scaling_performed": False,
        "current_choice_can_retain_pre_election_intent": True,
        "limits": [
            "Native candidate percentages condition on recalled prior choice among current survey participants.",
            "No q scaling, prior-composition renormalization, inferred omitted category or reconstructed suppression.",
            "Multiple Republican candidates are not pooled; the literal Independent remains independent.",
            "No ranked-choice round, matched final-round transition or ordinary two-party attribution is inferred.",
            "Unexplained prior-composition gaps retain the original population-arithmetic withholding gates.",
            "No population switcher/absence count, original-coalition rate, design CI or county/precinct allocation.",
            "SSRS current choice can retain pre-election intent; source calibration is not independent validation.",
            "Offices share respondents and are not additive; CNN/NBC/MS NOW are one study.",
        ],
        "contests": sorted(results, key=lambda row: (row["state_code"], row["contest_code"])),
    }

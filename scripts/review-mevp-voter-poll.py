#!/usr/bin/env python3
"""Review selected MEVP joint facts without inventing population denominators."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = "https://2026electionpoll.us/"
GROUPS = {
    "latino": ("Latino", "Latino"),
    "aapi": ("AAPI", "AAPI"),
    "white": ("White", "White"),
    "black": ("Black", "Black"),
    "native-american": ("NativeAm", "Native-American"),
}
BANNERS = [
    "Trump24/HouseDem26", "Abstain+Other24/HouseDem26", "Trump24",
    "Harris24", "Abstain/Other24", "NewVoter", "Men", "Women",
]


def integer(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Invalid source integer")
    return value


def review_snapshot(snapshot):
    if (snapshot["study_id"] != "bsp-aarc-mevp-2026"
            or snapshot["question_id"] != "Q10"
            or snapshot["contest_scope"] != "respondent_district_house_party_choice"
            or snapshot["prior_question_universe"] != "previous_voters_18plus_in_2024"):
        raise ValueError("Wrong study, question, contest or prior-choice universe")
    if (snapshot["methodology_url"] != ROOT + "methodology/"
            or snapshot["methods_field_end"] != "2026-11-03"
            or snapshot["pdf_field_end"] != "2026-11-02"):
        raise ValueError("Unexpected source methods or date observations")
    groups, seen = [], set()
    for table in snapshot["tables"]:
        code = table["group_id"]
        if code not in GROUPS or code in seen:
            raise ValueError("Unknown or duplicate source group")
        seen.add(code)
        name, file_prefix = GROUPS[code]
        expected = ROOT + f"wp-content/uploads/2026/11/{file_prefix}-Xtabs-Midterm-Election-Voter-Poll-2026.pdf"
        if table["source_url"] != expected or table["columns"] != [name] + BANNERS:
            raise ValueError("Wrong source or ambiguous conditional banners")
        digest = table["source_sha256"]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid source digest")
        integer(table["source_bytes"], 12_000_000)
        if not table["source_bytes"]:
            raise ValueError("Empty source")
        n = integer(table["raw_respondent_bases"][0], 100_000)
        if not n or len(table["raw_respondent_bases"]) != 9:
            raise ValueError("Invalid respondent bases")
        bases = [integer(value, n) for value in table["raw_respondent_bases"]]
        if bases[1] > bases[3] or bases[2] > bases[5]:
            raise ValueError("Outcome-selected raw subset exceeds its prior-choice parent")
        rows = table["house_choice_pct"]
        if set(rows) != {"D", "R", "O"} or any(len(row) != 9 for row in rows.values()):
            raise ValueError("Incomplete House-choice table")
        for values in rows.values():
            for value in values:
                integer(value, 100)
        for i, base in enumerate(bases):
            total = sum(row[i] for row in rows.values())
            if (base and not 99 <= total <= 101) or (not base and total != 0):
                raise ValueError("Invalid rounded conditional-choice column")
        prior = table["prior_choice_pct_among_previous_voters"]
        if set(prior) != {"D", "R", "O", "N"}:
            raise ValueError("Incomplete conditional prior-choice question")
        if not 98 <= sum(integer(value, 100) for value in prior.values()) <= 102:
            raise ValueError("Invalid rounded conditional prior-choice composition")
        first = table["first_november_election_pct"]
        if set(first) != {"2026", "2024", "2022", "earlier"}:
            raise ValueError("Incomplete first-November-election table")
        if not 98 <= sum(integer(value, 100) for value in first.values()) <= 102:
            raise ValueError("Invalid rounded first-November-election composition")
        unclassified = n - sum(bases[3:7])
        if unclassified < 0:
            raise ValueError("Disjoint prior/new raw bases exceed total")
        transitions = {}
        for prior_party, column, opposite in [("R", 3, "D"), ("D", 4, "R")]:
            transitions[prior_party] = {
                "raw_respondents": bases[column],
                "status": "published_conditional_percentage" if bases[column] else "withheld_zero_base",
                "current_house_choice_pct": {party: values[column] for party, values in rows.items()},
                "reported_opposite_party_pct": rows[opposite][column] if bases[column] else None,
                "reported_choice_sum_pct": sum(values[column] for values in rows.values()),
                "design_confidence_interval": None,
            }
        groups.append({
            "group_id": code, "source_group": name, "source_url": expected,
            "source_sha256": digest, "source_pages": table["source_pages"],
            "raw_group_respondents": n,
            "raw_unclassified_prior_or_first_november_respondents": unclassified,
            "reported_choices_among_current_voters_by_reported_prior": transitions,
            "reported_first_november_2026_pct": first["2026"],
            "reported_prior_composition_among_previous_voters": prior,
            "prior_composition_among_all_current_group_voters": None,
            "current_electorate_group_population_share": None,
            "switcher_population_count": None,
            "original_2024_coalition_switching_pct": None,
            "apparent_absence": None,
            "demographic_turnout_rate": None,
            "share_of_total_swing": None,
        })
    if seen != set(GROUPS):
        raise ValueError("Missing selected racial group")
    return {
        "study_id": snapshot["study_id"], "methodology_url": snapshot["methodology_url"],
        "source_snapshot_sha256": hashlib.sha256(json.dumps(
            snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
        "methods_field_end": snapshot["methods_field_end"],
        "pdf_field_end": snapshot["pdf_field_end"],
        "groups": groups,
        "qualification": {
            "source_published_conditional_house_choices": True,
            "state_or_local_estimates_released": False,
            "population_decomposition_released": False,
            "renormalized_published_percentages": False,
            "limitations": [
                "The universe includes reported early voters and respondents certain they would vote on Election Day.",
                "Reported past presidential choice and intended/completed House party choice are not administrative ballot validation.",
                "Q29 excludes first-November-2026 voters; its marginals are not the whole current electorate.",
                "The first-November-election response does not establish first-ever participation in any election.",
                "Raw banner bases are not weighted population fractions, effective samples or design confidence intervals.",
                "Unknown prior/first-November responses remain unclassified, not inferred nonvoters.",
                "The study oversamples racial groups and geographies; do not infer population shares from sample counts.",
                "House party choices are generic respondent-district answers, not candidate-ID-reconciled returns.",
                "National Senate/governor answers cover applicable subsets, not the same nationwide House electorate.",
                "Weights use turnout models and final comparisons with results; agreement is not independent validation.",
                "The methods end November 3 while all selected PDFs say November 2; retain both source observations.",
                "Do not pool this study with SSRS as if samples, weights and question universes were interchangeable.",
            ],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = review_snapshot(json.loads(args.snapshot.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"reviewed_groups": len(result["groups"]), "population_decomposition_released": False}))


if __name__ == "__main__":
    main()

"""Privately review the frozen Prolific pre-election recontact crosstabs."""

import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PINS = {
    "followup-results.xlsx": "0034b1c2f5447defecbb5891babfe3df18ce581e7b4ae519dc21e6057fb45fd1",
    "october-results.xlsx": "07b03761a76e2207110e932fa1ad5379f9898549d980207e7b2e13da50341cd0",
    "followup-questionnaire.pdf": "d3372450b627740028c7b16769b25e4c3f7b7a93c9bf9a20c45830c340225e1b",
    "october-questionnaire.pdf": "3f0bcfa53432242e20f03f3e036ec2bc4458353ab08160f9c62772dca10172aa",
}
FOLLOWUP_BASE = (
    "Base: follow-up respondents (weighted to represent US adult citizens who had not "
    "voted by October 22) (n = 1,131 unweighted). Weighted for non-response. "
    "\u00b1 rows: 95% bootstrap margin of error."
)
RV_BASE = (
    "Base: registered voters: follow-up respondents who say they are registered, plus "
    "the people who had voted by October (their October answers) (n = 1,090 unweighted). "
    "Weighted for non-response. \u00b1 rows: 95% bootstrap margin of error."
)
LIKE_ANSWERS = (
    "Definitely will vote %", "Probably will vote %", "Maybe / 50-50 %",
    "Probably will not vote %", "Definitely will not vote %",
    "I have already voted %", "I am not eligible to vote %",
)
HOUSE_ANSWERS = (
    "The Democratic Party candidate %", "The Republican Party candidate %",
    "Other %", "Not sure (after lean question) %", "I would not vote %",
)
TABLES = {
    "01 LikeVote": (FOLLOWUP_BASE, 1131, LIKE_ANSWERS),
    "03 GenBallot RV": (RV_BASE, 1090, HOUSE_ANSWERS),
    "05 GenBallot resp": (FOLLOWUP_BASE, 1131, HOUSE_ANSWERS),
}
UNSUPPORTED = (
    "completed_november_turnout", "population_switchers", "apparent_absence",
    "original_2024_coalition_rates", "demographic_turnout", "causal_persuasion",
    "total_swing_shares", "state_or_local_estimates",
)


def number(value, *, count=False, percentage=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Missing or nonnumeric native cell")
    if not math.isfinite(value) or value < 0:
        raise ValueError("Invalid negative or nonfinite native cell")
    if count and (value != int(value) or value == 0):
        raise ValueError("Invalid native base")
    if percentage and value > 100:
        raise ValueError("Invalid native percentage")
    return value


def review(tables):
    selected = []
    for name, (base, total, answers) in TABLES.items():
        cells = tables[name]
        if cells.get((3, 1)) != base or cells.get((7, 2)) != total:
            raise ValueError("Wrong respondent population or native total")
        for column, label in enumerate(
            ("Harris", "Trump", "Other candidate", "Did not vote / not eligible", "Rather not say"),
            6,
        ):
            if cells.get((6, column)) != label:
                raise ValueError("Ambiguous native prior-choice column")
        if cells.get((7, 1)) != "Unweighted n" or cells.get((8, 1)) != "Weighted n":
            raise ValueError("Missing native support headers")
        if cells.get((9, 1)) != "Effective n":
            raise ValueError("Missing native effective-base header")
        groups = []
        for column, label in ((6, "Harris"), (7, "Trump")):
            rows = []
            for offset, answer in enumerate(answers):
                row = 10 + 2 * offset
                if cells.get((row, 1)) != answer or str(cells.get((row + 1, 1))).strip() != "\u00b1":
                    raise ValueError("Missing or reordered native response or margin")
                rows.append({
                    "native_response": answer,
                    "weighted_percentage": number(cells.get((row, column)), percentage=True),
                    "publisher_bootstrap_margin_pp": number(cells.get((row + 1, column))),
                })
            mass_difference = math.fsum(item["weighted_percentage"] for item in rows) - 100
            if abs(mass_difference) > 1e-7:
                raise ValueError("Full native answer distribution does not reconcile")
            groups.append({
                "recalled_2024_choice": label,
                "unweighted_n": number(cells.get((7, column)), count=True),
                "publisher_rounded_weighted_n": number(cells.get((8, column)), count=True),
                "publisher_weight_variation_effective_n": number(cells.get((9, column)), count=True),
                "responses": rows,
                "signed_percentage_sum_minus_100": mass_difference,
            })
        selected.append({"native_sheet": name, "native_population": base, "groups": groups})
    for index in (0, 1):
        first, second = selected[0]["groups"][index], selected[2]["groups"][index]
        for field in ("unweighted_n", "publisher_rounded_weighted_n",
                      "publisher_weight_variation_effective_n"):
            if first[field] != second[field]:
                raise ValueError("Same-respondent crosstab support differs")
    return {
        "status": "private_pre_election_recontact_crosstabs_not_completed_turnout",
        "public_release_qualified": False,
        "field_period": ["2026-10-28", "2026-11-02"],
        "original_field_period": ["2026-10-21", "2026-10-22"],
        "original_adult_citizens": 1518,
        "reinvited": 1398, "followup_respondents": 1131,
        "october_already_voters_not_reinvited": 120,
        "tables": selected,
        **{field: None for field in UNSUPPORTED},
        "limits": [
            "The 120 October already-voters retain old answers in the RV table, but are absent from both follow-up-only tables.",
            "Follow-up-only percentages are not estimates for all former Trump or Harris voters.",
            "Participation and candidate choice are self-reported, not administratively validated.",
            "The two follow-up-only questions have matched respondents, not an exported turnout-by-choice joint table.",
            "Do not multiply the separate turnout and House-choice response distributions.",
            "The 2024 nonvote and ineligibility column combines distinct historical states; it is not a returning-voter identity.",
            "Generic district House responses include leaners and mix intentions with reported early choices, not named-candidate returns.",
            "October weights rake to historical presidential choice and other targets; recontact weights adjust attrition.",
            "Do not apply national voter totals or reweight the current electorate to its 2024 coalition shares.",
            "The separate headline likely-voter model fixes turnout at 47% of adult citizens; it is not observed turnout.",
            "Conditional margins are supplied bootstrap margins, not an overall poll margin assigned to subgroups.",
            "The 500-bootstrap procedure covers sampling and weighting variability, not all model, selection, nonresponse or reporting error.",
            "Rounded weighted bases cannot reconstruct exact weighted cell counts; marginal errors cannot be combined as a joint interval.",
            "No individual records, fine cells, state allocations, original-coalition absence or fresh survey refit are released.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT in args.output.resolve().parents:
        raise ValueError("Use a new private output outside the repository")
    for name, expected in SOURCE_PINS.items():
        if hashlib.sha256((args.source_dir / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen source changed: {name}")
    import openpyxl

    book = openpyxl.load_workbook(
        args.source_dir / "followup-results.xlsx", read_only=True, data_only=True)
    try:
        tables = {
            name: {(row_index, column): value
                   for row_index, row in enumerate(book[name].iter_rows(values_only=True), 1)
                   for column, value in enumerate(row, 1) if value is not None}
            for name in TABLES
        }
    finally:
        book.close()
    result = review(tables)
    result["source_pins"] = SOURCE_PINS
    with args.output.open("x") as target:
        target.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"tables": len(result["tables"]), "public_release_qualified": False,
                      "output": str(args.output)}))

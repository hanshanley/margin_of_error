"""Scale matched demographic joint tables, without inventing historical group baselines."""

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


survey = load("demographic_survey", "review-cnn-voter-poll.py")
turnout = load("demographic_turnout", "estimate-preliminary-coalitions.py")
GROUPS = {
    20: (11001, "Gender", "Male", "MEN"),
    21: (11001, "Gender", "Female", "WOM"),
    5: (260, "Race", "White", "WHT"),
    6: (260, "Race", "Black", "BLK"),
    7: (260, "Race", "Latino", "HIS"),
    45: (1974, "Education by race", "White voters, college degree", "WCol"),
    46: (1974, "Education by race", "White voters, no degree", "WNoC"),
    53: (159, "Age", "18-29", "UNDER30"),
    54: (1949, "Age", "18-44", "18TO44"),
    55: (159, "Age", "65 or older", "65PLUS"),
}
QUALIFIED = "conditional_matched_demographic_count"
DATA = "data/participation-demographic-counts/20261107-01"
UF = "data/participation-estimated-coalitions/20261107-01"
PUBLIC = "public/participation-demographic-counts/20261107-01"


def collect(snapshot, cache):
    result = copy.deepcopy(snapshot)
    for item in result["sources"]:
        if "selected_native_data" not in item:
            continue
        entry = item["configuration_entry"]
        raw = (cache / Path(survey.source_path(entry)).name).read_bytes()
        if survey.select_source(raw, entry) != item:
            raise ValueError("Frozen native source differs from the original selected snapshot")
        subset = entry["subsetNumber"]
        ids = ({group[0] for group in GROUPS.values()} if subset == 0 else
               {GROUPS[subset][0]} if subset in GROUPS else set())
        released = all((item["selected_native_data"].get(key) or {}).get("exitPollsReleased") is True
                       for key in ("exitPollEmbargo", "raceEmbargo"))
        item["selected_demographic_questions"] = [{
            key: question.get(key) for key in ("mxId", "question", "onDigital", "isDemographic")
        } | {"answers": [{key: answer.get(key) for key in ("answer", "totalPercentage")}
                         for answer in question["answers"]]}
            for question in json.loads(raw).get("questions", [])
            if released and question.get("mxId") in ids]
    result["demographic_selection"] = {
        "original_snapshot_unchanged": True, "native_files_refetched": False,
        "selected_fields": "Direct demographic population percentages and subgroup identity self-cells",
        "mode_population_share_identified": False,
    }
    return result


def question(item, mxid, label):
    matches = [q for q in item.get("selected_demographic_questions", []) if q["mxId"] == mxid]
    if not matches:
        return None
    if (len(matches) != 1 or matches[0]["question"] != label
            or matches[0]["onDigital"] is not True or matches[0]["isDemographic"] is not True):
        raise ValueError("Ambiguous, unpublished or redefined demographic question")
    answers = matches[0]["answers"]
    if len({answer["answer"] for answer in answers}) != len(answers):
        raise ValueError("Duplicate demographic answer")
    for answer in answers:
        survey.percent(answer["totalPercentage"])
    return matches[0]


def answer(q, label):
    values = [survey.percent(a["totalPercentage"]) for a in q["answers"] if a["answer"] == label]
    return values[0] if values else None


def population_match(main, group):
    entry = group["configuration_entry"]
    mxid, label, category, short = GROUPS[entry["subsetNumber"]]
    parent, subset = main["selected_native_data"], group["selected_native_data"]
    if (main["configuration_entry"]["subsetNumber"] != 0
            or any(main["configuration_entry"][key] != entry[key]
                   for key in ("stateAbbr", "raceTypeCode"))
            or any(parent[key] != subset[key] for key in
                   ("electionDate", "electionType", "raceType", "jurisdictionType", "state",
                    "timestamp", "stage", "candidates"))):
        raise ValueError("Demographic population and conditional table scopes or revisions differ")
    if (not parent["hasData"] or any(
            (parent.get(key) or {}).get("exitPollsReleased") is not True
            for key in ("exitPollEmbargo", "raceEmbargo"))):
        return {"status": "withheld_parent_not_released"}
    if subset["subset"]["shortName"] != short:
        return {"status": "withheld_subgroup_identity_mismatch"}
    all_question, self_question = question(main, mxid, label), question(group, mxid, label)
    if all_question is None or self_question is None:
        return {"status": "withheld_missing_population_question"}
    share = answer(all_question, category)
    if share is None:
        return {"status": "withheld_suppressed_population_share"}
    if answer(self_question, category) != 100:
        return {"status": "withheld_subgroup_identity_mismatch"}
    shares = [survey.percent(a["totalPercentage"]) for a in all_question["answers"]]
    if any(value is None for value in shares):
        return {"status": "withheld_incomplete_population_partition"}
    difference = 100 - sum(shares)
    if abs(difference) > len(shares) / 2:
        return {"status": "withheld_unreconciled_population_partition"}
    return {
        "status": "matched_published_population",
        "question_id": mxid, "question": label, "answer": category,
        "group_share_pct_of_current_electorate": share,
        "population_partition_signed_rounding_difference_pct": difference,
        "population_source_url": main["source_url"],
        "population_source_sha256": main["source_sha256"],
        "population_source_timestamp": parent["timestamp"],
        "subgroup_identity_self_percentage": 100,
    }


def calculate(row, population, total):
    if (row["status"] != "published_joint_question_reviewed"
            or population["status"] != "matched_published_population"
            or row["subset"]["sub"] not in GROUPS):
        raise ValueError("Unqualified demographic count")
    g = population["group_share_pct_of_current_electorate"]
    if survey.percent(g) is None:
        raise ValueError("Missing group population")
    n = turnout.math.finite(total, "current electorate")
    if n <= 0:
        raise ValueError("Invalid current electorate")
    group_total = n * g / 100
    composition = {}
    for prior in ("D", "R", "O", "N"):
        source = row["joint_question_rows"][prior]
        share = survey.percent(source["prior_choice_share_pct"])
        if share is None:
            raise ValueError("Suppressed prior composition")
        count = group_total * share / 100
        composition[prior] = {
            "share_pct_of_current_group": share, "estimated_current_group_count": count,
            "reported_current_choice_counts": {
                party: None if (p := survey.percent(source["current_choice_pct_within_prior_choice"][party]))
                is None else count * p / 100 for party in ("D", "R")},
        }
    if (not 98 <= sum(c["share_pct_of_current_group"] for c in composition.values()) <= 102
            or sum(c["share_pct_of_current_group"] for c in composition.values())
            != row["reported_composition_sum_pct"]):
        raise ValueError("Unreconciled prior composition")
    scenarios = []
    for scale in (.95, 1, 1.05):
        for transfer in (-2, 0, 2):
            flows = {}
            for prior, other, sign in (("R", "D", 1), ("D", "R", -1)):
                source = row["joint_question_rows"][prior]
                q = source["prior_choice_share_pct"] + sign * transfer
                p = source["current_choice_pct_within_prior_choice"][other]
                flows[prior] = None if not 0 <= q <= 100 or p is None else group_total * scale * q / 100 * p / 100
            scenarios.append({"total_scale": scale, "harris_to_trump_transfer_pp": transfer,
                              "reported_opposite_party_counts": flows})
    rounding = {}
    for prior, other in (("R", "D"), ("D", "R")):
        source = row["joint_question_rows"][prior]
        q, p = source["prior_choice_share_pct"], source["current_choice_pct_within_prior_choice"][other]
        rounding[prior] = None if p is None else {
            "lower": n * max(0, g - .5) / 100 * max(0, q - .5) / 100 * max(0, p - .5) / 100,
            "upper": n * min(100, g + .5) / 100 * min(100, q + .5) / 100 * min(100, p + .5) / 100,
        }
    return {
        "state_code": row["state_code"], "contest_code": row["contest_code"], "subset": row["subset"],
        "status": QUALIFIED, "population_match": population, "estimated_electorate_total": n,
        "population_scope": "50_states_excluding_DC" if row["state_code"] == "US" else "state",
        "estimated_current_group_count": group_total,
        "joint_source_url": row["source_url"], "joint_source_sha256": row["source_sha256"],
        "joint_source_timestamp": row["source_timestamp"],
        "composition": composition,
        "signed_prior_composition_rounding_difference_pct": 100 - row["reported_composition_sum_pct"],
        "rounding_only_opposite_choice_envelopes": rounding, "sensitivity_scenarios": scenarios,
        "original_2024_group_coalition_baseline": None, "group_dropoff_estimate": None,
        "demographic_turnout_rate": None, "share_of_total_swing": None,
        "design_confidence_interval": None,
    }


def estimate(snapshot, totals):
    review = survey.review_snapshot(snapshot)
    items = {(x["configuration_entry"]["stateAbbr"], x["configuration_entry"]["raceTypeCode"],
              x["configuration_entry"]["subsetNumber"]): x for x in snapshot["sources"]}
    estimates, dispositions = [], []
    for row in review["tables"]:
        code, contest, sub = row["state_code"], row["contest_code"], row["subset"]["sub"]
        if sub == 0:
            continue
        disposition = {key: row[key] for key in ("state_code", "contest_code", "subset")}
        disposition["joint_status"] = row["status"]
        if sub not in GROUPS:
            disposition["status"] = "withheld_no_matched_population_question"
        elif row["status"] != "published_joint_question_reviewed":
            disposition["status"] = row["status"]
        else:
            main, item = items.get((code, contest, 0)), items[(code, contest, sub)]
            if main is None or "selected_native_data" not in main:
                match = {"status": "withheld_parent_not_acquired"}
            else:
                match = population_match(main, item)
            disposition["status"] = match["status"]
            if match["status"] == "matched_published_population":
                if code == "US":
                    if contest != "HG":
                        raise ValueError("National demographic scope must be House")
                    n = sum(totals[state]["ballots"] for state in survey.CODES if state != "DC")
                    if n != totals["US"]["ballots"] - totals["DC"]["ballots"]:
                        raise ValueError("National population mismatch")
                else:
                    if code == "DC" or contest not in ("GG", "SG"):
                        raise ValueError("Unqualified state demographic contest")
                    n = totals[code]["ballots"]
                estimates.append(calculate(row, match, n))
                disposition["status"] = QUALIFIED
        dispositions.append(disposition)
    return {
        "status": "conditional_current_demographic_counts_not_validated_transitions",
        "estimates": estimates, "source_group_dispositions": dispositions,
        "jurisdictions": [{
            "state_code": code, "native_turnout": totals[code],
            "qualified_group_comparisons": sum(r["state_code"] == code for r in estimates),
            "next_evidence": "Acquire original2024 group-coalition baselines and linked turnout; qualify missing joint cells and actual local cohorts",
        } for code in survey.CODES],
        "native_national_turnout": totals["US"],
        "national_50_state_estimated_turnout": totals["US"]["ballots"] - totals["DC"]["ballots"],
        "assumptions_and_limits": [
            "N26*g*q*p uses the actual same-contest published group population share g and within-group joint prior/current choices. It is not a product of disconnected preference marginals or a national-to-state allocation.",
            "The reference assumes demographic shares and conditional response composition apply to all estimated ballot-casters. Exact response selection remains unresolved.",
            "UF Initial Estimate totals are preliminary, not observed/certified counts. Some current choices are retained pre-election choices after failed recontact.",
            "Groups are source-defined current2026 demographics, not frozen2024 cohorts; aging, education and residence changes are not identified.",
            "No2024 demographic coalition baselines are supplied. Group drop-off, original-coalition percentages, demographic turnout rates, causal persuasion and share-of-total-swing remain unavailable.",
            "N means reported no2024 presidential vote, not all-race nonvoting, first-ever voting, eligibility entry or identified returning voters.",
            "Suppressed/null/-1 cells stay unavailable. No reverse-conditional recovery, inferred intersections, renormalization or forced2024coalition calibration.",
            "The18-44 group uses the exact question1949, not summed rounded18-29/30-44 cells. Age groups overlap; race and White-education groups overlap. Do not add them, offices or national/state estimates.",
            "National House uses50states excluding unsampledDC; complete nativeUS/DC rows remain intact.",
            "Rounding envelopes allow half-point rounding in g,q,p. Total+-5percent and balanced recall+-2pp scenarios are stress assumptions, not design confidence intervals. Marginal endpoints cannot be added.",
            "No matched published early/ElectionDay group fraction is identified here; respondent fractions are not population weights.",
            "No county/precinct allocation, individual records, personal scores or restrictedNORC inputs.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect-cache", type=Path)
    parser.add_argument("--snapshot", type=Path, default=Path(DATA) / "selected-source-tables.json")
    parser.add_argument("--output", type=Path, default=Path(PUBLIC) / "demographic-current-counts.json")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to overwrite an existing versioned output")
    snapshot = json.loads(args.snapshot.read_text())
    if args.collect_cache:
        result = collect(snapshot, args.collect_cache)
    else:
        totals = turnout.read_turnout(Path(UF) / "Turnout_2026G_v0.2.csv", Path(UF) / "Turnout_2026G_v0.1_doc.txt")
        result = estimate(snapshot, totals)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":"), ensure_ascii=True) + "\n")
    print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size,
                      "estimates": len(result.get("estimates", []))}))

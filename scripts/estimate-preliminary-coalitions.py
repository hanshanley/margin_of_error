"""Scale qualified joint surveys using separately labeled preliminary turnout estimates."""

import argparse
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re


spec = importlib.util.spec_from_file_location(
    "coalition_math", Path(__file__).with_name("estimate-survey-coalition-absence.py"))
math = importlib.util.module_from_spec(spec)
spec.loader.exec_module(math)
CSV_SHA256 = "eef37c0606cc1406e76b84bae2216c592e74e6b8cf5034d8d0733f3ab942cf2b"
DOC_SHA256 = "403fee549826f57d620256fb33d42ffd67e19360bc611330a6ce9f01a79b8dcd"
REVIEWED_CSV_VERSIONS = {
    "20261107-01": CSV_SHA256,
    "20261107T055406Z": "ba4d9231f4da8daee738aec99c89101120132e9f39192339e9861af829b6f434",
}


def parse_rows(rows):
    result = {}
    for row in rows:
        code = row["STATE_ABV"]
        literal = row["TOTAL_BALLOTS_COUNTED"]
        if (code not in math.CODES + ["US"] or code in result
                or row["SOURCE"] != "Initial Estimate"
                or not re.fullmatch(r"(?:[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", literal)):
            raise ValueError("Invalid, duplicate or unreviewed preliminary turnout row")
        result[code] = {"ballots": int(literal.replace(",", "")), "native_record": dict(row)}
    if set(result) != set(math.CODES + ["US"]):
        raise ValueError("Preliminary totals must cover all 50 states, DC and the US")
    if sum(result[code]["ballots"] for code in math.CODES) != result["US"]["ballots"]:
        raise ValueError("Preliminary state totals do not reconcile to the native national row")
    return result


def read_turnout(csv_path, documentation, source_version="20261107-01"):
    raw, doc = csv_path.read_bytes(), documentation.read_bytes()
    if (source_version not in REVIEWED_CSV_VERSIONS
            or hashlib.sha256(raw).hexdigest() != REVIEWED_CSV_VERSIONS[source_version]
            or hashlib.sha256(doc).hexdigest() != DOC_SHA256):
        raise ValueError("Changed or unreviewed preliminary turnout source; review a new version")
    return parse_rows(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))


def national_inputs(totals, baselines):
    states = [code for code in math.CODES if code != "DC"]
    baseline = {key: sum(baselines[code][key] for code in states)
                for key in ("D", "R", "all_presidential_votes")}
    turnout = {
        **totals["US"], "ballots": sum(totals[code]["ballots"] for code in states),
        "population_scope": "50_states_excluding_DC_unsampled_by_SSRS",
        "native_national_ballots": totals["US"]["ballots"],
        "excluded_dc_ballots": totals["DC"]["ballots"],
        "derivation": "Sum of the 50 state estimates; equals the native national row minus the native DC row. Not a geographic allocation.",
    }
    return baseline, turnout


def calculate(table, baseline, turnout):
    code = table["state_code"]
    if (table["status"] != "published_joint_question_reviewed" or table["subset"]["sub"] != 0
            or code not in math.CODES + ["US"]
            or turnout["native_record"]["STATE_ABV"] != code
            or turnout["native_record"]["SOURCE"] != "Initial Estimate"
            or (code == "US" and (table["contest_code"] != "HG"
                or turnout.get("population_scope") != "50_states_excluding_DC_unsampled_by_SSRS"))
            or (code != "US" and table["contest_code"] not in ("GG", "SG"))):
        raise ValueError("Unqualified joint survey scope")
    rows = table["joint_question_rows"]
    total = turnout["ballots"]
    composition = {}
    for prior in ("D", "R", "O", "N"):
        row = rows[prior]
        share = math.finite(row["prior_choice_share_pct"], "composition")
        if not 0 <= share <= 100:
            raise ValueError("Invalid recalled presidential composition")
        count = total * share / 100
        choices = row["current_choice_pct_within_prior_choice"]
        flows = {}
        for party in ("D", "R"):
            value = choices.get(party)
            if value is not None and not 0 <= math.finite(value, "conditional choice") <= 100:
                raise ValueError("Invalid conditional choice")
            flows[party] = None if value is None else count * value / 100
        composition[prior] = {
            "reported_share_pct_of_current_electorate": share,
            "conditional_current_electorate_count": count,
            "reported_current_choice_counts": flows,
        }
    composition_sum = sum(row["reported_share_pct_of_current_electorate"] for row in composition.values())
    if not 98 <= composition_sum <= 102 or composition_sum != table["reported_composition_sum_pct"]:
        raise ValueError("Unqualified or changed joint composition")
    reference, rounding = {}, {}
    for prior, other in (("R", "D"), ("D", "R")):
        row = rows[prior]
        share, switched = row["prior_choice_share_pct"], row["current_choice_pct_within_prior_choice"][other]
        reference[prior] = math.coalition(baseline[prior], total, share, switched)
        rounding[prior] = math.rounding_envelope(baseline[prior], total, share, switched)
    scenarios = []
    for scale in (.95, 1, 1.05):
        for transfer in (-2, 0, 2):
            coalitions = {}
            for prior, other, sign in (("R", "D", 1), ("D", "R", -1)):
                row = rows[prior]
                share = row["prior_choice_share_pct"] + sign * transfer
                if not 0 <= share <= 100:
                    coalitions = None
                    break
                coalitions[prior] = math.coalition(
                    baseline[prior], total * scale, share,
                    row["current_choice_pct_within_prior_choice"][other])
            scenarios.append({"estimated_total_scale": scale,
                              "harris_to_trump_composition_transfer_pp": transfer,
                              "coalitions": coalitions})
    return {
        "state_code": code, "contest_code": table["contest_code"],
        "status": "preliminary_estimated_population_conditional_scenario_not_measured_dropoff",
        "official_2024_baseline": baseline,
        "preliminary_turnout": turnout,
        "survey_source_url": table["source_url"],
        "survey_source_sha256": table["source_sha256"],
        "survey_source_timestamp": table["source_timestamp"],
        "reported_joint_rows": rows,
        "reference": reference, "rounding_only_envelopes": rounding,
        "current_electorate_composition": composition,
        "signed_composition_rounding_difference_pct": 100 - composition_sum,
        "signed_composition_rounding_difference_is_not_a_person_count": True,
        "sensitivity_scenarios": scenarios,
    }


def run(workbook, csv_path, documentation, survey_path, methodology, output,
        source_version="20261107-01"):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Refusing to overwrite an existing preliminary analysis")
    totals = read_turnout(csv_path, documentation, source_version)
    baseline = math.fec_baselines(workbook)
    baseline["US"], totals["US"] = national_inputs(totals, baseline)
    tables = json.loads(survey_path.read_text())["tables"]
    main = [row for row in tables if row["subset"]["sub"] == 0]
    keys = [(row["state_code"], row["contest_code"]) for row in main]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate all-voter survey scope")
    estimates = [calculate(row, baseline[row["state_code"]], totals[row["state_code"]])
                 for row in main if row["status"] == "published_joint_question_reviewed"]
    state_estimates = [row for row in estimates if row["state_code"] != "US"]
    national = [row for row in estimates if row["state_code"] == "US"]
    if len(national) != 1:
        raise ValueError("Expected the separately qualified national House table")
    result = {
        "status": "preliminary_estimated_total_scenarios_not_validated_participation",
        "state_comparisons": state_estimates, "national_house_comparison": national[0],
        "source_methodology": json.loads(methodology.read_text()),
        "jurisdictions": [{
            "state_code": code, "preliminary_turnout": totals[code],
            "has_official_2024_baseline": True,
            "conditional_contests": [r["contest_code"] for r in state_estimates if r["state_code"] == code],
            "all_voter_joint_table_dispositions": [
                {"contest_code": row["contest_code"], "status": row["status"]}
                for row in main if row["state_code"] == code],
            "next_evidence": (
                "Validate turnout estimates, joint-response scope and linked participation"
                if any(r["state_code"] == code for r in state_estimates)
                else "Acquire an applicable qualified state-specific joint choice table; national allocation is not allowed"),
        } for code in math.CODES],
        "assumptions_and_limits": [
            "UF estimates total ballots; every native source row says Initial Estimate. These are not official observed or certified counts.",
            "The reference additionally assumes each contest's recalled-choice composition represents all state ballot-casters; exact response selection remains unresolved.",
            "Some current choices are retained pre-election choices after failed recontact; this is not universal completed-vote or administrative choice validation.",
            "Returning=N26*q; reported opposite-party choices=N26*q*p; apparent absence=T24-N26*q. FEC T24 is official; N26 and the transitions are conditional estimates.",
            "Apparent absence includes migration, mortality, recall and population-estimation error, not only staying home. Negative residuals are retained.",
            "Current N composition means reported no 2024 presidential vote, not no ballot in any 2024 contest, first-time voting, eligibility entry or identified returning voters.",
            "Current N/O counts equal N26 times their published composition. D/R choice flows use only published conditional cells; suppressed choices remain null.",
            "Composition is not renormalized; its signed difference from100 is a rounding diagnostic, not identified missing people.",
            "Count scales0.95/1/1.05 and balanced recall transfers+-2pp are symmetric stress assumptions, not estimated missing ballots or confidence intervals.",
            "Half-point rounding envelopes are marginal, not confidence intervals. These scenarios do not exhaust sampling, recall or population uncertainty.",
            "SSRS did not sample DC. National House uses the sum of50state turnout estimates and the official50state prior coalitions, excluding DC from both years. The entire native national and DC rows are retained; this is scope matching, not geographic allocation.",
            "Never add offices, national and state results, or marginal endpoints.",
            "No state-to-demographic, county or precinct allocation; no causal persuasion or share-of-overall-swing estimate. No reweighting2026to2024Trump/Harris shares.",
        ],
        "inputs": [{"file": str(path.resolve().relative_to(Path(__file__).resolve().parents[1])),
                    "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                   for path in (workbook, csv_path, documentation, survey_path, methodology)],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "estimated-coalition-scenarios.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"states": len({r["state_code"] for r in state_estimates}),
                      "state_contests": len(state_estimates), "national_house_separate": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("workbook", "turnout-csv", "documentation", "survey-review", "methodology", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--turnout-source-version", choices=REVIEWED_CSV_VERSIONS,
                        default="20261107-01")
    args = parser.parse_args()
    run(args.workbook, args.turnout_csv, args.documentation, args.survey_review, args.methodology,
        args.output, args.turnout_source_version)

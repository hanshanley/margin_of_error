"""Calculate explicitly conditional coalition switching and apparent-absence scenarios."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


CODES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def fec_baselines(path):
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook.findall("s:sheets/s:sheet", NS)
        if len(sheets) != 1 or sheets[0].get("name") != "OFFICIAL 2024 PRES GE RESULTS":
            raise ValueError("Wrong official election workbook")
        strings = ["".join(item.itertext()) for item in
                   ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        rows = []
        for row in ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).findall("s:sheetData/s:row", NS):
            cells = {}
            for cell in row:
                value = cell.find("s:v", NS)
                if value is not None:
                    column = "".join(char for char in cell.get("r") if char.isalpha())
                    cells[column] = strings[int(value.text)] if cell.get("t") == "s" else value.text
            rows.append(cells)
    if any(rows[0].get(column) != label for column, label in
           [("A", "STATE"), ("M", "HARRIS"), ("Y", "TRUMP"), ("AE", "TOTAL VOTES")]):
        raise ValueError("Wrong presidential candidate headers")
    result = {}
    for row in rows[1:]:
        state = row.get("A")
        if state not in CODES:
            continue
        if state in result:
            raise ValueError("Duplicate statewide presidential total")
        d, r, total = (int(row[key]) for key in ("M", "Y", "AE"))
        if min(d, r) <= 0 or d + r > total:
            raise ValueError("Invalid official presidential totals")
        result[state] = {"D": d, "R": r, "all_presidential_votes": total}
    if set(result) != set(CODES):
        raise ValueError("Official baselines must cover all 50 states and DC")
    totals = [row for row in rows if row.get("A") == "Total:"]
    if len(totals) != 1 or any(
            sum(row[key] for row in result.values()) != int(totals[0][column])
            for key, column in [("D", "M"), ("R", "Y"), ("all_presidential_votes", "AE")]):
        raise ValueError("State presidential totals do not reconcile to the official national row")
    return result


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return value


def coalition(prior_total, current_total, prior_share, switched_pct):
    if finite(prior_total, "prior total") <= 0 or finite(current_total, "current total") < 0:
        raise ValueError("Invalid population total")
    if not 0 <= finite(prior_share, "prior share") <= 100:
        raise ValueError("Invalid prior share")
    if not 0 <= finite(switched_pct, "switching percentage") <= 100:
        raise ValueError("Invalid switching percentage")
    returning = current_total * prior_share / 100
    switchers = returning * switched_pct / 100
    absent = prior_total - returning
    return {
        "returning_count": returning,
        "reported_switcher_count": switchers,
        "apparent_absence_count": absent,
        "returning_pct_of_original_coalition": 100 * returning / prior_total,
        "reported_switchers_pct_of_current_electorate": prior_share * switched_pct / 100,
        "reported_switchers_pct_of_original_coalition": 100 * switchers / prior_total,
        "apparent_absence_pct_of_original_coalition": 100 * absent / prior_total,
        "infeasible_as_closed_original_coalition": returning > prior_total,
    }


def rounding_envelope(prior_total, current_total, share, switched):
    if any(value != int(value) for value in (share, switched)):
        return None
    low_share, high_share = max(0, share - .5), min(100, share + .5)
    low_switch, high_switch = max(0, switched - .5), min(100, switched + .5)
    low = coalition(prior_total, current_total, low_share, low_switch)
    high = coalition(prior_total, current_total, high_share, high_switch)
    return {
        "status": "marginal_whole_percentage_rounding_only_not_confidence_interval",
        "returning_count": [low["returning_count"], high["returning_count"]],
        "reported_switcher_count": [low["reported_switcher_count"], high["reported_switcher_count"]],
        "apparent_absence_count": [high["apparent_absence_count"], low["apparent_absence_count"]],
    }


def estimate(table, baseline, reporting):
    if (table["state_code"] != reporting["state_code"] or table["subset"]["sub"] != 0
            or table["status"] != "published_joint_question_reviewed"
            or table["state_code"] not in CODES or reporting["status"] != "reported"):
        raise ValueError("Unqualified state, subgroup, joint table or turnout row")
    if reporting.get("quality"):
        raise ValueError("Turnout source has unresolved quality flags")
    rows = table["joint_question_rows"]
    output = {"state_code": table["state_code"], "contest_code": table["contest_code"],
              "status": "conditional_universe_assumption_not_validated_dropoff",
              "survey_source_url": table["source_url"], "survey_source_sha256": table["source_sha256"],
              "survey_source_timestamp": table["source_timestamp"],
              "survey_source_reported_respondents": table["source_reported_respondents"],
              "reported_joint_rows": rows,
              "reported_prior_composition_sum_pct": table["reported_composition_sum_pct"],
              "turnout_source": reporting, "official_2024_baseline": baseline,
              "reference": {}, "rounding_only_envelopes": {}, "sensitivity_scenarios": [],
              "response_scope_sensitivity": []}
    for prior, other in [("R", "D"), ("D", "R")]:
        row = rows[prior]
        share, switched = row["prior_choice_share_pct"], row["current_choice_pct_within_prior_choice"][other]
        output["reference"][prior] = coalition(
            baseline[prior], reporting["ballots"], share, switched)
        same = row["current_choice_pct_within_prior_choice"].get(prior)
        returning = output["reference"][prior]["returning_count"]
        output["reference"][prior].update(
            reported_same_party_count=None if same is None else returning * same / 100,
            signed_unshown_current_choice_count=None if same is None else returning * (100 - same - switched) / 100)
        output["rounding_only_envelopes"][prior] = rounding_envelope(
            baseline[prior], reporting["ballots"], share, switched)
    for unrepresented_pct in (0, 2.5, 5):
        unknown = reporting["ballots"] * unrepresented_pct / 100
        covered = reporting["ballots"] - unknown
        scenario = {"assumed_unrepresented_ballot_caster_pct": unrepresented_pct,
                    "marginal_coalition_envelopes": {}}
        for prior, other in [("R", "D"), ("D", "R")]:
            row = rows[prior]
            returning = covered * row["prior_choice_share_pct"] / 100
            switched = returning * row["current_choice_pct_within_prior_choice"][other] / 100
            scenario["marginal_coalition_envelopes"][prior] = {
                "returning_count": [returning, returning + unknown],
                "reported_switcher_count": [switched, switched + unknown],
                "apparent_absence_count": [baseline[prior] - returning - unknown, baseline[prior] - returning],
            }
        output["response_scope_sensitivity"].append(scenario)
    for turnout_scale in (1, 1.025, 1.05):
        for recall_transfer in (-2, 0, 2):
            scenario = {"current_ballot_count_scale": turnout_scale,
                        "harris_to_trump_composition_transfer_pp": recall_transfer, "coalitions": {}}
            for prior, other, sign in [("R", "D", 1), ("D", "R", -1)]:
                row = rows[prior]
                share = row["prior_choice_share_pct"] + sign * recall_transfer
                if not 0 <= share <= 100:
                    scenario["coalitions"] = None
                    break
                scenario["coalitions"][prior] = coalition(
                    baseline[prior], reporting["ballots"] * turnout_scale, share,
                    row["current_choice_pct_within_prior_choice"][other])
            output["sensitivity_scenarios"].append(scenario)
    return output


def run(workbook, snapshot, survey, output):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Refusing to overwrite an existing population review")
    baseline = fec_baselines(workbook)
    current = json.loads(snapshot.read_text())
    if current["election_date"] != "2026-11-03":
        raise ValueError("Wrong participation election")
    reporting = {row["state_code"]: row for row in current["reporting"]}
    if len(reporting) != len(current["reporting"]):
        raise ValueError("Duplicate statewide participation row")
    tables = json.loads(survey.read_text())["tables"]
    results = [estimate(table, baseline[table["state_code"]], reporting[table["state_code"]])
               for table in tables if table["state_code"] in reporting and table["subset"]["sub"] == 0
               and table["status"] == "published_joint_question_reviewed"]
    result = {
        "status": "conditional_survey_scaling_not_measured_dropoff",
        "estimates": results,
        "jurisdictions": [{
            "state_code": code, "has_official_2024_baseline": True,
            "has_existing_full_election_reported_ballots": code in reporting,
            "conditional_contests": [r["contest_code"] for r in results if r["state_code"] == code],
        } for code in CODES],
        "assumptions_and_limits": [
            "Reference assumes published prior-choice composition represents all 2026 state ballot-casters. Exact contest-specific response universes remain unverified.",
            "Published current-choice conditional responses include recall and retained pre-election choices, not validated individual ballots.",
            "Reported ballot totals are provisional snapshots, not certified final turnout.",
            "Apparent absence includes mortality, migration, recall error and incomplete reporting, not only staying home.",
            "Sensitivity transfers 2 composition points between Harris and Trump, preserving their sum; ballot scales of 1, 1.025 and 1.05 are assumptions, not estimated missing ballots.",
            "Response-scope sensitivity assumes 0, 2.5 or 5 percent of ballot-casters are unrepresented by the table. Their prior/current choices are unconstrained; coalition endpoints are marginal and cannot be jointly added.",
            "Unshown current-choice residuals are signed rounding diagnostics, not identified other-candidate votes or contest abstentions.",
            "Rounding envelopes allow half a percentage point in each whole-point cell, marginally; they exclude sampling and other errors and are not confidence intervals.",
            "Scenario ranges are not confidence intervals and do not exhaust sampling, recall or population uncertainty.",
            "Different offices share respondents and ballots; never sum their counts.",
            "A negative absence residual is an incompatibility diagnostic, never clamped to zero.",
            "No subgroup, county or precinct allocation; no share-of-overall-swing estimate.",
        ],
        "inputs": [{"role": role, "file": path.name, "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                   for role, path in [("official_2024_workbook", workbook),
                                      ("existing_participation_snapshot", snapshot),
                                      ("reviewed_joint_surveys", survey)]],
        "official_2024_source_url": "https://www.fec.gov/documents/5645/2024presgeresults.xlsx",
        "survey_methods_source_url": "https://ssrs.com/wp-content/uploads/The-Voter-Poll-by-SSRS-Methodology-Statement_Final.pdf",
        "survey_universe_review": "SSRS methods pages 6-7 target the estimated 2026 electorate in each state across voting modes. The public table's exact contest-specific response selection is not established.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "official-2024-baselines.json").write_text(json.dumps(baseline, indent=2) + "\n")
    (output / "conditional-coalition-scenarios.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"states": len({r["state_code"] for r in results}),
                      "contests": len(results), "conditional_scenarios": True,
                      "validated_dropoff_released": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True, type=Path)
    parser.add_argument("--participation-snapshot", required=True, type=Path)
    parser.add_argument("--survey-review", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.workbook, args.participation_snapshot, args.survey_review, args.output)

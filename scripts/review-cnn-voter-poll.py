"""Review configured state/contest joint survey tables without inventing drop-off."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request


SOURCE_ROOT = "https://politics.api.cnn.io/results/"
CONTESTS = {"HG": ("H", "G", "House"), "SG": ("S", "G", "Senate"),
            "GG": ("G", "G", "Governor"),
            "SP": ("S", "P", "Senate Special Election")}
CODES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
PRIOR = {"Harris": "D", "Trump": "R", "Another candidate": "O", "Did not vote": "N"}
FIELDS = ["ecKey", "electionDate", "electionType", "raceType", "jurisdictionType",
          "state", "subset", "titles", "respondents", "timestamp", "extractedAt",
          "hasData", "stage", "exitPollEmbargo", "raceEmbargo", "candidates"]


def percent(value):
    if value is None or value == -1:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid percentage type")
    if not 0 <= value <= 100:
        raise ValueError("Invalid percentage")
    return value


def source_path(entry):
    code = entry["raceTypeCode"]
    state = entry["stateAbbr"]
    subset = entry["subsetNumber"]
    if code not in CONTESTS or state not in CODES + ["US"]:
        raise ValueError("Unknown source contest or jurisdiction")
    if type(subset) is not int or subset < 0:
        raise ValueError("Invalid subset")
    expected = f"exit-poll/2026-{code}-{state}" + (f"-{subset}" if subset else "") + ".json"
    if entry["url"] != expected:
        raise ValueError("Source URL does not match configured scope")
    return expected


def select_source(raw, entry):
    path = source_path(entry)
    data = json.loads(raw)
    selected = {key: data.get(key) for key in FIELDS}
    released = data.get("hasData") and all(
        (data.get(key) or {}).get("exitPollsReleased") is True
        for key in ("exitPollEmbargo", "raceEmbargo"))
    selected["questions"] = [q for q in (data.get("questions") or [])
                             if released and q.get("mxId") == 10003
                             and q.get("onDigital") is True and not entry["isDisabled"]]
    return {"source_url": SOURCE_ROOT + path, "source_bytes": len(raw),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "configuration_entry": entry, "selected_native_data": selected}


def review_source(snapshot):
    entry = snapshot["configuration_entry"]
    path = source_path(entry)
    data = snapshot["selected_native_data"]
    race, stage, title = CONTESTS[entry["raceTypeCode"]]
    if (snapshot["source_url"] != SOURCE_ROOT + path
            or data["ecKey"] != Path(path).stem
            or data["electionDate"] != "2026-11-03"
            or (data["raceType"], data["electionType"]) != (race, stage)
            or data["titles"]["raceTitle"]["title"] != title
            or data["state"]["abbreviation"] != entry["stateAbbr"]
            or data["subset"]["sub"] != entry["subsetNumber"]
            or data["jurisdictionType"] != ("NR" if entry["stateAbbr"] == "US" else "SW")):
        raise ValueError("Source election/contest/geography/subgroup mismatch")
    row = {
        "state_code": entry["stateAbbr"], "contest_code": entry["raceTypeCode"],
        "contest_title": title, "subset": data["subset"], "source_url": snapshot["source_url"],
        "source_sha256": snapshot["source_sha256"], "source_timestamp": data["timestamp"],
        "source_reported_respondents": data["respondents"],
        "dropoff_estimate": None, "share_of_total_swing": None,
        "design_confidence_interval": None,
    }
    if entry["isDisabled"]:
        return dict(row, status="withheld_source_disabled")
    if (not data["hasData"] or any(
            not data[key] or data[key].get("exitPollsReleased") is not True
            for key in ("exitPollEmbargo", "raceEmbargo"))):
        return dict(row, status="withheld_not_released_or_no_data")
    questions = data["questions"]
    if not questions:
        return dict(row, status="withheld_missing_published_joint_question")
    if (len(questions) != 1 or questions[0].get("mxId") != 10003
            or questions[0].get("onDigital") is not True
            or questions[0]["question"].strip().lower() != "2024 presidential vote"):
        raise ValueError("Ambiguous joint question")
    candidates = {}
    party_ids = {"D": [], "R": []}
    for candidate in data["candidates"]:
        cid = candidate["candidateId"]
        if cid in candidates:
            raise ValueError("Duplicate candidate ID")
        candidates[cid] = candidate
        party = candidate["partyAbbreviation"]
        if party in party_ids:
            if candidate["partyName"] != {"D": "Democratic", "R": "Republican"}[party]:
                raise ValueError("Conflicting literal party fields")
            party_ids[party].append(cid)
    binary = all(len(ids) == 1 for ids in party_ids.values())
    joint = {}
    for answer in questions[0]["answers"]:
        prior = PRIOR[answer["answer"]]
        if prior in joint:
            raise ValueError("Duplicate prior-choice row")
        choices = {}
        for cell in answer["candidateAnswers"]:
            cid = cell["candidateId"]
            if cid not in candidates or cid in choices:
                raise ValueError("Unknown or duplicate current-choice ID")
            choices[cid] = percent(cell["percentage"])
        current = {party: choices.get(ids[0]) for party, ids in party_ids.items()} if binary else None
        if current and all(value is not None for value in current.values()) and sum(current.values()) > 101:
            raise ValueError("Current-choice percentages exceed rounded total")
        joint[prior] = {
            "prior_choice_share_pct": percent(answer["totalPercentage"]),
            "current_choice_pct_within_prior_choice": current,
        }
    if set(joint) != set(PRIOR.values()):
        raise ValueError("Incomplete selected joint question")
    shares = [item["prior_choice_share_pct"] for item in joint.values()]
    total = sum(shares) if all(value is not None for value in shares) else None
    if total is not None and total > 102:
        raise ValueError("Composition exceeds whole-point rounding tolerance")
    row.update(
        joint_question_rows=joint, reported_composition_sum_pct=total,
        reported_composition_difference_from_100_pct=None if total is None else 100 - total,
        composition_quality=("suppressed_composition" if total is None else
                             "below_four_row_rounding_tolerance" if total < 98 else
                             "within_four_row_rounding_tolerance"))
    if not binary:
        return dict(row, status="withheld_nonunique_literal_dem_rep_comparison")
    if entry["raceTypeCode"] == "SP":
        return dict(row, status="withheld_special_election_scope_review")
    if total is not None and total < 98:
        return dict(row, status="withheld_unreconciled_prior_composition")
    rd_share, dr_share = joint["R"]["prior_choice_share_pct"], joint["D"]["prior_choice_share_pct"]
    rd_pct = joint["R"]["current_choice_pct_within_prior_choice"]["D"]
    dr_pct = joint["D"]["current_choice_pct_within_prior_choice"]["R"]
    if any(value is None for value in (rd_share, dr_share, rd_pct, dr_pct)):
        return dict(row, status="withheld_suppressed_switching_cell")
    rd, dr = rd_share * rd_pct / 100, dr_share * dr_pct / 100
    return dict(row, status="published_joint_question_reviewed",
                arithmetic_from_rounded_percentages_per_100_current_group_voters={
                    "reported_trump_to_dem": round(rd, 6),
                    "reported_harris_to_rep": round(dr, 6),
                    "gross_reported_major_party_switchers": round(rd + dr, 6),
                    "net_reported_switching_toward_dem": round(rd - dr, 6)})


def review_snapshot(snapshot):
    rows = []
    seen = set()
    for item in snapshot["sources"]:
        entry = item["configuration_entry"]
        key = (entry["stateAbbr"], entry["raceTypeCode"], entry["subsetNumber"])
        if key in seen:
            raise ValueError("Duplicate configured table")
        seen.add(key)
        if "selected_native_data" in item:
            rows.append(review_source(item))
        else:
            source_path(entry)
            if item["status"] not in {
                    "withheld_source_disabled", "withheld_source_not_acquired"}:
                raise ValueError("Missing selected data cannot be successful evidence")
            rows.append({"state_code": key[0], "contest_code": key[1],
                         "subset": {"sub": key[2], "longName": entry["subsetTitle"]},
                         "status": item["status"]})
    if not rows:
        raise ValueError("No configured candidate survey tables")
    if "selected_configuration" in snapshot:
        expected = {(entry["stateAbbr"], entry["raceTypeCode"], entry["subsetNumber"])
                    for code, entries in snapshot["selected_configuration"].items()
                    if code in CONTESTS for entry in entries}
        if seen != expected:
            raise ValueError("Selected configuration/table inventory does not reconcile")
    return {
        "status": "reported_joint_survey_tables_not_population_decomposition",
        "tables": rows,
        "jurisdictions": [{
            "state_code": code, "jurisdiction_type": "federal_district" if code == "DC" else "state",
            "configured_candidate_tables": sum(r["state_code"] == code for r in rows),
            "reviewed_joint_tables": sum(r["state_code"] == code and
                                        r["status"] == "published_joint_question_reviewed" for r in rows),
            "survey_status": ("provider_configured" if any(r["state_code"] == code for r in rows)
                              else "not_in_this_provider_candidate_poll_configuration"),
            "population_decomposition_available": False,
            "next_action": "Acquire qualified participation histories and contest totals; seek another survey if this provider has no applicable table",
        } for code in CODES],
        "qualification": {
            "population_decomposition_released": False, "local_allocation_performed": False,
            "renormalized_published_percentages": False,
            "limitations": [
                "Current-electorate survey responses, not observed individual ballot transitions.",
                "N answers the prior presidential question, not validated all-ballot nonparticipation.",
                "No 2026 nonvoter rows; drop-off and total-swing attribution remain unmeasured.",
                "Source -1/null percentages stay suppressed; do not recover them from reverse conditionals.",
                "Respondent counts are not effective joint-cell sample sizes or design confidence intervals.",
                "Retain rounding, unshown choices and overlapping groups; do not sum subgroups.",
                "Four prior-answer shares below 98 leave an unexplained residual beyond rounding; retain cells but withhold composition-based arithmetic.",
                "Special-election stage/scope and nonunique literal D/R comparisons remain withheld.",
                "Survey candidate responses do not establish ranked-choice counting-round comparisons.",
                "Same SSRS study as NBC/MS NOW, not independent samples for validation or pooling.",
                "Some unrecontacted respondents retain initial choices; final weights match 2026 results.",
            ],
        },
    }


def collect(config_raw, cache, fetch):
    config = json.loads(config_raw)["dropdownConfig"]
    entries = [entry for code, values in config.items() if code in CONTESTS for entry in values]

    def load(entry):
        path = source_path(entry)
        if entry["isDisabled"]:
            return {"configuration_entry": entry, "status": "withheld_source_disabled"}
        file = cache / Path(path).name
        if fetch and not file.exists():
            with urllib.request.urlopen(SOURCE_ROOT + path, timeout=60) as response:
                raw = response.read()
            file.write_bytes(raw)
        if not file.exists():
            return {"configuration_entry": entry, "status": "withheld_source_not_acquired"}
        return select_source(file.read_bytes(), entry)

    cache.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        sources = list(executor.map(load, entries))
    return {"configuration_sha256": hashlib.sha256(config_raw).hexdigest(),
            "selected_configuration": config, "sources": sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path)
    source.add_argument("--snapshot", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.config and not args.cache:
        parser.error("--config requires --cache")
    snapshot = (collect(args.config.read_bytes(), args.cache, args.fetch) if args.config
                else json.loads(args.snapshot.read_text()))
    result = review_snapshot(snapshot)
    for path, data in [(args.snapshot_output, snapshot), (args.output, result)]:
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({"tables": len(result["tables"]), "reviewed": sum(
        row["status"] == "published_joint_question_reviewed" for row in result["tables"]),
        "states_with_reviewed_tables": sum(
            row["reviewed_joint_tables"] > 0 for row in result["jurisdictions"]),
        "population_decomposition_released": False}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Review the selected 2024-recall joint tables, not a population decomposition."""

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path


SOURCE = "https://www.nbcnews.com/politics/2026-elections/exit-polls"
QUESTION = "In the 2024 election for president, did you vote for:"
PRIOR_CHOICES = {
    "Kamala Harris (Dem)": "D",
    "Donald Trump (Rep)": "R",
    "Other": "O",
    "Did not vote": "N",
}


class PageData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.collecting = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self.collecting = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.collecting = False

    def handle_data(self, data):
        if self.collecting:
            self.parts.append(data)


def percent(value):
    if isinstance(value, bool):
        raise ValueError("Boolean percentage")
    result = float(value.rstrip("%") if isinstance(value, str) else value)
    if not 0 <= result <= 100:
        raise ValueError("Invalid percentage")
    return result


def snapshot_page(raw):
    parser = PageData()
    parser.feed(raw.decode("utf-8"))
    props = json.loads("".join(parser.parts))["props"]["pageProps"]
    selected = {key: props.get(key) for key in [
        "electionSeason", "electionType", "currentUrlPath", "lastModified"]}
    selected["nationalExitPollData"] = [{
        "code": view["code"], "title": view["title"],
        "polls": {
            "pollName": view["polls"]["pollName"],
            "lastUpdated": view["polls"].get("lastUpdated"),
            "candidates": view["polls"]["candidates"],
            "polls": [item for item in view["polls"]["polls"]
                      if item["question"] == QUESTION],
        },
    } for view in props["nationalExitPollData"]]
    return {
        "source_url": SOURCE, "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw), "selected_page_properties": selected,
    }


def review_page(raw):
    return review_snapshot(snapshot_page(raw))


def review_snapshot(snapshot):
    if snapshot["source_url"] != SOURCE:
        raise ValueError("Wrong source URL")
    props = snapshot["selected_page_properties"]
    if (props.get("electionSeason") != "2026"
            or props.get("electionType") != "general"
            or props.get("currentUrlPath") != "/politics/2026-elections/exit-polls"):
        raise ValueError("Wrong election or source page")
    groups = []
    seen = set()
    for view in props["nationalExitPollData"]:
        if view["code"] in seen:
            raise ValueError("Duplicate source view")
        seen.add(view["code"])
        poll = view["polls"]
        row = {
            "source_view_code": view["code"], "source_group": view["title"],
            "source_poll_name": poll["pollName"],
            "source_display_clock": poll.get("lastUpdated"),
        }
        questions = [item for item in poll["polls"] if item["question"] == QUESTION]
        if not questions:
            groups.append(dict(row, status="withheld_missing_joint_question"))
            continue
        if len(questions) != 1:
            raise ValueError("Ambiguous joint question")
        candidates = poll["candidates"]
        if (len(candidates) != 2
                or {item["party"] for item in candidates} != {"dem", "gop"}):
            raise ValueError("Unknown displayed candidate parties")
        colors = {item["colorHex"].lower(): "D" if item["party"] == "dem" else "R"
                  for item in candidates}
        if len(colors) != 2:
            raise ValueError("Ambiguous candidate colors")
        joint = {}
        for answer in questions[0]["answers"]:
            prior = PRIOR_CHOICES[answer["label"]]
            if prior in joint:
                raise ValueError("Duplicate prior-choice row")
            choices = {}
            for value in answer["values"]:
                party = colors[value["color"].lower()]
                if party in choices:
                    raise ValueError("Duplicate current-choice value")
                choices[party] = percent(value["value"])
            if set(choices) != {"D", "R"} or sum(choices.values()) > 101:
                raise ValueError("Invalid rounded current-choice percentages")
            joint[prior] = {
                "prior_choice_share_pct": percent(answer["percent"]),
                "current_choice_pct_within_prior_choice": choices,
            }
        if set(joint) != set(PRIOR_CHOICES.values()):
            raise ValueError("Incomplete selected question")
        composition_sum = sum(item["prior_choice_share_pct"] for item in joint.values())
        if not 98 <= composition_sum <= 102:
            raise ValueError("Composition does not reconcile within whole-point rounding")
        rd = joint["R"]["prior_choice_share_pct"] * joint["R"][
            "current_choice_pct_within_prior_choice"]["D"] / 100
        dr = joint["D"]["prior_choice_share_pct"] * joint["D"][
            "current_choice_pct_within_prior_choice"]["R"] / 100
        row.update({
            "status": "published_joint_question_reviewed",
            "joint_question_rows": joint,
            "reported_composition_sum_pct": composition_sum,
            "arithmetic_from_rounded_percentages_per_100_current_group_voters": {
                "reported_trump_to_dem": round(rd, 6),
                "reported_harris_to_rep": round(dr, 6),
                "net_reported_switching_toward_dem": round(rd - dr, 6),
            },
            "dropoff_estimate": None,
            "share_of_total_swing": None,
            "design_confidence_interval": None,
        })
        groups.append(row)
    if not groups:
        raise ValueError("No source views")
    return {
        "source_url": SOURCE, "source_sha256": snapshot["source_sha256"],
        "source_bytes": snapshot["source_bytes"],
        "source_last_modified": props.get("lastModified"),
        "selected_question": QUESTION, "groups": groups,
        "qualification": {
            "complete_selected_question_tables": all(
                row["status"] == "published_joint_question_reviewed" for row in groups),
            "whole_dashboard_or_native_microdata_redistributed": False,
            "independently_validated_transitions": False,
            "population_decomposition_released": False,
            "state_or_local_estimates_released": False,
            "subgroup_bases_or_replicate_weights_supplied": False,
            "renormalized_published_percentages": False,
            "limitations": [
                "Arithmetic describes the selected current-electorate subgroup only.",
                "Prior choice and nonvoting are recalled, not observed ballots.",
                "Prior N answers the presidential question, not validated all-ballot nonparticipation.",
                "No 2026 nonvoter rows; drop-off is not measured by this table.",
                "Groups overlap; do not sum groups or multiply separate marginals.",
                "Whole-point rounding is retained; unshown choices remain unresolved.",
                "No first-ever-voter inference from reported 2024 nonvoting.",
                "Legacy National Presidential pollName requires contest-scope review.",
                "Inspect final weighting and unrecontacted intended-choice treatment.",
                "Overall sample size is not a subgroup or prior-choice sample base.",
            ],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--html", type=Path)
    source.add_argument("--snapshot", type=Path)
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    snapshot = (snapshot_page(args.html.read_bytes()) if args.html
                else json.loads(args.snapshot.read_text()))
    result = review_snapshot(snapshot)
    if args.snapshot_output:
        args.snapshot_output.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot_output.write_text(json.dumps(snapshot, indent=2) + "\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"reviewed_groups": sum(
        row["status"] == "published_joint_question_reviewed" for row in result["groups"]),
        "population_decomposition_released": False}))


if __name__ == "__main__":
    main()

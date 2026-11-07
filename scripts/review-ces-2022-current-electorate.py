"""Reconstruct prior-choice composition of the current 2022 electorate, privately."""

import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path


SOURCE_SHA256 = "dcdaeba631e0bdf50f3d7dcf4dcde7cc980e4281ff5dab87efcaa7353ca089bc"
FIPS = dict(zip(
    "1 2 4 5 6 8 9 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56".split(),
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(),
))
MATCH_STATE = {str(i): state for i, state in enumerate(sorted(FIPS.values()), 1)}
PRIOR = ("D", "R", "O", "NO_PRESIDENT", "UNKNOWN")
HOUSE = ("D", "R", "O", "CONTEST_NONVOTE", "REPORTED_NONVOTE", "UNKNOWN")
AGE = ("UNDER_18_IN_2020", "BIRTHDAY_BOUNDARY_2002", "ADULT_IN_2020", "UNKNOWN")
SPECS = tuple(
    (weight, rule, geography)
    for weight in ("vvweight_post", "commonpostweight")
    for rule in ("record_positive", "reported_definitely_voted")
    for geography in ("survey_match_agreement", "survey_state_only")
)
REQUIRED = (
    "inputstate", "TS_state", "TS_g2022", "CC22_401", "presvote20post",
    "birthyr", "CC22_412", "vvweight_post", "commonpostweight",
) + tuple("HouseCand%dParty_post" % i for i in range(1, 9))
MISSING = {"", "NA"}
ZERO = Decimal(0)


def native_code(value, allowed, field):
    if value in MISSING:
        return None
    if value not in allowed:
        raise ValueError("Unexpected native code in " + field)
    return value


def parse_weight(value):
    if value in MISSING:
        return None
    number = Decimal(value)
    if not number.is_finite() or number < ZERO:
        raise ValueError("Nonfinite or negative weight")
    return number


def prior_choice(value):
    value = native_code(value, {"1", "2", "3", "4", "5", "6", "8", "9"}, "presvote20post")
    return {"1": "D", "2": "R", "3": "O", "4": "O", "5": "O",
            "6": "NO_PRESIDENT"}.get(value, "UNKNOWN")


def house_choice(row):
    value = native_code(row["CC22_412"],
                        {str(i) for i in range(1, 9)} | {"10", "11", "12", "13", "98", "99"},
                        "CC22_412")
    if value in {str(i) for i in range(1, 9)}:
        party = row["HouseCand%sParty_post" % value]
        if party in MISSING or party == "-1":
            return "UNKNOWN"
        return {"Democratic": "D", "Republican": "R"}.get(party, "O")
    return {"10": "O", "11": "CONTEST_NONVOTE", "12": "REPORTED_NONVOTE"}.get(value, "UNKNOWN")


def age_group(value):
    if value in MISSING:
        return "UNKNOWN"
    year = Decimal(value)
    if not year.is_finite() or year != year.to_integral_value() or not 1900 <= year <= 2004:
        return "UNKNOWN"
    if year >= 2003:
        return "UNDER_18_IN_2020"
    return "BIRTHDAY_BOUNDARY_2002" if year == 2002 else "ADULT_IN_2020"


def cell():
    return {"n": 0, "weight": ZERO, "squared_weight": ZERO}


def add(target, weight):
    target["n"] += 1
    target["weight"] += weight
    target["squared_weight"] += weight * weight


def accumulator():
    return {
        "dispositions": {key: cell() for key in (
            "missing_or_zero_weight", "matched_state_missing", "matched_state_disagreement",
            "not_current_query_voter", "retained")},
        "prior": {prior: cell() for prior in PRIOR},
        "prior_by_age": {prior: {age: cell() for age in AGE} for prior in PRIOR},
        "prior_by_house": {prior: {house: cell() for house in HOUSE} for prior in PRIOR},
    }


def finish(acc, control):
    total = acc["dispositions"]["retained"]["weight"]
    if total != sum(value["weight"] for value in acc["prior"].values()):
        raise ValueError("Prior composition lost the full denominator")
    n22 = Decimal(control["ballots_2022"])
    result = dict(acc)
    result["current_query_weight"] = total
    result["current_query_n"] = acc["dispositions"]["retained"]["n"]
    result["kish_effective_n_descriptive_not_design_precision"] = (
        total * total / acc["dispositions"]["retained"]["squared_weight"] if total else None)
    result["control"] = control
    result["prior_composition"] = {}
    for prior in PRIOR:
        w = acc["prior"][prior]["weight"]
        if w != sum(value["weight"] for value in acc["prior_by_age"][prior].values()):
            raise ValueError("Age partition does not reconcile")
        if w != sum(value["weight"] for value in acc["prior_by_house"][prior].values()):
            raise ValueError("House partition does not reconcile")
        share = w / total if total else None
        count = n22 * share if share is not None else None
        old = control["presidential_2020"].get(prior)
        opposite = {"D": "R", "R": "D"}.get(prior)
        result["prior_composition"][prior] = {
            "share_full_current_query_denominator": share,
            "conditional_scaled_current_people": count,
            "original_2020_presidential_votes": old,
            "return_pct_original_coalition": 100 * count / old if old and count is not None else None,
            "signed_apparent_absence": Decimal(old) - count if old is not None and count is not None else None,
            "conditional_scaled_opposite_house_choice": (
                n22 * acc["prior_by_house"][prior][opposite]["weight"] / total
                if opposite and total else None),
        }
    return result


def controls(selected):
    official = selected["official_2020"]["states"]
    turnout = selected["turnout_2022"]
    if set(official) != set(FIPS.values()) or set(turnout["states"]) != set(FIPS.values()):
        raise ValueError("Require complete 50-state plus DC controls")
    result = {}
    for state in sorted(official):
        baseline = official[state]
        ballots = turnout["states"][state]["ballots"]
        if (any(type(baseline[key]) is not int or baseline[key] < 0 for key in ("D", "R", "O", "total"))
                or baseline["total"] != sum(baseline[key] for key in ("D", "R", "O"))
                or type(ballots) is not int or ballots <= 0):
            raise ValueError("Invalid source control")
        result[state] = {
            "presidential_2020": dict(baseline), "ballots_2022": ballots,
            "contest_proxy_not_all_ballot": state in turnout["contest_proxy_states"],
            "EAVS_substitution": state in turnout["EAVS_substitution_states"],
        }
    result["US50"] = {
        "presidential_2020": {key: sum(result[s]["presidential_2020"][key]
                                     for s in official if s != "DC") for key in ("D", "R", "O", "total")},
        "ballots_2022": sum(result[s]["ballots_2022"] for s in official if s != "DC"),
        "contest_proxy_not_all_ballot": True, "EAVS_substitution": True,
    }
    return result


def review(rows, control):
    grouped = {state: [accumulator() for _ in SPECS] for state in control}
    source_n = unresolved = 0
    with localcontext() as context:
        context.prec = 50
        for row in rows:
            if set(REQUIRED) - set(row):
                raise ValueError("Missing native current-electorate fields")
            source_n += 1
            state = FIPS.get(native_code(row["inputstate"], set(FIPS) | {"98", "99"}, "inputstate"))
            match = MATCH_STATE.get(native_code(row["TS_state"], set(MATCH_STATE), "TS_state"))
            history = native_code(row["TS_g2022"], {str(i) for i in range(1, 8)}, "TS_g2022")
            report = native_code(row["CC22_401"], {"1", "2", "3", "4", "5", "8", "9"}, "CC22_401")
            prior, age, house = prior_choice(row["presvote20post"]), age_group(row["birthyr"]), house_choice(row)
            weights = {name: parse_weight(row[name]) for name in ("vvweight_post", "commonpostweight")}
            if state is None:
                unresolved += 1
                continue
            for i, (name, rule, geography) in enumerate(SPECS):
                weight = weights[name]
                if not weight:
                    disposition = "missing_or_zero_weight"
                elif geography == "survey_match_agreement" and match is None:
                    disposition = "matched_state_missing"
                elif geography == "survey_match_agreement" and match != state:
                    disposition = "matched_state_disagreement"
                elif not (history in {"1", "2", "3", "4", "5", "6"}
                          if rule == "record_positive" else report == "5"):
                    disposition = "not_current_query_voter"
                else:
                    disposition = "retained"
                for scope in (state,) if state == "DC" else (state, "US50"):
                    acc = grouped[scope][i]
                    add(acc["dispositions"][disposition], weight or ZERO)
                    if disposition == "retained":
                        add(acc["prior"][prior], weight)
                        add(acc["prior_by_age"][prior][age], weight)
                        add(acc["prior_by_house"][prior][house], weight)
        scopes = []
        for state in sorted(control):
            specs = []
            for spec, acc in zip(SPECS, grouped[state]):
                specs.append({
                    "weight": spec[0], "current_rule": spec[1], "geography_rule": spec[2],
                    **finish(acc, control[state]),
                })
            scopes.append({"state_code": state, "specifications": specs})
    return {
        "status": "all_state_current_2022_electorate_reconstruction_not_population_validation",
        "source_rows": source_n, "unresolved_survey_state_rows": unresolved, "states": scopes,
        "state_count_excluding_dc_and_national": 50, "specifications_per_scope": len(SPECS),
        "population_method_validated": False, "public_release_qualified": False,
        "limits": [
            "All current-query voters are eligible for inclusion; no restriction to positive 2020 turnout or candidate choice.",
            "Prior presidential nonvote, unknown choice and birth-year categories remain in the full denominator.",
            "Birth years 2003-2004 imply under 18 throughout 2020; 2002 is birthday-ambiguous; neither proves first-ever voting.",
            "Under-18 prior-choice conflicts are preserved in cross-cells, not silently recoded or removed.",
            "Current matched-state agreement does not establish 2020 residence, election-day residence or absence of migration.",
            "Reported/profile 2020 choice timing is not proven to be a newly asked 2022 recall question.",
            "State-qualified common-content raking includes historical choice and political outcomes; outcome recovery is not independent validation.",
            "The two weight frames differ; sensitivities are not confidence intervals and Kish support is not design precision.",
            "Turnout controls retain KS/MS/OK contest proxies and EAVS substitutions, not universal all-ballot gold.",
            "Signed apparent absence includes migration, mortality, response, record and denominator error; it is not measured staying home.",
            "First-ever voting, new registration, eligible nonparticipation and candidate-specific administrative gold remain unidentified.",
        ],
    }


def serialized(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: serialized(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [serialized(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "labels", "controls", "prespec", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise ValueError("Require new private output outside repository")
    paths = {"source": args.source, "labels": args.labels, "controls": args.controls,
             "reviewer": Path(__file__), "tests": Path(__file__).with_name("test-review-ces-2022-current-electorate.py")}
    hashes = {}
    for name, path in paths.items():
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes[name] = digest.hexdigest()
    prespec = json.loads(args.prespec.read_text())
    if prespec["input_sha256"] != hashes or hashes["source"] != SOURCE_SHA256:
        raise ValueError("Design/code/source binding differs before calculation")
    labels = json.loads(args.labels.read_text())
    if (labels["status"] != "native_common_content_code_labels_qualified"
            or labels["selected_variables"]["TS_state"]["codes"] != MATCH_STATE
            or labels["selected_variables"]["presvote20post"]["codes"]["6"] != "Did not vote for President"):
        raise ValueError("Native label qualification differs")
    with args.source.open(newline="", encoding="utf-8-sig") as source:
        result = review(csv.DictReader(source), controls(json.loads(args.controls.read_text())))
    if result["source_rows"] != 60000:
        raise ValueError("Native source case count differs")
    result["input_sha256"] = hashes
    result["prespec_sha256"] = hashlib.sha256(args.prespec.read_bytes()).hexdigest()
    args.output.mkdir(parents=True, mode=0o700)
    descriptor = os.open(args.output / "current-electorate.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(serialized(result), target, indent=2, allow_nan=False)
        target.write("\n")
    print(json.dumps({"status": result["status"], "source_rows": result["source_rows"],
                      "scopes": len(result["states"]), "specifications_per_scope": len(SPECS)}))


if __name__ == "__main__":
    main()

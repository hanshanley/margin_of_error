"""Reconstruct prior-vote profiles of all current 2024 voters, privately."""

import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import json
import os
from pathlib import Path


HELPER = Path(__file__).with_name("review-ces-2022-current-electorate.py")
_spec = importlib.util.spec_from_file_location("current_profile_arithmetic", HELPER)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
FIPS, PRIOR = _helper.FIPS, _helper.PRIOR
SOURCE_SHA256 = "8a5e9fbc982961ad910bad9aed8d521fa0a85e85cded43fb308cce0ab22ba5d9"
WEIGHTS = ("vvweight", "vvweight_post", "commonweight", "commonpostweight")
SPECS = tuple((weight, geography) for weight in WEIGHTS
              for geography in ("survey_match_agreement", "survey_state_only"))
AGE = ("ADULT_IN_2020", "BIRTHDAY_BOUNDARY_2002", "UNDER_18_IN_2020_POSSIBLE_2022",
       "UNDER_18_THROUGHOUT_2022", "UNKNOWN")
REQUIRED = ("inputstate", "TS_state", "TS_g2024", "presvote20post", "birthyr") + WEIGHTS
ZERO = Decimal(0)


def age_group(value):
    if value in _helper.MISSING:
        return "UNKNOWN"
    year = Decimal(value)
    if not year.is_finite() or year != year.to_integral_value() or not 1900 <= year <= 2006:
        return "UNKNOWN"
    if year >= 2005:
        return "UNDER_18_THROUGHOUT_2022"
    if year >= 2003:
        return "UNDER_18_IN_2020_POSSIBLE_2022"
    return "BIRTHDAY_BOUNDARY_2002" if year == 2002 else "ADULT_IN_2020"


def accumulator():
    return {
        "dispositions": {name: _helper.cell() for name in (
            "missing_or_zero_weight", "matched_state_missing", "matched_state_disagreement",
            "not_record_positive", "retained")},
        "prior": {prior: _helper.cell() for prior in PRIOR},
        "prior_by_age": {prior: {age: _helper.cell() for age in AGE} for prior in PRIOR},
    }


def controls(selected):
    old, current = selected["official_2020"]["states"], selected["turnout_2024"]["states"]
    if set(old) != set(FIPS.values()) or set(current) != set(old):
        raise ValueError("Require 50 states and DC in both controls")
    result = {}
    for state in sorted(old):
        previous, count = old[state], current[state]["ballots"]
        if (any(type(previous[key]) is not int or previous[key] < 0 for key in ("D", "R", "O", "total"))
                or previous["total"] != sum(previous[key] for key in ("D", "R", "O"))
                or type(count) is not int or count <= 0):
            raise ValueError("Invalid source control")
        result[state] = {
            "presidential_2020": dict(previous), "ballots_2024": count,
            "turnout_control_status": current[state]["status"],
        }
    for scope in ("US50", "US51"):
        states = [state for state in old if state != "DC" or scope == "US51"]
        result[scope] = {
            "presidential_2020": {key: sum(old[s][key] for s in states)
                                 for key in ("D", "R", "O", "total")},
            "ballots_2024": sum(current[s]["ballots"] for s in states),
            "turnout_control_status": "sum_of_source_reported_not_independently_certified_counts",
        }
    if result["US51"]["ballots_2024"] != selected["turnout_2024"]["separate_us_ballots"]:
        raise ValueError("Separate national control does not reconcile to state/DC counts")
    return result


def finish(acc, control):
    total = acc["dispositions"]["retained"]["weight"]
    if total != sum(value["weight"] for value in acc["prior"].values()):
        raise ValueError("Full current-electorate denominator lost")
    result = {**acc, "control": control, "current_query_weight": total,
              "current_query_n": acc["dispositions"]["retained"]["n"], "prior_composition": {}}
    for prior in PRIOR:
        weight = acc["prior"][prior]["weight"]
        if weight != sum(value["weight"] for value in acc["prior_by_age"][prior].values()):
            raise ValueError("Birth-year partition does not reconcile")
        share = weight / total if total else None
        people = Decimal(control["ballots_2024"]) * share if share is not None else None
        previous = control["presidential_2020"].get(prior)
        result["prior_composition"][prior] = {
            "share_full_current_query_denominator": share,
            "conditional_scaled_current_people": people,
            "original_2020_presidential_votes": previous,
            "return_pct_original_coalition": 100 * people / previous if people is not None and previous else None,
            "signed_apparent_absence": Decimal(previous) - people
            if people is not None and previous is not None else None,
        }
    return result


def review(rows, control):
    grouped = {state: [accumulator() for _ in SPECS] for state in control}
    source_n = unresolved = 0
    with localcontext() as context:
        context.prec = 50
        for row in rows:
            if set(REQUIRED) - set(row):
                raise ValueError("Missing native 2024 administrative/profile fields")
            source_n += 1
            state = FIPS.get(_helper.native_code(
                row["inputstate"], set(FIPS) | {"98", "99"}, "inputstate"))
            match = _helper.native_code(row["TS_state"], set(FIPS.values()), "TS_state")
            history = _helper.native_code(row["TS_g2024"], set("1234567"), "TS_g2024")
            prior, age = _helper.prior_choice(row["presvote20post"]), age_group(row["birthyr"])
            weights = {name: _helper.parse_weight(row[name]) for name in WEIGHTS}
            if state is None:
                unresolved += 1
                continue
            scopes = (state, "US51") if state == "DC" else (state, "US50", "US51")
            for index, (name, geography) in enumerate(SPECS):
                weight = weights[name]
                if not weight:
                    disposition = "missing_or_zero_weight"
                elif geography == "survey_match_agreement" and match is None:
                    disposition = "matched_state_missing"
                elif geography == "survey_match_agreement" and match != state:
                    disposition = "matched_state_disagreement"
                elif history not in set("123456"):
                    disposition = "not_record_positive"
                else:
                    disposition = "retained"
                for scope in scopes:
                    acc = grouped[scope][index]
                    _helper.add(acc["dispositions"][disposition], weight or ZERO)
                    if disposition == "retained":
                        _helper.add(acc["prior"][prior], weight)
                        _helper.add(acc["prior_by_age"][prior][age], weight)
        states = []
        for scope in sorted(control):
            specifications = [
                {"weight": spec[0], "geography_rule": spec[1], "current_rule": "record_positive",
                 **finish(acc, control[scope])}
                for spec, acc in zip(SPECS, grouped[scope])
            ]
            states.append({"state_code": scope, "specifications": specifications})
    return {
        "status": "all_state_2024_current_profile_reconstruction_not_population_validation",
        "source_rows": source_n, "unresolved_survey_state_rows": unresolved, "states": states,
        "state_count_excluding_dc_and_national": 50, "specifications_per_scope": len(SPECS),
        "population_method_validated": False, "public_release_qualified": False,
        "limits": [
            "All current record-positive voters remain eligible regardless of prior vote or current presidential choice.",
            "No 2024 post-interview response is consumed; vvweight is primary, post weights are attrition sensitivities.",
            "Native TS_state is postal, unlike the 2022 common file's numeric alphabetical factor.",
            "Unknown prior choice and presidential nonvote remain in the full denominator.",
            "Birth 2003/04 implies under 18 throughout 2020; 2005/06 implies under 18 throughout 2022.",
            "Birth 2002 is birthday-ambiguous; age/profile conflicts are preserved, not repaired.",
            "New age eligibility and presidential nonvote do not establish first-ever voting or new registration.",
            "2020 profile-question timing is not proven newly asked in 2024.",
            "Weights use historical/current political outcomes; recovering those margins is not independent validation.",
            "Utah private-record matching and missing histories/weights can affect participation coverage.",
            "Current survey/record state agreement does not prove 2020 residence or election-day residence.",
            "UF source-labeled TOTAL_BALLOTS_COUNTED has a TBD definition and an unlabeled source column in v0.4.",
            "UF counts, including rounded values, are retained as reported, not independently certified all-ballot gold.",
            "Signed apparent absence includes mortality, migration and survey/record/control errors, not measured staying home.",
            "Pew national 2024 resident-cohort rates are external concordance, not matched original-FEC-cohort error or state gold.",
            "Unknown cells and sensitivity variation are not confidence intervals; no fitted correction or 2026 certification.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "labels", "controls", "prespec", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise ValueError("Require fresh private output outside repository")
    paths = {"source": args.source, "labels": args.labels, "controls": args.controls,
             "reviewer": Path(__file__), "helper": HELPER,
             "tests": Path(__file__).with_name("test-review-ces-2024-current-profile.py")}
    hashes = {}
    for name, path in paths.items():
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes[name] = digest.hexdigest()
    design = json.loads(args.prespec.read_text())
    if (design["input_sha256"] != hashes or hashes["source"] != SOURCE_SHA256
            or design["primary"] != list(SPECS[0])):
        raise ValueError("Frozen source/code/design binding differs")
    labels = json.loads(args.labels.read_text())
    if (labels["status"] != "2024_current_profile_native_codes_and_guide_qualified"
            or labels["selected_variables"]["presvote20post"]["codes"]["6"] != "Did not vote for President"
            or labels["record_positive_codes"] != list("123456")
            or labels["matched_state_encoding"] != "literal_postal_abbreviation"):
        raise ValueError("Native coding qualification differs")
    with args.source.open(newline="", encoding="utf-8-sig") as source:
        result = review(csv.DictReader(source), controls(json.loads(args.controls.read_text())))
    if result["source_rows"] != 60000:
        raise ValueError("Source case count differs")
    result.update(input_sha256=hashes, prespec_sha256=hashlib.sha256(args.prespec.read_bytes()).hexdigest())
    args.output.mkdir(parents=True, mode=0o700)
    descriptor = os.open(args.output / "current-profile.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(_helper.serialized(result), target, indent=2, allow_nan=False)
        target.write("\n")
    print(json.dumps({"status": result["status"], "source_rows": result["source_rows"],
                      "scopes": len(result["states"]), "specifications_per_scope": len(SPECS)}))


if __name__ == "__main__":
    main()

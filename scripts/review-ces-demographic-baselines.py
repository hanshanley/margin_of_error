"""Audit private historical coalition demographics, not observed 2026 transitions."""

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSV_SHA256 = "8a5e9fbc982961ad910bad9aed8d521fa0a85e85cded43fb308cce0ab22ba5d9"
GUIDE_MD5 = "b1b24ed55a20193bb0301bc84cf6da9a"
STATE_CODES = dict(zip(
    "01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56".split(),
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()))
RACES = {"1": "White", "2": "Black", "3": "Hispanic", "4": "Asian",
         "5": "Native American", "6": "Two or more races", "7": "Other", "8": "Middle Eastern"}
LABELS = {
    "gender4": {"1": "Man", "2": "Woman", "3": "Non-binary", "4": "Other"},
    "race": RACES, "hispanic": {"1": "Yes", "2": "No"},
    "educ": {"1": "No HS", "2": "High school graduate", "3": "Some college",
             "4": "2-year", "5": "4-year", "6": "Post-grad"},
    "CC24_410": {"1": "Kamala Harris", "2": "Donald Trump", "3": "Robert F. Kennedy, Jr.",
                 "4": "Jill Stein", "5": "Cornel West", "6": "Chase Oliver",
                 "8": "Other", "9": "Did not vote for President"},
}


def verify_labels(audit):
    if audit["dataverse_file_id"] != 12050327 or audit["respondent_data_transferred"] is not False:
        raise ValueError("Wrong native code-label audit")
    for variable, expected in LABELS.items():
        actual = audit["selected_variables"][variable]["codes"]
        if any(actual.get(code) != label for code, label in expected.items()):
            raise ValueError(f"Native numeric labels differ: {variable}")


def age_group(birth_year, year):
    if not birth_year.isdigit() or not 1904 <= int(birth_year) <= 2006:
        return "Unknown birth year"
    age = year - int(birth_year)
    return "18-29" if age < 30 else "30-44" if age < 45 else "45-64" if age < 65 else "65+"


def demographics(row):
    race = RACES.get(row["race"], "Unknown race")
    if row["hispanic"] == "1" or row["race"] == "3":
        combined = "Hispanic"
    elif row["hispanic"] != "2":
        combined = "Unknown ethnicity"
    else:
        combined = "Unknown race" if race == "Unknown race" else f"Non-Hispanic {race}"
    education = LABELS["educ"].get(row["educ"], "Unknown education")
    college = ("College degree" if row["educ"] in ("5", "6") else
               "No college degree" if row["educ"] in ("1", "2", "3", "4") else "Unknown education")
    white = ("Non-Hispanic White" if combined == "Non-Hispanic White" else
             "Unknown race or ethnicity" if combined.startswith("Unknown") else "Not non-Hispanic White")
    return {
        "gender_2024": LABELS["gender4"].get(row["gender4"], "Unknown gender"),
        "source_race_2024": race, "race_ethnicity_2024": combined,
        "education_2024": education, "race_education_2024": f"{white}; {college}",
        "age_2024_by_birth_year": age_group(row["birthyr"], 2024),
        "age_2026_by_birth_year_if_alive": age_group(row["birthyr"], 2026),
    }


def accumulate(bucket, weight):
    bucket["respondents"] += 1
    bucket["sum_weight"] += weight
    bucket["sum_squared_weight"] += weight * weight


def effective(bucket):
    return bucket["sum_weight"] ** 2 / bucket["sum_squared_weight"]


def review(rows):
    audit, totals, cells = Counter(), {}, {}
    for row in rows:
        audit["native_respondents"] += 1
        if row["TS_g2024"] not in {"1", "2", "3", "4", "5", "6"}:
            audit["excluded_no_validated_2024_turnout"] += 1
            continue
        if row["CC24_410"] not in {"1", "2", "3", "4", "5", "6", "8"}:
            audit["excluded_no_reported_presidential_choice"] += 1
            continue
        if row["vvweight_post"] in {"", "NA"}:
            audit["excluded_missing_documented_weight"] += 1
            continue
        weight = float(row["vvweight_post"])
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("Invalid documented survey weight")
        state = STATE_CODES.get(row["inputstate"].zfill(2))
        if state is None:
            raise ValueError("Unrecognized survey state")
        if row["TS_state"] != state:
            audit["excluded_match_state_differs_from_survey_state"] += 1
            continue
        prior = {"1": "D", "2": "R"}.get(row["CC24_410"], "O")
        groups = demographics(row)
        audit["retained_respondents"] += 1
        for scope in (state, "US51") if state == "DC" else (state, "US50", "US51"):
            accumulate(totals.setdefault((scope, prior), Counter()), weight)
            for dimension, group in groups.items():
                accumulate(cells.setdefault((scope, prior, dimension, group), Counter()), weight)
    results = []
    for (scope, prior), total in sorted(totals.items()):
        partitions = {}
        for (cell_scope, cell_prior, dimension, group), cell in sorted(cells.items()):
            if (cell_scope, cell_prior) != (scope, prior):
                continue
            fraction = cell["sum_weight"] / total["sum_weight"]
            variance = (cell["sum_squared_weight"] * (1 - fraction) ** 2
                        + (total["sum_squared_weight"] - cell["sum_squared_weight"]) * fraction ** 2)
            partitions.setdefault(dimension, []).append({
                "group": group, **cell, "effective_sample_size": effective(cell),
                "fraction_within_reported_2024_coalition": fraction,
                "independent_row_ratio_standard_error_not_design": math.sqrt(max(0, variance)) / total["sum_weight"],
                "low_effective_base_diagnostic": effective(total) < 100 or effective(cell) < 30,
            })
        for groups in partitions.values():
            for key, expected in total.items():
                if not math.isclose(sum(g[key] for g in groups), expected, rel_tol=1e-10, abs_tol=1e-8):
                    raise ValueError("Demographic partition does not reconcile to the full coalition")
        results.append({"scope": scope, "prior_choice": prior, **total,
                        "effective_sample_size": effective(total), "partitions": partitions})
    return {
        "status": "private_historical_demographic_audit_not_qualified_2026_baseline",
        "source_audit": dict(audit), "coalitions": results,
        "original_group_population_estimates": None, "group_dropoff_estimates": None,
        "limits": [
            "Administrative validation measures 2024 turnout, not presidential candidate choice.",
            "vvweight_post targets registered adults; use only the validated-turnout/reported-choice subset here.",
            "Presidential choice entered the source weights; outcome agreement is not independent validation.",
            "Matched source survey and voter-file states agree, but this does not establish election-day residency or a fixed cross-election population.",
            "US50 excludes DC; US51 includes DC. Do not mix their denominators or sum overlapping national/state scopes.",
            "Fractions retain unknown, non-binary and other responses in the coalition denominator.",
            "Raw race and combined race/ethnicity are separate operationalizations, not interchangeable White or Black categories.",
            "Education is measured in 2024. The hypothetical 2026 age grouping ages the 2024 birth years; it does not observe survival, residence or 2026 participation.",
            "Effective bases and independent-row ratio standard errors are diagnostics, not design confidence intervals. Coalition effective base below100 or group base below30 is flagged, not treated as a publication qualification rule.",
            "No original group population, measured staying home, demographic turnout, total-swing share or individual political label is estimated.",
            "This private audit includes small aggregate cells; disclosure and cross-source semantic review are required before public export.",
        ],
    }


def digest(path, algorithm):
    value = hashlib.new(algorithm)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("survey", "guide", "labels", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT in args.output.resolve().parents:
        raise ValueError("Use a new private output outside the repository")
    if digest(args.survey, "sha256") != CSV_SHA256 or digest(args.guide, "md5") != GUIDE_MD5:
        raise ValueError("Frozen CES source or guide changed")
    verify_labels(json.loads(args.labels.read_text()))
    with args.survey.open(newline="") as source:
        result = review(csv.DictReader(source))
    result["source_pins"] = {
        "survey_sha256": CSV_SHA256, "guide_md5": GUIDE_MD5,
        "native_label_audit_sha256": digest(args.labels, "sha256"),
        "license": "CC0 1.0", "doi": "10.7910/DVN/X11EP6", "release": "9.0",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"source_audit": result["source_audit"],
                      "coalition_scopes": len(result["coalitions"]), "output": str(args.output)}))

"""Fit survey-informed historical choice; this does not itself estimate 2026 transitions."""

import argparse
import csv
import hashlib
import json
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

STATE_CODES = dict(zip(
    "01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56".split(),
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()))
SEED = 20261106


def age_bin(year):
    if not year.isdigit() or not 1904 <= int(year) <= 2006:
        return "Unknown"
    age = 2024 - int(year)
    return "18-29" if age < 30 else "30-44" if age < 45 else "45-64" if age < 65 else "65+"


def race_ethnicity(race, hispanic):
    if hispanic == "1" or race == "3":
        return "Hispanic"
    if hispanic != "2":
        return "Ethnicity unspecified"
    return {"1": "Non-Hispanic White", "2": "Non-Hispanic Black", "4": "Non-Hispanic Asian",
            "5": "Non-Hispanic Native American", "6": "Non-Hispanic multiracial",
            "7": "Non-Hispanic other", "8": "Non-Hispanic Middle Eastern"}.get(race, "Unspecified race")


def survey_features(row):
    state = STATE_CODES.get(row["inputstate"].zfill(2))
    if not state:
        raise ValueError("Unrecognized survey state")
    party = {"2": "DEM", "8": "REP"}.get(row["TS_partyreg"],
             "Unspecified" if row["TS_partyreg"] == "NA" else "Other")
    primary = {"1": "DEM", "6": "REP"}.get(row["TS_p2024_party"],
               "No matched primary" if row["TS_p2024_party"] == "NA" else "Other")
    return {"state": state, "age": age_bin(row["birthyr"]),
            "race_ethnicity": race_ethnicity(row["race"], row["hispanic"]),
            "registered_party": party, "primary_party": primary}


def predictor_features(values, include_party=True):
    output = {key: values[key] for key in ["state", "age", "race_ethnicity", "registered_party", "primary_party"]}
    if include_party:
        output["state_registration"] = f'{values["state"]}:{values["registered_party"]}'
    else:
        output.pop("registered_party")
    return output


def read_survey(path):
    values, outcomes, weights, groups = [], [], [], []
    audit = Counter()
    with path.open(newline="") as source:
        for row in csv.DictReader(source):
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
            if not np.isfinite(weight) or weight <= 0:
                raise ValueError("Invalid survey weight")
            feature = survey_features(row)
            if row["TS_state"] != feature["state"]:
                audit["excluded_match_state_differs_from_survey_state"] += 1
                continue
            values.append(feature)
            feature["source_race"] = row["race"]
            outcomes.append({"1": 0, "2": 1}.get(row["CC24_410"], 2))
            weights.append(weight)
            groups.append(f'{feature["state"]}:{row["countyfips"]}')
    return values, np.asarray(outcomes), np.asarray(weights), np.asarray(groups), dict(audit)


def scores(outcomes, probabilities, weights):
    if len(outcomes) == 0:
        return None
    labels = np.eye(3)[outcomes]
    return {
        "respondents": len(outcomes),
        "effective_sample_size": float(weights.sum() ** 2 / np.square(weights).sum()),
        "log_loss": float(np.average(-np.log(np.clip(probabilities[np.arange(len(outcomes)), outcomes], 1e-12, 1)), weights=weights)),
        "multiclass_brier": float(np.average(np.square(probabilities - labels).sum(axis=1), weights=weights)),
        "democratic_share_all_reported_choices": float(np.average(outcomes == 0, weights=weights)),
        "predicted_democratic_share_all_reported_choices": float(np.average(probabilities[:, 0], weights=weights)),
        "democratic_calibration_error_pp": float(100 * np.average(probabilities[:, 0] - (outcomes == 0), weights=weights)),
    }


def fit(matrix, outcomes, weights, regularization):
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        model = LogisticRegression(C=regularization, max_iter=3000, tol=1e-7, solver="lbfgs")
        model.fit(matrix, outcomes, sample_weight=weights / weights.mean())
    if list(model.classes_) != [0, 1, 2]:
        raise ValueError("Choice classes are missing")
    return model


def fit_model(values, outcomes, weights, groups, include_party=True, regularization=1.0):
    vectorizer = DictVectorizer()
    matrix = vectorizer.fit_transform([predictor_features(row, include_party) for row in values])
    predictions = np.full((len(values), 3), np.nan)
    folds = GroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    baseline = np.full_like(predictions, np.nan)
    for training, validation in folds.split(matrix, outcomes, groups):
        model = fit(matrix[training], outcomes[training], weights[training], regularization)
        predictions[validation] = model.predict_proba(matrix[validation])
        global_counts = np.bincount(outcomes[training], weights=weights[training], minlength=3)
        global_shares = global_counts / global_counts.sum()
        for state in {values[index]["state"] for index in validation}:
            local = training[[values[index]["state"] == state for index in training]]
            counts = np.bincount(outcomes[local], weights=weights[local], minlength=3) + 10 * global_shares
            positions = [index for index in validation if values[index]["state"] == state]
            baseline[positions] = counts / counts.sum()
    if not np.isfinite(predictions).all():
        raise ValueError("Incomplete held-out predictions")
    model = fit(matrix, outcomes, weights, regularization)
    diagnostics = {}
    for dimension in ["state", "age", "race_ethnicity", "registered_party", "primary_party"]:
        diagnostics[dimension] = []
        for group in sorted({row[dimension] for row in values}):
            selected = np.asarray([row[dimension] == group for row in values])
            metric = scores(outcomes[selected], predictions[selected], weights[selected])
            diagnostics[dimension].append({"group": group, **metric,
                "low_effective_sample": metric["effective_sample_size"] < 100})
    artifact = {
        "features": list(vectorizer.get_feature_names_out()),
        "coefficients": model.coef_.tolist(), "intercepts": model.intercept_.tolist(),
        "classes": ["Democratic", "Republican", "Other reported presidential choice"],
        "include_registration_party": include_party, "inverse_regularization": regularization,
        "validation": scores(outcomes, predictions, weights),
        "state_only_baseline_validation": scores(outcomes, baseline, weights),
        "group_diagnostics": diagnostics,
    }
    return artifact


def run(survey, output):
    if output.exists():
        raise ValueError("Refusing to overwrite an existing model review")
    values, outcomes, weights, groups, audit = read_survey(survey)
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for name, party, regularization in [
        ("registered-party-and-primary", True, 1.0),
        ("primary-without-registration-party", False, 1.0),
        ("stronger-regularization", True, 0.1),
        ("weaker-regularization", True, 10.0),
    ]:
        result = fit_model(values, outcomes, weights, groups, party, regularization)
        result["model"] = name
        results.append(result)
        print(json.dumps({"model": name, "held_out": result["validation"],
                          "state_only_baseline": result["state_only_baseline_validation"]}), flush=True)
    artifact = {
        "status": "historical_choice_model_only_not_2026_attribution",
        "source_sha256": hashlib.sha256(survey.read_bytes()).hexdigest(),
        "software": {"numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "source_audit": audit, "state_count": len({row["state"] for row in values}),
        "seed": SEED, "validation_design": "Five county-group held-out folds; survey weights normalized within fit",
        "limitations": [
            "Survey weights use election outcomes; weighted agreement is not independent validation.",
            "Respondents report vote choice; administrative matching validates turnout, not candidate choice.",
            "Registration measured at survey voter-file matching is not necessarily registration on election day.",
            "Unspecified survey registration is not an observed unaffiliated party label.",
            "Current voter attributes may differ from 2024 attributes; application requires sensitivity.",
            "This model alone does not estimate 2026 turnout, subgroup choices or individual transitions.",
            "Sex/gender, education and income are not predictors in this administrative-compatible first model.",
        ],
        "models": results,
    }
    mixtures = {}
    for row, weight in zip(values, weights):
        for state in [row["state"], "US"]:
            for race in [row["source_race"], "All"]:
                key = (state, race)
                bucket = mixtures.setdefault(key, Counter())
                bucket[row["race_ethnicity"]] += weight
    artifact["demographic_mixtures"] = [
        {"state": state, "survey_race_code": race,
         "probabilities": {group: weight / sum(counts.values()) for group, weight in sorted(counts.items())}}
        for (state, race), counts in sorted(mixtures.items())
    ]
    (output / "historical-choice-model.json").write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({"states": artifact["state_count"], "respondents": len(values), "complete": True}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.survey, args.output)

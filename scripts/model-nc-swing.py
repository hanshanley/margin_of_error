"""Experimental, assumption-conditioned county transitions; not observed individual switching."""

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, least_squares
from scipy.special import expit, softmax
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression

SPEC = importlib.util.spec_from_file_location("choice", Path(__file__).with_name("fit-historical-choice.py"))
choice = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(choice)
STATES = ["D", "R", "O", "B", "N", "X"]
COMPONENTS = ["switching", "dropoff", "new_returning", "other_and_contest", "eligibility_residence"]
RACES = {"W": "1", "WHITE": "1", "B": "2", "BLACK or AFRICAN AMERICAN": "2",
         "A": "4", "ASIAN": "4", "I": "5", "INDIAN AMERICAN or ALASKA NATIVE": "5",
         "M": "6", "TWO or MORE RACES": "6", "O": "7", "OTHER": "7",
         "P": "7", "NATIVE HAWAIIAN or PACIFIC ISLANDER": "7"}
NATIVE_RACE_LABELS = {"W": "WHITE", "B": "BLACK or AFRICAN AMERICAN", "A": "ASIAN",
                     "I": "INDIAN AMERICAN or ALASKA NATIVE", "M": "TWO or MORE RACES",
                     "O": "OTHER", "P": "NATIVE HAWAIIAN or PACIFIC ISLANDER", "U": "UNDESIGNATED"}


def demographic_value(cell, field):
    value = cell[field]
    mappings = {"race": NATIVE_RACE_LABELS,
                "ethnicity": {"HL": "HISPANIC or LATINO", "NL": "NOT HISPANIC or NOT LATINO", "UN": "UNDESIGNATED"},
                "gender": {"F": "FEMALE", "M": "MALE", "U": "UNDESIGNATED"}}
    return mappings.get(field, {}).get(value, value)


def harmonized(cell):
    race = RACES.get(cell["race"], "All")
    ethnicity = {"HL": "1", "HISPANIC or LATINO": "1",
                 "NL": "2", "NOT HISPANIC or NOT LATINO": "2"}.get(cell["ethnicity"], "Unknown")
    party = cell["registered_party_2026"]
    party = party if party in {"DEM", "REP"} else "Unspecified" if party in {"UNA", "Unknown"} else "Other"
    primary = cell["primary_2024"]
    primary = primary if primary in {"DEM", "REP", "No matched primary"} else (
        "Unspecified search" if primary == "History coverage incomplete" else "Other")
    return race, ethnicity, party, primary


def predict_choice(cells, artifact, model, entrant=False, ethnicity_sensitivity="mixture"):
    feature_index = {name: index for index, name in enumerate(model["features"])}
    coefficients, intercepts = np.asarray(model["coefficients"]), np.asarray(model["intercepts"])
    mixtures = {(row["state"], row["survey_race_code"]): row["probabilities"]
                for row in artifact["demographic_mixtures"]}
    predictions = []
    for cell in cells:
        race, ethnicity, party, primary = harmonized(cell)
        if ethnicity == "1":
            distribution = {"Hispanic": 1.}
        elif ethnicity == "2" and race != "All":
            distribution = {choice.race_ethnicity(race, "2"): 1.}
        else:
            distribution = mixtures.get(("NC", race), mixtures[("US", race)])
            if ethnicity == "2":
                distribution = {key: value for key, value in distribution.items() if key != "Hispanic"}
            if ethnicity_sensitivity == "all_non_hispanic" and ethnicity == "Unknown":
                distribution = {key: value for key, value in distribution.items() if key != "Hispanic"}
            if ethnicity_sensitivity == "all_hispanic" and ethnicity == "Unknown":
                distribution = {"Hispanic": 1.}
            total = sum(distribution.values())
            if not total:
                raise ValueError("Unsupported missing-demographic mixture")
            distribution = {key: value / total for key, value in distribution.items()}
        combined = np.zeros(3)
        for group, fraction in distribution.items():
            values = {"state": "NC", "age": cell["age_2026"] if entrant else cell["age_2024"],
                      "race_ethnicity": group, "registered_party": party, "primary_party": primary}
            features = choice.predictor_features(values, model["include_registration_party"])
            indices = [feature_index[f"{key}={value}"] for key, value in features.items()
                       if f"{key}={value}" in feature_index]
            logits = intercepts + coefficients[:, indices].sum(axis=1)
            combined += fraction * softmax(logits)
        predictions.append(combined)
    return np.asarray(predictions)


def calibrate(priors, weights, target):
    priors, weights, target = np.asarray(priors), np.asarray(weights), np.asarray(target)
    if (np.any(weights < 0) or not np.isfinite(weights).all() or not np.isfinite(target).all()
            or np.any(target < 0) or not np.isfinite(priors).all() or np.any(priors < 0)):
        raise ValueError("Invalid choice calibration input")
    if not np.isclose(target.sum(), weights.sum(), rtol=0, atol=1e-5):
        raise ValueError("Calibration populations disagree")
    active = np.flatnonzero(target > 0)
    if not len(active):
        raise ValueError("Empty vote universe")
    logits = np.log(np.clip(priors[:, active], 1e-12, None))
    shares = target[active] / target.sum()

    def adjusted(parameters):
        return softmax(logits + np.r_[parameters, 0.], axis=1)

    if len(active) > 1:
        result = least_squares(
            lambda parameters: ((weights[:, None] * adjusted(parameters)).sum(axis=0) / weights.sum() - shares)[:-1],
            np.zeros(len(active) - 1), ftol=1e-13, xtol=1e-13, gtol=1e-13, max_nfev=500)
        probabilities = adjusted(result.x)
    else:
        probabilities = np.ones((len(weights), 1))
    output = np.zeros_like(priors)
    output[:, active] = probabilities
    if np.max(np.abs((weights[:, None] * output).sum(axis=0) - target)) > 1e-3:
        raise ValueError("Choice margins failed to reconcile")
    return output


def turnout_features(cell, year, baseline_year):
    _, _, party, _ = harmonized(cell)
    prior = cell[f"prior_{baseline_year}_history"]
    if baseline_year == 2024:
        prior = (True if prior == "Positive 2024 NC history" else
                 False if cell["historical_search_complete"] else None)
    return {"age": cell[f"age_{year}"], "race_source": RACES.get(cell["race"], "Unspecified"),
            "registered_party": party, "prior_general": str(prior)}


def historical_turnout(cells):
    def eligible(year, baseline):
        return [cell for cell in cells if cell["registration_status_2026"] in {"ACTIVE", "INACTIVE"}
                and cell[f"registration_by_{baseline}"] is True and cell["historical_search_complete"]
                and cell[f"age_{year}"] not in {"Under 18", "Unknown"}]

    def train(rows, year, baseline):
        features = [turnout_features(row, year, baseline) for row in rows]
        labels = np.asarray([int(row[f"prior_{year}_history"]) for row in rows])
        weights = np.asarray([row["records"] for row in rows], dtype=float)
        if weights.sum() < 1000 or len(set(labels)) != 2:
            raise ValueError("Insufficient historical turnout model support")
        encoder = DictVectorizer()
        matrix = encoder.fit_transform(features)
        model = LogisticRegression(C=1., max_iter=3000, tol=1e-7)
        model.fit(matrix, labels, sample_weight=weights / weights.mean())
        return encoder, model

    training = eligible(2018, 2016)
    validation = eligible(2022, 2020)
    encoder, fitted = train(training, 2018, 2016)
    target = np.asarray([int(row["prior_2022_history"]) for row in validation])
    weights = np.asarray([row["records"] for row in validation], dtype=float)
    predictions = fitted.predict_proba(encoder.transform([turnout_features(row, 2022, 2020) for row in validation]))[:, 1]
    historical_rate = sum(row["records"] * row["prior_2018_history"] for row in training) / sum(row["records"] for row in training)
    diagnostics = {
        "training_2018_registered_records": sum(row["records"] for row in training),
        "validation_2022_registered_records": int(weights.sum()),
        "validation_brier": float(np.average((predictions - target) ** 2, weights=weights)),
        "historical_rate_baseline_brier": float(np.average((historical_rate - target) ** 2, weights=weights)),
        "validation_calibration_error_pp": float(100 * np.average(predictions - target, weights=weights)),
        "scope": "Retrospective prediction in the surviving current-registration panel, not independent 2026 validation",
    }
    logits = np.log(np.clip(predictions, 1e-9, 1 - 1e-9) / np.clip(1 - predictions, 1e-9, 1))
    target_rate = np.average(target, weights=weights)
    adjustment = brentq(lambda value: np.average(expit(logits + value), weights=weights) - target_rate, -40, 40)
    conditioned = expit(logits + adjustment)
    diagnostics.update({
        "known_2022_total_conditioned_brier": float(np.average((conditioned - target) ** 2, weights=weights)),
        "known_2022_total_constant_baseline_brier": float(np.average((target_rate - target) ** 2, weights=weights)),
        "known_total_conditioning_log_odds_adjustment": float(adjustment),
        "known_total_conditioning_note": "Uses only the observed overall 2022 participation total; matching that total is a constraint, not independent calibration evidence",
    })
    diagnostics["groups"] = []
    for field in ["age_2022", "race", "registered_party_2026", "gender"]:
        values = [demographic_value(row, field) for row in validation]
        for group in sorted(set(values)):
            selected = np.asarray([value == group for value in values])
            diagnostics["groups"].append({
                "field": field, "group": group, "registered_records": int(weights[selected].sum()),
                "observed_2022_participation_rate_pct": float(100 * np.average(target[selected], weights=weights[selected])),
                "raw_temporal_calibration_error_pp": float(100 * np.average(predictions[selected] - target[selected], weights=weights[selected])),
                "known_total_conditioned_calibration_error_pp": float(100 * np.average(conditioned[selected] - target[selected], weights=weights[selected])),
            })
    encoder, fitted = train(validation, 2022, 2020)
    probabilities = fitted.predict_proba(encoder.transform([turnout_features(row, 2026, 2024) for row in cells]))[:, 1]
    return probabilities, diagnostics


def late_membership(cells, historical_probabilities, target_ballots, exit_fraction, partisan_offset):
    counts = np.asarray([row["records"] for row in cells], dtype=float)
    early = np.asarray([row["cohort_membership_2026"].startswith("Accepted") for row in cells])
    baseline = np.asarray([row["baseline_2024_voted_county"] for row in cells])
    current = np.asarray([row["registration_status_2026"] in {"ACTIVE", "INACTIVE"} for row in cells])
    exit_probability = np.where(baseline & ~current & ~early, exit_fraction, 0.)
    adult = np.asarray([row.get("age_2026") != "Under 18" or row.get("prior_2024_history") == "Positive 2024 NC history"
                        for row in cells])
    capacity = (1 - exit_probability) * ~early * adult
    remaining = target_ballots - (counts * early).sum()
    if remaining < 0 or remaining > (counts * capacity).sum():
        raise ValueError("Infeasible all-mode cohort/ballot calibration")
    probabilities = np.clip(historical_probabilities, 1e-6, 1 - 1e-6)
    logits = np.log(probabilities / (1 - probabilities))
    logits += np.asarray([partisan_offset * (1 if harmonized(row)[2] == "REP" else -1
                         if harmonized(row)[2] == "DEM" else 0) for row in cells])
    offset = brentq(lambda value: (counts * capacity * expit(logits + value)).sum() - remaining, -40, 40)
    membership = early.astype(float) + capacity * expit(logits + offset)
    return membership, exit_probability


def component(from_state, to_state):
    if "X" in {from_state, to_state}:
        return 4
    if from_state != to_state and from_state in {"D", "R"} and to_state in {"D", "R"}:
        return 0
    if from_state in {"D", "R"} and to_state == "N":
        return 1
    if from_state == "N" and to_state in {"D", "R"}:
        return 2
    return 3


def shapley_coefficients(before, changes):
    nodes, weights = np.polynomial.legendre.leggauss(24)
    nodes, weights = (nodes + 1) / 2, weights / 2
    coefficients = np.zeros((len(changes), 2))
    for selected in range(len(changes)):
        others = [index for index in range(len(changes)) if index != selected]
        for length in range(len(others) + 1):
            weight = math.factorial(length) * math.factorial(len(others) - length) / math.factorial(len(changes))
            for subset in itertools.combinations(others, length):
                start = np.asarray(before, dtype=float) + changes[list(subset)].sum(axis=0)
                path = start + nodes[:, None] * changes[selected]
                if np.any(path.sum(axis=1) <= 0):
                    raise ValueError("Undefined counterfactual two-party denominator")
                gradient = 200 * np.column_stack([path[:, 1], -path[:, 0]]) / np.square(path.sum(axis=1))[:, None]
                coefficients[selected] += weight * (weights[:, None] * gradient).sum(axis=0)
    return coefficients


def accounting(flows):
    total = flows.sum(axis=0)
    before, after = total.sum(axis=1), total.sum(axis=0)
    changes = np.zeros((len(flows), len(COMPONENTS), 2))
    for source, destination in itertools.product(range(6), repeat=2):
        delta = np.asarray([int(destination == 0) - int(source == 0),
                            int(destination == 1) - int(source == 1)])
        changes[:, component(STATES[source], STATES[destination])] += flows[:, source, destination, None] * delta
    group_changes = changes.sum(axis=0)
    coefficients = shapley_coefficients(before[:2], group_changes)
    contributions = (changes * coefficients).sum(axis=2)
    swing = 100 * ((after[0] - after[1]) / (after[0] + after[1]) -
                   (before[0] - before[1]) / (before[0] + before[1]))
    if not np.isclose(contributions.sum(), swing, atol=1e-7):
        raise ValueError("Counterfactual contributions do not reconcile to observed swing")
    return contributions, {
        "before": dict(zip(STATES, before.tolist())), "after": dict(zip(STATES, after.tolist())),
        "swing_margin_pp": float(swing),
        "margin_pp_contributions": dict(zip(COMPONENTS, contributions.sum(axis=0).tolist())),
        "signed_share_of_swing_pct": dict(zip(COMPONENTS, (100 * contributions.sum(axis=0) / swing).tolist()))
        if abs(swing) >= 1 else dict.fromkeys(COMPONENTS),
        "gross_major_party_switchers": float(total[0, 1] + total[1, 0]),
    }


def cohort_counts(total, known_incoming, newly_adult, unresolved):
    return {
        "repeat_2024_county_participants": float(total[:4, :4].sum()),
        "prior_county_participants_now_nonvoting": float(total[:4, 4].sum()),
        "prior_county_participants_eligibility_residence_exit": float(total[:4, 5].sum()),
        "participants_without_2024_county_participation": float(total[4:, :4].sum()),
        "participants_with_2024_history_elsewhere_in_nc": float(known_incoming),
        "participants_newly_adult_since_2024": float(newly_adult),
        "participants_without_2024_nc_history_national_status_unresolved": float(unresolved),
        "republican_to_democratic": float(total[1, 0]),
        "democratic_to_republican": float(total[0, 1]),
    }


def scenario(cells, prior_choices, entry_choices, turnout, before_votes, after_votes,
             before_ballots, after_ballots, loyalty=.95, exit_fraction=1., partisan_offset=0.,
             unresolved_mover_fraction=.25, group_participation=False):
    counts = np.asarray([row["records"] for row in cells], dtype=float)
    baseline = np.asarray([row["baseline_2024_voted_county"] for row in cells])
    prior = prior_choices.copy()
    before_blank = 1 - before_votes.sum() / before_ballots
    after_blank = 1 - after_votes.sum() / after_ballots
    if not 0 <= before_blank < 1 or not 0 <= after_blank < 1:
        raise ValueError("Candidate votes exceed participation")
    prior[baseline] = calibrate(prior[baseline], counts[baseline], before_votes / before_votes.sum() * before_ballots)
    old_choices = np.column_stack([prior * (1 - before_blank), np.full(len(cells), before_blank)])
    membership, exits = late_membership(cells, turnout, after_ballots, exit_fraction, partisan_offset)
    kernel = np.array([[loyalty, (1 - loyalty) * .75, (1 - loyalty) * .25],
                       [(1 - loyalty) * .75, loyalty, (1 - loyalty) * .25], [.25, .25, .5]])
    choice_prior = np.broadcast_to(kernel, (len(cells), 3, 3)).copy()
    choice_prior = np.concatenate([choice_prior, prior[:, None, :], entry_choices[:, None, :]], axis=1)
    choice_weights = np.zeros((len(cells), 5))
    choice_weights[:, :4] = counts[:, None] * baseline[:, None] * old_choices * membership[:, None] * (1 - after_blank)
    choice_weights[:, 4] = counts * ~baseline * membership * (1 - after_blank)
    fitted_choice = calibrate(choice_prior.reshape(-1, 3), choice_weights.ravel(), after_votes).reshape(-1, 5, 3)
    flows = np.zeros((len(cells), 6, 6))
    for source in range(4):
        mass = counts * baseline * old_choices[:, source]
        flows[:, source, :3] = mass[:, None] * membership[:, None] * (1 - after_blank) * fitted_choice[:, source]
        flows[:, source, 3] = mass * membership * after_blank
        flows[:, source, 4] = mass * (1 - membership - exits)
        flows[:, source, 5] = mass * exits
    known_incoming = np.asarray([row["prior_2024_history"] == "Positive 2024 NC history" for row in cells])
    newly_eligible = np.asarray([row["age_2024"] == "Under 18 in 2024" for row in cells])
    incoming_fraction = np.where(known_incoming | newly_eligible, 1., unresolved_mover_fraction)
    for source, fraction in [(4, 1 - incoming_fraction), (5, incoming_fraction)]:
        mass = counts * ~baseline * fraction
        flows[:, source, :3] = mass[:, None] * membership[:, None] * (1 - after_blank) * fitted_choice[:, 4]
        flows[:, source, 3] = mass * membership * after_blank
        flows[:, source, 4] = mass * (1 - membership)
    if np.min(flows) < -1e-8 or not np.allclose(flows.sum(axis=(1, 2)), counts):
        raise ValueError("Invalid individual-cell flow accounting")
    contributions, result = accounting(flows)
    total = flows.sum(axis=0)
    known_mass = counts * ~baseline * membership * known_incoming
    adult_mass = counts * ~baseline * membership * newly_eligible
    unresolved_mass = counts * ~baseline * membership * ~known_incoming * ~newly_eligible
    result["modeled_cohort_counts"] = cohort_counts(
        total, known_mass.sum(), adult_mass.sum(), unresolved_mass.sum())
    result["assumptions"] = dict(loyalty=loyalty, exit_fraction=exit_fraction,
                                 republican_vs_democratic_late_log_odds_offset=partisan_offset,
                                 unresolved_mover_fraction=unresolved_mover_fraction)
    groups = []
    for dimension, field in [("overall", None), ("age_2024", "age_2024"), ("race", "race"),
                             ("ethnicity", "ethnicity"), ("administrative_gender", "gender")]:
        for group in sorted({demographic_value(row, field) for row in cells} if field else {"All groups"}):
            selected = np.asarray([demographic_value(row, field) == group for row in cells]) if field else np.ones(len(cells), dtype=bool)
            groups.append({"dimension": dimension, "group": group,
                           "registered_or_baseline_records": int(counts[selected].sum()),
                           "modeled_2026_participants": float((counts[selected] * membership[selected]).sum()),
                           "margin_pp_contributions": dict(zip(COMPONENTS, contributions[selected].sum(axis=0).tolist()))})
            if group_participation:
                group_total = flows[selected].sum(axis=0)
                groups[-1].update({
                    "modeled_2024_county_participants": float(group_total[:4].sum()),
                    "modeled_cohort_counts": cohort_counts(
                        group_total, known_mass[selected].sum(), adult_mass[selected].sum(),
                        unresolved_mass[selected].sum()),
                    "modeled_prior_choice_transitions": {
                        party: {
                            "original_2024_county_presidential_voters": float(group_total[source].sum()),
                            **dict(zip(STATES, group_total[source].tolist())),
                        } for source, party in enumerate(["D", "R"])
                    },
                    "group_turnout_rate_pct": None,
                    "measured_staying_home_count": None,
                })
    result["demographics"] = groups
    return result


def reconcile_source_ages(cells):
    resolved = []
    records = baseline_records = changed_cells = 0
    for cell in cells:
        histories = [year for year in (2016, 2018, 2020, 2022)
                     if cell.get(f"prior_{year}_history") is True]
        if (cell.get("baseline_2024_voted_county")
                or cell.get("prior_2024_history") == "Positive 2024 NC history"):
            histories.append(2024)
        if cell.get("positive_2026_history") is True:
            histories.append(2026)
        conflict = any(
            cell.get(f"age_{year}") in {"Under 18", "Under 18 in 2024"}
            and any(history <= year for history in histories)
            for year in (2018, 2022, 2024, 2026))
        if conflict:
            records += cell["records"]
            baseline_records += cell["records"] if cell.get("baseline_2024_voted_county") else 0
            changed_cells += 1
            cell = {**cell, **{f"age_{year}": "Unknown" for year in (2018, 2022, 2024, 2026)}}
        resolved.append(cell)
    audit = None if not changed_cells else {
        "conflicting_source_records": records,
        "conflicting_source_cells": changed_cells,
        "baseline_2024_records_retained": baseline_records,
        "rule": "Positive general-election history incompatible with a later under-18 age label makes all age predictors unknown; participation and original source cells are retained.",
    }
    return resolved, audit


def run(cells_path, model_path, candidates_path, participation_path, output,
        county="DURHAM", linkage_audit=None):
    if output.exists():
        raise ValueError("Refusing to overwrite an existing transition review")
    if not county or county != county.strip().upper():
        raise ValueError("Use the literal uppercase source county")
    if county != "DURHAM" and linkage_audit is None:
        raise ValueError("A hash-bound linkage audit is required for another county")
    cells = json.loads(cells_path.read_text())
    if linkage_audit is not None:
        audit = json.loads(linkage_audit.read_text())
        if (audit["state_code"] != "NC" or audit["county"] != county
                or audit["joint_cells_sha256"] != hashlib.sha256(cells_path.read_bytes()).hexdigest()
                or audit["aggregate_cells"] != len(cells)
                or any(type(row["records"]) is not int or row["records"] <= 0 for row in cells)
                or sum(row["records"] for row in cells if row["baseline_2024_voted_county"])
                != audit["history"]["baseline_county_2024_unique_identifiers"]
                or sum(row["records"] for row in cells if row["cohort_membership_2026"].startswith("Accepted"))
                != audit["accepted_cohort"]["unambiguous_records"]):
            raise ValueError("County linkage audit, hash or population controls do not match")
    source_age_handling = None
    if county != "DURHAM":
        cells, source_age_handling = reconcile_source_ages(cells)
    artifact = json.loads(model_path.read_text())
    candidates = json.loads(candidates_path.read_text())
    participation = json.loads(participation_path.read_text())
    reporting = [row for row in participation["reporting"] if row["county"] == county]
    if (participation["state"] != "North Carolina" or participation["election_date"] != "2026-11-03"
            or len(reporting) != 1 or type(reporting[0]["ballots_cast"]) is not int
            or reporting[0]["ballots_cast"] <= 0):
        raise ValueError("Missing or conflicting county participation scope")
    reported = reporting[0]

    def votes(year, contest):
        rows = [row for row in candidates if row["county"] == county and row["year"] == year
                and row["contest"] == contest and row["method"] == "Total Votes"]
        counts = [sum(row["votes"] for row in rows if row["party_literal"] == party) for party in ["DEM", "REP"]]
        return np.asarray([*counts, sum(row["votes"] for row in rows) - sum(counts)], dtype=float)

    before_votes, after_votes = votes(2024, "US PRESIDENT"), votes(2026, "US SENATE")
    before_ballots = sum(row["records"] for row in cells if row["baseline_2024_voted_county"])
    if not np.all(before_votes > 0) or not np.all(after_votes > 0):
        raise ValueError("Missing or unusable contest input")
    turnout, turnout_diagnostics = historical_turnout(cells)
    results = []
    priors = {}
    for model in artifact["models"]:
        priors[model["model"]] = (predict_choice(cells, artifact, model),
                                  predict_choice(cells, artifact, model, entrant=True))
    base_prior, base_entry = priors["registered-party-and-primary"]
    group_participation = county != "DURHAM"
    for loyalty, exit_fraction, partisan_offset, movers in itertools.product(
            [.8, .95, .99], [0., .5, 1.], [-.5, 0., .5], [0., .25, 1.]):
        result = scenario(cells, base_prior, base_entry, turnout, before_votes, after_votes,
                          before_ballots, reported["ballots_cast"], loyalty, exit_fraction, partisan_offset, movers,
                          group_participation=group_participation)
        result["historical_choice_model"] = "registered-party-and-primary"
        results.append(result)
    for name, (prior, entry) in priors.items():
        if name != "registered-party-and-primary":
            result = scenario(cells, prior, entry, turnout, before_votes, after_votes,
                              before_ballots, reported["ballots_cast"], group_participation=group_participation)
            result["historical_choice_model"] = name
            results.append(result)
    for sensitivity in ["all_non_hispanic", "all_hispanic"]:
        prior = predict_choice(cells, artifact, artifact["models"][0], ethnicity_sensitivity=sensitivity)
        entry = predict_choice(cells, artifact, artifact["models"][0], entrant=True, ethnicity_sensitivity=sensitivity)
        result = scenario(cells, prior, entry, turnout, before_votes, after_votes, before_ballots, reported["ballots_cast"],
                          group_participation=group_participation)
        result["unknown_ethnicity_sensitivity"] = sensitivity
        results.append(result)
    default = next(row for row in results if row["assumptions"] == dict(
        loyalty=.95, exit_fraction=1., republican_vs_democratic_late_log_odds_offset=0., unresolved_mover_fraction=.25))
    intervals = {key: {"minimum": min(row["margin_pp_contributions"][key] for row in results),
                       "maximum": max(row["margin_pp_contributions"][key] for row in results)}
                 for key in COMPONENTS}
    demographic_ranges = []
    for group in default["demographics"]:
        matches = [next(item for item in row["demographics"] if item["dimension"] == group["dimension"]
                        and item["group"] == group["group"]) for row in results]
        demographic_ranges.append({
            "dimension": group["dimension"], "group": group["group"],
            "margin_pp_contributions": {
                key: {"minimum": min(item["margin_pp_contributions"][key] for item in matches),
                      "maximum": max(item["margin_pp_contributions"][key] for item in matches)}
                for key in COMPONENTS},
        })
        if group_participation:
            demographic_ranges[-1].update({
                key: {"minimum": min(item[key] for item in matches),
                      "maximum": max(item[key] for item in matches)}
                for key in ["modeled_2024_county_participants", "modeled_2026_participants"]
            })
            demographic_ranges[-1]["modeled_cohort_counts"] = {
                key: {"minimum": min(item["modeled_cohort_counts"][key] for item in matches),
                      "maximum": max(item["modeled_cohort_counts"][key] for item in matches)}
                for key in group["modeled_cohort_counts"]
            }
            demographic_ranges[-1]["modeled_prior_choice_transitions"] = {
                party: {
                    key: {"minimum": min(item["modeled_prior_choice_transitions"][party][key] for item in matches),
                          "maximum": max(item["modeled_prior_choice_transitions"][party][key] for item in matches)}
                    for key in group["modeled_prior_choice_transitions"][party]
                } for party in ["D", "R"]
            }
    result = {
        "status": "experimental_conditional_model_not_individually_identified",
        "state": "NC", "county": county, "baseline_contest": "2024 President", "outcome_contest": "2026 Senate",
        "validated_individual_attribution": False, "scenario_count": len(results),
        "default_conditional_scenario": default, "sensitivity_range_margin_pp": intervals,
        "demographic_sensitivity_range_margin_pp": demographic_ranges,
        "uncertainty_type": "Assumption sensitivity, NOT a confidence or identification interval",
        "turnout_temporal_diagnostics": turnout_diagnostics,
        "normalization": "Exact five-component Shapley attribution of two-party margin; signed percentages, suppressed below 1 pp net swing",
        "limitations": [
            "Neither the registered-population model nor its latent transitions are observed 2026 individual histories.",
            "Late participation is modeled from retrospective historical midterms and raked to provisional all-mode ballots.",
            "Current registration predates Election Day; neither absence nor REMOVED proves an eligibility/residence exit.",
            "Unmatched 2024 NC history includes unresolved interstate participants; the mover fraction is an assumption.",
            "Conditional independence of turnout and prior choice within administrative cells is unvalidated.",
            f"Known prior votes outside {county.title()} enter the geographic component, not new nationwide voters.",
            "Voters under 18 throughout 2024 enter the eligibility component, never the prior-eligible-nonvoter component.",
            "The historical choice model is calibrated to county 2024 totals; that is not independent validation.",
            "A common choice-tilt calibrates entropy-regularized transitions to 2026 totals; aggregate fit cannot validate switching.",
            "Contest abstention is assumed uniform within each year; other choices and contest effects stay separate.",
            "Cohort and results snapshots have different clocks; accepted membership is a modeling constraint, not a proven counted-cohort match.",
            "Administrative gender is not survey gender; it is an output partition, not a survey-gender predictor.",
            "Education, income and residence-type estimates are unavailable in these administrative inputs.",
            "Small joint cells and person-level scores are not included in the exported model results.",
            "No nationwide transition estimate follows from this county pilot.",
        ],
        "inputs": [{"role": role, "file": path.name, "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                   for role, path in [("private_aggregate_cells", cells_path), ("fitted_choice_models", model_path),
                                      ("complete_candidate_methods", candidates_path), ("participation_snapshot", participation_path)]],
        "scenarios": results,
    }
    if source_age_handling is not None:
        result["source_age_handling"] = source_age_handling
        result["limitations"].append(source_age_handling["rule"])
    if linkage_audit is not None:
        result["inputs"].append({
            "role": "county_linkage_audit", "file": linkage_audit.name,
            "bytes": linkage_audit.stat().st_size,
            "sha256": hashlib.sha256(linkage_audit.read_bytes()).hexdigest(),
        })
    if group_participation:
        result["limitations"].append(
            "Demographic participation and prior-choice flows are conditional model counts using current administrative attributes and age in 2024, not observed fixed-attribute historical cohorts or eligible-population turnout rates.")
    output.mkdir(parents=True, exist_ok=False)
    (output / "conditional-transitions.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key not in {"scenarios", "inputs"}}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["cells", "choice-model", "candidates", "participation", "output"]:
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--county", default="DURHAM")
    parser.add_argument("--linkage-audit", type=Path)
    args = parser.parse_args()
    run(args.cells, args.choice_model, args.candidates, args.participation, args.output,
        county=args.county, linkage_audit=args.linkage_audit)

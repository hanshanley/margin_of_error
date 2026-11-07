"""Reproduce selected conditional county scenarios without publishing private model cells."""

import argparse
import copy
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-county-scenarios/{VERSION}"
PUBLIC = f"public/participation-county-scenarios/{VERSION}"
PINS = {
    "accounting-proof.json": "4b030fc073a5f7293228aba47ecaa37f273b4a897b94a9730b0cf05414424935",
    "linkage-audit.json": "ed5542efe41c02cd4730cfdd724a65ddffe364156a9a90cacc8febb08b6b3a81",
    "methodology-review.json": "2fa0bc4f350be181b2015d0de1bce7a83781c905bdaaf54aabe85b675dbd5c4b",
    "selected-scenarios.json": "2413ded08e9cbc47c1c9fe0a3657a8623e461ccba5d75c4f0e23b9e4d40b7cbb",
}
RELEASES = {
    VERSION: {"county": "WAKE", "pins": PINS},
    "20261107-02": {
        "county": "MECKLENBURG",
        "pins": {
            "accounting-proof.json": "b15d61950ef69bc23b7929a4ffdb53256ae7bddaa10183e5c4791a91dd0dddbd",
            "linkage-audit.json": "f7ab5f193427d150eb691a0e1024560469f2e6cfb8404c7cc741fa0bba1b5a7c",
            "methodology-review.json": "696e8580881d5b2f5785173c3ca1d86c9de351be9d7be0904ad59b4816a2e691",
            "selected-scenarios.json": "24dbbd9c7615be09f5503ee401045327fe17bb1c4c2686a352a613622098941f",
        },
    },
}
COMPONENTS = ("switching", "dropoff", "new_returning", "other_and_contest", "eligibility_residence")
STATES = ("D", "R", "O", "B", "N", "X")
ACTIVITY = (
    "repeat_2024_county_participants", "prior_county_participants_now_nonvoting",
    "prior_county_participants_eligibility_residence_exit", "participants_without_2024_county_participation",
    "participants_with_2024_history_elsewhere_in_nc", "participants_newly_adult_since_2024",
    "participants_without_2024_nc_history_national_status_unresolved",
    "republican_to_democratic", "democratic_to_republican",
)
FORBIDDEN_CLAIMS = (
    "validated_individual_attribution", "demographic_turnout_rates_available",
    "design_confidence_intervals_available", "individual_records_or_fine_cells_released",
    "downward_geographic_allocation_permitted",
)
INPUTS = (
    "data/participation-swing/20261106-conditional-model-01/historical-choice-model.json",
    "data/participation-swing/20261106-candidate-scope-01/county-contest-methods.json",
    "public/voter-participation/data/current/20261104T152627Z/snapshot.json",
)


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("Missing or unexpected fields in selected county inputs")


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("County counts must be finite numbers, not booleans")
    return value


def close(actual, expected):
    if abs(number(actual) - number(expected)) > .001:
        raise ValueError("Selected county participation or transition accounting differs")


def review(snapshot, methods, proof, version=VERSION):
    release = RELEASES[version]
    fields(snapshot, (
        "status", "state", "county", "baseline_contest", "outcome_contest",
        "validated_individual_attribution", "scenario_count", "default_conditional_scenario",
        "sensitivity_range_margin_pp", "demographic_sensitivity_range_margin_pp",
        "uncertainty_type", "turnout_temporal_diagnostics", "normalization", "limitations",
        "inputs", "scenarios", "withheld_demographic_groups", "selection_provenance",
    ))
    fields(methods, (
        "status", "state", "county", "selection_basis", "selected_groups", "estimand",
        "historical_attributes", "population", "membership", "model", "diagnostics",
        "uncertainty", "limits", "reproduction", "attribution", *FORBIDDEN_CLAIMS,
    ))
    fields(snapshot["selection_provenance"], (
        "private_model_sha256", "independent_accounting_proof_sha256",
        "independent_native_control_proof_sha256", "estimator_commit", "scope",
    ))
    for receipt in snapshot["inputs"]:
        fields(receipt, ("role", "file", "bytes", "sha256"))
    fields(snapshot["turnout_temporal_diagnostics"], (
        "training_2018_registered_records", "validation_2022_registered_records",
        "validation_brier", "historical_rate_baseline_brier", "validation_calibration_error_pp",
        "scope", "known_2022_total_conditioned_brier", "known_2022_total_constant_baseline_brier",
        "known_total_conditioning_log_odds_adjustment", "known_total_conditioning_note",
        "known_total_conditioned_max_group_error_pp_n_at_least_100",
    ))
    for row in snapshot["withheld_demographic_groups"]:
        fields(row, ("dimension", "group", "reason"))
    if (methods["status"] != "qualified_only_for_conditional_broad_aggregate_scenarios"
            or any(methods[key] is not False for key in FORBIDDEN_CLAIMS)
            or snapshot["state"] != methods["state"] or snapshot["county"] != methods["county"]
            or snapshot["county"] != release["county"] or snapshot["state"] != "NC"
            or snapshot["validated_individual_attribution"] is not False
            or snapshot["status"] != "experimental_conditional_model_not_individually_identified"
            or snapshot["uncertainty_type"] != "Assumption sensitivity, NOT a confidence or identification interval"):
        raise ValueError("Conditional county scope or qualification changed")
    if (proof["status"] != "independent_decimal_accounting_and_input_control_checks_pass"
            or proof["private_model_sha256"] != snapshot["selection_provenance"]["private_model_sha256"]
            or proof["all_demographic_participation_counts_prior_choice_flows_and_extrema_match"] is not True
            or proof["individual_attribution_independently_validated"] is not False
            or proof["numerical_warnings"] is not False):
        raise ValueError("Independent numerical accounting qualification is missing")
    selected = {tuple(row) for row in methods["selected_groups"]}
    if len(selected) != len(methods["selected_groups"]) or len(selected) != 12:
        raise ValueError("Reviewed broad group selection changed")
    scenarios = snapshot["scenarios"]
    if snapshot["scenario_count"] != len(scenarios) or len(scenarios) != 86:
        raise ValueError("Require all 86 conditional scenarios")
    grid = set()
    for scenario in scenarios:
        fields(scenario, (
            "before", "after", "swing_margin_pp", "margin_pp_contributions",
            "signed_share_of_swing_pct", "gross_major_party_switchers", "modeled_cohort_counts",
            "assumptions", "demographics",
            "unknown_ethnicity_sensitivity" if "unknown_ethnicity_sensitivity" in scenario else "historical_choice_model",
        ))
        fields(scenario["before"], STATES)
        fields(scenario["after"], STATES)
        fields(scenario["modeled_cohort_counts"], ACTIVITY)
        fields(scenario["margin_pp_contributions"], COMPONENTS)
        fields(scenario["signed_share_of_swing_pct"], COMPONENTS)
        fields(scenario["assumptions"], (
            "loyalty", "exit_fraction", "republican_vs_democratic_late_log_odds_offset",
            "unresolved_mover_fraction",
        ))
        for year in ("before", "after"):
            if any(number(value) < -.000001 for value in scenario[year].values()):
                raise ValueError("Negative modeled population state")
            for key in STATES[:4]:
                close(scenario[year][key], snapshot["default_conditional_scenario"][year][key])
        close(sum(scenario["before"].values()), sum(scenario["after"].values()))
        margin = lambda year: 100 * (scenario[year]["D"] - scenario[year]["R"]) / (
            scenario[year]["D"] + scenario[year]["R"])
        close(margin("after") - margin("before"), scenario["swing_margin_pp"])
        close(scenario["swing_margin_pp"], proof["swing_margin_pp"])
        close(sum(scenario["margin_pp_contributions"].values()), scenario["swing_margin_pp"])
        close(scenario["gross_major_party_switchers"],
              sum(scenario["modeled_cohort_counts"][key] for key in ACTIVITY[-2:]))
        if scenario.get("historical_choice_model") == "registered-party-and-primary":
            grid.add(tuple(scenario["assumptions"][key] for key in (
                "loyalty", "exit_fraction", "republican_vs_democratic_late_log_odds_offset",
                "unresolved_mover_fraction")))
        groups = scenario["demographics"]
        keys = {(group["dimension"], group["group"]) for group in groups}
        if keys != selected or len(groups) != len(selected):
            raise ValueError("Missing, duplicated or unreviewed demographic groups")
        for group in groups:
            fields(group, (
                "dimension", "group", "registered_or_baseline_records", "modeled_2026_participants",
                "margin_pp_contributions", "modeled_2024_county_participants", "modeled_cohort_counts",
                "modeled_prior_choice_transitions", "group_turnout_rate_pct", "measured_staying_home_count",
            ))
            if group["group_turnout_rate_pct"] is not None or group["measured_staying_home_count"] is not None:
                raise ValueError("A modeled count is not measured nonvoting or an eligible-population turnout rate")
            fields(group["modeled_cohort_counts"], ACTIVITY)
            fields(group["margin_pp_contributions"], COMPONENTS)
            counts = group["modeled_cohort_counts"]
            if any(number(value) < -.000001 for value in counts.values()):
                raise ValueError("Negative modeled activity")
            close(counts[ACTIVITY[0]] + counts[ACTIVITY[1]] + counts[ACTIVITY[2]],
                  group["modeled_2024_county_participants"])
            close(counts[ACTIVITY[0]] + counts[ACTIVITY[3]], group["modeled_2026_participants"])
            close(sum(counts[key] for key in ACTIVITY[4:7]), counts[ACTIVITY[3]])
            fields(group["modeled_prior_choice_transitions"], ("D", "R"))
            for flows in group["modeled_prior_choice_transitions"].values():
                fields(flows, (*STATES, "original_2024_county_presidential_voters"))
                if any(number(value) < -.000001 for value in flows.values()):
                    raise ValueError("Negative modeled prior-choice flow")
                close(sum(flows[state] for state in STATES), flows["original_2024_county_presidential_voters"])
            close(group["modeled_prior_choice_transitions"]["R"]["D"], counts["republican_to_democratic"])
            close(group["modeled_prior_choice_transitions"]["D"]["R"], counts["democratic_to_republican"])
            if group["dimension"] == "overall":
                for key in ACTIVITY:
                    close(counts[key], scenario["modeled_cohort_counts"][key])
                close(group["modeled_2024_county_participants"], sum(scenario["before"][key] for key in STATES[:4]))
                close(group["modeled_2026_participants"], sum(scenario["after"][key] for key in STATES[:4]))
    if grid != set(itertools.product((.8, .95, .99), (0., .5, 1.), (-.5, 0., .5), (0., .25, 1.))):
        raise ValueError("Conditional sensitivity grid changed")
    if snapshot["default_conditional_scenario"] not in scenarios:
        raise ValueError("Reference scenario is not in the complete grid")
    ranges = snapshot["demographic_sensitivity_range_margin_pp"]
    if {(row["dimension"], row["group"]) for row in ranges} != selected or len(ranges) != len(selected):
        raise ValueError("Selected demographic sensitivity ranges differ")
    for row in ranges:
        fields(row, (
            "dimension", "group", "margin_pp_contributions", "modeled_2024_county_participants",
            "modeled_2026_participants", "modeled_cohort_counts", "modeled_prior_choice_transitions",
        ))
        fields(row["modeled_cohort_counts"], ACTIVITY)
        fields(row["margin_pp_contributions"], COMPONENTS)
        fields(row["modeled_prior_choice_transitions"], ("D", "R"))
        for flows in row["modeled_prior_choice_transitions"].values():
            fields(flows, (*STATES, "original_2024_county_presidential_voters"))
        groups = [next(group for group in scenario["demographics"]
                       if (group["dimension"], group["group"]) == (row["dimension"], row["group"]))
                  for scenario in scenarios]
        for key in ("modeled_2024_county_participants", "modeled_2026_participants"):
            values = [group[key] for group in groups]
            if row[key] != {"minimum": min(values), "maximum": max(values)}:
                raise ValueError("Demographic participation sensitivity endpoint differs")
        for category in ("modeled_cohort_counts", "margin_pp_contributions"):
            for key, extrema in row[category].items():
                values = [group[category][key] for group in groups]
                if extrema != {"minimum": min(values), "maximum": max(values)}:
                    raise ValueError("Demographic sensitivity endpoint differs")
        for party, flows in row["modeled_prior_choice_transitions"].items():
            for key, extrema in flows.items():
                values = [group["modeled_prior_choice_transitions"][party][key] for group in groups]
                if extrema != {"minimum": min(values), "maximum": max(values)}:
                    raise ValueError("Prior-choice sensitivity endpoint differs")
    for component in COMPONENTS:
        values = [scenario["margin_pp_contributions"][component] for scenario in scenarios]
        if snapshot["sensitivity_range_margin_pp"][component] != {"minimum": min(values), "maximum": max(values)}:
            raise ValueError("County sensitivity endpoint differs")
    summary = copy.deepcopy({key: value for key, value in snapshot.items() if key != "scenarios"})
    summary["version"] = version
    summary["source_qualification"] = methods
    summary["complete_selected_scenarios_in_download"] = True
    summary["demographic_partitions_exhaustive"] = False
    return summary


def package(version=VERSION):
    pins = RELEASES[version]["pins"]
    data = f"data/participation-county-scenarios/{version}"
    public = f"public/participation-county-scenarios/{version}"
    selected = {}
    for name, digest in pins.items():
        raw = (ROOT / data / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Frozen county selection changed; create a new immutable version")
        selected[name] = json.loads(raw)
    summary = review(selected["selected-scenarios.json"], selected["methodology-review.json"],
                     selected["accounting-proof.json"], version)
    snapshot = selected["selected-scenarios.json"]
    inputs = {row["sha256"]: row for row in snapshot["inputs"]}
    contents = {f"{data}/{name}": (ROOT / data / name).read_bytes() for name in pins}
    for name in INPUTS:
        raw = (ROOT / name).read_bytes()
        receipt = inputs.get(hashlib.sha256(raw).hexdigest())
        if receipt is None or receipt["bytes"] != len(raw):
            raise ValueError("Frozen public model input receipt differs")
        contents[name] = raw
    contents[f"{public}/summary.json"] = encoded(summary)
    for name in (
        "package-county-scenarios.py", "test-package-county-scenarios.py",
        "model-nc-swing.py", "test-model-nc-swing.py",
        "fit-historical-choice.py", "test-fit-historical-choice.py",
        "review-nc-linked-cohort.py", "test-review-nc-linked-cohort.py",
        "review-nc-demographic-cohort.py", "test-review-nc-demographic-cohort.py",
        "requirements-swing-model.txt",
    ):
        contents[f"scripts/{name}"] = (ROOT / "scripts" / name).read_bytes()
    contents["REPRODUCTION.txt"] = (
        "Extract preserving paths. Python>=3.9 standard library reproduces the selected release:\n"
        f"python3 scripts/test-package-county-scenarios.py --version {version}\n"
        f"python3 scripts/package-county-scenarios.py --version {version}\n"
        "Verify every checksums.json member; summary/ZIP/download metadata reproduce exactly offline.\n"
        "ALL86 full SELECTED scenarios, source receipts, full public candidate/ballot inputs,\n"
        "historical model coefficients, qualification, exact model/linkage code and tests included.\n"
        "This is NOT a fresh independent latent refit. Private native records and fine joint cells\n"
        "are deliberately excluded. Refit code requires separately held source-pinned private inputs.\n"
        "Optional numerical tests require scripts/requirements-swing-model.txt in an isolated environment.\n"
        "Run test-model-nc-swing.py and test-fit-historical-choice.py there; do not install globally.\n"
        "Selected broad demographics are NOT exhaustive partitions. Omitted categories are withheld,\n"
        "not zero. Do not recover small categories or allocate these results to other geographies.\n"
        "See methodology-review.json for substantive calibration errors and all unvalidated assumptions.\n"
        "Ranges are tested assumption sensitivity, NOT confidence intervals or identified persuasion.\n"
        "2024age/currentadministrative attributes do not establish fixed historic demographic cohorts.\n"
        "Modeled nonvoting/exit are not observed stayinghome; group turnout rates remain unknown.\n"
        "Age/race/ethnicity/gender dimensions overlap. Offices, marginal endpoints and groups across\n"
        "dimensions are not additive. Preserve other choices, contest blanks, unknowns and geography.\n"
        "NCSBE administrative sources and CES2024release9 DOI10.7910/DVN/X11EP6 CC0; no provider endorsement.\n"
    ).encode()
    contents["checksums.json"] = encoded({name: {
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in sorted(contents.items())})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, raw in sorted(contents.items()):
            member = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    raw = buffer.getvalue()
    metadata = dict(file="complete-analysis.zip", bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                    members=len(contents), full_selected_scenarios=86, selected_groups=12,
                    complete_selected_aggregate_inputs_and_code=True, private_fit_reproduced=False,
                    personal_records_included=False, fine_joint_cells_included=False)
    output = ROOT / public
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("summary.json", encoded(summary)), ("complete-analysis.zip", raw),
                        ("download.json", encoded(metadata))):
        path = output / name
        if path.exists() and path.read_bytes() != value:
            raise ValueError("Frozen county output differs; create a new version")
        path.write_bytes(value)
    print(json.dumps(metadata))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=RELEASES, default=VERSION)
    package(parser.parse_args().version)

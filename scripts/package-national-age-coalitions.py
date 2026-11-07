"""Reproduce the complete selected national prospective-age scenario package."""

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-age-cohort-scenarios/{VERSION}"
PUBLIC = f"public/participation-age-cohort-scenarios/{VERSION}"
UF = "data/participation-estimated-coalitions/20261107-01"
FEC = "data/participation-coalition-scenarios/20261107-01"
BASELINES = "public/participation-coalition-scenarios/20261107-01/official-2024-baselines.json"
PINS = {
    "selected-historical-support.json": "084f8f308838c5ce73e847fdb23d6d8d03915b2199b6cf41d2c152c9db95a925",
    "selected-current-survey.json": "bbe9c799248d4d5a1840369a6e6ae18abd099138054ed8afa751b81ecb8addf6",
    "methodology-review.json": "f2ce81968ce52896cb7b76297f5b87f63aa8e9a904db97cfba1c2ae782c20227",
}


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


model = load("age_package_model", "estimate-national-age-coalitions.py")
current_model = load("age_package_current", "estimate-demographic-current-counts.py")


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def selected_inputs():
    result = {}
    for name, expected in PINS.items():
        raw = (ROOT / DATA / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Selected age inputs changed; review a new immutable version")
        result[name] = json.loads(raw)
    return result


def summarize(result, historical):
    summary = copy.deepcopy({key: value for key, value in result.items() if key != "estimates"})
    summary["complete_scenarios_in_download"] = True
    summary["estimates"] = []
    for row in result["estimates"]:
        item = copy.deepcopy({key: value for key, value in row.items() if key != "sensitivity_scenarios"})
        support = next(group for group in historical["cohorts"] if
                       (group["native_current_survey_subset"], group["prior_choice"])
                       == (row["subset"], row["prior_choice"]))
        item["historical_certain_group_raw_n"] = support["certain_age_support"]["respondents"]
        item["historical_certain_group_effective_n"] = support["certain_age_support"]["effective_sample_size"]
        item["historical_coalition_raw_n"] = support["coalition"]["respondents"]
        scenarios = [scenario for scenario in row["sensitivity_scenarios"]
                     if scenario["status"] == "conditional_sensitivity_scenario"]
        item["sensitivity_scenario_count"] = len(row["sensitivity_scenarios"])
        for field in ("reported_opposite_choice_count", "original_coalition_scaled_switching_pct"):
            values = [scenario[field] for scenario in scenarios]
            item[f"marginal_sensitivity_{field}"] = (
                model.bounds(values) if values and all(value is not None for value in values) else None)
        summary["estimates"].append(item)
    return summary


def package():
    inputs = selected_inputs()
    historical = inputs["selected-historical-support.json"]
    if (historical["status"] != "reviewed_selected_national_prospective_age_support"
            or historical["release_scope"] != "national_conditional_scenarios_only"):
        raise ValueError("Selected support is not reviewed for this scenario scope")
    snapshot = inputs["selected-current-survey.json"]
    native = current_model.turnout
    totals = native.read_turnout(ROOT / UF / "Turnout_2026G_v0.2.csv", ROOT / UF / "Turnout_2026G_v0.1_doc.txt")
    if hashlib.sha256((ROOT / FEC / "official-2024.xlsx").read_bytes()).hexdigest() != (
            "68acdee2924d771b92a05cd950dec850b462c633c05563207ac7e206116e7366"):
        raise ValueError("Frozen official presidential workbook changed")
    baselines = native.math.fec_baselines(ROOT / FEC / "official-2024.xlsx")
    if baselines != json.loads((ROOT / BASELINES).read_text()):
        raise ValueError("Official native workbook and baseline control differ")
    current = current_model.estimate(snapshot, totals)
    # This is the safe selected subset of the audited support structure, not the private audit.
    support = {**historical, "status": "private_national_birth_year_support_not_demographic_dropoff"}
    result = model.estimate(support, current, baselines, model.survey.review_snapshot(snapshot))
    scenario_count = sum(len(row["sensitivity_scenarios"]) for row in result["estimates"])
    if len(current["estimates"]) != 3 or len(result["estimates"]) != 6 or scenario_count != 2916:
        raise ValueError("Reviewed national age/scenario inventory differs")
    result["status"] = "conditional_national_prospective_age_scaling_scenarios"
    result["version"] = VERSION
    result["source_qualification"] = {
        "release_scope": "national_conditional_scenarios_only",
        "historical_controls_and_broad_aggregate_disclosure_reviewed": True,
        "current_native_age_population_and_joint_choice_matching_required": True,
        "independent_2026_transition_validation": False,
        "design_confidence_intervals_available": False,
        "methods_review": f"{DATA}/methodology-review.json",
    }
    result["assumptions_and_limits"][-1] = (
        "Released only as national conditional scaling scenarios, not observed nonvoting or a validated demographic decomposition.")
    paths = [f"{DATA}/{name}" for name in PINS]
    paths += [f"{UF}/Turnout_2026G_v0.2.csv", f"{UF}/Turnout_2026G_v0.1_doc.txt",
              f"{FEC}/official-2024.xlsx", BASELINES]
    contents = {path: (ROOT / path).read_bytes() for path in paths}
    result["input_sha256"] = {path: hashlib.sha256(raw).hexdigest() for path, raw in contents.items()}
    summary_raw = encoded(summarize(result, historical))
    contents[f"{PUBLIC}/summary.json"] = summary_raw
    contents[f"{PUBLIC}/complete-scenarios.json"] = encoded(result)
    scripts = (
        "package-national-age-coalitions.py", "test-package-national-age-coalitions.py",
        "estimate-national-age-coalitions.py", "test-estimate-national-age-coalitions.py",
        "review-ces-age-cohorts.py", "test-review-ces-age-cohorts.py",
        "review-ces-demographic-baselines.py", "test-review-ces-demographic-baselines.py",
        "review-cnn-voter-poll.py", "test-review-cnn-voter-poll.py",
        "estimate-demographic-current-counts.py", "estimate-preliminary-coalitions.py",
        "estimate-survey-coalition-absence.py",
    )
    contents.update({f"scripts/{name}": (ROOT / "scripts" / name).read_bytes() for name in scripts})
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9,standard library only. Extract preserving all paths; no network needed.\n"
        "Verify every file against checksums.json, then run:\n"
        "python3 scripts/test-review-cnn-voter-poll.py\n"
        "python3 scripts/test-review-ces-demographic-baselines.py\n"
        "python3 scripts/test-review-ces-age-cohorts.py\n"
        "python3 scripts/test-estimate-national-age-coalitions.py\n"
        "python3 scripts/test-package-national-age-coalitions.py\n"
        "python3 scripts/package-national-age-coalitions.py\n"
        "summary.json,complete-analysis.zip and download.json reproduce exactly.\n"
        "The archive includes complete-scenarios.json with all2916scenarios; it is generated\n"
        "in memory from all included selected inputs and included again in the reproduced ZIP.\n"
        "Inputs: six disclosure-reviewed broad CES national coalition/birth-year aggregates,\n"
        "four native selected SSRS national House tables including matched population/self-cells,\n"
        "full official FEC2024workbook/baselines,full licensed UF2026CSV/documentation,methods,\n"
        "all calculation/review/package code and33source/calculation plus3package tests.\n"
        "No original respondent/voter records,small boundary cells,full copyrighted source\n"
        "dashboards/PDFs or restricted NORC materials are included.\n"
        "CES2024release9,DOI10.7910/DVN/X11EP6,CC0; source hashes are in selected support.\n"
        "UF data: MichaelMcDonald/UniversityofFlorida ElectionLab,v0.2,CC-BY4.0;\n"
        "retain attribution,license and native version fields. Derived analysis is not endorsed.\n"
        "SSRS source URLs/hashes/revisions are retained in the four selected source entries.\n"
        "Full CES microdata are not necessary to reproduce these aggregate scenarios. The exact\n"
        "audit scripts and frozen source pins document how to regenerate historical support\n"
        "separately where lawful access permits; no microdata download is performed here.\n"
        "Certain/possible age support hypothetically ages2024participants without observing\n"
        "survival,residence or2026participation. Current age is self-reported.18-29/18-44overlap.\n"
        "Both years excludeDC. N26is preliminary; current choice can retain pre-election intent.\n"
        "Response-population and historical composition assumptions remain unvalidated.\n"
        "Negative apparent-absence residuals remain source/model diagnostics,not physical\n"
        "nonvoting counts. They include death,migration,recall and population/composition error.\n"
        "Birthday ranges,rounding and historicalmix/recall/turnout stresses are NOT confidence\n"
        "intervals or exhaustive empirically estimated uncertainty. Main grid holds nativep\n"
        "fixed; its rounding envelope is separate. Marginal endpoints must not be added.\n"
        "No measured stayinghome,new/returning identity,demographicturnout,causalpersuasion,\n"
        "total-swing share,designCI or state/county/precinct allocation is identified.\n"
    ).encode()
    contents["checksums.json"] = encoded({
        path: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for path, raw in sorted(contents.items())})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, raw in sorted(contents.items()):
            member = zipfile.ZipInfo(path, date_time=(2026, 11, 7, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    raw = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.testzip() is None
        assert all(archive.read(path) == value for path, value in contents.items())
    metadata = {
        "file": "complete-analysis.zip", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "members": len(contents), "complete_selected_public_inputs_and_code": True,
        "full_sensitivity_scenarios": scenario_count, "release_scope": "national_conditional_scenarios_only",
        "measured_demographic_dropoff_released": False, "personal_records_included": False,
    }
    output = ROOT / PUBLIC
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("summary.json", summary_raw), ("complete-analysis.zip", raw),
                        ("download.json", encoded(metadata))):
        path = output / name
        if path.exists() and path.read_bytes() != value:
            raise ValueError("Frozen age scenario artifact differs; create a new version")
        path.write_bytes(value)
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

"""Reproduce selected state-specific age scenarios, not measured turnout."""

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-state-age-scenarios/{VERSION}"
PUBLIC = f"public/participation-state-age-scenarios/{VERSION}"
UF = "data/participation-estimated-coalitions/20261107-01"
FEC = "data/participation-coalition-scenarios/20261107-01"
BASELINES = f"public/participation-coalition-scenarios/{VERSION}/official-2024-baselines.json"
PINS = {
    "selected-historical-support.json": "a8a2f0ef3339681f3124c07a0149e009df7c95fb1f8046292e9bf04712325710",
    "selected-current-survey.json": "d7e35031453fddd52d7df0e34386ddb84bf49231dfd1f24b442c9711a55b16e7",
    "methodology-review.json": "9a24d4a9fe83449af719d51851303f577bf6c0d8595045ffecd761d6ecba45cc",
    "coverage-review.json": "b609c06c9d6fd64f3fbaae62353ef7ffa64185739fed112336d456bbcd8dfd56",
}


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


model = load("state_age_package_model", "estimate-state-age-coalitions.py")
current_model = load("state_age_package_current", "estimate-demographic-current-counts.py")


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def selected_inputs():
    result = {}
    for name, expected in PINS.items():
        raw = (ROOT / DATA / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Selected state age inputs changed; review a new immutable version")
        result[name] = json.loads(raw)
    return result


def select_historical(audit, current):
    if (audit["status"] != "private_state_birth_year_support_not_qualified_population_estimates"
            or audit["historical_controls_checked"] is not True):
        raise ValueError("Historical state controls were not checked")
    history = {(r["state_code"], r["native_current_survey_subset"], r["prior_choice"]): r
               for r in audit["cohorts"]}
    if len(history) != len(audit["cohorts"]):
        raise ValueError("Duplicate historical support")
    states = sorted({r["state_code"] for r in current["estimates"]
                     if r["state_code"] != "US" and r["subset"]["sub"] == 55})
    selected = []
    for state in states:
        rows = [history[state, 55, prior] for prior in ("D", "R")]
        if not all(r["certain_age_support"]["respondents"] >= 100
                   and (r["certain_age_support"]["effective_sample_size"] or 0) >= 100 for r in rows):
            continue
        for row in rows:
            selected.append({
                **{key: row[key] for key in ("state_code", "prior_choice", "native_current_survey_subset",
                                             "minimum_age", "maximum_age")},
                "coalition": {key: row["coalition"][key] for key in ("respondents", "effective_sample_size")},
                "certain_age_support": {key: row["certain_age_support"][key] for key in
                                        ("respondents", "effective_sample_size", "fraction_within_reported_2024_coalition")},
                "possible_age_support_including_unknown_birth_year": {
                    "fraction_within_reported_2024_coalition": row[
                        "possible_age_support_including_unknown_birth_year"]["fraction_within_reported_2024_coalition"]},
            })
    return selected


def summarize(result, historical):
    support = {(r["state_code"], r["native_current_survey_subset"], r["prior_choice"]): r
               for r in historical["cohorts"]}
    summary = copy.deepcopy({key: value for key, value in result.items() if key != "estimates"})
    summary["complete_scenarios_in_download"] = True
    summary["estimates"] = []
    for row in result["estimates"]:
        item = copy.deepcopy({key: value for key, value in row.items() if key != "sensitivity_scenarios"})
        group = support[row["state_code"], row["subset"], row["prior_choice"]]["certain_age_support"]
        item["historical_certain_group_raw_n"] = group["respondents"]
        item["historical_certain_group_effective_n"] = group["effective_sample_size"]
        scenarios = [s for s in row["sensitivity_scenarios"] if s["status"] == "conditional_sensitivity_scenario"]
        item["sensitivity_scenario_count"] = len(row["sensitivity_scenarios"])
        for field in ("apparent_absence_count", "reported_opposite_choice_count",
                      "original_coalition_scaled_switching_pct"):
            values = [s[field] for s in scenarios]
            item[f"marginal_sensitivity_{field}"] = (
                model.model.bounds(values) if values and all(v is not None for v in values) else None)
        summary["estimates"].append(item)
    return summary


def package():
    inputs = selected_inputs()
    historical, coverage = inputs["selected-historical-support.json"], inputs["coverage-review.json"]
    if (historical["status"] != "reviewed_selected_state_prospective_age_support"
            or historical["release_scope"] != "selected_state_conditional_scenarios_only"):
        raise ValueError("Selected state support lacks scope review")
    snapshot = inputs["selected-current-survey.json"]
    native = current_model.turnout
    totals = native.read_turnout(ROOT / UF / "Turnout_2026G_v0.2.csv", ROOT / UF / "Turnout_2026G_v0.1_doc.txt")
    if hashlib.sha256((ROOT / FEC / "official-2024.xlsx").read_bytes()).hexdigest() != (
            "68acdee2924d771b92a05cd950dec850b462c633c05563207ac7e206116e7366"):
        raise ValueError("Frozen official presidential workbook changed")
    baselines = native.math.fec_baselines(ROOT / FEC / "official-2024.xlsx")
    if baselines != json.loads((ROOT / BASELINES).read_text()):
        raise ValueError("Native presidential workbook and controls differ")
    current = current_model.estimate(snapshot, totals)
    support = {**historical, "status": "private_state_birth_year_support_not_qualified_population_estimates"}
    result = model.estimate(support, current, baselines, model.model.survey.review_snapshot(snapshot))
    keys = {(r["state_code"], r["contest_code"], r["subset"]) for r in result["estimates"]}
    selected = {(r["state_code"], r["contest_code"], r["subset"]) for r in coverage["selected_contest_age_tables"]}
    if (keys != selected or len(current["estimates"]) != 8 or len(result["estimates"]) != 16
            or len(historical["cohorts"]) != 12):
        raise ValueError("Selected state age/scenario inventory differs")
    scenario_count = sum(len(r["sensitivity_scenarios"]) for r in result["estimates"])
    result["status"] = "conditional_selected_state_prospective_age_scaling_scenarios"
    result["version"] = VERSION
    result["jurisdiction_coverage"] = coverage["jurisdiction_coverage"]
    if {r["state_code"] for r in result["jurisdiction_coverage"]} != set(baselines):
        raise ValueError("State coverage inventory differs")
    result["withheld_contest_age_tables"] = coverage["withheld_contest_age_tables"]
    result["source_qualification"] = {
        "release_scope": "selected_state_conditional_scenarios_only",
        "historical_controls_and_broad_aggregate_disclosure_reviewed": True,
        "current_native_state_population_and_joint_choice_matching_required": True,
        "independent_2026_transition_validation": False,
        "design_confidence_intervals_available": False,
        "support_screen_is_not_precision_or_publication_guarantee": True,
        "methods_review": f"{DATA}/methodology-review.json",
    }
    result["assumptions_and_limits"][-2] = (
        "Only separately reviewed broad65+state supports are released as conditional scenarios; smaller groups remain withheld.")
    paths = [f"{DATA}/{name}" for name in PINS]
    paths += [f"{UF}/Turnout_2026G_v0.2.csv", f"{UF}/Turnout_2026G_v0.1_doc.txt",
              f"{FEC}/official-2024.xlsx", BASELINES]
    contents = {path: (ROOT / path).read_bytes() for path in paths}
    result["input_sha256"] = {path: hashlib.sha256(raw).hexdigest() for path, raw in contents.items()}
    summary_raw = encoded(summarize(result, historical))
    contents[f"{PUBLIC}/summary.json"] = summary_raw
    contents[f"{PUBLIC}/complete-scenarios.json"] = encoded(result)
    scripts = (
        "package-state-age-coalitions.py", "test-package-state-age-coalitions.py",
        "estimate-state-age-coalitions.py", "test-estimate-state-age-coalitions.py",
        "review-ces-state-age-cohorts.py", "test-review-ces-state-age-cohorts.py",
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
        "Verify each checksums.json member, then run the included test-*.py files and:\n"
        "python3 scripts/package-state-age-coalitions.py\n"
        "summary.json,complete-analysis.zip and download.json reproduce exactly.\n"
        "All7776full scenarios are INSIDE the ZIP,not duplicated as a giant public JSON.\n"
        "Complete selected inputs:12broad historical state-coalition supports,16native\n"
        "SSRSstate age/all-voter tables,full licensed UFCSV/documentation,official FEC\n"
        "workbook/baselines,51jurisdiction coverage,methods,all calculation/code/tests/results.\n"
        "Source/control hashes and audit code document historical regeneration separately.\n"
        "CES2024release9,DOI10.7910/DVN/X11EP6,CC0. No respondent records,fine boundary\n"
        "counts,private historical audits or restricted NORC materials are included.\n"
        "UF:MichaelMcDonald/UniversityofFlorida ElectionLab,v0.2,CC-BY4.0; retain attribution,\n"
        "license/native versions. Derived analysis is not endorsed. Totals are preliminary.\n"
        "SSRSURLs/hashes/revisions are in selected sources. No full copyrighted pages mirrored.\n"
        "These hypothetically age2024participants without observing survival/residence/voting.\n"
        "Current choices can retain pre-election intent. Survey population matching assumes\n"
        "published group/response composition applies to preliminary ballot-casters.\n"
        "Historical/current presidential/result calibration is not independent validation.\n"
        "Support screening is not a precision guarantee. Birthday/rounding/assumed stress\n"
        "ranges are NOT confidence intervals or exhaustive empirically estimated uncertainty.\n"
        "Negative absence is a source/model diagnostic,not physical nonvoting. Death/migration,\n"
        "recall,population and historical composition error remain,especially for older cohorts.\n"
        "No measured stayinghome,identified new/returning,demographicturnout,causalpersuasion,\n"
        "total-swing share,designCI or county/precinct allocation. Offices/groups are not additive.\n"
    ).encode()
    contents["checksums.json"] = encoded({path: {
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for path, raw in sorted(contents.items())})
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
        "full_sensitivity_scenarios": scenario_count,
        "release_scope": "selected_state_conditional_scenarios_only",
        "measured_demographic_dropoff_released": False, "personal_records_included": False,
    }
    output = ROOT / PUBLIC
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("summary.json", summary_raw), ("complete-analysis.zip", raw),
                        ("download.json", encoded(metadata))):
        path = output / name
        if path.exists() and path.read_bytes() != value:
            raise ValueError("Frozen state age artifact differs; create a new version")
        path.write_bytes(value)
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

"""Reproduce selected national classification evidence, not population turnout."""

import hashlib
import io
import json
import math
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-ces-classification/{VERSION}"
PUBLIC = f"public/participation-ces-classification/{VERSION}"
PINS = {
    "selected-aggregates.json": "9b1dd039cdc537b6c540ffafa2c2b0e580552bd34fa4eded0b32787de2ddc73c",
    "methodology-review.json": "4e87a696abdfe245aa2c955318c13b901a212dd11df2b2089fbdb7c61754f3ac",
}
STUDY = "ces2024-postwave-participation-classification"
FIELDS = ("respondents", "sum_weight", "sum_squared_weight")
CATEGORIES = ("recorded_vote", "classified_nonvote", "unresolved")
PERMISSIONS = (
    "adult_population_turnout_rate_permitted", "eligible_population_turnout_rate_permitted",
    "design_confidence_intervals_permitted", "population_scaling_permitted",
    "state_or_local_allocation_permitted", "completed_2026_participation_or_choice_permitted",
)
GROUPS = {
    "calendar_year_age_2024": ("18-29", "30-44", "45-64", "65+"),
    "education_2024": ("2-year", "4-year", "High school graduate", "No HS", "Post-grad", "Some college"),
    "gender_2024": ("Man", "Woman"),
    "race_education_2024": (
        "Non-Hispanic White; College degree", "Non-Hispanic White; No college degree",
        "Not non-Hispanic White; College degree", "Not non-Hispanic White; No college degree"),
    "race_ethnicity_2024": (
        "Hispanic", "Non-Hispanic Asian", "Non-Hispanic Black", "Non-Hispanic Native American",
        "Non-Hispanic Two or more races", "Non-Hispanic White"),
    "source_race_2024": (
        "Asian", "Black", "Hispanic", "Native American", "Two or more races", "White"),
}
JURISDICTIONS = set(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE "
    "NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
NATIVE_HELPERS = (
    "review-ces-hybrid-participation.py", "test-review-ces-hybrid-participation.py",
    "review-ces-participation-records.py", "test-review-ces-participation-records.py",
    "review-ces-demographic-baselines.py", "test-review-ces-demographic-baselines.py",
)


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def statistics(cell):
    if (set(cell) != set(FIELDS) or type(cell["respondents"]) is not int
            or cell["respondents"] < 30
            or not all(positive(cell[field]) for field in FIELDS[1:])
            or cell["sum_squared_weight"] * cell["respondents"]
            < cell["sum_weight"] ** 2 * (1 - 1e-10)):
        raise ValueError("Invalid or small coarsened support/weight statistics")


def close(actual, expected):
    return math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8)


def summarize(row):
    weight = row["sum_weight"]
    positive_weight = row["categories"]["recorded_vote"]["sum_weight"]
    nonvote = row["categories"]["classified_nonvote"]["sum_weight"]
    unresolved = row["categories"]["unresolved"]["sum_weight"]
    return {
        "dimension": row["dimension"], "group": row["group"],
        "respondents": row["respondents"],
        "record_positive_weight_fraction": positive_weight / weight,
        "classified_nonvote_weight_fraction": nonvote / weight,
        "unresolved_weight_fraction": unresolved / weight,
        "conditional_compatible_fraction": [positive_weight / weight,
                                           (positive_weight + unresolved) / weight],
        "effective_sample_size_not_design_precision": weight ** 2 / row["sum_squared_weight"],
        "adult_population_turnout_rate": None, "eligible_population_turnout_rate": None,
        "design_confidence_interval": None, "completed_2026_participation": None,
    }


def review(snapshot, methods):
    if (set(snapshot) != {
            "study_id", "release", "doi", "license", "election", "survey_scope", "weight_frame",
            "classification", "source_accounting", "source_files", "native_label_metadata_selection",
            "native_response_controls", "record_only_overall_nonvote_sum_weight", "rows", "jurisdictions"}
            or snapshot["study_id"] != STUDY or snapshot["release"] != "9.0"
            or snapshot["doi"] != "10.7910/DVN/X11EP6" or snapshot["license"] != "CC0 1.0"
            or snapshot["election"] != "2024 general" or snapshot["survey_scope"] != "US50"
            or snapshot["weight_frame"] != "adult_postwave_commonpostweight"
            or snapshot["classification"] != "conflict_as_unknown"):
        raise ValueError("Source, population, single conflict variant or private-field schema changed")
    if (set(methods) != {
            "study_id", "status", "estimand", "selection", "weights_and_nonresponse",
            "record_classification", "selfreport_classification", "formulas", "denominator_limits",
            "precision_review", "disclosure_review", "definitions", "additional_demographic_capability",
            "geographic_and_time_limits", "reproduction", "source_qualification", "attribution",
            *PERMISSIONS}
            or methods["study_id"] != STUDY
            or methods["status"] != "qualified_only_for_conditional_2024_classification_evidence"
            or any(methods[key] is not False for key in PERMISSIONS)
            or set(methods["definitions"]) != set(GROUPS)):
        raise ValueError("Conditional-only estimand, source qualification or permissions changed")
    accounting = snapshot["source_accounting"]
    if (accounting != {
            "native_respondents": 60000, "postwave_respondents": 49432,
            "missing_postwave_weight_nonresponse": 10568, "selected_US50_postwave_respondents": 49304,
            "DC_postwave_respondents_excluded_from_US50": 128}
            or any(type(value) is not int for value in accounting.values())):
        raise ValueError("Preserve post-wave nonresponse and exact US50/DC source accounting")
    sources = snapshot["source_files"]
    expected_sources = {
        "ces2024.csv": (12050325, 183679005,
                       "8a5e9fbc982961ad910bad9aed8d521fa0a85e85cded43fb308cce0ab22ba5d9",
                       "b740b9305fee50e1a34656b513f55c57"),
        "ces2024-guide.pdf": (12050326, 1162260,
                             "48ef8f229980b4778dd26f321062e9d9e089abdd849cc8db2529377f3e8b0c10",
                             "b1b24ed55a20193bb0301bc84cf6da9a"),
    }
    if len(sources) != 2 or {row["file"] for row in sources} != set(expected_sources):
        raise ValueError("Require both complete native-source receipts")
    for source in sources:
        file_id, size, sha, md5 = expected_sources[source["file"]]
        if (set(source) != {
                "file", "url", "bytes", "sha256", "md5", "expected_md5", "retrieved_at",
                "last_modified", "etag", "individual_records_exported"}
                or source["url"] != f"https://dataverse.harvard.edu/api/access/datafile/{file_id}"
                or type(source["bytes"]) is not int or source["bytes"] != size
                or source["sha256"] != sha or source["md5"] != md5 or source["expected_md5"] != md5
                or source["individual_records_exported"] is not False):
            raise ValueError("Native-source provenance or privacy changed")
    metadata = snapshot["native_label_metadata_selection"]
    if (digest(encoded(metadata)) != "35a7eb003258a3faebd548e3cdae2c37b289c7bbd1c56777274ffca80aa33493"
            or metadata["respondent_data_transferred"] is not False
            or metadata["full_native_file_downloaded_or_hash_verified"] is not False):
        raise ValueError("Require exact inspected native label metadata, not respondent bytes")
    if digest(encoded(snapshot["native_response_controls"])) != "461476121db4c1f5682ddfbe2f8ee505e150aa58aa0f92c88cf1b8232b5207da":
        raise ValueError("Native guide-response mapping controls changed")
    rows = snapshot["rows"]
    expected_keys = {("overall", "overall")} | {
        (dimension, group) for dimension, groups in GROUPS.items() for group in groups}
    if (len(rows) != len(expected_keys)
            or {(row["dimension"], row["group"]) for row in rows} != expected_keys):
        raise ValueError("Selected groups must remain complete, unique and nonexhaustive")
    indexed = {}
    for row in rows:
        if (set(row) != {"dimension", "group", *FIELDS, "categories"}
                or set(row["categories"]) != set(CATEGORIES)):
            raise ValueError("Fine outcome categories, extra private fields or missing categories")
        statistics({field: row[field] for field in FIELDS})
        for cell in row["categories"].values():
            statistics(cell)
        if not all(close(sum(cell[field] for cell in row["categories"].values()), row[field])
                   for field in FIELDS):
            raise ValueError("Coarsened categories do not reconcile to the complete group")
        indexed[row["dimension"], row["group"]] = row
    overall = indexed["overall", "overall"]
    if overall["respondents"] != accounting["selected_US50_postwave_respondents"]:
        raise ValueError("National respondent control differs")
    for dimension, groups in GROUPS.items():
        parts = [indexed[dimension, group] for group in groups]
        exhaustive = dimension in (
            "calendar_year_age_2024", "education_2024", "race_education_2024")
        for category in (None, *CATEGORIES):
            parent = overall if category is None else overall["categories"][category]
            children = parts if category is None else [row["categories"][category] for row in parts]
            residual = {field: parent[field] - sum(cell[field] for cell in children)
                        for field in FIELDS}
            if exhaustive:
                if not all(close(residual[field], 0) for field in FIELDS):
                    raise ValueError("Complete demographic partition does not reconcile")
            else:
                statistics(residual)
    jurisdictions = snapshot["jurisdictions"]
    if (len(jurisdictions) != 51
            or {row["survey_scope"] for row in jurisdictions} != JURISDICTIONS):
        raise ValueError("Keep every state and D.C. disposition without duplicate jurisdictions")
    for row in jurisdictions:
        if (set(row) != {"survey_scope", "source_reviewed_privately", "public_estimate",
                        "status", "reason", "next_step"}
                or row["source_reviewed_privately"] is not True or row["public_estimate"] is not None
                or row["status"] != "state_specific_public_qualification_incomplete"
                or not isinstance(row["reason"], str) or not row["reason"].strip()
                or not isinstance(row["next_step"], str) or not row["next_step"].strip()):
            raise ValueError("State estimates remain withheld with a concrete qualification step")
    explicit = snapshot["record_only_overall_nonvote_sum_weight"]
    if not positive(explicit) or explicit > overall["categories"]["classified_nonvote"]["sum_weight"]:
        raise ValueError("Invalid same-post-frame overall recorded-nonvote comparator")
    analysis = [summarize(row) for row in rows]
    return {
        "status": "conditional_2024_classification_evidence_not_population_turnout",
        "study_id": STUDY, "election": snapshot["election"], "survey_scope": "US50",
        "weight_frame": snapshot["weight_frame"], "classification": "conflict_as_unknown",
        "source_accounting": accounting, "source_files": sources,
        "rows": analysis, "jurisdictions": jurisdictions, "methodology": methods,
        "record_only_compatible_fraction_same_post_frame_overall_only": [
            overall["categories"]["recorded_vote"]["sum_weight"] / overall["sum_weight"],
            (overall["sum_weight"] - explicit) / overall["sum_weight"]],
        "adult_population_turnout_rate": None, "eligible_population_turnout_rate": None,
        "completed_2026_participation_or_choice": None, "switching_or_staying_home": None,
        "population_scaling": None, "state_or_local_estimates": None,
        "design_confidence_intervals": None,
    }


def package():
    contents = {}
    inputs = {}
    for name, sha in PINS.items():
        raw = (ROOT / DATA / name).read_bytes()
        if digest(raw) != sha:
            raise ValueError("Reviewed CES inputs changed; create a separately reviewed version")
        inputs[name] = json.loads(raw)
        contents[f"{DATA}/{name}"] = raw
    analysis_raw = encoded(review(inputs["selected-aggregates.json"], inputs["methodology-review.json"]))
    contents[f"{PUBLIC}/classification-evidence.json"] = analysis_raw
    for name in ("package-ces-classification.py", "test-package-ces-classification.py", *NATIVE_HELPERS):
        contents[f"scripts/{name}"] = (ROOT / "scripts" / name).read_bytes()
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9, standard library only. Extract preserving all paths.\n"
        "Verify all files against checksums.json, then run:\n"
        "python3 scripts/test-package-ces-classification.py\n"
        "python3 scripts/package-ces-classification.py\n"
        "Exact selected aggregate inputs, result JSON, complete ZIP and metadata reproduce offline.\n"
        "This is selected-aggregate reproduction, not fresh respondent extraction or validation.\n"
        "Original reviewer/helper code and focused tests document native extraction. Their tests run:\n"
        "python3 scripts/test-review-ces-hybrid-participation.py\n"
        "python3 scripts/test-review-ces-participation-records.py\n"
        "python3 scripts/test-review-ces-demographic-baselines.py\n"
        "Fresh extraction additionally requires original CSV/guide/full native-label audit; native\n"
        "respondents, fine aggregates and private proofs are NOT redistributed. Used source URLs,\n"
        "bytes/hashes/clocks, label definitions, complete selected sufficient statistics and methods\n"
        "are in selected-aggregates.json and methodology-review.json. No network is needed here.\n"
        "2024 Cooperative Election Study Common Content, Harvard Dataverse release9.0,\n"
        "DOI10.7910/DVN/X11EP6, CC0 1.0. Independent analysis, not endorsed by the study.\n"
        "Single conservative conflict-as-unknown variant; never recover private fine conflict cells.\n"
        "Compatible ranges condition on classifications and truthful reported nonparticipation.\n"
        "These are NOT adult/eligible-population turnout rates, design CIs or full error bounds.\n"
        "Post-wave nonresponse and unmatched histories remain explicit. Source demographics are not\n"
        "fixed2026cohorts; race/ethnicity definitions differ. Groups overlap and are not additive.\n"
        "All51state/DC dispositions remain, with no national-to-state/county/precinct allocation.\n"
        "No2026participation, choice, switching, staying-home or first-time-voter identity is inferred.\n"
    ).encode()
    contents["checksums.json"] = encoded({
        path: {"bytes": len(raw), "sha256": digest(raw)} for path, raw in sorted(contents.items())})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, raw in sorted(contents.items()):
            member = zipfile.ZipInfo(path, date_time=(2026, 11, 7, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    zipped = buffer.getvalue()
    metadata = {
        "file": "complete-analysis.zip", "bytes": len(zipped), "sha256": digest(zipped),
        "members": len(contents), "complete_selected_aggregate_inputs_and_code": True,
        "personal_records_included": False, "native_respondent_data_included": False,
        "population_turnout_or_2026_transitions_released": False,
    }
    outputs = {"classification-evidence.json": analysis_raw,
               "complete-analysis.zip": zipped, "download.json": encoded(metadata)}
    out = ROOT / PUBLIC
    for name, raw in outputs.items():
        if (out / name).exists() and (out / name).read_bytes() != raw:
            raise ValueError("Frozen CES output differs; create a new version")
    out.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        (out / name).write_bytes(raw)
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

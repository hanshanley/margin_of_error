"""Package limited published panel intentions, never completed-vote or population flows."""

import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-pew-intentions/{VERSION}"
PUBLIC = f"public/participation-pew-intentions/{VERSION}"
PINS = {
    "selected-aggregates.json": "56fe3596362b48f14e60f4b466d93d14497fdb86df28fa22d774b3afb57f9589",
    "methodology-review.json": "8698f6bf0dbb3bf2c88b2e9541450d2418dbca31ee4804884ceb97e491b8666c",
}
PERMISSIONS = (
    "population_scaling_permitted", "completed_participation_permitted",
    "demographic_joint_estimation_permitted", "state_or_local_allocation_permitted",
    "design_confidence_intervals_permitted",
)


def review(snapshot, methods):
    if (set(snapshot) != {
            "study_id", "publisher", "geography", "universe", "field_period",
            "raw_registered_voter_sample", "contest_scope", "prior_turnout_validated",
            "prior_choice_administratively_observed", "source_files", "rows"}
            or snapshot["study_id"] != "pew-atp-wave200-2026-10"
            or snapshot["publisher"] != "Pew Research Center"
            or snapshot["geography"] != "national"
            or snapshot["universe"] != "current_registered_voters"
            or snapshot["field_period"] != {
                "start": "2026-09-28", "end": "2026-10-04", "completed_november_2026_votes": False}
            or type(snapshot["raw_registered_voter_sample"]) is not int
            or snapshot["raw_registered_voter_sample"] != 3917
            or snapshot["contest_scope"] != "House_intentions_in_respondents_own_district_including_leaners"
            or snapshot["prior_turnout_validated"] is not True
            or snapshot["prior_choice_administratively_observed"] is not False):
        raise ValueError("Selected wave, national registered-voter universe or evidence type changed")
    if (set(methods) != {
            "study_id", "status", "selection", "historical_evidence", "current_evidence",
            "question_scope", "weights", "study_identity", "nonresponse_and_rounding",
            "precision", "demographic_and_local_limits", "rights", "copyright_notice",
            "attribution", *PERMISSIONS}
            or methods["study_id"] != snapshot["study_id"]
            or methods["status"] != "qualified_only_for_published_broad_pre_election_intentions"
            or any(methods[key] is not False for key in PERMISSIONS)):
        raise ValueError("Descriptive-only source qualification changed")
    sources = snapshot["source_files"]
    expected_files = {
        "publisher-article.html", "topline.pdf", "questionnaire.pdf", "methodology.html",
        "terms.html", "weighting-dimensions.png", "sample-bases.png", "detailed-tables.xlsx"}
    if len(sources) != 8 or {row["file"] for row in sources} != expected_files:
        raise ValueError("Require every used native-source receipt")
    for source in sources:
        allowed = {"file", "source_url", "bytes", "sha256", "acquired_at"}
        if source["file"] == "detailed-tables.xlsx":
            allowed.add("acquisition")
        url = urlsplit(source["source_url"])
        if (set(source) != allowed or type(source["bytes"]) is not int or source["bytes"] <= 0
                or not re.fullmatch(r"[a-f0-9]{64}", source["sha256"])
                or url.scheme != "https"
                or url.hostname not in ("www.pewresearch.org", "docs.google.com")):
            raise ValueError("Source provenance or disclosure changed")
    if (len(snapshot["rows"]) != 2
            or {row["source_group"] for row in snapshot["rows"]}
            != {"Trump 2024 voters", "Harris 2024 voters"}):
        raise ValueError("Require both broad historical-choice rows")
    rows = []
    for row in snapshot["rows"]:
        if (set(row) != {"source_group", "intended_house_pct", "no_answer_pct",
                         "published_sum_minus_100_pp"} or row["no_answer_pct"] is not None):
            raise ValueError("Unreported nonresponse must remain unknown; no extra private fields")
        values = row["intended_house_pct"]
        if (set(values) != {"D", "R", "Other", "Not sure"}
                or any(type(value) is not int or not 0 <= value <= 100 for value in values.values())
                or type(row["published_sum_minus_100_pp"]) is not int
                or row["published_sum_minus_100_pp"] != sum(values.values()) - 100):
            raise ValueError("Preserve all published rounded answers and their signed sum difference")
        rows.append({
            "source_group": row["source_group"], "intended_house_pct": dict(values),
            "no_answer_pct": None,
            "published_sum_minus_100_pp": row["published_sum_minus_100_pp"],
        })
    return {
        "status": "published_pre_election_intentions_not_completed_2026_transitions",
        "study_id": snapshot["study_id"], "geography": snapshot["geography"],
        "field_period": snapshot["field_period"], "universe": snapshot["universe"],
        "contest_scope": snapshot["contest_scope"],
        "raw_registered_voter_sample": snapshot["raw_registered_voter_sample"],
        "source_files": sources, "rows": rows, "methodology": methods,
        "prior_group_bases": None, "completed_2026_transitions": None,
        "population_switchers": None, "original_coalition_rates": None,
        "returning_population": None, "apparent_absence": None, "measured_staying_home": None,
        "new_or_returning_identity": None, "demographic_turnout": None,
        "demographic_by_prior_choice_estimates": None,
        "causal_persuasion": None, "overall_swing_share": None,
        "design_confidence_intervals": None, "state_or_local_estimates": None,
    }


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def frozen_write(path, raw):
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("Frozen panel-intention output differs; create a new version")
    path.write_bytes(raw)


def package():
    inputs = {}
    for name, digest in PINS.items():
        raw = (ROOT / DATA / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Reviewed panel-intention inputs changed")
        inputs[name] = json.loads(raw)
    analysis = review(inputs["selected-aggregates.json"], inputs["methodology-review.json"])
    out = ROOT / PUBLIC
    out.mkdir(parents=True, exist_ok=True)
    frozen_write(out / "intentions.json", encoded(analysis))
    paths = [f"{DATA}/{name}" for name in PINS] + [f"{PUBLIC}/intentions.json"]
    paths += ["scripts/package-pew-intentions.py", "scripts/test-package-pew-intentions.py"]
    contents = {path: (ROOT / path).read_bytes() for path in paths}
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9, standard library only. Extract preserving all paths.\n"
        "Verify all files against checksums.json, then run:\n"
        "python3 scripts/test-package-pew-intentions.py\n"
        "python3 scripts/package-pew-intentions.py\n"
        "Exact selected inputs, result JSON, ZIP and metadata reproduce without network.\n"
        "Pew Research Center, ATP Wave200, September28-October4,2026; published October8,2026.\n"
        "Copyright2026PewResearchCenter. Limited attributed factual excerpts, not a native-source mirror.\n"
        "Both broad prior groups and every published D/R/other/unsure percentage are included.\n"
        "No-answer is unreported, not zero. Preserve rounding; do not renormalize.\n"
        "Initial selection was independently checked against native literal HTML and the public\n"
        "workbook obtained through its ordinary File/Download menu. Full native bytes/hashes and\n"
        "canonical declared URLs are in selected-aggregates.json. Native files remain at the source;\n"
        "they are not required for offline reproduction from these complete selected aggregates.\n"
        "Official-record validation concerns2024participation, not administratively observed choice.\n"
        "The article describes choice collection in the month after2024; the workbook says the week\n"
        "after. Exact historical interview dates are unverified. Neither describes a2026-only recall.\n"
        "Current registered voters are not the full original2024coalitions or the2026electorate.\n"
        "No completed2026transitions, population scaling/absence, demographic joints, turnout rates,\n"
        "local allocation, design CIs or new-voter identity are inferred. Unsure is not nonvoting.\n"
        "Pew's national ATP study is not the SSRS Voter Poll sample despite a shared contractor.\n"
        "No respondent records, source HTML/PDFs/figures or whole workbook are redistributed.\n"
        "Analysis is not endorsed by Pew Research Center. Refer to the source terms before reuse.\n"
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
    frozen_write(out / "complete-analysis.zip", raw)
    metadata = {
        "file": "complete-analysis.zip", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "members": len(contents), "complete_selected_aggregate_inputs_and_code": True,
        "personal_records_included": False, "source_documents_redistributed": False,
        "population_decomposition_released": False,
    }
    frozen_write(out / "download.json", encoded(metadata))
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

"""Package only qualified broad native-group August intentions, not turnout."""

import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-slu-demographic-intentions/{VERSION}"
PUBLIC = f"public/participation-slu-demographic-intentions/{VERSION}"
PINS = {
    "selected-aggregates.json": "53e0508819fb57a202741256e04257dfcddeb862a2ab663f1c0d7dc4cd525a86",
    "methodology-review.json": "959b8e19754d56ce2b21729aa3a15441accb1a5ae3ba507b4f5242f40c1e8e29",
}
spec = importlib.util.spec_from_file_location(
    "native_slu_demographics", Path(__file__).with_name("review-slu-demographic-intentions.py"))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
GROUPS = {
    ("gender", "2"): ("Female (native Sex category)", {"D": 238, "R": 206}),
    ("race", "1"): ("White (native Race category)", {"D": 283, "R": 374}),
    ("USR_Classification", "3"): ("Suburban (native geographic context)", {"D": 163, "R": 145}),
    ("marstat", "1"): ("Married", {"D": 162, "R": 264}),
    ("child18", "2"): ("No children under 18 in household", {"D": 295, "R": 320}),
}
PERMISSIONS = (
    "population_scaling_permitted", "completed_participation_permitted",
    "district_or_county_allocation_permitted", "design_confidence_intervals_permitted",
    "cross_source_demographic_harmonization_permitted",
)


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def review(snapshot, methods):
    if (set(snapshot) != {"study_id", "geography", "universe", "completed_voting", "contest_scope",
                         "field_period", "raw_sample", "native_variables", "source_files", "groups"}
            or snapshot["study_id"] != "slu-yougov-2026-08-mo" or snapshot["geography"] != "MO"
            or snapshot["universe"] != "registered_likely_voters" or snapshot["completed_voting"] is not False
            or snapshot["contest_scope"] != "generic_US_House_party_in_respondents_own_district"
            or snapshot["field_period"] != {"start": "2026-08-13", "end": "2026-08-24"}
            or snapshot["raw_sample"] != 900
            or snapshot["native_variables"] != {
                "prior": "presvote24post", "house": "POLS025", "likelihood": "QB", "weight": "weight"}):
        raise ValueError("Selected wave, universe, scope or disclosure fields changed")
    if (set(snapshot["source_files"]) != set(native.slu.SOURCE_PINS)
            or any(set(receipt) != {"url", "bytes", "sha256"}
                   or receipt["sha256"] != native.slu.SOURCE_PINS[name]
                   or not receipt["url"].startswith("https://www.slu.edu/")
                   or not isinstance(receipt["bytes"], int) or receipt["bytes"] <= 0
                   for name, receipt in snapshot["source_files"].items())):
        raise ValueError("Native source receipts changed")
    if (methods["study_id"] != snapshot["study_id"]
            or methods["status"] != "qualified_only_for_selected_descriptive_august_intentions"
            or any(methods[key] is not False for key in PERMISSIONS)):
        raise ValueError("Descriptive-only qualification changed")
    identities = [(group["native_variable"], group["native_code"]) for group in snapshot["groups"]]
    if len(identities) != len(GROUPS) or set(identities) != set(GROUPS):
        raise ValueError("Keep exactly the five separately qualified native groups")
    groups = []
    for group in snapshot["groups"]:
        identity = (group["native_variable"], group["native_code"])
        label, bases = GROUPS[identity]
        definition = native.DIMENSIONS[identity[0]]
        if (set(group) != {"native_variable", "native_code", "native_description", "native_label",
                          "display_label", "rows"} or group["display_label"] != label
                or group["native_description"] != definition["description"]
                or group["native_label"] != definition["categories"][identity[1]][0]
                or len(group["rows"]) != 2
                or {row["prior_party"] for row in group["rows"]} != {"D", "R"}):
            raise ValueError("Native labels, prior groups or disclosure fields changed")
        rows = []
        for row in group["rows"]:
            prior = row["prior_party"]
            kish = row["kish_weight_concentration_base"]
            if (set(row) != {"prior_party", "reported_2024_choice", "raw_prior_base",
                            "kish_weight_concentration_base", "weighted_house_shares"}
                    or row["reported_2024_choice"] != {"D": "Harris", "R": "Trump"}[prior]
                    or row["raw_prior_base"] != bases[prior]
                    or not finite_number(kish) or not 100 <= kish <= bases[prior]):
                raise ValueError("Broad prior support, labels or disclosure changed")
            shares = row["weighted_house_shares"]
            if (set(shares) != {"D", "R", "Other", "Not sure"}
                    or any(not finite_number(value) or not 0 <= value <= 1 for value in shares.values())
                    or not math.isclose(math.fsum(shares.values()), 1, rel_tol=0, abs_tol=2e-15)):
                raise ValueError("Keep every response and the full prior/group denominator")
            rows.append({key: value for key, value in row.items() if key != "weighted_house_shares"})
            rows[-1]["intended_house_pct"] = {party: 100 * value for party, value in shares.items()}
        groups.append({**{key: value for key, value in group.items() if key != "rows"}, "rows": rows})
    return {
        "status": "descriptive_native_group_august_intentions_not_november_transitions",
        "study_id": snapshot["study_id"], "geography": "MO", "field_period": snapshot["field_period"],
        "universe": snapshot["universe"], "contest_scope": snapshot["contest_scope"],
        "source_files": snapshot["source_files"], "groups": groups, "methodology": methods,
        "groups_additive": False, "demographic_measurement_date": None,
        "population_switchers": None, "apparent_absence": None, "measured_staying_home": None,
        "new_or_returning_identity": None, "demographic_turnout": None,
        "overall_swing_share": None, "design_confidence_intervals": None,
        "district_or_county_estimates": None,
    }


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def frozen_write(path, raw):
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("Frozen demographic intention output differs; create a new version")
    path.write_bytes(raw)


def package():
    inputs = {}
    for name, digest in PINS.items():
        raw = (ROOT / DATA / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Reviewed demographic intention inputs changed")
        inputs[name] = json.loads(raw)
    analysis = review(inputs["selected-aggregates.json"], inputs["methodology-review.json"])
    out = ROOT / PUBLIC
    out.mkdir(parents=True, exist_ok=True)
    frozen_write(out / "intentions.json", encoded(analysis))
    paths = [f"{DATA}/{name}" for name in PINS] + [f"{PUBLIC}/intentions.json"]
    paths += ["scripts/" + name for name in (
        "review-slu-intended-house.py", "test-review-slu-intended-house.py",
        "review-slu-demographic-intentions.py", "test-review-slu-demographic-intentions.py",
        "package-slu-demographic-intentions.py", "test-package-slu-demographic-intentions.py")]
    contents = {path: (ROOT / path).read_bytes() for path in paths}
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9, standard library only. Extract preserving all paths.\n"
        "Verify all files against checksums.json, then run:\n"
        "python3 scripts/test-review-slu-intended-house.py\n"
        "python3 scripts/test-review-slu-demographic-intentions.py\n"
        "python3 scripts/test-package-slu-demographic-intentions.py\n"
        "python3 scripts/package-slu-demographic-intentions.py\n"
        "All complete selected inputs, exact code/tests/results, ZIP and metadata reproduce OFFLINE.\n"
        "SLU/YouGov Missouri, August13-24,2026,900registered likely voters. Not endorsed.\n"
        "Native URLs/bytes/SHA256 are in selected-aggregates.json. No native records/PDF/HTML mirrored.\n"
        "Ten broad prior/group bases and ALL40weighted House responses are included.\n"
        "No raw joint counts, joint weight sums, fine cells, respondent records or individual scores.\n"
        "Initial native record aggregation requires independently obtaining the pinned SLU sources;\n"
        "the exact private-source reviewer is included, distinct from offline selected-input reproduction.\n"
        "Support screening alone is NOT precision/disclosure qualification. Read methodology-review.json.\n"
        "Native categories only; no demographic harmonization, fixed cohorts or additive group totals.\n"
        "Generic own-district AUGUST House intentions are NOT observed November switching or turnout.\n"
        "No N26 scaling, apparent absence, staying home, local allocation, group difference tests or design CIs.\n"
        "Original2024coalitions are not the denominator. A rounded zero does not establish population absence.\n"
        "The original overall-intentions20261107-01 package remains unchanged and separately available.\n"
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
        "personal_records_included": False, "raw_joint_cells_included": False,
        "source_documents_redistributed": False, "population_decomposition_released": False,
    }
    frozen_write(out / "download.json", encoded(metadata))
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

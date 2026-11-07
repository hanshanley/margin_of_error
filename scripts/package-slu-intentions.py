"""Publish complete selected broad intention aggregates, never population transitions."""

import hashlib
import io
import json
import math
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-slu-intentions/{VERSION}"
PUBLIC = f"public/participation-slu-intentions/{VERSION}"
PINS = {
    "selected-aggregates.json": "6581cc6aed956775ea5416e93ad781d43245e340dfd4f2a7f54a44974d2bea5d",
    "methodology-review.json": "d8f4370b9b44ec03a9f0100032bd1af268075ebd11de39e62290d8855f6ce553",
}


def review(snapshot, methods):
    if (set(snapshot) != {"study_id", "geography", "universe", "completed_voting", "contest_scope",
                         "field_period", "raw_sample", "native_variables", "source_files", "rows"}
            or snapshot["study_id"] != "slu-yougov-2026-08-mo" or snapshot["geography"] != "MO"
            or snapshot["universe"] != "registered_likely_voters" or snapshot["completed_voting"] is not False
            or snapshot["contest_scope"] != "generic_US_House_party_in_respondents_own_district"
            or snapshot["field_period"] != {"start": "2026-08-13", "end": "2026-08-24"}
            or snapshot["raw_sample"] != 900
            or snapshot["native_variables"] != {
                "prior": "presvote24post", "house": "POLS025", "likelihood": "QB", "weight": "weight"}):
        raise ValueError("Selected wave, universe, scope or disclosure fields changed")
    if (methods["study_id"] != snapshot["study_id"]
            or methods["status"] != "qualified_only_for_broad_descriptive_august_intentions"
            or any(methods[key] is not False for key in (
                "population_scaling_permitted", "completed_participation_permitted",
                "district_or_county_allocation_permitted", "design_confidence_intervals_permitted"))):
        raise ValueError("Descriptive-only qualification changed")
    if (len(snapshot["rows"]) != 2 or {row["prior_party"] for row in snapshot["rows"]} != {"D", "R"}):
        raise ValueError("Require both broad prior coalitions, without duplicates")
    rows = []
    for row in snapshot["rows"]:
        prior = row["prior_party"]
        if (set(row) != {"prior_party", "reported_2024_choice", "raw_prior_base",
                        "kish_weight_concentration_base", "weighted_house_shares"}
                or row["reported_2024_choice"] != {"D": "Harris", "R": "Trump"}[prior]
                or row["raw_prior_base"] != {"D": 383, "R": 418}[prior]
                or not math.isfinite(row["kish_weight_concentration_base"])
                or not 0 < row["kish_weight_concentration_base"] <= row["raw_prior_base"]):
            raise ValueError("Broad prior support, labels or disclosure changed")
        shares = row["weighted_house_shares"]
        if (set(shares) != {"D", "R", "Other", "Not sure"}
                or any(not math.isfinite(value) or not 0 <= value <= 1 for value in shares.values())
                or not math.isclose(math.fsum(shares.values()), 1, rel_tol=0, abs_tol=2e-15)):
            raise ValueError("Keep the full four-response denominator without renormalization")
        rows.append({
            "prior_party": prior, "reported_2024_choice": row["reported_2024_choice"],
            "raw_prior_base": row["raw_prior_base"],
            "kish_weight_concentration_base": row["kish_weight_concentration_base"],
            "intended_house_pct": {party: 100 * value for party, value in shares.items()},
        })
    return {
        "status": "descriptive_august_intentions_not_observed_november_switching",
        "study_id": snapshot["study_id"], "geography": "MO",
        "field_period": snapshot["field_period"], "source_files": snapshot["source_files"],
        "universe": snapshot["universe"], "contest_scope": snapshot["contest_scope"], "rows": rows,
        "population_switchers": None, "apparent_absence": None, "measured_staying_home": None,
        "new_or_returning_identity": None, "demographic_turnout": None,
        "overall_swing_share": None, "design_confidence_intervals": None,
        "district_or_county_estimates": None,
        "methodology": methods,
    }


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def frozen_write(path, raw):
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("Frozen intention output differs; create a new version")
    path.write_bytes(raw)


def package():
    inputs = {}
    for name, digest in PINS.items():
        raw = (ROOT / DATA / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Reviewed intention inputs changed")
        inputs[name] = json.loads(raw)
    analysis = review(inputs["selected-aggregates.json"], inputs["methodology-review.json"])
    out = ROOT / PUBLIC
    out.mkdir(parents=True, exist_ok=True)
    frozen_write(out / "intentions.json", encoded(analysis))
    paths = [f"{DATA}/{name}" for name in PINS] + [f"{PUBLIC}/intentions.json"]
    paths += ["scripts/" + name for name in (
        "review-slu-intended-house.py", "test-review-slu-intended-house.py",
        "package-slu-intentions.py", "test-package-slu-intentions.py")]
    contents = {path: (ROOT / path).read_bytes() for path in paths}
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9, standard library only. Extract preserving all paths.\n"
        "Verify every file against checksums.json, then run:\n"
        "python3 scripts/test-review-slu-intended-house.py\n"
        "python3 scripts/test-package-slu-intentions.py\n"
        "python3 scripts/package-slu-intentions.py\n"
        "Complete selected aggregate inputs, exact code/tests/results, ZIP and metadata reproduce offline.\n"
        "Source: Saint Louis University/YouGov, August2026 Missouri poll, August13-24,900likely voters.\n"
        "Full original source URLs, bytes and SHA256 are in selected-aggregates.json.\n"
        "Selected inputs include BOTH broad prior coalitions and ALL four weighted House responses.\n"
        "No tiny raw joint counts, joint weight sums, fine demographics, records or scores are included.\n"
        "Native CSV and copyrighted PDF/HTML are not mirrored or relicensed. Analysis is not endorsed.\n"
        "The included private-source reviewer documents the exact initial weighting/coding calculation.\n"
        "Re-running initial record aggregation requires independently obtaining the pinned native source\n"
        "from SLU; that is separate from offline reproduction from these complete selected aggregates.\n"
        "August generic House-party intentions are not observed November transitions or district results.\n"
        "Likely-voter screening excludes unlikely/nonvoters. Retain other and unsure in denominators.\n"
        "No new historical reweighting, N26 scaling, population absence, demographic turnout, local allocation\n"
        "or subgroup design CIs. Broad raw n and Kish diagnostics are not design-aware conditional precision.\n"
        "The original2024coalition is not the denominator. This does not close the SSRS missing-state gap.\n"
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

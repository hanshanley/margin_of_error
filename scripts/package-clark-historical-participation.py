"""Package complete selected Clark native counts, not precinct transition estimates."""

import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
SOURCE = "data/precinct-source-acquisitions/20261105/NV-CLARK-2020-2024"
DATA = f"data/participation-clark-history/{VERSION}"
PUBLIC = f"public/participation-clark-history/{VERSION}"
PROOF_SHA256 = "6f287d0e216d238cd97c4756bc74a1b66b431377a3d555db3fc39f99e47de2fb"
REVIEW_SHA256 = "5c97cbcdc16d91c75c382bd3b589b26fcecac9ea24abc796a06dd64057ac31aa"
CODE = (
    "scripts/review-clark-historical-participation.py",
    "scripts/test-review-clark-historical-participation.py",
    "scripts/package-clark-historical-participation.py",
    "scripts/test-package-clark-historical-participation.py",
)
spec = importlib.util.spec_from_file_location("clark_history", ROOT / CODE[0])
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def precinct_csv(result):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow([
        "year", "native_contest", "native_precinct_id", "native_registration_once",
        "native_turnout", "election_day", "early_vote", "mail",
        "turnout_exceeds_registration", "qualified_turnout_rate",
    ])
    for observation in result["observations"]:
        for unit in observation["units"]:
            writer.writerow([
                observation["year"], observation["native_contest"], unit["native_precinct_id"],
                unit["native_registration"], unit["native_turnout"],
                *(unit["native_turnout_by_mode"][mode] for mode in history.MODES),
                str(unit["turnout_exceeds_registration"]).lower(), "",
            ])
    return stream.getvalue().encode()


def summary(result, proof):
    return {
        "version": VERSION,
        "status": "qualified_selected_native_statement_turnout_counts_only",
        "state_code": result["state_code"], "county_name": result["county_name"],
        "county_fips": result["county_fips"],
        "observations": [
            {key: value for key, value in observation.items()
             if key not in ("units", "pdf_content_independently_verified")}
            for observation in result["observations"]
        ],
        "same_year_contest_scope": result["same_year_contest_scope"],
        "limitations": result["limitations"],
        "independent_pdf_check": {
            "proof_sha256": PROOF_SHA256,
            "native_unit_observations_verified": proof["pdf_native_unit_observations_verified"],
            "native_unit_mode_counts_verified": proof["pdf_native_unit_mode_counts_verified"],
            "different_representation_not_independent_outcome_data": True,
            "fresh_pdf_check_rerun_by_packager": False,
        },
        **{key: result[key] for key in (
            "precinct_maps_qualified", "cross_year_precinct_comparisons_qualified",
            "all_county_ballot_universe_independently_qualified",
            "measured_prior_voter_dropoff", "new_or_returning_voters",
            "party_switchers", "demographic_turnout_rate")},
    }


def archive_bytes(contents):
    inventory = {
        name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for name, raw in sorted(contents.items())
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, raw in sorted({**contents, "checksums.json": encoded(inventory)}.items()):
            member = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def package(root=ROOT):
    raw_proof = (root / DATA / "pdf-source-consistency.json").read_bytes()
    if hashlib.sha256(raw_proof).hexdigest() != PROOF_SHA256:
        raise ValueError("Require the original independently verified PDF consistency receipt")
    proof = json.loads(raw_proof)
    reviewer_raw = (root / CODE[0]).read_bytes()
    if hashlib.sha256(reviewer_raw).hexdigest() != proof["reviewer_sha256"]:
        raise ValueError("Reviewer differs from the independently checked implementation")
    result = history.review(root / SOURCE)
    raw_review = (json.dumps(result, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
    if hashlib.sha256(raw_review).hexdigest() != REVIEW_SHA256:
        raise ValueError("Selected native counts differ from the independently verified review")
    selected = [f"originals/{key}.gz" for report in history.REPORTS for key in report[2:]]
    original_inventory = json.loads((root / SOURCE / "checksums.json").read_bytes())
    for name in selected:
        raw = (root / SOURCE / name).read_bytes()
        if original_inventory[name] != {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}:
            raise ValueError("Selected compressed original differs from its frozen inventory")
    raw_summary = encoded(summary(result, proof))
    inputs = [f"{SOURCE}/sources.json", f"{SOURCE}/checksums.json",
              f"{DATA}/pdf-source-consistency.json", *CODE,
              *(f"{SOURCE}/{name}" for name in selected)]
    contents = {name: (root / name).read_bytes() for name in inputs}
    contents.update({
        f"{PUBLIC}/summary.json": raw_summary,
        "results/native-counts.json": raw_review,
        "results/precinct-participation.csv": precinct_csv(result),
        "REPRODUCTION.txt": (
            "Python>=3.9; standard library only. Extract preserving all paths.\n"
            "Verify every member against the top-level checksums.json, then run:\n"
            "python3 scripts/test-review-clark-historical-participation.py\n"
            "python3 scripts/test-package-clark-historical-participation.py\n"
            "python3 scripts/package-clark-historical-participation.py\n"
            "Summary, all selected counts, complete ZIP and metadata reproduce without network.\n"
            "Source: Clark County Election Department, native 2020/2022/2024 statements.\n"
            "All eight USED PDF/Data originals are included, unchanged and gzip-compressed.\n"
            "The original source manifest and inventory include receipts for additional unused\n"
            "statements, NOT a claim those additional originals are in this selected package.\n"
            "The full original collection remains in the existing immutable release:\n"
            "voter-precinct-nevada-clark-historical-20261105, source commit\n"
            "096f1adc45c2d632e82e49de0959b53f6bc8c589.\n"
            "results/native-counts.json is the exact previously private native-source review.\n"
            "Its public_release_qualified=false is preserved: it does not qualify broader\n"
            "maps, turnout rates, common electorates, individual transitions or 2026 results.\n"
            "Only the selected historical native statement counts are qualified for this package.\n"
            "The included PDF receipt records a completed separate source-representation check.\n"
            "Packaging does not rerun it; source consistency is not independent outcome evidence.\n"
            "All 3894 selected unit vectors and all three mode counts are included in JSON/CSV.\n"
            "Precinct IDs are literal strings; import CSV ID columns as text to preserve zeros.\n"
            "Registration repeats across modes and is stored once per unit. It is not a\n"
            "qualified eligible-population denominator. Above-registration units are retained.\n"
            "CSV qualified_turnout_rate is empty (unknown), never a zero turnout estimate.\n"
            "Unused native footer percentages and candidate suppression remain unchanged.\n"
            "Candidate columns in native originals are not extracted or suppression-recovered.\n"
            "The 2024 President and Senate statements have different unit coverage; neither\n"
            "their counts nor overlapping precinct observations may be added across contests.\n"
            "No cross-year precinct crosswalk, demographic rate, switching, apparent absence,\n"
            "new/returning-voter identity, measured staying home or 2026 observation is supplied.\n"
            "No voter records, demographic joint cells, identities or individual scores included.\n"
        ).encode(),
    })
    raw_zip = archive_bytes(contents)
    metadata = {
        "file": "complete-analysis.zip", "bytes": len(raw_zip),
        "sha256": hashlib.sha256(raw_zip).hexdigest(), "members": len(contents) + 1,
        "complete_selected_originals_inputs_code_and_results": True,
        "selected_native_originals": len(selected),
        "selected_unit_observations": sum(row["native_reporting_units"] for row in result["observations"]),
        "personal_records_included": False, "maps_or_transitions_qualified": False,
    }
    outputs = {"summary.json": raw_summary, "complete-analysis.zip": raw_zip,
               "download.json": encoded(metadata)}
    out = root / PUBLIC
    for name, raw in outputs.items():
        if (out / name).exists() and (out / name).read_bytes() != raw:
            raise ValueError("Frozen Clark output differs; use a new version")
    out.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        if not (out / name).exists():
            (out / name).write_bytes(raw)
    return metadata


if __name__ == "__main__":
    print(json.dumps(package()))

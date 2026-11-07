"""Package all permitted selected demographic inputs and exact offline calculation."""

import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-demographic-counts/{VERSION}"
PUBLIC = f"public/participation-demographic-counts/{VERSION}"
UF = "data/participation-estimated-coalitions/20261107-01"


def package():
    paths = [f"{DATA}/selected-source-tables.json", f"{PUBLIC}/demographic-current-counts.json",
             "data/participation-survey/20261107-02/methods-audit.json"]
    paths += [f"{UF}/{name}" for name in
              ("Turnout_2026G_v0.2.csv", "Turnout_2026G_v0.1_doc.txt", "receipts.json", "methodology-review.json")]
    paths += ["scripts/" + name for name in (
        "review-cnn-voter-poll.py", "test-review-cnn-voter-poll.py",
        "estimate-survey-coalition-absence.py", "estimate-preliminary-coalitions.py",
        "estimate-demographic-current-counts.py", "test-estimate-demographic-current-counts.py",
        "package-demographic-current-counts.py")]
    contents = {path: (ROOT / path).read_bytes() for path in paths}
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9; standard library only. Extract preserving all paths.\n"
        "Verify all members against checksums.json, then run:\n"
        "python3 scripts/test-review-cnn-voter-poll.py\n"
        "python3 scripts/test-estimate-demographic-current-counts.py\n"
        f"Remove only the extracted {PUBLIC}/demographic-current-counts.json.\n"
        "python3 scripts/estimate-demographic-current-counts.py\n"
        "python3 scripts/package-demographic-current-counts.py\n"
        "The analysis JSON, complete ZIP and download metadata reproduce exactly offline.\n"
        "Includes all selected published joint tables, exact same-contest demographic population\n"
        "questions/self-cells, native source hashes, full unchanged licensed UF inputs/documentation,\n"
        "methodology, complete calculations/dependencies/tests and outputs. No full survey dashboard.\n"
        "The original selection is preserved; additional demographic facts came from the same frozen\n"
        "native files, verified against their original full-byte hashes before selection. No refetch.\n"
        "Attribution: Michael McDonald, University of Florida Election Lab,2026 General Election\n"
        "Turnout, CSVv0.2/documentationv0.1, Creative Commons Attribution4.0 International.\n"
        "Source: https://election.lab.ufl.edu/dataset/2026-general-election-turnout-rates-v0-2/\n"
        "License: https://creativecommons.org/licenses/by/4.0/\n"
        "Native UF files unchanged. Derived analysis not endorsed by UF, SSRS or CNN.\n"
        "Counts=N26*g*q*p, assuming matched current-group shares and joint responses represent all\n"
        "estimated ballot-casters. N26 is an Initial Estimate. Some choices remain pre-election.\n"
        "Current demographics are not frozen2024 cohorts. No historical group baselines are supplied;\n"
        "no demographic drop-off, original-coalition percentages, turnout rates or total-swing shares.\n"
        "N means reported no2024 presidential vote, not all-race nonvote or first-ever voting.\n"
        "National House excludes unsampledDC; complete nativeUS/DC rows remain intact.\n"
        "No suppression recovery or renormalization.18-44 uses exact question1949, not summed bins.\n"
        "Groups/offices/national-state comparisons overlap. Do not add them or marginal endpoints.\n"
        "Rounding envelopes and+-5percent population/+-2pp balanced recall stress are not design CIs.\n"
        "Mode weights are unqualified. No local allocation, individual records, scores or NORC inputs.\n"
    ).encode()
    contents["checksums.json"] = (json.dumps({
        path: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for path, raw in sorted(contents.items())}, indent=2) + "\n").encode()
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
    output = ROOT / PUBLIC / "complete-analysis.zip"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("Frozen demographic archive differs; create a new version")
    output.write_bytes(raw)
    metadata = {
        "file": output.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "members": len(contents), "complete_selected_public_inputs_and_code": True,
        "historical_group_baselines_included": False, "demographic_dropoff_released": False,
        "personal_records_included": False,
    }
    (output.parent / "download.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

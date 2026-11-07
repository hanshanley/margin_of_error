"""Package frozen official inputs, joint tables and conditional scaling code."""

import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-02"
DATA = f"data/participation-coalition-scenarios/{VERSION}"
PUBLIC = f"public/participation-coalition-scenarios/{VERSION}"
SURVEY = "20261107-02"


def package():
    paths = [
        f"{DATA}/official-2024.xlsx", f"{DATA}/participation-input.json",
        f"{PUBLIC}/official-2024-baselines.json", f"{PUBLIC}/conditional-coalition-scenarios.json",
        f"data/participation-survey/{SURVEY}/selected-source-tables.json",
        f"data/participation-survey/{SURVEY}/methods-audit.json",
        f"public/participation-survey/{SURVEY}/joint-table-review.json",
        "scripts/review-cnn-voter-poll.py", "scripts/test-review-cnn-voter-poll.py",
        "scripts/estimate-survey-coalition-absence.py",
        "scripts/test-estimate-survey-coalition-absence.py",
        "scripts/package-survey-coalition-scenarios.py",
    ]
    contents = {name: (ROOT / name).read_bytes() for name in paths}
    contents["REPRODUCTION.txt"] = (
        "Python >=3.9, standard library only. Extract preserving all paths.\n"
        "Check each member against checksums.json before running code.\n"
        "python3 scripts/test-review-cnn-voter-poll.py\n"
        "python3 scripts/test-estimate-survey-coalition-absence.py\n"
        f"python3 scripts/review-cnn-voter-poll.py --snapshot data/participation-survey/{SURVEY}/selected-source-tables.json "
        f"--output public/participation-survey/{SURVEY}/joint-table-review.json\n"
        f"Remove only the two extracted JSON files under {PUBLIC}/, leaving their directory empty.\n"
        f"python3 scripts/estimate-survey-coalition-absence.py --workbook {DATA}/official-2024.xlsx "
        f"--participation-snapshot {DATA}/participation-input.json "
        f"--survey-review public/participation-survey/{SURVEY}/joint-table-review.json --output {PUBLIC}\n"
        "python3 scripts/package-survey-coalition-scenarios.py\n"
        "Both JSON outputs and this complete archive reproduce byte-for-byte without network access.\n"
        "Includes the complete official FEC workbook, all selected statewide ballot observations and provenance,\n"
        "all selected published joint survey inputs, exact review/calculation/tests/package code and outputs.\n"
        "Government-source observation extraction was reviewed in the existing participation project;\n"
        "the selected immutable observations are inputs here, not a fresh live website extraction.\n"
        "No native voter/respondent records, restricted NORC materials or full copyrighted dashboard are included.\n"
        "These are conditional all-ballot scaling scenarios. Exact contest-table response universes remain unverified.\n"
        "Georgia and Delaware also assume source-defined Ballots Cast snapshots cover the entire ballot population.\n"
        "Their native observations, warnings and approval flags remain intact; all-mode scope is unconfirmed.\n"
        "The pinned adapter rejects any changed native observation; California voterTurnout is not admitted.\n"
        "Apparent absence is not measured staying home. Read every assumption in the scenario JSON.\n"
        "Rounding and response/recall/count sensitivity are not confidence intervals or exhaustive uncertainty.\n"
        "Different contests share voters. Do not sum offices, marginal endpoints or overlapping groups.\n"
    ).encode()
    checksums = {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                 for name, raw in sorted(contents.items())}
    contents["checksums.json"] = (json.dumps(checksums, indent=2) + "\n").encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, raw in sorted(contents.items()):
            member = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    raw = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.testzip() is None
        assert all(archive.read(name) == data for name, data in contents.items())
    output = ROOT / PUBLIC / "complete-analysis.zip"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("Existing scenario archive differs; create a new version")
    output.write_bytes(raw)
    metadata = {
        "file": output.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "members": len(contents), "complete_selected_public_inputs_and_code": True,
        "conditional_scenarios_released": True, "validated_dropoff_released": False,
        "personal_records_included": False,
    }
    (output.parent / "download.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

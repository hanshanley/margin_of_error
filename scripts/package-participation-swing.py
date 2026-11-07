"""Package every permitted aggregate input/output and exact analysis code reproducibly."""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "public/participation-swing/20261106-02"
CODE = [
    "scripts/participation-swing.mjs", "scripts/participation-swing.test.mjs",
    "scripts/build-participation-swing.mjs", "scripts/build-participation-swing.test.mjs",
    "scripts/review-nc-demographic-cohort.py", "scripts/test-review-nc-demographic-cohort.py",
    "scripts/review-nc-candidate-scope.py", "scripts/test-review-nc-candidate-scope.py",
    "scripts/review-nc-linked-cohort.py", "scripts/test-review-nc-linked-cohort.py",
    "scripts/fit-historical-choice.py", "scripts/test-fit-historical-choice.py",
    "scripts/model-nc-swing.py", "scripts/test-model-nc-swing.py",
    "scripts/build-swing-coverage.py", "scripts/test-build-swing-coverage.py",
    "scripts/requirements-swing-model.txt",
    "scripts/check-participation-swing-browser.py",
    "scripts/package-participation-swing.py",
    "public/scripts/participation-swing.js", "src/components/ParticipationSwing.astro",
]


def package():
    inputs = json.loads((DIRECTORY / "inputs.json").read_text())
    paths = []
    for row in inputs:
        path = ROOT / row["path"]
        if not path.resolve().is_relative_to(ROOT) or "nc-demographic-cohort-20261106-01" in str(path):
            raise ValueError("Disallowed public package input")
        data = path.read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("Changed analysis input")
        paths.append(path)
    paths += [DIRECTORY / file for file in [
        "analysis.json", "aggregate-cohort.json", "county-contest-methods.json",
        "observed-comparisons.json", "inputs.json",
        "conditional-transitions.json", "historical-choice-model.json", "nationwide-scope.json",
    ]]
    paths += [ROOT / file for file in CODE]
    contents = {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in paths}
    checksums = {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                 for name, data in sorted(contents.items())}
    contents["checksums.json"] = (json.dumps(checksums, indent=2) + "\n").encode()
    contents["REPRODUCTION.txt"] = (
        "Extract preserving paths. Requires Node >=22 and Python >=3.9 (standard library only).\n"
        "node --test scripts/participation-swing.test.mjs scripts/build-participation-swing.test.mjs\n"
        "python3 scripts/test-review-nc-demographic-cohort.py\n"
        "python3 scripts/test-review-nc-candidate-scope.py\n"
        "python3 scripts/test-review-nc-linked-cohort.py\n"
        "python3 scripts/test-build-swing-coverage.py\n"
        "node scripts/build-participation-swing.mjs\n"
        "python3 scripts/package-participation-swing.py\n"
        "All aggregate review inputs and native PUBLIC candidate results are included.\n"
        "Personal voter archives, individual joins and individual preference scores are deliberately absent.\n"
        "The private-source aggregation script documents how official records were reduced; it needs the separately acquired private archives.\n"
        "Cohort counts are accepted records, not unique voters, group turnout rates, or candidate choices.\n"
        "County comparisons are descriptive; no demographic or individual transition estimate is validated.\n"
        "Optional research models require the separate dependencies in scripts/requirements-swing-model.txt.\n"
        "With those already installed, run python3 scripts/test-fit-historical-choice.py and python3 scripts/test-model-nc-swing.py.\n"
        "Historical-choice fitting and the experimental transition model require separately acquired private inputs; their tests use synthetic data.\n"
        "Fitted historical models and all 86 experimental Durham scenarios are included, with diagnostics and assumption ranges.\n"
        "The nationwide scope ledger can be rebuilt with python3 scripts/build-swing-coverage.py --choice-model data/participation-swing/20261106-conditional-model-01/historical-choice-model.json --output a-new-directory.\n"
        "Re-running private-source fits requires separately acquired official voter and survey records; no fine joint cells are published.\n"
        "Sensitivity ranges are not confidence intervals. This is not a nationwide attribution release or observed individual switching.\n"
    ).encode()
    output = DIRECTORY / "complete-analysis.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(contents.items()):
            member = zipfile.ZipInfo(name, date_time=(2026, 11, 6, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            archive.writestr(member, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(contents):
            raise ValueError("Incomplete ZIP")
        for name, data in contents.items():
            if archive.read(name) != data:
                raise ValueError("Changed ZIP member")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (DIRECTORY / "download.json").write_text(json.dumps({
        "file": "complete-analysis.zip", "bytes": output.stat().st_size, "sha256": digest,
        "members": len(contents), "complete_aggregate_inputs_and_outputs": True,
        "personal_records_included": False,
    }, indent=2) + "\n")
    print(json.dumps({"bytes": output.stat().st_size, "sha256": digest, "members": len(contents)}))


if __name__ == "__main__":
    package()

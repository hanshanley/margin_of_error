"""Package the complete selected public joint tables and exact offline review code."""

import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-02"
DATA = f"data/participation-survey/{VERSION}"
PUBLIC = f"public/participation-survey/{VERSION}"


def package():
    paths = [
        f"{DATA}/selected-source-tables.json", f"{DATA}/methods-audit.json",
        f"{PUBLIC}/joint-table-review.json",
        "scripts/review-cnn-voter-poll.py", "scripts/test-review-cnn-voter-poll.py",
        "scripts/package-participation-survey.py",
    ]
    contents = {name: (ROOT / name).read_bytes() for name in paths}
    contents["REPRODUCTION.txt"] = (
        "Python >=3.9, standard library only. Extract preserving all paths.\n"
        "python3 scripts/test-review-cnn-voter-poll.py\n"
        f"python3 scripts/review-cnn-voter-poll.py --snapshot {DATA}/selected-source-tables.json "
        f"--output {PUBLIC}/joint-table-review.json\n"
        "python3 scripts/package-participation-survey.py\n"
        "Review JSON and complete archive reproduce byte-for-byte, with no network access.\n"
        "Includes every configured candidate-table disposition and every acquired selected joint question.\n"
        "The selected snapshot includes the publisher configuration, candidate metadata and source hashes.\n"
        "The full copyrighted dashboard/HTML, unrelated questions and personal records are not included.\n"
        "Suppression, composition gaps, disabled tables and nonunique/special comparisons stay explicit.\n"
        "No population drop-off, share of swing, unsupported design CIs or local allocations are released.\n"
        "Read methods-audit.json and the review qualification before using these rounded survey cells.\n"
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
        assert set(archive.namelist()) == set(contents)
        assert all(archive.read(name) == data for name, data in contents.items())
    directory = ROOT / PUBLIC
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "complete-analysis.zip"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("Existing survey archive differs; create a new version")
    output.write_bytes(raw)
    metadata = {
        "file": output.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "members": len(contents), "complete_selected_public_inputs_and_code": True,
        "personal_records_included": False, "population_decomposition_released": False,
    }
    (directory / "download.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

"""Package complete selected numerical inputs and exact independent-poll review."""

import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-mevp/{VERSION}"
PUBLIC = f"public/participation-mevp/{VERSION}"


def package():
    paths = [f"{DATA}/selected-source-tables.json", f"{DATA}/methodology-review.json",
             f"{PUBLIC}/joint-choices.json"]
    paths += ["scripts/" + name for name in (
        "review-mevp-voter-poll.py", "test-review-mevp-voter-poll.py", "package-mevp-voter-poll.py")]
    contents = {path: (ROOT / path).read_bytes() for path in paths}
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9; standard library only. Extract preserving all paths.\n"
        "Verify every member against checksums.json, then run:\n"
        "python3 scripts/test-review-mevp-voter-poll.py\n"
        "python3 scripts/review-mevp-voter-poll.py "
        f"--snapshot {DATA}/selected-source-tables.json --output {PUBLIC}/joint-choices.json\n"
        "python3 scripts/package-mevp-voter-poll.py\n"
        "The selected-fact review, complete ZIP and download metadata reproduce exactly offline.\n"
        "Includes all selected numerical inputs: five complete nine-banner, three-party Q10 tables,\n"
        "their raw respondent bases, first-November-election shares and conditional Q29 marginals.\n"
        "All source URLs/hashes/page numbers, methods review, exact code/tests/results are included.\n"
        "Source: BSP Research/African American Research Collaborative,2026MidtermElectionVoterPoll.\n"
        "https://2026electionpoll.us/crosstabs/ and https://2026electionpoll.us/methodology/\n"
        "Selected numerical facts/citations only; original copyrighted PDFs/HTML are not mirrored.\n"
        "Derived review is not endorsed by the source organizations and is not their microdata.\n"
        "Five source-defined national racial groups are not five state estimates or a population panel.\n"
        "Conditional House party choices are among current participants recalling a prior vote,\n"
        "not percentages of the original2024coalitions. Retain O choices and whole-point rounding.\n"
        "The universe includes reported early voters and intended ElectionDay voters. No administrative\n"
        "turnout/choice validation. Generic House party responses are not reconciled candidate returns.\n"
        "Q29 explicitly filters previous voters with2024eligibility; it is NOT unconditional2026composition.\n"
        "First-November2026 is not first-ever participation in any election. Raw sample fractions\n"
        "are not weighted group sizes or effective samples. Unknown responses remain unclassified.\n"
        "Methods say fieldwork endedNov3; selected PDFs sayNov2. Both observations are preserved.\n"
        "Weights use turnout models and final result comparisons, not independent outcome validation.\n"
        "No population switcher count, apparent absence, demographic turnout, original-coalition rate,\n"
        "causal persuasion, overall-swing share, designCI or state/local allocation is released.\n"
        "Do not pool this study with SSRS or multiply its conditional Q29 marginals by all voter totals.\n"
        "No individual records, scores or restricted NORC materials are included.\n"
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
        raise ValueError("Frozen MEVP archive differs; create a new version")
    output.write_bytes(raw)
    metadata = {
        "file": output.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "members": len(contents), "complete_selected_public_inputs_and_code": True,
        "population_decomposition_released": False, "source_documents_redistributed": False,
        "personal_records_included": False,
    }
    (output.parent / "download.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

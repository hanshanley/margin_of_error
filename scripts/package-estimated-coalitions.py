"""Package the licensed native turnout estimates and exact conditional analysis."""

import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-03"
DATA = "data/participation-estimated-coalitions/20261107-03"
PUBLIC = f"public/participation-estimated-coalitions/{VERSION}"
WORKBOOK = "data/participation-coalition-scenarios/20261107-02/official-2024.xlsx"
SURVEY = "20261107-02"
COMMAND = (
    f"python3 scripts/estimate-preliminary-coalitions.py --workbook {WORKBOOK} "
    f"--turnout-csv {DATA}/Turnout_2026G_v0.2.csv --documentation {DATA}/Turnout_2026G_v0.1_doc.txt "
    "--turnout-source-version 20261107T055406Z "
    f"--survey-review public/participation-survey/{SURVEY}/joint-table-review.json "
    f"--methodology {DATA}/methodology-review.json --output {PUBLIC}"
)


def package():
    paths = [WORKBOOK, f"{PUBLIC}/estimated-coalition-scenarios.json"]
    paths += [f"{DATA}/{name}" for name in
              ("Turnout_2026G_v0.2.csv", "Turnout_2026G_v0.1_doc.txt", "receipts.json", "methodology-review.json")]
    paths += [f"data/participation-estimated-coalitions/20261107-01/{name}" for name in
              ("Turnout_2026G_v0.2.csv", "Turnout_2026G_v0.1_doc.txt")]
    paths += [f"data/participation-survey/{SURVEY}/selected-source-tables.json",
              f"data/participation-survey/{SURVEY}/methods-audit.json",
              f"public/participation-survey/{SURVEY}/joint-table-review.json"]
    paths += ["scripts/" + name for name in
              ("review-cnn-voter-poll.py", "test-review-cnn-voter-poll.py",
               "estimate-survey-coalition-absence.py", "estimate-preliminary-coalitions.py",
               "test-estimate-preliminary-coalitions.py", "package-estimated-coalitions.py")]
    contents = {name: (ROOT / name).read_bytes() for name in paths}
    contents["REPRODUCTION.txt"] = (
        "Python >=3.9, standard library only. Extract preserving all paths.\n"
        "Verify all members against checksums.json, then run:\n"
        "python3 scripts/test-review-cnn-voter-poll.py\n"
        "python3 scripts/test-estimate-preliminary-coalitions.py\n"
        f"python3 scripts/review-cnn-voter-poll.py --snapshot data/participation-survey/{SURVEY}/selected-source-tables.json "
        f"--output public/participation-survey/{SURVEY}/joint-table-review.json\n"
        f"Remove only the extracted {PUBLIC}/estimated-coalition-scenarios.json, leaving its directory empty.\n"
        f"{COMMAND}\n"
        "python3 scripts/package-estimated-coalitions.py\n"
        "The survey review, analysis JSON, complete ZIP and download metadata reproduce exactly offline.\n"
        "Complete native UF CSV/documentation, source receipts and selected methodology facts are included.\n"
        "Attribution: Michael McDonald, University of Florida Election Lab, 2026 General Election Turnout,\n"
        "CSVv0.2 and documentationv0.1, Creative Commons Attribution4.0 International.\n"
        "License: https://creativecommons.org/licenses/by/4.0/\n"
        "Source: https://election.lab.ufl.edu/dataset/2026-general-election-turnout-rates-v0-2/\n"
        "Native files are unchanged. This derived analysis is not endorsed by UF, SSRS or FEC.\n"
        "This NEW analysis uses the explicitly reviewed20261107T055406Z CSV snapshot; older releases\n"
        "remain unchanged. The two older native regression fixtures verify the unchanged default pin.\n"
        "Includes the complete official FEC workbook, selected published joint survey cells, exact review,\n"
        "calculation/tests/package code and outputs. No full copyrighted webpage/dashboard is included.\n"
        "No individual voter/respondent records, restricted NORC materials or personal scores are included.\n"
        "Every turnout numerator is an Initial Estimate, not an observed certified count.\n"
        "The native page defines estimated total ballots; the older codebook still says TBD for that field.\n"
        "The earlier frozen definition review identifies this declared CSV URL; the refresh receipts\n"
        "identify the new exact bytes and native HTTP clock. No live webpage clock is inferred.\n"
        "Current-population response-scope assumptions remain unresolved. Apparent absence is not measured\n"
        "staying home; it includes migration, mortality, recall and population-estimation error.\n"
        "Recalled presidential nonvote does not establish first-ever voting or no ballot in any prior race.\n"
        "Suppressed choice cells remain null; composition is not renormalized. Stress/rounding is not a CI.\n"
        "National House matches the survey's50state scope: exclude unsampled DC from both2024coalitions\n"
        "and2026estimated totals. Complete native US/DC rows remain intact; no geographic allocation.\n"
        "Do not sum offices, national/state comparisons or marginal endpoints.\n"
        "No demographic/county/precinct allocation or causal share-of-swing estimate is released.\n"
    ).encode()
    contents["checksums.json"] = (json.dumps({
        name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for name, raw in sorted(contents.items())}, indent=2) + "\n").encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, raw in sorted(contents.items()):
            member = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    raw = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.testzip() is None
        assert all(archive.read(name) == value for name, value in contents.items())
    output = ROOT / PUBLIC / "complete-analysis.zip"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("Frozen preliminary archive differs; create a new version")
    output.write_bytes(raw)
    metadata = {"file": output.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "members": len(contents), "complete_selected_public_inputs_and_code": True,
                "preliminary_estimated_total_scenarios": True, "validated_dropoff_released": False,
                "personal_records_included": False}
    (output.parent / "download.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

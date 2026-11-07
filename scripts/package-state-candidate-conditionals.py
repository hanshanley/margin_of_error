"""Reproduce the complete selected unscaled state candidate-choice package."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DATA = "data/participation-candidate-conditionals/20261107-01"
PUBLIC = "public/participation-candidate-conditionals/20261107-01"
PINS = {
    "selected-source-tables.json": "8001a735d2e73b69038570a6c822b13685587409fe066614d5cf46d3794a26e6",
    "methodology-review.json": "3c00e46ed3121bb169d66dba47e48df714bd892f3df185bcefd47e93cee6f046",
}
spec = importlib.util.spec_from_file_location(
    "candidate_conditionals_package", Path(__file__).with_name("review-state-candidate-conditionals.py"))
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def package():
    contents = {}
    for name, digest in PINS.items():
        raw = (ROOT / DATA / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Selected candidate inputs changed; review a new version")
        contents[f"{DATA}/{name}"] = raw
    result = model.review(json.loads(contents[f"{DATA}/selected-source-tables.json"]))
    result["version"] = "20261107-01"
    result["selected_input_sha256"] = PINS
    output = encoded(result)
    contents[f"{PUBLIC}/candidate-conditionals.json"] = output
    for name in (
        "package-state-candidate-conditionals.py", "review-state-candidate-conditionals.py",
        "test-review-state-candidate-conditionals.py", "review-cnn-voter-poll.py",
        "test-review-cnn-voter-poll.py",
    ):
        contents[f"scripts/{name}"] = (ROOT / "scripts" / name).read_bytes()
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9,standard library only. Extract preserving all paths; no network needed.\n"
        "Verify every member against checksums.json,then run:\n"
        "python3 scripts/test-review-cnn-voter-poll.py\n"
        "python3 scripts/test-review-state-candidate-conditionals.py\n"
        "python3 scripts/package-state-candidate-conditionals.py\n"
        "All13tests and candidate-conditionals.json/complete-analysis.zip/download.json\n"
        "reproduce exactly from all included selected numerical inputs and exact code.\n"
        "Four selected CNN/SSRS all-voter state sources:AK/NH,Governor/Senate,2026general.\n"
        "All native candidates and all4recalled prior-choice rows are preserved.\n"
        "Native source URLs/full-byte hashes/revisions and source-selection lineage retained.\n"
        "No original dashboards/PDFs,individual records or restricted NORC materials mirrored.\n"
        "CandidateAnswers.percentage is conditional on recalled prior choice,totalPercentage\n"
        "is separate prior composition; no multiplication or renormalization is performed.\n"
        "Original AKnonunique-party and NHcomposition gates remain WITHHELD. Published prior\n"
        "composition totals97/95are not assigned an invented missing-response/nonvoter category.\n"
        "Multiple Republican candidates are not pooled; the literal Independent stays separate.\n"
        "DanS.Sullivan and DanielJ.Sullivan retain different native IDs,names and parties.\n"
        "No ranked-choice round or matched final-round switching is inferred. Initial choices\n"
        "may survive unsuccessful recontact; universally completed voting is not claimed.\n"
        "Suppressed/null choices remain unknown; rounded0is not proof of zero switching.\n"
        "N means no2024presidentialvote,not all-race nonvoting or identified new/returning voters.\n"
        "No population returning/switcher/absence count,measured stayinghome,original-coalition\n"
        "switching rate,overall-swing share,designCI or county/precinct allocation is identified.\n"
        "Offices share respondents and are not additive. CNN/NBC/MSNOW are ONE SSRS study.\n"
        "Derived analysis is not endorsed by source organizations.\n"
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
    metadata = {
        "file": "complete-analysis.zip", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "members": len(contents), "complete_selected_public_inputs_and_code": True,
        "states": ["AK", "NH"], "contests": 4, "population_scaling_performed": False,
    }
    directory = ROOT / PUBLIC
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in (("candidate-conditionals.json", output), ("complete-analysis.zip", raw),
                        ("download.json", encoded(metadata))):
        path = directory / name
        if path.exists() and path.read_bytes() != value:
            raise ValueError("Frozen candidate artifact differs; create a new version")
        path.write_bytes(value)
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()

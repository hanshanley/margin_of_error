"""Package all existing source observations and complete before/after mode decisions."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-native-mode-frames-01"


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(key for row in rows for key in row)),
                            lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: "" if value is None else json.dumps(value, ensure_ascii=True)
            if isinstance(value, (dict, list, bool)) else value for key, value in row.items()})
    return stream.getvalue().encode()


def build(args):
    source = ROOT / VERSION
    if args.output.exists() or (source / "download.json").exists():
        raise ValueError("Never replace an existing complete source-mode package")
    inputs = json.loads((source / "inputs.json").read_bytes())
    proofs = {name: json.loads(path.read_bytes()) for name, path in [
        ("local-all204-mode-browser-acceptance.json", args.browser),
        ("local-all51-geography-acceptance.json", args.navigation),
        ("local-preserved-AL67-acceptance.json", args.preserved),
        ("local-pages-size-and-download-acceptance.json", args.size)]}
    if not all(proof["status"].startswith("PASS") for proof in proofs.values()):
        raise ValueError("Actual local checks must pass before packaging")
    if len(inputs["files"]) != 58:
        raise ValueError("Changed complete input scope")
    raw = gzip.decompress((source / "queries.json.gz").read_bytes())
    query = json.loads(raw)
    if query["summary"]["changed_unsupported_mode_decisions"] != 23:
        raise ValueError("Changed merged-input source qualification")
    paths = {VERSION + "/" + name for name in inputs["files"]} | {
        VERSION + "/" + name for name in ["inputs.json", "queries.json.gz", "summary.json"]}
    paths.update([
        "scripts/native-mode-frames.mjs", "scripts/native-mode-frames.test.mjs",
        "scripts/prepare-native-mode-frames.mjs", "scripts/build-native-mode-frame-inputs.py",
        "scripts/package-native-mode-frames.py", "scripts/check-native-mode-frames-browser.py",
        "scripts/check-participation-2026-drilldowns-browser.py",
        "scripts/check-alabama-county-counts-browser.py", "scripts/local_reference_staging.py",
        "public/scripts/participation-geography.js", "public/scripts/participation-explorer.js",
        "public/scripts/provider-county-scopes.js",
    ])
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, expected in inputs["files"].items():
        if pin(members[VERSION + "/" + name]) != expected:
            raise ValueError("Changed complete source observation or baseline code: " + name)
    decisions = query["complete204_state_mode_decisions"]
    tables = {"all204-source-mode-decisions.csv": decisions,
        "all23-withheld-unqualified-mode-decisions.csv": [row for row in decisions if row["changed"]],
        "all181-preserved-selection-decisions.csv": [row for row in decisions if not row["changed"]]}
    if list(map(len, tables.values())) != [204, 23, 181]:
        raise ValueError("Incomplete before/after decision tables")
    for name, rows in tables.items():
        members[name] = csv_bytes(rows)
    members["queries.json"] = raw
    for name, proof in proofs.items():
        members[name] = encoded(proof)
    members["package.json"] = b'{"private":true,"type":"module"}\n'
    members["requirements.txt"] = b"# Numerical review/reproduction: Node22+ built-ins only.\n# Builder/independent verifier: Python3.9+ standard library.\n"
    members["reproduce.mjs"] = b"""import {reviewNativeModeFrames,encodeNativeModeReview} from './scripts/native-mode-frames.mjs';
process.stdout.write(encodeNativeModeReview(await reviewNativeModeFrames()));
"""
    members["README.txt"] = b"""SOURCE-MODE FRAMES: COMPLETE51-JURISDICTION /204-DECISION REVIEW

COMPLETE CONTENTS
All58 sufficient inputs:49 COMPLETE existing local-source exports, complete
shared native snapshot/local data, ALL464 reviewed county observations,
complete additional-source inventory, original baseline selector/provider/
explorer code and all102 preliminary audit decisions. ALL204 before/after
state/mode decisions and their selected observation queries are supplied,
including all23 changed and181 preserved decisions. Complete code, tests,
inputs, raw numerical results and exact offline reproduction are included.
This is not a metadata-only inventory. Earlier source releases, full
native originals, complete downloads and routes remain available.

WHAT CHANGES
23 unsupported local early/returned selections across16 jurisdictions no
longer expose all-method ballots, townVV, TOTALTURNOUT, CardsCast or other
unqualified source frames. Their exact original counts/registrations/
clocks/printed percentages remain in the FULL input observations.
All102 Available/official decisions and67 qualified requested-mode decisions
are unchanged. Twelve other unsupported selections were already empty.
No new source observation, normalized voting mode, unique person, population,
demographic participation or administrative certification is inferred.
Empty selected-mode coverage is unknown/not qualified, NOTobserved zero.

FULL MERGED INPUTS MATTER
The preliminary49-export audit flags19 decisions. The actual merged sidebar
also includes shared native and reviewed source rows: D.C., Pennsylvania
and South Dakota add four decisions. All23 are included, not guessed away.
No separate Alaska/DC export does NOTmean no source data: D.C.'s existing
185,086 county-equivalent count remains available/official, not allocated
to early/returned modes. Alaska's native precinct path and D.C.'s matched
precinct path are separately mode-gated. No precinct counts are reallocated.
Website missing-mode copy explains the held frame rather than claiming
no sources were ingested. Default closed Methods/navigation is preserved.

REPRODUCE IN AN EMPTY DIRECTORY
Extract every ZIP member; no download or source acquisition is required.
  node reproduce.mjs > reproduced-queries.json
Output must equal queries.json byte-for-byte.
  node --test scripts/native-mode-frames.test.mjs
All three tests use built-ins and the COMPLETE included source exports.
Local browser proofs require the full website/browser tooling and do NOT
constitute native Pages/live-production acceptance. manifest.json pins
every other archive member. The exact frozen source data and both original
and corrected source selectors are included in full, not fetched at runtime.
"""
    members["manifest.json"] = encoded(dict(summary=query["summary"], sufficient_inputs=58,
        files={name: pin(body) for name, body in sorted(members.items())}))
    assets = ["queries.json", *tables, "requirements.txt", "README.txt", "manifest.json"]
    args.output.mkdir(parents=True)
    for name in assets:
        (args.output / name).write_bytes(members[name])
    with zipfile.ZipFile(args.output / "complete-analysis.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)
    body = (args.output / "complete-analysis.zip").read_bytes()
    receipt = dict(url=inputs["complete_download_url"], **pin(body), members=len(members),
        sufficient_inputs=58, standalone_full_assets=len(assets) + 1,
        jurisdictions=51, complete_state_mode_decisions=204, changed_unsupported_mode_decisions=23,
        preserved_decisions=181, available_official_decisions_preserved=102,
        qualified_mode_decisions_preserved=67, residual_non_mode_specific_selections=0,
        source_counts_modified=False, new_normalized_mode_or_population_qualification=False)
    (source / "download.json").write_bytes(encoded(receipt))
    print(json.dumps(dict(status="PASS_complete_mode_frame_package_NOT_native_website_acceptance", **receipt)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["output", "browser", "navigation", "preserved", "size"]:
        parser.add_argument("--" + name, type=Path, required=True)
    build(parser.parse_args())

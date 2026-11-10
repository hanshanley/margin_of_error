"""Package every Maine source, mapped and held locality query with full sufficient held inputs."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-maine-locality-activity-01"
REPRODUCE = """import {loadMaineLocalityActivity} from './scripts/maine-locality-activity.mjs';
process.stdout.write(JSON.stringify(loadMaineLocalityActivity(),null,2)+'\\n');
"""


def csv_bytes(rows):
    out = io.StringIO()
    fields = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(out, fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, separators=(",", ":")) if isinstance(v, (dict, list)) else v
                         for k, v in row.items()})
    return out.getvalue().encode()


def build(output):
    if output.exists() or (ROOT / VERSION / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable Maine query package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    inputs = json.loads((ROOT / VERSION / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {VERSION + "/inputs.json",
        "scripts/maine-locality-activity.mjs", "scripts/maine-locality-activity.test.mjs",
        "scripts/build-maine-locality-inputs.py", "scripts/package-maine-locality-activity.py",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js"}
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed sufficient Maine original or complete identity/reference input")
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["queries.json"] = raw
    tables = {
        "all1168-source-region-queries.csv": queries["complete_source_region_queries"],
        "all1056-reference-queries.csv": queries["complete_reference_queries"],
        "all2-source-frame-decisions.csv": queries["complete_frame_queries"],
        "all960-mapped-locality-queries.csv": [r for rows in queries["locality_frames"].values() for r in rows],
    }
    for name, rows in tables.items():
        members[name] = csv_bytes(rows)
    members["README.txt"] = """MAINE: COMPLETE PARTIAL LOCALITY SOURCE-ACTIVITY QUERIES

Contents
All 1,168 native source-region queries (584 in each separate activity mode),
all 1,056 contextual reference decisions (528 per mode), both complete source
frame decisions and 960 selected source-locality observations (480 per mode).
Original provider JSONs, safe receipts, full 528-area 2024 reference geometry,
the complete 5,029-row held historical identity export, code/tests and results.
HTTP session headers and compiled publisher app code are excluded.

Counts are not turnout
Counts sum literal civicAPI source-category "votes" cells within ONE early
in-person or returned activity frame. Source buckets are not candidate choices;
operational affiliation, cast/accepted ballots and unique-person definitions
remain unqualified. Do not add early and returned modes. All denominators and
analysis rates are null. Native Other/Unknown/Unspecified/zero cells survive.
Collector 2026 context is not an independently qualified native election ID.
Native November 2, 2026 snapshot dates remain; clock/timezone is not inferred.

Partial geography, no allocation
480 source regions have one-to-one older contextual identities per mode.
441 use already-qualified 2024 identity links; 39 use unambiguous literal
Twp/Plt name suffixes. Historical voting counts/rates are NEVER transferred.
Each mode retains 104 native regions and 48 reference areas held. Ambiguous
Lincoln/Rangeley/Unity/Washington Plt/Twp records are not assigned by elimination.
Unmatched reference areas remain unknown, not zero. Source activity is not
aggregated into counties, unorganized areas or precincts. No clipping, repair
or coordinate change occurs: the full original reference gzip is unchanged.
Reference keys are contextual identities, not native FIPS or certified 2026
election/precinct boundaries. All held source cells remain in the full tables.

Offline reproduction (Node 22+, no packages or network needed)
Extract every member into an empty directory, then run:
  node reproduce.mjs > reproduced-queries.json
Compare byte-for-byte to queries.json. Run the focused tests:
  node --test scripts/maine-locality-activity.test.mjs

manifest.json hashes every other member. CSV empty values correspond to JSON
nulls; complete original JSON distinguishes literal source cells. Earlier full
releases are not replaced. This package is complete, not a metadata-only ledger.
""".encode()
    members["manifest.json"] = (json.dumps(dict(summary=queries["summary"], files={
        name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(members.items())}), indent=2) + "\n").encode()
    output.mkdir(parents=True)
    for name in ["queries.json", *tables, "README.txt", "manifest.json"]:
        (output / name).write_bytes(members[name])
    with zipfile.ZipFile(output / "complete-analysis.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)
    body = (output / "complete-analysis.zip").read_bytes()
    receipt = dict(url=inputs["complete_download_url"], bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(), members=len(members),
        complete_source_queries=1168, complete_reference_queries=1056, complete_frame_queries=2,
        mapped_per_mode=480, held_native_per_mode=104, held_reference_per_mode=48,
        analysis_rates_approved=False)
    (ROOT / VERSION / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (ROOT / VERSION / "summary.json").write_text(json.dumps(queries["summary"], indent=2) + "\n")
    (ROOT / VERSION / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)

"""Package all102 provider frame decisions and6371 region records with complete sufficient held inputs."""

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
VERSION = "data/county-source-reviews/20261109-provider-county-frames-01"
REPRODUCE = """import {loadProviderCountyFrames} from './scripts/provider-county-frames.mjs';
process.stdout.write(JSON.stringify(loadProviderCountyFrames(),null,2)+'\\n');
"""


def csv_bytes(rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    out = io.StringIO()
    writer = csv.DictWriter(out, fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, separators=(",", ":"))
            if isinstance(value, (dict, list)) else value for key, value in row.items()})
    return out.getvalue().encode()


def build(output):
    if output.exists() or (ROOT / VERSION / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable provider query package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    inputs = json.loads((ROOT / VERSION / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {VERSION + "/inputs.json",
        "scripts/provider-county-frames.mjs", "scripts/provider-county-frames.test.mjs",
        "scripts/build-provider-county-inputs.py", "scripts/package-provider-county-frames.py",
        "public/scripts/participation-geography.js"}
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed sufficient provider source input")
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["queries.json"] = raw
    members["complete-state-mode-decisions.csv"] = csv_bytes(queries["frame_queries"])
    members["complete-source-region-queries.csv"] = csv_bytes(queries["region_queries"])
    members["complete-qualified-county-queries.csv"] = csv_bytes([
        row for frames in queries["county_frames"].values() for rows in frames.values() for row in rows])
    members["README.txt"] = """COUNTY ACTIVITY: COMPLETE SOURCE QUERIES

Contents
  102 state/mode decisions, including missing and held frames.
  6,371 original regional records from all 79 captured provider responses.
  63 qualified county frames in 39 states: 4,731 county observations.
  Full original Census references, source receipts, code, tests and results.

The website preserves two stronger official West Virginia frames instead of
their provider copies. It therefore uses 61 provider frames in 38 states.

What the counts mean
Counts sum the provider's literal source-category "votes" cells within ONE
early in-person or returned activity frame. They are not candidate choices,
full-election turnout, qualified cast/accepted ballots or deduplicated people.
Do not add early and returned frames. Source affiliation definitions remain
unqualified; original Unknown/Other/Unspecified buckets, colors, zeros and
state-category tallies are preserved. All analysis denominators/rates are null.
No population, survey or candidate allocation, fitting or invented intervals.

Dates and identity
Native snapshot dates October 23-November 4, 2026 remain literal. Election-year
context comes from the collector; no independent native election identifier
is qualified. Original dataset directory 20261104T220424Z and source snapshot
20261104T220425Z are distinct identifiers and have not been repaired.
Complete county inventories are matched to separate 2026 Census references,
not native FIPS or certified precinct boundaries. Arkansas "St Francis" is
the reviewed spelling of "St. Francis County"; counts are unchanged.

Selection and holds
Native county observations, including zeros and partial snapshots, keep
priority. Best available uses one uniform activity frame only when native
county counts are absent. Explicit Official never promotes provider data.
Town, mixed, partial and state-only frames remain held. Their county_fips is
null; candidate_county_fips is only an unapproved county-name match. Missing
counts are not zeros. CSV empty values correspond to nulls in queries.json.

Privacy and provenance
Receipts contain safe source URL/date/status/hash facts. HTTP session headers,
compiled publisher app code, voter/survey identifiers and private fine cells
are excluded. Earlier archives are not replaced.

Offline reproduction (Node 22+, no packages or network needed)
Extract every member into an empty directory, then run:
  node reproduce.mjs > reproduced-queries.json
Compare byte-for-byte to queries.json. Run the focused tests:
  node --test scripts/provider-county-frames.test.mjs

manifest.json checksums every other member. The three complete CSVs contain
all frame decisions, all source-region queries, and all qualified county rows.
""".encode()
    manifest = dict(summary=queries["summary"], files={
        name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(members.items())})
    members["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.mkdir(parents=True)
    for name in ["queries.json", "complete-state-mode-decisions.csv", "complete-source-region-queries.csv",
                 "complete-qualified-county-queries.csv", "README.txt", "manifest.json"]:
        (output / name).write_bytes(members[name])
    archive = output / "complete-analysis.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as target:
        for name, body in sorted(members.items()):
            target.writestr(name, body)
    receipt = dict(url=inputs["complete_download_url"], bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), members=len(members),
        complete_state_mode_queries=102, all_source_region_queries=6371,
        approved_county_frames=63, approved_states=39, analysis_rates_approved=False)
    (ROOT / VERSION / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (ROOT / VERSION / "summary.json").write_text(json.dumps(queries["summary"], indent=2) + "\n")
    (ROOT / VERSION / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)

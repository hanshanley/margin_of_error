"""Package all CT town/Total queries, native versions, full contextual references and offline code."""

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
VERSION = "data/county-source-reviews/20261110-connecticut-towns-01"
REPRODUCE = """import {loadConnecticutTowns} from './scripts/connecticut-town-counts.mjs';
process.stdout.write(JSON.stringify(loadConnecticutTowns(),null,2)+'\\n');
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
        raise ValueError("Refuse to replace an immutable CT query package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    inputs = json.loads((ROOT / VERSION / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {VERSION + "/inputs.json",
        "scripts/connecticut-town-counts.mjs", "scripts/connecticut-town-counts.test.mjs",
        "scripts/build-connecticut-town-inputs.py", "scripts/package-connecticut-town-counts.py",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js"}
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed sufficient CT original or full reference")
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["queries.json"] = raw
    members["all169-town-queries.csv"] = csv_bytes(queries["towns"])
    members["all170-native-source-queries.csv"] = csv_bytes([
        dict(source_town_id=id, source_scope="Total" if id == "170" else "town",
             selected_for_town_map=id != "170", **row)
        for id, row in queries["all_native_source_queries"].items()])
    members["all-eight-column-accounting.csv"] = csv_bytes(queries["accounting"])
    members["README.txt"] = """CONNECTICUT: COMPLETE NATIVE TOWN PARTICIPATION QUERIES

What is included
All 169 town observations and the separate native Total (170 source rows);
all eight original numeric columns, blank reporting counters, printed TO and
town statuses; both source versions, independent election parent, native
election metadata, full original/derived reference shapes, code/tests/results.
HTTP session headers and compiled publisher app code are excluded.

Counts and holds
The map uses the literal native town VV field, not candidate votes, generic
certified cast ballots or unique people. All 169 VV cells sum to 1,150,127.
The native Total is NOT an extra town. All eight source columns reconcile to
that separate Total. EV, ABR/ABC, EBR/EBC and EDR/EDC cells and printed TO remain
literal; their definitions are not silently harmonized. No modes are added.
All analysis denominators/rates are null. Thirteen town PR cells are blank,
not zero. Reporting counters do not create precinct observations.

Election and geography
Native metadata identifies election 108 as November 3, 2026. Version tokens
52337 and 52338 are not clocks; their complete turnout payloads are identical.
Native update clock/timezone is absent; retrieval is not a counting cutoff.
Each native town joins to one full held 2024 contextual municipality shape,
without coordinate changes, clipping, repair or count allocation. The derived
CT-TOWN IDs are not FIPS. Original municipality keys remain reference-only.
These are NOT certified 2026 boundaries, nine county totals or 776 precincts.
Native counts, printed values and source conflicts are never repaired.

Offline reproduction (Node 22+, no packages or network needed)
Extract every member into an empty directory, then run:
  node reproduce.mjs > reproduced-queries.json
Compare byte-for-byte to queries.json. Run the focused tests:
  node --test scripts/connecticut-town-counts.test.mjs

manifest.json hashes every other member. The three CSVs contain all selected
towns, every original town/Total query, and every native column comparison.
Empty CSV values correspond to nulls or original empty source strings; the
complete original JSON distinguishes them. Older full releases remain intact.
""".encode()
    members["manifest.json"] = (json.dumps(dict(summary=queries["summary"], files={
        name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(members.items())}), indent=2) + "\n").encode()
    output.mkdir(parents=True)
    for name in ["queries.json", "all169-town-queries.csv", "all170-native-source-queries.csv",
                 "all-eight-column-accounting.csv", "README.txt", "manifest.json"]:
        (output / name).write_bytes(members[name])
    with zipfile.ZipFile(output / "complete-analysis.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)
    body = (output / "complete-analysis.zip").read_bytes()
    receipt = dict(url=inputs["complete_download_url"], bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(), members=len(members),
        native_town_observations=169, all_native_source_queries=170, analysis_rates_approved=False)
    (ROOT / VERSION / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (ROOT / VERSION / "summary.json").write_text(json.dumps(queries["summary"], indent=2) + "\n")
    (ROOT / VERSION / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)

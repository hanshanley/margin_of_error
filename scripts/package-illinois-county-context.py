"""Package all Illinois county-named/city-named source queries and unchanged context."""

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
VERSION = "data/county-source-reviews/20261110-illinois-county-context-01"
REPRODUCE = """import {loadIllinoisCountyContext} from './scripts/illinois-county-context.mjs';
process.stdout.write(JSON.stringify(loadIllinoisCountyContext(),null,2)+'\\n');
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
        raise ValueError("Refuse to replace an immutable Illinois source-context query package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    inputs = json.loads((ROOT / VERSION / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {VERSION + "/inputs.json",
        "scripts/illinois-county-context.mjs", "scripts/illinois-county-context.test.mjs",
        "scripts/build-illinois-county-context-inputs.py", "scripts/package-illinois-county-context.py",
        "scripts/check-illinois-county-context-browser.py",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js"}
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed sufficient Illinois original/context input")
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["queries.json"] = raw
    tables = {
        "all216-source-region-queries.csv": queries["source_queries"],
        "all204-county-context-decisions.csv": queries["reference_queries"],
        "all2-source-frame-decisions.csv": queries["frame_queries"],
        "all204-context-counts.csv": [r for rows in queries["county_context_frames"].values() for r in rows],
    }
    for name, rows in tables.items():
        members[name] = csv_bytes(rows)
    members["README.txt"] = """ILLINOIS: SOURCE-REGION ACTIVITY ON COUNTY CONTEXT, NOT COUNTY TOTALS

Complete contents
Both complete held civicAPI responses, unchanged full 102-county contextual
reference, safe source receipts and pins, independent numerical code, tests,
all 216 source-region queries, all 204 reference decisions and both frame
decisions. All 204 selected contextual observations and all 12 held city rows
remain in queries.json. No metadata-only replacement or missing source query.

Exactly what is displayed
Each separate native mode contains 108 named regions: 102 county-named records
and six City of ... records (Bloomington, Chicago, Danville, East St Louis,
Galesburg and Rockford). We put the 102 literal county-named records on a Census
county reference solely to locate their labels. A county shape is NOT a
qualified source-authority territory or a claim that the record covers every
part of the county. These values are NOT whole-county totals.
City records are never assigned to counties, added into county-named records,
allocated by geography or matched by elimination. We do not assume any city's
territorial jurisdiction is confined to one county. Both complete source-
category parent sums reconcile independently across all 108 native records.

Separate source snapshots
Early: 1,162,828 source activity counts = 915,498 county-named + 247,330 city.
Returned: 892,086 = 759,410 county-named + 132,676 city. DO NOT add the modes.
Counts sum literal native category "votes" cells, preserving Unspecified,
unknown categories and source zeros. They are not candidate choices, certified
cast/accepted ballots, deduplicated people, demographic participation or turnout.
All analysis denominators/rates are null. Native date November 4, 2026 remains;
clock and timezone are absent. Collector 2026 context is not an independently
qualified native election ID.

Geography and access
Source labels have unique county-name contextual matches; contextual FIPS
are derived reference keys, NOT native source geography IDs. The full original
2026 Census county gzip is byte-identical. No source geometry repair, clipping,
source-authority boundary certification, precinct inference or count allocation.
Official authority-directory access denials were stopped; no alternate client,
cache, mirror, challenge bypass or unpublished numerical original is implied.
Public page code, acquisition headers and contact/person-level records are
not part of this package.

Offline reproduction (Node 22+, no packages or network needed)
Extract every member into an empty directory:
  node reproduce.mjs > reproduced-queries.json
Compare byte-for-byte to queries.json, then run:
  node --test scripts/illinois-county-context.test.mjs

manifest.json hashes every other member. Empty CSV fields correspond to JSON
nulls; native JSON retains literal cells. Older releases are not replaced.
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
        complete_source_queries=216, complete_reference_queries=204, complete_frame_queries=2,
        contextual_regions_per_mode=102, city_holds_per_mode=6,
        whole_county_counts_qualified=False, authority_territories_qualified=False,
        native_election_id_qualified=False, rates_approved=False)
    (ROOT / VERSION / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (ROOT / VERSION / "summary.json").write_text(json.dumps(queries["summary"], indent=2) + "\n")
    (ROOT / VERSION / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)

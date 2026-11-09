"""Package all 25 native card queries and the new 24-county reference join."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-maryland-cards-01"
PUBLIC = "public/participation-county-cards/20261109-01/complete-analysis.zip"
REPRODUCE = """import { readFileSync } from 'node:fs';
import { loadMarylandCardCounts } from './scripts/maryland-county-cards.mjs';
const grid = JSON.parse(readFileSync('data/county-source-reviews/20261109-maryland-cards-01/independent-card-grid.json'));
process.stdout.write(JSON.stringify({ county_counts: loadMarylandCardCounts(),
  separate_native_state_reference: grid.rows.at(-1) }, null, 2) + '\\n');
"""


def build(original_parser):
    output = ROOT / VERSION
    archive = ROOT / PUBLIC
    if archive.exists() or (output / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable Maryland package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    if len(queries["county_counts"]) != 24 or queries["separate_native_state_reference"]["native_county_label"] != "Total":
        raise ValueError("Incomplete Maryland county/state query")
    inputs = json.loads((output / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {
        VERSION + "/inputs.json", "scripts/maryland-county-cards.mjs",
        "scripts/build-maryland-county-card-inputs.py", "scripts/package-maryland-county-cards.py",
        "scripts/maryland-county-cards.test.mjs",
    }
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed sufficient Maryland input: " + name)
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["queries.json"] = raw
    members["source-review/extract_maryland_election_frames.py"] = original_parser.read_bytes()
    members["source-review/requirements.txt"] = b"openpyxl==3.1.5\npdfplumber==0.11.8\n"
    members["README.txt"] = (
        "Maryland2026 complete source card-count query and 24-county reference join\n"
        "24 county-equivalent card observations plus the separate native state parent.\n"
        "Cards Cast is NOT qualified cast ballots, certified unique voters or a turnout rate.\n"
        "Original title includes MIB1/early voting/election day/MIB2; native run11/8/2026 7:44pm,\n"
        "timezone not supplied. Reporting counters are not individual precinct records or final counting.\n"
        "All25 native rows, original full PDF, independently verified grid, complete accepted card query,\n"
        "scope holds and full24-county2026Census geometry are included, not metadata-only.\n"
        "Baltimore city/county remain separate. Saint Mary's/St. Mary's has one explicit documented alias.\n"
        "Native Eligible Voters/percentages are retained, never promoted to qualified denominators/rates.\n"
        "No model fitting/allocation, party participation, precinct geometry or statewide voter total inferred.\n"
        "Extract every member into an empty directory; Node22+ needs no network/npm:\n"
        "  node reproduce.mjs > reproduced-queries.json\n"
        "Compare reproduced-queries.json byte-for-byte with queries.json.\n"
        "The original independent report parser is supplied separately with its existing dependencies.\n"
        "The prior native28 and every historical query/download remain unchanged.\n"
    ).encode()
    manifest = dict(version=VERSION, native_queries=25, mapped_county_card_queries=24,
        analysis_rates_approved=False, cast_ballot_count_qualified=False,
        unique_voter_count_qualified=False,
        files={name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
               for name, body in sorted(members.items())})
    members["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as target:
        for name, body in sorted(members.items()):
            target.writestr(name, body)
    (output / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (output / "manifest.json").write_bytes(members["manifest.json"])
    receipt = dict(archive=PUBLIC, bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), members=len(members),
        native_queries=25, mapped_county_card_queries=24)
    (output / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-parser", type=Path, required=True)
    build(parser.parse_args().original_parser)

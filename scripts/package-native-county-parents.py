"""Package complete sufficient inputs and all native county-parent queries offline."""

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261109-native-county-parents-01"
OUTPUT = ROOT / "data/county-source-reviews" / VERSION
PUBLIC = ROOT / "public/participation-county-parents/20261109-01/complete-analysis.zip"
REPRODUCE = """import { loadNativeCountyParents } from './scripts/native-county-parents.mjs';
process.stdout.write(JSON.stringify(loadNativeCountyParents(), null, 2) + '\\n');
"""


def build():
    if OUTPUT.exists() or PUBLIC.exists():
        raise ValueError("Refuse to replace a published native county-parent snapshot")
    raw = subprocess.check_output(
        ["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    if len(queries) != 97 or sum(row["reported_pct"] is not None for row in queries) != 43:
        raise ValueError("Unexpected native county query coverage")
    inputs = {
        "public/precinct-results.json", "public/county-results.json",
        "scripts/native-county-parents.mjs", "scripts/package-native-county-parents.py",
    }
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    inputs.add(pointer["data_directory"] + "/index.json")
    for row in queries:
        base = row["snapshot"]["data_directory"]
        inputs.update({base + "/checksums.json", base + "/participation.json.gz",
                       base + "/" + row["sourceFile"], row["reference"]["path"]})
        if row["code"] == "ID":
            inputs.add(base + "/count-review/originals/ballots-by-precinct.xlsx.gz")
        else:
            inputs.update({base + "/originals/election.json.gz", base + "/originals/turnout.json.gz"})
    members = {name: (ROOT / name).read_bytes() for name in sorted(inputs)}
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["queries.json"] = raw
    table = io.StringIO()
    fields = ["code", "county", "fips", "ballots", "denominator", "reported_pct",
              "denominator_basis", "source_update_label", "source_status_literal", "flags"]
    writer = csv.DictWriter(table, fields, lineterminator="\n")
    writer.writeheader()
    for row in queries:
        record = {field: row[field] for field in fields}
        record["flags"] = "; ".join(record["flags"])
        writer.writerow(record)
    members["queries.csv"] = table.getvalue().encode()
    members["README.txt"] = (
        "2026 native county participation parents: complete sufficient-input reproduction\n"
        "97 county queries: Idaho44; North Dakota53. No query or hold is omitted.\n"
        "Counts are explicit native whole-county ballot parents, not candidate sums.\n"
        "All986 Idaho and358 North Dakota participation rows are retained as validation inputs.\n"
        "Idaho county ballots match the independent original ballot-report workbook.\n"
        "43 Idaho native-registration fractions; Twin Falls rate withheld for conflicting registrations.\n"
        "All53 North Dakota analysis rates and denominators remain withheld; the native API field is preserved.\n"
        "2026 Census county reference shapes and both complete state identity sets are included.\n"
        "These are unofficial captured snapshots, not final, demographic or precinct turnout rates.\n"
        "Original source clocks and literal reporting/certification flags remain unchanged.\n"
        "Extract this entire archive into an empty directory. With Node22+, run:\n"
        "  node reproduce.mjs > reproduced-queries.json\n"
        "Compare reproduced-queries.json byte-for-byte with queries.json.\n"
        "The original gzip inputs, code and every query/hold are included; no network or npm install is needed.\n"
    ).encode()
    manifest = {
        "version": VERSION,
        "queries": len(queries),
        "selected_rates": 43,
        "withheld_rates": 54,
        "files": {name: {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
                  for name, value in members.items()},
    }
    members["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    OUTPUT.mkdir(parents=True)
    (OUTPUT / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (OUTPUT / "queries.csv").write_bytes(members["queries.csv"])
    (OUTPUT / "manifest.json").write_bytes(members["manifest.json"])
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(PUBLIC, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    result = {"archive": str(PUBLIC.relative_to(ROOT)), "bytes": PUBLIC.stat().st_size,
              "sha256": hashlib.sha256(PUBLIC.read_bytes()).hexdigest(),
              "members": len(members), "queries": 97, "selected_rates": 43, "withheld_rates": 54}
    (OUTPUT / "download.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    build()

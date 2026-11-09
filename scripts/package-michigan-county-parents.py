"""Package every Michigan county-parent query and its complete sufficient originals."""

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-michigan-native-parents-01"
PUBLIC = "public/participation-county-parents/20261109-02/complete-analysis.zip"
REPRODUCE = """import { loadMichiganCountyParents } from './scripts/michigan-county-parents.mjs';
process.stdout.write(JSON.stringify(loadMichiganCountyParents(), null, 2) + '\\n');
"""


def build():
    output = ROOT / VERSION
    archive = ROOT / PUBLIC
    if archive.exists() or (output / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable Michigan county-parent package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    if (len(queries) != 2 or [row["fips"] for row in queries] != ["26017", "26073"]
            or any(row["reported_pct"] is not None or row["denominator"] is not None for row in queries)):
        raise ValueError("Incorrect Michigan query or held-rate inventory")
    inputs = json.loads((output / "inputs.json").read_bytes())
    paths = set(inputs["files"])
    paths.update({
        VERSION + "/inputs.json", "public/participation-source-reviews.json",
        "scripts/michigan-county-parents.mjs", "scripts/build-michigan-county-parent-inputs.py",
        "scripts/package-michigan-county-parents.py",
    })
    source = inputs["source_directory"]
    checksums = json.loads((ROOT / source / "checksums.json").read_bytes())
    paths.add(source + "/checksums.json")
    for name, receipt in checksums.items():
        body = (ROOT / source / name).read_bytes()
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed original Michigan review input: " + name)
        paths.add(source + "/" + name)
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["queries.json"] = raw
    table = io.StringIO()
    fields = ["code", "county", "fips", "ballots", "denominator", "reported_pct",
              "denominator_basis", "source_update_label", "source_status_literal",
              "reported_units", "total_units", "flags", "rate_status"]
    writer = csv.DictWriter(table, fields, lineterminator="\n")
    writer.writeheader()
    for row in queries:
        record = {field: row.get(field) for field in fields}
        record["flags"] = "; ".join(row["flags"])
        record["rate_status"] = "withheld"
        writer.writerow(record)
    members["queries.csv"] = table.getvalue().encode()
    members["README.txt"] = (
        "2026 Michigan native county ballot parents: complete sufficient-input reproduction\n"
        "Two county queries: Bay50246; Isabella26288. Both analysis rates/denominators are withheld.\n"
        "These are explicit native county parents, not House votes or derived precinct sums.\n"
        "Bay's43 reporting counter versus35 report sections remains unresolved.\n"
        "Isabella's22 City of Clare election ballots versus0 House-scope ballots are not repaired.\n"
        "All63 native unit records, all four complete workbook tables, original workbook,\n"
        "five original PDFs, all three native API responses and portable original reviewer are included.\n"
        "Full83-county 2026 Census reference, source receipts and partial two-county scope are included.\n"
        "Other81 counties are missing, not zero; no precinct geometry or statewide total is inferred.\n"
        "Old native97-query and Michigan source archives are unchanged.\n"
        "Extract this entire archive into an empty directory. With Node22+, run:\n"
        "  node reproduce.mjs > reproduced-queries.json\n"
        "Compare reproduced-queries.json byte-for-byte with queries.json. No network/npm is needed.\n"
        "The separate first-page extraction script uses PyMuPDF and the retained original reviewer;\n"
        "its --output option accepts a new directory without replacing published inputs.\n"
        "No original acquisition or full source reduction must be repeated for these queries.\n"
    ).encode()
    manifest = {
        "version": VERSION, "queries": 2, "selected_ballot_counts": 2, "withheld_rates": 2,
        "native_reporting_unit_rows": 63, "reference_counties": 83,
        "observed_county_fips": ["26017", "26073"],
        "files": {name: {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
                  for name, body in members.items()},
    }
    members["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as target:
        for name, body in members.items():
            target.writestr(name, body)
    (output / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (output / "queries.csv").write_bytes(members["queries.csv"])
    (output / "manifest.json").write_bytes(members["manifest.json"])
    receipt = {"archive": PUBLIC, "bytes": archive.stat().st_size,
               "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
               "members": len(members), "queries": 2, "withheld_rates": 2}
    (output / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    build()

"""Package complete native city originals, visual readings, all queries and exact context."""

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
VERSION = "data/county-source-reviews/20261110-new-hampshire-cities-01"
REPRODUCE = """import {loadNewHampshireCities} from './scripts/new-hampshire-city-counts.mjs';
process.stdout.write(JSON.stringify(loadNewHampshireCities(),null,2)+'\\n');
"""


def csv_bytes(rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    out = io.StringIO()
    writer = csv.DictWriter(out, fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, separators=(",", ":")) if isinstance(v, (list, dict)) else v
                         for k, v in row.items()})
    return out.getvalue().encode()


def build(output):
    if output.exists() or (ROOT / VERSION / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable NH city query package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    inputs = json.loads((ROOT / VERSION / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {VERSION + "/inputs.json",
        "scripts/new-hampshire-city-counts.mjs", "scripts/new-hampshire-city-counts.test.mjs",
        "scripts/build-new-hampshire-city-inputs.py", "scripts/package-new-hampshire-city-counts.py",
        "scripts/check-new-hampshire-city-counts-browser.py",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js"}
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed actual original or exact visual/reference input")
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["queries.json"] = raw
    tables = {
        "all107-native-source-field-queries.csv": queries["source_queries"],
        "all12-source-accounting-queries.csv": queries["source_accounting_queries"],
        "all11-printed-rate-basis-queries.csv": queries["source_printed_rate_basis_queries"],
        "all259-municipality-reference-decisions.csv": queries["reference_queries"],
        "all2-native-city-source-counts.csv": queries["municipalities"],
        "all22-native-ward-source-counts.csv": queries["ward_rows"],
    }
    for name, rows in tables.items():
        members[name] = csv_bytes(rows)
    members["README.txt"] = """NEW HAMPSHIRE: TWO CITY SOURCE SNAPSHOTS, NOT STATE/COUNTY/PRECINCT TURNOUT

Complete sufficient inputs and outputs
All thirteen actual complete official PDFs: twelve declared Manchester ward
packets (183 pages / 105,248,219 bytes) and Concord's four-page general report
(175,306 bytes). Complete native headers/ballot crops, the three independently
enlarged ambiguous/revised fields, Concord's native closing block, exact visual
readings, safe original/index receipts and actual declared ward links, full
unchanged 259-area 2024 municipality reference, code/tests and ALL queries.
Private discovery HTML/session state and compiled publisher code are excluded.
This is not a metadata-only package.

Manchester
Native first-page fields are Election Day Ballots Cast, Absentee Ballots Cast,
Total Ballots Cast and Federal Office Only Ballots Cast. The complete twelve
printed totals sum to 38,562; this is a derived literal-field sum, NOT a
separately printed city parent. Election Day sums to 36,272 and absentee to
2,375. Ward7 PRINTS 2,712 versus 2,694 + 103 = 2,797. The 85-ballot source
disagreement is retained, never repaired from arithmetic or candidate votes.
Federal-only fields sum to 76 separately and are NEVER added into Total.
Their inclusion in native Total is not inferred. Ward4 explicitly strikes
through8 and writes2; preserve that source revision, not an analysis repair.
Wards4/5/10 carry native November4 revision labels. No common clock/timezone
or final counting/certification is inferred from filenames or upload tokens.

Concord
Native Total Cast is 19,234. Its twelve source columns include separate CSD/
MVSD cells in Wards1/2, plus separately PRINTED ward subtotals1,985/1,764.
The split cells, printed ward subtotals and city parent are separate records,
not amounts to add together. Ten ward rows remain distinct from twelve columns.
Opening registered voters25,879 + Election Day registrations1,461 = closing
registered voters27,340. Native printed Turn Out74.32% (and all ten ward
percentages) arithmetically uses OPENING, not closing. Original percentages/
stocks remain untouched; this diagnostic does NOT qualify an analysis rate.
The native measure is Total Cast; generic certified cast-ballot or unique-
person definitions are not inferred.

Scope and map context
Both native general-election sources identify November3,2026. All analysis
denominators/rates are null. No candidate selections, demographics, estimated
state shares, federal allocations or repaired source counts are substituted.
Only Manchester/Concord source snapshots join uniquely to older municipality
context; all259 reference decisions remain, with257 unknown areas NOT zero.
Full original2024 reference gzip is unchanged, and the two selected shapes
are valid without repair. This is not certified2026 legal election/ward
geography. All22 native ward rows remain TABLE-ONLY; no older boundaries or
city/count values are painted onto precincts.

Outputs
107 literal source fields,12 source-accounting decisions,11 printed-rate-basis
diagnostics,259 full reference decisions,two source-city profiles and22 ward
rows. Native registered/printed-rate cells remain separate from counts.

Offline reproduction (Node22+, no packages or network needed)
Extract EVERY member to an empty directory, then run:
  node reproduce.mjs > reproduced-queries.json
Compare byte-for-byte to queries.json. Run focused tests:
  node --test scripts/new-hampshire-city-counts.test.mjs

The loader verifies every complete original and visual/reference input hash.
Scanned native digits were visually read from exact PDF-derived crops, not
repaired OCR or inferred candidate sums. Original PDFs permit independent
glyph review. manifest.json hashes every other member; CSV blanks are JSON
nulls. Older immutable releases and complete downloads remain intact.
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
        original_pdfs=13, original_pages=187, original_bytes=105423525,
        complete_source_field_queries=107, complete_reference_queries=259,
        native_ward_rows=22, source_city_observations=2, unmapped_reference_areas=257,
        source_counts_repaired=False, federal_only_added=False, analysis_rates_approved=False)
    (ROOT / VERSION / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (ROOT / VERSION / "summary.json").write_text(json.dumps(queries["summary"], indent=2) + "\n")
    (ROOT / VERSION / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)

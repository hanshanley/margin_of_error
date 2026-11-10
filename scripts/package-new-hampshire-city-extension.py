"""Package all four city snapshots and every preserved or new sufficient input."""

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
VERSION = "data/county-source-reviews/20261110-new-hampshire-cities-02"
REPRODUCE = """import {loadNewHampshireCityExtension} from './scripts/new-hampshire-city-extension.mjs';
process.stdout.write(JSON.stringify(loadNewHampshireCityExtension(),null,2)+'\\n');
"""


def csv_bytes(rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    out = io.StringIO()
    writer = csv.DictWriter(out, fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, separators=(",", ":"))
                         if isinstance(value, (list, dict)) else value for key, value in row.items()})
    return out.getvalue().encode()


def build(output):
    if output.exists() or (ROOT / VERSION / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable four-city package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    inputs = json.loads((ROOT / VERSION / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {VERSION + "/inputs.json",
        "scripts/new-hampshire-city-counts.mjs", "scripts/new-hampshire-city-counts.test.mjs",
        "scripts/new-hampshire-city-extension.mjs", "scripts/new-hampshire-city-extension.test.mjs",
        "scripts/build-new-hampshire-city-inputs.py", "scripts/build-new-hampshire-city-extension-inputs.py",
        "scripts/package-new-hampshire-city-extension.py", "scripts/check-new-hampshire-city-counts-browser.py",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js"}
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed original, exact reading, visual evidence or full reference")
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["queries.json"] = raw
    tables = {
        "all242-native-source-field-queries.csv": queries["source_queries"],
        "all28-source-accounting-queries.csv": queries["source_accounting_queries"],
        "all18-printed-rate-basis-queries.csv": queries["source_printed_rate_basis_queries"],
        "all259-municipality-reference-decisions.csv": queries["reference_queries"],
        "all4-native-city-source-counts.csv": queries["municipalities"],
        "all37-native-ward-source-counts.csv": queries["ward_rows"],
    }
    for name, rows in tables.items():
        members[name] = csv_bytes(rows)
    members["README.txt"] = """NEW HAMPSHIRE: FOUR CITY SOURCES, NOT STATE/COUNTY/PRECINCT TURNOUT

COMPLETE CONTENTS
All15 complete official PDFs /217 pages /113,898,265 native bytes. Every
first-release original, visual reading and source field is preserved.
Includes all107 previous plus135 new source-field queries (242 total), full
unchanged259-area2024 municipality reference, all259 reference decisions,
28 accounting decisions,18 percentage-basis diagnostics, four city profiles,
37 TABLE-ONLY ward rows, exact native visual evidence, safe declarations/
receipts, code, tests and results. Private discovery HTML, request/session
headers and compiled publisher code are excluded. Not metadata-only.

LITERAL COUNTS AND SOURCE CONFLICTS
Manchester38,562 is a DERIVED sum of12 printed ward totals, not a separately
printed city parent. Ward7 prints2712 versus2694+103=2797; retain85 disagreement.
Federal-only76 remains separate and is NEVER added.
Concord's printed Total Cast19,234, CSD/MVSD cells, printed ward subtotals,
opening25,879/ED registrations1,461/closing27,340 and printed74.32% stay
separate. Printed percentages use opening-stock arithmetic, not closing.
Nashua33,849 is a DERIVED sum of9 printed ward totals. Election Day31,952
+ absentee1,895=33,847. Ward3 component-minusTotal+1, Ward4-2, Ward8-1
are source disagreements, not analyst repairs. SOURCE Ward8 red amendments
3349/3575 supersede cancelled3264/3489; absentee225 is unchanged. Federal-
only92 remains separate, NEVER added. Ward6 amendedNovember7; Wards1/3/4/
5/7/8 amendedNovember4;2/9 supply no native revision clock.
Dover prints Total Ballots Cast15,941 = polling-place14,632+absentee1,309.
Native checklist20,972 (verifiedOctober26) + Election Day registrations1,484
= all registered22,456. Native71.0% explicitly uses that source denominator.
The actual report identifies November3,2026 despite its2025.11.03 filename.
Registration-affiliation stocks are NOT ballot choice or group turnout;
poll-day registrations are not first-ever participation or new eligibility.

SCOPE
All four sources identify the November3,2026 general election. Analysis
denominators/rates are null; native printed percentages and explicit
source-defined fraction diagnostics remain separately available.
Four source cities use older2024 municipality CONTEXT;255 other reference
areas remain unknown, not zero. No2026 legal ward/precinct boundaries,
city/ward allocation, source repairs, federal additions, generic certified-
ballot/unique-person claims, demographic fitting or survey allocation.
Source clocks and absences are preserved; collector/upload times are not
native update clocks. Different native measure names remain distinct.

OFFLINE REPRODUCTION
Node22+, no packages or network needed. Extract every member to an empty
directory, then:
  node reproduce.mjs > reproduced-queries.json
Compare byte-for-byte to queries.json. Focused native tests:
  node --test scripts/new-hampshire-city-counts.test.mjs scripts/new-hampshire-city-extension.test.mjs

The loader checks every complete original and exact evidence/reference
input hash. Scanned digits were directly visually reviewed, not repaired
OCR or candidate sums. Native Dover fields are also PDF-text-readable.
manifest.json hashes every other member. CSV blanks represent JSON null.
All earlier immutable packages remain available unchanged.
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
        original_pdfs=15, original_pages=217, original_bytes=113898265,
        complete_source_field_queries=242, complete_reference_queries=259,
        native_ward_rows=37, source_city_observations=4, unknown_reference_areas=255,
        prior_source_values_unchanged=True, source_counts_repaired=False,
        federal_only_added=False, analysis_rates_approved=False)
    (ROOT / VERSION / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (ROOT / VERSION / "summary.json").write_text(json.dumps(queries["summary"], indent=2) + "\n")
    (ROOT / VERSION / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)

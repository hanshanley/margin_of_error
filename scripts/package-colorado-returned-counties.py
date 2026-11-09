"""Package all64 Colorado county queries, native workbook cells and sufficient originals for offline replay."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-colorado-returned-01"
REPRODUCE = """import { loadColoradoCountyReturns } from './scripts/colorado-returned-counties.mjs';
process.stdout.write(JSON.stringify(loadColoradoCountyReturns(), null, 2) + '\\n');
"""
REPRODUCE_WORKBOOK = """import json,runpy
from pathlib import Path
version=Path('data/county-source-reviews/20261109-colorado-returned-01')
decoder=runpy.run_path('scripts/west-virginia-workbooks.py')['original_sheets']
print(json.dumps(decoder(version/'workbook-original.xlsx'),indent=2))
"""


def build(output):
    if output.exists() or (ROOT / VERSION / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable Colorado package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    inputs = json.loads((ROOT / VERSION / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {VERSION + "/inputs.json",
        "scripts/colorado-returned-counties.mjs", "scripts/colorado-returned-counties.test.mjs",
        "scripts/build-colorado-returned-inputs.py", "scripts/package-colorado-returned-counties.py",
        "scripts/west-virginia-workbooks.py"}
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed sufficient Colorado source input")
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["reproduce-workbook.py"] = REPRODUCE_WORKBOOK.encode()
    members["queries.json"] = raw
    members["complete-county-queries.csv"] = (ROOT / VERSION / "native-county-query.csv").read_bytes()
    members["README.txt"] = (
        "Colorado2026: complete64-county returned/processed count and reference query\n"
        "Native ALL RETURNED BALLOTS - MAIL AND IN PERSON COMBINED:2761449.\n"
        "Native separate source parents:returned mail2618985/in-person142464.\n"
        "The displayed all-returned count uses the source's own total, not a researcher mode sum.\n"
        "Returned/processed is NOT cast, accepted, counted, certified, final or unique people.\n"
        "Source period11:59PMNovember5,2026; publicationNovember6; no native timezone supplied.\n"
        "All64county denominators/rates withheld. Native party labels are registration affiliation,\n"
        "not candidate choices. All seven original worksheets/cells/formulas/blanks and original\n"
        "state parents survive. No survey allocation, demographic turnout or fake interval.\n"
        "Every native county identity has a separate exact2026Census reference join; not precincts.\n"
        "The complete original aggregate workbook, full reference, all queries/code/tests/results\n"
        "are included. Acquisition HTTP/session headers, compiled publisher appcode and nonnumerical\n"
        "webpage/legal prose are excluded. Earlier providerNov4modes and frozen readers are unchanged.\n"
        "Extract every member into an empty directory; Node22+ and Python3.9+ need no packages/network:\n"
        "  node reproduce.mjs > reproduced-queries.json\n"
        "Compare byte-for-byte to queries.json. Then:\n"
        "  python3 reproduce-workbook.py > reproduced-workbook.json\n"
        "Compare to decompressed workbook-cells.json.gz under data/county-source-reviews.\n"
        "  node --test scripts/colorado-returned-counties.test.mjs\n"
    ).encode()
    manifest = dict(summary=queries["summary"], files={
        name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(members.items())})
    members["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.mkdir(parents=True)
    for name in ["queries.json", "complete-county-queries.csv", "README.txt", "manifest.json"]:
        (output / name).write_bytes(members[name])
    archive = output / "complete-analysis.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as target:
        for name, body in sorted(members.items()):
            target.writestr(name, body)
    receipt = dict(url=inputs["complete_download_url"], bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), members=len(members),
        county_queries=64, county_counts=64, analysis_rates_approved=False)
    (ROOT / VERSION / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (ROOT / VERSION / "summary.json").write_text(json.dumps(queries["summary"], indent=2) + "\n")
    (ROOT / VERSION / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)

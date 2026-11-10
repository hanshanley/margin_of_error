"""Package complete native Massachusetts inputs, queries, code and exact offline reproduction."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

import bs4
import fitz
import pyproj
import shapely


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261110-massachusetts-native-local-counts-01"
DIRECTORY = "data/county-source-reviews/" + VERSION
REPRODUCE = """import argparse
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
assert not args.output.exists(), 'Use a fresh reproduction directory'
args.output.mkdir(parents=True)
data=root/'data/county-source-reviews/20261110-massachusetts-native-local-counts-01'
tasks=[
 ('review-massachusetts-native-counts-01.py','native-count-review-01'),
 ('review-massachusetts-native-geometry-01.py','native-geometry-review-01'),
 ('review-massachusetts-reference-extension-01.py','native-reference-extension-review-01')]
for name,directory in tasks:
 subprocess.run([sys.executable,str(data/'code'/name),'--root',str(data),'--output',str(args.output/directory)],check=True)
 files=['complete-native-count-queries.json','boston-summary-native.csv','boston-all-native-times-cast.csv','somerville-native-counts.csv'] if directory=='native-count-review-01' else ['complete-native-reference-queries.json'] if directory=='native-geometry-review-01' else ['complete-reference-extension-queries.json.gz','summary.json']
 for filename in files:
  assert (args.output/directory/filename).read_bytes()==(data/directory/filename).read_bytes(), filename
subprocess.run([sys.executable,str(data/'code/verify-massachusetts-native-counts-01.py'),'--root',str(data),'--queries',str(args.output/'native-count-review-01/complete-native-count-queries.json'),'--proof',str(args.output/'native-count-review-01/independent-native-verification.json')],check=True)
assert (args.output/'native-count-review-01/independent-native-verification.json').read_bytes()==(data/'native-count-review-01/independent-native-verification.json').read_bytes()
with (args.output/'queries.json').open('wb') as output:
 subprocess.run(['node',str(root/'reproduce.mjs')],cwd=root,stdout=output,check=True)
assert (args.output/'queries.json').read_bytes()==(root/'queries.json').read_bytes()
print('PASS: all native queries and normalized outputs reproduce exactly')
"""


def digest(body):
    return hashlib.sha256(body).hexdigest()


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    columns = list(dict.fromkeys(key for row in rows for key in row))
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, sort_keys=True, separators=(",", ":"))
                         if isinstance(value, (dict, list)) else value
                         for key, value in row.items()})
    return stream.getvalue().encode()


def build(args):
    version = ROOT / DIRECTORY
    inputs = json.loads((version / "inputs.json").read_bytes())
    if args.output.exists() or (version / "download.json").exists():
        raise ValueError("A complete immutable numerical package cannot be overwritten")
    browser = json.loads(args.browser_proof.read_bytes())
    navigation = json.loads(args.navigation_proof.read_bytes())
    publication = json.loads(args.publication_proof.read_bytes())
    if not all(proof["status"].startswith("PASS") for proof in [browser, navigation, publication]):
        raise ValueError("Actual local source/browser and navigation acceptance must pass first")
    if len(browser["cases"]) != 2 or {row["mobile"] for row in browser["cases"]} != {False, True}:
        raise ValueError("Both real desktop and mobile cases are required")
    expression = (
        "import {loadMassachusettsNativeCounts} from './scripts/massachusetts-native-counts.mjs';"
        "process.stdout.write(JSON.stringify(loadMassachusettsNativeCounts(),null,2)+'\\n');")
    normalized = subprocess.check_output(
        ["node", "--input-type=module", "-e", expression], cwd=ROOT)
    data = json.loads(normalized)
    paths = {DIRECTORY + "/" + name for name in inputs["files"]}
    paths.update({
        DIRECTORY + "/inputs.json", DIRECTORY + "/publication.json",
        "scripts/massachusetts-native-counts.mjs", "scripts/massachusetts-native-counts.test.mjs",
        "scripts/build-massachusetts-native-inputs.py", "scripts/prepare-massachusetts-native-counts.mjs",
        "scripts/package-massachusetts-native-counts.py", "scripts/check-massachusetts-native-counts-browser.py",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js",
        "public/scripts/participation-explorer.js",
    })
    for family in ["participation-city-counts", "participation-precincts"]:
        paths.update({f"public/{family}/{VERSION}/{name}" for name in ["index.json", "MA.geojson.gz"]})
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, pin in inputs["files"].items():
        body = members[DIRECTORY + "/" + name]
        if len(body) != pin["bytes"] or digest(body) != pin["sha256"]:
            raise ValueError("Changed sufficient native original or numerical reader")
    counts = json.loads(members[DIRECTORY + "/" + inputs["queries"]["counts"]])
    reference = json.loads(members[DIRECTORY + "/" + inputs["queries"]["reporting_reference"]])
    extension = json.loads(gzip.decompress(members[DIRECTORY + "/" + inputs["queries"]["reference_extension"]]))
    full_pdfs = [body for name, body in members.items() if name.endswith(".pdf")]
    if len(full_pdfs) != 4 or sum(len(fitz.open(stream=body, filetype="pdf")) for body in full_pdfs) != 648:
        raise ValueError("Incomplete full native PDF corpus")
    tables = {
        "all307-native-reporting-unit-counts.csv": data["reporting_rows"],
        "all307-reporting-reference-decisions.csv": data["reporting_references"],
        "all351-native-municipality-decisions.csv": data["municipality_references"],
        "all275-Boston-native-summary-rows.csv": counts["boston_summary"],
        "all5775-native-Times-Cast-context-rows.csv": [
            row for rows in counts["boston_all_times_cast_frames"].values() for row in rows],
        "all40-Somerville-native-count-rows.csv": counts["somerville_native_counts"],
        "all16-Somerville-native-accounting-decisions.csv": counts["somerville_all_accounting"],
        "all99484-native-reference-pair-decisions.csv": [
            *reference["all_pair_decisions"], *extension["all_pair_decisions"]],
        "all4-held-split-parent-count-joins.csv": [
            row for row in data["reporting_references"] if not row["qualified"]],
    }
    for name, rows in tables.items():
        members[name] = csv_bytes(rows)
    members["queries.json"] = normalized
    members["reproduce.py"] = REPRODUCE.encode()
    members["reproduce.mjs"] = (
        "import {loadMassachusettsNativeCounts} from './scripts/massachusetts-native-counts.mjs';\n"
        "process.stdout.write(JSON.stringify(loadMassachusettsNativeCounts(),null,2)+'\\n');\n").encode()
    members["requirements.txt"] = (
        f"beautifulsoup4=={bs4.__version__}\nPyMuPDF=={fitz.VersionBind}\n"
        f"pyproj=={pyproj.__version__}\nshapely=={shapely.__version__}\n").encode()
    members["browser-acceptance.json"] = args.browser_proof.read_bytes()
    members["all51-navigation-acceptance.json"] = args.navigation_proof.read_bytes()
    members["local-publication-size-and-download-acceptance.json"] = args.publication_proof.read_bytes()
    members["README.txt"] = """MASSACHUSETTS: TWO NATIVE CITY SOURCES AND REPORTING-UNIT REFERENCES

COMPLETE CONTENTS
Four full native PDFs /648 pages, all67 sufficient permitted input pins, all
307 reporting rows, all44 native context frames /5775 Times Cast rows, all
275 separate Boston summary rows, all40 Somerville count rows, all351 original
municipal reference decisions, all99484 pair decisions, full original selected
geographic/projected geometry, native counts/IDs, safe declarations, exact code,
tests, CSV/JSON results and offline reproduction. This is not metadata-only.
Legacy filenames containing "private" are limited to explicitly curated public
aggregate declarations and a public datum-operation response; scripts, contacts,
keys, private app configs and personal/population/address features are excluded.

COUNT MEANING
Boston's native Times Cast across275 precincts sums to185569, corroborating six
complete statewide native contexts and their literal declaring-page Ballots Cast.
All44 context-specific sums match their own web fields; Q5-8=185348 and Q9=185452
are NOT homogenized. Separate summary Voters Cast556369/registered0/N_A remain
literal, never substituted, divided or repaired. Candidate votes are never summed.
Somerville's32 printed precinct/subprecinct rows and7 ward parents reconcile to
native city BALLOTS CAST - TOTAL64597 and REGISTERED VOTERS - TOTAL56008.
Ballots above registers and Official-page/UnOfficial-PDF labels remain literal.
No unique-person or analysis turnout rate is qualified. Central Tabulation is
a separately clocked partial product, included in full but never added to combined.
These are not statewide, county, demographic or population-turnout estimates.

REFERENCE MEANING
303 unchanged native reporting references: Boston275 and Somerville28.
Four Somerville parent count joins stay table-only because their parent polygons
contain separately reported A units. No remainder clipping or area allocation.
The source municipal frame has351 decisions/350 valid originals: Wayland's
invalid native/geographic ring is held without repair. All original geometry is
retained, including holds. Two native Boston overlaps are not clipped.
Boston's adopted2022 reference is explicitly for planning/visualization.
MassGIS subprecinct/parent/municipal references have separate native roles.
NativeEPSG3857 or26986 and per-product declared inverseESRI108190/EPSG1188
operations are checked at every vertex; strict1e-9degree tolerance is unchanged.
Default null-offset projection fails for the parent layer and is not substituted.
No newly certified2026 legal-boundary claim, source repair or inferred rate.

REPRODUCE
Python3.9+ with requirements.txt and Node22+; no source network access required.
Extract into an empty directory, then run:
  python reproduce.py --output reproduced
All8 original reader output files and normalized queries.json must match exactly.
  node --test scripts/massachusetts-native-counts.test.mjs
The full-website integration/browser tests require the website repository and
its separately preserved existing sources; they are not required to reproduce
this complete numerical analysis. Local browser/build proof is not native Pages
or production acceptance. The source/website ledger records those stages separately.
manifest.json hashes every other member. Earlier complete releases/routes remain.
""".encode()
    members["manifest.json"] = (json.dumps(dict(summary=data["summary"], files={
        name: dict(bytes=len(body), sha256=digest(body)) for name, body in sorted(members.items())
    }), indent=2)+"\n").encode()
    args.output.mkdir(parents=True)
    for name in ["queries.json", *tables, "requirements.txt", "README.txt", "manifest.json"]:
        (args.output / name).write_bytes(members[name])
    with zipfile.ZipFile(args.output / "complete-analysis.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)
    archive = (args.output / "complete-analysis.zip").read_bytes()
    receipt = dict(
        url=inputs["complete_download_url"], bytes=len(archive), sha256=digest(archive),
        members=len(members), sufficient_inputs=67, full_PDFs=4, full_pages=648,
        full_original_PDF_bytes=sum(map(len, full_pdfs)), native_reporting_rows=307,
        mapped_reporting_references=303, municipal_reference_decisions=351,
        invalid_municipal_geometry_holds=1, split_parent_holds=4, complete_pair_decisions=99484,
        source_counts_repaired=False, geometry_clipped=False, analysis_rates_approved=False)
    (version / "download.json").write_text(json.dumps(receipt, indent=2)+"\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser-proof", type=Path, required=True)
    parser.add_argument("--navigation-proof", type=Path, required=True)
    parser.add_argument("--publication-proof", type=Path, required=True)
    build(parser.parse_args())

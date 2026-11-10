"""Package all prior sufficient originals and the complete direct city-reference extension."""

import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

import shapefile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261110-massachusetts-city-precinct-reference-02"
PRIOR = "20261110-massachusetts-native-local-counts-01"
DIRECTORY = "data/county-source-reviews/" + VERSION
PRIOR_DIRECTORY = "data/county-source-reviews/" + PRIOR
spec = importlib.util.spec_from_file_location(
    "prior_ma_package", ROOT / "scripts/package-massachusetts-native-counts.py")
prior_package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior_package)
digest = prior_package.digest
csv_bytes = prior_package.csv_bytes
NORMALIZE = """import {loadMassachusettsCityReference} from './scripts/massachusetts-city-precinct-reference.mjs';
const value=loadMassachusettsCityReference();
process.stdout.write(JSON.stringify({...value,city_reference_geometries:[...value.city_reference_geometries.values()]},null,2)+'\\n');
"""
REPRODUCE = """import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
assert not args.output.exists(), 'Use a fresh reproduction directory'
args.output.mkdir(parents=True)
prior=root/'data/county-source-reviews/20261110-massachusetts-native-local-counts-01'
data=root/'data/county-source-reviews/20261110-massachusetts-city-precinct-reference-02'
tasks=[
 ('review-massachusetts-native-counts-01.py','native-count-review-01',['complete-native-count-queries.json','boston-summary-native.csv','boston-all-native-times-cast.csv','somerville-native-counts.csv']),
 ('review-massachusetts-native-geometry-01.py','native-geometry-review-01',['complete-native-reference-queries.json']),
 ('review-massachusetts-reference-extension-01.py','native-reference-extension-review-01',['complete-reference-extension-queries.json.gz','summary.json'])]
for name,directory,names in tasks:
 subprocess.run([sys.executable,str(prior/'code'/name),'--root',str(prior),'--output',str(args.output/directory)],check=True)
 for filename in names:
  assert (args.output/directory/filename).read_bytes()==(prior/directory/filename).read_bytes(), filename
subprocess.run([sys.executable,str(prior/'code/verify-massachusetts-native-counts-01.py'),'--root',str(prior),'--queries',str(args.output/'native-count-review-01/complete-native-count-queries.json'),'--proof',str(args.output/'native-count-review-01/independent-native-verification.json')],check=True)
assert (args.output/'native-count-review-01/independent-native-verification.json').read_bytes()==(prior/'native-count-review-01/independent-native-verification.json').read_bytes()
with (args.output/'prior-queries.json').open('wb') as output:
 subprocess.run(['node','--input-type=module','-e',"import {loadMassachusettsNativeCounts} from './scripts/massachusetts-native-counts.mjs';process.stdout.write(JSON.stringify(loadMassachusettsNativeCounts(),null,2)+'\\\\n');"],cwd=root,stdout=output,check=True)
assert (args.output/'prior-queries.json').read_bytes()==(root/'prior-analysis/queries.json').read_bytes()
new=args.output/'city-reference'
new.mkdir()
subprocess.run([sys.executable,str(data/'code/review-somerville-city-native-lead-01.py'),'--root',str(data),'--prior-root',str(prior),'--output',str(new/'native-only-review.json')],check=True)
subprocess.run([sys.executable,str(data/'code/project-somerville-city-native-lead-01.py'),'--root',str(data),'--prior-root',str(prior),'--geometry-server-receipt',str(data/'public-geometry-server.safe-receipt.json'),'--native-review',str(new/'native-only-review.json'),'--output',str(new)],check=True)
for name in ['native-only-review.json','geographic-review.json','verified32-city-display-reference.geojson']:
 assert (new/name).read_bytes()==(data/name).read_bytes(), name
with (args.output/'queries.json').open('wb') as output:
 subprocess.run(['node',str(root/'reproduce.mjs')],cwd=root,stdout=output,check=True)
assert (args.output/'queries.json').read_bytes()==(root/'queries.json').read_bytes()
spec=importlib.util.spec_from_file_location('current_ma_package',root/'scripts/package-massachusetts-city-reference.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
import json
for name,rows in module.query_tables(json.loads((args.output/'queries.json').read_bytes()),prior,data).items():
 body=module.csv_bytes(rows)
 assert body==(root/name).read_bytes(),name
 (args.output/name).write_bytes(body)
print('PASS: all11 native reader outputs, both normalized queries and every current CSV reproduce exactly')
"""


def query_tables(data, prior_root, city_root):
    counts = json.loads((prior_root / "native-count-review-01/complete-native-count-queries.json").read_bytes())
    reference = json.loads((prior_root / "native-geometry-review-01/complete-native-reference-queries.json").read_bytes())
    extension = json.loads(gzip.decompress(
        (prior_root / "native-reference-extension-review-01/complete-reference-extension-queries.json.gz").read_bytes()))
    native = json.loads((city_root / "native-only-review.json").read_bytes())
    geographic = json.loads((city_root / "geographic-review.json").read_bytes())
    new_pairs = [dict(source="somerville-city-precincts",
                      native_projected_area_units="US_survey_feet_squared_NOT_geodesic", **row)
                 for row in native["all_native_pair_decisions"]]
    all_pairs = [*reference["all_pair_decisions"], *extension["all_pair_decisions"], *new_pairs]
    assert len(all_pairs) == 99980
    return {
        "all307-native-reporting-unit-counts.csv": data["reporting_rows"],
        "all307-reporting-reference-decisions.csv": data["reporting_references"],
        "all351-native-municipality-decisions.csv": data["municipality_references"],
        "all275-Boston-native-summary-rows.csv": counts["boston_summary"],
        "all5775-native-Times-Cast-context-rows.csv": [
            row for rows in counts["boston_all_times_cast_frames"].values() for row in rows],
        "all40-Somerville-native-count-rows.csv": counts["somerville_native_counts"],
        "all16-Somerville-native-accounting-decisions.csv": counts["somerville_all_accounting"],
        "all99980-complete-native-pair-decisions.csv": all_pairs,
        "all32-direct-city-reference-decisions.csv": native["all_native_shape_decisions"],
        "all496-direct-city-native-pair-decisions.csv": new_pairs,
        "all32-independent-city-vertex-checks.csv": geographic["all_decisions"],
    }


def build(args):
    directory = ROOT / DIRECTORY
    inputs = json.loads((directory / "inputs.json").read_bytes())
    assert not args.output.exists() and not (directory / "download.json").exists()
    proofs = {name: json.loads(path.read_bytes()) for name, path in [
        ("browser", args.browser_proof), ("navigation", args.navigation_proof),
        ("publication", args.publication_proof), ("preserved_NH31", args.preserved_proof)]}
    assert all(value["status"].startswith("PASS") for value in proofs.values())
    assert len(proofs["browser"]["cases"]) == 2
    assert all(row["mapped_reporting_references"] == 307 and row["split_parent_holds"] == 0
               and row["former_four_holds_direct_clicks_verified"]
               for row in proofs["browser"]["cases"])
    prior_archive = args.prior_analysis.read_bytes()
    assert len(prior_archive) == 21432354
    assert digest(prior_archive) == "ab8248dffc6667b6f5e1f28f4b2d7937d6b2c3fcc528f51be328b5f56790e896"
    with zipfile.ZipFile(args.prior_analysis) as archive:
        assert archive.testzip() is None and len(archive.infolist()) == 100
        members = {member.filename: archive.read(member) for member in archive.infolist()}
    prior_manifest = json.loads(members["manifest.json"])
    for name, receipt in prior_manifest["files"].items():
        assert len(members[name]) == receipt["bytes"] and digest(members[name]) == receipt["sha256"]
    members["prior-analysis/queries.json"] = members["queries.json"]
    members["prior-analysis/manifest.json"] = members["manifest.json"]
    for name in ["all4-held-split-parent-count-joins.csv", "all99484-native-reference-pair-decisions.csv"]:
        members["prior-analysis/" + name] = members.pop(name)

    def put(name, body):
        if name in members and members[name] != body:
            members["prior-analysis/" + name] = members[name]
        members[name] = body

    paths = {DIRECTORY + "/" + name for name in inputs["files"]}
    paths.update({
        DIRECTORY + "/inputs.json", DIRECTORY + "/publication.json",
        "scripts/massachusetts-city-precinct-reference.mjs",
        "scripts/massachusetts-city-precinct-reference.test.mjs",
        "scripts/massachusetts-city-reference-integration.test.mjs",
        "scripts/build-massachusetts-city-reference-inputs.py",
        "scripts/prepare-massachusetts-city-precinct-reference.mjs",
        "scripts/package-massachusetts-city-reference.py",
        "scripts/check-massachusetts-native-counts-browser.py",
        "scripts/additional-participation.mjs",
        "public/scripts/participation-geography.js", "public/scripts/participation-explorer.js",
        f"public/participation-precincts/{VERSION}/index.json",
        f"public/participation-precincts/{VERSION}/MA.geojson.gz",
    })
    for name in sorted(paths):
        put(name, (ROOT / name).read_bytes())
    for name, receipt in inputs["files"].items():
        body = members[DIRECTORY + "/" + name]
        assert len(body) == receipt["bytes"] and digest(body) == receipt["sha256"]
    normalized = subprocess.check_output(["node", "--input-type=module", "-e", NORMALIZE], cwd=ROOT)
    data = json.loads(normalized)
    assert data["summary"]["mapped_reporting_references"] == 307 and data["summary"]["split_parent_holds"] == 0
    tables = query_tables(data, ROOT / PRIOR_DIRECTORY, directory)
    for name, rows in tables.items():
        put(name, csv_bytes(rows))
    put("queries.json", normalized)
    put("reproduce.mjs", NORMALIZE.encode())
    put("reproduce.py", REPRODUCE.encode())
    put("requirements.txt", members["requirements.txt"] + f"pyshp=={shapefile.__version__}\n".encode())
    for name, path in [
        ("browser-acceptance.json", args.browser_proof),
        ("all51-navigation-acceptance.json", args.navigation_proof),
        ("local-publication-size-and-download-acceptance.json", args.publication_proof),
        ("preserved-NH31-browser-acceptance.json", args.preserved_proof),
    ]:
        put(name, path.read_bytes())
    put("README.txt", """MASSACHUSETTS: 307 DIRECT NATIVE REPORTING REFERENCES

COMPLETE CONTENTS
All67 sufficient inputs from the prior complete analysis, including four FULL
PDFs/648 pages and original selected geometry/count/ID products, plus all17 new
sufficient inputs: the FULL8-member city precinct ZIP, safe declarations, exact
WKT transformation requests/responses, all32 native shape decisions/496 pairs,
all2697 geographic vertices, independent checks, portable readers and code.
All307 native reporting rows, all44 Boston contexts/5775 Times Cast rows,
all40 Somerville count rows, all351 municipal decisions and all99980 pair
decisions are supplied as full queries/results. No metadata-only replacement.
The raw city GIS ZIP includes public polling-place venue/address columns;
individual voter addresses or survey identifiers were not requested.

COUNT MEANING
All source counts/zeros/status conflicts are unchanged. Boston's selected native
Times Cast185569 remains separate from summary Voters Cast556369/registered0/N_A.
Somerville's printed ballots64597/register56008 and Official-page/UnOfficial-PDF
labels remain literal. No candidate sums, mode addition, source repair,
unique-person claim or analysis rate. Central Tabulation remains separate.
These are TWO city sources, not statewide/county or demographic turnout.

REFERENCE MEANING
Boston275 geometry is unchanged. Every one of Somerville's32 source units now
joins an actual city polygon, including the four former parent holds; no
remainder was clipped or allocated. Duplicate native IDs must not deduplicate
distinct Ward/Precinct labels. City metadata says September22,2023/2020 Census,
not a certified2026 or silently assumed2022 boundary vintage. Preserve the
exact original NAD83 MA Mainland US-survey-feet WKT, not rounded EPSG2249.
Declared inverseESRI108190 and all2697 vertices/cyclic edges pass independent
checking at the unchanged1e-9degree tolerance. Ring start/direction changes are
representation only; arbitrary vertex sorting would not prove edge preservation.
All32 native shapes are valid and all496 native pairs have zero overlap.
Boston's two original overlaps and invalid Wayland municipal hold are unchanged.
350 valid municipal shapes are reused, not duplicated or repaired.

REPRODUCE
Python3.9+ with requirements.txt and Node22+; no source network needed:
  python reproduce.py --output reproduced
All11 native reader outputs, prior/current normalized queries and all11 current
CSV exports must reproduce exactly. Source data are read-only; use fresh output.
  node --test scripts/massachusetts-native-counts.test.mjs scripts/massachusetts-city-precinct-reference.test.mjs
Both old/new numerical suites run without NPM dependencies. Full-website/browser
integration tests require the website repository and its other source families.
Local browser/build proof is NOT native Pages/live acceptance.

PROVENANCE
Prior sufficient data/readers/public references remain at their original paths.
prior-analysis/ preserves replaced historical code, queries, README, CSVs and
the original manifest, not an alternative current mapping claim. The immutable
prior full ZIP remains available at its original release. Current manifest.json
hashes every other member. Prior/current projected areas have explicit native
units and are NEVER summed across different coordinate systems.
""".encode())
    put("manifest.json", (json.dumps(dict(
        summary=data["summary"], prior_archive_sha256=digest(prior_archive),
        sufficient_inputs=84, full_PDFs=4, full_pages=648,
        files={name: dict(bytes=len(body), sha256=digest(body))
               for name, body in sorted(members.items()) if name != "manifest.json"},
    ), indent=2)+"\n").encode())
    args.output.mkdir(parents=True)
    for name in ["queries.json", *tables, "requirements.txt", "README.txt", "manifest.json"]:
        (args.output / name).write_bytes(members[name])
    with zipfile.ZipFile(args.output / "complete-analysis.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)
    archive = (args.output / "complete-analysis.zip").read_bytes()
    receipt = dict(
        url=inputs["complete_download_url"], bytes=len(archive), sha256=digest(archive),
        members=len(members), sufficient_inputs=84, prior_sufficient_inputs=67,
        additional_sufficient_inputs=17, full_PDFs=4, full_pages=648,
        native_reporting_rows=307, mapped_reporting_references=307, split_parent_holds=0,
        native_city_reference_shapes=32, native_city_reference_vertices=2697,
        complete_pair_decisions=99980, standalone_full_assets=16,
        old_source_counts_and_native_zeros_retained=True,
        original_geometry_clipped=False, source_counts_repaired=False, analysis_rates_approved=False)
    assert len(list(args.output.iterdir())) == receipt["standalone_full_assets"]
    (directory / "download.json").write_text(json.dumps(receipt, indent=2)+"\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior-analysis", type=Path, required=True)
    parser.add_argument("--browser-proof", type=Path, required=True)
    parser.add_argument("--navigation-proof", type=Path, required=True)
    parser.add_argument("--publication-proof", type=Path, required=True)
    parser.add_argument("--preserved-proof", type=Path, required=True)
    build(parser.parse_args())

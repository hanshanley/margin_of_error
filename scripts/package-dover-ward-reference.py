"""Package all sufficient originals and five generations of exact native ward queries."""

import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


core = module("dover", "dover-ward-reference.py")
old_package = module("previous_package", "package-new-hampshire-ward-reference.py")
REPRODUCE = """import importlib.util
from pathlib import Path
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('dover',root/'scripts/dover-ward-reference.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
print(core.encoded(core.load(root)).decode(),end='')
"""


def build(args):
    version = ROOT / core.VERSION
    if args.output.exists() or (version / "queries.json.gz").exists():
        raise ValueError("A complete source version cannot be overwritten")
    for path in [args.browser_proof, args.navigation_proof, args.preserved_proof, args.publication_proof]:
        if not json.loads(path.read_bytes())["status"].startswith("PASS"):
            raise ValueError("Actual local browser/build checks must pass before packaging")
    browser = json.loads(args.browser_proof.read_bytes())
    if len(browser["cases"]) != 2 or not all(row["all_six_Dover_click_roundtrips"] for row in browser["cases"]):
        raise ValueError("Both real desktop/mobile six-ward click checks are required")
    prior = args.prior_analysis.read_bytes()
    if len(prior) != 97907540 or core.digest(prior) != (
            "5802a9a7f17a67bd045b39447db30e44b359ab4ce2c8cc4ca782fe38524c3963"):
        raise ValueError("Changed complete prior scientific packet")
    with zipfile.ZipFile(args.prior_analysis) as archive:
        if archive.testzip() is not None or len(archive.infolist()) != 184:
            raise ValueError("Incomplete prior source corpus")
        members = {member.filename: archive.read(member) for member in archive.infolist()}
    for name, pin in json.loads(members["manifest.json"])["files"].items():
        if len(members[name]) != pin["bytes"] or core.digest(members[name]) != pin["sha256"]:
            raise ValueError("Changed sufficient prior source")
    members["prior-analysis/manifest.json"] = members["manifest.json"]
    for name in [
        "queries.json", "all31-native-ward-reference-decisions.csv", "all31-mapped-native-ward-counts.csv",
        "all6-Dover-table-only-native-ward-holds.csv",
    ]:
        members["prior-analysis/" + name] = members.pop(name)

    def put(name, body):
        if name in members and members[name] != body:
            members["prior-analysis/" + name] = members[name]
        members[name] = body

    data = core.load()
    raw = core.encoded(data)
    inputs = json.loads((version / "inputs.json").read_bytes())
    if gzip.compress(core.encoded(data["geojson"]), mtime=0) != (ROOT / core.PUBLIC / "NH.geojson.gz").read_bytes():
        raise ValueError("Prepared reference differs from complete queries")
    paths = set(inputs["files"]) | {
        core.VERSION+"/inputs.json", "scripts/dover-ward-reference.py",
        "scripts/test-dover-ward-reference.py", "scripts/dover-ward-reference.test.mjs",
        "scripts/build-dover-ward-reference-inputs.py", "scripts/prepare-dover-ward-reference.py",
        "scripts/package-dover-ward-reference.py", "scripts/check-new-hampshire-city-counts-browser.py",
        "scripts/manchester-ward-reference.test.mjs", "scripts/new-hampshire-ward-reference.test.mjs",
        "scripts/nashua-ward-reference.test.mjs", "public/scripts/participation-geography.js",
        "public/scripts/participation-explorer.js", "public/participation-precincts.json",
        core.PUBLIC+"/NH.geojson.gz", core.PUBLIC+"/index.json",
    }
    for name in sorted(paths):
        put(name, (ROOT / name).read_bytes())
    for name, pin in inputs["files"].items():
        if len(members[name]) != pin["bytes"] or core.digest(members[name]) != pin["sha256"]:
            raise ValueError("Changed sufficient original or earlier frozen query")
    tables = {
        "all242-retained-native-source-field-queries.csv": data["retained_city_source_queries"],
        "all37-native-ward-reference-dispositions.csv": data["complete_ward_disposition_queries"],
        "all37-native-ward-reference-decisions.csv": data["complete_reference_queries"],
        "all37-mapped-native-ward-counts.csv": [feature["properties"] for feature in data["geojson"]["features"]],
        "all36-Nashua-native-and-geographic-pair-decisions.csv": data["complete_nashua_pairwise_queries"],
        "all45-retained-Concord-pair-decisions.csv": data["complete_concord_pairwise_queries"],
        "all6-retained-Manchester-native-overlap-queries.csv": data["retained_manchester_overlap_queries"],
        "all15-Dover-native-pair-decisions.csv": data["complete_dover_pairwise_queries"],
        "all6-direct-Dover-reference-decisions.csv": data["complete_reference_queries"][31:],
    }
    for name, rows in tables.items():
        put(name, old_package.csv_bytes(rows))
    put("queries.json", raw)
    put("reproduce-v03.py", members["reproduce.py"])
    put("reproduce.py", REPRODUCE.encode())
    for name, path in [
        ("browser-acceptance.json", args.browser_proof), ("all51-navigation-acceptance.json", args.navigation_proof),
        ("preserved-MA307-browser-acceptance.json", args.preserved_proof),
        ("local-publication-size-and-download-acceptance.json", args.publication_proof),
    ]:
        put(name, path.read_bytes())
    put("README.txt", """NEW HAMPSHIRE: 37 DIRECT NATIVE WARD REFERENCES

COMPLETE CONTENTS
All17 FULL official PDFs/219 pages/117853795 native PDF bytes, all160 sufficient
pins, every earlier242 city-source field/37 ward count row/31 feature, all37
reference decisions, all15 Dover pairs,36 Nashua pairs,45 retained Concord pairs
and six Manchester overlap decisions. Complete original selected geometry/count/
ID products, source declarations, exact code/tests/full CSV/JSON queries/results
and FIVE generations of offline reproduction. No metadata-only replacement.
Private app code/keys/session headers and personal/population/address/parcel
feature data are excluded. Prior complete releases and public routes remain.

SOURCE MEANING
Dover's six literal Total Ballots Cast fields2577/2533/3207/2872/2298/2454 sum
to printed city15941. Native registers, affiliation stocks and printed fractions
stay separate, not ballot choice/group-turnout numerators or analysis rates.
Manchester Ward7's85-ballot disagreement and federal-only76 remain; Nashua's
Ward3/4/8 disagreements+1/-2/-1 and federal-only92 remain, never added or repaired.
All37 raw ward rows and242 source fields are unchanged. Four source cities,
not whole-state/county totals, unique people, eligibility or demographic turnout.

REFERENCE MEANING
All31 earlier feature properties/geometry stay unchanged. Dover's six original
state-published2022 NHGRANIT polygons use actual layer11/NHPolitDists_VW_2022,
not old layer5, city named-map keys, polling points, blocks or parcels.
Literal district labels, not FID-as-ward or nativeFIPS17010-as-county, control
joins. Native3437 and publisher-portal-declared inverseESRI108190 verify all1987
vertices/cyclic edges at strict1e-9degree tolerance; wrong null-offset rejects.
All six native/geographic polygons valid; all15 native pairs have zero overlap.
Six Manchester/fourteen Concord overlaps remain unrepaired. Native projected
area units remain explicit; metre/US-survey-feet/geographic areas are not pooled.
This is municipal display reference, not newly certified2026 legal precincts.
No repairs, remainder clipping, area/population allocation or inferred rates.

REPRODUCE
Python3.9+ with pinned requirements and Node22+; no source network needed.
  node reproduce-base.mjs > reproduced-base.json
  python reproduce-manchester.py > reproduced-manchester.json
  python reproduce-v02.py > reproduced-v02.json
  python reproduce-v03.py > reproduced-v03.json
  python reproduce.py > reproduced-queries.json
Compare each preserved generation with its frozen query; current output must
match queries.json byte-for-byte. Run the four Python test-*-ward-reference.py
suites and the included dedicated NH Node tests. Full-website/browser checks
require the website repository and its other source families.
Local proof is not native Pages/live acceptance; website records are separate.
prior-analysis/ retains replaced historical code/queries/CSV/readme/manifest.
Current manifest.json hashes every other member.
""".encode())
    put("manifest.json", (json.dumps(dict(summary=data["summary"], files={
        name: dict(bytes=len(body), sha256=core.digest(body))
        for name, body in sorted(members.items()) if name != "manifest.json"}), indent=2)+"\n").encode())
    args.output.mkdir(parents=True)
    for name in ["queries.json", *tables, "requirements.txt", "README.txt", "manifest.json"]:
        (args.output / name).write_bytes(members[name])
    with zipfile.ZipFile(args.output / "complete-analysis.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)
    body = (args.output / "complete-analysis.zip").read_bytes()
    receipt = dict(url=inputs["complete_download_url"], bytes=len(body), sha256=core.digest(body),
        members=len(members), sufficient_inputs=160, original_pdfs=17, original_pages=219,
        original_pdf_bytes=117853795, mapped_cities=dict(Manchester=12, Concord=10, Nashua=9, Dover=6),
        retained_city_source_fields=242, retained_native_ward_rows=37, complete_reference_decisions=37,
        complete_dover_pair_decisions=15, table_only_ward_holds=0, standalone_full_assets=14,
        source_repairs=False, geometry_repairs=False, native_federal_only_added=False, analysis_rates_approved=False)
    (version / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (version / "summary.json").write_text(json.dumps(data["summary"], indent=2)+"\n")
    (version / "download.json").write_text(json.dumps(receipt, indent=2)+"\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior-analysis", type=Path, required=True)
    parser.add_argument("--browser-proof", type=Path, required=True)
    parser.add_argument("--navigation-proof", type=Path, required=True)
    parser.add_argument("--preserved-proof", type=Path, required=True)
    parser.add_argument("--publication-proof", type=Path, required=True)
    build(parser.parse_args())

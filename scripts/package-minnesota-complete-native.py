"""Package every new count, entire prior original package and unchanged reference proof."""

import argparse
import csv
import gzip
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mn_complete", ROOT / "scripts/minnesota-complete-native.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def csv_bytes(rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(dict.fromkeys(key for row in rows for key in row)),
                            lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: "" if value is None else json.dumps(value, ensure_ascii=True)
            if isinstance(value, (dict, list, bool)) else value for key, value in row.items()})
    return buffer.getvalue().encode()


def build(args):
    source = ROOT / core.VERSION
    if args.output.exists() or (source / "download.json").exists():
        raise ValueError("Never replace an existing complete native analysis")
    proofs = {name: json.loads(path.read_bytes()) for name, path in [
        ("local-MN87-4105-browser-acceptance.json", args.browser),
        ("local-all204-mode-acceptance.json", args.modes),
        ("local-all51-navigation-acceptance.json", args.navigation),
        ("local-preserved-NV17-acceptance.json", args.preserved),
        ("local-exact-pages-size-and-download-acceptance.json", args.size)]}
    if not all(proof["status"].startswith("PASS") for proof in proofs.values()):
        raise ValueError("Actual local checks must pass before packaging")
    data = core.load()
    geometry = data.pop("full_unchanged_coordinate_feature_collection")
    references = dict(all4105_native_reference_decisions=data.pop("all4105_native_reference_decisions"),
        all_bbox_candidate_pair_decisions=data.pop("all_bbox_candidate_pair_decisions"))
    data["precinct_reference"] = json.loads((source / "reference-summary.json").read_bytes())
    raw = core.encoded(data)
    if (gzip.decompress((source / "queries.json.gz").read_bytes()) != raw
            or gzip.decompress((source / "MN.geojson.gz").read_bytes()) != core.encoded(geometry)
            or gzip.decompress((source / "precinct-reference-queries.json.gz").read_bytes()) != core.encoded(references)):
        raise ValueError("Prepared queries/reference properties differ from exact native reconstruction")
    inputs = json.loads((source / "inputs.json").read_bytes())
    paths = {core.VERSION + "/" + name for name in inputs["files"]} | {
        core.VERSION + "/" + name for name in ("inputs.json", "queries.json.gz", "summary.json",
            "reference-summary.json", "MN.geojson.gz", "precinct-reference-queries.json.gz")}
    paths.update([
        "scripts/minnesota-complete-native.py", "scripts/test-minnesota-complete-native.py",
        "scripts/minnesota-complete-native.mjs", "scripts/minnesota-complete-native.test.mjs",
        "scripts/build-minnesota-complete-inputs.py", "scripts/prepare-minnesota-complete-native.py",
        "scripts/package-minnesota-complete-native.py", "scripts/check-minnesota-followup-browser.py",
        "scripts/check-native-mode-frames-browser.py", "scripts/check-participation-2026-drilldowns-browser.py",
        "scripts/additional-participation.mjs", "scripts/local_reference_staging.py",
        "scripts/test-local-reference-staging.py",
        "scripts/manchester-ward-reference.test.mjs", "scripts/nashua-ward-reference.test.mjs",
        "scripts/new-hampshire-ward-reference.test.mjs", "scripts/minnesota-precinct-followup.test.mjs",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js",
        "public/scripts/participation-explorer.js", "public/participation-precincts.json",
        "public/participation-precincts/20261110-minnesota-complete-native-03/index.json",
        "src/pages/participation-local/[state].json.gz.ts", "src/pages/voter-participation.astro",
    ])
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, expected in inputs["files"].items():
        if core.pin(members[core.VERSION + "/" + name]) != expected:
            raise ValueError("Changed sufficient original: " + name)
    tables = {"all87-county-decisions.csv": data["complete_county_decisions"],
        "all4105-precinct-statistics.csv": data["all4105_native_precinct_decisions"],
        "all87-previous-current-comparisons.csv": data["complete87_previous_current_comparisons"],
        "all4105-unchanged-reference-decisions.csv": references["all4105_native_reference_decisions"],
        "all13619-retained-pair-decisions.csv": references["all_bbox_candidate_pair_decisions"]}
    members.update({name: csv_bytes(rows) for name, rows in tables.items()})
    members["queries.json"] = raw
    members["reference-queries.json"] = core.encoded(references)
    members["full-current-native-pctstats.txt"] = (source / "originals/pctstats.txt").read_bytes()
    members["MN.geojson.gz"] = (source / "MN.geojson.gz").read_bytes()
    members.update({name: core.encoded(proof) for name, proof in proofs.items()})
    members["package.json"] = b'{"private":true,"type":"module"}\n'
    members["requirements.txt"] = b"# Complete numerical/reference reproduction: Python3.9+ standard library; Node22+ built-ins.\n# Full website/browser integration uses existing project dependencies.\n"
    members["reproduce.py"] = b"""import importlib.util,json
from pathlib import Path
import sys
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mn_complete',root/'scripts/minnesota-complete-native.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
data=core.load(root)
data.pop('full_unchanged_coordinate_feature_collection')
data.pop('all4105_native_reference_decisions')
data.pop('all_bbox_candidate_pair_decisions')
data['precinct_reference']=json.loads((root/core.VERSION/'reference-summary.json').read_bytes())
sys.stdout.buffer.write(core.encoded(data))
"""
    members["README.txt"] = b"""MINNESOTA:87 COMPLETE COUNTY SOURCES / ALL4105 NATIVE STATISTICS ROWS

COMPLETE CONTENTS
All8 sufficient frozen inputs include the ENTIRE50,849,478-byte/80-member
previous immutable scientific ZIP, not a pointer or reduced metadata.
It preserves every sufficient older native original, all3 full geometry
pages, all4105 native identities, every original coordinate, all13619
previous pair decisions, earlier count queries/code/tests. The NEW full
native precinct-statistics TXT, safe one-request receipts, complete page
factual projection, all4105 old/new literal-field comparisons and full
independently prepared qualification queries are included directly.
All87 current county decisions,4105 unit decisions,87 county comparisons,
4105 unchanged-reference decisions and13619 retained pair rows, complete
maintained code/tests and exact offline reproduction are included.
Raw page HTML remains privately retained; publisher application code and
acquisition headers are excluded. This is not a metadata-only download.

SOURCE MEANING
The native results-page clock is11/10/26 8:08AM; timezone is unknown.
ALL4105 statistics flags explicitly report, including32 actual zeroes.
Fillmore,Hubbard,Wright and26 previously unknown rows now have counts.
The complete derived TotalNumberVoted sum2,852,618 equals the separately
labelled page EstimatedVoters value, but that estimate NEVER fills native
counts or becomes a certified/deduplicated state parent.
7AM registrations3,927,697 and ElectionDay registrations147,357 remain
separate native fields, not VEP or the November2 registration stock.
Existing rules qualify73 county registration fractions;14 remain withheld.
All60 component conflicts and6 precinct electorate excesses survive;
no counts are repaired. ALL precinct analysis rates remain NULL.
No demographic, first-ever, eligibility/death/migration or nonvoter
allocation is inferred. Provider early/returned frames remain separate.

UNCHANGED GEOGRAPHY / BROWSER DELIVERY
Every one of4105 geometry coordinate hashes equals the previously
verified full September18,2026 native reference. Prior13619 pair reviews
are reused, not a repeated geometry acquisition/intersection campaign.
Changed native count/provenance properties are NOT geometry repairs.
The16 invalid old generalizations stay unused; no clipping or aliases.
Source/reference name differences and literal county/VTD namespaces remain.
These are display references, not newly certified legal precincts.
The9.2MB exact reference is published as a full external asset; runtime
uses the same bytes via the existing tag-pinned raw-GitHub CORS-safe
pattern, not a release-download fetch or extra Pages-payload copy.
All old source readers, archives, references and full routes survive.

REPRODUCE IN AN EMPTY DIRECTORY, NO NETWORK NEEDED
Extract every outer ZIP member. The included Python reader opens the
entire prior original ZIP directly with standard-library zipfile; no
manual nested extraction, package installation or source download needed.
  python reproduce.py > reproduced-queries.json
The output must equal queries.json byte-for-byte.
  python scripts/test-minnesota-complete-native.py
  node --test --test-name-pattern="complete native frame|new county and precinct guards" scripts/minnesota-complete-native.test.mjs
The first two Node tests require built-ins only. Full website/browser
tests require the existing project/source families and browser tooling.
manifest.json pins every other member, including the complete old ZIP.
Included local browser/size proofs are NOT actual native Pages or live
production acceptance.
"""
    members["manifest.json"] = core.encoded(dict(summary=data["summary"], sufficient_inputs=8,
        entire_prior_original_archive_members=80,
        files={name: core.pin(body) for name, body in sorted(members.items())}))
    assets = ["queries.json", "reference-queries.json", *tables, "full-current-native-pctstats.txt",
              "MN.geojson.gz", "requirements.txt", "README.txt", "manifest.json"]
    args.output.mkdir(parents=True)
    for name in assets:
        (args.output / name).write_bytes(members[name])
    with zipfile.ZipFile(args.output / "complete-analysis.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body)
    receipt = dict(url=core.DOWNLOAD, **core.pin((args.output / "complete-analysis.zip").read_bytes()),
        members=len(members), sufficient_inputs=8, entire_prior_original_archive_members=80,
        standalone_full_assets=len(assets)+1, complete_counties=87, reported_source_rows=4105,
        unknown_source_rows=0, newly_reported_rows=26, reported_zero_rows=32,
        source_registration_fractions=73, precinct_analysis_rates=0,
        reference_coordinates_changed=False, prior_pair_decisions_reused=13619)
    (source / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(dict(status="PASS_complete_native_packet_NOT_live_acceptance", **receipt)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "browser", "modes", "navigation", "preserved", "size"):
        parser.add_argument("--"+name, type=Path, required=True)
    build(parser.parse_args())

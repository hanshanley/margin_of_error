"""Package all permitted sufficient native originals, queries and offline code."""

import argparse
import csv
import gzip
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mn_followup", ROOT / "scripts/minnesota-followup.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
geometry_spec = importlib.util.spec_from_file_location("mn_reference", ROOT / "scripts/minnesota-precinct-followup.py")
geometry_core = importlib.util.module_from_spec(geometry_spec)
geometry_spec.loader.exec_module(geometry_core)


def csv_bytes(rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: "" if value is None else json.dumps(value, ensure_ascii=True)
            if isinstance(value, (dict, list, bool)) else value for key, value in row.items()})
    return target.getvalue().encode()


def build(args):
    source = ROOT / core.VERSION
    if args.output.exists() or (source / "download.json").exists():
        raise ValueError("Never replace an immutable complete source package")
    proofs = {name: json.loads(path.read_bytes()) for name, path in [
        ("local-browser-acceptance.json", args.browser),
        ("all51-navigation-acceptance.json", args.navigation),
        ("preserved-NH37-browser-acceptance.json", args.preserved),
        ("local-pages-size-and-download-acceptance.json", args.size)]}
    if not all(proof["status"].startswith("PASS") for proof in proofs.values()):
        raise ValueError("Actual local checks must pass before packaging")
    data = core.load()
    raw = core.encoded(data)
    if gzip.decompress((source / "queries.json.gz").read_bytes()) != raw:
        raise ValueError("New numerical queries differ from the prepared cache")
    inputs = json.loads((source / "inputs.json").read_bytes())
    geometry_inputs = json.loads((source / "geometry-inputs.json").read_bytes())
    reference = geometry_core.qualify()
    reference_raw = core.encoded(reference)
    if gzip.decompress((source / "precinct-reference-queries.json.gz").read_bytes()) != reference_raw:
        raise ValueError("Full native reference queries differ from the prepared source")
    paths = {core.VERSION + "/" + name for name in inputs["files"]} | {
        core.VERSION + "/inputs.json", core.VERSION + "/queries.json.gz", core.VERSION + "/summary.json",
        "scripts/minnesota-followup.py", "scripts/test-minnesota-followup.py",
        "scripts/minnesota-county-followup.mjs", "scripts/minnesota-county-followup.test.mjs",
        "scripts/minnesota-followup-integration.test.mjs", "scripts/build-minnesota-followup-inputs.py",
        "scripts/prepare-minnesota-followup.py", "scripts/package-minnesota-followup.py",
        "scripts/check-minnesota-followup-browser.py",
        "scripts/minnesota-precinct-followup.py", "scripts/minnesota-precinct-followup.test.mjs",
        "scripts/local_reference_staging.py",
        "scripts/additional-participation.mjs", "public/scripts/participation-explorer.js",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js",
        geometry_core.PUBLIC + "/index.json", "public/participation-precincts.json",
        core.VERSION + "/geometry-inputs.json", core.VERSION + "/MN.geojson.gz",
        core.VERSION + "/precinct-reference-queries.json.gz",
    }
    paths.update(core.VERSION + "/" + name for name in geometry_inputs["files"])
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, pin in {**inputs["files"], **geometry_inputs["files"]}.items():
        body = members[core.VERSION + "/" + name]
        if len(body) != pin["bytes"] or core.digest(body) != pin["sha256"]:
            raise ValueError("Changed sufficient original or earlier complete numerical query")
    units = data["all4105_native_precinct_decisions"]
    tables = {
        "all87-native-county-decisions.csv": data["complete_county_decisions"],
        "all4105-native-precinct-statistics-decisions.csv": units,
        "all87-previous-current-native-comparisons.csv": data["complete87_previous_current_comparisons"],
        "all26-unreported-native-unit-decisions.csv": [row for row in units if not row["reported_statistics"]],
        "all60-native-component-conflict-decisions.csv": [row for row in units
            if row["native_component_residual"] not in (None, 0)],
        "all7-native-electorate-excess-decisions.csv": [row for row in units
            if row["native_electorate_excess"] is not None and row["native_electorate_excess"] > 0],
        "all9-newly-complete-native-county-decisions.csv": [
            row for row in data["complete87_previous_current_comparisons"] if row["newly_complete"]],
        "all4105-full-native-reference-decisions.csv": reference["all4105_reference_decisions"],
        "all13619-native-bbox-pair-decisions.csv": reference["all_bbox_candidate_pair_decisions"],
    }
    if list(map(len, tables.values())) != [87, 4105, 87, 26, 60, 7, 9, 4105, 13619]:
        raise ValueError("Changed full query/exception scope")
    for name, rows in tables.items():
        members[name] = csv_bytes(rows)
    for name, proof in proofs.items():
        members[name] = (json.dumps(proof, indent=2) + "\n").encode()
    members["queries.json"] = raw
    members["precinct-reference-queries.json"] = reference_raw
    members["MN.geojson.gz"] = (source / "MN.geojson.gz").read_bytes()
    members["index.json"] = (ROOT / geometry_core.PUBLIC / "index.json").read_bytes()
    members["requirements.txt"] = b"shapely==2.0.7\n# Node22+ for native reader/guard tests.\n"
    members["reproduce.py"] = b"""import importlib.util
from pathlib import Path
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mn_followup',root/'scripts/minnesota-followup.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
print(core.encoded(core.load(root)).decode(),end='')
"""
    members["reproduce-precincts.py"] = b"""import importlib.util
from pathlib import Path
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mn_reference',root/'scripts/minnesota-precinct-followup.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
print(core.core.encoded(core.qualify(root)).decode(),end='')
"""
    members["README.txt"] = """MINNESOTA: NATIVE TOTAL NUMBER VOTED,84 COMPLETE COUNTIES

COMPLETE CONTENTS
All34 sufficient pins, FULL current+previous native precinct-statistics
originals, full native layout/counties/precincts, all87 county decisions,
all4105 unit decisions, all87 previous/current comparisons, all26 unknown
units/60 component conflicts/seven electorate excesses/nine newly complete
counties. Every earlier retained query/component table/source qualification,
separate Estimated Voters observation, full87-county Census reference,
checksums/code/tests/numerical results and exact offline reproduction. All
three FULL native reference pages,4105 direct full-native reference decisions
and13619 native bbox-pair decisions; remaining8409841 pairs are bbox-disjoint
within all8423460 pairs. All full native shapes are valid with zero positive
overlaps. Sixteen invalid legacy generalizations are retained but not reused,
clipped or repaired. All full native coordinates stay unchanged.
No metadata-only replacement; earlier complete releases remain available.
Acquisition headers, raw page scripts, voter files and identifiers are excluded.
Native public precinct IDs/names are reporting units, not individual voters.

SOURCE MEANING
Unofficial native Total Number Voted, not candidate votes, independently
deduplicated people, certified cast ballots or demographic participation.
4079 of4105 source rows report;84 counties have complete statistics and
Fillmore/Hubbard/Wright remain partial with26 unreported rows. Their subtotals
are not complete county totals; original zero fields in unreported rows are
not observed zeros.2,827,091 is a reported-row subtotal, never an exact state
total or the separate page Estimated Voters2,852,528. Component conflicts and
excesses are unmodified.7AM+Election Day registration is its own source frame,
not November2 Registered-only3,927,036, preregistrations, VEP, CVAP or CPS.
71 county registration fractions pass complete-data/component/electorate
checks; all others are null. No normalized voting-mode/unique-person/first-ever/
eligibility/death/migration or nonparticipation-residual claim is made.
The results page prints11/07/26 5:18 PM; timezone remains unknown. The native
download receipt is separate, not an independently printed file-update clock.

GEOGRAPHY AND WEBSITE
Explicit native county names join the unmodified2026 Census county context
with only case and the County suffix normalized. Both names remain; native
county IDs are NOTFIPS(Becker03 is27005, not27003). Not certified2026 election
precincts. The separate September18,2026 native display-reference joins map
all4105 units:4079 native count reports and26 unknowns. Rates remain null.
Native countycode/pctcode and separate VTD/FIPS fields control identity;
all1723 names differing beyond case remain separate, not guessed aliases.
Current website opt-in selects this WHOLE snapshot over old75county records,
with matching unit tables. Frozen legacy readers/context-review hashes stay
unchanged. Provider early/returned frames are separate, never native-mode
allocations from roster or absentee components.
Packaged local proofs are not native Pages or live production acceptance.

REPRODUCE
Extract every member in an empty directory; no network/source acquisition.
  python reproduce.py > reproduced-queries.json
Output must equal queries.json byte-for-byte; this count reader is stdlib-only.
With pinned requirements for full geometry reproduction:
  python reproduce-precincts.py > reproduced-precinct-reference-queries.json
Output must equal precinct-reference-queries.json byte-for-byte.
  python scripts/test-minnesota-followup.py
  node --test scripts/minnesota-county-followup.test.mjs
  node --test scripts/minnesota-precinct-followup.test.mjs
The included integration/browser tests require the FULL website/other source
families and existing browser tooling. Node's cached-query reader validates
all sufficient pins and the exact prepared cache; Python recomputes from the
full native originals. manifest.json hashes every other member.
""".encode()
    members["manifest.json"] = (json.dumps(dict(summary=data["summary"],
        reference_summary=reference["summary"], files={
        name: dict(bytes=len(body), sha256=core.digest(body)) for name, body in sorted(members.items())}),
        indent=2) + "\n").encode()
    args.output.mkdir(parents=True)
    for name in ["queries.json", "precinct-reference-queries.json", "MN.geojson.gz", "index.json",
                 *tables, "requirements.txt", "README.txt", "manifest.json"]:
        (args.output / name).write_bytes(members[name])
    with zipfile.ZipFile(args.output / "complete-analysis.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)
    body = (args.output / "complete-analysis.zip").read_bytes()
    receipt = dict(url=inputs["complete_download_url"], bytes=len(body), sha256=core.digest(body),
        members=len(members), sufficient_inputs=34, standalone_full_assets=17,
        complete_county_decisions=87, complete_county_counts=84, partial_counties=3,
        complete_native_unit_decisions=4105, unreported_native_units=26,
        previous_current_decisions=87, qualified_registration_fractions=71,
        exact_statewide_count=None, direct_full_native_reference_joins=4105,
        reported_native_reference_counts=4079, unknown_native_reference_counts=26,
        native_pair_decisions=13619, positive_native_overlap_pairs=0,
        invalid_legacy_generalizations_not_reused=16, precinct_analysis_rates_approved=False,
        source_counts_repaired=False, candidate_votes_used_as_ballots=False)
    (source / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    parser.add_argument("--navigation", type=Path, required=True)
    parser.add_argument("--preserved", type=Path, required=True)
    parser.add_argument("--size", type=Path, required=True)
    build(parser.parse_args())

"""Publish complete sufficient originals, every county/mode/pair query and offline code."""

import argparse
import csv
import gzip
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nevada", ROOT / "scripts/nevada-native-counties.py")
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
        raise ValueError("Never replace an existing complete analysis")
    proofs = {name: json.loads(path.read_bytes()) for name, path in [
        ("local-NV17-browser-acceptance.json", args.browser),
        ("local-all51-navigation-acceptance.json", args.navigation),
        ("local-preserved-AL67-acceptance.json", args.preserved),
        ("local-pages-size-and-download-acceptance.json", args.size)]}
    if not all(proof["status"].startswith("PASS") for proof in proofs.values()):
        raise ValueError("Actual local checks must pass before packaging")
    data = core.load()
    raw = core.encoded(data)
    if gzip.decompress((source / "queries.json.gz").read_bytes()) != raw:
        raise ValueError("Complete reconstruction differs from prepared query")
    inputs = json.loads((source / "inputs.json").read_bytes())
    paths = {core.VERSION + "/" + name for name in inputs["files"]} | {
        core.VERSION + "/" + name for name in ("inputs.json", "queries.json.gz", "summary.json")}
    paths.update([
        "scripts/nevada-native-counties.py", "scripts/test-nevada-native-counties.py",
        "scripts/nevada-native-counties.mjs", "scripts/nevada-native-counties.test.mjs",
        "scripts/acquire-nevada-county-followup.py", "scripts/build-nevada-county-inputs.py",
        "scripts/prepare-nevada-native-counties.py", "scripts/package-nevada-native-counties.py",
        "scripts/check-nevada-native-counties-browser.py", "scripts/check-native-mode-frames-browser.py",
        "scripts/check-participation-2026-drilldowns-browser.py",
        "scripts/additional-participation.mjs", "scripts/additional-participation.test.mjs",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js",
    ])
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, expected in inputs["files"].items():
        if core.pin(members[core.VERSION + "/" + name]) != expected:
            raise ValueError("Changed sufficient original: " + name)
    tables = {"all17-county-decisions.csv": data["county_decisions"],
              "all19-native-counting-groups.csv": data["native_counting_groups"],
              "all136-county-reference-pairs.csv": data["all136_county_pairs"]}
    members.update({name: csv_bytes(rows) for name, rows in tables.items()})
    members["queries.json"] = raw
    members["all147-Clark-native-numerical-tables.json"] = (source / "originals/clark-complete-numerical-facts.json").read_bytes()
    members["full-Churchill-native-report.pdf"] = (source / "originals/churchill-original.pdf").read_bytes()
    members["full-White-Pine-native-report.pdf"] = (source / "originals/white-pine-original.pdf").read_bytes()
    members["NV-full-county-reference.geojson.gz"] = (source / "NV-full-county-reference.geojson.gz").read_bytes()
    members.update({name: core.encoded(proof) for name, proof in proofs.items()})
    members["package.json"] = b'{"private":true,"type":"module"}\n'
    members["requirements.txt"] = b"# Numerical reproduction: Python3.9+ standard library and Node22+ built-ins.\n# Independent original PDF and geometry review:\nPyMuPDF\npypdf\nshapely==2.0.7\n"
    members["reproduce.py"] = b"""import importlib.util
from pathlib import Path
import sys
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('nevada',root/'scripts/nevada-native-counties.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
sys.stdout.buffer.write(core.encoded(core.load(root)))
"""
    members["README.txt"] = b"""NEVADA: FOUR NATIVE COUNTY SNAPSHOTS, THIRTEEN UNKNOWN COUNTS

COMPLETE CONTENTS
All18 sufficient inputs: both entire new county PDFs (23 pages), complete
147 Clark native numerical tables and factual text, safe source receipts,
all inherited Washoe sufficient inputs including full23-page numerical
text, original reader, county/mode/candidate queries, and all17 unchanged
2026 Census county references with all136 pair decisions. Every new
county/mode/pair query and maintained reader/test/reproduction is included.
The raw Clark HTML remains privately retained with its exact467019-byte
source hash; publisher application code and acquisition headers are NOT
redistributed. The public Clark projection contains ALL numerical
tables/fields, not metadata alone. Earlier full releases stay available.

SOURCE MEANING
Clark745317 native Total Turnout, Churchill9685 and WhitePine3077 native
Voters Cast are distinct unofficial county snapshots. Held Washoe191830
and its earlier source clock are unchanged, NOT reacquired. All source
registers and native percentages remain literal; definitions and analysis
rates are NOT qualified. Timezones stay unknown. Different clocks are
never added into a statewide result. The13 other county counts and
registrations stay NULL, not zero or candidate counts. Counting groups
are not precincts. No state survey, demographic estimate or native state
ballot count is allocated locally. No new precinct map/rate is inferred.
Churchill House4 TimesCast1/register0/N/A remains literal, separate from
the county parent9685/register17211, without repair or extrapolation.

IDENTITY AND MODES
Four direct literal county identities join the complete unchanged17-county
2026 Census reference, not certified2026 election precinct boundaries.
All shapes are valid without repair; all136 overlap areas are0 in
coordinate degrees squared, not metres or geodesic areas.
The live-only source frame uses Available/official. Existing Nevada
provider early/returned frames remain separately qualified and unchanged;
all-method native counts never substitute for those provider frames.
Frozen legacy readers and the original Washoe key remain unchanged.

REPRODUCE IN AN EMPTY DIRECTORY, WITHOUT NETWORK ACCESS
Extract every ZIP member, then:
  python reproduce.py > reproduced-queries.json
The output must equal queries.json byte-for-byte.
  python scripts/test-nevada-native-counties.py
  node --test --test-name-pattern="four native|Nevada frame rejects" scripts/nevada-native-counties.test.mjs
The first two Node tests require built-ins only. Full website integration
and browser tests need the existing website and source families; do not
claim the numerical archive alone reproduces their full environment.
manifest.json pins every other member. Included local browser/size
proofs are NOT actual native Pages or live website acceptance.
The state SilverState and VIVID routes explicitly challenge/prohibit
automation and remain stopped, without another client/cache/mirror/key.
"""
    members["manifest.json"] = core.encoded(dict(summary=data["summary"], sufficient_inputs=18,
        files={name: core.pin(body) for name, body in sorted(members.items())}))
    assets = ["queries.json", *tables, "all147-Clark-native-numerical-tables.json",
        "full-Churchill-native-report.pdf", "full-White-Pine-native-report.pdf",
        "NV-full-county-reference.geojson.gz", "requirements.txt", "README.txt", "manifest.json"]
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
        members=len(members), sufficient_inputs=18, standalone_full_assets=len(assets) + 1,
        reference_counties=17, observed_counties=4, unknown_counties=13,
        newly_acquired_counties=3, native_counting_groups=19, complete_reference_pairs=136,
        new_precinct_coverage_approved=False, state_total_inferred=False, analysis_rates_approved=False,
        source_counts_repaired=False, candidate_votes_used_as_ballots=False)
    (source / "download.json").write_bytes(core.encoded(receipt))
    print(json.dumps(dict(status="PASS_complete_native_analysis_NOT_native_production_acceptance", **receipt)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "browser", "navigation", "preserved", "size"):
        parser.add_argument("--" + name, type=Path, required=True)
    build(parser.parse_args())

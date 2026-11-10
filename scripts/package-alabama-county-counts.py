"""Package every sufficient native input, county/pair query and offline reproduction."""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("alabama_counties", ROOT / "scripts/alabama-county-counts.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def csv_bytes(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(dict.fromkeys(key for row in rows for key in row)),
                            lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: "" if value is None else json.dumps(value, ensure_ascii=True)
            if isinstance(value, (dict, list, bool)) else value for key, value in row.items()})
    return output.getvalue().encode()


def build(args):
    source = ROOT / core.VERSION
    if args.output.exists() or (source / "download.json").exists():
        raise ValueError("Never replace an existing complete scientific package")
    proofs = {name: json.loads(path.read_bytes()) for name, path in [
        ("local-AL67-browser-acceptance.json", args.browser),
        ("local-all51-navigation-acceptance.json", args.navigation),
        ("local-preserved-MN84-acceptance.json", args.preserved),
        ("local-pages-size-and-download-acceptance.json", args.size)]}
    if not all(proof["status"].startswith("PASS") for proof in proofs.values()):
        raise ValueError("Actual local checks must pass before packaging")
    if proofs["local-preserved-MN84-acceptance.json"]["unpublished_reference_locally_staged"]:
        raise ValueError("The already-published native reference must not be overridden")
    data = core.load()
    raw = core.encoded(data)
    if gzip.decompress((source / "queries.json.gz").read_bytes()) != raw:
        raise ValueError("Prepared county queries disagree with complete native reconstruction")
    inputs = json.loads((source / "inputs.json").read_bytes())
    paths = {core.VERSION + "/" + name for name in inputs["files"]} | {
        core.VERSION + "/" + name for name in ["inputs.json", "queries.json.gz", "summary.json"]}
    paths.update([
        "scripts/alabama-county-counts.py", "scripts/test-alabama-county-counts.py",
        "scripts/alabama-county-counts.mjs", "scripts/alabama-county-counts.test.mjs",
        "scripts/build-alabama-county-inputs.py", "scripts/prepare-alabama-county-counts.py",
        "scripts/package-alabama-county-counts.py", "scripts/check-alabama-county-counts-browser.py",
        "scripts/additional-participation.mjs", "scripts/local_reference_staging.py",
        "scripts/test-local-reference-staging.py", "scripts/check-minnesota-followup-browser.py",
        "scripts/check-participation-2026-drilldowns-browser.py",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js",
    ])
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, expected in inputs["files"].items():
        if pin(members[core.VERSION + "/" + name]) != expected:
            raise ValueError("Changed sufficient original: " + name)
    tables = {"all67-native-county-counts.csv": data["county_decisions"],
              "all2211-native-county-pair-decisions.csv": data["all2211_county_pair_decisions"]}
    for name, rows in tables.items():
        members[name] = csv_bytes(rows)
    members["queries.json"] = raw
    members["full-native-workbook.xlsx"] = gzip.decompress((source / "originals/full-native-export.gz").read_bytes())
    members["AL-full-county-reference.geojson.gz"] = (source / "AL-full-county-reference.geojson.gz").read_bytes()
    for name, proof in proofs.items():
        members[name] = core.encoded(proof)
    members["package.json"] = b'{"private":true,"type":"module"}\n'
    members["requirements.txt"] = b"# Numerical reader: Python3.9+ standard library; Node22+ built-ins.\n# Independent geometry verification:\nshapely==2.0.7\n"
    members["reproduce.py"] = b"""import importlib.util
from pathlib import Path
import sys
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('alabama_counties',root/'scripts/alabama-county-counts.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
sys.stdout.buffer.write(core.encoded(core.load(root)))
"""
    members["README.txt"] = b"""ALABAMA:67 NATIVE COUNTY BALLOTS CAST AND EXPLICIT COUNTY REFERENCE JOINS

COMPLETE CONTENTS
All11 sufficient input pins: complete byte-exact native workbook, selected
factual fields from all67 county pages and their separate state page, safe
receipts, prior full county queries and reader, full2026 Census county
reference and all2211 original pair decisions. Every new67-county query,
full pair query, code, tests, checksum and exact offline reproduction is
included. The workbook is also supplied in full as an XLSX. Publisher
application code and acquisition headers are excluded; the selected native
page fields contain actual counts/registrations/percentages/clocks, not
metadata alone. Earlier full source releases and routes stay available.

SOURCE MEANING
The native Statistics column is Ballots Cast, not candidate votes.
All67 source county counts sum to the separately printed state1,693,621;
separate native registrations sum to3,852,947. Both are a source snapshot,
not independent unique people or certified final turnout. Each county's
printed percentage and clock remain literal; timezone is unknown.
Registrations are retained without qualifying the electorate frame.
ALL analysis rates remain null; no population, demographic, first-ever,
eligibility, death, migration or nonparticipation residual is inferred.
The source reports every county's native precinct count, but no new
precinct records, precinct boundaries or precinct rates are approved.

IDENTITY AND MODES
Native county codes are election ordinals, NOT FIPS:01 Jefferson joins
01073, not01001. Names join with only case/explicit County-suffix treatment;
native and reference names remain separate. The full unchanged2026 Census
county reference has67 valid unrepaired shapes and zero positive overlap
across all2211 pairs (coordinate-degrees-squared, not geodesic areas).
Old county IDs and counts remain compatible. The live opt-in selects this
reviewed native frame under available/official-source modes. All-method
counts never fill unsupported early/returned frames. Frozen legacy readers
remain unchanged. Included local acceptance is NOT native Pages/live proof.

REPRODUCE IN AN EMPTY DIRECTORY
Extract every ZIP member; no download or source acquisition is required.
  python reproduce.py > reproduced-queries.json
The output must equal queries.json byte-for-byte.
  python scripts/test-alabama-county-counts.py
  node --test --test-name-pattern="all67 native|native frame rejects" scripts/alabama-county-counts.test.mjs
The first two Node tests require built-ins only. The optional third
integration test/browser tests require the full website/other source
families and existing browser tooling; do not install research packages
or claim they are reproduced by this numerical-only archive.
manifest.json pins every other archive member. The raw original workbook,
selected factual inputs and full county reference remain inside the ZIP.
"""
    members["manifest.json"] = core.encoded(dict(summary=data["summary"],
        sufficient_inputs=11, files={name: pin(body) for name, body in sorted(members.items())}))
    assets = ["queries.json", *tables, "full-native-workbook.xlsx",
              "AL-full-county-reference.geojson.gz", "requirements.txt", "README.txt", "manifest.json"]
    args.output.mkdir(parents=True)
    for name in assets:
        (args.output / name).write_bytes(members[name])
    with zipfile.ZipFile(args.output / "complete-analysis.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)
    body = (args.output / "complete-analysis.zip").read_bytes()
    receipt = dict(url=inputs["complete_download_url"], **pin(body), members=len(members),
        sufficient_inputs=11, standalone_full_assets=len(assets) + 1,
        complete_county_decisions=67, native_ballots=1693621, native_registered=3852947,
        complete_pair_decisions=2211, positive_overlap_pairs=0,
        analysis_rates_approved=False, new_precinct_coverage_approved=False,
        source_counts_repaired=False, candidate_votes_used_as_ballots=False)
    (source / "download.json").write_bytes(core.encoded(receipt))
    print(json.dumps(dict(status="PASS_complete_native_analysis_package_NOT_native_website_acceptance", **receipt)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["output", "browser", "navigation", "preserved", "size"]:
        parser.add_argument("--" + name, type=Path, required=True)
    build(parser.parse_args())

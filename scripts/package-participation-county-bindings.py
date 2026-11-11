"""Package a reference-only extension with all three whole predecessor packets."""

import argparse
import importlib.util
import json
from pathlib import Path
import zipfile


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "inputs", "runtime", "base-counts", "base-native", "count-science",
                 "native-science", "context-science", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a fresh complete packet")
    helper = module(args.source / "scripts/package-participation-count-extension.py")
    verifier = module(args.source / "scripts/verify-participation-county-bindings.py")
    proof = verifier.verify(args.base_counts, args.base_native, args.runtime, args.inputs)
    names = [
        "scripts/extend-participation-county-bindings.mjs", "scripts/extend-participation-county-bindings.test.mjs",
        "scripts/participation-native-bindings.test.mjs", "scripts/participation-counts.test.mjs",
        "scripts/verify-participation-county-bindings.py", "scripts/package-participation-county-bindings.py",
        "scripts/reproduce-participation-county-bindings.py", "scripts/package-participation-count-extension.py",
        "scripts/reproduce-participation-count-extension.py", "scripts/deny-participation-count-network.mjs",
    ]
    members = helper.source_files(args.source, names)
    members["code/package.json"] = helper.encoded(dict(private=True, type="module"))
    members.update({
        "inputs/base-count-science.zip": args.count_science.read_bytes(),
        "inputs/base-native-science.zip": args.native_science.read_bytes(),
        "inputs/base-context-science.zip": args.context_science.read_bytes(),
        "checks/independent-binding-verification.json": helper.encoded(proof),
        "results/county-binding-queries.json": (args.runtime / "county-binding-queries.json").read_bytes(),
        "results/reference.json": (args.runtime / "reference.json").read_bytes(),
    })
    for name in ("recipe.json", "reference.json", "previous-review.json", "native-facts.json"):
        members["inputs/" + name] = (args.inputs / name).read_bytes()
    versions = {}
    for family in ("counts", "native"):
        root = args.runtime / family
        descriptor = json.loads((root / "dataset.json").read_bytes())
        versions[family] = descriptor["version"]
        for name in [*descriptor["files"], "dataset.json"]:
            members["runtime/" + family + "/" + name] = (root / name).read_bytes()
    members["README.txt"] = (
        "COMPLETE CONTEXTUAL COUNTY-BINDING EXTENSION\n\n"
        "Run: python3 code/scripts/reproduce-participation-county-bindings.py --package . --output /fresh/path\n"
        "Requires Python 3.9+ and Node.js 22, no installation or acquisition.\n"
        "Includes whole previous count, native-binding and contextual-identity scientific packets,\n"
        "full unchanged county geometry, complete native facts and original exact-record-hash oracle,\n"
        "all new code/tests, complete 21-county and four-mode binding queries and both runtime datasets.\n"
        "Offline reproduction copies accepted predecessor runtime bytes, not previous scientific reductions.\n"
        "Nineteen accepted contextual identities are retained; two newly supported whole-county source\n"
        "identities reuse the very same 2024 county features. No geometry is repaired or recomputed.\n"
        "Counts, denominators, null rates, reporting clocks, source fields and conflicts are unchanged.\n"
        "This is contextual county identity, not certified 2026 legal election/precinct boundaries,\n"
        "individual voter histories, final turnout or allocation of statewide survey estimates.\n"
        "Existing early/returned frames and all other states/native layers remain untouched.\n"
        "Archived descriptors intentionally omit final complete-download metadata to avoid a ZIP self-hash.\n"
        "Activation requires the actual immutable/anonymously verified package and browser catalog contract.\n"
    ).encode()
    manifest = dict(contract="participation.complete_county_binding_extension.v1",
        source_commit=args.commit, versions=versions,
        files={name: helper.pin(body) for name, body in sorted(members.items())},
        all_three_predecessor_packets_retained=True, new_geometry=False, source_counts_changed=False)
    members["manifest.json"] = helper.encoded(manifest)
    args.output.mkdir(parents=True)
    with zipfile.ZipFile(args.output / "complete-analysis.zip", "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, body)
    for name in ("manifest.json", "README.txt", "results/county-binding-queries.json",
                 "checks/independent-binding-verification.json"):
        (args.output / Path(name).name).write_bytes(members[name])
    summary = dict(proof, status="complete_county_binding_science_prepared",
        archive=helper.pin((args.output / "complete-analysis.zip").read_bytes()),
        members=len(members), versions=versions)
    (args.output / "package-receipt.json").write_bytes(helper.encoded(summary))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

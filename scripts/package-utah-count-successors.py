"""Package all Utah successor inputs, previous science, code, queries and runtime bytes."""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile


PARENT_SHA256 = "9039c32cb65bc42f0c412137ca413f7d4dc224250eb404a8fa6df4004da81d91"


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def query_members(runtime):
    index = json.loads((runtime / "counts/index.json").read_bytes())
    shard = json.loads(gzip.decompress((runtime / "counts" / index["states"]["UT"]["file"]).read_bytes()))
    rows = {row["id"]: row for row in shard["records"]}
    selected = [rows[key] for key in shard["views"]["official"]["counties"]]
    stream = io.StringIO(newline="")
    columns = ["view", "county", "source_id", "count", "status", "native_measure",
        "analysis_rate", "denominator", "native_update", "timezone", "source_url"]
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for mode, frame in sorted(shard["views"].items()):
        for identity in frame["counties"]:
            row = rows[identity]
            writer.writerow(dict(view=mode, county=row["geography"]["name"], source_id=row["source"]["id"],
                count=row["count"]["value"], status=row["count"]["status"],
                native_measure=row["measure"]["literal"], analysis_rate=row["view"].get("reported_pct"),
                denominator=row["denominator"]["value"] if row["denominator"] else None,
                native_update=row["source_clock"]["literal"], timezone=row["source_clock"]["timezone"],
                source_url=row["source"]["url"]))
    return {
        "results/complete-utah-county-query.json": encoded(selected),
        "results/complete-utah-source-history.json": encoded(shard["records"]),
        "results/complete-utah-mode-query.csv": stream.getvalue().encode(),
        "results/complete-county-reference-query.json": (runtime / "county-binding-queries.json").read_bytes(),
    }


def add_dataset(members, prefix, root):
    descriptor = json.loads((root / "dataset.json").read_bytes())
    for name in [*descriptor["files"], "dataset.json"]:
        members[prefix + "/" + name] = (root / name).read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "runtime", "base-counts", "base-native", "predecessor",
            "fixture-counts", "fixture-binding-counts", "fixture-binding-native", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.output.exists() or pin(args.predecessor.read_bytes())["sha256"] != PARENT_SHA256:
        raise ValueError("Use a fresh output and the entire accepted predecessor packet")
    verifier = module(root / "scripts/verify-utah-count-successors.py")
    proof = verifier.verify(args.base_counts, args.base_native, args.runtime, args.inputs, args.commit)
    helper = module(root / "scripts/package-participation-count-extension.py")
    names = [
        "scripts/extend-participation-counts.mjs", "scripts/extend-participation-counts.test.mjs",
        "scripts/extend-participation-county-bindings.mjs", "scripts/extend-participation-county-bindings.test.mjs",
        "scripts/extend-participation-partial-county-bindings.test.mjs", "scripts/participation-counts.test.mjs",
        "scripts/freeze-utah-successors.py", "scripts/prepare-utah-count-successors.py",
        "scripts/verify-utah-count-successors.py", "scripts/package-utah-count-successors.py",
        "scripts/reproduce-utah-count-successors.py", "scripts/package-participation-count-extension.py",
        "scripts/deny-participation-count-network.mjs",
    ]
    members = helper.source_files(root, names)
    members["code/package.json"] = encoded(dict(private=True, type="module"))
    members["inputs/complete-predecessor-science.zip"] = args.predecessor.read_bytes()
    for name in ("native-facts.json", "extension.json", "reference.json", "previous-review.json", "recipe.json"):
        members["inputs/" + name] = (args.inputs / name).read_bytes()
    facts_root = root / "data/participation-count-successors/20261111-ut-01"
    for name in ("native-verification.json", "summary-transcription.json"):
        members["inputs/" + name] = (facts_root / name).read_bytes()
    for family in ("counts", "native"):
        add_dataset(members, "runtime/" + family, args.runtime / family)
    for prefix, directory in (("fixtures/counts", args.fixture_counts),
            ("fixtures/binding-counts", args.fixture_binding_counts),
            ("fixtures/binding-native", args.fixture_binding_native)):
        add_dataset(members, prefix, directory)
    for prefix, directory, filenames in [
        ("fixtures/table-inputs", root / "data/participation-count-extensions/20261111-nj-gap-01",
            ("native-facts.json", "extension.json")),
        ("fixtures/binding-inputs", root / "data/participation-county-bindings/20261111-nj-01",
            ("native-facts.json", "recipe.json", "reference.json", "previous-review.json")),
    ]:
        for name in filenames:
            members[prefix + "/" + name] = (directory / name).read_bytes()
    members.update(query_members(args.runtime))
    members["checks/independent-verification.json"] = encoded(proof)
    members["README.txt"] = (
        "COMPLETE UTAH MISSING-COUNT SUCCESSOR SCIENCE\n\n"
        "Piute737, Kane3395, Millard4149, Cache42549 are explicit native Ballots Cast - Total,\n"
        "not candidate selections, processing subtotals or verified unique people.\n"
        "The entire immutable predecessor scientific archive is included, not just its manifest.\n"
        "All complete new factual cells, errors/blanks, source clocks, inputs/code/tests/query/runtime\n"
        "are retained. Unused certification identities and native presentation are not redistributed.\n"
        "Reproduce: python3 code/scripts/reproduce-utah-count-successors.py --package . --output /fresh/path\n"
        "Requires Python3.9+ and Node22; no installation, source acquisition or prior reductions.\n"
        "Reproduction reuses accepted prior runtime bytes, blocks network/Node child commands,\n"
        "runs22focused/contract regression tests, then checks every new runtime/query byte.\n"
        "All147 old UT records and six source holds remain; only four selected missing rows change.\n"
        "Nineteen accepted contextual identities and all prior rates/early/mail frames are preserved.\n"
        "New fractions, certification, statewide totals and precinct allocations remain unqualified.\n"
        "The same2024 county context, including native overlaps, is not repaired or simplified.\n"
        "The denied Cache workbook route remains stopped; the distinct summary PDF supplies its count.\n"
        "Runtime descriptors have null complete_download until verified external activation,\n"
        "avoiding a self-referential ZIP hash. Activation does not require a website build.\n"
    ).encode()
    manifest = dict(contract="participation.complete_utah_count_successors.v1",
        source_commit=args.commit, predecessor_sha256=PARENT_SHA256,
        files={name: pin(body) for name, body in sorted(members.items())},
        original_reductions_repeated=False, full_query_download=True,
        original_source_presentation_redistributed=False)
    members["manifest.json"] = encoded(manifest)
    args.output.mkdir(parents=True)
    with zipfile.ZipFile(args.output / "complete-analysis.zip", "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(members.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 11, 0, 0, 0))
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o100644 << 16
            archive.writestr(info, body)
    for name in ["manifest.json", "inputs/native-facts.json", "checks/independent-verification.json",
            *query_members(args.runtime)]:
        (args.output / Path(name).name).write_bytes(members[name])
    summary = dict(status="complete_utah_count_successor_packet_prepared", members=len(members),
        archive=pin((args.output / "complete-analysis.zip").read_bytes()), independent=proof)
    (args.output / "package-receipt.json").write_bytes(encoded(summary))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

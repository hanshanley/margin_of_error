"""Package complete incremental count inputs, prior science, code and query results."""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import zipfile


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def query_results(runtime):
    index = json.loads((runtime / "index.json").read_bytes())
    query = {}
    for code in sorted(index["states"]):
        shard = json.loads(gzip.decompress((runtime / index["states"][code]["file"]).read_bytes()))
        extension_ids = {row["id"] for row in shard["records"]
            if row["source"].get("classification") == "public_aggregate"
            and row["source"].get("selector", {}).get("report")}
        if not extension_ids:
            continue
        by_id = {row["id"]: row for row in shard["records"]}
        query[code] = dict(records=[by_id[key] for key in shard["views"]["available"]["counties"]],
            all_mode_bindings=shard["views"],
            qualification="Mixed native source clocks; individual source-defined observations, not a statewide turnout total.")
    buffer = io.StringIO(newline="")
    columns = ["state", "county", "count", "measure", "native_clock", "timezone", "reported_pct",
        "denominator", "source", "complete_download"]
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for code, state in sorted(query.items()):
        for row in state["records"]:
            writer.writerow(dict(state=code, county=row["geography"]["name"], count=row["count"]["value"],
                measure=row["measure"]["literal"], native_clock=row["source_clock"]["literal"],
                timezone=row["source_clock"]["timezone"], reported_pct=row["view"].get("reported_pct"),
                denominator=row["denominator"]["value"] if row["denominator"] else None,
                source=row["source"]["url"], complete_download=row["view"].get("complete_download_url")))
    return {"results/county-query.json": encoded(query), "results/county-query.csv": buffer.getvalue().encode()}


def source_files(root):
    names = {
        "scripts/extend-participation-counts.mjs", "scripts/extend-participation-counts.test.mjs",
        "scripts/participation-counts.test.mjs", "scripts/freeze-participation-table-inputs.py",
        "scripts/verify-participation-count-extension.py", "scripts/package-participation-count-extension.py",
        "scripts/reproduce-participation-count-extension.py", "scripts/deny-participation-count-network.mjs",
    }
    queue = list(names)
    while queue:
        name = queue.pop()
        if not name.endswith((".js", ".mjs")):
            continue
        for target in re.findall(r'from\s+["\']([^"\']+)["\']', (root / name).read_text()):
            if not target.startswith("."):
                continue
            relative = (root / name).parent.joinpath(target).resolve().relative_to(root.resolve()).as_posix()
            if relative not in names:
                names.add(relative)
                queue.append(relative)
    return {"code/" + name: (root / name).read_bytes() for name in sorted(names)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "input-directory", "base-archive", "prior-query", "runtime", "native-proof", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("A scientific package cannot overwrite an accepted output")
    facts = json.loads((args.input_directory / "native-facts.json").read_bytes())
    recipe = json.loads((args.input_directory / "extension.json").read_bytes())
    verifier = module(args.source / "scripts/verify-participation-count-extension.py")
    proof = verifier.verify(args.base_archive, args.runtime, facts, recipe)
    members = source_files(args.source)
    members["code/package.json"] = encoded(dict(private=True, type="module"))
    members.update({
        "inputs/base-count-migration.zip": args.base_archive.read_bytes(),
        "inputs/prior-source-query.zip": args.prior_query.read_bytes(),
        "checks/independent-native-vectors.json": args.native_proof.read_bytes(),
        "checks/independent-runtime.json": encoded(proof),
    })
    for name in ("native-facts.json", "extension.json", "native-requests.json"):
        members["inputs/" + name] = (args.input_directory / name).read_bytes()
    descriptor = json.loads((args.runtime / "dataset.json").read_bytes())
    for name in [*descriptor["files"], "dataset.json"]:
        members["runtime/" + name] = (args.runtime / name).read_bytes()
    members.update(query_results(args.runtime))
    members["README.txt"] = (
        "Complete native-table participation count extension\n\n"
        "Run: python3 code/scripts/reproduce-participation-count-extension.py --package . --output /fresh/path\n"
        "Requires Python 3 and Node.js 22; no third-party packages or network access.\n"
        "The entire previous count-migration and prior source-query scientific archives are retained.\n"
        "All new factual table cells, blanks, exact selectors, code and results are included.\n"
        "Native PDF/HTML presentation and acquisition/session headers are not redistributed.\n"
        "Official public source URLs and cryptographic original-file pins remain in the full facts.\n"
        "The optional native-table freezer uses pdfplumber and MuPDF against those original reports.\n"
        "Offline reproduction starts from the complete prior archive runtime, not prior reductions.\n"
        "The archived runtime descriptor is preactivation: its complete_download is intentionally null.\n"
        "This avoids a self-referential ZIP hash; the final public catalog carries the verified ZIP pin.\n"
        "Essex 225368 and Hudson 213051 are EV+ED+mail-tallied subtotals, not unique voters,\n"
        "certified complete-election ballots, turnout rates, or independently mapped precinct data.\n"
        "Conflicting nonselected cells, excluded provisionals, unknown clocks and blank rows remain literal.\n"
        "Do not sum mixed source-clock observations into a claimed statewide observed ballot total.\n"
    ).encode()
    manifest = dict(contract="participation.complete_count_extension.v1", source_commit=args.source_commit,
        files={name: pin(body) for name, body in sorted(members.items())},
        runtime_version=descriptor["version"], full_query_download=True,
        prior_scientific_archives_retained=True, native_presentation_redistributed=False)
    members["manifest.json"] = encoded(manifest)
    args.output.mkdir(parents=True)
    with zipfile.ZipFile(args.output / "complete-analysis.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, body)
    for name in ("inputs/native-facts.json", "inputs/extension.json", "results/county-query.json",
                 "results/county-query.csv", "manifest.json", "README.txt"):
        (args.output / Path(name).name).write_bytes(members[name])
    summary = dict(status="complete_scientific_packet_created", members=len(members),
        archive=pin((args.output / "complete-analysis.zip").read_bytes()), **proof)
    (args.output / "package-receipt.json").write_bytes(encoded(summary))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

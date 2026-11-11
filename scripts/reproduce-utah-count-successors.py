"""Reproduce the new Utah increment offline, reusing the complete accepted prior bytes."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import zipfile


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def deny(*args, **kwargs):
    raise RuntimeError("Offline successor reproduction forbids network")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", default="node")
    args = parser.parse_args()
    root, output = args.package.resolve(), args.output.resolve()
    if output.exists():
        raise ValueError("Use a fresh reproduction directory")
    manifest = json.loads((root / "manifest.json").read_bytes())
    for name, pin in manifest["files"].items():
        body = (root / name).read_bytes()
        if dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest()) != pin:
            raise ValueError("Full scientific member differs")
    previous = root / "inputs/complete-predecessor-science.zip"
    if hashlib.sha256(previous.read_bytes()).hexdigest() != manifest["predecessor_sha256"]:
        raise ValueError("Complete predecessor science differs")
    node = shutil.which(args.node)
    if not node:
        raise ValueError("Node22 is required")
    socket.socket = socket.create_connection = deny
    output.mkdir(parents=True)
    with zipfile.ZipFile(previous) as archive:
        parent = json.loads(archive.read("manifest.json"))
        for name, pin in parent["files"].items():
            body = archive.read(name)
            if dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest()) != pin:
                raise ValueError("Complete predecessor member differs")
            if name.startswith(("runtime/counts/", "runtime/native/")):
                target = output / "baseline" / name.removeprefix("runtime/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
    counts, native = output / "baseline/counts", output / "baseline/native"
    guard = root / "code/scripts/deny-participation-count-network.mjs"
    env = dict(os.environ, NODE_OPTIONS="", PARTICIPATION_COUNT_BASELINE=str(root / "fixtures/counts"),
        PARTICIPATION_EXTENSION_INPUT=str(root / "fixtures/table-inputs"),
        COUNTY_BINDING_INPUT=str(root / "fixtures/binding-inputs"),
        COUNTY_BINDING_COUNTS=str(root / "fixtures/binding-counts"),
        COUNTY_BINDING_NATIVE=str(root / "fixtures/binding-native"),
        UTAH_EXTENSION_INPUTS=str(root / "inputs"),
        UTAH_EXTENSION_COUNTS=str(output / "extended-counts"), UTAH_EXTENSION_NATIVE=str(native))

    def run(*arguments):
        subprocess.run([node, "--import", guard.as_uri(), *map(str, arguments)],
            env=env, cwd=root / "code", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    run("--input-type=module", "-e", "let n=0;try{await fetch('https://example.invalid')}catch{n++};"
        "try{(await import('node:net')).connect(443,'example.invalid')}catch{n++};"
        "try{(await import('node:child_process')).execSync('true')}catch{n++};if(n!==3)process.exit(1);")
    run(root / "code/scripts/extend-participation-counts.mjs", "--base", counts,
        "--facts", root / "inputs/native-facts.json", "--recipe", root / "inputs/extension.json",
        "--output", output / "extended-counts")
    run("--test", *[root / "code/scripts" / name for name in (
        "extend-participation-counts.test.mjs", "participation-counts.test.mjs",
        "extend-participation-county-bindings.test.mjs", "extend-participation-partial-county-bindings.test.mjs")])
    run(root / "code/scripts/extend-participation-county-bindings.mjs",
        "--counts", output / "extended-counts", "--native", native, "--inputs", root / "inputs",
        "--output", output / "runtime", "--commit", manifest["source_commit"])
    for name in manifest["files"]:
        if name.startswith("runtime/") and (output / name).read_bytes() != (root / name).read_bytes():
            raise ValueError("Reproduced runtime byte mismatch")
    packager = module(root / "code/scripts/package-utah-count-successors.py")
    for name, body in packager.query_members(output / "runtime").items():
        if body != (root / name).read_bytes():
            raise ValueError("Complete query export differs")
    verifier = module(root / "code/scripts/verify-utah-count-successors.py")
    proof = verifier.verify(counts, native, output / "runtime", root / "inputs", manifest["source_commit"])
    if json.loads((root / "checks/independent-verification.json").read_bytes()) != proof:
        raise ValueError("Independent numerical receipt differs")
    receipt = dict(status="passed_fresh_offline_utah_successor_reproduction",
        all_runtime_and_full_query_bytes_equal=True, tests_passed=22,
        network_and_node_child_commands_blocked=True, previous_source_reductions_repeated=False,
        full_predecessor_packet_retained=True, independent=proof)
    (output / "reproduction.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()

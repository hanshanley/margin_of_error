"""Reproduce a complete count extension offline, preserving prior accepted science."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import subprocess
import zipfile


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def safe_extract(archive, target):
    with zipfile.ZipFile(archive) as source:
        if len(set(source.namelist())) != len(source.namelist()):
            raise ValueError("Duplicate archive members")
        for name in source.namelist():
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or path.as_posix() != name:
                raise ValueError("Unsafe scientific archive member")
        source.extractall(target)


def deny(*args, **kwargs):
    raise RuntimeError("Offline reproduction forbids network access")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", default="node")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a fresh reproduction output")
    root = args.package.resolve()
    manifest = json.loads((root / "manifest.json").read_bytes())
    for name, expected in manifest["files"].items():
        body = (root / name).read_bytes()
        if dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest()) != expected:
            raise ValueError("Changed complete scientific member: " + name)
    node = shutil.which(args.node)
    if not node:
        raise ValueError("Node.js is required for the existing canonical count contract")
    socket.socket = deny
    socket.create_connection = deny
    args.output.mkdir(parents=True)
    baseline = args.output / "baseline"
    safe_extract(root / "inputs/base-count-migration.zip", baseline)
    guard = root / "code/scripts/deny-participation-count-network.mjs"
    compiled = args.output / "runtime"
    environment = dict(os.environ, NODE_OPTIONS="", PYTHONHASHSEED=os.environ.get("PYTHONHASHSEED", "0"),
        PARTICIPATION_EXTENSION_INPUT=str(root / "inputs"),
        PARTICIPATION_COUNT_BASELINE=str(baseline / "runtime"))
    commands = [
        [node, "--import", guard.as_uri(), "--input-type=module", "-e",
         "let n=0;try{await fetch('https://example.invalid')}catch{n++};"
         "try{(await import('node:net')).connect(443,'example.invalid')}catch{n++};"
         "try{(await import('node:child_process')).execSync('true')}catch{n++};"
         "if(n!==3)process.exit(1);"],
        [node, "--import", guard.as_uri(), str(root / "code/scripts/extend-participation-counts.test.mjs")],
        [node, "--import", guard.as_uri(), str(root / "code/scripts/participation-counts.test.mjs")],
        [node, "--import", guard.as_uri(), str(root / "code/scripts/extend-participation-counts.mjs"),
         "--base", str(baseline / "runtime"), "--facts", str(root / "inputs/native-facts.json"),
         "--recipe", str(root / "inputs/extension.json"), "--output", str(compiled)],
    ]
    for command in commands:
        subprocess.run(command, env=environment, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for name in manifest["files"]:
        if name.startswith("runtime/") and (args.output / name).read_bytes() != (root / name).read_bytes():
            raise ValueError("Reproduced runtime byte mismatch: " + name)
    helper = module(root / "code/scripts/package-participation-count-extension.py")
    for name, body in helper.query_results(compiled).items():
        if body != (root / name).read_bytes():
            raise ValueError("Reproduced full query mismatch: " + name)
    verifier = module(root / "code/scripts/verify-participation-count-extension.py")
    proof = verifier.verify(root / "inputs/base-count-migration.zip", compiled,
        json.loads((root / "inputs/native-facts.json").read_bytes()),
        json.loads((root / "inputs/extension.json").read_bytes()))
    result = dict(status="passed_fresh_offline_count_extension_reproduction",
        all_runtime_and_query_bytes_equal=True, python_network_blocked=True,
        all_11_contract_tests_passed_offline=True,
        node_network_and_subprocess_blocked_and_tested=True,
        earlier_scientific_reductions_repeated=False, independent_verification=proof)
    (args.output / "reproduction.json").write_bytes(helper.encoded(result))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
